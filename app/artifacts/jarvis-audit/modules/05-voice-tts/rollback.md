# Scoped rollback and deterministic continuation

Use normal Stop Jarvis before runtime rollback. Preserve current files/metadata. Review [source.patch](source.patch) and [byte hashes](source-hashes.json); captured preimages are `.jarvis-runtime/jarvis-audit/module05-pre/` and contain earlier dirty work. Restore only these reviewed hunks, not HEAD or a whole shared file. Manifest rollback removes speech_audit and restores only changed f5_speech fields; keep other module sections. Parent queue remains volatile; do not restore old speech or task queues or erase external-write uncertainty.

From app:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_voice_tts_audit.py tests/test_f5_speech.py tests/test_speech.py tests/test_natural_voice.py tests/test_runtime_health.py tests/test_answer_stream.py tests/test_recovery.py tests/test_gpu_scheduler.py tests/test_audit_result_accounting.py -q --tb=short --junitxml=artifacts/jarvis-audit/modules/05-voice-tts/cases-and-contracts.xml
.venv/Scripts/python.exe -m pytest tests -q --tb=short --junitxml=artifacts/jarvis-audit/modules/05-voice-tts/full-regression.xml
.venv/Scripts/python.exe -m jarvis.launcher --check
.venv/Scripts/python.exe -m scripts.verification.report_voice_tts_audit
```

Archive CSV/JSON/XML first before remeasurement. CPU benchmark command is `-m scripts.verification.verify_voice_tts_audit`; private preimages required. `--live` uses only cached F5 with offline flags and no playback; `--live-cpu` permits only a no-playback Kokoro child and local Piper PCM. Do not start simultaneous heavyweight models, download weights, install dependencies or open actual speakers as a test side effect.

Next module05 IDs: **JRV-05-004**, provide approved/labeled French/Hindi-name recordings and human listening rubric; **JRV-05-010**, design/test shared runtime admission with proper ownership/Stop policy and obtain a resource-safe controlled STT/F5 contention evaluation. Qwen reservation alone cannot substitute for that proof. Keep those IDs BLOCKED until actual assertions succeed. Whole-catalog next unrun module is06/JRV-06-001; prior04 acoustic blockers remain. Later modules are not completed by the full regression.

No config migration, dependency rollback, personal-file deletion or external write is necessary. Existing private logs may contain older spoken data; they were preserved and never published, not silently sanitized or erased. Shared host ability isolation and unsupported Python remain separate release issues.
