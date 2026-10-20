"""Independent final-requester checks with synthetic event delivery only.

No real UI input or external action. A saved host-issued receipt is delivered
at the response seam of a later request; the later card is never approved.
"""
from types import SimpleNamespace

import pytest

from jarvis.island_desk import Approval


@pytest.mark.parametrize('requester', ['application', 'learned_ability'])
def test_prior_receipt_cannot_approve_new_request_with_identical_display_text(requester):
    import main
    from jarvis.repo_abilities import AbilityForge

    saved = {}
    cards = []
    simulated_effects = []

    def report(kind, payload):
        assert kind == 'approval'
        card = Approval(payload)
        cards.append(card)
        if len(cards) == 1:
            # The first request genuinely receives one approved decision.
            assert card.decide(True)
            saved.update(card.answer)
        else:
            # Replay the old response; no decision occurs for the new card.
            assert card.token != saved['token']
            assert card.request != cards[0].request  # new requester-owned ID replaces the old equal-digest setup
            assert card.digest != saved['digest']
            card.answer.update(saved)
            card.ready.set()

    if requester == 'application':
        app = SimpleNamespace(report=report)
        request = lambda: main.App.request_approval(app, 'fixture', 'identical display scope', lambda: False)
    else:
        forge = AbilityForge.__new__(AbilityForge)
        forge.decider = None
        forge.actions = SimpleNamespace(report=report, approval_handler=object(), approvals_waiting=0)
        forge.approval_text = lambda row: 'identical display scope'
        request = lambda: forge.ask({}, lambda: False)

    first = request()
    if first:
        simulated_effects.append('first')
    second = request()
    if second:
        simulated_effects.append('second')
    assert first is True and cards[0].done
    assert cards[1].done is False, 'new card must have received no user decision'
    assert second is False, f'{requester} accepted an old token for a new card'
    assert simulated_effects == ['first']


def test_cancelled_request_still_rejects_genuine_receipt():
    import main
    stopped = [False]
    def report(kind, payload):
        assert Approval(payload).decide(True)
        stopped[0] = True
    app = SimpleNamespace(report=report)
    assert main.App.request_approval(app, 'fixture', 'one scope', lambda: stopped[0]) is False


def test_expired_card_cannot_issue_a_new_approval_receipt():
    import threading
    answer = {}
    card = Approval(('fixture', 'scope', answer, threading.Event(), lambda: False), now=10)
    assert card.decide(True, now=191) is False
    assert answer == {'approved': False}


def test_ui_rejects_old_token_even_when_new_card_has_identical_text():
    from tests.test_prompt31_approval_binding import desk_with_cards
    import threading
    desk, answers = desk_with_cards()
    first = desk.approvals[0]
    second_answer = {}
    second = Approval((first.kind, first.detail, second_answer, threading.Event(), lambda: False))
    desk.approvals = [first, second]
    assert desk.decide(True, first.token) is True
    assert desk.decide(True, first.token) is False
    assert second_answer == {} and not second.done
