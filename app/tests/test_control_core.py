import json
import threading
import time

import pytest

from jarvis.control.audit import AuditLog, fingerprint, scrub
from jarvis.control.batch import HALT_TEXT, run_batch
from jarvis.control.coords import Frame, Point
from jarvis.control.executor import Health, RouteExecutor
from jarvis.control.locks import LockManager
from jarvis.control.policy import ApprovalGate
from jarvis.control.recovery import Decision, LoopDetector, RecoveryController
from jarvis.control.refs import RefRegistry, stale_message
from jarvis.control.router import Intent, RouteStats, Router
from jarvis.control.timing import StageTimer
from jarvis.control.types import (Action, ActionResult, CancelToken, ControlError, ErrorCategory, Expectation,
                                  Observation, Ref, Risk, Route, ToolContract)
from jarvis.control.verify import Verifier, default_verifier

ALL = {route: True for route in Route}


def act(name='left_click', risk=Risk.REVERSIBLE, **kw):
    return Action(name, 'goal', kw.pop('route', Route.BROWSER), risk=risk, **kw)


def ok(action, verified=True):
    return ActionResult(action.action_id, True, action.route, executed=True, verified=verified)


# types -------------------------------------------------------------------
def test_action_validation_and_route_change():
    for bad in (dict(name=''), dict(timeout_s=0), dict(max_retries=4)):
        with pytest.raises(ControlError):
            act(**{'name': 'x', **bad})
    with pytest.raises(ControlError, match='never retried'):
        act(risk=Risk.CONSEQUENTIAL, idempotent=True)
    a = act(target=Ref('ref_1', Route.BROWSER, 'tab', 0))
    moved = a.with_route(Route.VISION)
    assert moved.route is Route.VISION and moved.target is None and moved.action_id == a.action_id
    assert Observation(Route.UIA, 'w').untrusted is True
    failure = ActionResult.failure(a, ControlError('x', ErrorCategory.TIMEOUT, executed=True))
    assert not failure.ok and failure.executed and failure.error_category is ErrorCategory.TIMEOUT
    contract = ToolContract('t', 'd', Route.API, Risk.READ, {}, {}, (ErrorCategory.TIMEOUT,), 1.0)
    assert contract.permission == 'none'


def test_cancel_tokens_propagate_from_parent():
    parent = CancelToken()
    child = parent.child()
    child.raise_if_cancelled()
    parent.cancel('stop')
    assert child.cancelled
    with pytest.raises(ControlError, match='stop') as raised:
        child.raise_if_cancelled()
    assert raised.value.category is ErrorCategory.CANCELLED


# refs --------------------------------------------------------------------
def test_refs_are_stable_until_navigation_and_never_reused():
    reg = RefRegistry(Route.BROWSER)
    first = reg.assign('tab-1', 'node-a')
    assert reg.assign('tab-1', 'node-a') == first and first.id == 'ref_1'
    second = reg.assign('tab-1', 'node-b')
    assert reg.resolve(second) == 'node-b' and reg.lookup('tab-1', 'ref_2') == second
    assert reg.generation('tab-1') == 0 and reg.generation('nope') is None
    reg.invalidate('tab-1')
    for stale in (first, second):
        with pytest.raises(ControlError, match='stale or not found') as raised:
            reg.resolve(stale)
        assert raised.value.category is ErrorCategory.STALE_REF
    again = reg.assign('tab-1', 'node-a')
    assert again.id == 'ref_3' and again.generation == 1  # numbering never restarts
    with pytest.raises(ControlError):
        reg.lookup('tab-1', 'ref_1')
    with pytest.raises(ControlError):
        reg.lookup('tab-9', 'ref_1')
    with pytest.raises(ControlError):
        reg.resolve(Ref('ref_3', Route.UIA, 'tab-1', 1))
    assert stale_message('ref_7') == 'ref_7 is stale or not found. Re-read the page to get fresh references.'


def test_material_change_drops_only_vanished_nodes():
    reg = RefRegistry(Route.UIA, prefix='u')
    a, b = reg.assign('w', 1), reg.assign('w', 2)
    assert reg.retain('w', [2]) == ('u1',)
    assert reg.resolve(b) == 2
    with pytest.raises(ControlError):
        reg.resolve(a)
    assert reg.retain('missing', []) == ()
    reg.drop('w')
    with pytest.raises(ControlError):
        reg.resolve(b)


# batch -------------------------------------------------------------------
def test_batch_halts_at_first_failure_with_exact_text():
    actions = [act(), act(), act(), act()]
    calls = []

    def execute(a):
        calls.append(a.action_id)
        if a is actions[1]:
            raise ControlError('not found', ErrorCategory.TARGET_NOT_FOUND)
        return ok(a)

    results = run_batch(actions, execute, ApprovalGate())
    assert calls == [actions[0].action_id, actions[1].action_id]
    assert [r.ok for r in results] == [True, False, False, False]
    assert all(r.text == HALT_TEXT and r.error_category is ErrorCategory.NOT_EXECUTED for r in results[2:])


def test_batch_asks_before_each_consequential_action_and_blocks_after_unverified():
    asked = []
    gate = ApprovalGate(lambda a: asked.append(a.name) or True)
    send1, send2 = act('send', Risk.CONSEQUENTIAL), act('submit', Risk.CONSEQUENTIAL)
    results = run_batch([act(), send1, send2], ok, gate)
    assert asked == ['send', 'submit'] and all(r.ok for r in results)

    unverified = run_batch([act(), act('send', Risk.CONSEQUENTIAL)], lambda a: ok(a, verified=False), gate)
    assert unverified[1].error_category is ErrorCategory.VERIFICATION_FAILED and asked == ['send', 'submit']

    denied = run_batch([act('send', Risk.CONSEQUENTIAL), act()], ok, ApprovalGate(lambda a: False))
    assert denied[0].error_category is ErrorCategory.APPROVAL_DENIED and denied[1].text == HALT_TEXT


def test_batch_treats_executor_bugs_as_uncertain_and_honours_cancel():
    a = act()
    result = run_batch([a], lambda _a: 1 / 0, ApprovalGate())[0]
    assert result.error_category is ErrorCategory.UNCERTAIN and result.executed
    cancelled = act()
    cancelled.cancel.cancel('user')
    assert run_batch([cancelled], ok, ApprovalGate())[0].error_category is ErrorCategory.CANCELLED


# verify ------------------------------------------------------------------
def test_builtin_verifiers(tmp_path):
    state = {'url': 'https://docs.python.org/3/library/venv.html', 'value': 'hello', 'signature': 'b'}

    def probe(what, **params):
        return state['url'] if what == 'url' else state['value'] if what == 'value' else (
            state.get(params.get('key')) if what == 'state' else state[what])

    f = tmp_path / 'notes.txt'
    f.write_text('venv summary https://docs.python.org', encoding='utf-8')
    import hashlib
    cases = [('url_equals', {'url': state['url']}, True), ('url_matches', {'pattern': r'python\.org'}, True),
             ('url_matches', {'pattern': 'example'}, False), ('value_equals', {'expected': 'hello'}, True),
             ('state_equals', {'key': 'value', 'expected': 'hello'}, True), ('changed', {'before': 'a'}, True),
             ('probe_equals', {'what': 'value', 'expected': 'hello'}, True),
             ('probe_equals', {'what': 'state', 'args': {'key': 'url'}, 'expected': 'nope'}, False),
             ('changed', {'before': 'b'}, False), ('file_exists', {'path': f}, True),
             ('file_exists', {'path': tmp_path, 'kind': 'dir'}, True), ('file_exists', {'path': tmp_path / 'x'}, False),
             ('file_contains', {'path': f, 'text': 'venv'}, True), ('file_contains', {'path': f, 'text': 'venv', 'exact': True}, False),
             ('file_contains', {'path': tmp_path / 'x', 'text': 'a'}, False),
             ('file_sha256', {'path': f, 'sha256': hashlib.sha256(f.read_bytes()).hexdigest()}, True),
             ('file_sha256', {'path': tmp_path / 'x', 'sha256': ''}, False)]
    for kind, params, expected in cases:
        assert default_verifier.check(Expectation(kind, params), probe)[0] is expected, kind


def test_verifier_errors_and_wait():
    v = Verifier()
    with pytest.raises(ControlError) as raised:
        v.check(Expectation('nope'), lambda *a, **k: None)
    assert raised.value.category is ErrorCategory.UNSUPPORTED
    with pytest.raises(ControlError) as raised:
        default_verifier.check(Expectation('url_equals', {}), lambda *a, **k: 'u')
    assert raised.value.category is ErrorCategory.INVALID_ARGUMENTS
    assert default_verifier.check(Expectation('url_equals', {'url': 'u'}), lambda *a, **k: 1 / 0) == (
        False, 'verification read failed: ZeroDivisionError')
    v.register('boom', lambda p, probe: (_ for _ in ()).throw(ControlError('x', ErrorCategory.FOCUS_LOST)))
    with pytest.raises(ControlError):
        v.check(Expectation('boom'), lambda *a, **k: None)

    values = iter(['a', 'a', 'b'])
    now = [0.0]
    okay, _ = default_verifier.wait(Expectation('changed', {'before': 'a'}), lambda w: next(values), 1.0,
                                    clock=lambda: now[0], sleep=lambda s: now.__setitem__(0, now[0] + s))
    assert okay
    events = []
    okay, _ = default_verifier.wait(Expectation('changed', {'before': 'a'}), lambda w: 'a', .2,
                                    clock=lambda: now[0], event=lambda t: (events.append(t), now.__setitem__(0, now[0] + t)))
    assert not okay and events
    token = CancelToken()
    token.cancel('stop')
    with pytest.raises(ControlError):
        default_verifier.wait(Expectation('changed', {'before': 'a'}), lambda w: 'a', 1.0, cancel=token)


# router ------------------------------------------------------------------
def test_router_reference_examples():
    router = Router(ALL)
    assert router.select(Intent('web', 'chrome')) is Route.BROWSER                     # open YouTube
    assert router.select(Intent('native', 'notepad', uia_usable=True)) is Route.UIA    # Notepad
    assert router.select(Intent('canvas', 'paint', uia_usable=False)) is Route.VISION  # canvas icon
    assert router.select(Intent('service', 'gmail', has_api=True)) is Route.API        # API access
    assert router.candidates(Intent('native', 'notepad')) == (Route.UIA, Route.VISION)
    assert router.candidates(Intent('file', has_api=True)) == (Route.API,)
    assert router.next_route(Intent('native', 'n'), [Route.UIA]) is Route.VISION
    assert router.next_route(Intent('native', 'n'), [Route.UIA, Route.VISION]) is None
    with pytest.raises(ControlError):
        Intent('teleport')
    with pytest.raises(ControlError):
        Router({}).select(Intent('web'))


def test_router_uses_measured_success_but_never_leads_with_vision():
    stats = RouteStats()
    for _ in range(20):
        stats.record(Route.API, 'excel', False, 50)
        stats.record(Route.UIA, 'excel', True, 120)
        stats.record(Route.VISION, 'excel', True, 900)
    router = Router(ALL, stats)
    intent = Intent('native', 'excel', has_api=True, uia_usable=True)
    assert router.candidates(intent) == (Route.UIA, Route.API, Route.VISION)
    assert stats.latency(Route.UIA, 'excel') == 120 and stats.latency(Route.UIA, 'x') is None
    router.set_available(Route.UIA, False)
    assert router.select(intent) is Route.API
    private = Router(ALL, vision_allows_private=False)
    assert Route.VISION not in private.candidates(Intent('native', contains_private=True))


def test_route_stats_persist(tmp_path):
    stats = RouteStats()
    stats.record(Route.BROWSER, 'Chrome', True, 300)
    path = tmp_path / 'stats.json'
    stats.save(path)
    loaded = RouteStats.load(path)
    assert loaded.success(Route.BROWSER, 'chrome') == pytest.approx(2 / 3)
    assert RouteStats.load(tmp_path / 'missing.json').counts == {}
    path.write_text(json.dumps([{'route': 'warp'}, 5]), encoding='utf-8')
    assert RouteStats.load(path).counts == {}


def test_router_cache_is_bounded():
    router = Router(ALL)
    for i in range(600):
        router.candidates(Intent('web', f'app{i}'))
    assert len(router._cache) <= 513


def test_routing_decision_is_sub_millisecond():
    router = Router(ALL)
    intent = Intent('native', 'notepad', uia_usable=True)
    router.select(intent)
    started = time.perf_counter()
    for _ in range(1000):
        router.select(intent)
    assert (time.perf_counter() - started) / 1000 < .001


# recovery ----------------------------------------------------------------
def failed(action, category, executed=False):
    return ActionResult(action.action_id, False, action.route, executed=executed, error_category=category)


def test_recovery_order_for_unexecuted_failures():
    rc = RecoveryController(max_attempts=2)
    a = act(expectation=Expectation('changed', {'before': 'x'}))
    assert rc.decide(a, ok(a), 1).decision is Decision.DONE
    assert rc.decide(a, failed(a, ErrorCategory.STALE_REF), 1).decision is Decision.REFRESH_REFS
    assert rc.decide(a, failed(a, ErrorCategory.FOCUS_LOST), 1).decision is Decision.REOBSERVE
    assert rc.decide(a, failed(a, ErrorCategory.TIMEOUT), 2, alternatives=True).decision is Decision.SWITCH_ROUTE
    assert rc.decide(a, failed(a, ErrorCategory.UNSUPPORTED), 1).decision is Decision.ESCALATE_MODEL
    assert rc.decide(a, failed(a, ErrorCategory.UNSUPPORTED), 1).decision is Decision.ASK_USER
    for category, decision in ((ErrorCategory.CANCELLED, Decision.STOP), (ErrorCategory.POLICY_DENIED, Decision.STOP),
                               (ErrorCategory.ELEVATED_TARGET, Decision.ASK_USER)):
        assert rc.decide(a, failed(a, category), 1).decision is decision
    assert rc.decide(act(), ok(act(), verified=False), 1).decision is Decision.DONE


def test_recovery_never_repeats_uncertain_input_blindly():
    rc = RecoveryController()
    send = act('send', Risk.CONSEQUENTIAL)
    uncertain = failed(send, ErrorCategory.UNCERTAIN, executed=True)
    assert rc.decide(send, uncertain, 1).decision is Decision.ASK_USER
    assert rc.decide(send, uncertain, 1, already_happened=False).decision is Decision.ASK_USER
    assert rc.decide(send, uncertain, 1, already_happened=True).decision is Decision.DONE
    click = act()
    assert rc.decide(click, failed(click, ErrorCategory.TIMEOUT, True), 1).decision is Decision.ASK_USER
    safe = act(idempotent=True, max_retries=1)
    assert rc.decide(safe, failed(safe, ErrorCategory.VERIFICATION_FAILED, True), 1).decision is Decision.REOBSERVE
    assert rc.decide(safe, failed(safe, ErrorCategory.VERIFICATION_FAILED, True), 2,
                     alternatives=True).decision is Decision.SWITCH_ROUTE


def test_loop_detection():
    rc = RecoveryController(loop_limit=2)
    a = act()
    result = failed(a, ErrorCategory.TARGET_NOT_FOUND)
    assert rc.decide(a, result, 1, state_signature='s').decision is Decision.REOBSERVE
    assert rc.decide(a, result, 1, state_signature='s').decision is Decision.REOBSERVE
    assert rc.decide(a, result, 1, state_signature='s').decision is Decision.STOP
    assert LoopDetector(0).record('x')


# locks -------------------------------------------------------------------
def test_locks_are_exclusive_reentrant_and_time_out():
    locks = LockManager()
    with locks.foreground_input('task-a'):
        assert locks.owner('input', 'foreground') == 'task-a'
        locks.acquire('input', 'foreground', 'task-a')  # same owner re-enters
        with pytest.raises(ControlError) as raised:
            locks.acquire('input', 'foreground', 'task-b', timeout_s=.05)
        assert raised.value.category is ErrorCategory.TIMEOUT
    assert locks.owner('input', 'foreground') is None
    locks.release('tab', 'nope', 'x')
    token = CancelToken()
    token.cancel()
    locks.acquire('tab', '1', 'a')
    with pytest.raises(ControlError, match='Cancelled'):
        locks.acquire('tab', '1', 'b', cancel=token)


def test_waiter_gets_lock_after_release():
    locks = LockManager()
    locks.acquire('window', '42', 'a')
    got = []
    t = threading.Thread(target=lambda: (locks.acquire('window', '42', 'b', 2), got.append(True)))
    t.start()
    time.sleep(.05)
    locks.release('window', '42', 'a')
    t.join(2)
    assert got == [True] and locks.owner('window', '42') == 'b'


def test_emergency_stop_cancels_running_actions_and_blocks_new_ones():
    locks = LockManager()
    running = locks.track(CancelToken())
    assert locks.emergency_stop('stop interacting with my screen') == 1
    assert running.cancelled and 'stop interacting' in running.reason
    with pytest.raises(ControlError, match='Emergency stop') as raised:
        locks.acquire('input', 'foreground', 'task')
    assert raised.value.category is ErrorCategory.CANCELLED
    late = locks.track(CancelToken())
    assert late.cancelled
    locks.reset()
    locks.acquire('input', 'foreground', 'task')
    assert not locks.track(CancelToken()).cancelled


# audit / timing -----------------------------------------------------------
def test_audit_never_writes_typed_text_or_secrets(tmp_path):
    seen = []
    log = AuditLog(tmp_path / 'audit.jsonl', sink=seen.append)
    a = act('type', params={'text': 'my secret diary', 'url': 'https://x.test/?token=abcdefgh123', 'repeat': 2,
                            'paths': ['C:/a'], 'nested': {'a': 1}})
    record = log.action(a, ActionResult(a.action_id, True, a.route, executed=True, verified=True,
                                        evidence='api_key=sk-0123456789abcdefghij', timings_ms={'total': 1.0}))
    text = (tmp_path / 'audit.jsonl').read_text(encoding='utf-8')
    assert 'secret diary' not in text and 'abcdefgh123' not in text and 'sk-0123456789' not in text
    assert record['params']['text']['len'] == 15 and record['params']['repeat'] == 2 and seen == [record]
    assert scrub({'flag': True, 'none': None}) == {'flag': True, 'none': None}
    assert fingerprint({'a': 1})['len'] == 8
    broken = AuditLog(tmp_path / 'b.jsonl', sink=lambda r: 1 / 0)
    broken.write('x')  # a failing sink never fails the write


def test_stage_timer():
    now = [0.0]
    timer = StageTimer(clock=lambda: now[0])
    with timer.stage('capture'):
        now[0] += .010
    with timer.stage('capture'):
        now[0] += .005
    timer.add('verify', 2)
    result = timer.result()
    assert result['capture'] == pytest.approx(15) and result['verify'] == 2 and result['total'] == pytest.approx(15)
    for bad in (lambda: timer.add('total', 1), lambda: timer.add('verify', -1)):
        with pytest.raises(ValueError):
            bad()
    with pytest.raises(ValueError):
        with timer.stage('nap'):
            pass


# executor ------------------------------------------------------------------
class EchoExecutor(RouteExecutor):
    route = Route.API

    def observe(self, scope=None, **options):
        return Observation(self.route, scope or 'api')

    def act(self, action):
        return ok(action)

    def probe(self, what, **params):
        return 'u' if what == 'url' else None

    def cancel(self):
        pass

    def health_check(self):
        return Health(True)

    def close(self):
        pass


def test_executor_default_verify_uses_probe():
    ex = EchoExecutor()
    assert ex.verify(Expectation('url_equals', {'url': 'u'}))[0]
    assert ex.health_check().ok and ex.observe().scope == 'api' and ex.act(act()).ok
    ex.cancel()
    ex.close()
    assert Point(1, 2, Frame.CROP).frame is Frame.CROP


def test_cancel_token_follows_the_host_stop_signal():
    from jarvis.control.types import CancelToken
    stop = {'now': False}
    token = CancelToken(signal=lambda: stop['now'])
    assert not token.cancelled
    stop['now'] = True
    assert token.cancelled and token.reason == 'stopped by the user'
    broken = CancelToken(signal=lambda: 1 / 0)
    assert broken.cancelled and broken.reason == 'cancel check failed'  # Unreadable stop counts as stop.
