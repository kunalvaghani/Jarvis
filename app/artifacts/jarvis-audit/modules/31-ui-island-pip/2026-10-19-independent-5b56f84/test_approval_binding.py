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


