"""Metadata-only tool lifecycle events and declarative deny hooks.

Audit hooks cannot run scripts, modify arguments, grant approval or retry tools.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import uuid

from .agent_context import bounded_text, scoped

_LOCK = threading.RLock()


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
    identifier = call_id or uuid.uuid4().hex
    if base is None:
        return identifier
    row = {'version': 1, 'at': datetime.now(timezone.utc).isoformat(), 'event': kind,
           'call_id': identifier, 'tool': name, **metadata}
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
