# Scoped changes — 2026-10-15 IST

Runtime files (exact patches/preimage provenance in [source.patch](source.patch) and [source-hashes.json](source-hashes.json)):

- `jarvis/audio.py`
- `jarvis/whisper_backend.py`
- `main.py`
- `jarvis/runtime_health.py`

Module 02 adds bounded perception/diagnostics and stale-window fixes, deep-history recovery, escaped stats, stalled sensor health and task identity binding in Brain/Tools/Actions/TaskState. Module 03 adds four anchored phrases, safe compound punctuation, parser type/size/depth validation and latest-document clarification in the shared Brain path. Module 04 repairs release-buffer resampling, duplicate dispatch and shutdown ownership; validates settings and exposes categorical health. These shared files intentionally cross module boundaries.

Tests: `tests/test_perception_cognition_audit.py`, `tests/test_intent_direct_audit.py`, `tests/test_voice_stt_audit.py`, `tests/test_audit_completion_cases.py`, `tests/audit_contract_helpers.py`, `tests/test_audit_result_accounting.py`. Existing cognition/routing privacy tests are reused as executable helpers, never merely referenced as a pass.

Harness/report: `scripts/verification/verify_perception_cognition.py`, `verify_intent_direct.py`, `verify_voice_stt_audit.py`, `audit_catalog.py`, `report_completion_02_04.py`; prior module report scripts are historical partial reporters and must not overwrite current completion reports. Documents: root/app README, docs index, cognitive architecture, natural language, fast conversation, push-to-write and system map; runtime_manifest and audit artifacts. [Complete scoped list](../../completion-files.json).

No new model/package/dependency/service; no real external action, installation or deployment. Capture/job ownership copies remain; only redundant padding copy removed. Correctness fixes retained despite small capture/cold-cognition timing increases. Existing dirty work preserved, no commit created.
