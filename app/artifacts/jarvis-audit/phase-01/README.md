# Upgrade Phase 1 of 8 — Audit, repair, verify and trusted baseline

**Status: PASS (all mandatory locally executable checks).** Date 2026-10-17 IST. Branch `claude`.
Live account, microphone, GPU-contention and desktop acceptance remain BLOCKED/NOT RUN and are not claimed.
No Codex review has taken place yet; no review evidence exists.

| | |
| --- | --- |
| Starting commit | `5b52737b0afa25677f5f82058aefa9656e88a375` (`main`, `codex`, `claude` identical at start — [git-state.txt](git-state.txt)) |
| Phase 1 commit on `claude` | recorded in [commit.txt](commit.txt) (written by the follow-up commit, because a commit cannot contain its own SHA) |
| Full regression | before **3,173 pass / 147 skip / 1 fail** → after **3,193 pass / 147 skip / 0 fail** |
| Launcher readiness | **ready** |

## Packet contents

| File | Contents |
| --- | --- |
| [architecture-and-dependency-map.md](architecture-and-dependency-map.md) | Inventory, implemented execution architecture, duplicate subsystems, new contracts, Phase 2–4 dependency map, doc-vs-code differences |
| [defects.md](defects.md) | Initial defects D1–D6, observations O1–O3, root causes, fixes, proof |
| [test-results.md](test-results.md) | Exact commands, results, PASS/FAIL/BLOCKED/NOT RUN classification |
| [metrics.md](metrics.md) | Before/after measurements |
| [rollback-and-codex-checklist.md](rollback-and-codex-checklist.md) | Rollback commands and independent verification checklist |
| [files-changed.txt](files-changed.txt), [source.patch](source.patch) | Exact modified files and complete source/test diff (packet and README edits are documentation) |
| `baseline-*` / `after-*` logs and XML, `metrics-*.json`, `module-imports-*.json`, `silent-exception-census.json`, `launcher-check.json` | Raw evidence |

## Changes in one paragraph

Fixed a ToolRegistry input-contract defect (D1), made cognition memory-source failures observable (D4), stopped a
regression test from overwriting dated audit evidence (D5), removed a Node startup race from a cleanup test without
removing assertions (D6) and replaced two fragile name patterns (D2, D3; no behaviour change). Added the shared,
metadata-only execution-outcome contract (`jarvis/execution_contracts.py`, `tool.outcome` rows in the existing
`agent-events.jsonl`) that Phases 2–4 consume, plus a reusable versioned metrics script
(`scripts/verification/phase_baseline.py`) and 19 regression tests.
