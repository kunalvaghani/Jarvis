"""Offline, resource-limited Docker workspace. Effects are never auto-replayed."""
import hashlib
import json
from pathlib import Path
import re
import threading
import time
import uuid

from .repo_sandbox import RepositorySandbox
from .skill_memory import atomic, linked

IMAGE = 'jarvis-deerflow-runtime:1'


class SandboxJob:
    def __init__(self, base, identifier=None):
        self.base = Path(base).resolve(strict=True)
        self.identifier = identifier or uuid.uuid4().hex
        if not re.fullmatch('[a-f0-9]{32}', self.identifier):
            raise ValueError('Invalid sandbox job identifier.')
        self.root = self.base / '.jarvis-runtime/deerflow/jobs' / self.identifier
        self.name = 'jarvis-deerflow-' + self.identifier
        self.runtime = RepositorySandbox(IMAGE)
        self.lock = threading.RLock()
        self.state = {'id': self.identifier, 'status': 'created', 'calls': [], 'container': self.name}
        import os
        import psutil
        self.state.update(owner_pid=os.getpid(), owner_started=psutil.Process().create_time())
        if identifier:
            self.state = json.loads((self.root / 'state.json').read_text(encoding='utf-8'))
            if self.state.get('id') != identifier:
                raise ValueError('Sandbox checkpoint identity mismatch.')
        self.closed = False
        self.storage_stop = threading.Event()

    def save(self):
        atomic(self.root / 'state.json', json.dumps(self.state, indent=2))

    def create(self):
        image = json.loads(self.runtime.cli(['image', 'inspect', IMAGE]))[0]
        if image.get('Os') != 'linux' or image.get('Config', {}).get('Labels', {}).get('org.jarvis.deerflow-runtime') != '1':
            raise ValueError('Reviewed DeerFlow sandbox image unavailable; run sandbox setup.')
        self.state['image'] = image['Id']
        for name in ('workspace', 'outputs', 'uploads'):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        skills = (self.base / 'integrations/deer-flow-upstream/skills/public').resolve(strict=True)
        args = ['run', '-d', '--pull', 'never', '--name', self.name,
            '--label', 'org.jarvis.deerflow-job=' + self.identifier,
            '--network', 'none', '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '--memory', '2g', '--memory-swap', '2g', '--cpus', '2', '--pids-limit', '128',
            '--ulimit', 'fsize=67108864:67108864', '--ulimit', 'nofile=128:128',
            '--user', '65534:65534', '--log-driver', 'none',
            '--tmpfs', '/tmp:rw,exec,nosuid,nodev,size=256m,mode=1777',
            '--workdir', '/mnt/user-data/workspace']
        for folder in ('workspace', 'outputs', 'uploads'):
            source = self.root / folder
            if linked(source) or ',' in str(source):
                raise ValueError('Sandbox mount path is unsupported.')
            args += ['--mount', 'type=bind,src=' + str(source) + ',dst=/mnt/user-data/' + folder + (',readonly' if folder == 'uploads' else '')]
        args += ['--mount', 'type=bind,src=' + str(skills) + ',dst=/mnt/skills/public,readonly']
        voices = self.base / 'models/voices/kokoro'
        for name in ('kokoro-v1.0.onnx', 'voices-v1.0.bin'):
            path = voices / name
            if path.is_file() and not linked(path):
                args += ['--mount', 'type=bind,src=' + str(path.resolve()) + ',dst=/mnt/models/kokoro/' + name + ',readonly']
        for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY', 'http_proxy', 'https_proxy', 'all_proxy', 'no_proxy'):
            args += ['--env', key + '=']
        args += [image['Id'], 'sleep', 'infinity']
        self.state['status'] = 'starting'
        self.save()
        self.runtime.cli(args, timeout=30)
        self.state['status'] = 'running'
        self.save()
        threading.Thread(target=self._storage_guard, name='jarvis-sandbox-storage', daemon=True).start()
        return self

    def _storage_guard(self):
        import os
        while not self.storage_stop.wait(.5):
            total = count = 0
            try:
                for folder in ('workspace', 'outputs'):
                    for directory, dirs, files in os.walk(self.root / folder, followlinks=False):
                        dirs[:] = [name for name in dirs if not linked(Path(directory) / name)]
                        for name in files:
                            path = Path(directory) / name
                            if not linked(path):
                                total += path.stat().st_size
                                count += 1
                            if total > 256*1024*1024 or count > 1000:
                                if not self.closed:
                                    info = self.owned()
                                    self.runtime.cli(['kill', info['Id']], timeout=8)
                                return
            except (OSError, ValueError):
                continue

    def stage_inputs(self, project, names):
        from .agent_context import scoped
        from .repo_acquisition import SENSITIVE
        allowed = {'.csv', '.json', '.txt', '.md', '.py', '.sql', '.png', '.jpg', '.jpeg', '.pdf', '.pptx', '.xlsx', '.wav', '.mp4', '.html', '.js'}
        if not isinstance(names, list) or len(names) > 10 or any(not isinstance(n, str) for n in names) or len(set(names)) != len(names):
            raise ValueError('Select up to ten explicit relative input files.')
        total = 0
        rows = []
        for name in names:
            if any(part.startswith('.') for part in Path(name).parts) or SENSITIVE.search(name):
                raise ValueError('Credential/hidden paths cannot enter the sandbox.')
            source = scoped(project, name)
            if not source.is_file() or source.suffix.lower() not in allowed:
                raise ValueError('Choose a supported explicit data/source/media file.')
            destination = scoped(self.root / 'uploads', name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with source.open('rb') as reader, destination.open('xb') as writer:
                while True:
                    chunk = reader.read(1024*1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > 64*1024*1024:
                        raise ValueError('Sandbox inputs exceed the 64 MB budget.')
                    writer.write(chunk)
            rows.append({'path': '/mnt/user-data/uploads/' + Path(name).as_posix(), 'bytes': destination.stat().st_size})
        return rows

    def owned(self):
        info = json.loads(self.runtime.cli(['inspect', self.name], timeout=5))[0]
        if (info.get('Image') != self.state['image'] or
                info.get('Config', {}).get('Labels', {}).get('org.jarvis.deerflow-job') != self.identifier):
            raise ValueError('Container ownership changed; no operation dispatched.')
        return info

    def execute(self, command, timeout=60, cancelled=lambda: False):
        if not isinstance(command, str) or not 1 <= len(command) <= 20000:
            raise ValueError('Sandbox command is missing or too large.')
        if self.closed:
            raise ValueError('Sandbox was deliberately closed.')
        if cancelled():
            raise ValueError('Sandbox cancelled before command dispatch.')
        with self.lock:
            if any(row['command'] == command for row in self.state['calls']):
                raise ValueError('Completed or uncertain command cannot be automatically repeated.')
            if len(self.state['calls']) >= 20 or self.state['status'] == 'uncertain':
                raise ValueError('Sandbox requires fresh inspection or exceeded its action budget.')
            if not self.owned().get('State', {}).get('Running'):
                self.state['status'] = 'uncertain'
                self.save()
                raise ValueError('Sandbox stopped; command not replayed.')
            row = {'command': command, 'status': 'attempted', 'started': time.time()}
            self.state['calls'].append(row)
            self.save()
            try:
                # Linux timeout fences the process inside the container as well
                # as the Docker client deadline. No host shell is involved.
                raw = self.runtime.cli(['exec', self.name, 'timeout', '--kill-after=2', str(min(120, max(1, timeout))),
                    'bash', '-lc', command], cancelled, timeout=min(120, max(1, timeout)) + 8)
                row.update(status='completed', output_sha256=hashlib.sha256(raw).hexdigest(), finished=time.time())
                self.save()
                return raw.decode('utf-8', errors='replace')[-20000:]
            except (ValueError, OSError) as exc:
                row.update(status='uncertain', finished=time.time())
                row['diagnostic'] = str(exc)[-1600:]
                self.state['status'] = 'uncertain'
                self.save()
                raise ValueError('Sandbox command failed or became uncertain; inspect outputs, no automatic replay.') from None

    def observe(self, action, value='.', content=''):
        if action == 'sandbox_command':
            if content:
                raise ValueError('Use value for the exact sandbox command.')
            return self.execute(value)
        if action == 'sandbox_write':
            if self.closed or self.state['status'] == 'uncertain':
                raise ValueError('Sandbox effects paused; inspect existing state first.')
            if not isinstance(content, str) or not content or len(content.encode()) > 100000:
                raise ValueError('Sandbox text write exceeds budget.')
            path = self.path(value)
            if path.exists():
                raise ValueError('Sandbox write would overwrite; use a new file or an explicit confined command.')
            path.parent.mkdir(parents=True, exist_ok=True)
            row = {'command': 'write:' + value, 'status': 'attempted', 'started': time.time()}
            self.state['calls'].append(row)
            self.save()
            try:
                path.write_text(content, encoding='utf-8')
                row['status'] = 'completed'
            except OSError:
                row['status'] = self.state['status'] = 'uncertain'
                raise
            finally:
                self.save()
            return 'Created ' + value
        if action == 'sandbox_read':
            path = self.path(value)
            if path.stat().st_size > 30000:
                raise ValueError('Read a bounded text output.')
            return path.read_text(encoding='utf-8')
        if action == 'sandbox_list':
            return json.dumps(self.inventory())
        raise ValueError('Unknown confined sandbox tool.')

    def path(self, value):
        from .agent_context import scoped
        if not isinstance(value, str):
            raise ValueError('Use a relative sandbox path.')
        value = value.removeprefix('/mnt/user-data/')
        if value.split('/', 1)[0] not in {'workspace', 'outputs'}:
            value = 'workspace/' + value
        return scoped(self.root, value)

    def inventory(self):
        rows = []
        for folder in ('workspace', 'outputs'):
            for path in sorted((self.root / folder).rglob('*')):
                if len(rows) >= 200:
                    return rows
                if path.is_file() and not any(linked(p) for p in [path, *[p for p in path.parents if p.is_relative_to(self.root)]]) and path.resolve().is_relative_to(self.root):
                    rows.append({'path': path.relative_to(self.root).as_posix(), 'bytes': path.stat().st_size})
        return rows

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.storage_stop.set()
        if (self.root / 'state.json').is_file():
            self.state = json.loads((self.root / 'state.json').read_text(encoding='utf-8'))
        try:
            self.owned()
            self.runtime.cli(['rm', '--force', self.name], timeout=10)
            self.state['status'] = 'closed' if self.state['status'] != 'uncertain' else 'uncertain'
        except (ValueError, OSError):
            self.state['status'] = 'uncertain'
        self.save()

    def __enter__(self):
        try:
            return self.create()
        except Exception:
            self.close()
            raise

    def __exit__(self, *args):
        self.close()


def reap_orphans(base):
    """Only reap attested job containers whose exact host owner has died."""
    import psutil
    root = Path(base) / '.jarvis-runtime/deerflow/jobs'
    if not root.is_dir():
        return 0
    reaped = 0
    started = time.monotonic()
    for folder in sorted(root.iterdir())[-200:]:
        if time.monotonic() - started > 8:
            break
        if not re.fullmatch('[a-f0-9]{32}', folder.name) or not (folder / 'state.json').is_file():
            continue
        try:
            state = json.loads((folder / 'state.json').read_text())
            if state.get('status') not in {'running', 'starting', 'uncertain'} or 'owner_pid' not in state:
                continue
            try:
                owner = psutil.Process(state['owner_pid'])
                if abs(owner.create_time() - state['owner_started']) < .01 and owner.is_running():
                    continue
            except psutil.NoSuchProcess:
                pass
            job = SandboxJob(base, folder.name)
            job.owned()
            job.close()
            reaped += 1
        except (OSError, ValueError, KeyError, psutil.AccessDenied):
            continue
    return reaped
