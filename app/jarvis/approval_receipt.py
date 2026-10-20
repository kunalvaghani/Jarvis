"""Identity of an exact approval request (Prompt 31: P31-001 callback binding, P31-002 receipt replay).

Protocol, shared by every requester and the island card:
1. The requester creates an unpredictable one-time request id *before* enqueueing the card, keeps its own
   copy and its own issue time, and sends the id inside the answer object.
2. The card reads the id once when it is created and digests kind, detail and id; the digest is written to
   the answer only when that card is approved (cards also refuse decisions after APPROVAL_TTL).
3. The requester accepts only ``receipt_valid``: approved, digest equal to the digest of *its* kind, detail
   and locally held id, within its own TTL, and not cancelled. A receipt from an earlier decision, even for a
   request with identical text, carries another id and is refused; each request is answered once.
"""
import hashlib
import secrets
import time

APPROVAL_TTL = 180.0


def new_request_id():
    return secrets.token_hex(16)


def approval_digest(kind, detail, request=''):
    return hashlib.sha256((str(kind) + '\0' + str(detail) + '\0' + str(request)).encode('utf-8', 'replace')).hexdigest()


def receipt_valid(answer, kind, detail, request, issued, cancelled=lambda: False, now=None):
    """True only for an approval issued for this exact pending request, within its lifetime."""
    now = time.monotonic() if now is None else now
    return (isinstance(answer, dict) and answer.get('approved') is True and bool(request)
            and answer.get('digest') == approval_digest(kind, detail, request)
            and 0 <= now - issued < APPROVAL_TTL and not cancelled())
