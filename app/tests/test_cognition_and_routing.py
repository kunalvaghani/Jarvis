"""Cognitive concurrency, routing/privacy and no-replay acceptance checks."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from jarvis.cognition import Cognition
from jarvis.commands import Command, parse
from jarvis.cloud_policy import settings
from jarvis.cloud_quota import QuotaGuardian
from jarvis.groq_adapter import GroqAdapter
from jarvis.hybrid_inference import HybridGateway
from tests.fake_groq import server

def fixture_actions(root):
    return SimpleNamespace(base=root, current_item=None, whatsapp_prompts=[], pending_tasks=[],
        session_style={}, approvals_waiting=0, memory=None)

@pytest.mark.asyncio
async def test_4hz_slow_storage_and_twenty_simultaneous_sensors(tmp_path):
    mind=Cognition(fixture_actions(tmp_path))
    samples=[]
    original=mind.tick
    def tick(): samples.append(time.monotonic());original()
    mind.tick=tick
    mind.write_state=lambda:time.sleep(.18)
    gate=threading.Barrier(21)
    def ingress(i):
        gate.wait(timeout=3)
        if i==20:mind.perceive_command(Command('ask','Voice input'))
        else:mind.perceive(('screen_awareness','gods_eye','weather_watch','whatsapp')[i%4],'sensor',str(i),.7)
    mind.start()
    heartbeats=[]
    async def heartbeat():
        end=time.monotonic()+2.2
        while time.monotonic()<end:
            heartbeats.append(time.monotonic());await asyncio.sleep(.02)
    try:
        with ThreadPoolExecutor(max_workers=21) as pool:
            loop=asyncio.get_running_loop()
            await asyncio.gather(heartbeat(),*(loop.run_in_executor(pool,ingress,i) for i in range(21)))
        intervals=[b-a for a,b in zip(samples,samples[1:])]
        assert len(samples)>=8
        assert max(intervals)<.31,intervals
        assert max(b-a for a,b in zip(heartbeats,heartbeats[1:]))<.12
    finally:
        mind.close();mind.thread.join(timeout=2)

def test_voice_window_weather_priority_and_backpressure(tmp_path):
    mind=Cognition(fixture_actions(tmp_path))
    mind.perceive_command(Command('ask','Voice input'))
    mind.perceive_window('Active application')
    for i in range(400):mind.perceive('weather_watch','sensor',f'Alert {i}',1.)
    mind.tick()
    assert len(mind.percepts)<=200 and len(mind.inbox)<=200
    assert [p.source for p in mind.attention[:2]]==['you','screen']

def test_seven_slots_deterministic_eviction_preserves_goal_and_task(tmp_path):
    from jarvis.context_hub import situation
    actions=fixture_actions(tmp_path)
    actions.current_item=('id',Command('task','Active protected task'))
    mind=actions.cognition=Cognition(actions)
    mind.workspace['goal']='Protected goal'
    for i in range(12):
        mind.perceive('sensor','sensor',f'Item {i}',.2 if i<5 else .6)
        mind.percepts[-1].at=1000+i
    with patch('jarvis.cognition.time.time',return_value=1012):mind.tick()
    assert len(mind.attention)==7
    assert [p.content for p in mind.attention]==[f'Item {i}' for i in range(11,4,-1)]
    with patch('jarvis.context_hub.foreground',return_value=('','')):
        context=situation(actions)
    assert context['working_memory']['goal']=='Protected goal'
    assert context['working_memory']['active_task']=='Active protected task'

@pytest.mark.parametrize('text,kind',[('pause','click_control'),('volume up','spotify_volume'),('open Chrome','open')])
def test_direct_reflex_priority_and_latency_without_models(tmp_path,text,kind):
    with patch('jarvis.repo_abilities.parse_learned',return_value=Command('ability_run','malicious')),patch('jarvis.phrasing.canonical',side_effect=AssertionError('Reflex must bypass slow canonical routing')):
        begin=time.perf_counter();result=parse(text)
        assert result.kind==kind
        assert time.perf_counter()-begin<.015

@pytest.mark.parametrize('payload',[
    {'question':'Summarize my unread Gmail from Raveena'},
    {'question':'Explain unread Gmail from Raveena and quantum entanglement'},
    {'question':'Explain m\u200by unread messages about quantum entanglement'},
    {'question':'Explain quantum entanglement','screen':{'image':'PRIVATE_IMAGE'}},
    {'question':'Explain quantum entanglement','pc_context':{'secret':'PRIVATE_PC'}},
    {'question':'Explain quantum entanglement','images':['PRIVATE_IMAGE']},
    {'question':'Explain quantum entanglement','working_memory':{'goal':'PRIVATE_GOAL'}}])
def test_private_screen_pc_payload_never_reaches_groq(tmp_path,payload):
    options=settings({'enabled':True,'routing':'public','account_plan':'free','free_tier_confirmed':True,'dedicated_quota_confirmed':True},environ={})
    with server() as (endpoint,state):
        guardian=QuotaGuardian(tmp_path/'quota.sqlite3',options)
        adapter=GroqAdapter('fake-test-only-key',options,guardian,endpoint=endpoint,testing=True)
        gateway=HybridGateway(tmp_path,options,adapter=adapter,guardian=guardian)
        try:
            assert gateway.answer(payload) is None
            assert state['calls']==0 and state['bodies']==[]
        finally:gateway.close()

@pytest.mark.parametrize('mode',['ok','429','timeout'])
def test_question_worker_public_route_and_local_fallback(tmp_path,mode):
    from jarvis.knowledge_worker import handle_request
    options=settings({'enabled':True,'routing':'public','account_plan':'free','free_tier_confirmed':True,'dedicated_quota_confirmed':True,'timeout_seconds':1},environ={})
    with server() as (endpoint,state):
        state['mode']='429' if mode=='429' else 'ok'
        if mode=='timeout':state['delay']=1.2
        guardian=QuotaGuardian(tmp_path/'quota.sqlite3',options)
        adapter=GroqAdapter('fake-test-only-key',options,guardian,endpoint=endpoint,testing=True)
        gateway=HybridGateway(tmp_path,options,adapter=adapter,guardian=guardian)
        local=Mock(return_value={'answer':'Local fallback answer'})
        try:
            with patch('jarvis.hybrid_inference.get_service',return_value=gateway),patch('jarvis.hybrid_inference.BASE',tmp_path),patch('jarvis.knowledge_worker.ensure_server',return_value={'models':[{'name':'qwen3.5:9b'}]}),patch('jarvis.knowledge_worker.answer',local):
                result=handle_request({'question':'Explain quantum entanglement','options':{'model':'qwen3.5:9b'}},Mock())
            assert state['calls']==1
            if mode=='ok':assert result['answer']=='Public answer';local.assert_not_called()
            else:
                assert result['answer']=='Local fallback answer'
                assert local.call_args.args[0]['options']['model']=='qwen3.5:9b'
            assert all('PRIVATE' not in json.dumps(row) for row in state['bodies'])
        finally:gateway.close()

def test_destructive_multi_effect_task_halts_and_logs_approval(tmp_path):
    from jarvis.actions import Actions
    actions=Actions({'apps':{},'files_root':'managed','_ui_verification':True,'memory':{'enabled':False},'brain':{'enabled':False}},tmp_path,lambda *_:None)
    prior_brain=actions.brain
    actions.brain=SimpleNamespace(run=Mock(side_effect=AssertionError('No task execution before approval')))
    try:
        result=actions.execute(Command('task','Delete all files in Downloads and email the log'))
        assert actions.pending_opinion and actions.pending_opinion['opinion']['risk']=='high'
        assert 'approval' in result.casefold() or 'go ahead' in result.casefold()
        assert actions.deliberation.decisions()[-1]['approval']=='proposed'
        actions.brain.run.assert_not_called()
    finally:
        actions.brain=prior_brain;actions.close()

def test_gmail_crash_records_uncertainty_and_refuses_restart_replay(tmp_path):
    from jarvis.gmail_writes import guard
    from jarvis.task_state import TaskState
    state=TaskState(tmp_path);state.start('Synthetic approved email','task')
    with pytest.raises(OSError):
        with guard(tmp_path,'gmail_api_send','new',{'to':'fixture@example.org'},state=state) as journal:
            journal.begin();raise OSError('Crash after external dispatch')
    restarted=TaskState(tmp_path)
    assert any(c['stage']=='uncertain_external_write' for c in restarted.snapshot()['checkpoints'])
    assert restarted.resume_blocker(restarted.snapshot())
    for _ in range(35):state.checkpoint('verified',action='read_file',evidence='Read only')
    state.finish('completed','Unexpected completion')
    assert state.snapshot()['status']=='paused'
    assert state.resume_blocker(state.snapshot())
    with pytest.raises(ValueError,match='uncertain'):
        with guard(tmp_path,'gmail_api_send','new',{'to':'fixture@example.org'},state=restarted):pytest.fail('Replay issued')

def test_read_and_inference_retry_are_bounded_but_writes_never_retry():
    from jarvis.task_recovery import retry_read
    read=Mock(side_effect=[OSError('Transient')]*4+['ok'])
    assert retry_read(read,read_only=True,wait=lambda _:None)=='ok'
    assert read.call_count==5
    read=Mock(side_effect=OSError('Permanent'))
    with pytest.raises(OSError):retry_read(read,read_only=True,wait=lambda _:None)
    assert read.call_count==5
    write=Mock()
    with pytest.raises(ValueError):retry_read(write,read_only=False)
    write.assert_not_called()
    read=Mock()
    with pytest.raises(InterruptedError):retry_read(read,read_only=True,cancelled=lambda:True)
    read.assert_not_called()

@pytest.mark.parametrize('stat',[None,{'attempts':'broken','successes':float('nan')},{'attempts':-10,'successes':99,'mean_seconds':'bad'}])
def test_predict_corrupt_history_fails_safe_with_bayesian_interval(tmp_path,stat):
    mind=Cognition(fixture_actions(tmp_path));mind.stats['open']=stat
    prediction=mind.predict(Command('open','Chrome'))
    lo,hi=prediction['confidence_interval']
    assert 0<=lo<=prediction['success_chance']<=hi<=1

def test_paused_task_is_not_learned_as_success(tmp_path):
    mind=Cognition(fixture_actions(tmp_path))
    mind.act(Command('task','Synthetic goal'),lambda:'Task paused: uncertain external effect')
    assert mind.stats['task']['successes']==0

def test_batched_decay_matches_scalar_and_bayesian_history(tmp_path):
    from jarvis.experience import hotness,hotness_many
    now=time.time();stamps=[now-i*3600 for i in range(200)]
    assert hotness_many(stamps,now=now)==pytest.approx([hotness(t,now=now) for t in stamps])
    mind=Cognition(fixture_actions(tmp_path));mind.stats['open']={'attempts':100,'successes':90,'failures':10,'mean_seconds':1.}
    p=mind.predict(Command('open','Chrome'))
    assert p['success_chance']==pytest.approx(91/102,abs=.005)
    assert p['confidence_interval'][1]-p['confidence_interval'][0]<.2

def test_concurrent_stats_and_snapshots_do_not_lose_updates(tmp_path):
    mind=Cognition(fixture_actions(tmp_path));mind.start()
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures=[pool.submit(mind.evaluate,Command('open',str(i)),{},True,.01) for i in range(100)]
            for _ in range(100):mind.snapshot()
            for future in futures:future.result(timeout=3)
        assert mind.stats['open']['attempts']==100
        assert mind.stats['open']['successes']==100
    finally:mind.close()
    assert not mind.thread.is_alive() and not mind.writer_thread.is_alive()
    assert json.loads(mind.stats_path.read_text())['open']['attempts']==100

def test_verified_external_write_clears_only_its_own_pending_marker(tmp_path):
    from jarvis.task_state import TaskState
    state=TaskState(tmp_path);state.start('Synthetic writes','task')
    state.checkpoint('uncertain_external_write',action='gmail_api_send',target='a')
    state.checkpoint('uncertain_external_write',action='gmail_api_send',target='b')
    state.checkpoint('external_write_verified',action='gmail_api_send',target='a')
    assert state.resume_blocker(state.snapshot())
    state.checkpoint('external_write_verified',action='gmail_api_send',target='b')
    assert not state.resume_blocker(state.snapshot())

def test_stats_disk_failure_never_replays_successful_action(tmp_path):
    mind=Cognition(fixture_actions(tmp_path));action=Mock(return_value='Opened synthetic app')
    with patch.object(mind,'_write_stats',side_effect=OSError('Disk unavailable')):
        assert mind.act(Command('open','Fixture'),action)=='Opened synthetic app'
    action.assert_called_once()
    assert mind.persistence_error == 'OSError'
    assert 'Disk unavailable' not in str(mind.snapshot())

def test_transient_read_observation_uses_real_retry_policy(tmp_path):
    from jarvis.brain import Brain
    actions=fixture_actions(tmp_path);ui=Mock();ui._handle.return_value=123
    ui.runner.side_effect=[OSError('Read transport unavailable')]*4+[{'title':'Owned fixture','controls':[]}]
    actions._ui=lambda:ui
    brain=Brain(actions,tmp_path,{'enabled':False})
    try:
        from jarvis.task_recovery import retry_read
        with patch('jarvis.task_recovery.retry_read',side_effect=lambda operation,**kwargs:retry_read(operation,**kwargs,wait=lambda _:None)):
            _,observed=brain.observe(lambda:False)
        assert observed['title']=='Owned fixture'
        assert ui.runner.call_count==5
    finally:brain.client.close()

def test_persistence_recovery_respects_stop_and_restart_budget(tmp_path):
    mind=Cognition(fixture_actions(tmp_path))
    mind.thread=Mock();mind.thread.is_alive.return_value=True
    mind.writer_thread=Mock();mind.writer_thread.is_alive.return_value=False
    mind._writer_restarts=3
    assert not mind.repair_persistence()
    mind._writer_restarts=0;mind.stop.set()
    assert not mind.repair_persistence()
    assert mind._writer_restarts==0

def test_builtin_dispatch_and_catalog_are_immutable():
    from jarvis.commands import REFLEX
    from jarvis.intent_catalog import COMPILED,BUILTIN_PATTERN_SHA256
    with pytest.raises(TypeError):REFLEX['pause']=Command('ability_run','shadow')
    assert isinstance(COMPILED,tuple) and len(BUILTIN_PATTERN_SHA256)==64
