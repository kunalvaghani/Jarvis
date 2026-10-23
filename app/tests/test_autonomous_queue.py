"""Real SQLite lifecycle + fake clocks/resources; no live accounts or desktop effects."""
from dataclasses import asdict
import json
import queue
import threading
import time
from pathlib import Path
from types import SimpleNamespace
import pytest
from jarvis.commands import Command
from jarvis.task_store import TaskStore
from jarvis.task_scheduler import ScheduledQueue
from jarvis.task_policy import classify, score, modifiers
from jarvis.task_decisions import DecisionManager
from jarvis.task_ingress import TaskIngress


@pytest.mark.parametrize('spoken', ['one', '1', '10', 'ten', 'ONE'])
def test_live_probe_accepts_only_equivalent_numbered_fixtures(spoken):
    from scripts.verification.live_voice_queue import fixture_command
    word = 'ten' if spoken in {'10', 'ten'} else 'one'
    assert fixture_command(Command('create', f'live {spoken}.txt')) == Command('create', f'live {word}.txt')


@pytest.mark.parametrize('command', [Command('delete', 'live one.txt'), Command('create', '../live one.txt'),
    Command('create', 'live 11.txt'), Command('create', 'live one.txt', 'private content'), Command('task', 'send a message')])
def test_live_probe_rejects_nonfixture_effects(command):
    from scripts.verification.live_voice_queue import fixture_command
    assert fixture_command(command) is None


def test_persisted_clarifications_bind_answer_to_original_task(tmp_path):
    from jarvis.actions import Actions
    from jarvis.clarification import TaskClarification
    from jarvis.engine import Engine
    actions=Actions({'files_root':'files','apps':{},'task_queue':{'enabled':True}},tmp_path,lambda *_:None)
    ingress=actions.ingress
    actions.knowledge.record_pair=lambda *_args,**_kwargs:None
    ingress.scheduler.observe=lambda:{'ram_available_mb':32000,'desktop':True,'cpu_percent':0,'battery_low':False}
    seen=[]
    def run(goal,cancelled,**kwargs):
        seen.append(goal)
        if 'Your answer:' not in goal:raise TaskClarification('Which harmless fixture label?', 'label')
        return 'Fixture inference verified'
    actions.brain.run=run
    try:
        actions.start()
        for name in ['first','second']:actions.submit(Command('task','create '+name+' fixture'))
        deadline=time.monotonic()+10
        while sum(r['state']=='WAITING_USER' for r in ingress.store.rows())<2 and time.monotonic()<deadline:time.sleep(.01)
        paused=[r for r in ingress.store.rows() if r['state']=='WAITING_USER']
        assert len(paused)==2 and all(r['checkpoint']['clarification'] for r in paused)
        engine=Engine(actions.submit,lambda *_:None);engine.activate()
        engine.feed('answer task 1: alpha',final=True,raw='answer task 1: alpha')
        deadline=time.monotonic()+10
        while ingress.store.get(paused[0]['id'])['state']!='COMPLETED' and time.monotonic()<deadline:time.sleep(.01)
        assert ingress.store.get(paused[0]['id'])['state']=='COMPLETED'
        assert ingress.store.get(paused[1]['id'])['state']=='WAITING_USER'
        assert seen[-1].startswith('create first fixture') and seen[-1].endswith('Your answer: alpha')
        engine.feed('answer task 1: duplicate',final=True,raw='answer task 1: duplicate')
        time.sleep(.2)
        assert len(seen)==3
    finally:actions.close()


def test_clarification_rejects_uncertain_effects_and_uses_saved_folder_choice():
    from jarvis.task_ingress import clarification_command
    row={'state':'WAITING_USER','checkpoint':{'clarification':{
        'goal':'create fixture','question':'Which folder?','slot':'folder','choices':['safe fixture'],
        'source':{'task_id':'original','checkpoints':[]}}}}
    command=clarification_command(row,'one',lambda answer,kind:'C:/owned/'+answer)
    assert command.value=='In folder C:/owned/safe fixture, create fixture'
    row['checkpoint']['clarification']['source']['uncertain_external_writes']=True
    with pytest.raises(ValueError,match='uncertain'):clarification_command(row,'one',lambda *_:None)


def test_deadline_response_applies_only_automatic_preference(tmp_path):
    actions=SimpleNamespace(base=tmp_path,generation=0,closed=threading.Event(),report=lambda *_:None)
    ingress=TaskIngress(actions,tmp_path/'queue.sqlite3')
    clock=Clock();ingress.decisions.clock=clock
    identity=ingress.decisions.create(None,'Overnight scheduling preference',
        ['Balanced priorities','Prefer coding'],confidence=.95,reversible=True,sensitive=False)
    ingress.decisions.presented(identity);clock.now+=20
    try:
        assert ingress.control(Command('task','prefer coding'))
        assert ingress.store.setting('overnight_preference')=='Balanced priorities'
        decision=ingress.decisions.rows()[0]
        assert decision['automatic'] and decision['choice']==0
        assert ingress.decisions.tick()==[]
    finally:ingress.close();ingress.store.db.close()


@pytest.mark.parametrize('kind,value', [('answer','Public fixture reply'),('answer_stream',{'text':'Public fixture reply'})])
def test_background_answers_preserve_displayed_queue_choice(kind,value):
    from jarvis.island_desk import IslandDesk
    desk=IslandDesk.__new__(IslandDesk)
    desk.view='Queue';desk.refresh_overview=lambda:None
    moved=[];desk.show=moved.append
    desk.notify(kind,value)
    assert desk.reply=='Public fixture reply' and not moved


def test_main_presents_new_routine_question_before_starting_mapped_timer():
    from main import App
    app=App.__new__(App);app.events=queue.Queue();seen=[]
    app.root=SimpleNamespace(after=lambda *_:None)
    app.desk=SimpleNamespace(notify=lambda kind,value:seen.append((kind,value)),
        queue_view=SimpleNamespace(tick=lambda:seen.append('tick')))
    app.events.put(('task_decision',{'id':'fixture','status':'PENDING'}))
    app.drain()
    assert seen==[('island_navigation',('Queue','')),'tick']


@pytest.mark.parametrize('with_control',[False,True])
def test_previous_dependency_uses_admission_order_during_burst(tmp_path,with_control):
    actions=SimpleNamespace(base=tmp_path,generation=0,closed=threading.Event(),queue_lock=threading.Lock(),
        pending_tasks=[],thread=threading.Thread(),report=lambda *_:None)
    ingress=TaskIngress(actions,tmp_path/'queue.sqlite3')
    actions._submit=lambda command,expected=None:ingress.enqueue((0,command,threading.Event()))
    first=ingress.submit(Command('create','first.txt'))
    control=ingress.submit(Command('task','pause the queue')) if with_control else None
    second=ingress.submit(Command('task','do this after the previous task: create file second'))
    third=ingress.submit(Command('create','third.txt'))
    try:
        ingress.start();deadline=time.monotonic()+4
        while any(ingress.store.get(key)['state']!='QUEUED' for key in [second,third]) and time.monotonic()<deadline:time.sleep(.01)
        assert ingress.store.get(second)['spec']['dependencies']==[first]
        assert ingress.store.get(third)['spec']['dependencies']==[]
        if control:assert ingress.store.get(control)['checkpoint']['control']
    finally:ingress.close();ingress.close_storage()


@pytest.mark.parametrize('level,state,flags,expected',[(1,0,1,True),(1,0,0,False),(1,4,1,False),(1,0,-1,False),(2,0,1,False)])
def test_windows_session_gate_reads_flags_and_frees_native_buffer(monkeypatch,level,state,flags,expected):
    import ctypes
    from unittest.mock import Mock
    from jarvis.task_policy import session_unlocked,_SessionInfoPrefix
    record=_SessionInfoPrefix();record.level=level;record.data.session.state=state;record.data.session.flags=flags
    def query(server,session,kind,buffer,size):
        assert server is None and session==0xffffffff and kind==25
        buffer._obj.value=ctypes.addressof(record);size._obj.value=ctypes.sizeof(record)
        return True
    api=SimpleNamespace(WTSQuerySessionInformationW=Mock(side_effect=query),WTSFreeMemory=Mock())
    monkeypatch.setattr(ctypes,'WinDLL',lambda *_args,**_kwargs:api)
    assert session_unlocked() is expected
    api.WTSFreeMemory.assert_called_once()


def test_windows_session_gate_fails_closed_on_unavailable_api(monkeypatch):
    import ctypes
    from jarvis.task_policy import session_unlocked
    def unavailable(*_args,**_kwargs):raise OSError('fixture API unavailable')
    monkeypatch.setattr(ctypes,'WinDLL',unavailable)
    assert not session_unlocked()


class Clock:
    def __init__(self): self.now = 1000.
    def __call__(self): return self.now


@pytest.fixture
def runtime(tmp_path):
    clock = Clock()
    store = TaskStore(tmp_path/'queue.sqlite3', clock=clock)
    host = {'ram_available_mb': 32000, 'cpu_percent': 10, 'battery_low': False, 'desktop': True}
    scheduler = ScheduledQueue(store, clock=clock, observe=lambda:host)
    return clock, store, scheduler, host


def add(scheduler, text='task', kind='task', **spec):
    token = threading.Event()
    identity = scheduler.put_nowait((0, Command(kind, text), token), overrides=spec)
    return identity, token


def finish(scheduler, state='COMPLETED'):
    scheduler.outcome(state, 'fixture verified', {'tests': ['simulated handler']})
    scheduler.task_done()


def test_durable_admission_backpressure_and_event_idempotency(tmp_path):
    store = TaskStore(tmp_path/'queue.sqlite3', capacity=1)
    task, fresh = store.admit(asdict(Command('task', 'same')), 'voice-session:utterance:final')
    assert fresh
    assert store.admit(asdict(Command('task', 'same')), 'voice-session:utterance:final') == (task, False)
    with pytest.raises(BufferError): store.admit(asdict(Command('task', 'another')))
    store.db.close()
    assert TaskStore(tmp_path/'queue.sqlite3').get(task)['state'] == 'RECEIVED'


def test_invalid_transition_cannot_replay_terminal(runtime):
    _, store, scheduler, _ = runtime
    identity, _ = add(scheduler)
    scheduler.get(); finish(scheduler)
    with pytest.raises(ValueError): store.transition(identity, 'RUNNING')
    assert store.get(identity)['state'] == 'COMPLETED'


def test_rapid_mixed_intake_while_another_task_runs(runtime):
    _, store, scheduler, _ = runtime
    active, _ = add(scheduler, 'active')
    scheduler.get()
    identities = [add(scheduler, ('voice ' if i%2 else 'typed ')+str(i))[0] for i in range(20)]
    assert len(set(identities)) == 20
    assert scheduler.unfinished_tasks == 21
    with pytest.raises(queue.Empty): scheduler.get(timeout=0)
    finish(scheduler)
    executed = []
    for _ in range(20):
        scheduler.get(); executed.append(scheduler.local.identity); finish(scheduler)
    assert set(executed) == set(identities)
    assert all(store.get(key)['state'] == 'COMPLETED' for key in identities+[active])


def test_priority_deadline_aging_and_duration(runtime):
    clock, store, scheduler, _ = runtime
    normal, _ = add(scheduler, 'normal')
    urgent, _ = add(scheduler, 'urgent', priority=100)
    scheduler.get(); assert scheduler.local.identity == urgent; finish(scheduler)
    late, _ = add(scheduler, 'deadline', deadline=clock()+1)
    scheduler.get(); assert scheduler.local.identity == late; finish(scheduler)
    old = store.get(normal)
    newer, _ = add(scheduler, 'new high', priority=100)
    clock.now += 100000
    # Compare an aged job with a freshly submitted high priority job.
    fresh = store.get(newer); fresh['created'] = clock()
    assert score(old, clock()) > score(fresh, clock())


def test_dependencies_cycle_and_failed_prerequisite(runtime):
    _, store, scheduler, _ = runtime
    a, _ = add(scheduler, 'a')
    b, _ = add(scheduler, 'b', dependencies=[a], priority=100)
    with pytest.raises(ValueError): scheduler.control('dependencies', a, [b])
    scheduler.get(); assert scheduler.local.identity == a; finish(scheduler, 'FAILED')
    with pytest.raises(queue.Empty): scheduler.get(timeout=0)
    assert store.get(b)['state'] == 'WAITING_DEPENDENCY'


def test_dependency_success_and_scheduled_gate(runtime):
    clock, store, scheduler, _ = runtime
    a, _ = add(scheduler)
    b, _ = add(scheduler, dependencies=[a], not_before=clock()+10)
    scheduler.get(); finish(scheduler)
    with pytest.raises(queue.Empty): scheduler.get(timeout=0)
    clock.now += 11
    scheduler.get(); assert scheduler.local.identity == b; finish(scheduler)


def test_concurrent_read_only_and_exclusive_desktop(runtime):
    _, _, scheduler, _ = runtime
    desktop, _ = add(scheduler)
    second, _ = add(scheduler)
    fast, _ = add(scheduler, 'status', kind='system_info')
    scheduler.get()
    def independent():
        scheduler.get(lane='fast'); assert scheduler.local.identity == fast; finish(scheduler)
    thread = threading.Thread(target=independent); thread.start(); thread.join(2)
    assert not thread.is_alive()
    with pytest.raises(queue.Empty): scheduler.get(timeout=0)
    finish(scheduler)
    scheduler.get(); assert scheduler.local.identity == second; finish(scheduler)


@pytest.mark.parametrize('condition,value', [('desktop',False),('ram_available_mb',20),('battery_low',True),('cpu_percent',99)])
def test_resource_pressure_blocks_without_losing_jobs(runtime, condition, value):
    _, store, scheduler, host = runtime
    identity, _ = add(scheduler)
    previous = host[condition]; host[condition] = value
    with pytest.raises(queue.Empty): scheduler.get(timeout=0)
    assert store.get(identity)['state'] == 'QUEUED'
    host[condition] = previous
    scheduler.get(); finish(scheduler)


def test_cancel_pause_and_shutdown_do_not_replay(runtime):
    _, store, scheduler, _ = runtime
    first, token = add(scheduler)
    queued, _ = add(scheduler)
    scheduler.get()
    scheduler.control('pause', first)
    assert token.is_set()
    finish(scheduler)
    assert store.get(first)['state'] == 'PAUSED'
    with pytest.raises(ValueError): scheduler.control('resume', first)
    scheduler.close()
    assert store.get(queued)['state'] == 'QUEUED'
    restored = ScheduledQueue(store, observe=lambda:{'ram_available_mb':32000,'desktop':True,'battery_low':False,'cpu_percent':0})
    restored.restore(9)
    assert first not in restored.items and queued in restored.items


def test_killed_worker_recovery_requires_reconciliation(runtime):
    _, store, scheduler, _ = runtime
    identity, _ = add(scheduler)
    scheduler.get()
    store.recover()
    assert store.get(identity)['state'] == 'PAUSED'
    assert store.get(identity)['checkpoint']['uncertain']
    with pytest.raises(ValueError): scheduler.control('resume', identity)


def test_read_only_retry_bounded_and_writes_never_retried(runtime):
    clock, store, scheduler, _ = runtime
    identity, _ = add(scheduler, kind='system_info')
    for attempt in range(4):
        scheduler.get(lane='fast')
        scheduler.failure(TimeoutError('fixture')); scheduler.task_done()
        if attempt < 3:
            assert store.get(identity)['state'] == 'RETRY_BACKOFF'
            with pytest.raises(queue.Empty): scheduler.get(timeout=0, lane='fast')
            clock.now += 20
    assert store.get(identity)['state'] == 'FAILED'
    write, _ = add(scheduler, 'write')
    scheduler.get(); scheduler.failure(TimeoutError('uncertain write')); scheduler.task_done()
    assert store.get(write)['state'] == 'FAILED' and store.get(write)['retries'] == 0


@pytest.mark.parametrize('sensitive,reversible,confidence,expected', [(False,True,.95,'SELECTED'),(True,True,.99,'WAITING_APPROVAL'),(False,True,.2,'DEFERRED'),(False,False,.99,'DEFERRED')])
def test_decision_timer_requires_presentation_and_safe_policy(runtime, sensitive, reversible, confidence, expected):
    clock, store, _, _ = runtime
    manager = DecisionManager(store, clock=clock)
    identity = manager.create(None, 'Question', ['A','B'], confidence=confidence, reversible=reversible, sensitive=sensitive)
    clock.now += 100
    assert manager.tick() == []
    manager.presented(identity)
    clock.now += 19.99
    assert manager.tick() == []
    clock.now += .01
    result = manager.tick()[0]
    assert result['status'] == expected
    assert manager.choose(identity, 1)[0] is False
    assert len([d for d in manager.rows() if d['status'] == 'SELECTED']) <= 1


def test_response_before_and_after_deadline_atomic(runtime):
    clock, store, _, _ = runtime
    manager = DecisionManager(store, clock=clock)
    a = manager.create(None, 'Choice', ['A','B'], confidence=.99, reversible=True, sensitive=False)
    manager.presented(a); clock.now += 19.999
    assert manager.choose(a, 1)[0]
    clock.now += 10
    assert manager.tick() == []
    b = manager.create(None, 'Choice', ['A','B'], confidence=.99, reversible=True, sensitive=False)
    manager.presented(b); clock.now += 20
    changed, result = manager.choose(b, 1)
    assert not changed and result['automatic'] and result['choice'] == 0


def test_scheduler_pause_and_reprioritize_running(runtime):
    clock, store, scheduler, _ = runtime
    a, _ = add(scheduler)
    b, _ = add(scheduler)
    scheduler.control('pause_queue')
    with pytest.raises(queue.Empty): scheduler.get(timeout=0)
    scheduler.control('urgent', b)
    scheduler.control('deadline', b, clock()+60)
    scheduler.control('resume_queue')
    scheduler.get(); assert scheduler.local.identity == b
    scheduler.control('urgent', b, 120)
    assert store.get(b)['spec']['priority'] == 120
    finish(scheduler)


def test_overnight_ten_jobs_truthful_report(runtime, tmp_path):
    _, store, scheduler, _ = runtime
    jobs = [add(scheduler, f'job{i}', priority=i%3)[0] for i in range(10)]
    store.setting('overnight', True)
    scheduler.control('pause', jobs[-1])
    for i in range(9):
        scheduler.get(); finish(scheduler, 'FAILED' if i == 3 else 'COMPLETED')
    report, path = scheduler.report(tmp_path/'reports')
    saved = json.loads(path.read_text(encoding='utf-8'))
    assert saved['counts'] == {'COMPLETED':8,'FAILED':1,'PAUSED':1}
    assert saved['tasks'] == store.rows()
    assert all('files created' not in r['outcome'] for r in saved['tasks'])


def test_ingress_buffer_overflow_is_durable_and_nonblocking(tmp_path):
    reports, handled = [], []
    actions = SimpleNamespace(base=tmp_path,generation=0,closed=threading.Event(),queue_lock=threading.Lock(),pending_tasks=[],
                              report=lambda *v:reports.append(v))
    ingress = TaskIngress(actions, tmp_path/'queue.sqlite3', {'buffer_size':1})
    def submit(command, expected=None):
        handled.append(command.value)
        ingress.enqueue((0,command,threading.Event()))
    actions._submit = submit
    for i in range(20): ingress.submit(Command('open', f'fixture{i}'))
    assert len(ingress.store.rows()) == 20 and len(reports) == 20
    ingress.start()
    deadline = time.monotonic()+4
    while len(handled) < 20 and time.monotonic() < deadline: time.sleep(.01)
    ingress.close()
    assert len(handled) == 20 and len(set(handled)) == 20


def test_modifiers_and_explicit_deadline():
    text, spec = modifiers('Urgent: add this to the queue: open calculator by 23:59', now=1000)
    assert text == 'open calculator' and spec['priority'] == 100 and spec['deadline'] > 1000
    assert modifiers('in 2 minutes open calculator', 1000) == ('open calculator', {'not_before':1120})
    assert modifiers('create file fixture by 23:59.',1000)[0]=='create file fixture'
    with pytest.raises(ValueError): modifiers('open calculator by 99:99')


def test_duration_estimates_learn_from_actual_runtime(runtime):
    clock, store, scheduler, _ = runtime
    add(scheduler); scheduler.get(); clock.now += 13; finish(scheduler)
    next_task, _ = add(scheduler)
    assert store.get(next_task)['spec']['duration_seconds'] == 13


def test_expected_state_claim_rejects_second_worker(runtime):
    _, store, scheduler, _ = runtime
    identity, _ = add(scheduler)
    scheduler.get()
    with pytest.raises(ValueError): store.transition(identity, 'RUNNING', expected={'QUEUED'})


def test_real_engine_actions_ten_files_and_voice_sleep(tmp_path):
    from jarvis.actions import Actions
    from jarvis.engine import Engine
    events = []
    actions = Actions({'files_root':'files','apps':{},'task_queue':{'enabled':True}}, tmp_path, lambda *r:events.append(r))
    actions.ingress.scheduler.observe = lambda:{'ram_available_mb':32000,'desktop':True,'cpu_percent':0,'battery_low':False}
    entered, release = threading.Event(), threading.Event()
    original = actions.execute
    def execute(command, cancelled):
        entered.set()
        release.wait(3)
        return original(command, cancelled)
    actions.execute = execute
    try:
        actions.start()
        engine = Engine(actions.submit, lambda *_:None); engine.activate()
        engine.feed('create file fixture0', final=True)
        assert entered.wait(2)
        for i in range(1,10):
            if i % 2:
                engine.feed('create file fixture'+str(i), final=True)
            else:
                actions.submit(Command('create','fixture'+str(i)+'.txt'))
        actions.submit(Command('sleep'))
        assert len(actions.ingress.store.rows()) == 10
        assert all(r['state'] != 'CANCELLED' for r in actions.ingress.store.rows())
        release.set()
        actions.queue.join()
        assert all((actions.root/f'fixture{i}.txt').is_file() for i in range(10))
        assert all(r['state'] == 'COMPLETED' for r in actions.ingress.store.rows())
        assert len([r for r in events if r[0]=='task_received']) == 10
        report, _ = actions.ingress.scheduler.report(tmp_path/'morning-reports')
        assert len(report['files']) == 10
        assert all(effect['verification']=='fresh byte readback' for effect in report['files'])
        assert report['recorded_test_evidence']==[]
    finally:
        release.set(); actions.close()


def test_native_queue_controls_and_hidden_decision_timer(tmp_path):
    import tkinter as tk
    from jarvis.island_queue import QueueView
    root = tk.Tk(); root.withdraw()
    actions = SimpleNamespace(base=tmp_path,generation=0,closed=threading.Event(),queue_lock=threading.Lock(),pending_tasks=[],report=lambda *_:None)
    ingress = TaskIngress(actions, tmp_path/'queue.sqlite3')
    actions.ingress = ingress
    app = SimpleNamespace(actions=actions, report=actions.report)
    try:
        view = QueueView(root, app)
        identity, _ = add(ingress.scheduler, 'native fixture')
        decision = ingress.decisions.create(None, 'Choice', ['A','B'], reversible=True,sensitive=False,confidence=.99)
        view.tick()
        assert view.tree.exists(identity)
        assert ingress.decisions.rows()[0]['presented_at'] is None
        view.tree.selection_set(identity)
        view.control('urgent', True)
        assert ingress.store.get(identity)['spec']['priority'] == 100
        view.inspect()
        assert 'User reprioritized' in view.detail.get('1.0','end')
    finally:
        ingress.close(); root.destroy(); ingress.store.db.close()


def test_overnight_sensitive_job_defers_and_independent_work_continues(runtime):
    _, store, scheduler, _ = runtime
    sensitive, _ = add(scheduler, 'echo never executed', kind='run_command', priority=100)
    safe, _ = add(scheduler, 'status', kind='system_info')
    store.setting('overnight', True)
    with pytest.raises(queue.Empty): scheduler.get(timeout=0)
    assert store.get(sensitive)['state'] == 'WAITING_APPROVAL'
    scheduler.get(lane='fast'); assert scheduler.local.identity == safe; finish(scheduler)
    store.setting('overnight', False)
    scheduler.control('resume', sensitive)
    scheduler.get(); assert scheduler.local.identity == sensitive
    finish(scheduler, 'PARTIAL')


def test_dead_worker_supervision_never_replays(runtime):
    _, store, scheduler, _ = runtime
    identity, _ = add(scheduler)
    def die(): scheduler.get()
    worker=threading.Thread(target=die);worker.start();worker.join(2)
    messages = scheduler.supervise()
    assert messages and store.get(identity)['state'] == 'PAUSED'
    assert not scheduler.active and not scheduler.held
    assert identity not in scheduler.items


def test_routine_decision_survives_restart(runtime):
    clock, store, _, _ = runtime
    manager=DecisionManager(store,clock=clock)
    identity=manager.create(None,'Preference',['A','B'],confidence=.95,reversible=True,sensitive=False)
    manager.presented(identity)
    clock.now += 21
    replacement=DecisionManager(store,clock=clock)
    assert replacement.tick()[0]['choice'] == 0
    assert not replacement.tick()


def test_stale_heartbeat_preserves_lock_until_handler_returns(runtime):
    clock, store, scheduler, _ = runtime
    identity, token = add(scheduler)
    scheduler.get();clock.now += 130
    assert scheduler.supervise()
    assert 'desktop' in scheduler.held
    assert store.get(identity)['checkpoint']['heartbeat_stale']
    assert not token.is_set()
    clock.now += 3600;scheduler.supervise()
    assert token.is_set() and 'desktop' in scheduler.held
    finish(scheduler)


def test_queued_commands_keep_original_instruction(runtime):
    _, store, scheduler, _=runtime
    original=asdict(Command('task','Urgent: add this to the queue: open calculator'))
    identity,_=store.admit(original)
    store.transition(identity,'CLASSIFYING')
    scheduler.put_nowait((0,Command('open','calculator'),threading.Event()),identity)
    assert store.get(identity)['original']==original
    assert store.get(identity)['command']['kind']=='open'


def test_real_knowledge_completion_and_targeted_cancellation(tmp_path, monkeypatch):
    from jarvis.knowledge import Knowledge
    import jarvis.hybrid_inference
    monkeypatch.setattr(jarvis.hybrid_inference, 'standalone_public', lambda *_:False)
    reports=[]
    knowledge=Knowledge({'enabled':True,'stream':False},lambda *r:reports.append(r))
    knowledge.prepare_context=lambda *_:None
    knowledge._context=lambda *a,**k:{'history':[],'source':'none','matches':[]}
    knowledge.quick.answer=lambda _:None
    entered=threading.Event()
    def request(payload,cancelled):
        if payload['question']=='first public fixture':
            entered.set()
            deadline=time.monotonic()+4
            while not cancelled() and time.monotonic()<deadline:time.sleep(.01)
        return {'answer':payload['question']+' verified'}
    monkeypatch.setattr(knowledge.client,'request',request)
    actions=SimpleNamespace(base=tmp_path,generation=0,closed=threading.Event(),queue_lock=threading.Lock(),pending_tasks=[],
                            knowledge=knowledge,report=lambda *r:reports.append(r))
    ingress=TaskIngress(actions,tmp_path/'queue.sqlite3')
    ingress.scheduler.observe=lambda:{'ram_available_mb':32000,'desktop':True,'cpu_percent':0,'battery_low':False}
    def submit(command,expected=None):
        ingress.local.overrides={'lane':'question','locks':['conversation'],'read_only':True}
        ingress.enqueue((0,command,threading.Event()))
    actions._submit=submit
    knowledge.start();ingress.start()
    try:
        first=ingress.submit(Command('ask','first public fixture'))
        assert entered.wait(2)
        second=ingress.submit(Command('ask','second public fixture'))
        ingress.scheduler.control('cancel',first)
        deadline=time.monotonic()+5
        while ingress.store.get(second)['state']!='COMPLETED' and time.monotonic()<deadline:time.sleep(.01)
        assert ingress.store.get(first)['state']=='CANCELLED'
        assert ingress.store.get(second)['state']=='COMPLETED'
        assert ingress.store.get(second)['outcome']=='second public fixture verified'
        assert not any(kind=='answer' and text.startswith('first') for kind,text in reports)
    finally:
        ingress.close();knowledge.close()
        for worker in [ingress.thread,ingress.fast_thread,ingress.background_thread,ingress.question_thread]:worker.join(2)
        ingress.store.db.close()


def test_individual_task_response_guard_rejects_already_queued_ui_event():
    from jarvis.voice_runtime import ResponseReports
    token=threading.Event()
    class UI:
        def report(self,*_):raise AssertionError('Expected a scoped event')
        def report_scoped(self,kind,message,guard): self.guard=guard
    ui=UI();reports=ResponseReports(ui.report,lambda:0)
    reports.bind(0,lambda:not token.is_set())
    reports('answer','fixture')
    assert ui.guard()
    token.set()
    assert not ui.guard() and not reports.accepts('answer')


def test_sleep_prevention_is_opt_in_and_cleared_on_owner_thread(tmp_path,monkeypatch):
    import ctypes
    calls=[]
    def request(flags):calls.append(flags);return 1
    monkeypatch.setattr(ctypes.windll.kernel32,'SetThreadExecutionState',request)
    actions=SimpleNamespace(base=tmp_path,report=lambda *_:None)
    ingress=TaskIngress(actions,tmp_path/'queue.sqlite3')
    ingress.store.setting('overnight',True)
    ingress.scheduler.last_resource={'battery_low':False}
    ingress._power(); assert calls==[]
    ingress.options['prevent_sleep']=True
    ingress._power();assert calls==[0x80000001]
    ingress.store.setting('overnight',False)
    ingress._power();assert calls[-1]==0x80000000
    ingress.close();ingress.store.db.close()


def test_reports_redact_credentials(runtime,tmp_path):
    _,store,scheduler,_=runtime
    identity,_=add(scheduler,'public fixture api_key=do-not-export')
    scheduler.get();finish(scheduler)
    report,path=scheduler.report(tmp_path/'reports')
    assert 'do-not-export' not in path.read_text(encoding='utf-8')
    assert 'do-not-export' in store.get(identity)['original']['value']


def test_second_queue_owner_cannot_recover_or_dispatch_active_task(tmp_path):
    def make_actions():
        return SimpleNamespace(base=tmp_path,generation=0,closed=threading.Event(),thread=threading.Thread(),
            queue_lock=threading.Lock(),pending_tasks=[],report=lambda *_:None)
    first=TaskIngress(make_actions(),tmp_path/'queue.sqlite3')
    first.start()
    first.scheduler.observe=lambda:{'ram_available_mb':32000,'desktop':True,'cpu_percent':0,'battery_low':False}
    identity,_=add(first.scheduler,'owned task')
    first.scheduler.get()
    second=TaskIngress(make_actions(),tmp_path/'queue.sqlite3')
    try:
        with pytest.raises(ValueError,match='Another Jarvis'):second.start()
        assert first.store.get(identity)['state']=='RUNNING'
    finally:
        second.close();second.store.db.close()
        first.close();first.close_storage()


def test_engine_preserves_deadline_and_batch_punctuation_before_cleanup():
    from jarvis.engine import Engine
    from jarvis.audio import command_text
    sent=[]
    engine=Engine(sent.append,lambda *_:None);engine.activate()
    for raw in ['Jarvis, create file notes by 23:59','queue these three requests: open calculator; open notepad; create file notes']:
        engine.feed(command_text(raw),final=False,raw=raw)
        assert len(sent) < 2
        engine.feed(command_text(raw),final=True,raw=raw)
    assert sent[0].value=='create file notes by 23:59'
    assert sent[1].value.count(';')==2
    assert all(command.extra=='queue_request' for command in sent)


def test_native_deadline_and_explicit_batch_reach_same_queue(tmp_path):
    from jarvis.actions import Actions
    from jarvis.engine import Engine
    from jarvis.audio import command_text
    actions=Actions({'files_root':'files','apps':{},'task_queue':{'enabled':True}},tmp_path,lambda *_:None)
    actions.ingress.scheduler.observe=lambda:{'ram_available_mb':32000,'desktop':True,'cpu_percent':0,'battery_low':False}
    try:
        actions.start();engine=Engine(actions.submit,lambda *_:None);engine.activate()
        for raw in ['Jarvis, create file deadline by 23:59','queue these two requests: create file batched1; create file batched2']:
            engine.feed(command_text(raw),final=True,raw=raw)
        actions.queue.join()
        rows=actions.ingress.store.rows()
        assert (actions.root/'deadline.txt').is_file()
        assert (actions.root/'batched1.txt').is_file() and (actions.root/'batched2.txt').is_file()
        deadline=next(r for r in rows if r['command']['kind']=='create' and r['command']['value']=='deadline.txt')
        assert deadline['spec']['deadline'] is not None
        assert sum(r['state']=='COMPLETED' for r in rows)==3
    finally:actions.close()


def test_explicit_queue_task_does_not_answer_pending_whatsapp_free_text(tmp_path):
    from jarvis.actions import Actions
    from jarvis.engine import Engine
    from jarvis.whatsapp import Prompt
    actions=Actions({'files_root':'files','apps':{},'task_queue':{'enabled':True}},tmp_path,lambda *_:None)
    actions.ingress.scheduler.observe=lambda:{'ram_available_mb':32000,'desktop':True,'cpu_percent':0,'battery_low':False}
    actions.execute=lambda *_:'Synthetic independent task result'
    actions._route_unparsed=lambda text,generation=None:actions.submit(Command('task',text),expected_generation=generation)
    prompt=Prompt('Which contact?',[],kind='text',free_text=True)
    actions.whatsapp_prompts=[prompt]
    try:
        actions.start();engine=Engine(actions.submit,lambda *_:None);engine.activate();engine.free_text=lambda:True
        engine.feed('add this to the queue: analyze the public fixture',final=True)
        actions.queue.join()
        assert not prompt.ready.is_set()
        assert any(r['state']=='COMPLETED' and 'analyze' in r['command']['value'] for r in actions.ingress.store.rows())
        engine.feed('Fixture Contact',final=True)
        assert prompt.ready.is_set() and prompt.answer=='Fixture Contact'
    finally:actions.close()
