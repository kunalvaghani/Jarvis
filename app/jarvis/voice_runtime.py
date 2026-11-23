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
    delay = {'fast': .5, 'balanced': base, 'careful': 1.4, 'conversation': .55}[mode]
    unfinished = re.search(r'(?:\b(?:and|then|or|for|to|with|aur|ane|et|pour|uh|um|phir|ki|ke|toh|ya)|और|फिर|कि)\W*$',
                           text, re.I)
    if writing or unfinished:
        delay = max(delay, 1.8)
    elif mode == 'conversation':
        # Talking turn-taking: a short pause ends the turn. The final transcription is decoded early (during this
        # pause) and is what Jarvis acts on, so unstable partial captions need no extra wait; long turns get a bit more.
        if len(text.split()) > 14:
            delay = max(delay, .9)
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
    if language == 'hi':
        return 'Respond in natural Hindi. ' + DEVANAGARI
    if language in LANGUAGES:
        return 'Respond in natural ' + LANGUAGES[language] + '. '
    return ('Understand English, Hindi, Gujarati, French and mixed-language requests. '
            'Reply in the language of the user, preserving technical names. ' + DEVANAGARI +
            'An explicit requested response language overrides automatic detection. ')


# The reply is spoken: Hindi words in Latin letters ("main abhi khol raha hoon") cannot be pronounced correctly,
# Devanagari can. English names/terms may stay in English; the voice pronounces them as English.
DEVANAGARI = ('When you reply in Hindi or Hinglish, write the Hindi words in Devanagari script (for example '
              '"ठीक है, मैं YouTube खोल रहा '
              'हूँ"), not Hindi in Latin letters. ')


# App and site names the multilingual recognizer writes in Devanagari when the sentence is Hindi/Hinglish.
DEVANAGARI_NAMES = {'यूट्यूब': 'YouTube', 'क्रोम': 'Chrome', 'नोटपैड': 'Notepad', 'स्पॉटिफाई': 'Spotify',
                    'स्पोटिफाई': 'Spotify', 'कैलकुलेटर': 'Calculator', 'व्हाट्सएप': 'WhatsApp', 'व्हाट्सऐप': 'WhatsApp',
                    'जीमेल': 'Gmail', 'गूगल': 'Google', 'एक्सप्लोरर': 'Explorer', 'पेंट': 'Paint', 'वर्ड': 'Word',
                    'एक्सेल': 'Excel', 'ब्लेंडर': 'Blender', 'डिस्कॉर्ड': 'Discord', 'सेटिंग्स': 'Settings'}
# Hinglish command verbs (Latin or Devanagari) -> the English command the parser already knows.
HINGLISH = (
    (r'(?P<app>[\w .+-]+?)\s+(?:kholo|khol do|open karo|खोलो|खोल दो|ખોલ)', 'open {app}'),
    (r'(?:खोलो|ખોલ)\s+(?P<app>[\w .+-]+)', 'open {app}'),
    (r'(?:ouvre|ouvrez)\s+(?P<app>[\w .+-]+)', 'open {app}'),
    (r'(?P<app>[\w .+-]+?)\s+(?:band karo|band kar do|band kardo|close karo|बंद करो|बंद कर दो)', 'close {app}'),
    (r'(?P<app>[\w .+-]+?)\s+(?:bajao|baja do|chalao|chala do|play karo|बजाओ|बजा दो|चलाओ|चला दो)', 'play {app}'),
    (r'(?P<app>[\w .+-]+?)\s+(?:search karo|search kar do|dhundo|dhoondo|सर्च करो|ढूंढो|खोजो)', 'search for {app}'),
)


def normalize_intent(text):
    """Narrow whole-command aliases only; preserve literals and complex requests."""
    named = text
    for hindi, english in DEVANAGARI_NAMES.items():
        named = named.replace(hindi, english)
    parts = re.split(r'\s+(?:aur|और)\s+', named.strip(' .!?।'), flags=re.I)
    if len(parts) > 1:
        # "Chrome kholo aur Python tutorial search karo": every part a known Hinglish command -> spoken steps.
        steps = [normalize_intent(part) for part in parts]
        return ' then '.join(steps) if all(step != part for step, part in zip(steps, parts)) else text
    for pattern, command in HINGLISH:
        match = re.fullmatch(pattern, named.strip(' .!?।'), re.I)
        if match and match['app'].strip() and not re.search(r'\b(?:et|and|then|aur|ane|और)\b', match['app'], re.I) \
                and not re.match(r'(?:write|type|likho)\b', match['app'].strip(), re.I):
            return command.format(app=match['app'].strip())
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
