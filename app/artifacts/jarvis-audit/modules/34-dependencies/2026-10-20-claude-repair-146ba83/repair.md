# Prompt 34 repairs — P34-001 and P34-002 (Claude, 2026-10-20 IST)

Branch `claude`, base `146ba83`. Responds to Codex's packet `modules/34-dependencies/2026-10-20-independent-146ba83/`
(codex-review worktree). No Codex re-review of this repair exists yet; Prompt 34 stays BLOCKED until it does. No setup or
install script was run, nothing was installed or downloaded, and no module 35 work was started.

## Repairs

| ID | Codex finding | Repair |
| --- | --- | --- |
| **P34-001** (P1) | `launcher.prepare_runtime` ran `pip --isolated install` (and venv creation, Whisper/Laya/voice downloads, CUDA torch installs) as soon as an import check failed, with no approval and despite offline settings | `prepare_runtime` is now **read-only readiness**: one import check per declared environment and presence checks for model files. Anything absent raises `RepairRequired` (`repair_required`) with "Nothing was installed or downloaded". The launcher records it and rechecks read-only at its slowest cadence, never retrying a repair. The only repair it performs is rebuilding a **single environment** from an explicit, single-use authorization (`python -m jarvis.repair_authorization dependency …`). That authorization names the environment, a **locked** requirements file (every line `==`-pinned with a `sha256` hash; its file hash is bound), a local wheelhouse (the approved artifact set), a byte budget and a one-hour expiry. The replacement is staged as `<env>.staging-<id>` with `pip install --no-index --find-links <wheelhouse> --require-hashes --only-binary=:all:`. `--isolated` is removed, so pip configuration and offline flags stay in force. The staged environment must pass its import check before a swap; the old environment is kept as `<env>.previous-<id>`. A failed stage leaves the working environment untouched and the staging folder in place. The current `requirements/*.txt` files are not hash-locked, so **no approved artifact set exists yet**. Until one is created, absent dependencies stay `repair_required` (the user can still run the setup launchers themselves). |
| **P34-002** (P1) | `ModelRecovery.repair` launched `setup_brain --ollama-only` (Ollama pulls) in the background with no approval or disk budget | The default is now **diagnosis**. A background thread reports each missing configured model and the installed compatible fallback that model selection uses (`installed_model`'s documented list), or "no installed compatible model". It downloads, deletes and recreates nothing, and substitutes no other provider. A configured tag is not consent. `download(approval)` is the final executor. Immediately before launch, `check_model_download` requires: the exact model (one of the missing configured tags), a `sha256:` manifest revision, a known source (`ollama`), an explicit network permission, no offline flag (`JARVIS_OFFLINE`, `PIP_NO_INDEX`, `HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE`, `OLLAMA_OFFLINE`), a known byte budget that fits free space in the model store plus a 2 GiB reserve, a known RAM budget within installed RAM, and, when VRAM is budgeted, a measured GPU that meets it. Anything unknown or insufficient refuses before launch. An approved run pulls only that model (`setup_brain --model/--revision/--max-bytes`). It first checks the registry manifest digest and size against the approval, has no retries, keeps partial layers and verifies the installed digest afterwards. Authorizations are single use. Deliberate shutdown still prevents any launch. |

Files: `jarvis/repair_authorization.py` (new), `jarvis/launcher.py`, `jarvis/model_recovery.py`, `scripts/setup/setup_brain.py`,
`tests/test_prompt34_dependency_repair.py` (new), `tests/test_model_recovery.py`.

`tests/test_model_recovery.py::test_failed_download_reports_real_cooldown_and_preserves_other_work` called
`download()` without any approval, which is exactly the behaviour Codex flagged. It is replaced by
`test_failed_approved_download_reports_cooldown_keeps_partials_and_does_not_retry`, which uses an approved, budgeted
download ([list](codex-replaced-tests.txt)).

## Verification (2026-10-20)

| Check | Result |
| --- | --- |
| Codex's `test_dependency_boundaries.py`, byte-identical (JRV-34-012, JRV-34-011, installed-runtime and deliberate-shutdown controls) | **4 passed** (was 2 FAIL / 2 PASS) — [log](codex-boundaries-unchanged.log), [xml](codex-boundaries-unchanged.xml). Traces: [install](unapproved-install-trace.json) (one read-only import check, no pip), [model](unapproved-model-trace.json) (0 launches) |
| Codex's **50** baseline checks (IDs from Codex's `baseline.xml`) | 49 still-existing IDs pass, and the replaced test's successor passes. Run together with the whole `test_model_recovery.py` (pytest counted 55 because the file's IDs overlap) — [log](codex-baseline-50.log) |
| Codex's **112** passing retention checks (IDs from Codex's `retention.xml`) | **112 pass**, plus `test_model_recovery.py` (118 executions) — [log](codex-retention-112.log) |
| New Prompt 34 tests (read-only readiness for each absent dependency, authorized staging keeps the old environment, failed staging untouched, 7 refused authorization shapes, current requirements are not a locked set, single-use authorizations, authorization not spent when more is missing, launcher waits without repairing, diagnosis with fallback, ample resources are not consent, approved download launches exactly the approved model, 13 refused bounds, refused download reported, shutdown, approved-pull revision/budget/installed-digest checks) | **44 passed** with `test_model_recovery.py` — [log](prompt34-repair-tests.log) |
| Model routing, fidelity and manifest regressions (`test_model_selection`, `test_ollama_models`, `test_model_routing_audit`, `test_cognition_and_routing`, `test_task_routing`, `test_phase2_gpu_models_voice_ui`, `test_launcher_readiness`, `test_recovery`, `test_task_recovery`, `test_prompt32_recovery_boundaries`, `test_architecture_audit`) | **238 passed / 7 skipped** (all BLOCKED live GPU/voice gates) — [log](model-routing-fidelity-manifest.log) |
| Full regression (2026-10-20 01:21–01:39 IST) | **3,511 passed / 0 failed / 147 skipped (all BLOCKED)** — [log](full-regression.log), [xml](full-regression.xml) |
| `python -m jarvis.launcher --check` | `ready` — [launcher-check.json](launcher-check.json) |

## Not addressed (still open)

- **No hash-locked requirements or wheelhouse exist.** Building one needs package downloads, which this audit did not
  do. Until a user creates one, an authorized environment rebuild is refused, and absent dependencies remain
  `repair_required`.
- The approved Ollama pull path is tested with mocked registry/Ollama responses only. That the Ollama tag digest equals
  the sha256 of the registry manifest is an assumption, NOT RUN live. No real pull was performed.
- Renaming an environment that the launcher itself is running from fails on Windows; the swap then fails closed with
  the old environment kept.
- The user-run setup launchers (`launchers/Setup Jarvis Brain.cmd`, `Resume Whisper Setup.cmd`) are explicit user
  actions and were not changed or run.
