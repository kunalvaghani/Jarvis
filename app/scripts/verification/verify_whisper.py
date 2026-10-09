"""Exercise real CUDA inference without microphone capture or desktop actions."""
import argparse
import json
from pathlib import Path
import time
import threading

from jarvis.whisper_backend import load_model
from jarvis.audio import ASR_PROMPT, command_text, DecodeJob, Listener
from jarvis.engine import Engine


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", type=Path)
    parser.add_argument("--model-path", type=Path, help="Test another downloaded model without changing Jarvis configuration")
    parser.add_argument("--language", choices=("auto", "en"), help="Override recognition language for this test")
    parser.add_argument("--stream", action="store_true", help="Replay incremental hypotheses through the actual decoder worker")
    args = parser.parse_args()
    base = Path(__file__).resolve().parents[2]
    audio_path = args.audio or (base / "tests/fixtures/jarvis-command.wav")
    if not audio_path.is_file():
        raise FileNotFoundError(f"Verification audio is missing: {audio_path}")
    config = json.loads((base / "config/config.json").read_text(encoding="utf-8"))
    options = {**config["whisper"], **({"language": args.language} if args.language else {})}
    model_path = args.model_path or (base / config["model_path"])
    model = load_model(model_path, options)
    import numpy as np
    from faster_whisper.vad import get_vad_model
    get_vad_model()(np.zeros(16384, dtype=np.float32))
    warmup, _ = model.transcribe(np.zeros(16000, dtype=np.float32), language="en", beam_size=1)
    list(warmup)
    audio = str(audio_path)
    started = time.perf_counter()
    language = options.get("language", "en")
    segments, info = model.transcribe(audio, language=None if language == "auto" else language, beam_size=5,
                                     word_timestamps=True, temperature=0,
                                     condition_on_previous_text=False,
                                     initial_prompt=ASR_PROMPT)
    text = " ".join(segment.text.strip() for segment in segments)
    elapsed = time.perf_counter() - started
    planned = []
    Engine(lambda command: planned.append(command.__dict__), lambda *args: None).feed(command_text(text), final=True)
    result = {"device": model.model.device, "compute_type": model.model.compute_type,
              "audio_seconds": round(info.duration, 2), "decode_seconds": round(elapsed, 2),
              "text": text, "planned_only": planned}
    if args.stream:
        from faster_whisper.audio import decode_audio
        samples = decode_audio(str(audio_path), sampling_rate=16000)
        streamed, messages = [], []
        ready = threading.Event()
        def report(kind, value):
            messages.append((kind, value))
            if kind in {"partial", "final", "fatal"}:
                ready.set()
        listener = Listener(model_path, None,
                            Engine(lambda command: streamed.append(command.__dict__), report), report, options)
        worker = threading.Thread(target=listener._decode, args=(model,), daemon=True)
        worker.start()
        try:
            for end in list(range(16000, len(samples), 16000)) + [len(samples)]:
                ready.clear()
                listener.jobs.put(DecodeJob(1, 0, samples[:end], final=end == len(samples)))
                if not ready.wait(30):
                    raise RuntimeError("Streaming GPU test timed out")
                if any(kind == "fatal" for kind, _ in messages):
                    raise RuntimeError(str(messages[-1]))
            # The final callback occurs immediately before the engine consumes it.
            deadline = time.monotonic() + 5
            while len(streamed) < len(planned) and time.monotonic() < deadline:
                time.sleep(0.01)
        finally:
            listener.stop()
            worker.join(30)
        result["stream_planned_only"] = streamed
        result["stream_matches_final"] = streamed == planned
    print(json.dumps(result, indent=2))
    if result.get("stream_matches_final") is False:
        raise RuntimeError("Streaming commands differed from final transcription; inspect results above.")
    if config["whisper"]["device"] == "cuda" and model.model.device != "cuda":
        raise RuntimeError("GPU verification failed")


if __name__ == "__main__":
    main()
