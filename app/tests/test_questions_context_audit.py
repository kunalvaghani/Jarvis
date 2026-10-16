"""Prompt 06 regressions: synthetic data and fake transports only."""
import json
import hashlib
import threading
import queue
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock

import pytest

from jarvis.context_selector import ContextSelector, select_payload, settings
from jarvis.knowledge_worker import answer
from jarvis.question_client import QuestionClient


@pytest.mark.parametrize('field,value', [
    ('history', [{'role': 'user', 'content': 'PRIVATE_SENTINEL'}]),
    ('memory_context', [{'text': 'PRIVATE_SENTINEL'}]),
    ('live_app_context', {'title': 'PRIVATE_SENTINEL'}),
    ('memory_facts', ['PRIVATE_SENTINEL']),
])
@pytest.mark.parametrize('reply', ['not JSON', '{"answer":"unsure","needs_web":true}'])
def test_private_context_never_falls_through_to_search(field, value, reply):
    search = Mock(side_effect=AssertionError('private network dispatch'))
    result = answer({'question': 'Explain this observation', field: value},
                    chat_fn=Mock(return_value=reply), search_fn=search)
    assert result['answer']
    search.assert_not_called()


def test_empty_search_has_no_second_inference_or_fake_citations():
    chat = Mock(return_value='invented [7]')
    result = answer({'question': 'weather today'}, chat_fn=chat, search_fn=lambda _: [])
    chat.assert_not_called()
    assert 'could not' in result['answer'].lower()
    assert 'Sources:' not in result['answer']


def test_search_transport_error_does_not_echo_secrets():
    result = answer({'question': 'weather today'}, chat_fn=Mock(),
                    search_fn=Mock(side_effect=OSError('password=PRIVATE_SENTINEL')))
    assert 'PRIVATE_SENTINEL' not in result['answer']
    assert 'could not verify' in result['answer'].lower()


@pytest.mark.parametrize('url', ['javascript:alert(1)', 'https://user:password@example.com', 'https://example.com/a\nforged'])
def test_unsafe_retrieval_urls_do_not_reach_inference(url):
    chat = Mock()
    result = answer({'question':'weather today'},chat_fn=chat,
        search_fn=lambda _: [{'title':'bad','url':url,'snippet':'unsafe'}])
    chat.assert_not_called()
    assert 'could not find usable' in result['answer'].lower()


def test_out_of_range_model_citation_is_not_published_as_verified():
    result = answer({'question':'weather today'},chat_fn=Mock(return_value='False claim [7]'),
        search_fn=lambda _: [{'title':'safe','url':'https://example.com','snippet':'synthetic observation'}])
    assert '[7]' not in result['answer'] and 'Sources:' not in result['answer']


def test_request_trace_reaches_runtime_health_without_payload(tmp_path):
    from types import SimpleNamespace
    from jarvis.runtime_health import RuntimeHealth
    client = ready_client(tmp_path,[json.dumps({'answer':'PRIVATE_ANSWER'})])
    try:
        client.request({'question':'PRIVATE_QUESTION'},lambda:False)
        worker = SimpleNamespace(thread=None,client=client)
        app = SimpleNamespace(listening_requested=False,listener=None,actions=SimpleNamespace(thread=None,knowledge=worker),speech=None)
        snapshot = RuntimeHealth().snapshot(app)
        assert snapshot['answer']['request']['status']=='complete'
        assert 'PRIVATE_' not in json.dumps(snapshot)
    finally: client.close()


def test_cancelled_queued_future_does_not_kill_selector():
    selector = ContextSelector({'enabled': True}, Mock())
    entered, release = threading.Event(), threading.Event()
    def blocking(*_):
        entered.set()
        assert release.wait(2)
    try:
        first = selector.prepare(blocking)
        assert entered.wait(1)
        cancelled = selector.prepare(lambda *_: pytest.fail('cancelled work ran'))
        assert cancelled.cancel()
        release.set()
        first.result(timeout=2)
        # Wait for the cancelled item to be consumed, then prove liveness/readback.
        selector.queue.join()
        assert selector.prepare(lambda *_: 'alive').result(timeout=2) == 'alive'
        assert selector.healthy()
    finally:
        release.set()
        selector.close()


def test_selector_payload_bounds_keywords_and_active_app():
    rows = [{'id': str(i), 'question': 'q'*1000, 'answer': 'a'*1000,
             'keywords': ['k'*1000]*1000} for i in range(20)]
    payload = select_payload({'request': 'x'*10000, 'active_app': {'title': 'x'*100000}}, rows, settings())
    projected = json.loads(payload['messages'][1]['content'])
    assert len(projected['candidates']) == 8
    assert len(json.dumps(projected)) < 15000
    assert all(len(row['keywords']) <= 12 for row in projected['candidates'])


@pytest.mark.parametrize('reply', ['[]', 'null', '{"answer":"","needs_web":false}'])
def test_malformed_local_reply_is_honest_without_private_dispatch(reply):
    result = answer({'question': 'What did I ask?', 'history': [{'role': 'user', 'content': 'secret'}]},
                    chat_fn=Mock(return_value=reply), search_fn=Mock(side_effect=AssertionError('network')))
    assert isinstance(result['answer'], str) and result['answer'].strip()


def ready_client(tmp_path, lines):
    client = QuestionClient(tmp_path, Mock())
    client.process = Mock()
    client.process.poll.return_value = None
    client.responses = queue.Queue()
    for line in lines:
        client.responses.put(line)
    return client


def run_existing(module, cls, method):
    # TestCase.debug propagates assertion failures and executes setup/cleanups.
    from importlib import import_module
    getattr(import_module('tests.'+module), cls)(method).debug()


EXISTING = {
    4: ('test_conversation_context', 'KnowledgeContextTests', 'test_new_topic_in_conversation_answers_without_choice_card'),
    6: ('test_documents', 'Indexing', 'test_light_mode_for_short_documents_answers_with_pages'),
    10: ('test_answer_stream', 'AnswerStreamTests', 'test_cancel_after_partial_never_publishes_final'),
    11: ('test_conversation_context', 'SelectorTests', 'test_timeout_backoff_keeps_thread_alive_and_recovers'),
    14: ('test_answer_stream', 'AnswerStreamTests', 'test_progress_does_not_remove_total_ceiling'),
    16: ('test_question_speed', 'QuestionSpeedTests', 'test_missing_model_never_falls_back'),
    18: ('test_conversation_context', 'SelectorTests', 'test_cancelled_job_never_calls_model'),
    19: ('test_question_speed', 'QuestionSpeedTests', 'test_crash_retries_only_inference_once_and_records_repair'),
    20: ('test_conversation_context', 'SelectorTests', 'test_transport_rejects_unknown_ids_and_extra_instructions'),
    21: ('test_groq', 'IntegrationTests', 'test_private_enrichment_does_not_enter_public_payload'),
    24: ('test_conversation_context', 'SelectorTests', 'test_app_switch_invalidates_same_goal_selector_cache'),
    26: ('test_groq', 'IntegrationTests', 'test_partial_stream_pauses_without_local_duplicate'),
    30: ('test_answer_stream', 'AnswerStreamTests', 'test_worker_loss_after_progress_does_not_restart_or_mix_answers'),
}


@pytest.mark.parametrize('number', range(1, 33), ids=lambda n: f'JRV-06-{n:03d}')
def test_catalog(number, tmp_path):
    if number in EXISTING:
        run_existing(*EXISTING[number])
        return
    if number in (2, 9):
        base = Path(__file__).resolve().parents[1]
        evidence = base/'artifacts/jarvis-audit/modules/06-questions-context/native-default.json'
        result = json.loads(evidence.read_text(encoding='utf-8'))
        assert result['status']=='PASS' and result['model']=='qwen3.5:9b'
        current_hash=hashlib.sha256((base/'jarvis/knowledge_worker.py').read_bytes()).hexdigest()
        if result['worker_sha256']!=current_hash:
            pytest.skip('BLOCKED: cached native qwen3.5:9b proof predates current knowledge_worker source; fresh local inference validation is required. Historical answers/hashes are preserved, not rehashed. The Prompt14 prerequisite probe found Ollama unavailable; no service start or model download authorized.')
        assert result['external_searches']==result['external_writes']==0
        observation = result['cases'][0 if number==2 else 1]
        assert 'qubit' in observation['answer'].lower() and observation['first_content_seconds'] is not None
        if number==9:
            assert any(word in observation['answer'].lower() for word in ('untrusted','malicious','disregard','ignore'))
            assert 'i deleted files' not in observation['answer'].lower()
        return
    if number in (1, 8):
        from jarvis.quick_answers import QuickAnswers
        quick = QuickAnswers()
        results = [quick.answer(q) for q in ('What is two plus two?', 'two plus two', 'what is 2 plus 2')]
        assert all(result and '4' in result for result in results)
    elif number == 3:
        from jarvis.conversation_memory import current_context
        history = [{'role':'user','content':'Explain ocean tides'},
                   {'role':'assistant','content':'The Moon produces tidal forces.'}]
        projection, found = current_context(history,'What did I ask a minute ago?',2000)
        assert found and projection == history
    elif number == 5:
        search = Mock(side_effect=OSError('offline'))
        result = answer({'question':'Explain zorbulatorium'},
            chat_fn=lambda *a, **k:'{"answer":"unknown","needs_web":true}',search_fn=search)
        assert search.call_count == 1 and 'could not verify' in result['answer'].lower()
    elif number == 7:
        from jarvis.conversation_memory import current_context
        history = [{'role':'user','content':'The telescope costs 25 euros'},
                   {'role':'assistant','content':'The telescope is portable.'}]
        projection, found = current_context(history,'what about its cost',2000)
        assert found and projection == history
    elif number == 12:
        test_empty_search_has_no_second_inference_or_fake_citations()
    elif number == 13:
        test_search_transport_error_does_not_echo_secrets()
    elif number == 15:
        for line in ('[]', 'null', '{"answer":12}', 'not JSON'):
            client = ready_client(tmp_path, [line])
            try:
                with pytest.raises(ValueError): client.request({'question':'fixture'}, lambda:False)
                assert client.snapshot()['status']=='failed'
                assert client.process is None
            finally: client.close()
    elif number == 17:
        client = ready_client(tmp_path, [])
        def echo(line):
            request = json.loads(line)
            client.responses.put(json.dumps({'answer':request['question']}))
            time.sleep(.001)
        client.process.stdin.write.side_effect = echo
        try:
            with ThreadPoolExecutor(max_workers=5) as pool:
                for repeat in range(20):
                    questions = [f'question-{repeat}-{i}' for i in range(5)]
                    results = list(pool.map(lambda q:client.request({'question':q},lambda:False)['answer'],questions))
                    assert results == questions
            assert client.process.stdin.write.call_count == 100
        finally: client.close()
    elif number == 22:
        text = 'हिन्दी ગુજરાતી français 😀 "quoted" '+('a'*500)
        client = ready_client(tmp_path,[json.dumps({'answer':text})])
        try:
            assert client.request({'question':text},lambda:False)['answer']==text
            assert json.loads(client.process.stdin.write.call_args.args[0])['question']==text
        finally: client.close()
    elif number in (23,28):
        # The actual question transport returns prose only. Forged tool fields
        # cannot become executable actions; no executor is attached here.
        client = ready_client(tmp_path,[json.dumps({'answer':'No actions performed',
            'steps':[{'tool':'delete','approval':True}]}) for _ in range(2)])
        try:
            for q in ('Delete the example', 'Do not delete the example'):
                result = client.request({'question':q},lambda:False)
                assert result['answer']=='No actions performed'
            assert not hasattr(client,'executor')
        finally: client.close()
    elif number == 25:
        selector = ContextSelector({'enabled':True},Mock(),request=Mock(side_effect=MemoryError()))
        try:
            assert selector.choose('fixture',[],lambda:False)=='ambiguous'
            assert selector.retry_after > selector.clock()
        finally: selector.close()
    elif number == 27:
        rows = __import__('csv').DictReader((Path(__file__).resolve().parents[1]/
            'artifacts/jarvis-audit/modules/06-questions-context/benchmarks.csv').open())
        rows = list(rows)
        for version in ('before','after'):
            assert sum(r['version']==version and r['mode']=='warm_projection' for r in rows)==20
            assert sum(r['version']==version and r['mode']=='cold_projection' for r in rows)==5
        assert all(float(r['latency_ms'])>0 and int(r['external_writes'])==0 for r in rows)
    elif number == 29:
        client = ready_client(tmp_path,[])
        try:
            with pytest.raises(ValueError):
                client.request({'question':'fixture','options':{'timeout_seconds':float('nan')}},lambda:False)
            client.process.stdin.write.assert_not_called()
            with pytest.raises(ValueError): settings({'timeout_seconds':50})
        finally: client.close()
    elif number == 31:
        client = ready_client(tmp_path,[])
        nested = []
        for _ in range(20): nested = [nested]
        try:
            for request in ({'question':'x'*256001},{'question':'fixture','history':nested}):
                with pytest.raises(ValueError): client.request(request,lambda:False)
            client.process.stdin.write.assert_not_called()
            test_selector_payload_bounds_keywords_and_active_app()
        finally: client.close()
    elif number == 32:
        client = ready_client(tmp_path,[json.dumps({'answer':'fine'}),json.dumps({'error':'password=PRIVATE_SENTINEL'})])
        try:
            assert client.request({'question':'fixture'},lambda:False)['answer']=='fine'
            first = client.snapshot()
            assert first['status']=='complete' and len(first['trace_id'])==32
            with pytest.raises(ValueError, match='Question inference failed'):
                client.request({'question':'fixture'},lambda:False)
            second = client.snapshot()
            assert first['trace_id']!=second['trace_id'] and second['status']=='failed'
            assert 'PRIVATE_SENTINEL' not in json.dumps(second)
        finally: client.close()
    else:
        pytest.fail(f'Unmapped case {number}')
