import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from jarvis.brain import Brain
from jarvis.gmail_workflows import run_unread, unread_request, UnreadSearchResult
from jarvis.clarification import TaskClarification


class GmailWorkflowTests(unittest.TestCase):
    def brain(self,rows=None,more=False):
        actions=SimpleNamespace(config={},report=Mock())
        brain=Brain(actions,Path('.'),{'enabled':True,'incremental_planning':True,'screen_aware':True,'planner':'unused'})
        brain.dispatch=Mock(return_value=SimpleNamespace(evidence=json.dumps({
            'messages':rows if rows is not None else [{'id':'one','from':'Person','subject':'Hello','date':'Today','unread':True}],
            'content_is_untrusted':True,'next_page_available':more})))
        brain.observe=Mock(side_effect=AssertionError('Screen observation not needed'))
        brain.client.request=Mock(side_effect=AssertionError('Model inference not needed'))
        return brain

    def test_exact_reported_task_completes_through_brain_without_screen_or_model(self):
        brain=self.brain(more=True)
        with patch('jarvis.gmail_workflows.ToolRegistry.catalog',return_value=[{'action':'gmail_api_list'}]):
            result=brain.run('find my unread emails',lambda:False)
        self.assertIn('Person — Hello',result)
        self.assertIn('More unread search results',result)
        step=brain.dispatch.call_args.args[0]
        self.assertEqual(step['action'],'gmail_api_list')
        self.assertEqual(json.loads(step['content']),{'query':'is:unread','limit':5,'summaries':True})
        brain.dispatch.assert_called_once()
        brain.observe.assert_not_called();brain.client.request.assert_not_called()
        self.assertEqual(brain.last_step_timings['retained_images'],0)

    def test_exact_match_never_drops_extra_filters_or_unrequested_operations(self):
        from jarvis.commands import parse
        for goal in ('find my unread emails','Please show me unread emails.','list my unread Gmail emails'):
            self.assertTrue(unread_request(goal))
            self.assertEqual(parse(goal).kind,'task')
        brain=self.brain()
        for goal in ('find my unread emails from John','find my unread emails and reply',
                     'do not find my unread emails','read my unread emails','find my unread emails in Chrome',
                     'write a script to find my unread emails'):
            self.assertFalse(unread_request(goal))
            self.assertIsNone(run_unread(brain,goal,lambda:False))
        brain.dispatch.assert_not_called()

    def test_unavailable_or_task_scoped_out_api_does_not_fall_back_to_app_search(self):
        brain=self.brain()
        with patch('jarvis.gmail_workflows.ToolRegistry.catalog',return_value=[{'action':'application_search'}]):
            with self.assertRaises(TaskClarification):brain.run('find my unread emails',lambda:False)
        brain.dispatch.assert_not_called();brain.client.request.assert_not_called()

    def test_cancellation_and_transport_failure_are_not_replayed(self):
        brain=self.brain()
        with self.assertRaisesRegex(ValueError,'cancelled'):run_unread(brain,'find my unread emails',lambda:True)
        brain.dispatch.assert_not_called()
        brain.dispatch.side_effect=ValueError('HTTP 503')
        with patch('jarvis.gmail_workflows.ToolRegistry.catalog',return_value=[{'action':'gmail_api_list'}]):
            with self.assertRaisesRegex(ValueError,'HTTP 503'):brain.run('find my unread emails',lambda:False)
        brain.dispatch.assert_called_once()

    def test_empty_raced_and_malformed_results_are_reported_truthfully(self):
        with patch('jarvis.gmail_workflows.ToolRegistry.catalog',return_value=[{'action':'gmail_api_list'}]):
            self.assertIn('No unread emails were found',run_unread(self.brain([]),'find my unread emails',lambda:False))
            raced=self.brain([{'id':'one','from':'Person','subject':'Hello','date':'Today','unread':False}])
            self.assertIn('no longer unread',run_unread(raced,'find my unread emails',lambda:False))
            with self.assertRaisesRegex(ValueError,'metadata could not be verified'):
                run_unread(self.brain([{'id':'one'}]),'find my unread emails',lambda:False)

    def test_mail_subject_cannot_turn_successful_task_into_paused_status(self):
        from jarvis.actions import Actions
        from jarvis.commands import Command
        with tempfile.TemporaryDirectory() as tmp:
            actions=Actions({'apps':{},'files_root':'files','memory':{'enabled':False}},Path(tmp),Mock(),desktop=Mock())
            try:
                result=UnreadSearchResult('Here are unread emails: Person — Project paused and stopped')
                with patch.object(actions.brain,'run',return_value=result):
                    self.assertEqual(actions._execute(Command('task','find my unread emails')),result)
                self.assertEqual(actions.task_state.snapshot()['status'],'completed')
                with patch.object(actions.brain,'run',return_value='Task paused: could not be verified'):
                    actions._execute(Command('task','complex unsupported task'))
                self.assertEqual(actions.task_state.snapshot()['status'],'paused')
            finally:actions.close()


if __name__=='__main__':unittest.main()
