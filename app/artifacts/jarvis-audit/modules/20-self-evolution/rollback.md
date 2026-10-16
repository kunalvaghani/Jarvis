# Scoped rollback and deterministic resume

No audit commit. Preserve dirty inherited branch and user/module14–19 changes. Compare source.patch and current hashes before restoring only module20 changes from ignored .jarvis-runtime/jarvis-audit/module20-pre (app-relative paths use __; root-README.md for parent). Never reset all, overwrite a vault or discard user source edits. No real self-patch/ability/dependency installation was performed. New max_attempts default3 is additive; no user config file was modified.

Do not downgrade a live pending-learning backlog without reviewing needs_review entries: older code can lose its uncertain-state guarantees. Discover-only interrupted jobs can return pending; interrupted learner writes require fresh state review and an explicit new request, not automatic retry. Process-owned patch test receipts are intentionally not restored across restart; re-evaluate. Rollback applies only while target bytes still equal the deployed candidate; later user edits block overwrite. Restore only a verified backup after inspecting external state.

From app/ with existing .venv/Scripts/python.exe:
1. scripts/verification/verify_self_evolution_audit.py (immutable original preimage A/B).
2. -m pytest tests/test_self_evolution_audit.py tests/test_self_evolution.py tests/test_anticipation.py tests/test_repo_learning.py tests/test_repo_abilities.py tests/test_gpu_scheduler.py tests/test_audit_result_accounting.py -q --junitxml=artifacts/jarvis-audit/modules/20-self-evolution/cases-and-contracts.xml
3. Freeze jarvis/*.py and tests/test_*.py hashes, then -m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/20-self-evolution/full-regression.xml. No source edits during accepted full run.
4. -m jarvis.launcher --check (read-only), keep raw output in ignored runtime storage; publish only redacted summary.
5. scripts/verification/report_self_evolution_audit.py then scripts/verification/verify_self_evolution_artifacts.py; git diff --check.

Next unrun module/case JRV-21-001; earliest older unresolved JRV-04-001. Current module incomplete002/003/006/011; exact global pending IDs remain in artifacts/jarvis-audit/remaining-case-ids.txt. Resolve these missing contracts with isolated fixtures before live acceptance. Any real source deployment, runtime installation or account action requires the prompt's separate explicit per-action approval.
