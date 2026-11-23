"""Fixed C2 native adapter reusing existing installation/resource/owned-process helpers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import uuid
from jarvis.app_adapters import blender_executable, resource_budget
from jarvis.repo_acquisition import command
from jarvis.discovery.sandbox.budget import Budget

TEMPLATE=Path(__file__).with_name('pendulum_scene.py')


def native(actions, request, *, journal, cancelled=lambda:False):
    from jarvis.discovery.sandbox.local_trials import reserve
    executable=blender_executable(actions)
    resource_budget(actions)
    if cancelled():raise ValueError('native operation cancelled before dispatch')
    output=Path(request['output'])
    # The C2 adapter accepts only its newly created owned experiment directory.
    expected=Path(actions.base)/'.jarvis-runtime/discovery/experiments'
    if not output.resolve().is_relative_to(expected.resolve()) or output.suffix!='.blend':
        raise ValueError('native output is outside the owned experiment root')
    from jarvis.skill_memory import linked
    if any(linked(p) for p in (output,*output.parents)):raise ValueError('linked native output')
    if request['operation']=='create' and any(output.with_suffix(s).exists() for s in ('.blend','.obj','.png')):
        raise ValueError('native outputs already exist; never replay or overwrite')
    if request['operation']=='inspect' and not output.is_file():raise ValueError('native file missing')
    identity=uuid.uuid4().hex
    request_ref=journal.put({'operation':request['operation'],'output':str(output),
                             'model':request['run']['model'],
                             'template_sha256':hashlib.sha256(TEMPLATE.read_bytes()).hexdigest()},data_type='Report')
    reserve('blender-pendulum',request_ref)
    budget=Budget(journal)
    reservation='blender-'+identity
    budget.reserve(reservation,cpu_s=60 if request['operation']=='create' else 10,disk_bytes=2_000_000)
    req=output.parent/f'{request["operation"]}-{identity}-request.json';res=output.parent/f'{request["operation"]}-{identity}-result.json'
    if req.exists() or res.exists():raise ValueError('native operation receipt exists; inspect before retry')
    req.write_text(json.dumps(request,allow_nan=False),encoding='utf-8')
    try:
        command([str(executable),'--background','--factory-startup','--disable-autoexec','--offline-mode','--threads','2',
                 '--python',str(TEMPLATE),'--',str(req),str(res)],cancelled,120,None,2_000_000)
        if not res.is_file() or res.stat().st_size>64_000:raise ValueError('missing/bounded native result required')
        result=json.loads(res.read_text(encoding='utf-8'))
        if result.get('ok') is not True:raise ValueError('native C2 check failed: '+str(result.get('error_type'))+': '+str(result.get('error')))
        cpu=result.get('cpu_s')
        if type(cpu) not in (int,float) or not 0<=cpu<=240:raise ValueError('native CPU measurement invalid')
        budget.settle(reservation,cpu_s=cpu,disk_bytes=sum(p.stat().st_size for p in output.parent.iterdir() if p.is_file()))
        return result['value']
    except BaseException:
        budget.settle(reservation,uncertain=True)
        raise
