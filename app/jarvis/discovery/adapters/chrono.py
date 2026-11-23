"""Approved isolated fixed-worker Chrono access; no solver code from an LLM."""
import hashlib,json,uuid
from pathlib import Path
from ..model.vehicle import VehicleCase,validate_result

APP=Path(__file__).resolve().parents[3]
HOME=APP/'.jarvis-runtime/discovery/tools/chrono-10.0.0'
PREFIX=APP/'.venv-discovery-chrono'
WORKER=Path(__file__).with_name('chrono_worker.py')
COMPANION=Path(__file__).with_name('chrono_vehicle_worker.py')


def worker_hash():
    return hashlib.sha256(WORKER.read_bytes()+COMPANION.read_bytes()).hexdigest()


def qualification():
    problems=[];digest=worker_hash();proof=None
    from ...skill_memory import linked
    if any(linked(p) for p in (HOME,PREFIX,WORKER,COMPANION)):
        problems.append('linked solver environment/source refused')
    if not (PREFIX/'python.exe').is_file() or not (HOME/'install-result.json').is_file():
        problems.append('approved isolated setup is absent')
    for path in sorted(HOME.glob('canonical-??.json')):
        try:data=json.loads(path.read_text())
        except (OSError,ValueError):
            problems.append('unreadable canonical proof retained for review: '+path.name)
            continue
        if data.get('passed') is True and data.get('worker_sha256')==digest:
            proof=data
    if proof is None:problems.append('current fixed worker requires canonical qualification')
    return {'runtime_ready':not problems,'problems':problems,'worker_sha256':digest,
            'used_slots':len(list((HOME/'invocations').glob('slot-*.json'))),'max_invocations':50,
            'solver':'Chrono::Vehicle','version':'10.0.0','gpu_simulation':False,
            'full_A_acceptance_passed':False,'physical_validation':False}


def reserve(request_ref,operation='vehicle'):
    if operation not in ('vehicle','prepare','study'):raise ValueError('unregistered fixed solver operation')
    status=qualification()
    if not status['runtime_ready']:raise ValueError('; '.join(status['problems']))
    directory=HOME/'invocations'
    for i in range(50):
        try:
            with (directory/f'slot-{i:02}.json').open('x') as stream:
                json.dump({'request_ref':request_ref,'worker_sha256':status['worker_sha256'],
                           'operation':operation,'state':'consumed-before-dispatch'},stream)
            return i
        except FileExistsError:continue
    raise PermissionError('50 approved Chrono invocations exhausted')


def run(case,journal,cancelled=lambda:False,*,study=False,prepare=False):
    if cancelled():raise ValueError('vehicle cancelled before admission')
    case=VehicleCase.model_validate_json(case.model_dump_json())
    if study and prepare:raise ValueError('one worker operation required')
    payload={'operation':'prepare' if prepare else 'study' if study else 'vehicle','case':case.model_dump(mode='json'),'run_id':uuid.uuid4().hex}
    ref=journal.put(payload,'Report')
    from ..sandbox.budget import Budget
    budget=Budget(journal);identity='vehicle-'+uuid.uuid4().hex
    budget.reserve(identity,cpu_s=100,disk_bytes=8_000_000)
    try:slot=reserve(ref,payload['operation'])
    except BaseException:
        # No subprocess command was admitted. Keep any consumed invocation slot,
        # but do not mislabel its 100-second estimate as actual solver CPU use.
        budget.settle(identity,cpu_s=0,disk_bytes=0)
        raise
    digest=worker_hash()
    from ...repo_acquisition import command
    try:
        raw=command([str(PREFIX/'python.exe'),'-I','-B',str(WORKER)],cancelled,120,
                    json.dumps(payload,allow_nan=False).encode(),8_000_000)
        lines=[s for s in raw.decode(errors='replace').splitlines() if s.startswith('JARVIS_CHRONO_RESULT=')]
        if len(lines)!=1:raise ValueError('one exact fixed-worker result required')
        report=json.loads(lines[0].split('=',1)[1])
        if prepare:
            from ..vehicle_checks import validate_prepared
            checks=validate_prepared(case,report)
        elif study:
            from .chrono_vehicle_worker import study_cases
            expected=study_cases(case.model_dump(mode='json'))
            if report.get('kind')!='conditional_vehicle_study' or set(report.get('reports',{}))!=set(expected):
                raise ValueError('incomplete fixed study')
            checks=[]
            for name,value in expected.items():
                child=VehicleCase.model_validate_json(json.dumps(value))
                checks.extend(validate_result(child,report['reports'][name]))
        else:checks=validate_result(case,report)
        cpu=report['cpu_s']
        if type(cpu) not in (int,float) or not 0<=cpu<=100:raise ValueError('actual CPU cap exceeded')
        if worker_hash()!=digest:raise ValueError('worker changed during execution')
        report.update(slot=slot,worker_sha256=digest,input_ref=ref,checks=checks)
        if len(json.dumps(report))>1_900_000:raise ValueError('study exceeds immutable Journal artifact cap; no truncated success')
        result_ref=journal.put(report,'Report')
        with (HOME/'invocations'/f'result-{slot:02}.json').open('x') as stream:
            json.dump({'result_ref':result_ref,'request_ref':ref,'worker_sha256':digest,
                'stdout_sha256':hashlib.sha256(raw).hexdigest()},stream)
        budget.settle(identity,cpu_s=cpu,disk_bytes=len(raw))
        return result_ref,report
    except BaseException:
        budget.settle(identity,uncertain=True)
        raise
