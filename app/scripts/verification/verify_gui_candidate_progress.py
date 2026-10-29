"""Reject exact retained neutral Qwen source; never author or save app code."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
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
    old=BASE/'.jarvis-runtime/autonomous-repair/160ce0dfd45f49a99122712fd48c9a51'
    campaign=json.loads((old/'campaign.json').read_text(encoding='utf-8'))
    if not campaign.get('finished_at'):raise ValueError('Prior owner must be terminal.')
    native=old/'.jarvis-runtime/native-code/dde61838c5dd4f0792f7ea5ed2520a07'
    request=json.loads((native/'request.json').read_text(encoding='utf-8'))
    project=Path(campaign['workspace_parent']).resolve(strict=True);before=fingerprint(project)
    if before!=campaign['source_before']:raise ValueError('Original checkpoint changed; no replay.')
    selected=None
    for path in sorted((native/'candidate-checks').glob('*/candidate-decision.json')):
        decision=json.loads(path.read_text(encoding='utf-8'))
        if decision.get('accepted_for_save') is not True or decision.get('lost_previously_passing_cases'):continue
        evidence=Path(decision['candidate_evidence']).resolve(strict=True)
        if evidence.parent!=path.parent.resolve() or not evidence.name.startswith('validation-'):continue
        value=json.loads(evidence.read_text(encoding='utf-8'));snapshot=path.parent/'input'
        if not all(source_path(snapshot,name).is_file() and hashlib.sha256(source_path(snapshot,name).read_bytes()).hexdigest()==sha
                   for name,sha in value['hashes'].items()):continue
        if not all(hashlib.sha256(source_path(snapshot,name).read_bytes()).hexdigest()==sha
                   for name,sha in before.items() if name not in {'ui_builder.py','README.md'}):continue
        raw=source_path(snapshot,'ui_builder.py').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=decision['proposed_sha256']:continue
        selected=(path,evidence,raw);break
    if selected is None:raise ValueError('No intact retained accepted neutral candidate.')
    decision_path,validation_path,raw=selected
    parent=BASE/'.jarvis-runtime/gui-candidate-progress'/uuid4().hex
    baseline_run=parent/'baseline';baseline_run.mkdir(parents=True)
    plan=request['validation_contract'];goal=campaign['request']
    baseline=validate_project(project,baseline_run,goal,[],plan,lambda:False,lambda *args:None)
    checker=CandidateChecks(project,parent,goal,plan,lambda:False,lambda *args:None)
    rejected=False
    try:checker.check('ui_builder.py',raw.decode('utf-8'),baseline,require_progress=True)
    except CandidateRegression:rejected=True
    unchanged=fingerprint(project)==before
    decision=checker.decisions[-1] if checker.decisions else {}
    neutral=(not decision.get('lost_previously_passing_cases') and not decision.get('newly_passing_cases')
             and not decision.get('errors_reaching_assertions') and not decision.get('new_runtime_errors'))
    passed=rejected and unchanged and neutral and decision.get('progress_required') is True and decision.get('accepted_for_save') is False
    result={'date':datetime.now(timezone.utc).isoformat(),'status':'PASS' if passed else 'FAIL',
        'application_acceptance':False,'scope':'Exact complete retained Qwen source executed only in an isolated candidate; no app implementation authored or saved by supervisor.',
        'source_campaign':old.name,'source_decision':decision_path.relative_to(BASE).as_posix(),
        'source_validation':validation_path.relative_to(BASE).as_posix(),
        'source_validation_sha256':hashlib.sha256(validation_path.read_bytes()).hexdigest(),
        'proposed_source_sha256':hashlib.sha256(raw).hexdigest(),'baseline_evidence':baseline.get('evidence'),
        'baseline_outcomes':baseline.get('python_test_outcomes'),'candidate_decision':decision,
        'rejected_before_working_save':rejected,'original_eight_file_hashes_unchanged':unchanged,'before_hashes':before,
        'limitations':'Controller/progress-gate regression proof; no repaired GUI, physical/visual, fresh generation or release acceptance.'}
    (parent/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    target=BASE/'artifacts/autonomous-repair/candidate-progress-gui-regression.json'
    target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':result['status'],'evidence':str(target),'original_unchanged':unchanged}))
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
