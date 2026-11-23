"""Approved isolated MuJoCo CPU worker with a non-refundable global 50-call cap."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import uuid

from ..model.mechanics import MechanicsCase,validate_result

APP=Path(__file__).resolve().parents[3]
SETUP=APP/'.jarvis-runtime/lab-validation/ah-mechanics-setup'
ENV=APP/'.venv-discovery-mechanics'
WORKER=Path(__file__).with_name('mechanics_worker.py')
LOCK_SHA='f55ee8319662e61a74f85d2d920bf3f94487c4146a3bc299e7140a8728d7b25c'


def environment():
    from ...skill_memory import linked
    problems=[]
    try:
        if any(linked(p) for p in (ENV,SETUP,*SETUP.parents)):raise ValueError('linked mechanics environment')
        raw=(SETUP/'lock.json').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=LOCK_SHA:raise ValueError('approved mechanics lock changed')
        pins=json.loads(raw)['pins']
        versions={(d.metadata.get('Name') or '').casefold().replace('_','-'):d.version
                  for d in importlib.metadata.distributions(path=[str(ENV/'Lib/site-packages')])}
        if any(versions.get(p['name'].casefold().replace('_','-'))!=p['version'] for p in pins):
            raise ValueError('mechanics dependency pins changed')
        grant=json.loads((SETUP/'authorization.json').read_text(encoding='utf-8'))
        if grant.get('scope')!='user-approved-ah-mechanics-2026-11-04' or grant.get('max_cpu_invocations')!=50 or grant.get('host_generated_code') is not False:
            raise ValueError('approved mechanics invocation grant absent')
    except (OSError,ValueError,KeyError) as error:problems.append(str(error))
    return {'ready':not problems,'problems':problems,'worker_sha256':hashlib.sha256(WORKER.read_bytes()).hexdigest(),
            'max_invocations':50,'used_slots':len(list((SETUP/'invocations').glob('slot-*.json'))),
            'gpu_required':False,'sandbox_for_untrusted_code':False,
            'isolation':'owned fixed worker only; audit hook is not an OS security sandbox'}


def reserve(request_ref, *, operation='primitive'):
    status=environment()
    if not status['ready']:raise ValueError('Mechanics environment unavailable: '+'; '.join(status['problems']))
    if operation not in ('primitive','asset_inspection'):raise ValueError('unregistered owned mechanics operation')
    actual_hash=status['worker_sha256']
    if operation=='asset_inspection':
        from .asset_inspection import worker_hash
        actual_hash=worker_hash()
    from ...skill_memory import linked
    directory=SETUP/'invocations'
    if linked(directory):raise ValueError('linked mechanics ledger')
    directory.mkdir(exist_ok=True)
    for i in range(50):
        try:
            with (directory/f'slot-{i:02}.json').open('x',encoding='utf-8') as stream:
                json.dump({'request_ref':request_ref,'worker_sha256':actual_hash,'operation':operation,
                           'state':'consumed-before-dispatch'},stream)
            return i
        except FileExistsError:continue
    raise PermissionError('50 approved mechanics calls exhausted; no reset or automatic extension')


def qualification():
    """Static installed/qualified availability, never an invocation or physical claim."""
    status=environment();problems=list(status['problems'])
    path=SETUP/('golden-'+status['worker_sha256']+'.json')
    try:
        from ...skill_memory import linked
        if linked(path) or not path.is_file() or path.stat().st_size>64000:
            raise ValueError('current worker canonical proof is absent')
        proof=json.loads(path.read_text(encoding='utf-8'))
        rows=proof.get('goldens',[])
        if (proof.get('worker_sha256')!=status['worker_sha256'] or proof.get('solver')!='mujoco'
                or proof.get('version')!='3.17.0' or len(rows)!=2
                or {r.get('case') for r in rows}!={'analytic-free-fall','rigid-sphere-pendulum'}
                or not all(r.get('passed') is True for r in rows)):
            raise ValueError('canonical proof does not qualify this installed worker')
    except (OSError,ValueError,TypeError,KeyError,AttributeError) as error:problems.append(str(error))
    return {'solver':'mujoco','version':'3.17.0','runtime_ready':not problems,
            'proof_batch_remaining':50-status['used_slots'],'gpu_required':False,
            'problems':problems,'physical_validation':False}


def run(case:MechanicsCase,*,journal,cancelled=lambda:False):
    if cancelled():raise ValueError('mechanics cancelled before admission')
    case=MechanicsCase.model_validate(case.model_dump())
    payload=json.dumps(case.model_dump(mode='json'),allow_nan=False).encode()
    ref=journal.put({'inputs':case.model_dump(mode='json'),'worker_sha256':environment()['worker_sha256'],
                     'input_origin':'explicit unverified assumptions'},'Report')
    from ..sandbox.budget import Budget
    budget=Budget(journal);identity='mechanics-'+uuid.uuid4().hex
    budget.reserve(identity,cpu_s=20,disk_bytes=2000000)
    slot=reserve(ref)
    from ...repo_acquisition import command
    try:
        raw=command([str(ENV/('Scripts/python.exe' if os.name=='nt' else 'bin/python')),
                     '-I','-B',str(WORKER)],cancelled,30,payload,2000000)
        report=json.loads(raw)
        checks=validate_result(case,report)
        cpu=report['cpu_s']
        if type(cpu) not in (int,float) or not 0<=cpu<=20:raise ValueError('numeric worker CPU bound exceeded')
        report.update(input_ref=ref,worker_sha256=environment()['worker_sha256'],slot=slot,checks=checks)
        result_ref=journal.put(report,'Report')
        budget.settle(identity,cpu_s=cpu,disk_bytes=len(raw))
        return result_ref,report
    except BaseException:
        budget.settle(identity,uncertain=True)
        raise
