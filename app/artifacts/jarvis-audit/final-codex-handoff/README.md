# Final Codex handoff — Jarvis upgrade Phases 1–8

Date 2026-10-19 IST. Branch `claude`. Pre-upgrade baseline `5b52737`. No Codex review has taken place yet; nothing
here claims Codex approval. Nothing was deployed or merged by this phase. (After Phase 5, at the user's explicit
request, `main` was fast-forwarded to `b909e92`; Phases 6–8 exist only on `claude`.)

## Verdict: **PARTIALLY VERIFIED**

Every locally executable acceptance check passed:
- full regression **3,379 passed / 147 skipped / 0 failed** (17 min 32 s);
- `python -m jarvis.launcher --check` → `ready`;
- 18 cross-pillar and red-team tests;
- real runs recorded in each phase.

It is not *fully* verified because some required checks depend on things unavailable here. These are BLOCKED or NOT RUN, with reasons in [defects-and-unresolved.md](defects-and-unresolved.md):
- live Groq consultation (not authorized);
- GGUF/Ollama export (no converter);
- desktop GUI exploration (no VM);
- Unreal editor projects (no disposable project);
- a physical-click demonstration;
- live voice-to-action and planner-latency measurement;
- post-upgrade real-usage metrics (Jarvis was not run interactively after the upgrade).

All 147 skips are explicitly labelled `BLOCKED` environment dependencies, the same count as at the Phase 1 baseline.

## Package contents (Stage 9)

| # | Item | File |
| --- | --- | --- |
| 1 | Changed-file manifest since the baseline | [changed-files-all.txt](changed-files-all.txt), [changed-files-source.txt](changed-files-source.txt) |
| 2 | Exact `claude` commit SHAs | [commits.txt](commits.txt); per phase: `../phase-0N/commit.txt` |
| 3 | Complete source diff against `5b52737` | [source-since-baseline.patch](source-since-baseline.patch) (code, tests, config, docs; held-out data excluded for size, it is in Git) |
| 4 | Source and dependency inventory | [module-dependency-map.json](module-dependency-map.json), [module-dependency-map.mmd](module-dependency-map.mmd), [module-import-check.json](module-import-check.json), [environment/](environment/), [environment-and-dependencies.md](environment-and-dependencies.md) |
| 5 | Executed commands | [commands-executed.md](commands-executed.md) |
| 6 | Full test output | [full-regression.log](full-regression.log), [full-regression.xml](full-regression.xml), [launcher-check.json](launcher-check.json) |
| 7 | Pass/fail/blocked/skipped/unrun counts | below and [regression-matrix.json](regression-matrix.json) |
| 8 | Security findings | [security-redteam.md](security-redteam.md); per-phase findings in phase packets |
| 9 | Cross-domain regression matrix | below and [regression-matrix.json](regression-matrix.json) |
| 10 | Before/after performance | [performance.md](performance.md), [benchmarks/](benchmarks/) |
| 11 | Model training and inference compatibility | [../phase-07/README.md](../phase-07/README.md), [../phase-07/methodology-and-provenance.md](../phase-07/methodology-and-provenance.md) |
| 12 | Environment requirements | [environment-and-dependencies.md](environment-and-dependencies.md) |
| 13–14 | Unresolved defects and reproduction steps | [defects-and-unresolved.md](defects-and-unresolved.md) |
| 15 | Rollback | below and [../../../docs/upgrade-architecture.md](../../../docs/upgrade-architecture.md) §10 |
| 16 | Codex inspection checklist | below |
| 17 | Claims to falsify | [claims-to-falsify.md](claims-to-falsify.md) |

Verification by stage: pillars and upgrades — [pillar-verification.md](pillar-verification.md); cross-pillar
scenarios 1–17 — [cross-pillar-scenarios.md](cross-pillar-scenarios.md); architecture —
[docs/upgrade-architecture.md](../../../docs/upgrade-architecture.md).

## Test counts (final run, 2026-10-19 11:57–12:15 IST)

| Category | Count |
| --- | --- |
| Passed | 3,379 |
| Failed | 0 |
| Skipped (all `BLOCKED: …` environment dependencies) | 147 |
| Blocked outside the suite (live integrations) | Groq live call, GGUF export, VM exploration, Unreal project, physical click |
| Not run | voice-to-action latency, live planner latency, post-upgrade usage metrics, full-app RAM/VRAM |

History of full regressions: Phase 1 3,193 → Phase 2 3,223 → Phase 3 3,257 → Phase 4 3,277 → Phase 5 3,315 →
Phase 6 3,340 → Phase 7 3,361 → final 3,379 passed. Every run had 147 skipped and 0 failed. One Phase 7 attempt
stalled and was stopped and rerun (D8-3).

## Cross-domain regression matrix (final run; the gate's ten domain suites)

| Domain | Passed | Skipped | Failed |
| --- | --- | --- | --- |
| Voice routing | 52 | 0 | 0 |
| Privacy and cloud isolation | 84 | 0 | 0 |
| DAG planning | 47 | 0 | 0 |
| Coding and file operations | 19 | 0 | 0 |
| Desktop UIA and browser control | 43 | 0 | 0 |
| Skill/MCP registry | 91 | 1 | 0 |
| Memory and retrieval | 59 | 4 | 0 |
| Recovery and idempotency | 35 | 0 | 0 |
| CPU/RAM/VRAM scheduling | 70 | 1 | 0 |
| Integrations and backward compatibility | 84 | 0 | 0 |

Phase test files: P1 19, P2 30, P3 34, P4 20, P5 38, P6 25, P7 21, P8 18 — all passed, none skipped.

## What changed in Phase 8

- **D8-1 repaired:** the cloud architect now has a real, fail-closed, approval-gated entry point (`cloud_architect_consult`).
- **D8-5 repaired (pre-existing bug):** the citation regex in `documents.py` contained literal backspace characters.
- **D8-3 mitigated:** UIA stall diagnostics.
- **New tests:** cross-pillar flows and red-team checks in `tests/test_phase08_integration.py`.
- **New measurement and documentation:** dependency map, final benchmarks, architecture document, this package.

## Rollback

```powershell
git revert --no-edit <commits newest first>   # on claude; full list in commits.txt; baseline 5b52737
```

Runtime features can be disabled through configuration without reverting (see the architecture document §10).
Last known good implementation: the baseline `5b52737` and every intermediate phase head remain recoverable on `claude`.

## Codex inspection checklist

1. [ ] Re-run `python -m pytest tests -q -p no:cacheprovider` and `python -m jarvis.launcher --check`; compare with the logs here.
2. [ ] Check that every skip message starts with `BLOCKED` and that the environment really lacks the stated dependency.
3. [ ] Work through [claims-to-falsify.md](claims-to-falsify.md).
4. [ ] Run each phase packet's own checklist (`../phase-0N/rollback-and-codex-checklist.md`).
5. [ ] Re-run `scripts/verification/phase08_final_benchmarks.py --out <new>` and compare with [performance.md](performance.md).
6. [ ] Inspect D8-1 (`jarvis/cloud_architect.py` `consult_tool`, `jarvis/deliberation.py` `FailureRouter.evidence_row`, `jarvis/brain.py` recover_task notice).
7. [ ] Confirm no file in this package contains credentials or private recordings (the secret scan found none).
