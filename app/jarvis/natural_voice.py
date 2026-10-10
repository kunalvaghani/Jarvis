"""Human-sounding delivery for Kokoro: phrasing, pauses, breaths, pace and emotion.

Kokoro speaks each phrase well but delivers a long reply with uniform gaps and no
breathing. This module plans a reply the way a person speaks it: sentence-sized
phrases, pauses that depend on punctuation and paragraphs, a soft breath before
longer sentences, slight pace variation, and emotional colour from the words
(quicker and brighter when excited, slower when sorry or serious).
"""
from dataclasses import dataclass
import random
import re

EXCITED = re.compile(r"\b(?:great|awesome|amazing|fantastic|wow|yay|congrat\w*|nice|brilliant|perfect|love|excited|woohoo|cool)\b", re.I)
SOMBRE = re.compile(r"\b(?:sorry|unfortunately|sadly|condolences|loss|passed away|careful|warning|danger|serious|failed|"
                    r"can't|cannot|unable|afraid)\b", re.I)
PLAYFUL = re.compile(r"\b(?:ha(?:ha)+|hehe|kidding|joke|funny|lol)\b", re.I)
SENTENCE = re.compile(r"(?<=[.!?…])[\"')\]]*\s+(?=[\"'(\[]?[A-Z0-9])")


@dataclass
class Phrase:
    text: str
    speed: float
    pause_after: float  # Seconds of silence after this phrase.
    breath_before: bool
    gain: float = 1.0


def tts_text(text):
    """Clean text so Kokoro reads it like a person would say it."""
    text = re.sub(r"[\U0001F300-\U0001FAFF☀-➿]", "", text)  # Emoji are not spoken.
    text = re.sub(r"\b(?:lol|lmao)\b", "haha", text, flags=re.I)
    text = re.sub(r"\b(ha)(?:ha)+\b", lambda m: "ha ha" + ("!" if not m.string[m.end():m.end() + 1] in "!.?" else ""), text, flags=re.I)
    text = re.sub(r"\be\.g\.", "for example", text, flags=re.I)
    text = re.sub(r"\bi\.e\.", "that is", text, flags=re.I)
    text = re.sub(r"\betc\.", "and so on.", text, flags=re.I)
    text = re.sub(r"[ \t]*[*_#`]+[ \t]*", " ", text)
    # Keep paragraph breaks (they get a longer pause); everything else is single-spaced.
    paragraphs = [" ".join(part.split()) for part in re.split(r"\n\s*\n", text)]
    return "\n\n".join(part for part in paragraphs if part)


def split_phrases(text, longest=230):
    """Sentence-sized phrases; tiny sentences join the next, long ones split at clause marks."""
    phrases = []
    for paragraph_index, paragraph in enumerate(p for p in re.split(r"\n\s*\n", text) if p.strip()):
        sentences = [s.strip() for s in SENTENCE.split(" ".join(paragraph.split())) if s.strip()]
        merged = []
        for sentence in sentences:
            if merged and len(merged[-1].split()) < 4 and not merged[-1].endswith("?"):
                merged[-1] += " " + sentence
            else:
                merged.append(sentence)
        for index, sentence in enumerate(merged):
            pieces = [sentence]
            if not phrases and len(sentence) > 90:
                # Start speaking sooner: a long opening sentence breaks at its first natural clause.
                cut = next((m.start() for m in re.finditer(r"[,;:] ", sentence) if 25 <= m.start() <= 110), -1)
                if cut > 0:
                    pieces = [sentence[:cut + 1].strip(), sentence[cut + 1:].strip()]
            while len(pieces[-1]) > longest:
                head = pieces[-1]
                cut = max(head.rfind(mark, 0, longest) for mark in (", ", "; ", ": ", " - ", " — "))
                if cut < 60:
                    cut = head.rfind(" ", 0, longest)
                if cut <= 0:
                    break
                pieces[-1:] = [head[:cut + 1].strip(), head[cut + 1:].strip()]
            for piece_index, piece in enumerate(pieces):
                end_of_paragraph = index == len(merged) - 1 and piece_index == len(pieces) - 1
                phrases.append((piece, piece_index < len(pieces) - 1, end_of_paragraph and paragraph_index >= 0))
    return phrases


def plan(text, base_speed=1.0, rng=None, breaths=True):
    """Phrase plan for one reply (or one streamed part of a reply)."""
    rng = rng or random.Random()
    rows, words_since_breath = [], 0
    phrases = split_phrases(tts_text(text))
    for index, (phrase, mid_sentence, paragraph_end) in enumerate(phrases):
        words = len(phrase.split())
        speed, gain = base_speed * rng.uniform(.97, 1.03), 1.0
        if PLAYFUL.search(phrase):
            speed *= 1.04
        elif EXCITED.search(phrase) or phrase.endswith("!"):
            speed, gain = speed * 1.05, 1.06
        elif SOMBRE.search(phrase):
            speed, gain = speed * .94, .95
        if words > 22:
            speed *= .98  # Long sentences are delivered a touch more deliberately.
        if mid_sentence:
            pause = rng.uniform(.12, .2)
        elif phrase.endswith("?"):
            pause = rng.uniform(.42, .6)
        elif phrase.endswith(("!", "…", "...")):
            pause = rng.uniform(.36, .52)
        elif phrase.endswith(":"):
            pause = rng.uniform(.28, .36)
        else:
            pause = rng.uniform(.3, .5)
        if paragraph_end and index < len(phrases) - 1:
            pause = rng.uniform(.7, .95)
        # People breathe before a longer stretch of speech, not before every phrase.
        breath = bool(breaths and index > 0 and not phrases[index - 1][1] and words >= 9
                      and words_since_breath >= 12 and rng.random() < .65)
        if breaths and index == 0 and len(phrases) > 2 and rng.random() < .35:
            breath = True
        words_since_breath = 0 if breath else words_since_breath + words
        rows.append(Phrase(phrase, round(min(1.2, max(.85, speed)), 3), round(pause, 3), breath, gain))
    return rows


def breath(rate, rng=None, seconds=None, level=.012):
    """A soft synthetic inhale: band-limited air noise with a rise-and-fall envelope."""
    import numpy as np
    rng = rng or random.Random()
    seconds = seconds or rng.uniform(.28, .42)
    count = int(rate * seconds)
    noise = np.random.default_rng(rng.randrange(1 << 30)).standard_normal(count).astype(np.float32)
    spectrum = np.fft.rfft(noise)
    frequencies = np.fft.rfftfreq(count, 1 / rate)
    shape = np.exp(-((np.log(np.maximum(frequencies, 1)) - np.log(1400)) ** 2) / (2 * .55 ** 2))  # Airy mid band.
    air = np.fft.irfft(spectrum * shape, count).astype(np.float32)
    position = np.linspace(0, 1, count, dtype=np.float32)
    # Quick swell, softer release; clipped so rounding can never give a negative base (NaN).
    envelope = np.clip(np.sin(np.pi * np.minimum(1, position * 1.15)), 0, 1) ** 1.6
    air *= envelope
    rms = float(np.sqrt(np.mean(air ** 2))) or 1.0
    return (air * (level / rms)).astype(np.float32)


def trim(audio, rate, threshold=.006, keep=.03):
    """Remove the model's own leading/trailing silence so planned pauses are exact."""
    import numpy as np
    loud = np.flatnonzero(np.abs(audio) > threshold)
    if not loud.size:
        return audio[:0]
    pad = int(rate * keep)
    return audio[max(0, loud[0] - pad):min(len(audio), loud[-1] + pad)]


def finish(audio, rate, gain=1.0, target_rms=.075, fade=.006):
    """Even loudness between phrases and click-free edges."""
    import numpy as np
    audio = np.asarray(audio, dtype=np.float32)
    if not audio.size:
        return audio
    rms = float(np.sqrt(np.mean(audio ** 2))) or 1.0
    audio = audio * min(2.5, max(.5, target_rms / rms)) * gain
    ramp = min(len(audio) // 2, int(rate * fade))
    if ramp:
        window = np.linspace(0, 1, ramp, dtype=np.float32)
        audio[:ramp] *= window
        audio[-ramp:] *= window[::-1]
    return np.clip(audio, -.98, .98).astype(np.float32)


def voice_style(voice, spec):
    """'am_michael' or a blend such as 'am_michael:60,am_fenrir:40' (Kokoro style vectors)."""
    parts = [part.strip() for part in str(spec).split(",") if part.strip()]
    if len(parts) == 1 and ":" not in parts[0]:
        if parts[0] not in voice.voices:
            raise ValueError("Selected Kokoro voice is unavailable: " + parts[0])
        return parts[0]
    import numpy as np
    total, mixed = 0.0, None
    for part in parts:
        name, _, weight = part.partition(":")
        name, weight = name.strip(), float(weight or 1)
        if name not in voice.voices or weight <= 0:
            raise ValueError("Invalid Kokoro voice blend part: " + part)
        style = np.asarray(voice.get_voice_style(name), dtype=np.float32) * weight
        mixed = style if mixed is None else mixed + style
        total += weight
    return mixed / total


def language_for(spec):
    first = str(spec).split(",")[0].strip()
    return "en-gb" if first.startswith("b") else "en-us"
