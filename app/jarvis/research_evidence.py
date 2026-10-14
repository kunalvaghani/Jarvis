"""DeerFlow-style source receipts; citation resolution is not answer correctness."""
import hashlib
import json

from ._vendor.deerflow_contracts import parse_citations, receipt_id


def receipts(observations):
    rows = []
    for item in observations:
        if item.get('action') == 'runtime_feedback':
            continue
        rows.append({'id': receipt_id(len(rows) + 1), 'action': item.get('action'),
            'value': item.get('value'), 'ok': item.get('ok') is True,
            'output_sha256': hashlib.sha256(str(item.get('result', '')).encode('utf-8')).hexdigest()})
    return rows


def assess(answer, observations):
    ledger = {row['id']: row for row in receipts(observations)}
    cites = parse_citations(answer)
    problems = []
    for rid, anchor in cites:
        row = ledger.get(rid)
        if row is None or not row['ok'] or (anchor and anchor != row['action']):
            problems.append(rid)
    return {'status': 'invalid' if problems else 'resolved' if cites else 'uncited',
            'citations': len(cites), 'invalid_ids': sorted(set(problems)),
            'scope': 'Source-call citation check only; does not grade factual correctness.'}
