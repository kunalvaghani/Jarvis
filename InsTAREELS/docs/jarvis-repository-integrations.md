# Planning and natural speech integrations

**DeepSeek Harness update (2026-10-02):** General planning/replanning now uses the official SDK and matching Windows runtime with local Qwen. Read-only research has an explicit Harness backend. [How it works, integration boundaries, setup and verification](deepseek-harness.md); [retained MIT license](../integrations/DEEPSEEK-HARNESS-LICENSE).

**Current voice update (2026-10-01):** English now uses Kokoro Heart with a warm worker and continuous reply playback. The Piper implementation below describes the earlier integration and remains available as a fallback; Hindi still uses Piper. See [current voice setup, preview and verification](natural-voice-and-model-repair.md).

## Microsoft JARVIS

Repository: https://github.com/microsoft/JARVIS
Pinned revision: `7624cf388b47334ff8a0868e7d862dde18cfda86`.
License: MIT, retained in `integrations/MICROSOFT-JARVIS-LICENSE`.

HuggingGPT separates planning, model selection, execution, and response
generation. Its `resource_has_dep` and `fix_dep` functions detect dependencies
between model outputs using `<GENERATED>-id` references. Our existing local
planner, screen model, decision model, and tool registry already serve the
corresponding roles; importing its entire Linux model server is unnecessary.

`jarvis/task_graph.py` adapts dependency discovery for flat desktop tool
arguments and validates optional `id`/`dep` task metadata. Missing, duplicate,
self-referential, cyclic, and wrongly ordered dependencies stop execution.
Replanning can refer to completed IDs only if verified. Validation runs before
planning dispatch and again before each action. Generated resource placeholders
are rejected: desktop tools must receive actual, freshly observed targets.
Execution remains sequential, with existing approval, verification, cancellation,
and uncertain-action safeguards. Completion replies use conversational wording
only after the existing final verification succeeds.

## isair/jarvis

Repository: https://github.com/isair/jarvis
Pinned revision: `30c46ca8bf4929e9cad31ceca56dd704ddc288f0`.
Reference license: `integrations/ISAIR-JARVIS-LICENSE`. It restricts commercial
use and requires derivatives to use the same terms. Its source was inspected
as a reference, with the license retained alongside the downloaded originals.
No isair source or prompt text is copied into Jarvis's runtime modules.

The voice implementation uses local Piper with the British male
`en_GB-alan-medium` voice, concise conversational replies, formatting cleanup,
configurable synthesis pacing, and interruption. Our Jarvis already had this
same voice installed, plus Hindi `hi_IN-rohan-medium`, but saved settings had
speech disabled. This change enables speech and independently implements:

- Conversational question-answer style without breaking the worker JSON protocol.
- Speech for answers and final results of supported tasks/app/file commands.
- Text cleanup retaining link labels, suppressing source URLs, and referring
  code blocks to the transcript instead of reading source code aloud.
- Sentence-by-sentence playback rather than buffering the entire answer.
- Bounded synthesis settings and brief sentence pauses. Default length scale
  is 1.05, noise scale 0.667, noise width 0.8, and sentence silence 0.18 seconds.
- Cancellation synchronized with worker launch, so Stop during model checking
  cannot launch canceled audio. Turning off Speak answers cancels playback too.
- Bounded playback timeout accounting for reply length. Failed/stalled playback
  is never replayed automatically; repair reports remain silent.

This is the installed Piper voice, not a cloned movie actor or a new voice model.
Quality remains limited by that model. Both transcript and audio remain local.
No new dependencies or services are introduced. The existing speech worker is
already registered with the watchdog; source snapshots and hidden startup/stop
entrypoints remain compatible. A running Jarvis loads the changes on its next
launch; this upgrade does not interrupt an active task or restart the app.

`speech.enabled`, `language`, `length_scale`, `noise_scale`, `noise_w_scale`, and
`sentence_silence` are saved in `config.json`. Use **Speak answers** and **Stop
voice** in Jarvis; the language chooser continues to select English/Hindi/Auto.
The English voice preview is in `artifacts/jarvis-voice-preview.wav`.

Validation commands:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe verify_speech.py --preview artifacts\jarvis-voice-preview.wav
.\.venv\Scripts\python.exe -m jarvis.launcher --check
```

Speech verification runs both installed models through the new sentence
playback pipeline using an audio sink, without playing the computer's speakers.
Tests inject playback failure, worker timeout, cancellation before launch,
and shutdown. The existing recovery regression suite covers retry backoff and
shutdown. No new automatic recovery/retry path is introduced.

Results on 2026-09-26: all 276 tests passed; English and Hindi sentence
synthesis passed; launcher reported `ready` with no missing dependencies.
