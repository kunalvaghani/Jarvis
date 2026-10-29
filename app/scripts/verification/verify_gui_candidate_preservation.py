"""Replay exact retained Qwen source through candidate guards; no app edits."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from uuid import uuid4

BASE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(BASE))
from jarvis.candidate_checks import CandidateChecks,CandidateRegression
from jarvis.codex_workload import fingerprint
from jarvis.codex_validation import validate_project,source_path


def main():
    from jarvis.campaign_pause import assert_allowed
    assert_allowed(whole_campaign=True)
    old=BASE/'.jarvis-runtime/autonomous-repair/458aa08047f74b079eeb3ac8e6450902'
    campaign=json.loads((old/'campaign.json').read_text(encoding='utf-8'))
    if not campaign.get('finished_at'):raise ValueError('Prior owner must be terminal.')
    native=old/'.jarvis-runtime/native-code/14b15daf6774416c996b4d94f49551e5'
    request=json.loads((native/'request.json').read_text(encoding='utf-8'))
    project=Path(campaign['workspace_parent']).resolve(strict=True)
    before=fingerprint(project)
    if before!=campaign['source_before']:raise ValueError('Retained checkpoint changed; no replay.')
    selected=None
    for path in sorted(native.glob('validation-*.json'),key=lambda p:p.stat().st_mtime):
        value=json.loads(path.read_text(encoding='utf-8'))
        if not any('cannot use geometry manager pack' in e.get('error','') for e in value.get('errors',[])):continue
        for error in value['errors']:
            for filename in re.findall(r'File "([^"\r\n]+)"',error.get('error','')):
                snapshot=Path(filename.replace('\\\\','\\')).parent.resolve()
                if snapshot.parent!=native or not snapshot.name.startswith('check-workspace-'):continue
                if not all(source_path(snapshot,name).is_file() and hashlib.sha256(source_path(snapshot,name).read_bytes()).hexdigest()==sha for name,sha in value['hashes'].items()):continue
                selected=(path,value,snapshot);break
            if selected:break
        if selected:break
    if not selected:raise ValueError('No intact recorded Qwen regression snapshot.')
    validation_path,value,snapshot=selected
    content=source_path(snapshot,'ui_builder.py').read_bytes().decode('utf-8')
    parent=BASE/'.jarvis-runtime/gui-candidate-preservation'/uuid4().hex
    baseline_run=parent/'baseline';baseline_run.mkdir(parents=True)
    plan=request['validation_contract'];goal=campaign['request']
    baseline=validate_project(project,baseline_run,goal,[],plan,lambda:False,lambda *args:None)
    checker=CandidateChecks(project,parent,goal,plan,lambda:False,lambda *args:None)
    rejected=False
    try:checker.check('ui_builder.py',content,baseline)
    except CandidateRegression:rejected=True
    unchanged=fingerprint(project)==before
    decision=checker.decisions[0] if checker.decisions else {}
    lost=decision.get('lost_previously_passing_cases',{})
    preserved_initial='test_gui_behavior.TestCalculatorGUI.test_display_initial_state' in lost.get('test_gui_behavior.py',[])
    result={'date':datetime.now(timezone.utc).isoformat(),'status':'PASS' if rejected and unchanged and preserved_initial else 'FAIL',
        'application_acceptance':False,'scope':'Exact complete retained Qwen implementation replayed only in isolated candidate snapshots. Original application and frozen tests unchanged.',
        'source_trial':old.name,'source_validation':validation_path.relative_to(BASE).as_posix(),
        'source_validation_sha256':hashlib.sha256(validation_path.read_bytes()).hexdigest(),
        'proposed_source_sha256':hashlib.sha256(content.encode('utf-8')).hexdigest(),
        'baseline_evidence':baseline.get('evidence'),'baseline_outcomes':baseline.get('python_test_outcomes'),
        'candidate_decision':decision,'candidate_rejected_before_working_save':rejected,
        'original_eight_file_hashes_unchanged':unchanged,'before_hashes':before,
        'limitations':'Controller regression proof, not a repaired GUI, new generation, visual acceptance or release acceptance.'}
    (parent/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    target=BASE/'artifacts/autonomous-repair/candidate-preservation-gui-regression.json'
    target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':result['status'],'evidence':str(target),'source_unchanged':unchanged}))
    return 0 if result['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
