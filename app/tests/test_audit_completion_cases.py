"""Complete exact remaining module contracts using bounded owned transports."""
from concurrent.futures import ThreadPoolExecutor
import builtins
import json
import queue
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch
import pytest

from jarvis.commands import Command, parse
from jarvis.engine import Engine
from tests.audit_contract_helpers import benchmark_contract, read_fault, recovery_contract, trace_contract
from tests.test_perception_cognition_audit import mind_at


@pytest.mark.parametrize('case',[8,13,14,15,16,19,23,24,25,26,27,30,32],ids=lambda n:f'JRV-02-{n:03}')
def test_perception_completion(case,tmp_path):
    mind=mind_at(tmp_path)
    if case==8:
        from jarvis.screen_awareness import ScreenAwareness
        mind.actions.report=Mock();screen=ScreenAwareness(mind.actions)
        entered,release=threading.Event(),threading.Event()
        def parser(*_):
            entered.set()
            while not release.is_set():sum(range(3000))
            return {'controls':[]}
        screen._snapshot=parser
        focus={'handle':1,'exe':'fixture.exe','title':'Owned fixture','class':''}
        screen.reading=True;worker=threading.Thread(target=screen._prepare,args=(focus,{'private':True},'fixture'))
        worker.start();assert entered.wait(1)
        mind.start()
        try:
            screen.read_started=time.monotonic()-16
            screen.tick()
            assert screen.health()['state']=='stalled'
            assert mind.actions.report.call_args.args[0]=='repair'
            mind.perceive_command(Command('ask','Priority voice'))
            time.sleep(.8)
            assert mind.cycles>=2 and mind.attention[0].source=='you'
        finally:
            release.set();worker.join(2);mind.close()
    elif case in (13,14):read_fault(OSError('Offline fixture') if case==13 else TimeoutError('30-second-equivalent deadline'))
    elif case==15:
        mind.stats_path.parent.mkdir(parents=True)
        mind.stats_path.write_text('['*1500+'0'+']'*1500,encoding='utf-8')
        restored=mind_at(tmp_path);restored.tick()
        assert restored.predict(Command('open','fixture'))['success_chance']==.5
    elif case==16:
        mind.actions.curator=None;mind.actions.repo_learner=SimpleNamespace(enabled=False)
        assert mind.recall('fixture')=={}
        mind.tick();assert mind.cycles==1
    elif case==19:
        mind.perceive_command(Command('open','fixture'));mind.write_state()
        restored=mind_at(tmp_path)
        assert not restored.inbox and restored.last_outcome is None
        recovery_contract(tmp_path)
    elif case==23:
        sent=[];engine=Engine(sent.append,Mock());engine.activate()
        engine.feed('open Chrome',final=True);engine.feed('Please do not open Chrome',final=True)
        assert sent==[Command('open','chrome')]
    elif case==24:
        from jarvis.task_state import TaskState
        from jarvis.brain import Brain
        state=TaskState(tmp_path);first=state.start('First','task')
        mind.actions.task_state=state;mind.actions.apps={};mind.actions.execute=Mock()
        brain=Brain(mind.actions,tmp_path,{'enabled':False});brain.client=Mock()
        def swapped(*_,**__):
            state.start('Unrelated second','task');return {'steps':[{'action':'open','value':'wrong'}]}
        brain.client.request.side_effect=swapped
        with pytest.raises(ValueError,match='identity'):brain.propose_plan('plan',lambda:False,goal='First')
        assert state.finish('failed','stale result',task_id=first) is False
        assert state.snapshot()['goal']=='Unrelated second' and state.snapshot()['status']=='running'
        mind.actions.execute.assert_not_called()
    elif case==25:
        original=mind.tick;attempts=[0]
        def fault_then_recover():
            attempts[0]+=1
            if attempts[0]==1:raise MemoryError('RAM pressure')
            if attempts[0]==2:raise RuntimeError('GPU allocation')
            original()
        mind.tick=fault_then_recover
        mind.start()
        try:
            time.sleep(.85)
            assert mind.tick_errors==2 and mind.cycles>=1 and mind.thread.is_alive()
            assert parse('open Chrome')==Command('open','chrome')
        finally:mind.close()
    elif case==26:
        from tests.test_cognition_and_routing import test_gmail_crash_records_uncertainty_and_refuses_restart_replay
        test_gmail_crash_records_uncertainty_and_refuses_restart_replay(tmp_path)
    elif case==27:benchmark_contract('02-perception-cognition')
    elif case==30:
        from tests.test_cognition_and_routing import test_persistence_recovery_respects_stop_and_restart_budget
        test_persistence_recovery_respects_stop_and_restart_budget(tmp_path)
    elif case==32:trace_contract(tmp_path)


@pytest.mark.parametrize('case',list(range(13,33)),ids=lambda n:f'JRV-03-{n:03}')
def test_intent_completion(case,tmp_path):
    if case in (13,14,16,25):
        # Known reflexes admit neither optional model dependencies nor network calls.
        with patch('socket.create_connection',side_effect=OSError('offline')) as network, \
             patch('jarvis.phrasing.canonical',side_effect=TimeoutError('unavailable normalizer')) as model:
            assert parse('open Chrome')==Command('open','chrome')
            assert parse('pause').kind=='click_control'
        network.assert_not_called();model.assert_not_called()
    elif case==15:
        for value in (None,{},[],b'open Chrome'):
            with pytest.raises(ValueError):parse(value)
        with pytest.raises(ValueError):parse('tool open_xxx {}')
    elif case==17:
        with ThreadPoolExecutor(max_workers=5) as pool:
            for _ in range(20):
                assert list(pool.map(parse,['open Chrome']*5))==[Command('open','chrome')]*5
    elif case==18:
        from tests.test_audit_resilience import test_AUD_STOP_serializes_with_inflight_feed
        test_AUD_STOP_serializes_with_inflight_feed()
    elif case==19:
        from jarvis.task_state import TaskState
        state=TaskState(tmp_path);state.start('Pending owned command','task')
        restarted=TaskState(tmp_path);assert restarted.snapshot()['status']=='interrupted'
        sent=[];Engine(sent.append,Mock()).feed('open Chrome',final=True);assert not sent
    elif case==20:
        with patch('jarvis.repo_abilities.parse_learned',return_value=Command('run_command','injected')) as learned:
            assert parse('pause')==Command('click_control','pause','click')
            assert parse('Could you bring up Chrome for me?')==Command('open','chrome')
        learned.assert_not_called()
    elif case==21:
        from tests.test_cognition_and_routing import test_private_screen_pc_payload_never_reaches_groq
        test_private_screen_pc_payload_never_reaches_groq(tmp_path,{'question':'Explain api_key=FAKE_PRIVATE_TOKEN','pc_context':{'secret':'PRIVATE_MARKER'}})
    elif case==22:
        command=parse('type exactly "હેલો é 🙂"')
        assert all(token in command.value for token in ('હેલો','é','🙂'))
        assert parse('open\u00a0Chrome')==Command('open','chrome')
        assert len(parse('open folder '+'x'*500).value)==500
    elif case==23:
        sent=[];engine=Engine(sent.append,Mock());engine.activate()
        engine.feed('open Chrome',final=True);engine.feed('Please do not open Chrome',final=True)
        assert sent==[Command('open','chrome')]
    elif case==24:
        from jarvis.actions import Actions
        actions=Actions({'apps':{},'files_root':'managed','_ui_verification':True,'memory':{'enabled':False},'brain':{'enabled':False}},tmp_path,Mock())
        try:
            actions.pending_open={'time':time.monotonic()-1000,'choices':[Command('open','wrong')]}
            with patch('jarvis.actions.subprocess.Popen') as launch:
                result=actions._resolve_reply(Command('choose_control','1'))
            assert result.kind=='clarification_blocked';launch.assert_not_called()
        finally:actions.close()
    elif case==26:
        from tests.test_cognition_and_routing import test_gmail_crash_records_uncertainty_and_refuses_restart_replay
        test_gmail_crash_records_uncertainty_and_refuses_restart_replay(tmp_path)
    elif case==27:benchmark_contract('03-intent-direct')
    elif case==28:
        from tests.test_perception_cognition_audit import test_JRV_02_028_forged_approval_never_opens_gate
        test_JRV_02_028_forged_approval_never_opens_gate(tmp_path)
    elif case==29:
        from jarvis.config_contract import validate_root
        with pytest.raises(ValueError):validate_root({'apps':[]})
        with pytest.raises(ValueError):parse('tool open_xxx {}')
    elif case==30:recovery_contract(tmp_path)
    elif case==31:
        with pytest.raises(ValueError):parse('x'*100001)
        with pytest.raises(ValueError):parse('tool read_file '+ '['*1500+'0'+']'*1500)
    elif case==32:trace_contract(tmp_path)


VOICE_CASES=[1,2,3,6,7,8,9,10,11,13,14,15,16,17,18,19,20,21,22,23,24,25,27,28,30,31,32]
@pytest.mark.parametrize('case',VOICE_CASES,ids=lambda n:f'JRV-04-{n:03}')
def test_voice_completion(case,tmp_path):
    from jarvis.audio import DecodeJob,DecodeQueue,Listener,workers_alive
    from jarvis.command_cleanup import CommandCleanup
    from tests.test_voice_stt_audit import capture_fixture,decode_words,wait_for
    if case in (1,2,3):
        prerequisites={1:'Dedicated medium.en WER/latency session requires free GPU headroom; only 1396 MiB free was observed and no labeled quiet-room corpus is supplied.',
            2:'No labeled background-TV audio corpus with channel/source annotations; textual echo tests cannot measure acoustic false activation rate.',
            3:'No labeled long-pause utterance corpus or reference word timings; 0.8-second VAD endpoint policy cannot certify arbitrary pause intent.'}
        pytest.skip('BLOCKED: '+prerequisites[case])
    elif case==6:
        from jarvis.whisper_backend import WhisperUnavailable
        from main import App
        events=[];listener=Listener(tmp_path,None,Mock(),lambda *a:events.append(a))
        with patch('jarvis.whisper_backend.load_model',side_effect=WhisperUnavailable('model_missing','private path')):
            listener.run()
        assert listener.health()['error']=='model_missing' and listener.stop_event.is_set()
        app=SimpleNamespace(preview=Mock(),actions=SimpleNamespace(submit=Mock()),report=Mock())
        app.preview.get.return_value='open Calculator';App.send_input(app)
        app.actions.submit.assert_called_once_with(Command('open','calculator'))
    elif case in (7,25):
        listener,_,sent,_,_=decode_words(tmp_path,[])
        model=Mock();model.transcribe.side_effect=MemoryError('Synthetic CUDA or RAM allocation pressure')
        listener.jobs.put(DecodeJob(1,0,None,final=True));started=time.monotonic();listener._decode(model)
        assert time.monotonic()-started<1 and listener.stop_event.is_set()
        assert listener.health()['error']=='decode_failure' and not sent
        model.transcribe.assert_called_once()
    elif case==8:
        from tests.test_push_to_write import ListenerRoutingTests,SpokenWriterTests
        check=ListenerRoutingTests('test_held_speech_is_typed_with_case_and_never_reaches_commands')
        result=check.run();assert not result.errors and not result.failures
        check=SpokenWriterTests('test_phrases_follow_the_cursor_with_spacing_and_spoken_new_lines')
        result=check.run();assert not result.errors and not result.failures
    elif case==9:
        from jarvis.push_to_write import PushToWrite,VK_LCONTROL,VK_LMENU
        changes=Mock();keys=PushToWrite(changes,hold_seconds=1,send=Mock())
        try:
            keys.key(VK_LCONTROL,True);keys.key(VK_LMENU,True)
            keys.key(VK_LMENU,False);keys.key(VK_LCONTROL,False)
            assert not keys.active.is_set() and keys.session==0
            changes.assert_not_called()
        finally:keys.closed.set()
    elif case==10:
        from jarvis.actions import Actions
        engine=Engine(Mock(),Mock());engine.activate()
        cleanup=CommandCleanup({'enabled':True},request=lambda text,alternative,*_:alternative)
        assert cleanup.clean('um open ZéphyrWorks',engine)=='open ZéphyrWorks'
        actions=Actions({'apps':{},'files_root':'managed','_ui_verification':True,'memory':{'enabled':False},'brain':{'enabled':False}},tmp_path,Mock())
        try:
            with patch('jarvis.actions.subprocess.Popen') as launch:
                with pytest.raises(ValueError,match='Try another word'):actions.execute(parse('open ZéphyrWorks'))
            launch.assert_not_called()
        finally:actions.close()
    elif case in (11,30):
        from main import App
        from jarvis.recovery import Watchdog
        capture=Mock();capture.is_alive.return_value=False
        app=SimpleNamespace(listener=SimpleNamespace(thread=capture,decoder=None),report=Mock())
        clock=[0.];watch=Watchdog(Mock(),clock=lambda:clock[0])
        watch.register('Owned microphone',lambda:False,lambda:App.repair_listener(app))
        watch.tick();watch.tick();assert app.report.call_count==1
        clock[0]=10.;watch.tick();assert app.report.call_count==2
        watch.close()
    elif case in (13,14,16):
        engine=Engine(Mock(),Mock());engine.activate();clock=[0.]
        error={13:OSError('offline'),14:TimeoutError('30-second-equivalent deadline'),16:ImportError('optional cleanup dependency missing')}[case]
        request=Mock(side_effect=error)
        cleanup=CommandCleanup({'enabled':True},request=request,clock=lambda:clock[0])
        assert cleanup.clean('open note pad',engine)=='open note pad'
        assert cleanup.clean('open note pad',engine)=='open note pad'
        request.assert_called_once();assert cleanup.retry_after==30.
    elif case in (15,20,28):
        engine=Engine(Mock(),Mock());engine.activate()
        for result in (None,[],{'choice':'approved'},'approve','delete all files'):
            cleanup=CommandCleanup({'enabled':True},request=Mock(return_value=result))
            assert cleanup.clean('open note pad',engine)=='open note pad'
        assert not engine.done
    elif case==17:
        engine=Engine(Mock(),Mock());engine.activate()
        cleanup=CommandCleanup({'enabled':True},request=lambda text,alternative,*_:alternative)
        with ThreadPoolExecutor(max_workers=5) as pool:
            for _ in range(20):assert list(pool.map(lambda _:cleanup.clean('open note pad',engine),range(5)))==['open notepad']*5
    elif case in (18,24):
        listener,model,sent,_,_=decode_words(tmp_path,['Jarvis open Calculator'])
        listener.input_filter=lambda text,*_:(listener.stop() or 'jarvis open calculator')
        listener.jobs.put(DecodeJob(1,0,None,final=True))
        listener._decode(model);assert not sent and listener.stop_event.is_set()
    elif case==19:
        first=Listener(tmp_path,None,Mock(),Mock());first.jobs.put(DecodeJob(1,0,None,final=True));first.stop()
        new=Listener(tmp_path,None,Mock(),Mock())
        assert not new.jobs.items and not first.jobs.items
        assert first.trace_id!=new.trace_id and not workers_alive(first)
    elif case==21:
        request=Mock();report=Mock();engine=Engine(Mock(),Mock());engine.activate()
        text='um send Raveena api_key=FAKE_PRIVATE_TOKEN'
        assert CommandCleanup({'enabled':True},report,request).clean(text,engine)==text
        request.assert_not_called();report.assert_not_called()
        trace_contract(tmp_path)
    elif case==22:
        engine=Engine(Mock(),Mock());engine.activate();request=Mock()
        cleanup=CommandCleanup({'enabled':True},request=request)
        text='um type exactly "હેલો é 🙂" '+('x'*500)
        assert cleanup.clean(text,engine)==text;request.assert_not_called()
    elif case==23:
        engine=Engine(Mock(),Mock());engine.activate();request=Mock(return_value='open Calculator')
        cleanup=CommandCleanup({'enabled':True},request=request)
        assert cleanup.clean('do not open Calculator',engine)=='do not open Calculator'
        request.assert_not_called()
        assert parse('open Calculator').kind=='open'
        with pytest.raises(ValueError):parse('do not open Calculator')
    elif case==27:benchmark_contract('04-voice-stt')
    elif case==31:
        for job in (DecodeJob(-1,0,None),DecodeJob(1,float('nan'),None),DecodeJob(1,0,None,final='yes')):
            with pytest.raises(ValueError):DecodeQueue().put(job)
        jobs=DecodeQueue(limit=1);jobs.put(DecodeJob(1,0,None,final=True))
        with pytest.raises(RuntimeError):jobs.put(DecodeJob(2,0,None,final=True))
        assert len(jobs.items)==1
    elif case==32:
        from jarvis.runtime_health import RuntimeHealth
        events=[];listener=Listener(tmp_path,None,Mock(),lambda *a:events.append(a))
        listener._fail('decode_failure',RuntimeError('FAKE_PRIVATE_TOKEN'))
        health=listener.health()
        assert len(health['trace_id'])==32 and health['error']=='decode_failure'
        assert 'FAKE_PRIVATE_TOKEN' not in json.dumps(health) and 'FAKE_PRIVATE_TOKEN' not in str(events)
        listener.error=None;assert listener.health()['trace_id']==health['trace_id']


def test_stalled_decoder_blocks_restart_without_cancelling_active_task():
    from main import App
    capture,decoder=Mock(),Mock();capture.is_alive.return_value=False;decoder.is_alive.return_value=True
    listener=SimpleNamespace(thread=capture,decoder=decoder,stop=Mock())
    app=SimpleNamespace(listener=listener,config={},stop=Mock(),report=Mock(),actions=SimpleNamespace(task_active=True))
    App.toggle_listening(app);app.stop.assert_not_called()
    assert App.repair_listener(app) is False
    listener.stop.assert_called_once()
