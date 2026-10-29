import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from jarvis.codex_workload import localgithub, workload_contract, fingerprint, promote, run, propose, planning_schema, static_assignment, proposal_diagnostics, explicit_browser_steps, complete_single_test_ownership, single_python_source_goal
from jarvis.codex_files import execute
from jarvis.coder import Coder


def proposal():
    files=[];checks=[];tasks=[]
    for key in ('alpha','beta'):
        files.extend([{'path':key+'.py','role':'logic','purpose':'Implement '+key+' value'},
                      {'path':'test_'+key+'.py','role':'test','purpose':'Assert '+key+' behavior'}])
        checks.append({'kind':'python_tests','path':'test_'+key+'.py'})
        tasks.append({'key':key,'goal':'Implement the '+key+' pure value function and unittest.',
                      'estimated_minutes':3,'paths':[key+'.py','test_'+key+'.py'],'dependencies':[],
                      'check_indices':[len(checks)-1]})
    return {'interfaces':'Each module exports value() returning its module name. No shared runtime dependencies.',
            'files':files,'checks':checks,'tasks':tasks}


class Workloads(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.utilities,cls.git,_=localgithub({})

    def test_parent_constraints_survive_worker_handoff_and_existing_changes_cannot_promote(self):
        from jarvis.codex_workload import worker_request,preserve_existing_sources
        goal='Add new launch tests. Preserve every existing implementation, documentation and test file byte-for-byte; add only the new test file.'
        child=worker_request(goal,{'goal':'Planner suggested reimplementing the entrypoint'},'CLI')
        self.assertIn(goal,child)
        self.assertTrue(preserve_existing_sources(child))
        self.assertFalse(preserve_existing_sources('Preserve every existing test; repair implementation.'))
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);project=root/'project';project.mkdir();integration=root/'integration';integration.mkdir()
            (project/'main.py').write_text('original=1\n');(integration/'main.py').write_text('original=2\n')
            before=fingerprint(project)
            with self.assertRaisesRegex(ValueError,'preserves every existing'):
                promote(project,integration,root,' '+goal,{},before,['main.py'],lambda:False)
            self.assertEqual(fingerprint(project),before)

    def test_single_native_worker_uses_canonical_parent_goal_without_planner_diagnosis(self):
        from jarvis.codex_workload import worker_request
        goal='Implement controlled modules against the original interfaces and checks.'
        value=proposal();hypothesis='UNVERIFIED_PLANNER_HYPOTHESIS: repair a specific callback before observing failures.'
        value['tasks']=[{'key':'all','goal':hypothesis,'estimated_minutes':10,
            'paths':[row['path'] for row in value['files']],'dependencies':[],'check_indices':[0,1]}]
        seen=[]
        def observe(child,workspace,request,cancelled,**kwargs):
            seen.append(request)
            self.assertEqual(child.validation_goal,goal)
            raise ValueError('controlled handoff exit; no source action')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);project=root/'project';project.mkdir()
            coder=Coder(SimpleNamespace(base=root,report=lambda *row:None),SimpleNamespace(options={'max_coding_seconds':120}))
            with patch('jarvis.codex_workload.propose',return_value=value):
                with self.assertRaisesRegex(ValueError,'controlled handoff exit'):
                    run(coder,project,goal,executor=observe,backend='Jarvis')
            self.assertEqual(len(seen),1);self.assertIn(goal,seen[0]);self.assertNotIn(hypothesis,seen[0])
            self.assertIn('Assigned immutable file scope',seen[0]);self.assertIn('unverified',seen[0])
            self.assertEqual(list(project.iterdir()),[])
            receipt=json.loads(next((root/'.jarvis-runtime/native-workloads').glob('*/receipt.json')).read_text())
            self.assertEqual(receipt['worker_goal_source'],'canonical-parent-goal')
            self.assertEqual(json.loads(next((root/'.jarvis-runtime/native-workloads').glob('*/plan.json')).read_text())['tasks'][0]['goal'],hypothesis)
        # Existing split-worker/legacy request construction retains task guidance.
        self.assertIn(hypothesis,worker_request(goal,value['tasks'][0],value['interfaces']))

    def test_graph_ownership_cycles_checks_and_estimates(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            self.assertEqual(len(workload_contract(root,'Create modules',proposal(),self.utilities)['tasks']),2)
            cases=[]
            value=proposal();value['tasks'][1]['paths'][0]='alpha.py';cases.append(value)
            value=proposal();value['tasks'][0]['dependencies']=['beta'];value['tasks'][1]['dependencies']=['alpha'];cases.append(value)
            value=proposal();value['tasks'][0]['dependencies']=['missing'];cases.append(value)
            value=proposal();value['tasks'][0]['paths']=['.'];cases.append(value)
            value=proposal();value['tasks'][0]['estimated_minutes']=True;cases.append(value)
            value=proposal();value['tasks'][0]['check_indices']=[1];cases.append(value)
            value=proposal();value['tasks'][0]['paths'].pop();cases.append(value)
            for value in cases:
                with self.assertRaises(ValueError):workload_contract(root,'Create modules',value,self.utilities)

    def test_supported_twelve_file_unowned_split_keeps_every_file_and_check(self):
        from jarvis.codex_workload import collapse_unowned_split
        value={'files':[],'checks':[],'tasks':[],'interfaces':'Each module exports value(); all behavior is checked after assembly.'}
        for index in range(6):
            name=f'module{index}.py';test=f'test_module{index}.py'
            value['files'] += [{'path':name,'role':'logic','purpose':'Implement module value'},
                              {'path':test,'role':'test','purpose':'Check module behavior'}]
            value['checks'].append({'kind':'python_tests','path':test})
            value['tasks'].append({'key':f'module{index}','goal':'Implement the assigned value module and behavior.',
                'paths':[name,test],'check_indices':[0],'dependencies':[],'estimated_minutes':3})
        merged,changed=collapse_unowned_split(value)
        self.assertTrue(changed);self.assertEqual(merged['files'],value['files']);self.assertEqual(merged['checks'],value['checks'])
        self.assertEqual(len(merged['tasks']),1);self.assertEqual(len(merged['tasks'][0]['paths']),12)
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(len(workload_contract(Path(folder),'Create checked modules',merged,self.utilities)['files']),12)
        too_large={**value,'files':value['files']*3}
        self.assertFalse(collapse_unowned_split(too_large)[1])

    def test_merging_valid_estimates_does_not_create_an_invalid_worker(self):
        from jarvis.codex_workload import collapse_unowned_split
        value=proposal()
        for task in value['tasks']:task['estimated_minutes']=40;task['check_indices']=[0]
        original=json.loads(json.dumps(value))
        merged,changed=collapse_unowned_split(value)
        self.assertTrue(changed);self.assertEqual(value,original)
        self.assertEqual(merged['tasks'][0]['estimated_minutes'],60)
        self.assertEqual(merged['tasks'][0]['source_estimated_minutes'],80)
        with tempfile.TemporaryDirectory() as folder:
            checked=workload_contract(Path(folder),'Create Python modules',merged,self.utilities)
        self.assertEqual(checked['checks'],value['checks'])
        self.assertEqual(checked['files'],value['files'])

    def test_python_only_planner_excludes_unrelated_npm_checks(self):
        from jarvis.codex_workload import python_only_goal
        from jarvis.structured_output import validate_contract
        self.assertTrue(python_only_goal('Create a Python command-line calculator with tests.'))
        for goal,names in [('Create a Python backend and React frontend',[]),
                           ('Build Python full-stack website',[]),
                           ('Modify Python helpers',['app.tsx']),('Modify Python helpers',['package.json'])]:
            self.assertFalse(python_only_goal(goal,names))
        with tempfile.TemporaryDirectory() as folder:
            sent=[];value=proposal()
            class Response:
                def __enter__(self):return self
                def __exit__(self,*args):return False
                def raise_for_status(self):return None
                def iter_lines(self,**kwargs):yield json.dumps({'done':True,'message':{'content':json.dumps(value)}}).encode()
            class Client:
                def __enter__(self):return self
                def __exit__(self,*args):return False
                def post(self,url,**kwargs):sent.append(kwargs['json']);return Response()
            coder=Coder(SimpleNamespace(report=lambda *row:None),SimpleNamespace(options={}))
            with patch('jarvis.knowledge_worker.session',return_value=Client()),patch('jarvis.ollama_models.coding_model'),patch('jarvis.knowledge_worker.local_prompt_format',return_value='ollama_chat'):
                propose(coder,Path(folder),'Create a Python command-line calculator with tests.',lambda:False,time.monotonic()+3)
            checks=sent[0]['format']['properties']['checks']['items']
            validate_contract(checks,{'kind':'python_tests','path':'test_calc.py'})
            with self.assertRaises(ValueError):validate_contract(checks,{'kind':'npm_build','path':'package.json'})
            self.assertIn('Python only',sent[0]['messages'][0]['content'])

    def test_plain_fullstack_schema_excludes_npm_without_removing_browser_or_node_tests(self):
        from jarvis.codex_workload import package_stack_goal
        self.assertFalse(package_stack_goal('Create HTML CSS JavaScript with a Python HTTP backend and SQLite'))
        self.assertFalse(package_stack_goal('Complete the next step: HTML CSS JavaScript with a Python server and clickable node cards'))
        for goal,names in [('Create a React website',[]),('Create a Node.js backend',[]),
                           ('Fix current app',['web/package.json']),('Fix current UI',['src/App.jsx'])]:
            self.assertTrue(package_stack_goal(goal,names))
        with tempfile.TemporaryDirectory() as folder:
            sent=[];value=proposal()
            class Response:
                def __enter__(self):return self
                def __exit__(self,*args):return False
                def raise_for_status(self):return None
                def iter_lines(self,**kwargs):yield json.dumps({'done':True,'message':{'content':json.dumps(value)}}).encode()
            class Client:
                def __enter__(self):return self
                def __exit__(self,*args):return False
                def post(self,url,**kwargs):sent.append(kwargs['json']);return Response()
            coder=Coder(SimpleNamespace(report=lambda *row:None),SimpleNamespace(options={}))
            with patch('jarvis.knowledge_worker.session',return_value=Client()),patch('jarvis.ollama_models.coding_model'),patch('jarvis.knowledge_worker.local_prompt_format',return_value='ollama_chat'):
                propose(coder,Path(folder),'Create HTML CSS JavaScript with a Python backend and SQLite',lambda:False,time.monotonic()+3)
            variants=sent[0]['format']['properties']['checks']['items']['anyOf']
            kinds={v['properties']['kind']['enum'][0] for v in variants}
            self.assertIn('node_tests',kinds);self.assertIn('python_tests',kinds);self.assertIn('browser',kinds)
            self.assertFalse(any(k.startswith('npm_') for k in kinds))
            browser=next(v for v in variants if v['properties']['kind']['enum']==['browser'])
            self.assertIn('server',browser['required'])

    def test_new_plain_website_assigns_source_and_tests_without_authoring_code(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);goal='Build a plain animated website using index.html, styles.css and app.js.'
            value=static_assignment(root,goal)
            self.assertEqual(len(value['tasks']),3);self.assertEqual(len(value['files']),3)
            self.assertTrue(all(len(t['paths'])==1 for t in value['tasks']))
            self.assertTrue(all(c['kind']=='browser_component' for c in value['checks']))
            self.assertEqual(value['tasks'][1]['dependencies'],['markup'])
            self.assertEqual(value['tasks'][2]['dependencies'],['markup'])
            self.assertIn('normal browser script',value['tasks'][2]['goal'])
            self.assertEqual(static_assignment(root,'Build an animated website')['tasks'][0]['paths'][0],'index.html')
            self.assertIsNone(static_assignment(root,'Build a single-file animated website'))
            self.assertEqual(list(root.iterdir()),[])

            # Real registration creates these reference documents before coding.
            (root/'PROJECT.md').write_text('Registered project objective')
            (root/'REQUIREMENTS.md').write_text('Authoritative reference specification')
            before=fingerprint(root)
            self.assertEqual(len(static_assignment(root,goal)['tasks']),3)
            self.assertEqual(fingerprint(root),before)
            documented=static_assignment(root,goal+' Include a README with local launch instructions.')
            self.assertIn('README.md',documented['tasks'][0]['paths'])
            self.assertEqual(documented['files'][-1]['role'],'documentation')
            self.assertIn('Write ONLY index.html and README.md',documented['tasks'][0]['goal'])

            self.assertIsNone(static_assignment(root,'Build a React website using index.html, styles.css and app.js.'))
            (root/'index.html').write_text('<html><body>Existing page</body></html>')
            self.assertIsNone(static_assignment(root,goal))

    def test_planner_diagnostics_report_missing_test_owners_together(self):
        value=proposal();value['tasks'][0]['paths'].pop();value['tasks'][1]['paths'].pop()
        diagnosis=proposal_diagnostics(value,ValueError('Missing tests'))
        self.assertTrue(any('test_alpha.py' in row for row in diagnosis['errors']))
        self.assertTrue(any('test_beta.py' in row for row in diagnosis['errors']))

    def test_typed_check_and_react_feedback_retains_paths_without_repeating_large_prose(self):
        from jarvis.codex_workload import planning_feedback
        value=proposal();value['interfaces']='long shared interface '*1000
        value['checks'][0]={'kind':'node_tests','path':'test_alpha.py'}
        diagnosis=proposal_diagnostics(value,ValueError('A new React project requires an executable npm_build check'))
        self.assertTrue(any('test_alpha.py' in s and 'Python unittest' in s for s in diagnosis['errors']))
        self.assertTrue(any('package.json' in s and 'npm_build' in s for s in diagnosis['errors']))
        compact=planning_feedback(diagnosis)
        self.assertEqual(compact['previous_checks'][0],value['checks'][0])
        self.assertNotIn('interfaces',compact)
        self.assertIs(diagnosis['previous_proposal'],value)
        self.assertLess(len(json.dumps(compact)),2500)
        self.assertEqual(planning_feedback({'errors':['Expected arrays'],'previous_proposal':{'files':None,'checks':None}})['previous_checks'],[])
        huge={'checks':[{'kind':'browser','path':'x'*10000,'server':{'path':{'nested':['x'*10000]}}}]*50,
              'files':[{'path':'x'*10000,'role':'frontend'}]*100}
        self.assertLessEqual(len(json.dumps(planning_feedback({'errors':['bad']*20,'previous_proposal':huge}))),5000)

    def test_fullstack_correction_targets_declared_frontend_not_test_copy(self):
        from jarvis.codex_workload import constrain_frontend_correction
        from jarvis.structured_output import validate_contract
        schema=planning_schema(full_stack=True)
        self.assertEqual(constrain_frontend_correction(schema,{'previous_files':[
            {'path':'index.html','role':'frontend'},{'path':'test_ui.html','role':'test'},
            {'path':'style.css','role':'frontend'}]}),['index.html'])
        check=schema['properties']['checks']['items']
        value={'kind':'browser','path':'index.html','server':{'kind':'python','path':'server.py'},
               'steps':[{'action':'text','selector':'h1','value':'Tasks'}]}
        validate_contract(check,value)
        with self.assertRaises(ValueError):validate_contract(check,{**value,'path':'test_ui.html'})
        self.assertEqual(constrain_frontend_correction(planning_schema(True),None),[])

    def test_npm_correction_keeps_manifest_paths_and_prioritizes_check_feedback(self):
        from jarvis.codex_workload import constrain_manifest_correction,planning_feedback
        from jarvis.structured_output import validate_contract
        value=proposal();value['files'].append({'path':'web/package.json','role':'configuration'})
        value['checks'].append({'kind':'npm_test','path':'test/index.test.js'})
        for i in range(8):value['tasks'].append({'key':str(i),'paths':[],'check_indices':[0]})
        diagnostic=proposal_diagnostics(value,ValueError('Bad path. Evidence: '+'x'*3000))
        compact=planning_feedback(diagnostic)
        self.assertTrue(any('npm_test' in e and 'package.json' in e for e in compact['errors']))
        self.assertFalse(any('Evidence:' in e for e in compact['errors']))
        self.assertIs(diagnostic['previous_proposal'],value)
        schema=planning_schema();self.assertEqual(constrain_manifest_correction(schema,compact),['web/package.json'])
        check=schema['properties']['checks']['items']
        validate_contract(check,{'kind':'npm_test','path':'web/package.json'})
        with self.assertRaises(ValueError):validate_contract(check,{'kind':'npm_test','path':'test/index.test.js'})
        with self.assertRaises(ValueError):validate_contract(planning_schema()['properties']['checks']['items'],{'kind':'npm_build','path':'config.json'})

    def test_diagnostics_report_all_workers_with_empty_or_invalid_check_indices(self):
        value=proposal();value['tasks'][0]['check_indices']=[];value['tasks'][1]['check_indices']=[99]
        errors=proposal_diagnostics(value,ValueError('Invalid checks'))['errors']
        self.assertTrue(any('Worker alpha needs nonempty check_indices' in row for row in errors))
        self.assertTrue(any('Worker beta needs nonempty check_indices' in row for row in errors))
        self.assertEqual(planning_schema()['properties']['tasks']['items']['properties']['check_indices']['minItems'],1)

    def test_unnamed_python_script_rejects_language_drift_and_split_workers_before_writes(self):
        goal='create a python script for drawing circle on screen in test codes folder'
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);value=proposal()
            with self.assertRaisesRegex(ValueError,'single Python script'):workload_contract(root,goal,value,self.utilities)
            value['tasks']=value['tasks'][:1];value['checks']=value['checks'][:1];value['files']=value['files'][:2]
            self.assertEqual(len(workload_contract(root,goal,value,self.utilities)['tasks']),1)
            value['files'][0]['path']='index.html';value['tasks'][0]['paths'][0]='index.html'
            with self.assertRaisesRegex(ValueError,'HTML/CSS/JavaScript'):workload_contract(root,goal,value,self.utilities)
            self.assertEqual(list(root.iterdir()),[])

    def test_python_implementation_role_and_gui_check_faults_fail_before_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);value=proposal()
            value['files']=value['files'][:2];value['tasks']=value['tasks'][:1];value['checks']=value['checks'][:1]
            value['files'][0]['role']='test'
            with self.assertRaisesRegex(ValueError,'Never label the implementation'):workload_contract(root,'Create a Python script',value,self.utilities)
            value['files'][0]['role']='entrypoint';value['checks'].append({'kind':'python_script','path':'alpha.py'})
            value['tasks'][0]['check_indices'].append(1)
            with self.assertRaisesRegex(ValueError,'persistent event loop'):workload_contract(root,'Create a Python script drawing on screen',value,self.utilities)
            self.assertEqual(len(workload_contract(root,'Create a Python script printing a result',value,self.utilities)['tasks']),1)
            self.assertEqual(list(root.iterdir()),[])

    def test_single_worker_declared_test_ownership_is_completed_without_source_or_plan_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);value=proposal()
            value['files']=value['files'][:2];value['checks']=value['checks'][:1];value['tasks']=value['tasks'][:1]
            value['tasks'][0]['paths']=['alpha.py']
            before=json.dumps(value,sort_keys=True)
            completed,added=complete_single_test_ownership(value)
            self.assertEqual(added,['test_alpha.py'])
            self.assertEqual(json.dumps(value,sort_keys=True),before)
            self.assertEqual(completed['checks'],value['checks'])
            self.assertEqual(workload_contract(root,'Create module',completed,self.utilities)['tasks'][0]['paths'],['alpha.py','test_alpha.py'])
            self.assertEqual(list(root.iterdir()),[])

    def test_ownership_completion_never_redistributes_or_adds_undeclared_files(self):
        value=proposal();value['tasks'][0]['paths'].pop()
        self.assertEqual(complete_single_test_ownership(value),(value,[]))
        value['tasks']=value['tasks'][:1];value['files']=value['files'][:2];value['checks']=value['checks'][:1]
        value['tasks'][0]['dependencies']=['peer']
        self.assertEqual(complete_single_test_ownership(value),(value,[]))
        value['tasks'][0]['dependencies']=[];value['files'][1]['role']='logic'
        self.assertEqual(complete_single_test_ownership(value),(value,[]))
        value['files'][1]['role']='test';value['checks'][0]['path']='undeclared_test.py'
        self.assertEqual(complete_single_test_ownership(value),(value,[]))

    def test_single_worker_omitted_declared_files_get_one_owner_without_writes(self):
        from jarvis.codex_workload import complete_single_file_ownership
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);value=proposal()
            value['tasks']=[{'key':'all','goal':'Repair declared source and preserve original references',
                'estimated_minutes':10,'paths':['alpha.py','test_alpha.py'],'dependencies':[],
                'check_indices':[0,1]}]
            original=json.dumps(value,sort_keys=True)
            completed,added=complete_single_file_ownership(value)
            self.assertEqual(added,['beta.py','test_beta.py'])
            self.assertEqual(json.dumps(value,sort_keys=True),original)
            normalized=workload_contract(root,'Repair declared modules',completed,self.utilities)
            self.assertEqual(normalized['tasks'][0]['paths'],['alpha.py','beta.py','test_alpha.py','test_beta.py'])
            self.assertEqual(completed['files'],value['files'])
            self.assertEqual(completed['checks'],value['checks'])
            self.assertEqual(list(root.iterdir()),[])
            self.assertEqual(complete_single_file_ownership(completed),(completed,[]))
            for invalid in [proposal(),{**value,'tasks':[{**value['tasks'][0],'dependencies':['peer']}]},
                            {**value,'files':[{'role':'logic'}]}]:
                self.assertEqual(complete_single_file_ownership(invalid),(invalid,[]))

    def test_existing_explicitly_frozen_check_metadata_is_completed_without_write_rights(self):
        from jarvis.codex_workload import complete_frozen_test_metadata,complete_single_file_ownership
        from jarvis.coding_files import FileSession
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);value=proposal();value['files']=value['files'][:1]
            value['checks']=value['checks'][:1];value['tasks']=value['tasks'][:1]
            value['tasks'][0]['paths']=['alpha.py']
            (root/'test_alpha.py').write_bytes(b'import unittest\r\nclass Checks(unittest.TestCase):\r\n def test_value(self): self.assertTrue(True)\r\n')
            before=fingerprint(root);original=json.dumps(value,sort_keys=True)
            goal='Repair alpha.py. Preserve test_alpha.py byte-for-byte.'
            completed,added=complete_frozen_test_metadata(value,root,goal,before)
            self.assertEqual(added,['test_alpha.py']);self.assertEqual(json.dumps(value,sort_keys=True),original)
            completed,_=complete_single_file_ownership(completed)
            normalized=workload_contract(root,goal,completed,self.utilities)
            self.assertEqual(completed['checks'],value['checks']);self.assertEqual(completed['tasks'][0]['goal'],value['tasks'][0]['goal'])
            self.assertEqual(fingerprint(root),before)
            run=root/'run';run.mkdir();(run/'request.json').write_text(json.dumps({'validation_goal':goal}))
            (run/'validation-contract.json').write_text(json.dumps(normalized))
            session=FileSession(root,run)
            with self.assertRaisesRegex(ValueError,'assertions are fixed'):session.protect('test_alpha.py')
            self.assertEqual(complete_frozen_test_metadata(completed,root,goal,before),(completed,[]))
            for candidate,candidate_goal in ((value,'Repair alpha.py.'),
                    ({**value,'tasks':value['tasks']*2},goal),
                    ({**value,'tasks':[{**value['tasks'][0],'dependencies':['peer']}]},goal),
                    ({**value,'checks':[{'kind':'python_tests','path':'../test_alpha.py'}]},goal)):
                self.assertEqual(complete_frozen_test_metadata(candidate,root,candidate_goal,before),(candidate,[]))
            (root/'test_alpha.py').write_text('changed = True\n')
            self.assertEqual(complete_frozen_test_metadata(value,root,goal,before),(value,[]))

    def test_backend_worker_can_test_part_while_final_contract_requires_both_layers(self):
        from jarvis.codex_validation import contract
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            value={'files':[{'path':'server.py','role':'backend','purpose':'Implement actual count API'},
                            {'path':'test_server.py','role':'test','purpose':'Assert count API persistence'}],
                   'checks':[{'kind':'python_tests','path':'test_server.py'}]}
            self.assertEqual(contract(root,'Implement backend',value,partial=True),value)
            with self.assertRaisesRegex(ValueError,'both frontend and backend'):contract(root,'Implement backend',value)

    def test_file_tools_enforce_assignment_before_saves(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'project';root.mkdir();directory=Path(folder)/'run';directory.mkdir()
            (directory/'request.json').write_text(json.dumps({'goal':'Create logic','allowed_paths':['alpha.py']}))
            with patch.dict(os.environ,{'JARVIS_CODEX_PROJECT':str(root),'JARVIS_CODEX_RUN':str(directory)}):
                with self.assertRaisesRegex(ValueError,'another worker'):
                    execute('Write',{'file_path':'beta.py','content':'def value():\n    return 1\n'})
                self.assertFalse((root/'beta.py').exists())
                self.assertTrue(execute('Write',{'file_path':'alpha.py','content':'def value():\n    return 1\n'})['saved'])

    def test_registered_worker_plan_cannot_be_replaced_or_broadened(self):
        from jarvis.codex_validation import declare
        from jarvis.codex_code import configuration,MODEL
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'project';root.mkdir();directory=Path(folder)/'run';directory.mkdir()
            value=proposal();plan={'files':value['files'][:2],'checks':value['checks'][:1]}
            (directory/'request.json').write_text(json.dumps({'goal':'Implement alpha','allowed_paths':['alpha.py','test_alpha.py']}))
            (directory/'validation-contract.json').write_text(json.dumps(plan))
            result=declare(root,directory,{'plans':'quoted mistaken plan'})
            self.assertTrue(result['assignment_unchanged']);self.assertEqual(result['files'],plan['files'])
            self.assertEqual(json.loads((directory/'validation-contract.json').read_text()),plan)
            settings=configuration(root,directory,MODEL,12345)
            self.assertIn('enabled_tools = ["Read", "Write", "Edit"]',settings)

    def test_partition_requires_missing_behavioral_test_before_implementation(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'project';root.mkdir();directory=Path(folder)/'run';directory.mkdir()
            value=proposal();plan={'files':value['files'][:2],'checks':value['checks'][:1]}
            (directory/'request.json').write_text(json.dumps({'goal':'Implement alpha','allowed_paths':['alpha.py','test_alpha.py'],'test_first':True}))
            (directory/'validation-contract.json').write_text(json.dumps(plan))
            with patch.dict(os.environ,{'JARVIS_CODEX_PROJECT':str(root),'JARVIS_CODEX_RUN':str(directory)}):
                with self.assertRaisesRegex(ValueError,'test first'):
                    execute('Write',{'file_path':'alpha.py','content':'def value():\n    return 1\n'})
                self.assertFalse((root/'alpha.py').exists());self.assertFalse((directory/'file-events.jsonl').exists())
                execute('Write',{'file_path':'test_alpha.py','content':'import unittest\nfrom alpha import value\nclass Checks(unittest.TestCase):\n    def test_value(self):\n        self.assertEqual(value(),1)\n'})
                self.assertTrue(execute('Write',{'file_path':'alpha.py','content':'def value():\n    return 1\n'})['saved'])

    def test_partial_references_deferred_only_for_declared_other_workers(self):
        from jarvis.codex_validation import inspect
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'index.html').write_text('<html><body>Hello<script src="app.js"></script><link rel="stylesheet" href="styles.css"></body></html>')
            plan={'files':[{'path':'index.html','role':'frontend','purpose':'Display real controls'}],'checks':[]}
            errors,_=inspect(root,plan,[],'Create index.html connecting app.js and styles.css',['app.js','styles.css'])
            self.assertEqual(errors,[])
            errors,_=inspect(root,plan,[],'Create index.html connecting app.js and styles.css')
            self.assertTrue(any(e['path']=='app.js' and 'resource' in e['error'] for e in errors))

    def test_read_only_planner_stop_is_prompt_during_model_prefill(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);release=threading.Event();entered=threading.Event();stop=threading.Event()
            class Response:
                def __enter__(self):return self
                def __exit__(self,*args):return False
                def raise_for_status(self):return None
                def iter_lines(self,**kwargs):
                    entered.set();release.wait(timeout=3)
                    yield json.dumps({'done':True,'message':{'content':'{}'}}).encode()
            class Client:
                def __enter__(self):return self
                def __exit__(self,*args):return False
                def post(self,*args,**kwargs):return Response()
            coder=Coder(SimpleNamespace(report=lambda *row:None),SimpleNamespace(options={}))
            def stopper():entered.wait(timeout=3);stop.set()
            thread=threading.Thread(target=stopper);thread.start();started=time.monotonic()
            with patch('jarvis.knowledge_worker.session',return_value=Client()),patch('jarvis.ollama_models.coding_model'),patch('jarvis.knowledge_worker.local_prompt_format',return_value='ollama_chat'):
                with self.assertRaisesRegex(ValueError,'planning stopped'):propose(coder,root,'Build a website',stop.is_set,time.monotonic()+5)
            self.assertLess(time.monotonic()-started,1);release.set();thread.join(timeout=1)
            self.assertEqual(list(root.iterdir()),[])
            self.assertEqual(planning_schema()['properties']['interfaces']['type'],'string')

    def test_raw_template_planner_uses_roles_and_structured_schema(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);sent=[]
            class Response:
                def __enter__(self):return self
                def __exit__(self,*args):return False
                def raise_for_status(self):return None
                def iter_lines(self,**kwargs):
                    yield json.dumps({'done':True,'response':json.dumps(proposal())}).encode()
            class Client:
                def __enter__(self):return self
                def __exit__(self,*args):return False
                def post(self,url,**kwargs):sent.append((url,kwargs));return Response()
            coder=Coder(SimpleNamespace(report=lambda *row:None),SimpleNamespace(options={}))
            with patch('jarvis.knowledge_worker.session',return_value=Client()),patch('jarvis.ollama_models.coding_model'),patch('jarvis.knowledge_worker.local_prompt_format',return_value='qwen_chatml'):
                value=propose(coder,root,'Build independent modules',lambda:False,time.monotonic()+3)
            self.assertEqual(value,proposal());url,request=sent[0];self.assertTrue(url.endswith('/api/generate'))
            self.assertTrue(request['stream']);self.assertTrue(request['json']['raw'])
            self.assertIn('<|im_start|>user',request['json']['prompt'])
            self.assertEqual(request['json']['format']['properties']['interfaces']['type'],'string')
            self.assertNotIn('"pattern":',json.dumps(request['json']['format']))
            self.assertNotIn('messages',request['json']);self.assertEqual(list(root.iterdir()),[])

    def test_single_python_module_planner_keeps_tests_in_same_worker_schema(self):
        self.assertTrue(single_python_source_goal('Modify main.py and test_main.py; preserve add and CLI output.'))
        self.assertTrue(single_python_source_goal('Create main.py. Include actual tests.'))
        self.assertTrue(single_python_source_goal('create a python script for drawing circle on screen in test codes folder'))
        self.assertTrue(single_python_source_goal('Write a script using Python to draw a circle.'))
        self.assertTrue(single_python_source_goal('Fix the existing file main.py and preserve test_main.py.'))
        self.assertTrue(single_python_source_goal('Create a Python script and save it as main.py.'))
        self.assertTrue(single_python_source_goal('Implement a calculator in a single Python file named main.py.'))
        self.assertFalse(single_python_source_goal('Repair this Jarvis-generated Python CLI calculator. Preserve test_calculator.py and test_main.py byte-for-byte. Verify actual main.py subprocess behavior and preserve library interfaces.'))
        self.assertFalse(single_python_source_goal('Repair this application and verify main.py launches with its existing library.'))
        for goal in ('Create alpha.py and beta.py','Build a backend in main.py','Create a package in main.py','Build a website in index.html','Write main.py and app.js','Write two Python scripts','Create a Python script with a website frontend'):
            self.assertFalse(single_python_source_goal(goal))
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);sent=[];value=proposal()
            value['files']=value['files'][:2];value['checks']=value['checks'][:1];value['tasks']=value['tasks'][:1]
            class Response:
                def __enter__(self):return self
                def __exit__(self,*args):return False
                def raise_for_status(self):return None
                def iter_lines(self,**kwargs):yield json.dumps({'done':True,'message':{'content':json.dumps(value)}}).encode()
            class Client:
                def __enter__(self):return self
                def __exit__(self,*args):return False
                def post(self,url,**kwargs):sent.append(kwargs['json']);return Response()
            coder=Coder(SimpleNamespace(report=lambda *row:None),SimpleNamespace(options={}))
            with patch('jarvis.knowledge_worker.session',return_value=Client()),patch('jarvis.ollama_models.coding_model'),patch('jarvis.knowledge_worker.local_prompt_format',return_value='ollama_chat'):
                self.assertEqual(propose(coder,root,'Create alpha.py and its behavioral unittests.',lambda:False,time.monotonic()+3),value)
                self.assertEqual(propose(coder,root,'create a python script for drawing circle on screen in test codes folder',lambda:False,time.monotonic()+3),value)
                # Generation no longer asks the backend regex converter to
                # enforce suffixes. The original local contract must still do so.
                from jarvis.structured_output import ModelOutputError
                value['files'][0]['path']='invalid.txt'
                with self.assertRaisesRegex(ModelOutputError,'required path format'):
                    propose(coder,root,'Create alpha.py and its behavioral unittests.',lambda:False,time.monotonic()+3)
            self.assertEqual(sent[0]['format']['properties']['tasks']['maxItems'],1)
            self.assertEqual(sent[1]['format']['properties']['tasks']['maxItems'],1)
            self.assertEqual(sent[1]['format']['properties']['checks']['items']['properties']['kind']['enum'],['python_tests'])
            self.assertNotIn('pattern',sent[1]['format']['properties']['files']['items']['properties']['path'])
            self.assertIn('not a website',sent[1]['messages'][0]['content'])
            self.assertIn('ONE inseparable',sent[0]['messages'][0]['content'])
            self.assertEqual(planning_schema()['properties']['tasks']['maxItems'],8)
            self.assertEqual(list(root.iterdir()),[])

    def test_website_planner_delivers_separate_feature_briefs_without_whole_task(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            model_plan={'interfaces':'Use shared #count #add #reset and .orb with the declared HTML/CSS/JS links.',
                        'worker_goals':{'markup':'Semantic controls with the heading, #count #add #reset and a real .orb element.',
                                        'styles':'Purple responsive glass cards with a visibly moving luminous .orb.',
                                        'logic':'Actual launch increments count and reset restores zero using shared ids.'},
                        'browser':{'kind':'browser','path':'index.html','steps':[{'action':'text','selector':'#count','value':'0'}],'animation_selectors':['.orb']}}
            class Response:
                def __enter__(self):return self
                def __exit__(self,*args):return False
                def raise_for_status(self):return None
                def iter_lines(self,**kwargs):yield json.dumps({'done':True,'message':{'content':json.dumps(model_plan)}}).encode()
            class Client:
                def __enter__(self):return self
                def __exit__(self,*args):return False
                def post(self,*args,**kwargs):return Response()
            coder=Coder(SimpleNamespace(report=lambda *row:None),SimpleNamespace(options={}))
            goal='Build an animated website. Split all markup, CSS and JS with separate tests and a final browser check.'
            with patch('jarvis.knowledge_worker.session',return_value=Client()),patch('jarvis.ollama_models.coding_model'),patch('jarvis.knowledge_worker.local_prompt_format',return_value='ollama_chat'):
                value=propose(coder,root,goal,lambda:False,time.monotonic()+3)
            for task in value['tasks']:
                self.assertTrue(task['goal'].startswith(model_plan['worker_goals'][task['key']]))
                self.assertNotIn(goal,task['goal'])
                for key,brief in model_plan['worker_goals'].items():
                    if key!=task['key']:self.assertNotIn(brief,task['goal'])
            self.assertEqual(list(root.iterdir()),[])
            model_plan['worker_goals']['markup']=model_plan['worker_goals']['markup'].replace('#count','#counter')
            with patch('jarvis.knowledge_worker.session',return_value=Client()),patch('jarvis.ollama_models.coding_model'),patch('jarvis.knowledge_worker.local_prompt_format',return_value='ollama_chat'):
                propagated=propose(coder,root,goal,lambda:False,time.monotonic()+3)
            from jarvis.codex_workload import worker_request
            markup=propagated['tasks'][0]
            self.assertIn('#count',markup['selector_requirements'])
            self.assertIn('#count',markup['brief_selector_omissions'])
            self.assertIn('Authoritative exact selectors',worker_request(goal,markup,propagated['interfaces']))
            self.assertEqual(markup['resource_paths'],{'markup':'index.html','styles':'styles.css','logic':'app.js'})
            self.assertIn('Authoritative project resource paths',worker_request(goal,markup,propagated['interfaces']))
            self.assertEqual(propagated['checks'][-1],model_plan['browser'])
            self.assertIn('#count',propagated['checks'][0]['required_selectors'])

    def test_html_parser_ignored_tokens_are_valid_while_empty_tests_and_logic_fail(self):
        from jarvis.codex_validation import placeholders
        text='from html.parser import HTMLParser\nclass Tags(HTMLParser):\n    def handle_starttag(self,tag,attrs):\n        self.tag=tag\n    def handle_data(self,data):\n        pass\n    def handle_comment(self,data):\n        pass\n'
        self.assertEqual(placeholders(Path('test_markup.py'),text),[])
        self.assertIn('Empty function: test_controls',placeholders(Path('test_markup.py'),text+'def test_controls():\n    pass\n'))
        self.assertIn('Empty function: handle_data',placeholders(Path('logic.py'),'def handle_data(data):\n    pass\n'))

    def test_explicit_requested_browser_sequence_is_preserved(self):
        goal='Use a browser check: text #count 0, click #add, text #count 1, click #reset, text #count 0. Keep the UI animated.'
        steps=explicit_browser_steps(goal)
        self.assertEqual([s.get('value') for s in steps],['0',None,'1',None,'0'])
        self.assertEqual(explicit_browser_steps('browser check: text #greeting "Hello world". Next sentence')[0]['value'],'Hello world')
        self.assertIsNone(explicit_browser_steps('browser check: click #add'))

    def test_model_markup_property_mismatch_is_rejected_before_save(self):
        from jarvis.codex_files import execute,READS
        import os
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'project';root.mkdir();run=Path(folder)/'run';run.mkdir()
            (run/'request.json').write_text(json.dumps({'project':str(root),'goal':'Implement markup','allowed_paths':['index.html'],'platform_component':True}))
            (run/'validation-contract.json').write_text(json.dumps({'files':[{'path':'index.html','role':'frontend'}],'checks':[{'steps':[{'action':'text','selector':'#count','value':'0'}]}]}))
            READS.clear()
            with patch.dict(os.environ,{'JARVIS_CODEX_PROJECT':str(root),'JARVIS_CODEX_RUN':str(run)}):
                with self.assertRaisesRegex(ValueError,'text-bearing element'):execute('Write',{'file_path':'index.html','content':'<input id="count" value="0">'})
                self.assertFalse((root/'index.html').exists());self.assertFalse((run/'file-events.jsonl').exists())
                (root/'index.html').write_text('<span id="count">0</span>');execute('Read',{'file_path':'index.html'})
                with self.assertRaisesRegex(ValueError,'unchanged'):execute('Edit',{'file_path':'index.html','old_string':'0','new_string':'0'})
                self.assertFalse((run/'file-events.jsonl').exists())
                request=json.loads((run/'request.json').read_text());request['repair_diagnostics']={'error':'Observed browser failure'}
                (run/'request.json').write_text(json.dumps(request))
                with self.assertRaisesRegex(ValueError,'complete corrected file'):execute('Edit',{'file_path':'index.html','old_string':'0','new_string':'1'})
                self.assertEqual((root/'index.html').read_text(),'<span id="count">0</span>');self.assertFalse((run/'file-events.jsonl').exists())

    def test_actual_browser_component_checks_and_final_unsuppressed_assembly(self):
        from jarvis.codex_validation import validate_project
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);project=root/'project';project.mkdir();directory=root/'checks';directory.mkdir()
            (project/'index.html').write_text('<html><head><link rel="stylesheet" href="styles.css"></head><body><h1>Component fixture</h1><span id="count">0</span><button id="add">Add</button><button id="reset">Reset</button><div class="orb"></div><script src="app.js"></script></body></html>')
            (project/'styles.css').write_text('.orb{width:20px;height:20px;background:purple;animation:move 1s infinite alternate}@keyframes move{to{transform:translateX(20px)}}')
            (project/'app.js').write_text('let n=0;const e=document.querySelector("#count");document.querySelector("#add").addEventListener("click",()=>e.textContent=String(++n));document.querySelector("#reset").addEventListener("click",()=>{n=0;e.textContent="0"});')
            selectors=['#count','#add','#reset','.orb']
            steps=[{'action':'text','selector':'#count','value':'0'},{'action':'click','selector':'#add'},
                   {'action':'text','selector':'#count','value':'1'},{'action':'click','selector':'#reset'},{'action':'text','selector':'#count','value':'0'}]
            files=[{'path':n,'role':'frontend','purpose':'Implement real browser component fixture'} for n in ('index.html','styles.css','app.js')]
            checks=[]
            for component,path,suppress in [('markup','index.html',['styles.css','app.js']),('styles','styles.css',['app.js']),('logic','app.js',['styles.css'])]:
                check={'kind':'browser_component','component':component,'path':path,'entry':'index.html','suppress_resources':suppress,
                       'required_selectors':selectors,'steps':steps if component=='logic' else steps[:1]}
                if component=='styles':check['animation_selectors']=['.orb']
                checks.append(check)
            checks.append({'kind':'browser','path':'index.html','steps':steps,'animation_selectors':['.orb']})
            before=fingerprint(project)
            result=validate_project(project,directory,'Verify component fixtures',list(before),{'files':files,'checks':checks},lambda:False,lambda *row:None)
            self.assertTrue(result['passed'],result['errors']);self.assertEqual(len(result['checks']),4)
            for checked in result['checks']:self.assertEqual(json.loads(checked['output'])['tested_widths'],[320,390,768,1280,1920])
            self.assertEqual(fingerprint(project),before)
            (project/'app.js').write_text('document.querySelector("#add").addEventListener("click",()=>{});')
            failed=root/'failed';failed.mkdir()
            result=validate_project(project,failed,'Verify actual click behavior',list(before),{'files':files,'checks':[checks[2]]},lambda:False,lambda *row:None)
            self.assertFalse(result['passed']);self.assertIn('Browser step failed',result['errors'][0]['error'])
            (project/'styles.css').write_text((project/'styles.css').read_text()+'body{min-width:340px}')
            failed=root/'narrow-failed';failed.mkdir()
            result=validate_project(project,failed,'Verify narrow mobile rendering',list(before),{'files':files,'checks':[checks[1]]},lambda:False,lambda *row:None)
            self.assertFalse(result['passed']);self.assertIn('UI overflows the 320px viewport',result['errors'][0]['error'])
            (project/'index.html').write_text((project/'index.html').read_text().replace('<span id="count">0</span>','<input id="count" value="0">'))
            failed=root/'input-failed';failed.mkdir()
            result=validate_project(project,failed,'Verify text assertion contract',list(before),{'files':files,'checks':[checks[0]]},lambda:False,lambda *row:None)
            self.assertFalse(result['passed']);self.assertIn('not a loading/timing failure',result['errors'][0]['error'])
            (project/'index.html').write_text((project/'index.html').read_text().replace('<input id="count" value="0">','<span id="count">0</span><article aria-label="Empty feature"></article>'))
            failed=root/'empty-article-failed';failed.mkdir()
            result=validate_project(project,failed,'Verify visible feature card content',list(before),{'files':files,'checks':[checks[0]]},lambda:False,lambda *row:None)
            self.assertFalse(result['passed']);self.assertIn('unfinished content',result['errors'][0]['error'])

    def test_false_rendered_animation_fails_real_browser_check(self):
        from jarvis.codex_validation import validate_project
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);project=root/'project';project.mkdir();directory=root/'checks';directory.mkdir()
            (project/'index.html').write_text('<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><div class="orb">Static orb</div>')
            plan={'files':[{'path':'index.html','role':'frontend','purpose':'Show the requested orb'}],
                  'checks':[{'kind':'browser','path':'index.html','steps':[{'action':'text','selector':'.orb','value':'Static orb'}],'animation_selectors':['.orb']}]}
            result=validate_project(project,directory,'Create a page',[],plan,lambda:False,lambda *row:None)
            self.assertFalse(result['passed']);self.assertTrue(any('No advancing rendered animation' in e['error'] for e in result['errors']),result)
            (project/'index.html').write_text('<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><style>.orb{animation:still 1s infinite}@keyframes still{from{opacity:1}to{opacity:1}}</style><div class="orb">Static orb</div>')
            result=validate_project(project,directory,'Create a page',[],plan,lambda:False,lambda *row:None)
            self.assertFalse(result['passed']);self.assertTrue(any('without an observed visual style change' in e['error'] for e in result['errors']),result)

    def test_destination_drift_blocks_all_promotion_and_preserves_originals(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);project=root/'project';project.mkdir();integration=root/'integration';integration.mkdir();directory=root/'run';directory.mkdir()
            (project/'alpha.py').write_text('VALUE = 1\n');before=fingerprint(project)
            (integration/'alpha.py').write_text('VALUE = 2\n')
            (project/'alpha.py').write_text('VALUE = 3\n')
            with self.assertRaisesRegex(ValueError,'Destination changed'):
                promote(project,integration,directory,'Update',{},before,['alpha.py'],lambda:False)
            self.assertEqual((project/'alpha.py').read_text(),'VALUE = 3\n')
            before=fingerprint(project)
            promote(project,integration,directory,'Update',{},before,['alpha.py'],lambda:False)
            self.assertEqual((directory/'originals/alpha.py').read_text(),'VALUE = 3\n')
            self.assertEqual([json.loads(s)['stage'] for s in (directory/'promotion.jsonl').read_text().splitlines()],['attempted','applied'])

    def test_real_worktrees_parallel_workers_and_combined_runtime_checks(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);project=root/'project';project.mkdir();events=[];barrier=threading.Barrier(2)
            coder=Coder(SimpleNamespace(base=root,report=lambda *row:events.append(row)),SimpleNamespace(options={'max_coding_seconds':120,'codex_max_workers':2}))
            def worker(child,workspace,goal,cancelled,**kwargs):
                key=Path(workspace).name;barrier.wait(timeout=15)
                (workspace/(key+'.py')).write_text('def value():\n    return '+repr(key)+'\n')
                (workspace/('test_'+key+'.py')).write_text('import unittest\nfrom '+key+' import value\nclass Checks(unittest.TestCase):\n    def test_value(self):\n        self.assertEqual(value(),'+repr(key)+')\n')
                from jarvis.codex_validation import validate_project
                directory=root/('check-'+key);directory.mkdir()
                validation=validate_project(workspace,directory,goal,kwargs['allowed_paths'],kwargs['initial_plan'],cancelled,child.actions.report)
                self.assertTrue(validation['passed'],validation)
                return {'validation':validation,'turns':[str(directory)],'plan':kwargs['initial_plan'],'seconds':0}
            with patch('jarvis.codex_workload.propose',return_value=proposal()),patch('jarvis.codex_code.run',side_effect=worker):
                result=run(coder,project,'Create independent modules')
            self.assertIn('2 Codex workloads',result)
            receipts=list((root/'.jarvis-runtime/codex-workloads').glob('*/receipt.json'))
            receipt=json.loads(receipts[0].read_text());self.assertEqual(receipt['status'],'passed')
            self.assertEqual(len(receipt['validation']['checks']),2)
            self.assertEqual({p.name for p in project.iterdir()},{'alpha.py','beta.py','test_alpha.py','test_beta.py'})
            self.assertTrue(all(w['commit'] for w in receipt['workers']))

    def test_owned_snapshot_preserves_mixed_line_endings_under_windows_git_defaults(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);project=root/'project';project.mkdir()
            frozen={'keep_lf.py':b'# original LF\nVALUE = 1\n',
                    'keep_crlf.py':b'# original CRLF\r\nVALUE = 2\r\n'}
            attributes=root/'global-attributes';attributes.write_bytes(b'*.py text eol=crlf\n')
            for name,data in frozen.items():(project/name).write_bytes(data)
            coder=Coder(SimpleNamespace(base=root,report=lambda *row:None),SimpleNamespace(options={'max_coding_seconds':120}))
            seen=[]
            def worker(child,workspace,goal,cancelled,**kwargs):
                for name,data in frozen.items():self.assertEqual((workspace/name).read_bytes(),data)
                seen.append(Path(workspace).name)
                key=Path(workspace).name
                (workspace/(key+'.py')).write_bytes(('VALUE = '+repr(key)+'\n').encode())
                (workspace/('test_'+key+'.py')).write_bytes(b'import unittest\nclass Check(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n')
                return {'validation':{'passed':True},'turns':[],'plan':kwargs['initial_plan'],'seconds':0}
            with patch.dict(os.environ,{'GIT_CONFIG_COUNT':'2','GIT_CONFIG_KEY_0':'core.autocrlf','GIT_CONFIG_VALUE_0':'true','GIT_CONFIG_KEY_1':'core.attributesFile','GIT_CONFIG_VALUE_1':str(attributes)}),patch('jarvis.codex_workload.propose',return_value=proposal()),patch('jarvis.codex_code.run',side_effect=worker):
                run(coder,project,'Create independent modules')
            self.assertEqual(sorted(seen),['alpha','beta'])
            for name,data in frozen.items():self.assertEqual((project/name).read_bytes(),data)

    def test_dependency_worker_sees_tested_predecessor(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);project=root/'project';project.mkdir();value=proposal();value['tasks'][1]['dependencies']=['alpha'];order=[]
            coder=Coder(SimpleNamespace(base=root,report=lambda *row:None),SimpleNamespace(options={'max_coding_seconds':120}))
            def worker(child,workspace,goal,cancelled,**kwargs):
                key=Path(workspace).name;order.append(key)
                if key=='beta':self.assertTrue((workspace/'alpha.py').exists())
                (workspace/(key+'.py')).write_text('def value():\n    return '+repr(key)+'\n')
                (workspace/('test_'+key+'.py')).write_text('import unittest\nfrom '+key+' import value\nclass Checks(unittest.TestCase):\n    def test_value(self):\n        self.assertEqual(value(),'+repr(key)+')\n')
                return {'validation':{'passed':True},'turns':[],'plan':kwargs['initial_plan'],'seconds':0}
            with patch('jarvis.codex_workload.propose',return_value=value),patch('jarvis.codex_code.run',side_effect=worker):run(coder,project,'Create dependent modules')
            self.assertEqual(order,['alpha','beta'])

    def test_failed_worker_cancels_peers_without_promotion_or_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);project=root/'project';project.mkdir();barrier=threading.Barrier(2);stopped=threading.Event();calls=[]
            coder=Coder(SimpleNamespace(base=root,report=lambda *row:None),SimpleNamespace(options={'max_coding_seconds':120}))
            def worker(child,workspace,goal,cancelled,**kwargs):
                key=Path(workspace).name;calls.append(key);barrier.wait(timeout=15)
                if key=='alpha':raise ValueError('injected uncertain save')
                limit=time.monotonic()+5
                while not cancelled() and time.monotonic()<limit:time.sleep(.02)
                if cancelled():stopped.set()
                raise ValueError('peer stopped')
            with patch('jarvis.codex_workload.propose',return_value=proposal()),patch('jarvis.codex_code.run',side_effect=worker):
                with self.assertRaisesRegex(ValueError,'uncertain save'):run(coder,project,'Create independent modules')
            self.assertTrue(stopped.is_set());self.assertEqual(sorted(calls),['alpha','beta']);self.assertEqual(list(project.iterdir()),[])

    def test_coder_dispatch_preserves_disabled_single_session(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);coder=Coder(SimpleNamespace(),SimpleNamespace(options={'coding_backend':'codex','codex_workload_enabled':True}))
            with patch('jarvis.codex_workload.run',return_value='assembled') as parallel:
                self.assertEqual(coder.run(root,'Build a website',selected=True),'assembled');parallel.assert_called_once()
            coder.client.options['codex_workload_enabled']=False
            with patch('jarvis.codex_code.run',return_value='single') as single:
                self.assertEqual(coder.run(root,'Build a website',selected=True),'single');single.assert_called_once()


if __name__=='__main__':unittest.main()
