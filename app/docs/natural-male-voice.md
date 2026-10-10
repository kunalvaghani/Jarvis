# Natural male voice and smooth long speech — 2026-10-10 IST

Jarvis now speaks with a man's voice and a more human delivery: varied pauses, soft breaths before longer
sentences, slight changes of pace, emotional colour, and a warmer, wittier conversational style with the
occasional light joke. Long answers are spoken in full, without stopping partway, and answers start being spoken
while they are still being written.

## What you hear

- **Voice:** a blend of Kokoro's best-rated American male voices, `am_michael` (60%) and `am_fenrir` (40%).
- **Pauses:** about 0.3–0.5 s between sentences, a little longer after questions and exclamations, a short
  catch at commas when a long sentence is split, and 0.7–0.95 s between paragraphs.
- **Breathing:** a soft inhale before some longer sentences (never before every phrase), and sometimes before a
  longer reply begins.
- **Pace and emotion:** each sentence varies slightly (±3%). Excited sentences are a bit quicker and brighter;
  apologies and serious news are slower and softer; long sentences are delivered a touch more deliberately.
  Loudness is evened out between sentences, and every join is click-free.
- **Personality:** answers are written like a warm, witty friend on a call, with contractions and natural
  reactions ("Oh, nice!", "Hmm, good question."). When the mood is light, roughly one reply in four may carry a
  short friendly joke. There are no jokes about serious, sad, medical, financial or urgent matters, and no emoji
  or markdown in spoken replies.

## Smooth long conversations

The voice worker ([kokoro_speech.py](../jarvis/kokoro_speech.py)) keeps one audio stream open. A separate thread
synthesises each phrase ahead of playback, so sentences follow each other without gaps, and new replies are
queued straight behind whatever is playing. Previously each reply was synthesised in full before playing, speech
was cut at 2,500 characters, and the worker was stopped after at most 240 seconds. Now:

- There is no total length or time limit. A watchdog restarts the worker only if it makes no progress for 60 s.
- A long first sentence is split at its first natural clause, so speech starts sooner.
- **Speaking while writing:** finished sentences of an answer are spoken while the model is still writing the
  rest; the final answer then adds only what was not spoken. If the draft is replaced (for example by an
  online-verified answer), the draft stops and the final answer is spoken in full.
- Interrupting Jarvis (saying "Jarvis …" over it) stops speech instantly with a stop message; the voice model
  stays loaded, so the next reply starts without the ~3 s reload.
- The voice worker runs at above-normal CPU priority so the planner cannot make speech stutter.

Delivery planning is in [natural_voice.py](../jarvis/natural_voice.py); the main-process speech queue is in
[speech.py](../jarvis/speech.py).

## Voice choice and samples

All candidates were rendered through the full natural pipeline and checked with the local Whisper model. Listen
to the samples in `artifacts/media/voice-samples/` (created by
[voice_samples.py](../scripts/verification/voice_samples.py); [measurements](../artifacts/reports/voice-samples.json)).

| Voice (`speech.voice`) | Word error (Whisper) | Synthesis speed (idle) |
| --- | --- | --- |
| `am_michael:60,am_fenrir:40` (default) | 0% | 0.30× real time |
| `am_fenrir` | 0% | 0.28× |
| `am_puck` | 0% | 0.30× |
| `bm_george` (British) | 0% | 0.37× |
| `am_fenrir:50,am_puck:50` | 0% | 0.35× |
| `am_michael` | 3.6% | 0.31× |
| `am_michael:50,am_puck:50` | 3.6% | 0.33× |

Word error measures clarity only; how natural a voice sounds needs your own ears.

**Other voice models.** Models with built-in laughter and breathing tags (Chatterbox-Turbo, Orpheus, Fish Audio
S2) were considered. On this computer the GPU is fully used by Whisper and the planner, so a voice model must run
on the CPU in real time alongside the planner. Kokoro does (0.6× real time even while the 9B model generates);
those larger models are GPU-oriented or not confirmed to run in real time on a CPU, so they would risk the
mid-sentence stalls this update removes. Fish Audio S2 is also licensed for non-commercial use only.

## Configuration

`speech` in [config/config.json](../config/config.json):

| Setting | Default | Meaning |
| --- | --- | --- |
| `voice` | `am_michael:60,am_fenrir:40` | Any Kokoro voice, or a weighted blend |
| `speed` | 1.0 | Base pace (0.85–1.2) |
| `natural` | `true` | Phrase planning, pauses, emotion and breaths |
| `breaths` | `true` | Soft breaths before some longer sentences |
| `breath_level` | 0.012 | Breath loudness |
| `stream_answers` | `true` | Speak answers while they are still being written |

## Measurements — live, 2026-10-10 IST

Live on this computer (16 CPU threads, RTX 3050 Laptop 4 GB):

- A 4,278-character reply (40 phrases, 4.5 minutes of speech) was synthesised in full: 0.30× real time with the
  CPU idle, and 0.60× while `qwen3.5:9b` was generating at the same time. Both stay ahead of playback.
- Through the real speech path: the voice model loaded once in 3.2 s; a three-sentence reply started playing
  1.47 s after it was sent and finished cleanly; an interruption stopped speech, kept the same worker process,
  and the next reply started in 0.83 s; no warnings.
- The rendered default sample has pauses of 0.26–0.46 s between sentences, a 0.84 s paragraph break, two soft
  breaths, peak level 0.63 and no invalid samples.

These checks played audio on this computer's speakers; listening quality was not judged by a person yet.

## Limitations

- Kokoro has no real laughter or sighs; "ha ha" is spoken as words, and the breath is a soft synthetic inhale.
- Emotion comes from the words and from pace and loudness, not from a separately controllable voice style.
- A spoken draft can be cut short when the final answer is replaced by an online-verified version.

## Verification

- Fixture tests: [test_natural_voice.py](../tests/test_natural_voice.py) (queueing into one worker, stop without
  reload, errors not retried, no 2,500-character cut, answer streaming without repeats, draft replacement, plan
  pauses/breaths/emotion, breath audio, voice blends, gapless player).
- Regression, 2026-10-10 IST: **1,377 tests ran in 214.570 s, OK with one skipped class**
  ([log](../artifacts/logs/natural-voice-regression.log)); the skipped class needs Docker's Linux engine.
  `python -m jarvis.launcher --check` reports `ready`.
