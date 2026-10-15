# Prompt05: F5-TTS / Kokoro / Piper — 2026-10-15 IST

**30 catalog PASS, 2 BLOCKED, 0 FAIL/SKIPPED/NOT RUN. Live acceptance remains blocked; this is not whole-system production certification.** All32 IDs have [executed-assertion or blocker evidence](tests.jsonl). JRV-05-004 needs a listening evaluation; JRV-05-010 lacks shared STT/F5 lease admission and controlled contention proof. Physical speaker/device churn and acoustic barge-in remain unverified beyond fixtures.

Commit `e9f6f735bc310d11e3cdecfbf95a85d96b170ec2`, branch `codex/jarvis-prove-fix-audit`; existing dirty work preserved. Windows, main/F5 Python3.10.6, Ryzen7/32GB target, RTX3050 Laptop4096MiB. GPU was idle at census; only one heavyweight GPU worker ran at a time. No account/OS mutation, sends, personal deletes, installation, model download or deployment. No new dependency/service or UI layout; no new screenshot/sample is fabricated.

## Source map and call order

The candidate `jarvis/speech_worker.py` does not exist. Actual flow: answer progress/final in main → Speech.stream/say → owned parent queue → F5 child in separate venv or installed CPU worker → renderer → Player callback → typed progress/health. Risk/Stop/ownership contracts were tested before native checks. Piper fallback follows existing English/Hindi models. F5 engine/reference/32-step quality configuration is retained.

| Claim | Actual source | Evidence / boundary |
| --- | --- | --- |
| Parent speech routing | [jarvis/speech.py:79](../../../../jarvis/speech.py) | Generation-bound queue, ready handshake, installed CPU fallback before text submission, no retry of failed submitted text |
| F5 rendering | [jarvis/f5_speech.py:116](../../../../jarvis/f5_speech.py) | Sequential cached-reference chunks, fixed quality settings, crossfade and post-inference cancellation |
| Continuous output | [jarvis/kokoro_speech.py:104](../../../../jarvis/kokoro_speech.py) | Finite mono audio, 128-piece bound, cancellation under buffer lock and periodic playback heartbeat |
| Worker protocol | [jarvis/kokoro_speech.py:219](../../../../jarvis/kokoro_speech.py) | 64 requests, monotonic IDs, categorical errors, malformed-frame rejection and bounded EOF shutdown |
| Hindi / final fallback | [jarvis/piper_speech.py:8](../../../../jarvis/piper_speech.py) | Existing streaming Piper path unchanged; installed component PCM synthesis verified |
| Resource policy | [jarvis/gpu_scheduler.py:54](../../../../jarvis/gpu_scheduler.py) | Qwen reservation only; STT and F5 are outside shared lease coordinator |
| Health | [jarvis/runtime_health.py:10](../../../../jarvis/runtime_health.py) | Speech UUID/backend/queue/restart metadata; no spoken payload |

## Executed checks

Existing baseline command: `.venv/Scripts/python.exe -m pytest tests/test_f5_speech.py tests/test_speech.py tests/test_natural_voice.py tests/test_answer_stream.py tests/test_gpu_scheduler.py -q --tb=short --junitxml=artifacts/jarvis-audit/modules/05-voice-tts/existing-baseline.xml`: **88 PASS in6.74s**. [Baseline](existing-baseline.xml). New adversarial baseline: **16 FAIL/1 BLOCKED in1.06s**; later interrupted-queue and missing-playback-heartbeat reproductions each failed. [Diagnosis and fixture corrections](failures.md).

Final dedicated command adds `tests/test_voice_tts_audit.py`, `test_runtime_health.py`, `test_recovery.py` and `test_audit_result_accounting.py` to the baseline modules: **161 PASS / 2 BLOCKED**, 8.44s JUnit time. [Targeted XML](cases-and-contracts.xml). Full `.venv/Scripts/python.exe -m pytest tests -q --tb=short --junitxml=artifacts/jarvis-audit/modules/05-voice-tts/full-regression.xml`: **2073 PASS / 5 BLOCKED**, 319.67s JUnit time; one pywinauto STA COM UserWarning. Three skips belong to prior Prompt04, two to05. [Full XML](full-regression.xml). These overlapping runs are not summed.

Real `.venv/Scripts/python.exe -m scripts.verification.verify_voice_tts_audit --live`: **PASS**, one cached F5 CUDA model load; short+long ordered replies, Stop discards request3, new request4 succeeds. No speaker playback. Ready **23.531s**, first request audio **4.938s**, measured Stop acknowledgement **0.0000s** (rounded protocol timing, not acoustic stop). Peak Torch allocated/reserved **798.46/840.00MiB**. [Events/metrics](live-worker.json). Pilot remains separately labeled; it is not a pre-change native baseline.

Real `--live-cpu`: forced missing-reference options in an isolated Speech instance; installed Kokoro handled **2 replies/1 warm process**, and Piper produced **93696 finite PCM samples**. No output stream; [evidence](live-cpu-fallback.json). This was a functional check under regression load, not a controlled latency comparison. `.venv-f5/Scripts/python.exe -m pip check`: no broken requirements; launcher `--check`: **ready**, [readiness](readiness.json). Dependency readiness is not acoustic acceptance.

## Equivalent CPU experiment

`.venv/Scripts/python.exe -m scripts.verification.verify_voice_tts_audit`: 20 alternating warm batches/build (40 requests/batch),5 cold child imports/build; same synthetic local PCM header and phrase corpus. [CSV](benchmarks.csv), [summary](benchmark-summary.json). Full chunk words/boundaries asserted; reference replacement invalidates cache. Warm P50/P95 **0.3910/0.4051→0.3036/0.3253ms**. Cold P50/P95 **30.2856/30.4211→30.2081/31.2581ms**. Keep the small metadata win; cold difference is not a demonstrated startup gain. RSS is sampled, not peak. This saves header work, not several seconds of F5 inference; no native before/after speedup, WER, listening-quality or2-second guarantee claimed.

[Exact files/decisions](changes.md), [official versions/release dates](compatibility.md), [scoped runtime patch](source.patch), [hashes](source-hashes.json), [rollback/resume](rollback.md), [remaining IDs](remaining-case-ids.txt). All prior scaffold reports are preserved in history-before-audit. Earlier02–04 results remain in [previous final report](../../final-report-before-module05.md).
