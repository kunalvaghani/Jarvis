# Continuous, natural voice (2026-10-20 IST)

The user reported that Jarvis stops while speaking and sounds laggy, choppy and robotic, and asked for a
continuous, natural, emotional voice.

## Cause, measured on this PC (RTX 3050 Laptop, 4 GB)

**1. The F5-TTS engine cannot keep up with playback here.** `.jarvis-runtime/speech.log` shows 6–14 s of
synthesis per short sentence during real use. The benchmark below was run with Jarvis stopped and the GPU idle:

| Engine | First audio | Synthesis ÷ audio length | Result |
| --- | --- | --- | --- |
| F5, 32 steps (was configured) | 4.5–4.7 s | 1.8–3.1× | Silent gap after every sentence |
| F5, 16 steps | 2.3–2.4 s | 0.9–1.6× | Still gaps; worse while Whisper/Ollama use the 4 GB GPU |
| Kokoro (CPU, ONNX) | 0.36–1.07 s (after a one-time warm-up) | 0.29× (about 3.4× faster than speech) | Continuous |

Data: [f5-benchmark.json](f5-benchmark.json), [kokoro-benchmark.json](kokoro-benchmark.json). The first
Kokoro row includes its warm-up.

**2. Gaps let stray sound cancel the reply.** `Speech.output_recent()` was true only while audio was being
synthesized or played, plus 1.2 s. In a gap between sentences (the next one still rendering or still being
written by the model), microphone input no longer needed the wake word. Room noise, a "hmm" or the speaker's own
tail could therefore become a command, and every new command interrupts speech.

## Repairs

- **Engine:** the user's live `config/config.json` now sets `speech.engine` to `kokoro`, with the existing
  `am_michael:60,am_fenrir:40` voice blend and the natural-delivery layer (`jarvis/natural_voice.py`). That layer
  gives sentence-sized phrases, punctuation- and paragraph-dependent pauses, occasional soft breaths and
  emotional pacing: brighter and quicker for good news, slower and softer for apologies and warnings.
  `config.json` is the user's local configuration and is not committed. To return to the cloned F5 voice, set
  `"engine": "f5"`.
- **Mid-answer protection (`jarvis/speech.py`):** a reply now counts as ongoing while a sentence is queued or
  still synthesizing, and for 4 s after each streamed update while the answer is being written. Only "Jarvis …"
  interrupts mid-reply. `cancel()` clears the window.

## Verification (2026-10-20)

| Check | Result |
| --- | --- |
| Continuity simulation: a 5-phrase, 22.2 s reply with the configured voice; each phrase's render-complete time compared with when playback reaches it | **0 unplanned stalls** in both runs (saved run: first audio 0.98 s, all 22.1 s of audio rendered in 7.1 s; an earlier unsaved run: 0.94 s / 6.3 s) — [kokoro-continuity.json](kokoro-continuity.json) |
| New `tests/test_continuous_speech.py` (queued / synthesizing / streaming keep protection; gap noise does not cancel; "Jarvis stop" still interrupts; cancel clears) | **7 passed** |
| Speech suites (`test_speech`, `test_natural_voice`, `test_f5_speech`, `test_voice_stt_audit`, `test_voice_tts_audit`, `test_phase2_gpu_models_voice_ui`) plus the new file | **191 passed / 9 skipped** (all BLOCKED live gates) |
| Full regression (16:50–17:08 IST) | **3,668 passed / 0 failed / 148 skipped (all BLOCKED)** — [log](full-regression.log), [xml](full-regression.xml) |

A sample of the new voice reading that reply is saved locally at `app/.jarvis-runtime/voice-samples/kokoro-continuous-sample.wav`
(runtime folder, not committed).

**Limits:** Kokoro is a fixed-voice model. It is not a clone of the F5 reference voice and has no true
emotional acting; emotion here comes from pacing, loudness, pauses and breaths. Live speaker playback, acoustic
echo and listener judgement of "how human" were NOT RUN in this record. Jarvis must be restarted to load the
new engine.
