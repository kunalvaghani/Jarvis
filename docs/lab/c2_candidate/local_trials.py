"""A capped batch of approved, installed local tools; no service billing or installer."""
import json
from pathlib import Path

APP=Path(__file__).resolve().parents[3]  # Reconciled to app/ when staged into discovery/sandbox.
TOOLS=frozenset({'scipy-pendulum','blender-pendulum'})


def reserve(tool, request_ref):
    if tool not in TOOLS:raise PermissionError('tool not in approved free-local C2 batch')
    root=APP/'.jarvis-runtime/discovery/local-trials'
    grant=json.loads((root/'authorization.json').read_text(encoding='utf-8'))
    if grant!={'scope':'user-approved-free-local-c2-2026-11-04','max_per_tool':50,'money':0,'tools':sorted(TOOLS)}:
        raise PermissionError('approved local test batch missing or changed')
    from jarvis.skill_memory import linked
    folder=root/tool
    if any(linked(p) for p in (folder,*folder.parents)):raise ValueError('linked trial ledger')
    folder.mkdir(parents=True,exist_ok=True)
    for i in range(50):
        try:
            with (folder/f'slot-{i:02}.json').open('x',encoding='utf-8') as out:
                json.dump({'request_ref':request_ref,'state':'consumed-before-dispatch'},out)
            return i
        except FileExistsError:continue
    raise PermissionError('50 approved local trials exhausted; no implicit reset or paid fallback')
