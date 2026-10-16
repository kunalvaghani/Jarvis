# Scoped rollback and deterministic resume

No audit commit. Preserve inherited dirty audit/12-tool-registry and user/module14–17 changes. Compare source.patch/current hashes before manually restoring only module18 changes from ignored .jarvis-runtime/jarvis-audit/module18-pre (app paths use __; root-README.md for parent). Never reset all, regenerate old preimages, delete user data or overwrite real vault/cache. No production data migration or dependency install. Commit/hash fields additive; legacy unpinned metadata readable with snippets suppressed; never invent old commit IDs.

From app/ with existing .venv/Scripts/python.exe:
1. scripts/verification/verify_repo_learning_audit.py (immutable before-source A/B).
2. scripts/verification/verify_repo_learning_journey.py (temporary command/worker/restart/coding context/trusted Git read; no downloaded source execution).
3. -m pytest tests/test_repo_learning_audit.py tests/test_repo_learning.py tests/test_repo_abilities.py tests/test_repository_skills.py tests/test_repository_skill_isolation.py tests/test_toolkits.py tests/test_audit_result_accounting.py tests/test_gpu_scheduler.py tests/test_gpu_scheduler_audit.py -q --junitxml=artifacts/jarvis-audit/modules/18-repo-learning/cases-and-contracts.xml
4. Freeze runtime/test hashes, then -m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/18-repo-learning/full-regression.xml
5. -m jarvis.launcher --check (read-only); retain raw output locally, publish redacted readiness.json.
6. scripts/verification/report_repo_learning_audit.py; scripts/verification/verify_repo_learning_artifacts.py.

Next NOT RUN JRV-19-001; earliest older unresolved JRV-04-001. Exact remaining IDs in remaining-case-ids.txt. Module18 open003/019 require authorized sandbox behavior oracle and durable in-flight job checkpoint contract, with actual faults/crash tests. Missing live services require concrete environment; no ability install/arbitrary script/system upgrade/deployment authorized by verification commands.
