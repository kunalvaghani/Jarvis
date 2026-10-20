# Claude integration of Codex's e5af0e7 proposals: P99-R8 / V2-004 model-path fix and new tests (2026-10-20 IST)

Branch `claude`, base `e5af0e700517bac5fb48dcebc8f6cc9c9df9a369`. This responds to the cumulative handoff ([CLAUDE_HANDOFF.md](../../../../docs/CLAUDE_HANDOFF.md)). No independent verification of this commit exists yet, and release remains **NOT READY**. Nothing was merged, pushed, deployed, installed or downloaded.

## What was integrated

| Item | Source | Check |
| --- | --- | --- |
| `jarvis/repair_authorization.py` (`model_reference`; enforced in `check_model_download`) and `scripts/setup/setup_brain.py` (re-validated before HTTP; the resolved manifest must stay inside the store; tag lookup fixed) | Codex [source-only.patch](../../codex-v2-independent-review/2026-10-20-e5af0e7/source-only.patch), applied with `git apply` | Byte-identical to Codex's `Jarvis-v2-mutants-e5af0e7` checkout |
| `tests/test_prompt99_model_paths.py`, `tests/test_prompt37_ui_restart.py`, `tests/test_prompt37_reasoning_repeat.py` | Codex [combined-new-tests.patch](../../codex-v2-independent-review/2026-10-20-e5af0e7/combined-new-tests.patch) | Same as Codex's checkouts apart from line endings |
| Evidence packets `codex-v2-independent-review/2026-10-20-e5af0e7`, `modules/37-e2e/2026-10-20-independent-e5af0e7`, `modules/37-e2e/2026-10-20-memory-e5af0e7` | codex-review checkout | Byte-identical (`diff -rq`). A scan found only synthetic credential fixtures |
| `README.md`, `app/README.md`, `docs/CLAUDE_HANDOFF.md`, `docs/CRASH_RECOVERY.md` | Codex's edits since `3fbfbf6` | Three-way merge with `3fbfbf6` as the base; Codex's and Claude's dated blocks are both kept |

The user's `config/config.json` was excluded.

**Review.** Before the fix, an approved or configured alias containing `..`, a drive letter, extra path segments or backslashes could make `approved_pull` write its manifest outside `<store>/manifests`. The finding needs an approved download, so it is not a remote exploit. The patch rejects anything that is not `name[:tag]` or `namespace/name[:tag]` at both the authorization and transport boundaries, before any HTTP request, and checks the resolved target is inside the store. Three-segment registry names such as `hf.co/user/model` are now refused, which fails closed. The `/api/tags` lookup now keys on whether the alias names a tag, not on the parsed default.

## Verification (2026-10-20)

| Check | Result |
| --- | --- |
| `test_prompt99_model_paths.py` against **unfixed** `e5af0e7` source (source files stashed, then restored) | **27 failed / 4 passed** (the 4 are the valid controls), matching Codex's before run |
| New tests plus the P34 and model-recovery suites, with the fix | **106 passed** — [log](targeted.log), [xml](targeted.xml) |
| Full regression (15:13–15:32 IST) | **3,635 passed / 0 failed / 148 skipped (all BLOCKED)** — [log](full-regression.log), [xml](full-regression.xml) |
| `python -m jarvis.launcher --check`, directly after the full run | `check_incomplete`: the F5-TTS readiness probe hit its 60 s timeout (`TimeoutExpired`); nothing missing — [json](launcher-check.json) |
| Same check rerun once (15:35 IST, read-only) | `ready` — [json](launcher-check-rerun.json) |

The F5 timeout came right after an 18-minute test run on the same machine and did not recur. It is recorded rather than hidden; F5 probe timing under load is not certified.

## Still open

These are unchanged from the handoff:

- the global verifier/replay/target-authority P1;
- the semantic cloud provenance P1;
- the IR-004 deep-cwd P2;
- the 25 BLOCKED P37 journeys, including the real ReasoningBank planner loop (JRV-37-017);
- every live native, voice, account, GPU, training, service, rollback and flag gate.
