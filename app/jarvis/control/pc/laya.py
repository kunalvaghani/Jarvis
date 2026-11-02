"""Laya on this PC's GPU as the local replacement for JEV's paid decision service (user request 2026-11-02).

JEV (agent-desktop's goal loop) asks a decision model to pick one element out of the whole window. Laya is a
small, fast local decision model (``laya-serve``, the same ``/v1/systemone`` contract as TypeSafe JEV), but it
is weak on long option lists (its own card: 0.43 on 77 labels). Measured live on Calculator (40 elements):
JEV's full-list question abstained on every intent, while a name shortlist of 8 followed by one Laya choice
picked the right button 7 of 8 times at about 0.25 s, the eighth below the confidence bar.

So Jarvis uses Laya the way it is strong: when the planner names a control in words instead of its exact ref
("the Save button"), the window's controls are shortlisted by name with no model, and Laya chooses among at most
eight (or "none"). It acts only at ``MIN_CONFIDENCE`` or above; otherwise it reports the candidates instead of
guessing. Screen text goes only to the loopback server; the key lives in secrets/laya.key.
"""
from __future__ import annotations

import difflib
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlsplit

APP = Path(__file__).resolve().parents[3]
KEY = APP / 'secrets' / 'laya.key'
ENDPOINT = 'http://127.0.0.1:8765/v1/systemone'
SHORTLIST = 8
MIN_CONFIDENCE = 0.9
# JEV 1.13 (TypeSafe's own decision model) through OpenRouter's System One route: same request shape as Laya, but
# in the cloud, reading the whole window (255 options). The user's rule (2026-11-02): Laya always first; JEV only
# as a backup when Laya cannot decide, and only if it is free. On 2026-11-02 OpenRouter priced JEV 1.13 at
# $0.042/M input and listed no free variant, so the backup is off. It needs, in config "control":
#   decision_backup = "jev", decision_backup_free = true (the user confirmed a free price) and
#   decision_cloud_consent = true (each decision sends a text description of the window to OpenRouter/TypeSafe).
JEV_URL = 'https://openrouter.ai/api/v1/systemone'
JEV_MODEL = 'typesafe/jev-1.13'
JEV_KEY = APP / 'secrets' / 'openrouter.key'
JEV_OPTIONS = 254
WORD = re.compile(r'\w+')


def endpoint() -> Optional[str]:
    url = os.environ.get('JARVIS_LAYA_URL', ENDPOINT)
    host = (urlsplit(url).hostname or '').lower()
    return url if host in ('127.0.0.1', 'localhost', '::1') else None  # never send screen text off this PC


def shortlist(intent: str, controls: Dict[str, Tuple[str, str]], k: int = SHORTLIST) -> List[str]:
    """Refs of the k controls whose kind and name best match the words of the intent (no model)."""
    words = set(WORD.findall(intent.lower()))

    def score(ref: str) -> float:
        kind, name = controls[ref]
        text = f'{kind} {name}'.lower()
        return 2 * len(words & set(WORD.findall(text))) + difflib.SequenceMatcher(None, intent.lower(), name.lower()).ratio()
    return sorted(controls, key=score, reverse=True)[:k]


def backup_allowed(config: Optional[Dict[str, object]] = None) -> bool:
    """JEV as Laya's backup: only when the config says it is free AND the user consented to the cloud.
    The environment cannot grant either."""
    section = (config or {}).get('control', {}) if isinstance(config, dict) else {}
    section = section if isinstance(section, dict) else {}
    return (str(section.get('decision_backup', '')).lower() == 'jev' and section.get('decision_backup_free') is True
            and section.get('decision_cloud_consent') is True)


class Resolver:
    def __init__(self, url: Optional[str] = None, key: Optional[str] = None, timeout_s: float = 5.0,
                 model: str = '') -> None:
        self.model = model
        self.url: Optional[str]
        if model == 'jev':
            self.url = url if url is not None else JEV_URL
            key_file = JEV_KEY
        else:
            self.url = url if url is not None else endpoint()
            key_file = KEY
        try:
            self.key = key if key is not None else key_file.read_text(encoding='ascii').strip()
        except OSError:
            self.key = ''
        self.timeout_s = timeout_s

    @classmethod
    def resolve(cls, intent: str, app: str, controls: Dict[str, Tuple[str, str]],
                config: Optional[Dict[str, object]] = None) -> Dict[str, object]:
        """Laya first; JEV only as the allowed backup when Laya found nothing confident."""
        answer = cls().choose(intent, app, controls)
        if answer['ref'] is None and backup_allowed(config):
            backup = cls(model='jev')
            if backup.ready():
                second = backup.choose(intent, app, controls)
                if second['ref'] is not None:
                    return {**second, 'why': 'jev backup'}
        return answer

    def ready(self) -> bool:
        return bool(self.url and self.key)

    def choose(self, intent: str, app: str, controls: Dict[str, Tuple[str, str]]) -> Dict[str, object]:
        """{ref, confidence, candidates}: ref is None when nothing is confident enough."""
        # JEV reads the whole window; Laya is asked only about a short list it can tell apart.
        refs = shortlist(intent, controls, JEV_OPTIONS if self.model == 'jev' else SHORTLIST)
        if not refs or not self.ready():
            return {'ref': None, 'confidence': 0.0, 'candidates': refs, 'why': 'no candidates or no local model'}
        criteria = {f'c{i}': f'{controls[r][0]} "{controls[r][1]}"' for i, r in enumerate(refs)}
        criteria['none'] = 'nothing here matches'
        body: Dict[str, object] = {'state': {'intent': intent[:300], 'app': app[:80]},
                'questions': {'target': {'type': 'choice', 'instructions': 'Which control does the intent refer to?',
                                         'criteria': criteria}}}
        if self.model == 'jev':
            body['model'] = JEV_MODEL
        request = urllib.request.Request(str(self.url), json.dumps(body).encode('utf-8'),
                                         {'content-type': 'application/json', 'Authorization': 'Bearer ' + self.key})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as reply:
                answer = json.loads(reply.read().decode('utf-8'))['answers']['target']
        except (urllib.error.URLError, OSError, ValueError, KeyError) as error:
            return {'ref': None, 'confidence': 0.0, 'candidates': refs, 'why': f'local model unavailable ({type(error).__name__})'}
        choice = str(answer.get('choice', 'none'))
        confidence = float(answer.get('answer_confidence') or answer.get('confidence') or 0.0)
        if choice == 'none' or not choice.startswith('c') or confidence < MIN_CONFIDENCE:
            return {'ref': None, 'confidence': confidence, 'candidates': refs,
                    'why': 'no control matched confidently' if choice != 'none' else 'nothing matched'}
        return {'ref': refs[int(choice[1:])], 'confidence': confidence, 'candidates': refs, 'why': 'laya'}
