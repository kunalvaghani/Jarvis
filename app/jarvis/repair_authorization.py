"""Explicit, bounded authorization for dependency repair and model downloads (Prompt 34, P34-001/P34-002).

Readiness checks are read-only. A failed import or a missing model never starts a package or network operation by
itself: it is reported as ``repair_required`` and Jarvis keeps using what is installed. Changing an environment or
downloading weights needs a one-time authorization that the user writes explicitly with this module's command line.
Each authorization is bounded:

* **Dependency repair** names the environment, a **locked** requirements file (every line pinned with ``==`` and at
  least one ``--hash=sha256:``) and its SHA-256, a local wheelhouse (the approved artifact set), a byte budget and an
  expiry. The repair is built in a staging environment from that wheelhouse only (``--no-index --require-hashes``;
  no ``--isolated``, so the user's pip configuration and offline settings stay in force). The old environment is kept
  until the replacement imports correctly, and is then kept as ``<env>.previous-<id>`` rather than deleted.
* **Model download** names the exact model tag, its revision (manifest digest), its source, a byte budget, RAM/VRAM
  budgets, an explicit network permission and an expiry. ``check_model_download`` is run by the final executor
  immediately before launch; an unknown or insufficient budget, an offline policy or a mismatch refuses it.

Authorizations are single use: loading one deletes its file, so a crash loop can never repeat it.
"""
from dataclasses import asdict, dataclass
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import time

DEPENDENCY_FILE = 'dependency-repair-authorization.json'
MODEL_FILE = 'model-download-authorization.json'
ENVIRONMENTS = {'.venv': 'main_imports', '.venv-brain': 'brain_imports', '.venv-f5': 'f5_imports'}
MODEL_SOURCES = {'ollama': 'registry.ollama.ai'}
DISK_RESERVE = 2 * 1024 ** 3  # never fill the volume: keep 2 GiB free after the budgeted download
MAX_AGE = 3600
OFFLINE_FLAGS = ('JARVIS_OFFLINE', 'PIP_NO_INDEX', 'HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'OLLAMA_OFFLINE')


class RepairRequired(ValueError):
    """Something declared is absent; nothing was installed or downloaded."""

    def __init__(self, missing, guidance=''):
        self.missing = list(missing)
        super().__init__('Repair required: ' + '; '.join(self.missing) + '. Nothing was installed or downloaded.'
                         + (' ' + guidance if guidance else ''))


class RepairRefused(ValueError):
    """An authorization was present but does not satisfy its bounds; nothing was started."""


def offline_policy(environment=None):
    environment = os.environ if environment is None else environment
    return [flag for flag in OFFLINE_FLAGS if str(environment.get(flag, '')).strip().lower() in {'1', 'true', 'yes', 'on'}]


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def _inside(base, path):
    resolved = (Path(base) / path).resolve()
    resolved.relative_to(Path(base).resolve())
    return resolved


@dataclass(frozen=True)
class DependencyRepair:
    environment: str
    lock: str
    lock_sha256: str
    wheelhouse: str
    max_bytes: int
    expires: float
    approval_id: str


@dataclass(frozen=True)
class ModelDownload:
    model: str
    revision: str
    source: str
    max_bytes: int
    ram_bytes: int
    vram_bytes: int
    network_allowed: bool
    expires: float
    approval_id: str


def locked_requirements(text):
    """Return pinned requirement names, or raise unless every requirement is pinned and hash-locked."""
    names, current = [], ''
    for raw in text.splitlines():
        line = raw.split(' #', 1)[0].strip()
        if not line or line.startswith('#'):
            continue
        current += line.rstrip('\\').strip() + ' '
        if line.endswith('\\'):
            continue
        entry, current = current.strip(), ''
        if entry.startswith('-'):
            raise RepairRefused('The approved lock may only contain pinned, hashed requirements (found an option line).')
        requirement = entry.split(' --hash', 1)[0].strip()
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*(\[[A-Za-z0-9,._-]+\])?==[A-Za-z0-9.+!_-]+(\s*;.*)?', requirement):
            raise RepairRefused('The approved lock pins every requirement with ==; ' + requirement[:80] + ' is not pinned.')
        if not re.search(r'--hash=sha256:[0-9a-f]{64}', entry):
            raise RepairRefused('The approved lock needs a sha256 hash for ' + requirement[:80] + '.')
        names.append(requirement)
    if current.strip():
        raise RepairRefused('The approved lock ends with an unfinished continuation line.')
    if not names:
        raise RepairRefused('The approved lock lists no requirements.')
    return names


def check_dependency_repair(base, approval, environment_name, now=None, disk_usage=None):
    """Validate a dependency authorization for ``environment_name``; return (lock path, wheelhouse path)."""
    now = time.time() if now is None else now
    disk_usage = disk_usage or shutil.disk_usage
    if approval.environment != environment_name or environment_name not in ENVIRONMENTS:
        raise RepairRefused('The authorization is for ' + approval.environment + ', not ' + environment_name + '.')
    if not approval.expires or now > approval.expires:
        raise RepairRefused('The dependency repair authorization has expired; authorize it again.')
    try:
        lock = _inside(base, approval.lock)
    except ValueError:
        raise RepairRefused('The approved lock must be inside the Jarvis folder.') from None
    if not lock.is_file() or _sha256(lock) != approval.lock_sha256:
        raise RepairRefused('The approved lock changed or is missing; authorize the current lock again.')
    locked_requirements(lock.read_text(encoding='utf-8'))
    wheelhouse = Path(approval.wheelhouse).resolve()
    if not wheelhouse.is_dir():
        raise RepairRefused('The approved local artifact set (wheelhouse) is missing.')
    size = sum(path.stat().st_size for path in wheelhouse.rglob('*') if path.is_file())
    if not isinstance(approval.max_bytes, int) or approval.max_bytes <= 0 or size > approval.max_bytes:
        raise RepairRefused('The approved artifact set exceeds its byte budget or the budget is unknown.')
    # Staging keeps the old environment in place, so room is needed for an unpacked copy beside it.
    if disk_usage(str(base)).free < 3 * approval.max_bytes + DISK_RESERVE:
        raise RepairRefused('Not enough free disk space to stage the replacement beside the existing environment.')
    return lock, wheelhouse


def check_model_download(approval, missing, model_store, environment=None, now=None, disk_usage=None,
                         ram_total=None, vram_total=None):
    """Final pre-launch gate for a model download; raises RepairRefused for anything unknown or insufficient."""
    now = time.time() if now is None else now
    disk_usage = disk_usage or shutil.disk_usage
    if approval is None:
        raise RepairRefused('No approved model download; nothing was started.')
    if not approval.expires or now > approval.expires:
        raise RepairRefused('The model download authorization has expired; authorize it again.')
    if approval.model not in missing:
        raise RepairRefused('The approved model ' + approval.model[:80] + ' is not one of the missing configured models.')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', approval.revision or ''):
        raise RepairRefused('The approved model revision must be an exact sha256 manifest digest.')
    if approval.source not in MODEL_SOURCES:
        raise RepairRefused('The approved model source is not a known registry.')
    if not approval.network_allowed:
        raise RepairRefused('The model download authorization does not permit network use.')
    blocked = offline_policy(environment)
    if blocked:
        raise RepairRefused('Offline policy is set (' + ', '.join(blocked) + '); the download was not started.')
    for name in ('max_bytes', 'ram_bytes', 'vram_bytes'):
        value = getattr(approval, name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0 or (name == 'max_bytes' and value == 0):
            raise RepairRefused('The model download ' + name.replace('_', ' ') + ' budget is unknown.')
    store = Path(model_store)
    probe = store if store.exists() else next((parent for parent in store.parents if parent.exists()), store)
    try:
        free = disk_usage(str(probe)).free
    except OSError:
        raise RepairRefused('Free disk space for the model store could not be measured.') from None
    if free < approval.max_bytes + DISK_RESERVE:
        raise RepairRefused('Not enough free disk space for the approved model download budget.')
    if ram_total is None:
        try:
            import psutil
            ram_total = psutil.virtual_memory().total
        except Exception:
            ram_total = None
    if ram_total is None or ram_total < approval.ram_bytes:
        raise RepairRefused('Installed RAM is unknown or below the approved model RAM budget.')
    if approval.vram_bytes:
        if vram_total is None:
            from .gpu_scheduler import memory
            measured = memory()
            vram_total = measured['total_mb'] * 1024 ** 2 if measured else None
        if vram_total is None or vram_total < approval.vram_bytes:
            raise RepairRefused('GPU memory is unknown or below the approved model VRAM budget.')
    return approval


def model_store(environment=None):
    environment = os.environ if environment is None else environment
    return Path(environment.get('OLLAMA_MODELS') or Path.home() / '.ollama' / 'models')


def _take(runtime, name, kind):
    path = Path(runtime) / name
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        path.unlink(missing_ok=True)
        raise RepairRefused('The repair authorization file is unreadable; it was discarded.') from None
    path.unlink(missing_ok=True)  # single use, whether or not it is valid
    try:
        return kind(**data)
    except TypeError:
        raise RepairRefused('The repair authorization file has unexpected fields; it was discarded.') from None


def take_dependency_repair(runtime):
    return _take(runtime, DEPENDENCY_FILE, DependencyRepair)


def take_model_download(runtime):
    return _take(runtime, MODEL_FILE, ModelDownload)


def _write(runtime, name, approval):
    Path(runtime).mkdir(parents=True, exist_ok=True)
    temporary = Path(runtime) / (name + '.tmp')
    temporary.write_text(json.dumps(asdict(approval), indent=2), encoding='utf-8')
    os.replace(temporary, Path(runtime) / name)


def main(argv=None):
    base = Path(__file__).resolve().parent.parent
    runtime = base / '.jarvis-runtime'
    parser = argparse.ArgumentParser(description='Explicitly authorize one bounded Jarvis repair.')
    kinds = parser.add_subparsers(dest='kind', required=True)
    dependency = kinds.add_parser('dependency', help='rebuild one environment from a locked local artifact set')
    dependency.add_argument('--environment', choices=sorted(ENVIRONMENTS), required=True)
    dependency.add_argument('--lock', required=True, help='requirements file with == pins and sha256 hashes')
    dependency.add_argument('--wheelhouse', required=True, help='local folder with the approved wheels')
    dependency.add_argument('--max-bytes', type=int, required=True)
    model = kinds.add_parser('model', help='download one exact model revision')
    model.add_argument('--model', required=True)
    model.add_argument('--revision', required=True, help='sha256:<manifest digest>')
    model.add_argument('--source', choices=sorted(MODEL_SOURCES), required=True)
    model.add_argument('--max-bytes', type=int, required=True)
    model.add_argument('--ram-bytes', type=int, required=True)
    model.add_argument('--vram-bytes', type=int, required=True)
    model.add_argument('--allow-network', action='store_true', required=True)
    args = parser.parse_args(argv)
    expires, approval_id = time.time() + MAX_AGE, secrets.token_hex(8)
    if args.kind == 'dependency':
        lock = _inside(base, args.lock)
        locked_requirements(lock.read_text(encoding='utf-8'))
        approval = DependencyRepair(args.environment, str(lock.relative_to(base.resolve())).replace('\\', '/'),
                                    _sha256(lock), str(Path(args.wheelhouse).resolve()), args.max_bytes, expires, approval_id)
        _write(runtime, DEPENDENCY_FILE, approval)
    else:
        approval = ModelDownload(args.model, args.revision, args.source, args.max_bytes, args.ram_bytes,
                                 args.vram_bytes, bool(args.allow_network), expires, approval_id)
        _write(runtime, MODEL_FILE, approval)
    print('Authorized once, valid for one hour: ' + json.dumps(asdict(approval)))


if __name__ == '__main__':
    main()
