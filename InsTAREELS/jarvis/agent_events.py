"""Metadata-only tool lifecycle events and declarative deny hooks.

Audit hooks cannot run scripts, modify arguments, grant approval or retry tools.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import uuid
import re
import builtins
from functools import lru_cache

from .agent_context import bounded_text, scoped

_LOCK = threading.RLock()
_BACKENDS = frozenset({'files','terminal','browser','desktop','toolkit','dom','realtime','spotify','desktop_observation'})
_ERROR_TYPES = frozenset(name for name,value in vars(builtins).items()
    if isinstance(value,type) and issubclass(value,BaseException)) | frozenset({'UncertainCoding','AbilityError','CloudFailure','QuotaDenied','Unsupported','Cancelled',
    'ToolArgumentError','ToolUnavailable','TaskFailure'})
_CATEGORIES = frozenset({'invalid_arguments','unavailable','cancelled','failed'})

@lru_cache(maxsize=1)
def lifecycle_tools():
    # Lazy to keep module import side-effect free; execution happens after registry setup.
    from .tools import TOOL_NAMES
    return frozenset(TOOL_NAMES)

def lifecycle_metadata(metadata):
    """Allow categorical fields only; extra payloads cannot overwrite the envelope."""
    result = {}
    backend = metadata.get('backend')
    if isinstance(backend,str) and backend in _BACKENDS:
        result['backend'] = backend
    error = metadata.get('error_type')
    if isinstance(error,str) and error in _ERROR_TYPES:
        result['error_type'] = error
    category = metadata.get('category')
    if isinstance(category,str) and category in _CATEGORIES:
        result['category'] = category
    discarded = len(metadata)-len(result)
    if discarded: result['discarded_metadata_fields'] = discarded
    return result


def runtime_base(actions):
    base = getattr(actions, 'base', None)
    return Path(base) if isinstance(base, (str, Path)) else None


def check_policy(actions, name):
    base = runtime_base(actions)
    if base is None:
        return
    path = scoped(base, '.jarvis/policy.json')
    if not path.is_file():
        return
    data = json.loads(bounded_text(path))
    if not isinstance(data, dict) or set(data) - {'deny_tools', 'hooks'}:
        raise ValueError('Invalid Jarvis tool policy.')
    denied = data.get('deny_tools', [])
    hooks = data.get('hooks', [])
    if not isinstance(denied, list) or not all(isinstance(n, str) for n in denied) or not isinstance(hooks, list):
        raise ValueError('Invalid Jarvis deny rules.')
    for hook in hooks:
        if (not isinstance(hook, dict) or set(hook) != {'event', 'tool', 'decision'}
                or hook['event'] != 'before_tool' or hook['decision'] != 'deny'
                or not isinstance(hook['tool'], str)):
            raise ValueError('Hooks support only before_tool deny rules.')
        if hook['tool'] in {name, '*'}:
            raise ValueError('Tool denied by before_tool hook: ' + name)
    if name in denied or '*' in denied:
        raise ValueError('Tool denied by policy: ' + name)


def event(actions, kind, name, call_id=None, **metadata):
    base = runtime_base(actions)
    identifier = call_id if isinstance(call_id,str) and re.fullmatch(r'[0-9a-f]{32}',call_id) else uuid.uuid4().hex
    if base is None:
        return identifier
    row = {'version': 1, 'at': datetime.now(timezone.utc).isoformat(),
           'event':kind if kind in {'tool.started','tool.completed','tool.failed'} else 'tool.invalid_event',
           'call_id': identifier, 'tool':name if isinstance(name,str) and name in lifecycle_tools() else 'invalid_tool',
           **lifecycle_metadata(metadata)}
    # Never store arguments, source, responses, credentials or private recordings.
    with _LOCK:
        path = scoped(base, '.jarvis-runtime/agent-events.jsonl')
        folder = path.parent
        folder.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            raise ValueError('Agent event path must not be linked.')
        with path.open('a', encoding='utf-8') as output:
            output.write(json.dumps(row, ensure_ascii=False) + '\n')
    return identifier
