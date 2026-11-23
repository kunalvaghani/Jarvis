"""Bounded deterministic study state in the existing Journal; no job runner or new database."""
from __future__ import annotations
import hashlib,json,math,time,uuid,re
from pathlib import Path
from pydantic import Field,model_validator
from ..contracts import StrictModel,Finite,Experiment,Quantity,RunArtifact,Source
from ..memory import LabMemory
from .pendulum import Pendulum,solve,independent_checks,sha,scenario
from ..sandbox.budget import Budget,BudgetExceeded
from ..sandbox.local_trials import reserve


class Study(StrictModel):
    baseline: Pendulum
    lower_length_m: Finite = Field(ge=.1,le=5)
    upper_length_m: Finite = Field(ge=.1,le=5)
    grid_points: int = Field(ge=3,le=12)
    max_trials: int = Field(ge=2,le=12)
    target_period_s: Finite = Field(gt=0,le=100)
    tolerance_s: Finite = Field(ge=0,le=1)
    max_gravity_moment_nm: Finite = Field(gt=0,le=10000)
    cpu_budget_s: Finite = Field(ge=0,le=120)

    @model_validator(mode='before')
    @classmethod
    def explicit_physics(cls,data):
        if isinstance(data,dict) and isinstance(data.get('baseline'),dict):
            required={'length_m','radius_m','mass_kg','gravity_m_s2','damping_nm_s','initial_angle_rad','duration_s','dt_s'}
            if not required<=data['baseline'].keys():raise ValueError('all physical baseline fields must be explicit')
        return data

    @model_validator(mode='after')
    def limits(self):
        if not self.lower_length_m<=self.baseline.length_m<=self.upper_length_m:raise ValueError('baseline outside authorized design bounds')
        for length in (self.lower_length_m,self.upper_length_m):
            Pendulum(**{**self.baseline.model_dump(),'length_m':length})
        return self


def version():
    from . import pendulum
    from importlib.metadata import version as installed
    return hashlib.sha256(Path(__file__).read_bytes()+Path(pendulum.__file__).read_bytes()+installed('scipy').encode()+installed('numpy').encode()).hexdigest()


def candidates(spec):
    lo,hi=spec.lower_length_m,spec.upper_length_m
    grid=[lo+(hi-lo)*i/(spec.grid_points-1) for i in range(spec.grid_points)]
    values=[spec.baseline.length_m,hi,(lo+hi)/2,lo,*grid]
    return list(dict.fromkeys(values))[:spec.max_trials]


class Studies:
    def __init__(self,journal):
        self.j=journal;self.memory=LabMemory(journal);self.memory.migrate()
        with journal.tx() as db:
            db.execute('CREATE TABLE IF NOT EXISTS discovery_studies (id TEXT PRIMARY KEY, spec_ref TEXT NOT NULL, path TEXT NOT NULL, source_sha TEXT NOT NULL, code_sha TEXT NOT NULL, state TEXT NOT NULL, owner TEXT, lease_until REAL)')
            db.execute('CREATE TABLE IF NOT EXISTS discovery_optimization_trials (study TEXT NOT NULL, number INTEGER NOT NULL, request_ref TEXT NOT NULL, budget_id TEXT NOT NULL, state TEXT NOT NULL, run_ref TEXT, detail TEXT NOT NULL, PRIMARY KEY(study,number))')

    def create(self,base,path):
        from ..adapters.assets import local_bytes
        raw=local_bytes(Path(base),path,limit=30000);spec=Study.model_validate_json(raw)
        digest=hashlib.sha256(raw).hexdigest();identity='study-'+sha([path,digest,version()])[:32]
        ref=self.j.put(spec.model_dump(mode='json'),data_type='Report')
        self.memory.put(Source(id=identity+'-input',locator=path,sha256=digest,justification='User-authorized immutable study, design bounds, objective, scenario and resource budget.'))
        with self.j.tx() as db:
            db.execute('INSERT OR IGNORE INTO discovery_studies VALUES (?,?,?,?,?,?,?,?)',(identity,ref,path,digest,version(),'READY',None,None))
        return self.describe(identity)

    def row(self,identity):
        rows=self.j.rows('SELECT * FROM discovery_studies WHERE id=?',(identity,))
        if not rows:raise ValueError('unknown optimization study')
        return rows[0]

    def load(self,identity,base=None):
        row=self.row(identity)
        if row['code_sha']!=version():raise ValueError('solver/study implementation changed; create a new study, do not silently resume')
        if base is not None:
            from ..adapters.assets import local_bytes
            if hashlib.sha256(local_bytes(Path(base),row['path'],limit=30000)).hexdigest()!=row['source_sha']:
                raise ValueError('study source changed; scenario/objective/bounds cannot change during resume')
        return row,Study.model_validate_json(self.j.get(row['spec_ref']))

    def describe(self,identity):
        row,spec=self.load(identity);trials=self.j.rows('SELECT * FROM discovery_optimization_trials WHERE study=? ORDER BY number',(identity,))
        results=[]
        for trial in trials:
            item={k:trial[k] for k in ('number','state','detail','run_ref')}
            if trial['run_ref']:
                run=json.loads(self.j.get(trial['run_ref']));independent_checks(Pendulum.model_validate_json(json.dumps(run['model'])),run)
                expected=Pendulum(**{**spec.baseline.model_dump(),'length_m':candidates(spec)[trial['number']]})
                if run['model']!=expected.model_dump(mode='json'):raise ValueError('trial changed more than the authorized length')
                length=run['model']['length_m'];period=run['metrics']['measured_period_s']
                torque=spec.baseline.mass_kg*spec.baseline.gravity_m_s2*length*abs(math.sin(spec.baseline.initial_angle_rad))
                if sha(scenario(Pendulum.model_validate_json(json.dumps(run['model']))))!=sha(scenario(spec.baseline)):
                    raise ValueError('recorded trial changed the fixed scenario')
                item.update(length_m=length,period_s=period,gravity_moment_nm=torque,
                            feasible=period is not None and torque<=spec.max_gravity_moment_nm,
                            decision='REJECTED_CONSTRAINT' if torque>spec.max_gravity_moment_nm else 'INSUFFICIENT_PERIOD' if period is None else 'CANDIDATE',
                            error_s=None if period is None else abs(period-spec.target_period_s))
            results.append(item)
        feasible=[r for r in results if r.get('feasible') and r['state']=='COMPLETED']
        best=min(feasible,key=lambda r:r['error_s']) if feasible else None
        baseline=results[0] if results and results[0]['state']=='COMPLETED' else None
        return {'study_id':identity,'state':row['state'],'scenario_sha256':sha(scenario(spec.baseline)),
            'objective':{'target_period_s':spec.target_period_s,'tolerance_s':spec.tolerance_s},
            'candidates_m':candidates(spec),'trials':results,'best':best,
            'baseline_error_s':baseline.get('error_s') if baseline else None,
            'objective_met':best is not None and best['error_s']<=spec.tolerance_s,
            'evidence_status':'SIMULATION_PASSED_WITH_ASSUMPTIONS' if best else 'INSUFFICIENT_EVIDENCE',
            'physical_validation':False,'scope':'ideal pendulum bounded grid search; objective/constraint decision is separate from numerical verification'}

    def control(self,identity,operation):
        self.row(identity)
        if operation not in ('pause','resume','cancel'):raise ValueError('unknown study control')
        with self.j.tx() as db:
            old=db.execute('SELECT state FROM discovery_studies WHERE id=?',(identity,)).fetchone()[0]
            if operation=='resume' and old not in ('PAUSED',):raise ValueError('only explicitly paused studies can resume; budgets/terminal states are not relaxed')
            if old in ('COMPLETED','CANCELLED','BUDGET_STOP'):raise ValueError('terminal study cannot be restarted or constraints relaxed')
            state={'pause':'PAUSED','resume':'READY','cancel':'CANCELLED'}[operation]
            db.execute('UPDATE discovery_studies SET state=? WHERE id=?',(state,identity))
        return self.describe(identity)

    def advance(self,identity,base,cancelled=lambda:False,task_state=None):
        row,spec=self.load(identity,base)
        if cancelled():return self.describe(identity)
        if row['state'] not in ('READY','RUNNING'):return self.describe(identity)
        owner=uuid.uuid4().hex;budget=Budget(self.j)
        with self.j.tx() as db:
            current=db.execute('SELECT state,owner,lease_until FROM discovery_studies WHERE id=?',(identity,)).fetchone()
            if current[0] not in ('READY','RUNNING'):return self.describe(identity)
            if current[1] and current[2]>time.time():raise ValueError('study already has an active trial lease')
            # Expired attempts remain charged and are never re-evaluated on resume.
            pending=db.execute("SELECT number,budget_id FROM discovery_optimization_trials WHERE study=? AND state='RUNNING'",(identity,)).fetchall()
            for number,reservation in pending:
                db.execute("UPDATE discovery_optimization_trials SET state='UNCERTAIN',detail='interrupted trial; no replay' WHERE study=? AND number=?",(identity,number))
                db.execute("UPDATE discovery_budget SET state='uncertain' WHERE id=? AND state='reserved'",(reservation,))
            number=db.execute('SELECT COUNT(*) FROM discovery_optimization_trials WHERE study=?',(identity,)).fetchone()[0]
            if number>=len(candidates(spec)):
                db.execute("UPDATE discovery_studies SET state='COMPLETED',owner=NULL,lease_until=NULL WHERE id=?",(identity,))
                return self.describe(identity)
            db.execute("UPDATE discovery_studies SET state='RUNNING',owner=?,lease_until=? WHERE id=?",(owner,time.time()+20,identity))
        length=candidates(spec)[number];model=Pendulum(**{**spec.baseline.model_dump(),'length_m':length})
        request_ref=self.j.put({'study':identity,'number':number,'model':model.model_dump(mode='json')},data_type='Report')
        reservation='optimization-'+identity+'-'+str(number);started=time.process_time();wall=time.monotonic()
        with self.j.tx() as db:
            db.execute('INSERT INTO discovery_optimization_trials VALUES (?,?,?,?,?,?,?)',(identity,number,request_ref,reservation,'RUNNING',None,''))
        try:
            spent=self.j.rows('SELECT COALESCE(SUM(b.cpu_s),0) AS used FROM discovery_optimization_trials t JOIN discovery_budget b ON b.id=t.budget_id WHERE t.study=?',(identity,))[0]['used']
            if spent+5>spec.cpu_budget_s:raise BudgetExceeded('study CPU admission budget reached')
            budget.reserve(reservation,cpu_s=5,disk_bytes=500000)
            reserve('scipy-pendulum',request_ref)
            def stopped():
                return cancelled() or time.monotonic()-wall>15 or self.row(identity)['state'] in ('PAUSED','CANCELLED')
            result=solve(model,cancelled=stopped)
            independent_checks(model,result)
            if stopped():raise ValueError('optimization paused/cancelled at trial boundary')
            ref=self.j.put(result,data_type='Report')
            with self.j.tx() as db:
                lease=db.execute('SELECT owner,state FROM discovery_studies WHERE id=?',(identity,)).fetchone()
                if lease[0]!=owner or lease[1]!='RUNNING':raise ValueError('trial lease/control changed; no stale result commit')
                db.execute("UPDATE discovery_optimization_trials SET state='COMPLETED',run_ref=?,detail='numerically verified; constraints evaluated separately' WHERE study=? AND number=?",(ref,identity,number))
                state='COMPLETED' if number+1>=len(candidates(spec)) else 'READY'
                db.execute('UPDATE discovery_studies SET state=?,owner=NULL,lease_until=NULL WHERE id=?',(state,identity))
            budget.settle(reservation,cpu_s=time.process_time()-started,disk_bytes=len(self.j.get(ref).encode()))
            artifact=identity+'-trial-'+str(number)
            self.memory.put(RunArtifact(id=artifact,locator=ref,sha256=hashlib.sha256(self.j.get(ref).encode()).hexdigest(),
                media_type='application/json',source_ids=(identity+'-input',),evidence_status='SIMULATION_PASSED_WITH_ASSUMPTIONS',justification='Actual SciPy trial with independent numerical checks; hard design constraints are evaluated separately.'))
            experiment=Experiment(id=artifact+'-experiment',design_sha256=result['design_sha256'],scenario_sha256=result['scenario_sha256'],
                solver=result['solver'],solver_version=result['solver_version'],artifact_ids=(artifact,),source_ids=(identity+'-input',),
                metrics={'period':Quantity(value=result['metrics']['measured_period_s'],unit='s',origin='solver',source_ref=ref)} if result['metrics']['measured_period_s'] is not None else {},
                evidence_status='SIMULATION_PASSED_WITH_ASSUMPTIONS',justification='Conditional numeric trial, not physical qualification.')
            from ..jobs import checkpoint
            if task_state is not None:checkpoint(self.memory,task_state,experiment)
            else:self.memory.put(experiment)
        except Exception as error:
            admitted=self.j.rows('SELECT id FROM discovery_budget WHERE id=?',(reservation,))
            if admitted:budget.settle(reservation,uncertain=True)
            blocked=isinstance(error,(BudgetExceeded,PermissionError))
            with self.j.tx() as db:
                current=db.execute('SELECT owner,state FROM discovery_studies WHERE id=?',(identity,)).fetchone()
                if current[0]==owner:
                    db.execute("UPDATE discovery_optimization_trials SET state=?,detail=? WHERE study=? AND number=? AND state='RUNNING'",('BLOCKED' if blocked else 'FAILED',type(error).__name__,identity,number))
                    state='BUDGET_STOP' if blocked else current[1] if current[1] in ('PAUSED','CANCELLED') else 'PAUSED' if cancelled() else 'READY'
                    db.execute('UPDATE discovery_studies SET state=?,owner=NULL,lease_until=NULL WHERE id=?',(state,identity))
        return self.describe(identity)


def enqueue(queue,config,study_id,generation,token,dependencies=(),key=None):
    """Use the existing durable queue/DAG, never a polling service."""
    from ...task_scheduler import ScheduledQueue
    from ...commands import Command
    from ..catalog import enabled
    if not re.fullmatch(r'study-[a-f0-9]{32}',study_id):raise ValueError('invalid study identity')
    if not enabled(config,'sim') or type(queue) is not ScheduledQueue:raise PermissionError('existing enabled durable queue required')
    command=Command('task','lab optimize step "'+study_id+'"')
    overrides={
        'lane':'inference','read_only':True,'reversible':True,'unattended':True,'approval':False,
        'locks':['legacy-actions','discovery-study:'+study_id],'dependencies':list(dependencies),'model':None,
        'resources':{'ram_mb':128,'cpu':1,'gpu':False,'network':False,'disk':'small'}}
    if key is None:return queue.put_nowait((generation,command,token),overrides=overrides)
    from dataclasses import asdict
    from ...task_store import TERMINAL
    with queue.lock,queue.store.transaction():
        # An explicit queue request after resume may replace drained no-op jobs.
        # Never reopen old task rows or replay a recorded numeric trial.
        for _ in range(50):
            identity,fresh=queue.store.admit(asdict(command),key)
            state=queue.store.get(identity)['state']
            if fresh or state not in TERMINAL:break
            key='discovery-optimization-requeue:'+identity
        else:raise ValueError('explicit requeue history limit reached')
        if not fresh and state!='RECEIVED':return identity
        queue.store.transition(identity,'CLASSIFYING','Trusted bounded optimizer trial, existing scheduler policy applies')
        return queue.put_nowait((generation,command,token),identity=identity,overrides=overrides)


def enqueue_remaining(studies,queue,config,study_id,generation):
    import threading
    report=studies.describe(study_id)
    if report['state'] not in ('READY','RUNNING'):return []
    queued=[]
    for number in range(len(report['trials']),len(report['candidates_m'])):
        identity=enqueue(queue,config,study_id,generation,threading.Event(),queued[-1:],
                         key='discovery-optimization:'+study_id+':'+str(number))
        queued.append(identity)
    return queued
