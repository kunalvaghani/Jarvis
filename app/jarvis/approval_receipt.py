"""Identity of an exact approval request (Prompt 31, P31-001).

An approval card records this digest when it is approved; every requester recomputes it for the
request it sent and acts only if the two match, so an approval can never authorize another request.
"""
import hashlib


def approval_digest(kind, detail):
    return hashlib.sha256((str(kind) + '\0' + str(detail)).encode('utf-8', 'replace')).hexdigest()
