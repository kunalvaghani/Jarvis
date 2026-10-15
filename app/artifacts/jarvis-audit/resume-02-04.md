# Deterministic continuation — 2026-10-15 IST

All96 IDs in Prompts02–04 have an explicit result. In that scope only JRV-04-001/002/003 remain BLOCKED. Full-system pending IDs remain in [remaining-case-ids.txt](remaining-case-ids.txt); next unrun module is05, JRV-05-001. Preserve the dirty checkout and captured preimages; do not start a second heavyweight GPU job.

From app, reproduce accessible assertions:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_audit_completion_cases.py tests/test_voice_stt_audit.py tests/test_intent_direct_audit.py tests/test_perception_cognition_audit.py -q --tb=short --junitxml=artifacts/jarvis-audit/completion-targeted.xml
.venv/Scripts/python.exe -m pytest tests -q --tb=short --junitxml=artifacts/jarvis-audit/completion-full-regression.xml
.venv/Scripts/python.exe -m jarvis.launcher --check
.venv/Scripts/python.exe -m scripts.verification.report_completion_02_04 --final
```

Archive current XML/CSV/summary before repeating measurements. Paired scripts: `verify_perception_cognition.py`, `verify_intent_direct.py`, `verify_voice_stt_audit.py` under `scripts/verification/`, run as `-m scripts.verification.<name>`. They require private captured preimages; hashes/provenance are retained per module. They benchmark owned CPU fixtures only, not GPU recognition. Do not run older partial report generators over the completion reports.

Acoustic prerequisites: independently supplied/labeled quiet-room command recordings and expected text; background-TV clips with channel/source annotations and negative examples; long-pause utterances with reference words/timings/intent. Dedicated GPU headroom for installed medium.en/CUDA runtime must be available without interrupting unowned processes. Use local reference audio and approved physical microphone capture only. No recording or bulk model download is implied by this audit. Do not send recordings to a cloud service.

For001 measure actual decode/command accuracy and capture-to-dispatch P50/P95 over repeated cold/warm trials. For002 measure false activations over labeled duration. For003 test execution timing relative to annotated pauses and final intent; the current0.8-second endpoint cannot certify arbitrary pause intent. Keep held writing, negation, numbers and proper nouns in the test bank. Record model/runtime hashes, peakVRAM/RSS, timing and exact result per case. Implement real assertions and remove only the matching explicit blocker after proof; current tests deliberately skip these missing acoustic validations. Never simply relabel a textual fixture as acoustic PASS.

New installs, account changes, personal file mutation, live typing/sends or deployment still need their own concrete approval. After any supported native-runtime upgrade, rerun acoustic plus owned regression tests before promoting it. Python3.10 end-of-life, native GIL hangs and host ability isolation remain separate release issues.
