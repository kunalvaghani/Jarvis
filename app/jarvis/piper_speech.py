"""Run local synthesis in a separate process so Stop voice interrupts playback."""
import json
from pathlib import Path
import sys
from .speech import speech_parameters


def play_reply(voice, text, options, audio, numpy):
    """Play Piper's sentence chunks as they arrive, with a small phrase pause."""
    from piper import SynthesisConfig
    parameters = speech_parameters(options)
    pause = parameters.pop("sentence_silence")
    config = SynthesisConfig(**parameters)
    stream = None
    count = 0
    try:
        for chunk in voice.synthesize(text, config):
            if not chunk.audio_float_array.size:
                continue
            if stream is None:
                stream = audio.OutputStream(samplerate=chunk.sample_rate,
                                            channels=chunk.sample_channels, dtype="float32")
                stream.start()
            elif pause:
                stream.write(numpy.zeros((int(chunk.sample_rate * pause), chunk.sample_channels), dtype=numpy.float32))
            stream.write(chunk.audio_float_array.reshape(-1, chunk.sample_channels))
            count += 1
        if not count:
            raise ValueError("Voice synthesis produced no audio.")
    finally:
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()


def main():
    import numpy as np
    import sounddevice as sd
    from piper import PiperVoice

    request = json.load(sys.stdin)
    model_path = Path(request["model"])
    voice = PiperVoice.load(str(model_path))
    play_reply(voice, request["text"], request, sd, np)


if __name__ == "__main__":
    main()
