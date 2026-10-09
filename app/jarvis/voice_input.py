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
    def __init__(self, speech):
        self.speech = speech

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
