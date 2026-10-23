"""Small local voice policies; no inference, external actions or audio retention."""
from dataclasses import asdict, dataclass
import re
import time
import threading

LANGUAGES = {'en': 'English', 'hi': 'Hindi', 'gu': 'Gujarati', 'fr': 'French'}


def repetitive_hypothesis(text):
    """Reject decode loops; ask for repetition rather than infer an action."""
    return bool(re.search(r'([^\W\d_])\1{7,}', text, re.UNICODE)
                or re.search(r'\b(\w+)(?:\W+\1){5,}\b', text, re.UNICODE | re.I))


class ResponseReports:
    """Fence producer events and events already queued on the UI thread."""
    KINDS = {'answer', 'answer_stream', 'spoken_reply', 'answer_error', 'thinking', 'question'}

    def __init__(self, report, generation):
        self.report, self.generation = report, generation
        self.local = threading.local()

    def bind(self, generation, valid=None):
        self.local.generation = generation
        self.local.valid = valid

    def unbind(self):
        self.local.__dict__.pop('generation', None)
        self.local.__dict__.pop('valid', None)

    def accepts(self, kind):
        valid = getattr(self.local, 'valid', None)
        return kind not in self.KINDS or (getattr(self.local, 'generation', self.generation()) == self.generation() and (valid is None or valid()))

    def __call__(self, kind, message=''):
        token = getattr(self.local, 'generation', self.generation())
        valid = getattr(self.local, 'valid', None)
        if kind in self.KINDS:
            guard = lambda: token == self.generation() and (valid is None or valid())
            guard.voice_key = (id(self), token, id(valid)) if valid else (id(self), token)
            if not guard():
                return
            owner = getattr(self.report, '__self__', None)
            scoped = getattr(owner, 'report_scoped', None)
            if scoped is not None:
                scoped(kind, message, guard)
                return
        self.report(kind, message)


@dataclass(frozen=True)
class TranscriptEvent:
    session_id: str
    utterance_id: int
    revision: int
    state: str
    text: str
    stable: str
    replace_from: int
    replacement: str
    timestamp: float
    language: str


class Stabilizer:
    """Two-hypothesis agreement; stable text can still be revised before FINAL."""
    def __init__(self):
        self.utterance = None
        self.previous = ''
        self.revision = 0

    def update(self, session, utterance, text, final=False, language='en'):
        if utterance != self.utterance:
            self.utterance, self.previous, self.revision = utterance, '', 0
        old, new = self.previous.split(), text.split()
        count = 0
        for a, b in zip(old, new):
            if a != b:
                break
            count += 1
        stable = text if final else ' '.join(new[:count])
        common = 0
        for a, b in zip(self.previous, text):
            if a != b:
                break
            common += 1
        self.revision += 1
        event = TranscriptEvent(session, utterance, self.revision,
            'FINAL' if final else ('STABLE' if stable else 'PROVISIONAL'), text,
            stable, common, text[common:], time.monotonic(), language)
        self.previous = text
        return asdict(event)


def endpoint_delay(mode, text='', stable=False, writing=False, base=.8):
    delay = {'fast': .5, 'balanced': base, 'careful': 1.4}[mode]
    unfinished = re.search(r'\b(?:and|then|or|for|to|with|aur|ane|et|pour|uh|um)\W*$', text, re.I)
    if writing or unfinished:
        delay = max(delay, 1.8)
    elif len(text.split()) > 14 or not stable:
        delay = max(delay, 1.1)
    return delay


def detect_language(text, metadata=None, confidence=0., previous='en', threshold=.8):
    # Scripts provide high-confidence evidence; romanization needs multiple markers.
    counts = {'gu': len(re.findall(r'[\u0a80-\u0aff]', text)),
              'hi': len(re.findall(r'[\u0900-\u097f]', text))}
    winner = max(counts, key=counts.get)
    if counts[winner] >= 2:
        return winner
    markers = {
        'hi': r'\b(?:kholo|karo|mujhe|batao|hai|hain|kya|kyun|kaise|aap|yeh|pani|hota|hoti|nahi)\b',
        'gu': r'\b(?:mara|maru|kholo|khol|kar|chhe|tame|mane|ma)\b',
        'fr': r'\b(?:ouvre|cherche|bonjour|merci|navigateur|vidéos|pour|avec|le|la|les|est|votre|vous|une|sont)\b'}
    scores = {lang: len(set(re.findall(pattern, text.lower()))) for lang, pattern in markers.items()}
    candidate = max(scores, key=scores.get)
    if scores[candidate] >= 2 and list(scores.values()).count(scores[candidate]) == 1:
        return candidate
    if metadata in LANGUAGES and isinstance(confidence, (int, float)) and confidence >= threshold:
        return metadata
    return previous


class LanguageTracker:
    """Retain ambiguous context; require consecutive metadata votes to switch."""
    def __init__(self, threshold=.8, confirmations=2):
        self.language = 'en'
        self.threshold, self.confirmations = threshold, confirmations
        self.pending, self.count = None, 0

    def update(self, text, metadata=None, confidence=0.):
        candidate = detect_language(text, metadata, confidence, self.language, self.threshold)
        if candidate == self.language:
            self.pending, self.count = None, 0
        elif re.search(r'[\u0900-\u097f\u0a80-\u0aff]', text):
            self.language = candidate  # Strong script evidence needs no metadata votes.
            self.pending, self.count = None, 0
        else:
            self.count = self.count + 1 if candidate == self.pending else 1
            self.pending = candidate
            if self.count >= self.confirmations:
                self.language = candidate
                self.pending, self.count = None, 0
        return self.language


def response_instruction(language='auto'):
    if language == 'en':
        return 'Respond only in English regardless of the question language. '
    if language in LANGUAGES:
        return 'Respond in natural ' + LANGUAGES[language] + '. '
    return ('Understand English, Hindi, Gujarati, French and mixed-language requests. '
            'Reply in the language of the user, preserving technical names. '
            'An explicit requested response language overrides automatic detection. ')


def normalize_intent(text):
    """Narrow whole-command aliases only; preserve literals and complex requests."""
    patterns = (
        r'(?P<app>[\w .+-]+)\s+(?:kholo|खोलो|ખોલ)',
        r'(?:ouvre|ouvrez)\s+(?P<app>[\w .+-]+)',
        r'(?:खोलो|ખોલ)\s+(?P<app>[\w .+-]+)',
    )
    for pattern in patterns:
        match = re.fullmatch(pattern, text, re.I)
        if match and not re.search(r'\b(?:et|and|then|aur|ane)\b', match['app'], re.I):
            return 'open ' + match['app'].strip()
    return text


def interruption_kind(text):
    value = text.lower().strip(' .!?')
    if re.fullmatch(r'(?:stop (?:talking|speaking)|be quiet|silence)', value):
        return 'STOP'
    if re.fullmatch(r'(?:hold on|wait|pause talking)', value):
        return 'PAUSE'
    if re.fullmatch(r'(?:continue where you stopped|resume talking|continue speaking)', value):
        return 'RESUME'
    if re.match(r'^(?:cancel|stop all tasks)\b', value):
        return 'CANCEL'
    if re.match(r'^(?:no\b|i meant\b|actually\b)', value):
        return 'CORRECTION'
    if re.match(r'^(?:instead\b|rather\b)', value):
        return 'REPLACEMENT'
    if re.match(r'^(?:and also\b|also\b)', value):
        return 'CONTINUATION'
    return 'FOLLOW-UP'
