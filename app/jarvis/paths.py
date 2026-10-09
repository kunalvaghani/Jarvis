"""Application-root paths; relative settings never resolve from config/ or cwd."""
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_GROUPS = {'reports', 'media', 'training', 'projects', 'research', 'fixtures', 'logs'}

def linked(path):
    """Recognize Windows junctions as well as ordinary symbolic links."""
    path = Path(path)
    try:
        return path.is_symlink() or bool(getattr(path.lstat(), 'st_file_attributes', 0) & 0x400)
    except OSError:
        return True

def app_root(base=None):
    return Path(base) if base is not None else APP_ROOT

def config_file(base=None):
    return app_root(base) / 'config/config.json'

def manifest_file(base=None):
    return app_root(base) / 'config/runtime_manifest.json'

def state_file(name, base=None):
    if Path(name).name != name:
        raise ValueError('State filenames must be local basenames.')
    return app_root(base) / '.jarvis-runtime/state' / name

def log_file(name, base=None):
    if Path(name).name != name:
        raise ValueError('Log filenames must be local basenames.')
    return app_root(base) / '.jarvis-runtime/logs' / name

def artifact_path(base, relative):
    """Place both established and future output names in their matching group."""
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Artifact paths must remain inside the application artifacts.')
    if relative.parts and relative.parts[0] in ARTIFACT_GROUPS:
        return app_root(base) / 'artifacts' / relative
    name = relative.parts[0] if relative.parts else ''
    suffix = Path(name).suffix.lower()
    group = {'.json':'reports', '.jsonl':'reports', '.txt':'reports', '.log':'logs',
             '.png':'media', '.jpg':'media', '.jpeg':'media', '.gif':'media', '.wav':'media',
             '.mp4':'media', '.py':'fixtures'}.get(suffix)
    if group is None:
        if name.startswith(('qwen-', 'coding-')): group = 'training'
        elif name == 'development-previews': group = 'media'
        elif name == 'development-research': group = 'research'
        else: group = 'projects'
    return app_root(base) / 'artifacts' / group / relative
