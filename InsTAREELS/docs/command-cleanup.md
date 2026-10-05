# Conservative local voice-command cleanup

Updated 2026-10-04. Jarvis uses **Qwen2.5 0.5B** as a separate speech cleanup
selector, while Qwen3.5 9B continues to handle general planning and answers.
Whisper still transcribes the microphone. Cleanup only operates on final accepted
transcripts after the existing playback/echo gate; it never handles audio itself.

## Why this model

The [official Ollama package](https://ollama.com/library/qwen2.5:0.5b) is about
398 MB, Q4_K_M, and Apache 2.0 licensed. It runs locally without paid inference
APIs. The [Qwen model card](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct)
describes instruction following and structured-output support. This application
needs a short constrained choice, rather than a large reasoning model.

We also tested [Qwen3.5 0.8B](https://ollama.com/library/qwen3.5:0.8b) and the
already-installed Qwen2.5 3B Instruct. Qwen3.5's
[official model card](https://huggingface.co/Qwen/Qwen3.5-0.8B) notes possible
thinking loops in 0.8B; thinking was disabled for these tests. Catalog/model-card
claims are separate from our small application measurements.

All three used the same final prompt, schema, CPU-only inference, four threads,
1,024-token context and 32-token output cap on this PC. The comparison harness
waited up to 60 seconds to measure results, without executing any tasks.

| Tested model | Warm median | Warm maximum | Expected fixture result |
| --- | ---: | ---: | ---: |
| Qwen2.5 0.5B | 0.265 s | 0.312 s | 16/16 |
| Qwen3.5 0.8B | 1.032 s | 1.390 s | 16/16 |
| Qwen2.5 3B Instruct | 0.609 s | 0.719 s | 16/16 |

Qwen2.5 0.5B was the fastest of these tested options with equal fixture results.
These are authored text fixtures with constrained choices, **not** a general
speech accuracy score or proof of performance on every spoken command. First
requests may have already-loaded weights; their timing and load duration are
recorded separately in the [model comparison](../artifacts/command-cleanup-model-check.json).
An [earlier prompt-only pilot](../artifacts/command-cleanup-prompt-pilot.json)
returned malformed shapes and unwanted wording changes. The final design does
not trust arbitrary model rewrites.

## Preserving what you said

[The cleanup implementation](../jarvis/command_cleanup.py) constructs one finite
allowed surface edit and asks the model to choose **original** or **cleaned**.
It does not ask the model to invent a better task. Code validates the choice and
the exact resulting text before the command engine receives it.

Supported repairs:

- Remove leading `uh`, `um`, `erm`, `er` after an existing wake word or at the
  start of an awake command. Internal words remain intact.
- Join whole launch targets: `note pad`, `you tube`, `spot ify`, `cal culator`.
  This never replaces those words inside a search query or dictated content.
- Correct launch-verb spellings `opne`/`opun` to `open`.

For example, `Jarvis um open note pad` becomes `Jarvis open notepad`.
`search for you tube bugs` stays unchanged. Cleanup skips commands containing
numbers, explicit negation, paths/several literal delimiters, writing/filling,
sending, deleting, renaming, moving, shell execution, saving, creating, or
multi-action connectors. Dictation, stop/cancel commands, partial hypotheses and
utterances with already-committed actions or typing also bypass it. Clear
commands incur no model request. Names/targets outside the exact alias list are
never corrected by guesswork. Existing Whisper punctuation/case normalization
still runs before this stage; that behavior predates this change.

The raw final transcript remains visible. Applied changes and fallback status
appear as `CLEANUP` transcript entries, without speech announcements or popups.
The selector has no tools and cannot execute a command. Existing execution
verification/approval rules still apply. Ambiguous or missing ASR words remain
unchanged; the existing parser/planner handles the original input. This cannot
guarantee that every audio command becomes executable without inventing intent.

## Configuration and lifecycle

[config.json](../config.json) contains:

```json
"command_cleanup": {
  "enabled": true,
  "model": "qwen2.5:0.5b",
  "timeout_seconds": 2.0,
  "backoff_seconds": 30.0,
  "max_characters": 240
}
```

Set `enabled` to `false` to disable cleanup. Restart through **Stop Jarvis.cmd**
and **Start Jarvis.cmd** after configuration/source changes. Normal brain setup
and existing bounded model recovery include the selected model only when enabled;
the download is already installed on the checked machine. No new Python dependency
or long-running service is added. Both downloaded comparison models are retained;
only the configured one is used by Jarvis for cleanup.

The request goes only to `127.0.0.1:11434`. CPU-only execution preserves GPU
space for Whisper. The model uses five-minute keep-alive. A socket budget limits
cleanup to two seconds by default (configurable from 0.25 to 3 seconds); cold
loading or a busy shared Ollama server can exhaust it. Failure closes the owned
request, retains the original command and skips further cleanup inference for
30 seconds. There is no retry/replay of that command. A later utterance can try
again after backoff. Stop/shutdown discards results before command dispatch and
does not terminate shared Ollama. No audio recording is created by this feature.

## Verification scope

- **Live local cleanup, 2026-10-04:** all 16 synthetic transcripts matched the
  expected production result; seven used actual streamed Ollama inference and
  nine bypassed it. Maximum observed cleanup time was 0.328 seconds. No microphone
  input, external desktop action or payment/message was performed.
  [Runtime evidence](../artifacts/command-cleanup-runtime-check.json).
- **Regression/readiness, 2026-10-04:** **886 tests passed; launcher status `ready`**.
  [Dated results](../artifacts/command-cleanup-regression-check.json)
  are separate from live model measurements. Tests cover forbidden edits,
  cancellation, echo gating, final-only operation, dictation/committed-state
  preservation, missing-model recovery, timeout/backoff and malformed streams.

Reproduce model comparison and production loopback checks with
`.venv\Scripts\python.exe verify_command_cleanup.py`; run regression/readiness
with `.venv\Scripts\python.exe verify_cleanup_regression.py` from the app directory.
