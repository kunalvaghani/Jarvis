# Rollback and deterministic resume

No commit made. Existing branch audit/12-tool-registry and inherited dirty diffs preserved. Baseline HEAD/environment in environment.json. Scoped original files are in ignored .jarvis-runtime/jarvis-audit/module15-pre (relative app paths use __); do not use git reset/restore across unrelated changes. Review source.patch and compare current hashes to source-hashes.json before manually copying these originals over only this module's changes. Preserve subsequent user edits. New scripts/tests may be removed only as a reviewed scoped rollback; never remove personal files or the production app store. No data migration or dependency rollback needed. To disable acquisition use existing knowledge_acquisition.enabled=false configuration and normal Stop/Start only when explicitly requested; this audit did not change live settings.

From app/ using .venv/Scripts/python.exe:
1. -m pytest tests/test_app_research_audit.py tests/test_knowledge_acquisition.py tests/test_live_app_context.py tests/test_skill_memory.py tests/test_task_state.py tests/test_tools.py tests/test_toolkits.py tests/test_audit_result_accounting.py -q --junitxml=artifacts/jarvis-audit/modules/15-app-research/cases-and-contracts.xml
2. scripts/verification/verify_app_research_audit.py (requires preserved preimage; never recreate baseline from modified source).
3. -m scripts.verification.verify_app_research_journey (owned headless intercepted synthetic click only; authored planner).
4. -m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/15-app-research/full-regression.xml
5. -m jarvis.launcher --check; preserve full private output locally and publish redacted readiness status.
6. scripts/verification/report_app_research_audit.py after validating unchanged source hashes and saved readiness JSON.

Exact outstanding catalog IDs: remaining-case-ids.txt. Next unrun module:16, JRV-16-001. Earliest older blocker remains JRV-04-001; this pass does not certify earlier acceptance gates. Resolve plugin namespace before claiming 15-010. Future live account writes/install/credential operations still require per-action approval.
