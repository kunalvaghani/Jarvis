import copy
import json
import unittest
from unittest.mock import Mock
from jarvis.live_app_context import LiveAppContext
from jarvis.brain import BrainClient
from jarvis.knowledge_worker import answer


class LiveAppTests(unittest.TestCase):
    def setUp(self):
        self.rows={1:{'handle':1,'pid':100,'process_started':'one','window_class':'app',
                      'title':'Calculator fixture','visible':True},
                   2:{'handle':2,'pid':200,'process_started':'two','window_class':'app',
                      'title':'Game fixture','visible':True}}
        self.focus=1
        self.clock=10
        self.context=LiveAppContext(lambda h:copy.deepcopy(self.rows.get(h)),lambda:self.clock,lambda:self.focus)
        self.controls={'title':'Calculator fixture','controls':[{'name':'Apply','role':'Button','id':[100],
            'rect':[0,0,20,20]},{'name':'Password','role':'Edit','password':True,'value':'secret'}]}

    def test_open_status_and_controls_do_not_retain_action_ids_or_passwords(self):
        self.context.record_controls(1,self.controls)
        current=self.context.snapshot()['current']
        self.assertEqual(current['status'],'open')
        self.assertEqual(current['controls'],[{'name':'Apply','role':'Button'}])
        self.assertEqual(current['controls_age_seconds'],0)
        self.assertNotIn('secret',json.dumps(current))

    def test_closed_window_cannot_offer_old_controls(self):
        self.context.record_controls(1,self.controls)
        self.rows.pop(1)
        current=self.context.snapshot()['current']
        self.assertEqual(current['status'],'closed')
        self.assertEqual(current['controls'],[])

    def test_reused_handle_or_process_identity_invalidates_controls(self):
        self.context.record_controls(1,self.controls)
        self.focus=0
        self.rows[1]['process_started']='replacement'
        current=self.context.snapshot()['current']
        self.assertEqual(current['status'],'replaced')
        self.assertEqual(current['controls'],[])

    def test_switch_keeps_previous_window_status_and_current_window(self):
        self.context.record_controls(1,self.controls)
        self.focus=2
        result=self.context.snapshot()
        self.assertEqual(result['current']['title'],'Game fixture')
        self.rows.pop(1)
        result=self.context.snapshot()
        self.assertEqual(result['recent_windows'][0]['status'],'closed')
        self.assertEqual(result['current']['status'],'open')

    def test_changed_title_or_hidden_window_clears_controls(self):
        self.context.record_controls(1,self.controls)
        self.rows[1]['title']='New document'
        self.assertEqual(self.context.snapshot()['current']['controls'],[])
        self.rows[1]['visible']=False
        self.assertEqual(self.context.snapshot()['current']['status'],'open')

    def test_failed_or_cancelled_refresh_cannot_reuse_old_controls(self):
        self.context.record_controls(1,self.controls)
        ui=Mock()
        ui._handle.return_value=1
        ui.runner.side_effect=RuntimeError('UIA timeout')
        self.assertEqual(self.context.refresh(ui)['current']['controls'],[])
        ui.reset_mock()
        self.context.refresh(ui,lambda:True)
        ui.runner.assert_not_called()

    def test_successful_refresh_updates_changed_control_list(self):
        ui=Mock()
        ui._handle.return_value=1
        ui.runner.return_value=self.controls
        self.assertEqual(self.context.refresh(ui)['current']['controls'][0]['name'],'Apply')
        self.controls['controls'][0]['name']='Applied 1'
        self.assertEqual(self.context.refresh(ui)['current']['controls'][0]['name'],'Applied 1')

    def test_each_planner_operation_receives_live_status(self):
        client=BrainClient.__new__(BrainClient)
        client.options={}; client.worker_module='jarvis.brain_worker'
        client.app_context_provider=self.context.snapshot
        client._request_once=Mock(return_value={})
        for operation in ('plan','replan','next_step','code_plan','code_edit'):
            client.request(operation,lambda:False,goal='Use that app')
            self.assertEqual(client._request_once.call_args.kwargs['live_app_context']['current']['status'],'open')
        self.rows.pop(1)
        client.request('next_step',lambda:False,goal='Use that app')
        self.assertEqual(client._request_once.call_args.kwargs['live_app_context']['current']['status'],'closed')

    def test_local_app_answer_contains_status_and_controls(self):
        self.context.record_controls(1,self.controls)
        chat=Mock(return_value='{"answer":"Apply","needs_web":true}')
        search=Mock()
        answer({'question':'Which buttons does that app have?', 'live_app_context':self.context.snapshot()},chat_fn=chat,search_fn=search)
        search.assert_not_called()
        content=json.dumps(chat.call_args.args[2])
        self.assertIn('Apply',content)
        self.assertIn('Current app context',content)


if __name__=='__main__':unittest.main()
