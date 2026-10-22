# Voice architecture baseline — 2026-10-23 IST

Inspected before implementation on main; clean working tree. Task branch: `codex/realtime-multilingual-voice`.

- `main.App.toggle_listening` owns one `audio.Listener`; `pcm_ring.CaptureQueue` bounds callback PCM, Silero VAD runs on the capture consumer, and one decoder uses the existing `whisper_backend` GPU scheduler.
- Capture used 100 ms blocks; partial hypotheses every 1 s, fixed 0.8 s silence, 20 s windows with 4 s overlap. `TranscriptAssembler` joins timestamped rollover words. This is rolling-window Whisper decoding, not native streaming ASR.
- `Engine` owns wake/follow-up state and preserves final writing; it could dispatch an opening clause before final speech. No explicit stable/revision event existed.
- Capture stays active during synthesis. `VoiceInput` rejects textual speaker echo and requires a wake word during output/tail; only speech output was interrupted there. `Actions` task generations/tokens, `Knowledge` generation/session/history and `Speech` generations already coordinate their respective workers.
- Speech workers use bounded queues, progressive Kokoro/F5 output and cancellation. Existing tool permissions/checkpoints remain authoritative. No acoustic playback-reference AEC exists.
- Installed ASR directories are `medium.en` and `small.en`, both English-only. Configuration selects CUDA medium.en/int8_float16 and language en. Installed Piper assets: English Alan and Hindi Rohan; Kokoro English and optional F5 configuration exist. No French/Gujarati Piper assets were found. Language accuracy cannot be established from script classification.
- No new dependency/model/driver is required for deterministic orchestration changes. Existing owned services/recovery/launcher remain in place.

Baseline regression: `pytest tests/test_continuous_speech.py tests/test_voice_stt_audit.py tests/test_voice_tts_audit.py -q`: 73 passed, 2 gated skips, 7.29 s. This is regression evidence, not live acoustic acceptance. No physical microphone session was started for this audit.

Plan: enforce final-only effects, add revision/stability events and adaptive endpoints in the current listener; add explicit playback interruption policy with existing cancellation; extend lightweight language metadata/intent/voice capability routing and existing UI. Retain speaker wake gating without verified AEC. Keep unavailable language/acoustic/performance acceptance explicit.

Research: official [faster-whisper](https://github.com/SYSTRAN/faster-whisper) retrieved through Firecrawl on 2026-10-23. Its API exposes detected language/probability, local CPU int8 and lazy decoding; streaming integrations are separate wrappers. Preserve existing rolling decoding rather than claiming native streaming or adding a second ASR service.

Follow-up inventory discovery: inspecting the installed Kokoro style-vector bank (beyond the configured English worker and Piper filenames) found `ff_siwis`. It was already installed at baseline but unused by the language router. The candidate adds and tests French phonemization/routing without a voice download. The two new multilingual ASR assets were downloaded later only after explicit user approvals; they do not change this pre-upgrade inventory.
