"""Read a recorded, exact user approval; never manufacture or infer permission.

This extends admissions in the existing Journal Budget. It is not an approval
service. Missing, changed, linked or unrelated grants keep the shipped bounds.
"""
import hashlib
import json
from pathlib import Path
import uuid
from ..sandbox.budget import Budget

APP=Path(__file__).resolve().parents[3]
HOME=APP/'.jarvis-runtime/discovery/asset-authorizations/full-a-2026-11-06'
PLAN=APP.parent/'docs/lab/FULL_A_ASSET_RUNTIME_PLAN.md'
SCOPE='user-approved-full-a-assets-2026-11-06'


def grant(expected_sha=None):
    from ...skill_memory import linked
    path=HOME/'authorization.json'
    if any(linked(p) for p in (path,*path.parents)) or path.stat().st_size>16000:raise PermissionError('invalid asset-resource approval record')
    raw=path.read_bytes();sha=hashlib.sha256(raw).hexdigest();data=json.loads(raw)
    if (expected_sha is not None and expected_sha!=sha) or data.get('scope')!=SCOPE or data.get('approved') is not True:
        raise PermissionError('matching explicit asset-resource approval required')
    limits={'maximum_asset_bytes':100_000_000,'project_disk_bytes':500_000_000,'maximum_transfer_pairs':4,
            'maximum_parser_input_bytes':100_000_000,'parser_memory_bytes':2*1024**3,'parser_cpu_seconds':60}
    if any(data.get(k)!=v for k,v in limits.items()) or data.get('plan_sha256')!=hashlib.sha256(PLAN.read_bytes()).hexdigest():
        raise PermissionError('asset-resource approval differs from its reviewed plan')
    if data.get('paid_usage') is not False or data.get('source_scripts_allowed') is not False:
        raise PermissionError('asset-resource grant cannot authorize paid use or source scripts')
    return {**data,'sha256':sha}


def applicable(target_year,title):
    import re
    if target_year not in (2025,2026) or not re.search(r'(?i)\bF1\b|\bFormula\s*(?:one|1)\b',title):return None
    try:return grant()
    except (OSError,ValueError,PermissionError):return None


def budget(journal,grant_sha=None):
    return Budget(journal,disk_bytes=grant(grant_sha)['project_disk_bytes']) if grant_sha else Budget(journal)


def reserve_pair(grant_sha,request_ref):
    permission=grant(grant_sha)
    from ...skill_memory import linked
    folder=HOME/'transfer-pairs'
    if linked(folder):raise PermissionError('linked asset invocation ledger')
    folder.mkdir(exist_ok=True)
    for slot in range(permission['maximum_transfer_pairs']):
        try:
            with (folder/f'slot-{slot:02}.json').open('x',encoding='utf-8') as file:
                json.dump({'grant_sha256':grant_sha,'request_ref':request_ref,'nonce':uuid.uuid4().hex,
                    'state':'consumed-before-file-handoff'},file)
            return slot
        except FileExistsError:continue
    raise PermissionError('approved full-A transfer pairs exhausted; no reset or implicit extension')
