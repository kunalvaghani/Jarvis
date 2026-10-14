"""Real local F5 synthesis, with a private output and measured latency (no playback)."""
import json
import time
import threading
import sys
from pathlib import Path
import soundfile as sf
from jarvis.f5_speech import load_voice, render


def main():
    base = Path(__file__).resolve().parents[2]
    started = time.monotonic()
    voice = load_voice()
    import torch
    if voice.device == 'cuda':
        torch.cuda.reset_peak_memory_stats()
    loaded = time.monotonic()
    text = "Good evening, sir. Your systems are ready, and I am here to help."
    long_reply = '--long' in sys.argv
    if long_reply:
        text = ('Good evening, sir. Your systems are ready, and I am here to help. '
                'We can review your schedule, look through the latest project changes, or prepare the next task together. '
                'Take your time deciding what matters most. I will keep the details clear and the conversation moving at a comfortable pace. '
                'Whenever you are ready, tell me where you would like to begin.')
    parts = list(render(voice, {"text": text}, threading.Event()))
    audio, rate = parts[0]
    suffix = '-long' if long_reply else ''
    output = base / f'.jarvis-runtime/f5-sample{suffix}.wav'
    sf.write(str(output), audio, rate)
    result = {'text': text, 'output': str(output), 'device': voice.device,
              'load_seconds': round(loaded-started, 3),
              'synthesis_seconds': round(time.monotonic()-loaded, 3),
              'audio_seconds': round(len(audio)/rate, 3)}
    if voice.device == 'cuda':
        result['peak_allocated_mb'] = round(torch.cuda.max_memory_allocated()/1048576)
        result['peak_reserved_mb'] = round(torch.cuda.max_memory_reserved()/1048576)
    (base / f'.jarvis-runtime/f5-verification{suffix}.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
