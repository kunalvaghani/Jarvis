"""Stage admission, immutable traces and checkpoints in Jarvis's existing Journal.

No scheduler, model calls, filesystem writes or implicit permission grants.
"""
import hashlib,json,time,uuid
from .model.scenario_a import ScenarioAVehicleState,STAGES,Stage


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()


class NoProgress(ValueError):pass
class UncertainStage(ValueError):pass
class BlockedStage(ValueError):pass


class StageJournal:
    def __init__(self,journal,*,workflow=None):
        self.journal=journal
        # Other domain workflows reuse this same admission/checkpoint engine.
        # The default contract and historical project keys stay unchanged.
        from .model.scenario_a import resolve,StageResponse
        self.workflow=workflow
        self.state_type=ScenarioAVehicleState if workflow is None else workflow.state_type
        self.response_type=StageResponse if workflow is None else workflow.response_type
        self.stages=STAGES if workflow is None else workflow.stages
        self.stage_type=Stage if workflow is None else workflow.stage_type
        self.resolve=resolve if workflow is None else workflow.resolve
        self.allowed=({'source_records','candidate_assets','selected_asset','source_licenses','geometry_manifest',
            'physical_manifest','solver_configuration','validated_metrics','evidence_files','uncertainties'}
            if workflow is None else set(workflow.projection_fields))
        with journal.tx() as db:
            db.execute('CREATE TABLE IF NOT EXISTS discovery_scenario_projects (goal_hash TEXT PRIMARY KEY,state_ref TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS discovery_scenario_actions (run_id TEXT, fingerprint TEXT, stage TEXT, action TEXT, '
                'arguments_ref TEXT, pre_digest TEXT, post_digest TEXT, result_ref TEXT, category TEXT, attempts INTEGER, seconds REAL, '
                'retry_reason TEXT, PRIMARY KEY(run_id,fingerprint))')
            db.execute('CREATE TABLE IF NOT EXISTS discovery_scenario_attempts (run_id TEXT,fingerprint TEXT,attempt INTEGER, '
                'category TEXT,pre_digest TEXT,post_digest TEXT,result_ref TEXT,seconds REAL,retry_reason TEXT, '
                'PRIMARY KEY(run_id,fingerprint,attempt))')

    def load(self,ref):
        from .acceptance import artifact
        return self.state_type.model_validate_json(json.dumps(artifact(self.journal,ref)))

    def key(self,target):
        value=target.model_dump(mode='json')
        return digest(value if self.workflow is None else {'workflow':self.workflow.namespace,'target':value})

    def open(self,target):
        key=self.key(target)
        rows=self.journal.rows('SELECT state_ref FROM discovery_scenario_projects WHERE goal_hash=?',(key,))
        if rows:return self.load(rows[0]['state_ref'])
        state=(ScenarioAVehicleState(run_id='scenario-'+uuid.uuid4().hex,original_goal=target.goal,
            target_year=target.year,target_team_or_class=target.team_or_class) if self.workflow is None else self.workflow.new_state(target))
        self.save(state)
        return state

    def save(self,state):
        # Re-parse rather than trust unchecked model_copy updates.
        state=self.state_type.model_validate_json(state.model_dump_json())
        target=self.resolve(state.original_goal)
        if target is None:raise ValueError('scenario target no longer resolves')
        ref=self.journal.put(state.model_dump(mode='json'),'Report')
        key=self.key(target)
        with self.journal.tx() as db:
            db.execute('INSERT OR REPLACE INTO discovery_scenario_projects VALUES (?,?)',(key,ref))
        return state

    def perform(self,state,stage,action,arguments,operation,verify,*,read_only=False,project=lambda output:{},reconcile=None):
        """Journal before dispatch; advance only after independent output checks.

        One retry of a failed read is allowed. Unknown writes are never replayed.
        A caller must select a different registered alternative after no progress.
        """
        index=self.stages.index(stage)
        if tuple(state.verified_stages)!=self.stages[:index]:raise ValueError('unverified or out-of-order stage transition')
        fingerprint=digest({'stage':stage,'action':action,'arguments':arguments,'artifacts':state.stage_artifacts})
        args_ref=self.journal.put(arguments,'Report');before=digest(state.model_dump(mode='json'))
        reconciling=False
        with self.journal.tx() as db:
            prior=self.journal.rows('SELECT * FROM discovery_scenario_actions WHERE run_id=? AND fingerprint=?',(state.run_id,fingerprint))
            tries=1
            if prior:
                row=prior[0];tries=row['attempts']+1
                if row['category']=='verified':raise NoProgress('verified action must resume from its checkpoint, not execute again')
                if row['category'] in ('claimed','uncertain'):
                    if reconcile is None:raise UncertainStage('prior action may have acted or is still running; reconcile before any retry')
                    reconciling=True
                if tries>2:raise NoProgress('same action and evidence failed twice; leave this route')
            db.execute('INSERT OR REPLACE INTO discovery_scenario_actions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                (state.run_id,fingerprint,stage,action,args_ref,before,None,None,'claimed',tries,0.,'read-only reconciliation of uncertain effect' if reconciling else 'read retry after retained failure' if prior else ''))
            db.execute('INSERT INTO discovery_scenario_attempts VALUES (?,?,?,?,?,?,?,?,?)',
                (state.run_id,fingerprint,tries,'claimed',before,None,None,0.,'read-only reconciliation of uncertain effect' if reconciling else 'read retry after retained failure' if prior else ''))
        started=time.monotonic()
        try:
            output=reconcile() if reconciling else operation()
            parsed=self.response_type.model_validate_json(json.dumps(output,allow_nan=False))
            if parsed.stage.value!=stage:raise ValueError('stage response identity differs')
            # A success flag/narration alone cannot satisfy the stage verifier.
            verify(output)
            ref=self.journal.put(output,'Report')
            artifacts={**state.stage_artifacts,stage:ref}
            projected=project(output)
            if set(projected)-self.allowed:raise ValueError('stage projection cannot alter workflow control state')
            next_state=state.model_copy(update={**projected,'stage':self.stage_type(stage),'stage_status':'completed' if stage=='completed' else 'verified',
                'state_revision':state.state_revision+1,'verified_stages':(*state.verified_stages,stage),
                'stage_artifacts':artifacts,'attempts':{**state.attempts,stage:tries}})
            after=digest(next_state.model_dump(mode='json'))
            next_state=self.state_type.model_validate_json(next_state.model_dump_json())
            next_ref=self.journal.put(next_state.model_dump(mode='json'),'Report')
            target=self.resolve(next_state.original_goal)
            key=self.key(target)
            with self.journal.tx() as db:
                # Commit checkpoint and result atomically; a crash cannot lose a
                # verified stage while leaving only an uncertain claim behind.
                db.execute('UPDATE discovery_scenario_projects SET state_ref=? WHERE goal_hash=?',(next_ref,key))
                db.execute('UPDATE discovery_scenario_actions SET category=?,result_ref=?,post_digest=?,seconds=? '
                    'WHERE run_id=? AND fingerprint=?',('verified',ref,after,time.monotonic()-started,state.run_id,fingerprint))
                db.execute('UPDATE discovery_scenario_attempts SET category=?,result_ref=?,post_digest=?,seconds=? '
                    'WHERE run_id=? AND fingerprint=? AND attempt=?',('verified',ref,after,time.monotonic()-started,state.run_id,fingerprint,tries))
            return next_state,output
        except BaseException as exc:
            category='blocked' if isinstance(exc,BlockedStage) else 'failed' if read_only else 'uncertain'
            reason=type(exc).__name__+': '+str(exc)[:800]
            with self.journal.tx() as db:
                db.execute('UPDATE discovery_scenario_actions SET category=?,seconds=?,retry_reason=? WHERE run_id=? AND fingerprint=?',
                    (category,time.monotonic()-started,reason,state.run_id,fingerprint))
                db.execute('UPDATE discovery_scenario_attempts SET category=?,seconds=?,retry_reason=? WHERE run_id=? AND fingerprint=? AND attempt=?',
                    (category,time.monotonic()-started,reason,state.run_id,fingerprint,tries))
            self.save(state.model_copy(update={'stage':self.stage_type(stage),'stage_status':'blocked' if read_only or category=='blocked' else 'uncertain',
                'failures':(*state.failures,reason),'attempts':{**state.attempts,stage:tries}}))
            raise

    def episode(self,run_id):
        rows=self.journal.rows('SELECT a.stage,a.action,a.arguments_ref,t.* FROM discovery_scenario_attempts t '
            'JOIN discovery_scenario_actions a ON a.run_id=t.run_id AND a.fingerprint=t.fingerprint WHERE t.run_id=? ORDER BY t.rowid',(run_id,))
        for row in rows:
            row['arguments']=json.loads(self.journal.get(row.pop('arguments_ref')))
            row['evidence_changed']=bool(row['post_digest'] and row['post_digest']!=row['pre_digest'])
            row['artifact_files']={};row['budget_usage']={}
            if row['result_ref']:
                output=json.loads(self.journal.get(row['result_ref']));row['artifact_files']=output.get('files',{})
                facts=output.get('facts',{})
                ref=facts.get('study_ref') or facts.get('prepared_ref')
                if ref:
                    actual=json.loads(self.journal.get(ref))
                    row['budget_usage']={k:actual[k] for k in ('cpu_s','slot','worker_sha256') if k in actual}
        return rows
