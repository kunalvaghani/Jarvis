"""Independent final-requester checks with synthetic event delivery only (Codex, ddf3247; one setup line adapted, see below).

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
            # Adapted from Codex's ddf3247 test: its setup asserted equal digests, which held only in the
            # vulnerable design. With the per-request id the digests must differ; the replay below and every
            # security assertion are unchanged.
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


# ---- Claude P31-002 repair verification (added below Codex's tests) --------------------------------------------------
def _requester(kind_of, decide):
    """Run one request through the real requester; decide(card, answer) plays the UI/attacker role."""
    import main
    from jarvis.repo_abilities import AbilityForge
    cards = []
    def report(kind, payload):
        card = Approval(payload)
        cards.append(card)
        decide(card, card.answer)
    if kind_of == 'application':
        app = SimpleNamespace(report=report)
        return (lambda: main.App.request_approval(app, 'fixture', 'identical display scope', lambda: False)), cards
    forge = AbilityForge.__new__(AbilityForge)
    forge.decider = None
    forge.actions = SimpleNamespace(report=report, approval_handler=object(), approvals_waiting=0)
    forge.approval_text = lambda row: 'identical display scope'
    return (lambda: forge.ask({}, lambda: False)), cards


@pytest.mark.parametrize('requester', ['application', 'learned_ability'])
def test_genuine_repeated_identical_requests_each_need_and_accept_their_own_decision(requester):
    request, cards = _requester(requester, lambda card, answer: card.decide(True))
    assert request() is True and request() is True
    assert len(cards) == 2 and cards[0].request != cards[1].request and all(card.done for card in cards)


@pytest.mark.parametrize('requester', ['application', 'learned_ability'])
@pytest.mark.parametrize('forge', ['missing_digest', 'wrong_request_digest', 'swapped_request_id', 'other_kind'])
def test_forged_missing_or_wrong_receipts_are_refused(requester, forge):
    from jarvis.approval_receipt import approval_digest
    import threading
    def decide(card, answer):
        if forge == 'missing_digest':
            answer['approved'] = True
        elif forge == 'wrong_request_digest':
            answer.update(approved=True, digest=approval_digest(card.kind, card.detail, 'f' * 32))
        elif forge == 'swapped_request_id':
            answer['request'] = 'e' * 32  # the requester keeps its own id; editing the answer changes nothing
            answer.update(approved=True, digest=approval_digest(card.kind, card.detail, 'e' * 32))
        else:
            other = Approval(('other_kind', card.detail, {'request': card.request}, threading.Event(), lambda: False))
            other.decide(True)
            answer.update(other.answer)
        answer['approved'] = True
        card.ready.set()
    request, _ = _requester(requester, decide)
    assert request() is False


def test_delayed_receipt_after_the_requesters_own_lifetime_is_refused():
    import threading
    from jarvis.approval_receipt import APPROVAL_TTL, new_request_id, receipt_valid
    request = new_request_id()
    answer = {'request': request}
    card = Approval(('fixture', 'scope', answer, threading.Event(), lambda: False), now=100)
    assert card.decide(True, now=101)
    assert receipt_valid(answer, 'fixture', 'scope', request, issued=100, now=102) is True
    assert receipt_valid(answer, 'fixture', 'scope', request, issued=100, now=100 + APPROVAL_TTL) is False
    assert receipt_valid(answer, 'fixture', 'scope', request, issued=100, now=99) is False  # clock went backwards
    assert receipt_valid(answer, 'fixture', 'scope', request, issued=100, now=102, cancelled=lambda: True) is False
    assert receipt_valid(answer, 'fixture', 'scope', '', issued=100, now=102) is False


def test_card_reads_the_request_id_once_at_creation():
    import threading
    answer = {'request': 'a' * 32}
    card = Approval(('fixture', 'scope', answer, threading.Event(), lambda: False))
    answer['request'] = 'b' * 32  # a later edit cannot re-target the card
    assert card.decide(True) and card.request == 'a' * 32
    from jarvis.approval_receipt import approval_digest
    assert answer['digest'] == approval_digest('fixture', 'scope', 'a' * 32)


def test_denied_and_lapsed_cards_issue_no_receipt():
    import threading
    for action in ('deny', 'lapse'):
        answer = {'request': 'c' * 32}
        card = Approval(('fixture', 'scope', answer, threading.Event(), lambda: False))
        card.decide(False) if action == 'deny' else card.lapse()
        assert answer.get('approved') is False and 'digest' not in answer
