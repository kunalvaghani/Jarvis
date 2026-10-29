"""Independent Test 9 observations. Never edits the acceptance application's source."""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

sys.dont_write_bytecode=True


def fingerprints(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def main():
    parser=argparse.ArgumentParser();parser.add_argument('campaign',type=Path);args=parser.parse_args()
    run=args.campaign.resolve(strict=True);campaign=json.loads((run/'campaign.json').read_text(encoding='utf-8'))
    if campaign.get('case')!=9:parser.error('Requires the controlled existing-project search campaign.')
    project=Path(campaign['workspace_parent']).resolve(strict=True);before=fingerprints(project)
    record={'date':datetime.now(timezone.utc).isoformat(),'status':'FAIL','campaign':run.name,
        'scope':'Independent controlled Notes API search/regression acceptance; not fresh application creation, GUI or memory-reuse proof.',
        'campaign_harness_result':campaign['result'],'project':str(project),'checks':[],'errors':[],
        'artifact_hashes':before,'source_changed_during_generation':campaign.get('jarvis_source_changed_during_trial'),
        'supervisor_authored_implementation':False,'supervisor_authored_fixture_and_probes':True}
    def check(name,call):
        try:call();record['checks'].append({'name':name,'passed':True})
        except Exception as error:record['errors'].append({'name':name,'type':type(error).__name__,'error':str(error)})
    def require(value,message):
        if not value:raise AssertionError(message)
    check('production task completed',lambda:require(any(r['state']=='COMPLETED' and r['command']['kind']=='code_task' for r in campaign['tasks']),'No completed production coding task.'))
    check('unrelated README/sentinel and frozen baseline tests unchanged',lambda:require(all(
        before.get(name)==campaign['source_before'].get(name) for name in ('README.md','UNCHANGED.txt','test_notes.py')),'Unrelated/frozen source changed.'))
    notes=load(project/'notes.py','controlled_notes_acceptance').Notes()
    first=notes.add('  Alpha notebook  ');second=notes.add('Blue folder');notes.add('Green pencil')
    original=notes.all()
    check('case-insensitive substring search',lambda:require(notes.search('ALPHA')==['Alpha notebook'] and notes.search('book')==['Alpha notebook'],'Case/substring result mismatch.'))
    check('empty/missing/non-string queries',lambda:require(notes.search('')==list(original.values()) and notes.search('absent')==[] and notes.search(None)==[] and notes.search(123)==[],'Query edge-case mismatch.'))
    result=notes.search('alpha');result.append('outside result mutation')
    check('search and result mutation preserve stored notes',lambda:require(notes.all()==original,'Search mutated existing data.'))
    notes.add('Alpha notebook')
    check('duplicate matches retained',lambda:require(notes.search('alpha')==['Alpha notebook','Alpha notebook'],'Duplicate search result lost.'))
    notes.remove(first)
    check('removed note no longer matched',lambda:require(notes.search('alpha')==['Alpha notebook'] and second in notes.all(),'Removal/search integration failed.'))
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
    def cli():
        result=subprocess.run([sys.executable,str(project/'notes.py'),'list'],cwd=project,env=env,
            stdin=subprocess.DEVNULL,capture_output=True,text=True,encoding='utf-8',timeout=15)
        require(result.returncode==0 and list(json.loads(result.stdout).values())==['Red notebook','Blue folder','Green pencil'],'Original CLI list behavior changed.')
    check('original real CLI list subprocess',cli)
    helper=load(project/'search_notes.py','controlled_search_helper_acceptance')
    check('additional helper valid substring inputs',lambda:require(helper.search_notes(['Amber','Blue','AMBER'],'amber')==['Amber','AMBER'],'Added helper substring mismatch.'))
    def helper_cli():
        result=subprocess.run([sys.executable,str(project/'search_notes.py'),'Red'],cwd=project,env=env,
            stdin=subprocess.DEVNULL,capture_output=True,text=True,encoding='utf-8',timeout=15)
        require(result.returncode==0 and ast.literal_eval(result.stdout)==['Red notebook'],'Added sample CLI helper failed.')
    check('additional sample-data CLI helper subprocess',helper_cli)
    def unittests():
        result=subprocess.run([sys.executable,'-m','unittest','discover','-v'],cwd=project,env=env,
            stdin=subprocess.DEVNULL,capture_output=True,text=True,encoding='utf-8',timeout=30)
        record['unittest']={'returncode':result.returncode,'output':result.stdout+result.stderr}
        require(result.returncode==0 and 'Ran 9 tests' in record['unittest']['output'],'Fresh combined tests failed or expected tests were not discovered.')
    check('fresh original plus generated unittest discovery',unittests)
    check('acceptance observation made no source changes',lambda:require(fingerprints(project)==before,'Source changed during independent observation.'))
    record['limitations']=['Additional helper CLI uses sample data; primary existing Notes API is the feature acceptance surface.',
        'Helper empty-query semantics differ from Notes.search; no single unified CLI search interface is claimed.',
        'No general Unicode collation, persistence, GUI, cross-project reuse or fresh-project success claim.']
    if not record['errors']:record['status']='PASS'
    target=run/('independent-acceptance-'+uuid4().hex+'.json');target.write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps({'status':record['status'],'checks':len(record['checks']),'errors':record['errors'],'evidence':str(target)}))
    return 0 if record['status']=='PASS' else 1


if __name__=='__main__':sys.exit(main())
