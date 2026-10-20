"""Synthetic UI callbacks; no desktop input or external action is performed."""
import threading
from types import SimpleNamespace
from unittest.mock import Mock

from jarvis.island_desk import Approval, IslandDesk


def desk_with_cards():
    desk = IslandDesk.__new__(IslandDesk)
    desk.app = SimpleNamespace(actions=SimpleNamespace(root='fixture'))
    desk.approval_title = Mock()
    desk.approval_text = Mock()
    desk.approve_button = Mock()
    desk.deny_button = Mock()
    desk.show = Mock()
    desk._write = Mock()
    answers = [{}, {}]
    desk.approvals = [Approval(('fixture', label, answer, threading.Event(), lambda: False))
                      for label, answer in zip(('first', 'second'), answers)]
    desk.render_approval()
    return desk, answers


def test_stale_approve_callback_cannot_authorize_next_card():
    desk, answers = desk_with_cards()
    first_callback = (desk.approve_button.configure.call_args.kwargs.get('command') if desk.approve_button.configure.call_args else None)
    # Use the legacy callback when reproducing against the pinned baseline.
    if first_callback is None:
        first_callback = lambda: desk.decide(True)
    first_callback()
    assert answers[0]['approved'] is True
    first_callback()
    assert answers[1] == {}, 'stale callback authorized a different request'
    assert len(desk.approvals) == 1


def test_callback_for_expired_removed_card_cannot_decide_successor():
    desk, answers = desk_with_cards()
    old_callback = (desk.approve_button.configure.call_args.kwargs.get('command') if desk.approve_button.configure.call_args else None)
    if old_callback is None:
        old_callback = lambda: desk.decide(True)
    desk.approvals.pop(0).lapse()
    desk.render_approval()
    old_callback()
    assert answers[0]['approved'] is False
    assert answers[1] == {}


def test_unbound_decision_is_rejected():
    desk, answers = desk_with_cards()
    desk.decide(True)
    assert answers == [{}, {}]


def test_current_approval_and_close_denial_positive_control():
    desk, answers = desk_with_cards()
    callback = (desk.approve_button.configure.call_args.kwargs.get('command') if desk.approve_button.configure.call_args else None)
    if callback is None:
        callback = lambda: desk.decide(True)
    callback()
    desk.view = 'Approval'
    desk.cancel_approvals()
    assert answers[0]['approved'] is True
    assert answers[1]['approved'] is False




# ---- Claude repair verification (added below Codex's unchanged reproduction) ---------------------------------------
def test_deny_callback_is_bound_to_its_card_too():
    desk, answers = desk_with_cards()
    deny_first = desk.deny_button.configure.call_args.kwargs['command']
    deny_first()
    assert answers[0]['approved'] is False
    deny_first()  # stale deny must not touch the next card either
    assert answers[1] == {} and len(desk.approvals) == 1


def test_tokens_and_digests_identify_each_exact_request():
    desk, answers = desk_with_cards()
    first, second = desk.approvals
    assert first.token != second.token and len(first.token) == 32
    assert first.digest != second.digest  # different detail text, different request identity
    assert desk.decide(True, second.token) is False and answers == [{}, {}]  # not the displayed card
    assert desk.decide(True, first.token) is True
    assert answers[0]['token'] == first.token and answers[0]['digest'] == first.digest


def test_voice_decision_binds_to_the_card_on_screen_when_heard():
    import main
    desk, answers = desk_with_cards()
    scheduled = []
    app = SimpleNamespace(desk=desk, root=SimpleNamespace(after=lambda delay, fn: scheduled.append(fn)))
    main.App.voice_decision(app, True)  # heard while card "first" is displayed
    desk.approvals.pop(0).lapse()      # card "first" expires before the UI applies the answer
    desk.render_approval()
    scheduled[0]()
    assert answers[0]['approved'] is False and answers[1] == {}  # "yes" never reaches the second card
    main.App.voice_decision(app, True)
    scheduled[1]()
    assert answers[1]['approved'] is True


def test_request_approval_requires_a_receipt_for_its_own_exact_request():
    import main
    from jarvis.island_desk import Approval
    def run(forge):
        reports = []
        def report(kind, payload):
            reports.append(payload)
            kind_, detail, answer, ready, cancelled = payload
            card = Approval(payload)
            if forge == 'other':
                Approval(('send', 'a different message', answer, ready, cancelled)).decide(True)
            elif forge == 'bare':
                answer['approved'] = True
                ready.set()
            else:
                card.decide(True)
        app = SimpleNamespace(report=report)
        return main.App.request_approval(app, 'send', 'message one', lambda: False)
    assert run('own') is True
    assert run('other') is False  # an approval issued for another request does not authorize this one
    assert run('bare') is False   # a bare approved flag without the request receipt is refused


def test_concurrent_stale_clicks_never_reach_another_card():
    from concurrent.futures import ThreadPoolExecutor
    desk, answers = desk_with_cards()
    first = desk.approve_button.configure.call_args.kwargs['command']
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: first(), range(16)))
    assert results.count(True) == 1 and answers[0]['approved'] is True and answers[1] == {}
