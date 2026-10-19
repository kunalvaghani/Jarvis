"""Isolated experiment repository for evolution candidates (Pillar C).

The canonical Jarvis repository is only *read*: ``git rev-parse`` identifies it and its HEAD,
and ``git archive`` exports a snapshot. No branch, worktree, ref or file is created in it.
Experiments live in a separate Git repository under ``.jarvis-runtime/evolution/lab/repo``:
the snapshot is committed there, each candidate is a commit on its own lab branch
``cand/<id>`` built from its parent's lab commit, and evaluation uses detached lab worktrees
that are removed afterwards. The evaluator directory and held-out data are excluded from
snapshots, so candidates can neither read nor modify them.

The lab is not a hostile-code sandbox. Safety comes from what a candidate may be: a change
to one declared surface literal, verified on source text before anything runs.
"""
import io
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

from .evolution_surfaces import SURFACES, render, verify_bounded

# Source, tests and the read-only fixtures/evidence the domain suites read (no evaluator, no user data).
SNAPSHOT_PATHS = ('jarvis', 'tests', 'skills', 'config', 'requirements', 'main.py', 'jarvis_bootstrap.py',
                  'integrations/windows-command-reference', 'integrations/profiles', 'artifacts/jarvis-audit/modules',
                  'artifacts/reports/utility-validation.json')
EXCLUDED = ('evolution_eval',)
LAB_IDENTITY = ['-c', 'user.name=Jarvis evolution lab', '-c', 'user.email=lab@localhost', '-c', 'commit.gpgsign=false',
                '-c', 'core.autocrlf=false', '-c', 'core.hooksPath=' + os.devnull]


def git_env():
    env = {k: v for k, v in os.environ.items() if k.upper() in
           {'PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'COMSPEC', 'PATHEXT', 'LOCALAPPDATA', 'APPDATA'}}
    env.update(GIT_TERMINAL_PROMPT='0', GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
    return env


def member_path(prefix, name):
    return Path(prefix, name) if prefix else Path(name)


class LabError(RuntimeError):
    pass


class ExperimentLab:
    def __init__(self, base, lab_root=None):
        self.base = Path(base).resolve()  # the Jarvis app directory (production)
        self.root = Path(lab_root or self.base / '.jarvis-runtime' / 'evolution' / 'lab').resolve()
        self.repo = self.root / 'repo'
        self.work = self.root / 'work'
        if self.repo == self.base or self.base in self.repo.parents and '.jarvis-runtime' not in self.repo.parts:
            raise LabError('The experiment repository must be separate from the production tree.')

    # ---- git helpers -------------------------------------------------------------------------------------------------
    def _run(self, args, cwd, binary=False, timeout=300):
        result = subprocess.run(['git', '-c', 'core.longpaths=true', *args], cwd=cwd, env=git_env(),
                                capture_output=True, timeout=timeout)
        if result.returncode:
            raise LabError('git ' + ' '.join(args[:2]) + ' failed: ' + result.stderr.decode('utf-8', 'replace').strip()[:300])
        return result.stdout if binary else result.stdout.decode('utf-8', 'replace').strip()

    def lab_git(self, *args, cwd=None):
        return self._run([*LAB_IDENTITY, *args], cwd or self.repo)

    def canonical(self):
        """(repository root, app path inside it, HEAD commit) of the production checkout, read-only."""
        top = Path(self._run(['rev-parse', '--show-toplevel'], self.base)).resolve()
        if top == self.repo or self.repo in top.parents:
            raise LabError('Refusing to treat the lab repository as the canonical source.')
        prefix = self.base.relative_to(top).as_posix()
        return top, '' if prefix == '.' else prefix, self._run(['rev-parse', 'HEAD'], self.base)

    # ---- snapshots ---------------------------------------------------------------------------------------------------
    def ensure_repo(self):
        if not (self.repo / '.git').exists():
            self.repo.mkdir(parents=True, exist_ok=True)
            self._run(['init', '-q', '-b', 'lab-main'], self.repo)
            self._run(['config', 'core.autocrlf', 'false'], self.repo)  # store snapshot bytes exactly
        return self.repo

    def snapshot(self, commit=None):
        """Import the canonical commit into the lab (idempotent); returns the lab commit for it."""
        self.ensure_repo()
        top, prefix, head = self.canonical()
        commit = commit or head
        branch = 'baseline/' + commit[:12]
        existing = self._run(['branch', '--list', branch], self.repo)
        if existing:
            return self.lab_git('rev-parse', branch), commit
        paths = [(prefix + '/' + p) if prefix else p for p in SNAPSHOT_PATHS]
        present = self._run(['ls-tree', '--name-only', commit, '--', *paths], top).splitlines()
        archive = self._run(['-c', 'core.autocrlf=false', 'archive', '--format=tar', commit, '--', *present], top, binary=True)
        staging = self.root / 'staging'
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            for member in tar.getmembers():
                name = member.name[len(prefix) + 1:] if prefix and member.name.startswith(prefix + '/') else member.name
                if not name or not member.isfile() or any(part in EXCLUDED for part in Path(name).parts):
                    continue  # directories are implied; links and devices are never imported
                target = (staging / name).resolve()
                if Path(name).is_absolute() or '..' in Path(name).parts or staging.resolve() not in target.parents:
                    raise LabError('Unsafe path in snapshot archive: ' + name)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(self._checkout_bytes(top / member_path(prefix, name), tar.extractfile(member).read()))
        self.lab_git('checkout', '-q', '--orphan', branch)
        self.lab_git('rm', '-rq', '--cached', '--ignore-unmatch', '.')
        for item in self.repo.iterdir():
            if item.name != '.git':
                shutil.rmtree(item) if item.is_dir() else item.unlink()
        for item in staging.iterdir():
            shutil.move(str(item), str(self.repo / item.name))
        staging.rmdir()
        self.lab_git('add', '-A')
        self.lab_git('commit', '-q', '-m', 'Snapshot of canonical ' + commit)
        return self.lab_git('rev-parse', 'HEAD'), commit

    @staticmethod
    def _checkout_bytes(production, blob):
        """Production line endings for an unchanged file (checkouts here mix LF and CRLF); else the committed blob."""
        try:
            local = production.read_bytes() if production.is_file() and not production.is_symlink() else None
        except OSError:
            local = None
        crlf, lf = b'\r\n', b'\n'
        return local if local is not None and local.replace(crlf, lf) == blob.replace(crlf, lf) else blob

    # ---- candidates --------------------------------------------------------------------------------------------------
    def read(self, lab_commit, relative):
        return self._run(['show', f'{lab_commit}:{relative}'], self.repo, binary=True).decode('utf-8')

    def create_candidate(self, candidate_id, parent_commit, surface_name, values, message):
        """Commit one bounded surface mutation on lab branch cand/<id>; returns its lab commit."""
        spec = SURFACES[surface_name]
        source = self.read(parent_commit, spec['file'])
        changed = render(source, surface_name, values)
        verify_bounded(source, changed, surface_name)
        path = self.worktree(candidate_id, parent_commit)
        try:
            (path / spec['file']).write_bytes(changed.encode('utf-8'))
            self.lab_git('checkout', '-q', '-b', 'cand/' + candidate_id, cwd=path)
            self.lab_git('add', spec['file'], cwd=path)
            self.lab_git('commit', '-q', '-m', message[:200], cwd=path)
            return self.lab_git('rev-parse', 'HEAD', cwd=path)
        finally:
            self.remove_worktree(path)

    def worktree(self, name, commit):
        path = self.work / name
        if path.exists():
            self.remove_worktree(path)
        self.work.mkdir(parents=True, exist_ok=True)
        self.lab_git('worktree', 'add', '-q', '--detach', str(path), commit)
        return path

    def remove_worktree(self, path):
        try:
            self.lab_git('worktree', 'remove', '--force', str(path))
        except LabError:
            if Path(path).exists():
                shutil.rmtree(path, ignore_errors=True)
            self.lab_git('worktree', 'prune')

    def cleanup(self):
        if self.work.exists():
            for item in self.work.iterdir():
                self.remove_worktree(item)
        if self.repo.exists():
            self.lab_git('worktree', 'prune')

    def branches(self):
        return self._run(['branch', '--format=%(refname:short)'], self.repo).splitlines() if self.repo.exists() else []
