"""F5-TTS adapter for the owned, cancellable continuous audio worker."""
import json
import math
import os
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def number(options, key, default, low, high):
    try:
        value = float(options.get(key, default))
        return min(high, max(low, value)) if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def reference(options, text=""):
    from .natural_voice import EXCITED, SOMBRE, PLAYFUL, speech_unicode
    style = "neutral"
    if options.get("auto_emotion", True):
        style = "serious" if SOMBRE.search(text) else "playful" if PLAYFUL.search(text) else "excited" if EXCITED.search(text) else "neutral"
    selected = options.get("references", {}).get(style) or options
    path = Path(selected.get("reference_audio", ""))
    path = path if path.is_absolute() else BASE / path
    transcript = speech_unicode(str(selected.get("reference_text", ""))).strip()
    if not path.is_file() or not transcript:
        raise ValueError("F5-TTS needs a local 3–11 second reference recording and its exact reference_text. Configure speech.f5.")
    import wave
    try:
        with wave.open(str(path), 'rb') as audio:
            duration = audio.getnframes() / audio.getframerate()
    except (wave.Error, EOFError) as exc:
        raise ValueError('F5 reference must be a PCM WAV recording.') from exc
    if not 3 <= duration <= 11:
        raise ValueError("F5-TTS reference must be 3–11 seconds, including a short quiet tail.")
    return path, transcript, style


def readiness(options):
    if not (BASE / ".venv-f5/Scripts/python.exe").is_file():
        return "F5-TTS environment missing: run scripts/setup/setup_f5.ps1"
    try:
        reference(options)
    except (ValueError, OSError, ImportError) as exc:
        return str(exc)
    return None


def load_voice():
    options = json.loads((BASE / "config/config.json").read_text(encoding="utf-8"))["speech"].get("f5", {})
    reference(options)
    os.environ.setdefault('HF_HUB_DISABLE_XET', '1')
    import torch
    torch.set_num_threads(int(number(options, 'cpu_threads', 4, 1, 16)))
    from f5_tts.api import F5TTS
    # CPU avoids competing with Whisper/Qwen on the measured 4 GB GPU.
    voice = F5TTS(model="F5TTS_v1_Base", device=options.get("device", "cpu"),
                  ckpt_file=options.get("checkpoint", ""),
                  hf_cache_dir=str(BASE / "models/voices/f5/cache"))
    voice.jarvis_options = options
    return voice


def chunks(text, path, transcript, pacing):
    """Keep each API call to one bounded chunk, avoiding upstream unbounded futures."""
    import wave
    with wave.open(str(path), 'rb') as audio:
        duration = audio.getnframes() / audio.getframerate() + .1
    maximum = max(1, int(len(transcript.encode('utf-8')) / duration * (22-duration) * pacing * .8))
    rows, words, size = [], [], 0
    for word in text.split():
        count = len(word.encode('utf-8')) + 1
        if words and size + count > maximum:
            boundaries = [index+1 for index, value in enumerate(words)
                          if value.endswith(('.', ',', ';', ':', '!', '?')) and index >= len(words)//2]
            cut = boundaries[-1] if boundaries else len(words)
            rows.append(' '.join(words[:cut]))
            words = words[cut:]
            size = sum(len(value.encode('utf-8'))+1 for value in words)
        words.append(word)
        size += count
    if words:
        rows.append(' '.join(words))
    return rows


def render(voice, request, stop, emit_progress=lambda index: None, rng=None):
    import numpy as np
    from .natural_voice import tts_text, finish
    options = voice.jarvis_options
    text = tts_text(request["text"])
    if not text or stop.is_set():
        return
    path, transcript, style = reference(options, text)
    pacing = number(options, "speed", 1., .85, 1.15)
    if options.get("auto_emotion", True):
        pacing *= {"serious": .97, "playful": 1.02, "excited": 1.03}.get(style, 1.)
    crossfade = number(options, "cross_fade_duration", .15, 0., .3)
    pieces = []
    for index, text_chunk in enumerate(chunks(text, path, transcript, pacing)):
        if stop.is_set():
            return
        audio, rate, _ = voice.infer(ref_file=str(path), ref_text=transcript, gen_text=text_chunk,
            speed=pacing, nfe_step=int(number(options, "nfe_step", 32, 16, 64)),
            cfg_strength=number(options, "cfg_strength", 2., 1., 3.),
            sway_sampling_coef=-1, cross_fade_duration=crossfade,
            remove_silence=False, show_info=lambda *args: None)
        emit_progress(index)
        audio = np.asarray(audio, dtype=np.float32)
        if not audio.size or not np.isfinite(audio).all() or rate != 24000:
            raise ValueError("F5-TTS returned invalid audio or sample rate.")
        pieces.append(audio)
    if not pieces:
        return
    audio = pieces[0]
    for piece in pieces[1:]:
        overlap = min(int(24000*crossfade), len(audio), len(piece))
        if overlap:
            fade = np.linspace(0, 1, overlap, dtype=np.float32)
            audio = np.concatenate((audio[:-overlap], audio[-overlap:]*(1-fade) + piece[:overlap]*fade, piece[overlap:]))
        else:
            audio = np.concatenate((audio, piece))
    if not stop.is_set():
        # Enqueue the crossfaded complete reply to prevent underruns.
        # Preserve its pauses and breaths rather than injecting synthetic ones.
        yield finish(audio, rate), rate


if __name__ == "__main__":
    import sys
    if '--check' in sys.argv:
        options = json.loads((BASE / 'config/config.json').read_text(encoding='utf-8'))['speech'].get('f5', {})
        issue = readiness(options)
        from f5_tts.api import F5TTS
        import torch
        if options.get('device', 'cpu') == 'cuda' and not torch.cuda.is_available():
            issue = 'F5 CUDA device unavailable; run setup_f5.ps1 -Cuda or select device cpu.'
        print(json.dumps({'ready': not issue, 'error': issue}))
        sys.exit(1 if issue else 0)
    else:
        from .kokoro_speech import serve
        serve(load_voice, render)
