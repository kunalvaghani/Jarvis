import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from jarvis.coder import Coder
from jarvis.task_state import TaskState

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.project=self.root/'project'
        self.project.mkdir()
        self.actions=Mock(base=self.root)
        self.actions.task_state=TaskState(self.root)
        self.actions.task_state.start('Build React dashboard','code_task',self.project)
        self.client=Mock()
        self.coder=Coder(self.actions,self.client)

    def answer(self,operation,*args,**kwargs):
        if operation=='code_plan':
            self.assertTrue(kwargs['design_spec'])
            return {'directories':[], 'files':[{'path':f'src/Card{i}.tsx','reason':'Component'} for i in range(5)]}
        if operation=='code_edit': return {'content':'export default function Card() { return <button>Open</button>; }\n'}
        return {'text':json.dumps([{'name':f'Outcome {j}','steps':[{'action':'click','name':'Open'},{'action':'assert_text','value':str(j)}]} for j in range(3)])}

    def test_multiple_batches_and_no_early_goal_success(self):
        self.client.request.side_effect=self.answer
        seen=[]
        def verify(*a,**kw):
            stages=[c['stage'] for c in self.actions.task_state.snapshot()['checkpoints']]
            self.assertNotIn('goal_verified',stages)
            self.assertEqual(len(list((self.project/'src').glob('Card*.tsx'))),5)
            seen.extend(stages)
            return {'goal_verified':True,'preview_url':'http://127.0.0.1:1','evidence_file':'fixture.json'}
        with patch('jarvis.development.verify',side_effect=verify):
            result=self.coder.run(self.project,'Build React dashboard',selected=True)
        self.assertIn('2 implementation batches',result)
        self.assertEqual(sum(c.args[0]=='code_plan' for c in self.client.request.call_args_list),1)
        self.assertTrue(list((self.project/'.jarvis/development').glob('design-*.json')))
        self.assertIn('development_batch_saved',seen)
        self.assertEqual(self.actions.task_state.snapshot()['stage'],'goal_verified')

    def test_invalid_full_plan_stops_before_generated_writes(self):
        self.client.request.return_value={'directories':[], 'files':[{'path':'../escape.ts','reason':'unsafe'}]}
        with self.assertRaises(ValueError): self.coder.run(self.project,'Build React dashboard',selected=True)
        self.assertFalse((self.root/'escape.ts').exists())
        self.assertEqual(self.client.request.call_count,1)

    def test_rejected_verification_is_not_completed(self):
        self.client.request.side_effect=self.answer
        with patch('jarvis.development.verify',side_effect=ValueError('Approval denied')):
            with self.assertRaisesRegex(ValueError,'Approval denied'):
                self.coder.run(self.project,'Build React dashboard',selected=True)
        self.assertNotEqual(self.actions.task_state.snapshot()['stage'],'goal_verified')

    def test_explicit_single_file_scope_rejects_extra_plan_files(self):
        self.client.request.return_value={'directories':[],'files':[{'path':'src/Probe.tsx','reason':'requested'}, {'path':'src/App.tsx','reason':'unrequested mount'}]}
        with self.assertRaisesRegex(ValueError,'single-file scope'):
            self.coder.run(self.project,'Create React component src/Probe.tsx. Only create this file.',selected=True)
        self.assertFalse((self.project/'src/Probe.tsx').exists())
        self.assertEqual(self.client.request.call_count,1)

    def test_correction_with_no_new_changes_does_not_replay_commands(self):
        def infer(operation,*args,**kwargs):
            if operation=='code_plan':return {'directories':[],'files':[{'path':'src/Card.tsx','reason':'component'}]}
            if operation=='code_edit':return {'content':'export default function Card() { return <button>Open</button>; }\n'}
            return {'text':json.dumps([{'name':f'Outcome {j}','steps':[{'action':'click','name':'Open'},{'action':'assert_text','value':str(j)}]} for j in range(3)])}
        self.client.request.side_effect=infer
        with patch('jarvis.development.verify',return_value={'goal_verified':False,'evidence_file':'fixture.json','project':str(self.project),'stack':'vite'}) as verify:
            with self.assertRaisesRegex(ValueError,'no new source changes'):
                self.coder.run(self.project,'Build React dashboard',selected=True)
            self.assertEqual(verify.call_count,1)
        self.assertFalse(any(c['stage']=='goal_verified' for c in self.actions.task_state.snapshot()['checkpoints']))

    def test_test_writer_replans_invalid_inference_before_actions(self):
        from jarvis.development import functional_tests
        valid=[{'name':f'Outcome {i}','steps':[{'action':'click','name':'Open'},{'action':'assert_text','value':'Saved'}]} for i in range(3)]
        self.client.request.side_effect=[{'text':json.dumps([{'name':'invalid','steps':[{'action':'click','role':'generic','name':'Open'}]}]*3)}, {'text':json.dumps(valid)}]
        self.assertEqual(functional_tests(self.client,self.project,'Check save outcomes',lambda:False),valid)
        self.assertEqual(self.client.request.call_count,2)
        call=self.client.request.call_args
        self.assertIn('Unsupported semantic role',call.kwargs['context']['validation_error'])
        self.assertTrue(call.kwargs['development'])
        self.assertFalse(self.actions._approve.called)

    def test_test_writer_stops_after_two_invalid_proposals(self):
        from jarvis.development import functional_tests
        self.client.request.return_value={'text':'not JSON'}
        with self.assertRaisesRegex(ValueError,'bounded inference correction'):
            functional_tests(self.client,self.project,'Check save outcomes',lambda:False)
        self.assertEqual(self.client.request.call_count,2)
        self.assertFalse(self.actions._approve.called)

    def test_test_writer_uses_constrained_structured_worker_response(self):
        from jarvis.development import functional_tests
        from jarvis.brain_worker import Models
        valid=[{'name':f'Outcome {i}','steps':[{'action':'click','name':'Open'},{'action':'assert_text','value':'Saved'}]} for i in range(3)]
        models=Models.__new__(Models);models.client=Mock()
        with patch('jarvis.brain_worker.chat',return_value=json.dumps({'tests':valid})) as chat:
            self.client.request.return_value=models.generate('qwen3.5:4b','Plan tests',{'development':True,'browser_test_plan':True},'tool_text')
            self.assertEqual(functional_tests(self.client,self.project,'Check save outcomes',lambda:False),valid)
            settings=chat.call_args.args[1]
            self.assertTrue(settings['stream'])
            variants=settings['format_schema']['properties']['tests']['items']['properties']['steps']['items']['oneOf']
            press=next(v for v in variants if v['properties']['action']['enum']==['press'])
            self.assertNotIn('Control+O',press['properties']['value']['enum'])
            self.assertIn('Escape',press['properties']['value']['enum'])

    def test_runtime_builds_and_observes_before_model_test_planning(self):
        from jarvis.development import verify
        events=[]
        tools=Mock()
        tools.build.side_effect=lambda *a:events.append('build') or [{'exit_code':0},{'exit_code':0}]
        tools.start_preview.return_value='http://127.0.0.1:1'
        observed={'views':[{'name':'desktop','observation':'- textbox "Search projects"'}]}
        def inspect(*args):
            events.append('observe' if args[2]==[] else 'check')
            return observed if args[2]==[] else {'goal_verified':True}
        tools.inspect.side_effect=inspect
        planned=[{'name':'Search','steps':[{'action':'fill','role':'textbox','name':'Search projects','value':'missing'}]}]
        def plan(*args,**kwargs):
            events.append('plan')
            self.assertIn('Search projects',kwargs['observations'][0]['snapshot'])
            return planned
        with patch('jarvis.development.tools_for',return_value=tools),patch('jarvis.development.functional_tests',side_effect=plan):
            result=verify(self.actions,self.project,'vite',None,lambda:False,install=False,test_client=self.client,goal='Check search')
        self.assertEqual(events,['build','observe','plan','check'])
        self.assertTrue(result['goal_verified'])
        self.assertEqual(result['tests'],planned)
