"""Check the sentence playback pipeline without speakers; optionally save a preview."""
import argparse
import json
from pathlib import Path
import wave

from piper import PiperVoice
import numpy as np
from jarvis.piper_speech import play_reply


BASE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", type=Path, help="Save an English WAV sample; never plays speakers.")
    args = parser.parse_args()
    cases = (("en_GB-alan-medium", "Hello. I'm Jarvis. You can ask me a question, or tell me what you'd like me to do."),
             ("hi_IN-rohan-medium", "नमस्ते, मैं जार्विस हूँ। आप मुझसे कोई भी सवाल पूछ सकते हैं।"))
    class Sink:
        def __init__(self, samplerate, channels, dtype):
            self.rate, self.channels, self.chunks = samplerate, channels, []
        def start(self):
            pass
        def write(self, samples):
            self.chunks.append(samples.copy())
        def stop(self):
            pass
        def close(self):
            pass
    class Audio:
        def OutputStream(self, **kwargs):
            self.sink = Sink(**kwargs)
            return self.sink
    options = json.loads((BASE / "config.json").read_text(encoding="utf-8")).get("speech", {})
    for name, text in cases:
        path = BASE / "models" / "voices" / f"{name}.onnx"
        if not path.is_file():
            raise FileNotFoundError(path)
        voice = PiperVoice.load(str(path))
        audio = Audio()
        play_reply(voice, text, options, audio, np)
        samples = np.concatenate(audio.sink.chunks)
        frames, rate = len(samples), audio.sink.rate
        if frames <= 0 or rate <= 0:
            raise ValueError(f"{name} produced no audio")
        print(f"{name}: {frames} frames at {rate} Hz")
        if args.preview and name.startswith("en_"):
            args.preview.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(args.preview), "wb") as output:
                output.setnchannels(audio.sink.channels)
                output.setsampwidth(2)
                output.setframerate(rate)
                output.writeframes((np.clip(samples, -1, 1) * 32767).astype(np.int16).tobytes())
    print("English and Hindi sentence synthesis passed. No audio was played.")


if __name__ == "__main__":
    main()
