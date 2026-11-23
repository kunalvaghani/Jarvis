"""Independent read-only acceptance audit of a terminal Jarvis-created project.

No solver/model call, stage completion, operator case data or original-run edit.
PASS is explicitly limited to the user-authorized educational surrogate scope.
"""
import argparse,hashlib,json,sqlite3,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];APP=ROOT/'app';sys.path.insert(0,str(APP))


class ReadJournal:
    def __init__(self,path):
        self.db=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True);self.db.row_factory=sqlite3.Row
    def rows(self,sql,args=()):return [dict(r) for r in self.db.execute(sql,args)]
    def get(self,ref):
        rows=self.rows('SELECT body FROM artifacts WHERE ref=?',(ref,))
        return rows[0]['body'] if rows else None


def audit(home):
    from jarvis.discovery.acceptance import artifact
    from jarvis.discovery.model.scenario_a import ScenarioAVehicleState,STAGES,resolve
    from jarvis.discovery.scenario_checks import verify_stage
    from jarvis.discovery.scenario_verify import verify
    from jarvis.discovery.adapters.chrono import worker_hash
    receipt=json.loads((home/'result-private.json').read_text())
    if receipt.get('error') or receipt.get('model_or_solver_patches') is not False or not receipt.get('no_prepared_case_json'):
        raise ValueError('attempt did not finish unassisted')
    if receipt['source_sha256_before']!=receipt['source_sha256_after']:raise ValueError('source changed during live attempt')
    if receipt['harness_sha256_before']!=receipt['harness_sha256_after']:raise ValueError('harness changed during live attempt')
    journal=ReadJournal(home/'brain.sqlite3')
    try:
        goals=journal.rows('SELECT * FROM goals WHERE text=? AND state=?',(receipt['goal'],'verified'))
        goals=[r for r in goals if json.loads(r['plan']).get('workflow')=='discovery.vehicle.scenario']
        task_files=list((home/'task-owner').rglob('task_state.json'))
        current=json.loads(task_files[0].read_text(encoding='utf-8'))['current']
        reports=[]
        for goal in goals:
            rows=journal.rows('SELECT result_ref FROM outbox WHERE goal_id=? AND node_id=? AND state=?',
                (goal['goal_id'],'discovery.vehicle.scenario@v1','done'))
            if rows:
                item=artifact(journal,artifact(journal,rows[0]['result_ref'])['report'])
                if item.get('task_id')==current['task_id']:reports.append(item)
        if len(reports)!=1 or current['status']!='completed':raise ValueError('one verified current-task project receipt required')
        report=reports[0]
        state=ScenarioAVehicleState.model_validate_json(journal.get(report['state_ref']))
        if state.verified_stages!=STAGES or state.stage_status!='completed':raise ValueError('stage completion missing')
        target=resolve(receipt['goal'])
        if not target.allow_surrogate:raise ValueError('surrogate scope not authorized by actual goal')
        for stage in STAGES:
            prefix=state.model_copy(update={'verified_stages':state.verified_stages[:STAGES.index(stage)],
                'stage_artifacts':{k:v for k,v in state.stage_artifacts.items() if STAGES.index(k)<STAGES.index(stage)}})
            verify_stage(stage,artifact(journal,state.stage_artifacts[stage]),base=APP,journal=journal,state=prefix,target=target)
        completed=artifact(journal,state.stage_artifacts['completed'])['facts'];manifest_path=completed['run_manifest']
        check=verify(APP,manifest_path);manifest=json.loads((APP/manifest_path).read_text())
        if manifest['worker_sha256']!=worker_hash():raise ValueError('current worker mismatch')
        root=(APP/manifest_path).parent
        episode=json.loads((root/'episode.json').read_text())
        if len(episode)!=len(STAGES) or any(r['category']!='verified' or not r['evidence_changed'] for r in episode):
            raise ValueError('repeated, failed or missing stage transition')
        raw=json.loads((root/'raw_solver_output.json').read_text())
        sources=json.loads((root/'sources.json').read_text());reg=sources['regulation']['regulation']
        return {'case':receipt['case'],'status':'PASS_CONDITIONAL_SURROGATE','exact_input':receipt['goal'],
            'original_exact_team_acceptance':False,'physical_validation':False,'operator_provided_solution':False,
            'seconds':receipt['seconds'],'model_calls':receipt['model_calls'],'stage_seconds':{r['stage']:r['seconds'] for r in episode},
            'chrono_slots_before':json.loads((home/'started.json').read_text()).get('chrono_slots_before'),
            'chrono_slots_after':receipt.get('chrono_slots_after'),
            'stage_count':len(episode),'no_repeated_transition':True,'run_id':state.run_id,
            'source_sha256':receipt['source_sha256_before'],'worker_sha256':worker_hash(),
            'solver':'Chrono::Vehicle 10.0.0 (actual approved CPU invocation)',
            'regulation':{k:reg[k] for k in ('url','publication_date','edition','sha256','limits')},
            'asset_provenance':'Bounded exact-season catalog read; no inspected engineering asset acquired. Explicitly authorized procedural class surrogate.',
            'found_vs_generated':{'acquired_asset_files':0,'generated_visual_components':11,'native_json_origin':'BSD-licensed Chrono templates + explicit model assumptions'},
            'physics':check['verification'],'metrics':manifest['comparison'],
            'mode_sets':{run['variant']:sorted({row['mode'] for row in run['samples']}) for run in raw['reports']['primary']['runs']},
            'artifacts':{'run_manifest':manifest_path,'report':completed['report'],'csv':(root/'raw_output.csv').relative_to(APP).as_posix(),
                'mesh':(root/'asset_or_surrogate.glb').relative_to(APP).as_posix(),'diagnostic_png':(root/'side.png').relative_to(APP).as_posix()},
            'artifact_hashes':manifest['files'],'independent_offline_audit_passed':check['passed'],
            'limits':['No exact proprietary team CAD or calibrated F1 aero/tire maps.','No demonstrated terminal top speed or race-lap prediction.',
                'Mechanical engine shaft energy excludes fuel/hybrid conversion losses.','Aero envelope is conditional; other uncertain input ranges are not exhaustively propagated.',
                'Generated PNGs are mesh/trace diagnostics, not desktop screenshots or physical evidence.']}
    finally:journal.db.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--case',choices=['A1','A2'],required=True);p.add_argument('--attempt',type=int,required=True)
    a=p.parse_args();home=APP/f'.jarvis-runtime/lab-validation/a-{a.case.lower()}-attempt-{a.attempt}'
    result=audit(home);dest=ROOT/f'docs/lab/evidence/scenario-{a.case.lower()}-attempt-{a.attempt}-audit.json'
    if dest.exists():raise ValueError('audit output already exists; immutable evidence is not overwritten')
    dest.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('case','status','seconds','model_calls','stage_count','no_repeated_transition','run_id')}))


if __name__=='__main__':main()
