"""Hierarchical, recoverable index of the Obsidian vault on an owned OpenViking server.

OpenViking (AGPL-3.0) runs unmodified from .venv-openviking as a loopback-only
server with local Ollama models; Jarvis talks to it through jarvis.viking_worker.
The vault is only read: OpenViking stores uploaded copies in its own workspace
under .jarvis-runtime/openviking, so the index can be deleted and rebuilt.

A Jarvis manifest gives stable links: every indexed viking:// URI maps to its vault
path and the SHA-256 of the source; links are verified by hashing the L2 content
OpenViking returns. Unchanged files are skipped (incremental), changed files get a
new version, identical contents are indexed once (deduplication), and skill guides
owned by the living-skill store are excluded so they are not duplicated here.
L0/L1 summaries are model-generated hints and are always returned with their
L2 source path; they are never treated as facts.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
import uuid

ROOT_URI = 'viking://resources/jarvis_vault'
EXCLUDED_DIRS = ('.obsidian', '.trash', 'Jarvis Skills', 'Jarvis Executions')
MAX_FILE_BYTES = 2_000_000
DEFAULTS = {'enabled': True, 'port': 19330, 'processing_mode': 'vectors_only', 'semantic_directories': [],
            'embedding_model': 'ollama/nomic-embed-text', 'embedding_dimension': 768,
            'summary_model': 'ollama/qwen3.5:0.8b', 'timeout_seconds': 900}


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def slug(name):
    return re.sub(r'[^a-z0-9_]+', '_', name.casefold()).strip('_')[:60] or 'root'


class VikingMemory:
    def __init__(self, base, vault, options=None):
        self.base, self.vault = Path(base), Path(vault)
        self.options = {**DEFAULTS, **(options or {})}
        self.root = self.base / '.jarvis-runtime' / 'openviking'
        self.manifest_path = self.root / 'manifest.json'
        self.config_path = self.root / 'ov.conf'
        self.python = Path(__file__).resolve().parents[1] / '.venv-openviking' / 'Scripts' / 'python.exe'
        self.server = Path(__file__).resolve().parents[1] / '.venv-openviking' / 'Scripts' / 'openviking-server.exe'
        self.lock = threading.RLock()
        self.process = None
        self.job = None
        self.error = None

    # ---- configuration and lifecycle --------------------------------------------------------------------------------
    def available(self):
        return bool(self.options['enabled']) and self.python.is_file() and self.server.is_file() and self.vault.is_dir()

    def config(self):
        if self.config_path.is_file():
            return json.loads(self.config_path.read_text(encoding='utf-8'))
        self.root.mkdir(parents=True, exist_ok=True)
        options = self.options
        config = {'service_name': 'jarvis-openviking',
                  'storage': {'workspace': str(self.root / 'data'), 'vectordb': {'name': 'context', 'backend': 'local'},
                              'agfs': {'backend': 'local'}},
                  'embedding': {'dense': {'provider': 'litellm', 'model': options['embedding_model'],
                                          'api_base': 'http://127.0.0.1:11434', 'dimension': options['embedding_dimension']}},
                  'vlm': {'provider': 'litellm', 'api_key': 'ollama', 'model': options['summary_model'],
                          'api_base': 'http://127.0.0.1:11434', 'extra_request_body': {'think': False}},
                  # Loopback only; trusted mode still requires the root key on every request.
                  'server': {'host': '127.0.0.1', 'port': int(options['port']), 'auth_mode': 'trusted',
                             'root_api_key': secrets.token_urlsafe(32)}}
        temporary = self.config_path.with_name('.ov.conf.' + uuid.uuid4().hex[:8])
        temporary.write_text(json.dumps(config, indent=1), encoding='utf-8')
        temporary.replace(self.config_path)
        return config

    @property
    def url(self):
        return 'http://127.0.0.1:' + str(self.config()['server']['port'])

    def healthy(self):
        try:
            with urllib.request.urlopen(self.url + '/ready', timeout=3) as response:
                data = json.loads(response.read(100000))
            return data.get('status') == 'ready'
        except (OSError, ValueError):
            return False

    def start(self, wait_seconds=90):
        """Owned hidden server; a second Jarvis process reuses a healthy one instead of starting another."""
        with self.lock:
            if self.healthy():
                return True
            if not self.available():
                return False
            from .harness_process import OwnedJob, hidden_spawn
            config = self.config()
            # OpenViking's bootstrap starts `ollama serve` itself when none is reachable; that copy would
            # not see the user's OLLAMA_MODELS store. Start Ollama the Jarvis way first and require the
            # configured embedding model, so OpenViking never needs to launch one (Phase 4 defect H1).
            try:
                from .knowledge_worker import ensure_server, session
                tags = ensure_server(session())
            except Exception as exc:  # Broad by design: an unavailable Ollama makes the index unavailable, not Jarvis.
                self.error = 'Ollama unavailable for the vault index: ' + type(exc).__name__
                return False
            wanted = config['embedding']['dense']['model'].split('/', 1)[-1]
            names = {m.get('name', '').split(':')[0] for m in (tags or {}).get('models', [])}
            if wanted.split(':')[0] not in names:
                self.error = 'Embedding model ' + wanted + ' is not installed in Ollama; the vault index stays off.'
                return False
            self.job = OwnedJob()
            log = (self.root / 'server.log').open('ab')
            env = {k: v for k, v in os.environ.items() if k.upper() in {
                'PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'LOCALAPPDATA', 'APPDATA', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH'}
                or k.upper().startswith('OLLAMA_')}  # never hide the user's model store from a fallback start
            env.update(OPENVIKING_CONFIG_FILE=str(self.config_path), PYTHONIOENCODING='utf-8')
            self.process = hidden_spawn(self.job, subprocess.Popen)(
                [str(self.server), '--config', str(self.config_path)], cwd=str(self.root), env=env,
                stdin=subprocess.DEVNULL, stdout=log, stderr=log)
            deadline = time.monotonic() + wait_seconds
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    self.error = 'OpenViking server exited with code ' + str(self.process.returncode)
                    return False
                if self.healthy():
                    return True
                time.sleep(.5)
            self.error = 'OpenViking server did not become ready.'
            return False

    def repair(self):
        self.stop()
        return self.start()

    def repair_async(self):
        """Watchdog repair that never blocks the watchdog thread: None means work is pending."""
        with self.lock:
            starter = getattr(self, '_starter', None)
            if starter is not None and starter.is_alive():
                return None
            self._starter = threading.Thread(target=self.repair, name='jarvis-openviking-start', daemon=True)
            self._starter.start()
        return None

    def stop(self):
        with self.lock:
            if self.job is not None:
                self.job.close()  # Terminates only the owned server tree.
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            self.process, self.job = None, None

    def worker(self, request, cancelled=lambda: False, timeout=None):
        timeout = timeout or self.options['timeout_seconds'] + 60
        payload = json.dumps({**request, 'url': self.url, 'key': self.config()['server']['root_api_key'],
                              'timeout': self.options['timeout_seconds']}).encode()
        env = {k: v for k, v in os.environ.items() if k.upper() in {'PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP',
                                                                     'LOCALAPPDATA', 'APPDATA', 'USERPROFILE'}}
        env.update(PYTHONIOENCODING='utf-8', OPENVIKING_CONFIG_FILE=str(self.config_path))
        with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
            process = subprocess.Popen([str(self.python), '-m', 'jarvis.viking_worker'], cwd=str(Path(__file__).resolve().parents[1]),
                                       env=env, stdin=subprocess.PIPE, stdout=output, stderr=errors,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            try:
                process.stdin.write(payload)
                process.stdin.close()
                deadline = time.monotonic() + timeout
                while process.poll() is None:
                    if cancelled() or time.monotonic() > deadline:
                        process.kill()
                        raise ValueError('OpenViking request cancelled or timed out; index state is rechecked before reuse.')
                    time.sleep(.05)
            finally:
                if process.poll() is None:
                    process.kill()
            output.seek(0)
            raw = output.read(8_000_000).decode('utf-8', errors='replace')
        try:
            reply = json.loads(raw[raw.find('{'):]) if '{' in raw else {}
        except ValueError:
            reply = {}
        if reply.get('ok') is not True:
            raise ValueError('OpenViking ' + request['operation'] + ' failed: ' + str(reply.get('error', 'no reply'))[:300])
        return reply['value']

    # ---- manifest ---------------------------------------------------------------------------------------------------
    def manifest(self):
        if not self.manifest_path.is_file():
            return {'version': 1, 'vault': str(self.vault), 'files': {}, 'directories': {}, 'reports': []}
        try:
            data = json.loads(self.manifest_path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('files'), dict):
                raise ValueError('bad manifest')
            return data
        except ValueError:
            damaged = self.manifest_path.with_name('manifest.damaged-' + uuid.uuid4().hex[:8] + '.json')
            self.manifest_path.replace(damaged)
            self.error = 'Index manifest was damaged and preserved as ' + damaged.name + '; links will be rebuilt.'
            return {'version': 1, 'vault': str(self.vault), 'files': {}, 'directories': {}, 'reports': []}

    def save(self, manifest):
        self.root.mkdir(parents=True, exist_ok=True)
        if self.manifest_path.is_file():
            shutil.copy2(self.manifest_path, self.manifest_path.with_suffix('.json.bak'))
        temporary = self.manifest_path.with_name('.manifest.' + uuid.uuid4().hex[:8])
        temporary.write_text(json.dumps(manifest, indent=1), encoding='utf-8')
        temporary.replace(self.manifest_path)

    def scan(self):
        """Read-only vault scan: Markdown files outside excluded folders."""
        files = {}
        for path in sorted(self.vault.rglob('*.md')):
            relative = path.relative_to(self.vault)
            if any(part in EXCLUDED_DIRS or part.startswith('.') for part in relative.parts[:-1]) or path.is_symlink():
                continue
            stat = path.stat()
            if stat.st_size > MAX_FILE_BYTES:
                continue
            files[relative.as_posix()] = {'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}
        return files

    def plan(self, manifest=None):
        """Changed directories, version bumps and duplicate groups; hashes only files whose stat changed."""
        manifest = manifest or self.manifest()
        current, changes, hashes = self.scan(), {}, {}
        for relative, stat in current.items():
            old = manifest['files'].get(relative)
            if old and old.get('size') == stat['size'] and old.get('mtime_ns') == stat['mtime_ns']:
                hashes[relative] = old['sha256']
                continue
            digest = sha256((self.vault / relative).read_bytes())
            hashes[relative] = digest
            if not old or old.get('sha256') != digest:
                changes[relative] = 'new' if not old else 'changed'
        removed = sorted(set(manifest['files']) - set(current))
        first = {}
        duplicates = {}
        for relative in sorted(hashes):
            if hashes[relative] in first:
                duplicates[relative] = first[hashes[relative]]
            else:
                first[hashes[relative]] = relative
        directories = sorted({(r.split('/', 1)[0] if '/' in r else '.') for r in list(changes) + removed})
        return {'current': current, 'hashes': hashes, 'changes': changes, 'removed': removed,
                'duplicates': duplicates, 'directories': directories}

    # ---- indexing ---------------------------------------------------------------------------------------------------
    def index(self, cancelled=lambda: False, directories=None):
        """Incremental: only changed top-level directories are (re)uploaded; links verified afterwards."""
        if not self.start():
            raise ValueError('OpenViking server unavailable: ' + str(self.error))
        manifest = self.manifest()
        plan = self.plan(manifest)
        targets = directories if directories is not None else plan['directories']
        report = {'at': now(), 'changes': len(plan['changes']), 'removed': len(plan['removed']),
                  'duplicates': len(plan['duplicates']), 'directories': [], 'failed': []}
        for directory in targets:
            if cancelled():
                report['cancelled'] = True
                break
            started = time.monotonic()
            members = sorted(r for r in plan['current'] if (r.split('/', 1)[0] if '/' in r else '.') == directory)
            uri = ROOT_URI + '/' + slug(directory if directory != '.' else 'vault_root')
            mode = 'semantic_and_vectors' if directory in self.options['semantic_directories'] else self.options['processing_mode']
            kept = [r for r in members if r not in plan['duplicates']]
            if not kept:
                if directory in manifest['directories']:
                    self.worker({'operation': 'remove', 'uri': manifest['directories'][directory]['uri']}, cancelled)
                    del manifest['directories'][directory]
                continue
            # Stage copies so OpenViking never receives a handle to the vault itself.
            with tempfile.TemporaryDirectory(prefix='jarvis-viking-') as staging:
                folder = Path(staging) / slug(directory if directory != '.' else 'vault_root')
                for relative in kept:
                    source = self.vault / relative
                    inner = Path(relative).relative_to(directory) if directory != '.' else Path(relative)
                    target = folder / inner
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
                result = self.worker({'operation': 'add', 'path': str(folder), 'to': uri, 'include': '*.md',
                                      'processing_mode': mode}, cancelled)
            report['failed'].extend(result.get('failed', []))
            links = self.link(uri, directory, kept, plan['hashes'], cancelled)
            for relative in members:
                old = manifest['files'].get(relative, {})
                manifest['files'][relative] = {**plan['current'][relative], 'sha256': plan['hashes'][relative],
                    'version': old.get('version', 0) + (1 if relative in plan['changes'] or not old else 0),
                    'uri': links.get(relative, {}).get('uri') if relative not in plan['duplicates'] else None,
                    'verified_link': links.get(relative, {}).get('verified', False),
                    'duplicate_of': plan['duplicates'].get(relative), 'indexed_at': now(), 'mode': mode}
            manifest['directories'][directory] = {'uri': uri, 'mode': mode, 'files': len(kept), 'indexed_at': now()}
            report['directories'].append({'directory': directory, 'uri': uri, 'files': len(kept), 'mode': mode,
                                          'seconds': round(time.monotonic() - started, 1),
                                          'verified_links': sum(1 for v in links.values() if v['verified'])})
        for relative in plan['removed']:
            manifest['files'].pop(relative, None)
        manifest['reports'] = (manifest.get('reports', []) + [report])[-20:]
        self.save(manifest)
        return report

    def link(self, uri, directory, members, hashes, cancelled):
        """Map indexed L2 files back to vault paths and verify each by hashing the stored content."""
        nodes = [n for n in self.worker({'operation': 'tree', 'uri': uri, 'depth': 12}, cancelled)['nodes'] if not n.get('isDir')]
        # OpenViking normalizes stored names (e.g. spaces become underscores), so match normalized stems.
        key = lambda name: re.sub(r'[^a-z0-9]+', '_', Path(name).stem.casefold()).strip('_')
        by_name = {}
        for node in nodes:
            by_name.setdefault(key(node['name']), []).append(node)
        links = {}
        for relative in members:
            candidates = list(by_name.get(key(relative), []))
            inner = (Path(relative).relative_to(directory) if directory != '.' else Path(relative)).with_suffix('')
            candidates.sort(key=lambda n: -sum(key(part) in n['rel_path'].casefold() for part in inner.parts))
            source = (self.vault / relative).read_text(encoding='utf-8', errors='replace').replace('\r\n', '\n')
            for node in candidates[:3]:
                content = self.worker({'operation': 'read', 'uri': node['uri'], 'max_chars': MAX_FILE_BYTES}, cancelled)['content']
                if (sha256(content.encode('utf-8')) == hashes[relative]
                        or content.replace('\r\n', '\n').strip() == source.strip()):
                    links[relative] = {'uri': node['uri'], 'verified': True}
                    break
            else:
                if candidates:
                    links[relative] = {'uri': candidates[0]['uri'], 'verified': False}
        return links

    # ---- retrieval --------------------------------------------------------------------------------------------------
    def find(self, query, limit=5, cancelled=lambda: False):
        started = time.perf_counter()
        manifest = self.manifest()
        by_uri = {row['uri']: (relative, row) for relative, row in manifest['files'].items() if row.get('uri')}
        try:
            results = self.direct_find(str(query)[:2000], max(1, min(int(limit), 20)))
            engine = 'openviking-find-http'
        except (OSError, ValueError) as exc:
            self.error = 'HTTP find fell back to the worker: ' + type(exc).__name__ + ': ' + str(exc)[:120]
            results = self.worker({'operation': 'find', 'query': str(query)[:2000], 'target': ROOT_URI,
                                   'limit': max(1, min(int(limit), 20))}, cancelled, timeout=60)['results']
            engine = 'openviking-find-worker'
        rows = []
        for row in results:
            source = by_uri.get(row['uri'])
            stale = False
            if source:
                path = self.vault / source[0]
                stale = not path.is_file() or path.stat().st_mtime_ns != source[1].get('mtime_ns')
            rows.append({'uri': row['uri'], 'level': row['level'], 'score': round(row['score'] or 0, 4),
                         'summary': row['abstract'][:600], 'summary_is_generated': row['level'] != 2,
                         'source_path': source[0] if source else None,
                         'verified_link': bool(source and source[1].get('verified_link')), 'stale': stale})
        return {'results': rows, 'diagnostics': {'latency_ms': round((time.perf_counter() - started) * 1000, 1),
                'engine': engine, 'returned': len(rows),
                'unlinked': sum(1 for r in rows if r['source_path'] is None and r['level'] == 2)}}

    def direct_find(self, query, limit):
        """Read-only fast path to the owned loopback server (same headers the official SDK sends)."""
        config = self.config()
        body = json.dumps({'query': query, 'target_uri': ROOT_URI, 'limit': limit}).encode()
        request = urllib.request.Request(self.url + '/api/v1/search/find', data=body, method='POST', headers={
            'Content-Type': 'application/json', 'X-API-Key': config['server']['root_api_key'],
            'X-OpenViking-Account': 'jarvis', 'X-OpenViking-User': 'jarvis'})
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read(4_000_000))
        result = data.get('result', data)
        if not isinstance(result, dict):
            raise ValueError('Unexpected OpenViking find reply.')
        return [{'type': kind, 'uri': row.get('uri'), 'level': row.get('level'), 'score': row.get('score'),
                 'abstract': str(row.get('abstract', ''))[:1200]}
                for kind in ('resources', 'memories', 'skills') for row in result.get(kind, []) or []]

    def browse(self, uri=ROOT_URI, depth=2):
        return self.worker({'operation': 'tree', 'uri': uri, 'depth': depth})['nodes']

    def abstract(self, uri):
        return self.worker({'operation': 'abstract', 'uri': uri})['content']

    def overview(self, uri):
        return self.worker({'operation': 'overview', 'uri': uri})['content']

    def diagnostics(self):
        manifest = self.manifest()
        files = manifest['files'].values()
        return {'server_ready': self.healthy(), 'files': len(manifest['files']),
                'verified_links': sum(1 for f in files if f.get('verified_link')),
                'duplicates': sum(1 for f in files if f.get('duplicate_of')),
                'directories': len(manifest['directories']), 'last_report': (manifest.get('reports') or [None])[-1],
                'error': self.error}

    def rebuild(self, cancelled=lambda: False):
        """Recover from a damaged index: preserve the old workspace, start empty, re-index from the vault."""
        self.stop()
        workspace = self.root / 'data'
        if workspace.exists():
            workspace.rename(self.root / ('data.damaged-' + uuid.uuid4().hex[:8]))
        if self.manifest_path.exists():
            self.manifest_path.replace(self.root / ('manifest.preserved-' + uuid.uuid4().hex[:8] + '.json'))
        return self.index(cancelled)
