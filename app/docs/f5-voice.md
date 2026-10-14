# F5-TTS voice integration

Added 2026-10-14 IST. The F5-TTS v1 Base adapter uses the same hidden,
owned audio worker and continuous output stream as Kokoro. Dependencies live in
`.venv-f5`; the main environment is unchanged. F5 is selected in the current
configuration with CUDA and the supplied Jarvis reference. Restart Jarvis to apply
the selection to an already running instance.

## Setup and activation

From `app/`, run `powershell -ExecutionPolicy Bypass -File scripts/setup/setup_f5.ps1 -Cuda`
for this GPU configuration, or omit `-Cuda` for CPU-only setup.
Put a clean PCM WAV at `models/voices/f5/reference.wav`. Use 3–11 seconds,
ideally 8–10 seconds of one speaker without music, overlapping voices or effects,
including a short quiet tail. Supply its exact spoken transcript in
`speech.f5.reference_text` in [config.json](../config/config.json).
Set `speech.engine` to `f5`, then restart Jarvis. Readiness checks report a missing
reference or environment; launcher repair installs declared dependencies but
cannot reconstruct a private voice recording. Initial inference downloads the
upstream model and vocoder to the local model cache.

This is zero-shot reference conditioning, not training. The user-supplied
[YouTube source](https://www.youtube.com/watch?v=9hhIc8iWUx4), “JARVIS: A Second
Screen Experience - All Audio,” was downloaded locally. The configured 9.85-second
reference uses 00:02.05–00:11.90; its transcript agrees with local Whisper
transcription and the video's automatic captions. The video describes its audio
as originating from Marvel's 2013 companion app; preserve that source attribution.
No weights have been fine-tuned. Voice
references and caches remain in ignored `models/`; do not commit recordings.

## Natural delivery and emotion

Default settings: 32 inference steps, CFG 2, sway -1, speed 1.0, crossfade 0.15 s.
The adapter preserves the model's own breaths and punctuation pauses, without
adding the Kokoro planner's synthetic breaths or sentence silences. The adapter
bounds text chunks by the reference duration and transcript, prefers punctuation
boundaries, generates them sequentially to avoid unbounded concurrent GPU
inference, and crossfades their joins. Each complete reply is synthesized before playback so
generation cannot cause gaps inside that reply. This increases first-audio
latency. F5 skips draft sentence streaming and speaks the final answer; separate
replies can still have gaps if synthesis is slower than playback.

`speech.f5.auto_emotion: true` uses word cues to choose neutral, serious,
playful or excited style and applies small speed changes. For stronger emotional
delivery, add recordings from the same speaker to `speech.f5.references`:

```json
{"serious": {"reference_audio": "models/voices/f5/serious.wav",
             "reference_text": "Exact words spoken in that recording."}}
```

Each style reference must meet the same audio requirements. Without a style
reference, the neutral recording is used; speed variation alone is not learned
emotion control. Misclassification is possible; disable `auto_emotion` if needed.
Hindi retains the existing Piper route; the English F5 voice is not assumed to
support Hindi. Stop immediately clears playback and discards the current
generation's eventual audio; the current chunk's model inference finishes in the
worker, and remaining chunks are discarded.
Quit terminates the owned worker. Stalled F5 requests are disposed after 600 s
without replay; a later new request may start a fresh worker.

## Hardware and upstream limits

This machine has an RTX 3050 Laptop GPU with 4096 MiB VRAM. The setup script's
`-Cuda` switch installs the matching official PyTorch/TorchAudio 2.6.0+cu124 wheels;
the base requirements pin Transformers 4.44.2 and Gradio 6.16.0 for compatibility.
CPU inference remains available with `device: cpu`, but one 32-step CPU test took
189.625 seconds to generate 3.861 seconds of speech, with a 16.282-second model
load. This is unsuitable for conversational latency on this machine.
When F5 is selected with `device: cuda`, Jarvis's Qwen scheduler reserves at
least 2048 MiB for speech plus the existing 512 MiB additional headroom. On an
otherwise idle 4 GB GPU and an 8192-token context, the policy permits five Qwen
GPU layers instead of twelve; actual admission also considers other VRAM use.
Whisper and unrelated GPU processes remain outside that reservation. GPU
contention and longer replies still need separate measurement.
Cloning fidelity, pronunciation and emotion depend on the reference and text;
perfect cloning and uninterrupted real-time speaking are not guaranteed.

Upstream attribution: [SWivid/F5-TTS](https://github.com/SWivid/F5-TTS),
[inference guide](https://github.com/SWivid/F5-TTS/tree/main/src/f5_tts/infer).
Upstream code is MIT; pretrained weights are CC-BY-NC because of their training
data. Preserve those terms when using/distributing the models.

## Verification

**Unicode speech repair, 2026-10-14 IST:** Lone surrogate characters (including
the reported `\udc81`) are converted to spacing in speech input; valid surrogate
pairs are repaired and Unicode compatibility forms become ordinary letters.
Cleanup runs before speech worker transport and inside `tts_text`, covering direct
worker input, with the same protection for reference transcripts. Stored answers
are unchanged. 126 selected voice/Groq/launcher/recovery/GPU tests passed outside
the sandbox. Initial sandbox runs hit temporary-file permissions and local-network
restrictions. No real Groq inference was issued during this repair verification.
`python -m scripts.verification.verify_f5_worker --unicode` injects invalid Unicode
into the real worker without speaker playback and saves local evidence.
The real CUDA worker successfully synthesized the injected malformed answer,
completed the next queued answer, acknowledged Stop and completed a new answer
without restarting the model. Full launcher readiness reported `ready`. This
checks real synthesis and worker protocol; acoustic speaker playback was not tested.

2026-10-14 IST: 80 selected offline voice/launcher/recovery/GPU scheduling regression tests passed, including
F5 cancellation during inference, full-reply buffering, invalid audio rejection,
bounded settings and warm-worker stop behavior. These use a mocked model and
do not establish live synthesis quality. Two initial recovery tests hit sandbox
temporary-file permissions; the 80-test run passed outside the sandbox.
`python -m jarvis.launcher --check` reported `ready` outside the sandbox;
`--offline-check` reported `dependencies_ready`. The sandbox service check could
not reach Docker, Ollama or LocalGithub. Real CPU F5 synthesis succeeded; local
Whisper transcribed the generated sample exactly as requested. A human listening
comparison, microphone-to-output latency and fine-tuning result remain unavailable.

With F5 selected, the full launcher check reported `ready`. The real warm worker
completed two queued replies in order, acknowledged Stop, discarded the cancelled
reply and completed a fresh reply in the same process. This protocol test used
`--no-playback`; speaker output and acoustic barge-in were not measured.

A real 32-step CUDA sample generated 3.861 seconds of speech in 6.218 seconds,
with 23.422 seconds of model loading, 771 MiB peak allocated VRAM and 814 MiB
peak reserved VRAM. These are one-run synthesis measurements, not guaranteed
latency or whole-machine VRAM figures. The script is
`python -m scripts.verification.verify_f5` in `.venv-f5`; `--long` exercises
multiple chunks. Generated samples and measurement JSON remain local in
`.jarvis-runtime/`. The isolated environment's `pip check` passed after the
compatibility pins were applied.

The final punctuation-aware, sequential three-chunk CUDA run generated 20.852
seconds of speech in 21.719 seconds, with a 34.656-second model load, 798 MiB
peak allocated VRAM and 846 MiB peak reserved VRAM. Full-reply buffering means
that reply waits for synthesis before it begins playing. Warm model reuse removes
model loading from subsequent requests, but not the synthesis delay. These
measurements used isolated synthesis; simultaneous Whisper/Qwen operation was
not benchmarked.
