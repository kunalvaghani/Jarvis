from concurrent.futures import Future
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from jarvis.commands import Command
from jarvis.conversation_memory import ConversationMemory, current_context, messages
from jarvis.context_selector import ContextSelector, select
from jarvis.knowledge import Knowledge
from jarvis.knowledge_worker import answer
from jarvis.actions import Actions
from jarvis.island_choices import snapshot


def wait_until(test, condition):
    deadline=time.monotonic()+3
    while not condition() and time.monotonic()<deadline:
        time.sleep(.01)
    test.assertTrue(condition())


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'conversations.sqlite3'
        self.store=ConversationMemory(self.path)

    def pair(self, session, question, reply):
        turn=self.store.begin(session,question)
        self.store.finish(turn,reply)
        return turn

    def test_all_full_pairs_survive_restart_and_search_excludes_current(self):
        session=self.store.start_session()
        long='Full code\n'*9000
        for i in range(10):
            self.pair(session,'Snake game '+str(i),long+str(i))
        restarted=ConversationMemory(self.path)
        self.assertEqual(len(restarted.turns(session)),10)
        self.assertEqual(restarted.turns(session)[-1]['answer'],long+'9')
        self.assertEqual(restarted.matches('snake game',session),[])
        self.assertEqual(len(restarted.matches('snake game',restarted.start_session())),1)

    def test_failed_cancelled_and_pending_are_not_answer_memories(self):
        session=self.store.start_session()
        for status in ('cancelled','failed','expired','pending'):
            turn=self.store.begin(session,'snake game')
            self.store.finish(turn,'partial code',status)
        self.assertEqual(self.store.matches('snake','new'),[])

    def test_multiple_sessions_remain_separate_with_matching_keywords(self):
        for language in ('python','cpp'):
            self.pair(self.store.start_session(),language+' snake game','dice board '+language)
        rows=self.store.matches('snake dice','new')
        self.assertEqual(len(rows),2)
        self.assertTrue(all(row['keywords']==['dice','snake'] for row in rows))

    def test_sensitive_text_is_redacted_on_disk(self):
        session=self.store.start_session()
        self.pair(session,'my password is example','api_key = example')
        row=self.store.turns(session)[0]
        self.assertEqual(row['question'],'[redacted sensitive text]')
        self.assertEqual(row['answer'],'[redacted sensitive text]')

    def test_context_keeps_old_match_beyond_previous_three_pairs(self):
        history=[]
        for i in range(12):
            history += [{'role':'user','content':'gravity' if i==0 else 'music '+str(i)},
                        {'role':'assistant','content':'force' if i==0 else 'song '*1000}]
        context,found=current_context(history,'explain gravity again',24000)
        self.assertTrue(found)
        self.assertIn('gravity',[row['content'] for row in context])
        self.assertLessEqual(sum(len(row['content']) for row in context),24000)

    def test_follow_up_uses_recent_current_context_unrelated_query_does_not(self):
        history=[{'role':'user','content':'explain gravity'},{'role':'assistant','content':'attraction'}]
        self.assertTrue(current_context(history,'explain it more')[1])
        self.assertEqual(current_context(history,'tell me about spotify'),([],False))


class KnowledgeContextTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.events=[]
        self.worker=Knowledge({'stream':False},lambda *args:self.events.append(args))
        self.worker.attach_conversations(Path(self.temp.name)/'conversation.sqlite3',{'enabled':True})
        self.worker.quick.answer=Mock(return_value=None)
        self.worker.client.request=Mock(return_value={'answer':'Follow-up result'})
        self.addCleanup(self.worker.close)

    def saved(self, question, reply):
        store=self.worker.conversations
        session=store.start_session()
        turn=store.begin(session,question)
        store.finish(turn,reply)
        return session

    def test_current_session_has_priority_over_conflicting_old_memory(self):
        self.saved('snake game','Old Python implementation')
        self.worker.record_pair('snake game','Current C++ Win32 implementation')
        self.worker.start()
        self.worker.submit('What UI does the snake game use?')
        wait_until(self,lambda:self.worker.client.request.called)
        payload=self.worker.client.request.call_args.args[0]
        self.assertEqual(payload['context_source'],'current_session')
        self.assertIn('Current C++',json.dumps(payload['history']))
        self.assertNotIn('Old Python',json.dumps(payload['history']))
        self.assertIsNone(self.worker.pending_memory)

    def test_one_old_memory_supplies_question_and_answer_context(self):
        self.saved('snake game','Python pygame')
        self.worker.start()
        self.worker.submit('Explain the snake game')
        wait_until(self,lambda:self.worker.client.request.called)
        payload=self.worker.client.request.call_args.args[0]
        self.assertIn('Python pygame',json.dumps(payload['history']))
        self.assertTrue(payload['conversation_context'])

    def test_multiple_memories_pause_then_clicked_selection_generates_once(self):
        self.saved('snake game','Python implementation')
        self.saved('snake game','C++ implementation')
        self.worker.start()
        self.worker.submit('Explain the snake game')
        wait_until(self,lambda:self.worker.pending_memory is not None)
        card=self.worker.choice_snapshot()
        self.worker.client.request.assert_not_called()
        self.assertEqual(len(card['options']),2)
        self.assertTrue(all('snake' in option['context'] and 'Matched:' in option['context'] for option in card['options']))
        chosen=self.worker.pending_memory['matches'][1]['answer']
        other=self.worker.pending_memory['matches'][0]['answer']
        self.worker.choose_memory(card['token'],1)
        with self.assertRaises(ValueError):
            self.worker.choose_memory(card['token'],1)
        wait_until(self,lambda:self.worker.client.request.called)
        payload=self.worker.client.request.call_args.args[0]
        self.assertIn(chosen,json.dumps(payload['history']))
        self.assertNotIn(other,json.dumps(payload['history']))
        self.assertEqual(payload['question'],'Explain the snake game')
        wait_until(self,lambda:len(self.worker.history)==2)
        self.worker.submit('Explain it more')
        wait_until(self,lambda:self.worker.client.request.call_count==2)
        self.assertIn(chosen,json.dumps(self.worker.client.request.call_args.args[0]['history']))

    def test_memory_click_bypasses_running_desktop_task(self):
        actions=Actions.__new__(Actions)
        actions.knowledge=self.worker
        actions.task_active=True
        actions.report=Mock()
        actions.task_state=None
        self.worker.choose_memory=Mock()
        Actions.submit(actions,Command('memory_choice','1','token'))
        self.worker.choose_memory.assert_called_once_with('token',1)
        actions.report.assert_not_called()

    def test_spoken_selection_and_stale_click(self):
        self.saved('snake game','Python')
        self.saved('snake game','C++')
        self.worker.start()
        self.worker.submit('snake game details')
        wait_until(self,lambda:self.worker.pending_memory is not None)
        self.assertTrue(self.worker.memory_reply(Command('select_context','2:option')))
        wait_until(self,lambda:self.worker.client.request.called)
        self.assertEqual(self.worker.client.request.call_count,1)

    def test_cancel_expiry_and_new_question_invalidate_choices(self):
        for mode in ('cancel','expire','new'):
            worker=self.worker
            if not worker.thread.is_alive(): worker.start()
            self.saved('snake game','Python')
            self.saved('snake game','C++')
            worker.submit('snake game details')
            wait_until(self,lambda:worker.pending_memory is not None)
            token=worker.pending_memory['token']
            if mode=='cancel': worker.cancel()
            elif mode=='expire': worker.pending_memory['expires']=0; worker.choice_snapshot()
            else: worker.submit('unrelated gravity topic')
            with self.assertRaises(ValueError): worker.choose_memory(token,0)
            wait_until(self,lambda:worker.queue.unfinished_tasks==0)
            worker.history=[]
            worker.context_seed=[]

    def test_forget_starts_new_session_but_retains_archive(self):
        before=self.worker.session_id
        self.worker.record_pair('snake game','complete')
        self.worker.forget()
        self.assertNotEqual(before,self.worker.session_id)
        self.assertEqual(self.worker.history,[])
        self.assertEqual(self.worker.conversations.turns(before)[0]['answer'],'complete')

    def test_quick_answers_also_persist_full_pair(self):
        self.worker.quick.answer.return_value='A direct local answer'
        self.worker.start()
        self.worker.submit('local question')
        wait_until(self,lambda:len(self.worker.history)==2)
        self.assertEqual(self.worker.conversations.turns(self.worker.session_id)[0]['answer'],'A direct local answer')

    def test_corrupt_storage_degrades_to_ram_without_replacing_file(self):
        bad=Path(self.temp.name)/'corrupt.sqlite3'
        bad.write_bytes(b'preserve corrupt data')
        self.worker.attach_conversations(bad,{'enabled':True})
        self.worker.record_pair('hello','world')
        self.assertEqual(bad.read_bytes(),b'preserve corrupt data')
        self.assertEqual(self.worker.history[-1]['content'],'world')
        self.assertTrue(any(kind=='repair' for kind,_ in self.events))

    def test_storage_failure_throttles_reports_and_later_recovers(self):
        self.worker.conversations=Mock()
        self.worker.conversations.matches.side_effect=sqlite3.OperationalError('locked')
        with patch('jarvis.knowledge.time.monotonic',return_value=100):
            self.worker._saved('matches','x','session')
            self.worker._saved('matches','x','session')
        self.assertEqual(sum(kind=='repair' for kind,_ in self.events),1)
        self.worker.conversations.matches.side_effect=None
        self.worker.conversations.matches.return_value=[]
        self.assertEqual(self.worker._saved('matches','x','session'),[])

    def test_legacy_notes_are_bound_choices_not_silently_merged(self):
        self.worker.memory=Mock()
        self.worker.memory.recall.return_value=[{'date_utc':'2026-10-01','observation':'snake python context'},
                                               {'date_utc':'2026-10-02','observation':'snake cpp context'}]
        self.worker.start()
        self.worker.submit('snake details')
        wait_until(self,lambda:self.worker.pending_memory is not None)
        self.worker.choose_memory(self.worker.pending_memory['token'],0)
        wait_until(self,lambda:self.worker.client.request.called)
        payload=self.worker.client.request.call_args.args[0]
        self.assertIn('snake python context',json.dumps(payload['history']))
        self.assertNotIn('snake cpp context',json.dumps(payload['history']))


class SelectorTests(unittest.TestCase):
    def test_app_switch_invalidates_same_goal_selector_cache(self):
        worker=Knowledge({},Mock())
        worker.context_selector=Mock()
        worker.context_selector.options={'enabled':True}
        current={'handle':1,'pid':20,'title':'calculator','status':'open'}
        worker.app_snapshot_provider=lambda:{'current':current}
        worker.prepare_context('improve it')
        worker.prepare_context('improve it')
        self.assertEqual(worker.context_selector.prepare.call_count,1)
        current['title']='snake game'
        worker.prepare_context('improve it')
        self.assertEqual(worker.context_selector.prepare.call_count,2)

    def test_app_followup_uses_open_window_for_retrieval_without_rewriting_request(self):
        worker=Knowledge({},Mock())
        worker._saved=Mock(return_value=[{'id':'a','score':3},{'id':'b','score':1}])
        worker._memory_history=Mock(return_value=[{'role':'assistant','content':'calculator context'}])
        choose=Mock(return_value='a')
        result=worker._context('improve it',[],'session',choose,app_context={'current':{'title':'Python calculator','status':'open'}})
        self.assertEqual(worker._saved.call_args.args[1],'improve it Python calculator')
        self.assertEqual(choose.call_args.args[0]['request'],'improve it')
        self.assertEqual(result['selected_id'],'a')
        worker._context('improve it',[],'session',choose,app_context={'current':{'title':'Python calculator','status':'closed'}})
        self.assertEqual(worker._saved.call_args.args[1],'improve it')

    def test_selector_defaults_are_independent_from_voice_cleanup(self):
        from jarvis.context_selector import settings
        self.assertEqual(settings()['model'],'qwen3.5:0.8b')
        self.assertFalse(settings()['enabled'])
        with self.assertRaisesRegex(ValueError,'context_selector.timeout_seconds'):
            settings({'timeout_seconds':50})

    def test_short_wire_ids_map_back_to_exact_saved_turn(self):
        from jarvis.context_selector import select_payload
        rows=[{'id':'0123456789abcdef'*2,'question':'calculator','answer':'purple'},
              {'id':'fedcba9876543210'*2,'question':'snake','answer':'blue'}]
        payload=select_payload('calculator',rows,self.selector.options)
        self.assertNotIn(rows[0]['id'],json.dumps(payload))
        with patch('jarvis.context_selector.stream_json',return_value={'id':'b'}):
            self.assertEqual(select('snake',rows,self.selector.options),rows[1]['id'])

    def setUp(self):
        self.request=Mock(return_value='a')
        self.clock=[100.0]
        self.selector=ContextSelector({'enabled':True},Mock(),self.request,lambda:self.clock[0])
        self.addCleanup(self.selector.close)

    def test_preparation_is_async_and_planner_does_not_wait(self):
        entered,release=threading.Event(),threading.Event()
        def producer(choose,cancelled):
            entered.set(); release.wait(2); return {'history':[{'role':'assistant','content':'context'}], 'matches':[], 'source':'saved_memory'}
        future=self.selector.prepare(producer)
        self.assertTrue(entered.wait(2))
        worker=Knowledge({},Mock())
        worker.prepare_context=Mock(return_value=future)
        started=time.monotonic()
        self.assertIsNone(worker.planning_context('goal'))
        self.assertLess(time.monotonic()-started,.1)
        release.set()
        future.result(2)
        self.assertEqual(worker.planning_context('goal')['status'],'selected')

    def test_timeout_backoff_keeps_thread_alive_and_recovers(self):
        self.request.side_effect=TimeoutError()
        self.assertEqual(self.selector.choose('goal',[],lambda:False),'ambiguous')
        self.clock[0]=129
        self.selector.choose('goal',[],lambda:False)
        self.assertEqual(self.request.call_count,1)
        self.clock[0]=131
        self.request.side_effect=None
        self.assertEqual(self.selector.choose('goal',[],lambda:False),'a')

    def test_shutdown_discards_output_and_prevents_repair(self):
        entered,release=threading.Event(),threading.Event()
        def producer(choose,cancelled):
            entered.set(); release.wait(2); return 'discard'
        future=self.selector.prepare(producer)
        self.assertTrue(entered.wait(2))
        self.selector.closed.set()
        release.set()
        self.assertIsNone(future.result(2))
        self.selector.close()
        self.assertFalse(self.selector.repair())
        self.assertIsNone(self.selector.prepare(lambda *_:'wrong').result(1))

    def test_cancelled_job_never_calls_model(self):
        future=self.selector.prepare(lambda choose,stopped:choose('goal',[],stopped),lambda:True)
        self.assertIsNone(future.result(1))
        self.request.assert_not_called()

    def test_transport_rejects_unknown_ids_and_extra_instructions(self):
        for result in ({'id':'invented'},{'id':'a','action':'delete'},{'id':['a']}):
            with patch('jarvis.context_selector.stream_json',return_value=result),self.assertRaises(ValueError):
                select('goal',[{'id':'a','question':'x','answer':'y'}],self.selector.options)

    def test_selector_failure_does_not_drop_bound_options(self):
        worker=Knowledge({},Mock())
        worker._saved=Mock(return_value=[{'id':'a','score':1},{'id':'b','score':1}])
        result=worker._context('goal',[],'session',choose=lambda *_:'a')
        self.assertEqual(len(result['matches']),2)
        self.assertEqual(result['history'],[])

    def test_specific_selector_choice_passes_but_tied_choice_does_not(self):
        worker=Knowledge({},Mock())
        worker._saved=Mock(return_value=[{'id':'a','score':3},{'id':'b','score':1}])
        worker._memory_history=Mock(return_value=[{'role':'assistant','content':'selected'}])
        result=worker._context('goal',[],'session',choose=lambda *_:'a')
        self.assertEqual(result['selected_id'],'a')
        self.assertEqual(result['matches'],[])


class PromptContextTests(unittest.TestCase):
    def test_answer_projection_reserves_space_in_small_model_window(self):
        history=[]
        for i in range(8):
            history.extend([{'role':'user','content':'topic '+str(i)},
                            {'role':'assistant','content':'code '*4000}])
        chat=Mock(return_value=json.dumps({'answer':'done','needs_web':False}))
        answer({'question':'continue it','history':history,'conversation_context':True,
                'options':{'num_ctx':4096}},chat_fn=chat)
        sent=chat.call_args.args[2]
        self.assertLessEqual(sum(len(item['content']) for item in sent[1:-1]),6144)
        self.assertEqual(len(history[-1]['content']),20000)

    def test_selected_recall_is_explicit_and_does_not_require_web(self):
        history=[{'role':'user','content':'Nimbus calculator colors'},
                 {'role':'assistant','content':'We chose purple buttons.'}]
        chat=Mock(return_value=json.dumps({'answer':'Purple.','needs_web':True}))
        search=Mock()
        result=answer({'question':'What color did we choose for Nimbus?', 'history':history,
                       'conversation_context':True,'context_source':'selected_memory'},
                      chat_fn=chat,search_fn=search)
        self.assertEqual(result['answer'],'Purple.')
        search.assert_not_called()
        sent=chat.call_args.args[2]
        self.assertEqual(len(sent),2)
        self.assertIn('Selected saved conversation',sent[-1]['content'])
        self.assertIn('purple buttons',sent[-1]['content'])
        self.assertTrue(sent[-1]['content'].endswith('What color did we choose for Nimbus?'))

    def test_ready_context_reaches_each_planner_operation(self):
        from jarvis.brain import BrainClient
        client=BrainClient.__new__(BrainClient)
        client.worker_module='jarvis.brain_worker'
        client.options={}
        context={'status':'selected','source':'saved_memory','messages':[{'role':'assistant','content':'purple'}]}
        client.context_provider=Mock(return_value=context)
        client._request_once=Mock(return_value={'steps':[]})
        for operation in ('plan','replan','next_step','code_plan','code_edit'):
            client.request(operation,lambda:False,goal='Nimbus calculator',memory_context={'projects':['kept']})
            sent=client._request_once.call_args.kwargs
            self.assertEqual(sent['memory_context']['conversation'],context)
            self.assertEqual(sent['memory_context']['projects'],['kept'])

    def test_worker_keeps_more_than_three_pairs_and_context_priority_instruction(self):
        history=[]
        for i in range(8): history += [{'role':'user','content':'topic '+str(i)},{'role':'assistant','content':'answer '+str(i)}]
        chat=Mock(return_value=json.dumps({'answer':'done','needs_web':False}))
        answer({'question':'continue it','history':history,'conversation_context':True},chat_fn=chat)
        sent=chat.call_args.args[2]
        self.assertEqual(sent[1:-1],history)
        self.assertIn('Current-session corrections take priority',sent[0]['content'])


if __name__=='__main__': unittest.main()
