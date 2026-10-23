# Voice profile restoration — 2026-10-23 IST

The user reported poorer transcription and unspoken gibberish during physical headphone/microphone tests, then explicitly requested Jarvis's earlier voice model and architecture. The pre-multilingual Git parent (`1e8adef^`) already used `models/faster-whisper-medium.en`, English, CUDA `int8_float16`, one-second partial decoding and a fixed 0.8-second endpoint. The model was unchanged by the multilingual candidate; its capture frames had changed from 100 to 32 ms and adaptive endpoints had been enabled.

The shipped configuration and absent-option defaults now restore **100 ms capture** and **adaptive endpointing disabled**. The original decoder prompt, thresholds, capture VAD, overlapping Whisper windows, existing command cleanup and final-only effects remain. Passive transcript/language metadata, explicit opt-in settings and queue integration remain available. No packages, drivers or models were installed. The user confirmed the earlier behavior was restored. This is usability confirmation, separate from exact ten-command acceptance.

## Preserved physical evidence

| Receipt | Result |
|---|---|
| [Initial physical probe](../artifacts/task-queue/live-headphone-intake.json) | Capture and decoding ran; zero fixture commands admitted. The probe initially rejected digit-form fixture names; its filter was corrected without permitting unrelated actions. |
| [Digit-filter retry](../artifacts/task-queue/live-headphone-intake-retry.json) | One fixture file completed. User reported unspoken words and inaccurate transcription. |
| [Experimental decoder filtering](../artifacts/task-queue/live-headphone-filtered.json) | Eight fixture tasks admitted; seven completed. The deliberately held first worker exceeded the probe's old 180-second hold limit. Two fixture commands and the decision timeout were not verified. Hold backstop was increased for subsequent probes. |
| [Restored earlier profile](../artifacts/task-queue/live-headphone-restored-profile.json) | Eight distinct fixture files completed and were reopened. `live six.txt` and `live ten.txt` were absent; routine choices were still pending at Finish. **Strict acceptance did not pass.** |

Each probe uses the actual Listener, Engine, Actions and durable queue in its own test workspace. Unknown commands are rejected; no private audio or unknown transcripts are written to receipts or uploaded. Ephemeral final-recognition feedback appears only in the local window. Only ten fixture creates and the exact overnight control can execute. Main Jarvis remains stopped.

## Decoder experiment, not the selected default

A [local comparison](../artifacts/task-queue/asr-silence-comparison.json) reproduced “Thank you very much.” from digital silence and generated low-level white noise with the existing decoder. An experimental decoder VAD/no-vocabulary-prompt path suppressed all three silence/noise fixtures and retained the correct public synthetic “Jarvis Open Calculator” phrase, including its padded variant. The physical user still reported mistakes and requested the older path. **The experiment was reverted from production**, despite its synthetic result. Do not describe it as active or infer general human accuracy from five fixtures.

Official decoder behavior was checked against [SYSTRAN's upstream source](https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/transcribe.py) with Firecrawl and the installed faster-whisper 1.2.1 signature. The source documents VAD filtering and hallucination-silence handling; it does not certify the local microphone.

[Restored-profile focused regression](../artifacts/task-queue/restored-voice-regression.txt): **323 passed in 47.93 seconds**. The full frozen-source suite is tracked separately in the [queue evidence index](../artifacts/task-queue/README.md). Existing Gujarati/mixed-language and physical acoustic-duplex gates remain open. Exact speech admission, a real 20-second presented choice, and extended unattended operation still need successful receipts.
