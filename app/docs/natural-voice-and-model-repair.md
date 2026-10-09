# Free natural speech and configured-model recovery

Updated 2026-10-01.

## Voice choice and costs

The supplied screenshot says Hermes Voice is powered by ElevenLabs, but provides no voice ID or audio sample. Its exact British voice cannot be identified from the image. [ElevenLabs](https://elevenlabs.io/pricing) offers a limited free tier (10,000 monthly credits when checked), with paid tiers beyond that allowance. It is not unlimited free local speech.

The user selected **Kokoro Heart (`af_heart`)**, an American female voice. [Kokoro's voice notes](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md) rate Heart highly but explicitly describe preferences as subjective. This is a practical free local choice, not proof of the world's most natural voice. [Kokoro-ONNX](https://github.com/thewh1teagle/kokoro-onnx) is MIT licensed; Kokoro model weights are Apache 2.0. Attribution: hexgrad/Kokoro and thewh1teagle/kokoro-onnx. There is no API key, subscription or monthly synthesis quota. Microphone recordings and speech text are not uploaded for synthesis.

Listen to the [current synthetic Heart preview](../artifacts/media/jarvis-heart-preview.wav). It is generated speech, not a microphone recording. The old Piper preview is historical.

## Configuration and playback

The [config](../config/config.json) now selects:

```json
"speech": {
  "enabled": true,
  "language": "en",
  "engine": "kokoro",
  "voice": "af_heart",
  "speed": 1.0,
  "sentence_silence": 0.0
}
```

The hidden owned worker preloads Kokoro and stays warm between replies. Each reply is synthesized with phrase context into one continuous audio buffer before playback. Jarvis does not add word-by-word or inter-chunk gaps. Natural punctuation pauses remain part of model output. Longer replies take longer before speech begins. Pronunciation and perceived naturalness still depend on the text and model.

Stop voice or Quit kills the owned worker. Stale queued replies are discarded, and uncertain playback is never replayed automatically. A subsequent explicitly queued reply can start a fresh worker. Worker liveness is checked before every request; bounded synthesis/playback deadlines detect stalls. Diagnostics are in ignored `.jarvis-runtime/speech.log`. Kokoro runs on CPU with four inference threads, leaving the existing Whisper GPU configuration intact.

Piper remains available by setting `speech.engine` to `piper`; Hindi uses the existing Rohan Piper model. The current language setting is English. This update does not establish improved multilingual speech quality.

## Setup and model compatibility

[scripts/setup/setup.ps1](../scripts/setup/setup.ps1) installs the declared `kokoro-onnx==0.4.9` dependency and runs [scripts/setup/setup_voice.py](../scripts/setup/setup_voice.py). The voice assets live under `models/voices/kokoro`, excluded from Git. Their fixed release URLs and SHA-256 checksums are in [kokoro-assets.json](../integrations/profiles/kokoro/kokoro-assets.json). Setup validates checksums and replaces an asset only after its downloaded copy matches. Launcher checks required assets and can restore missing files with hidden setup.

The v1.1 ONNX export expects floating-point speed, while Kokoro-ONNX 0.4.9 supplies an integer for that input. Jarvis's session adapter supplies the correct float and preserves fractional pacing. Installed third-party source is unchanged.

## Why “Configured models is not repaired yet” kept appearing

Jarvis expected `brain.coder: qwen3-coder:30b`, while the already installed 30.5B Qwen3-Coder was named **`Qwen3-Coder:latest`**. The watchdog treated the expected name as missing, launched repeated pulls, and counted an asynchronous repair as an immediate failure. The logs show those pulls failed. A local alias-copy attempt also failed because the model manifest directory denied writes.

The coder configuration now uses the verified installed name. This uses the existing 30.5B model without changing its files or filesystem permissions. A live `scripts/setup/setup_brain.py --ollama-only` check reported all configured models installed; `ModelRecovery.healthy()` returned true with no missing models.

Recovery now distinguishes pending background work from failed repair. It lists missing model names, reports real restoration failure and uses a 300-second cooldown after completion. Setup and recovery share the same required-model list, including the enabled Hermes model. Pending model repair does not cancel unrelated tasks or replay actions.

The status message itself does not cancel a task. A task needing an unavailable model can fail or pause at its checkpoint. Restart Jarvis once to load these changes. If a previous task remains unfinished, say **“resume last task”**; Jarvis inspects current state before continuing. Uncertain writes/clicks are not blindly repeated.

## Verification on 2026-10-01

- Regression/readiness checks: **462 tests passed** in 28.523 seconds. Launcher returned `ready` with no missing dependencies/assets. These are readiness checks, not proof that every desktop task or spoken answer completes within five seconds.

- Actual CPU synthesis created the Heart preview: 6.515 seconds model initialization, 6.281 seconds synthesis, 8.768 seconds audio at 24 kHz. [Evidence](../artifacts/reports/kokoro-voice-check.json).
- The real reusable worker synthesized two short replies in **2.359** and **2.000 seconds** after a **9.047-second cold startup**. [Evidence](../artifacts/reports/kokoro-worker-check.json). These measurements excluded speaker playback, answer generation and microphone recognition.
- Speaker playback and a subjective listening comparison were not performed. The preview lets the user judge naturalness. A universal 2–4 second spoken-answer target is not guaranteed.

Verification commands:

```powershell
.venv\Scripts\python.exe -m scripts.verification.verify_voice
.venv\Scripts\python.exe -m scripts.verification.verify_voice_worker
.venv\Scripts\python.exe -m scripts.setup.setup_brain --ollama-only
.venv\Scripts\python.exe -m unittest discover -s tests -q
.venv\Scripts\python.exe -m jarvis.launcher --check
```

The voice checks generate only synthetic speech and do not use the microphone or speakers. The worker check exits after its two replies.
