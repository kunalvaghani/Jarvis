"""Explicit task questions and conservative matching of short option replies."""
import re


class TaskClarification(ValueError):
    def __init__(self, question, slot=""):
        self.slot = slot
        super().__init__(question)


def choice_index(text, labels):
    text = text.strip().strip(".!?").casefold()
    text = re.sub(r"^(?:i (?:choose|want|mean)|use|choose|select|click|open|go with)\s+", "", text)
    text = re.sub(r"^(?:the\s+)?(?:option|number)\s+", "", text)
    text = re.sub(r"^the\s+|\s+(?:one|option|please)$", "", text).strip()
    words = "one two three four five six seven eight nine ten".split()
    ordinals = "first second third fourth fifth sixth seventh eighth ninth tenth".split()
    if text in words or text in ordinals or re.fullmatch(r"\d+(?:st|nd|rd|th)?", text):
        index = words.index(text) if text in words else ordinals.index(text) if text in ordinals else int(re.match(r"\d+", text)[0]) - 1
        return index
    matches = [i for i, label in enumerate(labels) if text == str(label).strip().casefold()]
    return matches[0] if len(matches) == 1 else None


def short_reply(command):
    if command.kind not in {"ask", "task", "click_control", "choose_control", "confirm_suggestion"}:
        return False
    text = command.value.strip()
    return bool(text and len(text) <= 250 and not re.match(
        r"^(?:what|why|how|when|who|where|research|search|create|make|write|delete|remove|send|run|execute|stop|cancel|open|launch)\b", text, re.I))
