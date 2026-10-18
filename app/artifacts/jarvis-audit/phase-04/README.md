# Upgrade Phase 4 of 8 — SEAgent-style exploration, ReasoningBank and OpenViking

**Status: PASS for all mandatory locally executable checks.** Date 2026-10-18 IST. Branch `claude`. No Codex review evidence exists yet.
Desktop GUI exploration is BLOCKED (no verified VM); live model-authored lessons are NOT RUN.

| | |
| --- | --- |
| Predecessors | Phase 1 `e847b00`, Phase 2 `16d9b4d`, Phase 3 `6f88033` |
| Phase 4 commit | [commit.txt](commit.txt) (follow-up commit) |
| Preflight suites | 367 passed / 9 skipped |
| Phase 4 tests | 21 passed (real isolated browser, Blender 4.4.3, OpenViking 0.5.0, local embeddings) |
| Full regression | 3,277 passed / 147 skipped / 0 failed |
| Launcher | ready |
| Real vault | indexed read-only; unchanged (full-tree SHA-256); 46/49 verified links; search p50 127 ms |

| File | Contents |
| --- | --- |
| [architecture-and-provenance.md](architecture-and-provenance.md) | Upstream revisions/licenses (incl. OpenViking AGPL handling), components, ReasoningBank schema, index layout, exploration safety model |
| [findings-and-limitations.md](findings-and-limitations.md) | Defects H1–H5 (including the stray Ollama incident), measurements, limitations M1–M8 |
| [test-results.md](test-results.md) | Commands, results, classification against the brief |
| [measurements.md](measurements.md) | Before/after metric harness |
| [rollback-and-codex-checklist.md](rollback-and-codex-checklist.md) | Rollback, disable switches, checklist |
| [files-changed.txt](files-changed.txt), [source.patch](source.patch) | Exact files and diff |
