# F5-TTS voice integration

**Phase 2 — 2026-10-15 IST:** [Current changes and measurements](phase2-gpu-voice-ui.md)
add shared native inference leases, bounded shared-memory PCM, English speech
normalization, opening-clause lookahead and confirmed pre-audio fallback. The
500 ms first-audio target is unmet; historical timing/voice checks below retain
their original scope. No new listening-quality acceptance is claimed.

**Audit follow-up — 2026-10-15 IST:** Missing reference/environment or cold worker
initialization failure now selects installed Kokoro CPU, then installed Piper.
The worker must report ready before receiving text; startup waits at most 60 s
without holding the Stop lock. A failed F5 backend stays bypassed for this Speech
session. No model download is performed by fallback selection. The launcher still
checks the configured primary dependencies separately; ordinary launcher repair
retains its previously documented dependency policy.

Once text has been submitted, a runtime/transport failure is not replayed through
another voice. Failed submitted fragments are discarded; new text requests or
later unsent stream fragments can restart the owned worker. Stop invalidates text preparation and buffer enqueue, including
queued replies before playback. Language/backend changes drain earlier audio
instead of killing it mid-clause. Playback sends periodic metadata heartbeats so
a long completed waveform is not mistaken for stalled synthesis. F5's progress
watchdog remains 600 s; Kokoro uses 60 s.

Queues are bounded: 64 parent text entries, 64 worker requests and 128 playback
pieces, each finite mono PCM of at most 30 s. Speech text has a 20,000-character
bound; individual words exceeding F5's reference-derived chunk budget are rejected
before inference. Errors preserve the transcript and never grant tool permissions.
Malformed protocol roots/types, stale worker events and duplicate request IDs are
rejected. Native stderr is discarded in production Speech workers; categorical protocol
and health metadata remain. Historical private `speech.log` files are untouched.

A 16-entry header-duration cache keys on path, size and modification/change times;
it stores no audio or reference transcript. Actual cached CUDA synthesis and the
Speech→Kokoro fallback path plus Piper PCM synthesis passed without speaker
playback. These are functional checks, not a listening evaluation. Model weights,
32 steps, CFG, reference and pacing defaults are unchanged. Shared STT/F5 admission
is still absent; the Qwen speech reserve is not a shared lease. No two-second
first-audio guarantee or acoustic equivalence is claimed.
[Current assertions, paired measurements, upstream checks and blockers](../artifacts/jarvis-audit/modules/05-voice-tts/inventory.md).
All October 14 measurements below retain their historical context.

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
inference, and crossfades their joins. Completed sentences or substantial opening
clauses from conversation, Groq public answers and verified research answers are
sent to the voice worker while the island continues receiving text. Unverified
research drafts wait for the final answer. The final delivery adds only the words
that were not already queued; replaced drafts and failed answers cancel speech.

The worker plays each synthesized chunk immediately while generating the next,
retaining just the crossfade tail. Pending text fragments are combined in order
(at most eight requests and 1,000 characters per batch), reducing repeated
reference-processing overhead. Stop invalidates the batch and clears playback;
cancelled text is never replayed. `first_chunk_characters: 80` bounds the opening
chunk of long text; already short sentences stay together. `warm_synthesis: true`
silently primes CUDA synthesis during background worker startup. This extends
initial loading but produces no spoken greeting. Neither setting reduces the
32 inference steps or changes the configured reference, CFG or crossfade.

Streaming removes the wait for the entire reply, but F5 still finishes each text
chunk before producing its audio. Fast text generation can finish before the
first audio is ready. Gaps remain possible when synthesis is slower than playback.
Chunk boundaries and per-chunk level normalization can affect prosody; unchanged
inference settings do not establish acoustically identical output.

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

**Incremental playback, 2026-10-14 IST:** 161 selected speech, answer-stream,
Groq, conversation, question-speed, launcher, recovery and GPU regression tests
passed. They cover early chunk delivery, crossfade sample counts, final-text
deduplication, draft filtering, batch ordering/EOF and Stop. These are regression
checks, not listening-quality measurements.

The real CUDA worker also passed ordered/coalesced replies, malformed-Unicode
input, Stop acknowledgement, cancelled-reply disposal and a new reply in the
same warm process (`verify_f5_worker --unicode`, without speaker playback).
Full `python -m jarvis.launcher --check` reported `ready` after the changes;
this checks dependencies and configured services, not acoustic playback or live
Groq inference. Regression/readiness runs used the unrestricted environment
because sandbox temporary-file and local-service access are limited.

Real isolated CUDA synthesis at the unchanged 32 steps generated a long reply
in 19.657 s, with first audio at 5.079 s rather than waiting for the entire
reply; it produced 20.841 s of audio in three pieces. Model loading including
silent priming took 25.078 s; peak reserved VRAM was 854 MiB. Local Whisper
transcribed the generated words. These are single-run component measurements.

`python -m scripts.verification.verify_f5_island_stream` exercises the actual
Speech queue and CUDA worker using synthetic text arriving every 0.1 s per word,
without a Groq request, island rendering or speaker playback. The final run
queued the opening clause at 0.703 s, produced first audio at 5.312 s, and finished
receiving text at 7.219 s; synthesis completed at 28.078 s. Every word was queued
once. Earlier runs produced first audio at 7.047 and 7.266 s, and one finished
receiving text before audio was ready. Overlap is workload-dependent. Human
listening, speaker underruns and microphone-to-speaker latency remain unmeasured.

Firecrawl retrieved the official [F5 inference implementation](https://github.com/SWivid/F5-TTS/blob/main/src/f5_tts/infer/utils_infer.py).
Its streaming mode emits audio after each text chunk's inference completes. The
Jarvis adapter keeps sequential GPU inference and bounded crossfades without
using the upstream unbounded parallel chunk path. Evidence and recordings stay
in ignored `.jarvis-runtime/`.

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

Historical initial integration, 2026-10-14 IST: 80 selected offline voice/launcher/recovery/GPU scheduling regression tests passed, including
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

Before incremental playback, a punctuation-aware, sequential three-chunk CUDA run generated 20.852
seconds of speech in 21.719 seconds, with a 34.656-second model load, 798 MiB
peak allocated VRAM and 846 MiB peak reserved VRAM. Full-reply buffering means
that reply waits for synthesis before it begins playing. Warm model reuse removes
model loading from subsequent requests, but not the synthesis delay. These
measurements used isolated synthesis; simultaneous Whisper/Qwen operation was
not benchmarked.
