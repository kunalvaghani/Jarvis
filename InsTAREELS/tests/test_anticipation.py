import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from jarvis.anticipation import Anticipation, request_signal, settings, window_signal
from jarvis.anticipation_worker import prepare, public_url
from jarvis.commands import Command, parse


class Clock:
    def __init__(self): self.now = 10000.
    def __call__(self): return self.now
    def advance(self, seconds): self.now += seconds


class AnticipationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.clock = Clock()
        self.report = Mock()
        self.busy = False
        self.runner = Mock(return_value=dict(content='# Research outline\nEvidence, sources and questions.', scope='fixture'))
        self.service = Anticipation(self.temp.name,
            dict(idle_seconds=5,dwell_seconds=5,cooldown_seconds=30,expiry_seconds=60),
            self.report, busy=lambda:self.busy, clock=self.clock, wall=self.clock, runner=self.runner)
        self.addCleanup(self.service.close)

    def request(self, topic='Python asyncio'):
        self.service.observe_request('task','research '+topic)
        self.clock.advance(6)

    def suggestion(self, topic='Python asyncio'):
        self.service.observe_window(topic+' - Google Search - Google Chrome', 123)
        self.clock.advance(6)
        self.service.tick()
        return self.service.snapshot()['preparations'][-1]

    def test_commands_route_without_model_or_desktop(self):
        for phrase, action in [('what have you prepared','show'),('pause anticipation','pause'),
                ('resume anticipation','resume'),('accept preparation','accept'),
                ('dismiss preparation','dismiss'),('always prepare public research','authorize'),
                ('stop automatic public research','revoke')]:
            self.assertEqual(parse(phrase),Command('anticipation',action))
        self.assertEqual(parse('please pause anticipation'),Command('anticipation','pause'))

    def test_spoken_authorization_waits_for_final_transcript(self):
        from jarvis.engine import Engine
        submit=Mock()
        engine=Engine(submit,Mock()); engine.activate()
        engine.feed('always prepare public research.',final=False)
        submit.assert_not_called()
        engine.feed('always prepare public research.',final=True)
        submit.assert_called_once_with(Command('anticipation','authorize'))

    def test_settings_reject_unbounded_or_wrong_types(self):
        for options in [dict(enabled='yes'),dict(idle_seconds=True),dict(max_seconds_per_job=9999),
                        dict(model_tokens=-1),dict(expiry_seconds=float('nan')),[]]:
            with self.assertRaises(ValueError): settings(options)

    def test_topics_require_research_evidence(self):
        self.assertIsNone(request_signal('ask','what is 2 plus 2'))
        self.assertIsNone(window_signal('Welcome - Google Chrome'))
        self.assertEqual(window_signal('asyncio.py - Demo - Visual Studio Code')['kind'],'code_review')
        self.assertEqual(request_signal('browser_search','Python asyncio')['origin'],'request')

    def test_sensitive_topics_are_excluded(self):
        for topic in ['password manager','api_key abc','Alice@example.com','https://private.example',
                      'bank account','D:/private/project','inbox','incognito tutorial']:
            self.assertIsNone(request_signal('task','research '+topic))
            self.assertIsNone(window_signal(topic+' - Google Search - Google Chrome'))
        self.assertIsNone(request_signal('task','research asyncio and then email results'))

    def test_no_preparation_before_idle_or_during_busy_work(self):
        self.service.observe_request('task','research Python')
        self.service.tick(); self.runner.assert_not_called()
        self.clock.advance(6); self.busy=True
        self.service.tick(); self.runner.assert_not_called()
        self.busy=False; self.service.tick(); self.runner.assert_called_once()

    def test_request_prepares_silently_with_disk_readback(self):
        self.request(); self.service.tick()
        row = self.service.snapshot()['preparations'][0]
        self.assertEqual(row['mode'],'prepare')
        self.assertEqual(row['status'],'prepared')
        self.assertEqual((self.service.directory/row['artifact']).read_text(encoding='utf-8'),row['content'])
        self.assertFalse(any(c.args[0] in {'answer','spoken_reply','island_navigation'} for c in self.report.call_args_list))

    def test_inferred_topic_only_suggests_until_accepted(self):
        row = self.suggestion()
        self.assertEqual(row['mode'],'suggest'); self.runner.assert_not_called()
        self.service.handle('accept',row['id'])
        self.clock.advance(31); self.service.tick()
        self.assertEqual(self.service.snapshot()['preparations'][0]['mode'],'perform_authorized')
        self.runner.assert_called_once()

    def test_standing_authorization_is_scoped_and_revocable(self):
        self.service.handle('authorize')
        row = self.suggestion()
        self.assertEqual(row['status'],'prepared')
        self.service.handle('revoke')
        self.clock.advance(31)
        row = self.suggestion('JavaScript promises')
        self.assertEqual(row['status'],'suggested')
        self.assertEqual(self.runner.call_count,1)

    def test_editor_authorization_does_not_grant_code_edits(self):
        self.service.handle('authorize')
        self.service.observe_window('main.py - Demo - Visual Studio Code',123)
        self.clock.advance(6); self.service.tick()
        row = self.service.snapshot()['preparations'][0]
        self.assertEqual(row['kind'],'code_review')
        self.assertEqual(row['status'],'suggested')
        self.runner.assert_not_called()

    def test_new_request_preempts_preparation_without_publishing(self):
        def interrupted(request,cancelled,budget):
            self.service.observe_request('open','notepad')
            self.assertTrue(cancelled())
            return dict(content='Stale result')
        self.service.runner=interrupted
        self.request(); self.service.tick()
        self.assertEqual(self.service.snapshot()['preparations'],[])
        self.assertFalse(list(self.service.directory.glob('draft-*.md')))
        self.assertFalse(self.service.storage_failed)

    def test_busy_transition_discards_result(self):
        def interrupted(request,cancelled,budget):
            self.busy=True
            return dict(content='Late result')
        self.service.runner=interrupted
        self.request(); self.service.tick()
        self.assertEqual(self.service.rows[0]['status'],'cancelled')

    def test_topic_change_invalidates_artifact_and_card_token(self):
        self.request(); self.service.tick()
        token=self.service.rows[0]['id']
        self.service.observe_window('JavaScript tutorial - Google Chrome',124)
        self.assertIn('expired',self.service.handle('accept',token))
        self.assertEqual(self.service.rows[0]['status'],'stale')

    def test_expiry_counts_ignored_suggestions_only_once(self):
        row=self.suggestion()
        self.clock.advance(61); self.service.tick(); self.service.tick()
        self.assertEqual(self.service.feedback['research:window']['ignored'],1)
        self.assertIn('expired',self.service.handle('accept',row['id']))

    def test_expired_silent_preparation_is_not_user_rejection(self):
        self.request(); self.service.tick(); self.clock.advance(61)
        self.service.tick()
        self.assertNotIn('research:request',self.service.feedback)

    def test_repeated_dismissals_suppress_similar_predictions(self):
        for topic in ['Python','JavaScript']:
            row=self.suggestion(topic)
            self.service.handle('dismiss',row['id']); self.clock.advance(31)
        self.service.observe_window('SQLite - Google Search - Google Chrome',123)
        self.clock.advance(6); self.service.tick()
        self.assertEqual(self.service.snapshot()['preparations'],[])
        self.runner.assert_not_called()

    def test_feedback_and_grants_survive_but_jobs_never_resume_on_restart(self):
        row=self.suggestion(); self.service.handle('dismiss',row['id'])
        self.service.handle('authorize')
        other=Anticipation(self.temp.name,{},self.report)
        self.addCleanup(other.close)
        self.assertEqual(other.feedback['research:window']['dismissed'],1)
        self.assertEqual(other.grants,['public_research'])
        self.assertEqual(other.rows,[]); self.assertIsNone(other.signal)

    def test_deliberate_pause_survives_restart(self):
        self.service.handle('pause')
        other=Anticipation(self.temp.name,{},self.report)
        self.addCleanup(other.close)
        self.assertTrue(other.paused)

    def test_accepting_ready_output_does_not_double_count_proposal_feedback(self):
        row=self.suggestion()
        self.service.handle('accept',row['id']); self.clock.advance(31); self.service.tick()
        self.service.handle('accept',row['id'])
        self.assertEqual(self.service.feedback['research:window']['accepted'],1)

    def test_corrupt_state_is_preserved_and_not_overwritten(self):
        self.service.directory.mkdir(parents=True)
        path=self.service.directory/'state.json'; path.write_text('{bad',encoding='utf-8')
        other=Anticipation(self.temp.name,{},self.report)
        self.addCleanup(other.close)
        other.handle('authorize'); other.start()
        self.assertTrue(other.storage_failed); self.assertIsNone(other.thread)
        self.assertEqual(path.read_text(encoding='utf-8'),'{bad')
        self.assertEqual(other.grants,[])

    def test_changed_disk_artifact_cannot_be_accepted(self):
        self.request(); self.service.tick(); row=self.service.rows[0]
        (self.service.directory/row['artifact']).write_text('tampered',encoding='utf-8')
        self.assertIn('changed',self.service.handle('accept',row['id']))
        self.assertEqual(row['status'],'stale')

    def test_pause_and_microphone_stop_are_not_undone_by_repair(self):
        self.request(); self.service.cancel(microphone=True)
        self.clock.advance(6); self.service.tick(); self.runner.assert_not_called()
        self.service.repair(); self.assertTrue(self.service.microphone_stopped)
        self.service.microphone_started(); self.service.handle('pause')
        self.clock.advance(6); self.service.tick(); self.runner.assert_not_called()
        self.service.handle('resume'); self.clock.advance(6); self.service.tick()
        self.runner.assert_called_once()

    def test_shutdown_is_final_and_repair_cannot_restart(self):
        self.service.start(); self.service.close()
        self.assertFalse(self.service.thread.is_alive())
        self.assertFalse(self.service.repair())

    def test_hourly_job_budget_and_cooldown(self):
        self.service.options['max_jobs_per_hour']=1
        self.request(); self.service.tick()
        self.request('JavaScript'); self.clock.advance(31); self.service.tick()
        self.assertEqual(self.runner.call_count,1)
        self.clock.advance(3601); self.request('SQLite'); self.service.tick()
        self.assertEqual(self.runner.call_count,2)

    def test_hourly_time_reservation_limits_next_worker(self):
        self.service.options['max_seconds_per_hour']=5
        def slow(request,cancelled,budget):
            self.assertEqual(budget,5)
            self.clock.advance(5)
            return dict(content='Budgeted outline')
        self.service.runner=Mock(side_effect=slow)
        self.request(); self.service.tick()
        self.request('JavaScript'); self.clock.advance(31); self.service.tick()
        self.assertEqual(self.service.runner.call_count,1)

    def test_read_failure_backs_off_without_storage_halt(self):
        self.service.runner=Mock(side_effect=OSError('worker missing'))
        self.request(); self.service.tick()
        self.assertFalse(self.service.storage_failed)
        self.assertGreater(self.service.next_retry,self.clock())
        self.service.tick(); self.assertEqual(self.service.runner.call_count,1)

    def test_disk_failure_stops_writes_without_claiming_prepared(self):
        self.request()
        with patch.object(self.service,'_path',side_effect=OSError('disk unavailable')):
            self.service.tick()
        self.assertTrue(self.service.storage_failed)
        self.assertEqual(self.service.rows[0]['status'],'failed')
        self.service.tick(); self.runner.assert_called_once()

    def test_owned_subprocess_cancelled_and_no_shared_process_killed(self):
        real_popen=subprocess.Popen
        children=[]
        def create(*args,**kwargs):
            child=real_popen([sys.executable,'-c','import time; time.sleep(10)'],**kwargs)
            children.append(child); return child
        cancelled=threading.Event()
        timer=threading.Timer(.2,cancelled.set); timer.start(); self.addCleanup(timer.cancel)
        with patch('jarvis.anticipation.subprocess.Popen',side_effect=create):
            with self.assertRaises(InterruptedError):
                self.service._worker({},cancelled.is_set,5)
        self.assertIsNotNone(children[0].poll()); self.assertIsNone(self.service.process)

    def test_owned_subprocess_deadline_is_enforced(self):
        real_popen=subprocess.Popen
        def create(*args,**kwargs):
            return real_popen([sys.executable,'-c','import time; time.sleep(10)'],**kwargs)
        # Use the real monotonic clock for this subprocess-only injected stall.
        self.service.clock=time.monotonic
        with patch('jarvis.anticipation.subprocess.Popen',side_effect=create):
            with self.assertRaises(TimeoutError): self.service._worker({},lambda:False,.2)
        self.assertIsNone(self.service.process)

    def test_worker_protocol_handles_unicode_under_windows_locale(self):
        real_popen=subprocess.Popen
        def create(*args,**kwargs):
            return real_popen([sys.executable,'-c',
                'import json; print(json.dumps({"content":chr(8212)+chr(233)},ensure_ascii=False))'],**kwargs)
        self.service.clock=time.monotonic
        with patch('jarvis.anticipation.subprocess.Popen',side_effect=create):
            result=self.service._worker({},lambda:False,5)
        self.assertEqual(result['content'],'—é')

    def test_actions_control_preserves_current_task_generation(self):
        from jarvis.actions import Actions
        actions=Actions.__new__(Actions)
        actions.anticipation=self.service; actions.generation=19; actions.task_active=True; actions.report=Mock()
        Actions.submit(actions,Command('anticipation','status'))
        self.assertEqual(actions.generation,19); self.assertTrue(actions.task_active)

    def test_ask_and_do_task_buttons_route_control_without_invalidating_artifact(self):
        from jarvis.actions import Actions
        self.request(); self.service.tick(); row=self.service.rows[0]
        actions=Actions.__new__(Actions)
        actions.anticipation=self.service; actions.generation=19; actions.task_active=True; actions.report=Mock()
        for kind in ('ask','task'):
            Actions.submit(actions,Command(kind,'what have you prepared'))
            self.assertEqual(row['status'],'prepared')
            self.assertEqual(actions.generation,19)


class PreparationWorkerTests(unittest.TestCase):
    def request(self,**kwargs):
        return dict(topic='Python asyncio',kind='research',authorized=True,
                    evidence='Explicit research request',options=kwargs)

    def test_public_snippets_have_attribution_and_unverified_scope(self):
        result=prepare(self.request(),search_fn=lambda _: [dict(title='Python docs',
            href='https://docs.python.org/3/library/asyncio.html',body='Asyncio documentation')])
        self.assertEqual(result['source_count'],1)
        self.assertIn('https://docs.python.org',result['content'])
        self.assertIn('full pages have not been read',result['content'])
        self.assertIn('Unanswered questions',result['content'])

    def test_no_authorization_cannot_use_network_or_model(self):
        request=self.request(); request['authorized']=False
        with self.assertRaises(ValueError): prepare(request,search_fn=Mock(),model_fn=Mock())

    def test_private_and_invalid_urls_excluded(self):
        for url in ['http://example.com','https://localhost/test','https://10.0.0.1',
                    'file:///private','https://user:pass@example.com','https://server.internal']:
            self.assertEqual(public_url(url),'')
        self.assertEqual(public_url('https://docs.python.org/test'),'https://docs.python.org/test')

    def test_search_failure_returns_incomplete_outline(self):
        result=prepare(self.request(),search_fn=Mock(side_effect=TimeoutError()))
        self.assertEqual(result['source_count'],0)
        self.assertIn('incomplete outline',result['content'])
        self.assertIn('unavailable',result['content'])

    def test_network_and_model_can_be_disabled(self):
        search,model=Mock(),Mock()
        result=prepare(self.request(public_search=False),search_fn=search,model_fn=model)
        search.assert_not_called(); model.assert_not_called()
        self.assertIn('disabled',result['content'])

    def test_optional_model_uses_only_sources_and_labels_draft(self):
        model=Mock(return_value='Source 1 explains event loops; cancellation needs investigation.')
        result=prepare(self.request(local_model=True),search_fn=lambda _: [dict(title='Docs',
            href='https://docs.python.org',body='Snippet')],model_fn=model)
        model.assert_called_once()
        self.assertIn('unverified',result['content'])
        self.assertEqual(model.call_args.args[2]['model_tokens'],256)

    def test_editor_checklist_reads_no_source_or_network(self):
        request=self.request(); request.update(kind='code_review',topic='main.py')
        search=Mock(side_effect=AssertionError('Unexpected network'))
        result=prepare(request,search_fn=search)
        search.assert_not_called()
        self.assertIn('No source was read or edited',result['content'])


if __name__=='__main__': unittest.main()
