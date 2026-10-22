"""Wake-gated barge-in and textual self-echo rejection; no acoustic AEC claim."""
from difflib import SequenceMatcher
import re

from .audio import command_text
from .engine import WAKE


def echo_match(text, references):
    text = command_text(text)
    for reference in references:
        spoken = command_text(reference)
        if not text or not spoken:
            continue
        if ' ' + text + ' ' in ' ' + spoken + ' ':
            return True
        # Whisper may slightly revise a loudspeaker's phrase. Match contiguous word windows.
        words, source = text.split(), spoken.split()
        if len(words) >= 4:
            for count in range(max(4, len(words)-2), min(len(source), len(words)+2)+1):
                for index in range(len(source)-count+1):
                    if SequenceMatcher(None, text, ' '.join(source[index:index+count]), autojunk=False).ratio() >= .88:
                        return True
    return False


class VoiceInput:
    def __init__(self, speech, options=None, awake=None, interrupt=None, report=None, responding=None):
        self.speech = speech
        self.options = {} if options is None else options
        if (not isinstance(self.options, dict)
                or any(type(self.options.get(key, default)) is not bool for key, default in (('enabled', False), ('barge_in', True)))
                or self.options.get('audio_mode', 'speakers') not in {'speakers', 'headphones'}):
            raise ValueError('Invalid full-duplex configuration')
        self.awake = awake or (lambda: False)
        self.on_interrupt = interrupt or (lambda kind: self.speech.interrupt())
        self.report = report or (lambda *args: None)
        self.interrupted = None
        self.responding = responding or self.speech.output_recent

    def update(self, text, final, utterance, playback, references, duration):
        """Headphone duplex is opt-in; speakers retain wake gating without AEC.

        Only committed, validated speech can supersede tool work. Explicit wake
        speech can silence output early; no partial ever reaches a tool.
        """
        from .voice_runtime import interruption_kind
        normalized = command_text(text)
        protected = playback or self.responding()
        if protected and echo_match(normalized, references):
            return None
        wake = WAKE.search(normalized)
        duplex = (self.options.get('enabled', False) and self.options.get('barge_in', True)
                  and self.options.get('audio_mode') == 'headphones' and self.awake())
        if protected and not wake and not duplex:
            return None
        if protected and not wake and (not final or duration < .25 or not normalized):
            return None
        candidate = normalized[wake.end():].strip() if wake else normalized
        control = interruption_kind(candidate)
        if final and (wake or self.awake()) and control in {'STOP', 'PAUSE', 'RESUME'}:
            self.on_interrupt(control)
            self.report('voice_interrupt', control)
            self.interrupted = utterance
            return None
        if protected and (wake or duplex) and self.interrupted != utterance:
            if not final:
                self.speech.interrupt()
            else:
                self.on_interrupt(interruption_kind(candidate))
                self.interrupted = utterance
                self.report('voice_interrupt', interruption_kind(candidate))
        if final and self.interrupted == utterance:
            kind = interruption_kind(candidate)
            if kind in {'STOP', 'PAUSE', 'RESUME'}:
                return None
        return ('jarvis ' + candidate).strip() if wake else normalized

    def filter(self, text, playback=None, references=None):
        """Require an explicit wake word for audio overlapping voice output/tail."""
        normalized = command_text(text)
        protected = self.speech.output_recent() if playback is None else playback
        if not protected:
            return normalized
        references = self.speech.output_references() if references is None else references
        if echo_match(normalized, references):
            return None
        # Ignore preceding speaker text when the user speaks over an answer.
        for wake in reversed(list(WAKE.finditer(normalized))):
            candidate = 'jarvis ' + normalized[wake.end():].strip()
            candidate = candidate.strip()
            if not echo_match(candidate, references):
                self.speech.interrupt()
                return candidate
        return None
