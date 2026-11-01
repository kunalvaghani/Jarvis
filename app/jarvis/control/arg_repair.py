"""Repair one unambiguous planner mistake in `app_act` arguments (flag control.arg_repair, default off).

Live S2 (2026-10-31), 6 runs out of 6 across two gates: the planner put the arguments where the operation name goes,
`app_act` value `{"content": {"text": "1234*56-789="}}` with no content. app_act refused it (nothing was sent)
and the recovery that followed went wrong in 3 of 6 runs (one typed only "1").

Only that shape is repaired: a JSON object whose sole field is text (directly or under "content") becomes
`type` with that text, which is what the planner's own read-back then checks. Anything else, a ref, an
operation name, other fields, is left unchanged so app_act refuses it as before. Typing is an ordinary input
step; it does not send, submit or save anything by itself.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Mapping


def repaired(step: Mapping[str, Any]) -> Dict[str, Any]:
    value = str(step.get('value', '')).strip()
    if not value.startswith('{') or str(step.get('content', '') or '').strip():
        return dict(step)
    try:
        data = json.loads(value)
    except (ValueError, RecursionError):
        return dict(step)
    if isinstance(data, dict) and set(data) == {'content'} and isinstance(data['content'], dict):
        data = data['content']
    if not isinstance(data, dict) or set(data) != {'text'} or not isinstance(data['text'], str) or not data['text']:
        return dict(step)
    return {**step, 'value': 'type', 'content': json.dumps({'text': data['text']}, ensure_ascii=False)}
