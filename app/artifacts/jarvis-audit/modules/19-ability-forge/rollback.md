# Rollback and deterministic resume

No audit commit. Preserve inherited dirty branch and user/module14–18 diffs. Compare source.patch and current SHA256 before restoring only this change from ignored .jarvis-runtime/jarvis-audit/module19-pre (app-relative paths encoded with __, root-README.md for parent). Never git reset all or overwrite user state/vault/recordings. New fields are additive; old code may ignore uncertain_external_write, so never downgrade against a live ability registry until pending external actions are inspected. No production data migrated or ability installed by this audit.

Runtime rollback stores one previous approved version; failed-type output restores its metadata only after verifying the old code hash. Nothing is executed or resent. Missing/tampered previous version remains failed. Failed approved validation preserves the already working version. Rebuild/review is required after changed code or an uncertain network result, following inspection of fresh external state. Voice queue consent hashes are ephemeral; restart cannot replay the old queued approval.

From app/ with existing .venv/Scripts/python.exe:
1. scripts/verification/verify_ability_forge_audit.py (bounded original preimage versus current A/B).
2. -m pytest tests/test_ability_forge_audit.py tests/test_repo_abilities.py tests/test_repository_skills.py tests/test_repository_skill_isolation.py tests/test_repo_learning.py tests/test_intent_direct_audit.py tests/test_capabilities.py tests/test_toolkits.py tests/test_audit_result_accounting.py -q --junitxml=artifacts/jarvis-audit/modules/19-ability-forge/cases-and-contracts.xml
3. Freeze jarvis/*.py and tests/test_*.py SHA256, then -m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/19-ability-forge/full-regression.xml; do not edit runtime/tests during acceptance.
4. -m jarvis.launcher --check (read-only); keep raw diagnostics in ignored runtime storage and publish only redacted summary.
5. scripts/verification/report_ability_forge_audit.py then scripts/verification/verify_ability_forge_artifacts.py; git diff --check.

Next unrun module/case: JRV-20-001. Earliest older unresolved: JRV-04-001. Global remaining-case-ids.txt records every exact incomplete ID; do not infer PASS from a related regression. Open live/hardening gates listed in compatibility.md and failures.md. Future runtime installation, ability activation, accounts, deployment require the prompt's explicit per-action authorization.
