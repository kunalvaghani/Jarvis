# Upgrade Phase 2 of 8 — API/code-first execution router

**Status: PASS for all mandatory locally executable checks; BLOCKED items listed in test-results.md.** Date 2026-10-17 IST. Branch `claude`. No Codex review evidence exists yet.

Policy implemented: **API/code first → structured automation (UIA / DOM / native object model) → GUI coordinates last**,
chosen per request from discovered, compatible, available and authorized methods, ranked with measured verified
outcomes. Every attempt goes through the existing `ToolRegistry`; no second registry was created.

| | |
| --- | --- |
| Phase 1 commit (predecessor) | `e847b0012e2097dd007938d61555da6a55568a12` |
| Phase 2 commit | [commit.txt](commit.txt) (written by a follow-up commit) |
| Pre-upgrade relevant suites | 390 passed / 4 skipped |
| Phase 2 tests | 30 passed (real Excel, Word, Blender, UIA, headless Chrome, openpyxl, python-docx, pypdf; mocks labelled) |
| Full regression | Full regression **3,223 passed / 147 skipped / 0 failed** (run 2); run 1 had 3 failures from one strict event-list test helper, fixed and preserved as `run1-*`. |
| Launcher readiness | **ready** (includes `openpyxl`/`docx` in `.venv-skills`) |

## Contents

| File | Contents |
| --- | --- |
| [compatibility-matrix.md](compatibility-matrix.md) | Every execution method, tier, operations, verification, refusals, availability, test evidence; desktop provider order |
| [findings.md](findings.md) | ToolRegistry integration evidence, planner integration, tested fallback paths, security/data-preservation findings, defects found and fixed, remaining unsupported cases |
| [measurements.md](measurements.md) | Before/after Phase 1 metrics and real per-method latency / call counts |
| [test-results.md](test-results.md) | Commands, results, PASS/FAIL/BLOCKED/NOT RUN classification against the brief |
| [rollback-and-codex-checklist.md](rollback-and-codex-checklist.md) | Rollback (code, behaviour toggle, environment) and verification checklist |
| [files-changed.txt](files-changed.txt), [source.patch](source.patch) | Exact files and complete source/config/test diff |
| [prompt01-source-inventory-before-phase02.json](prompt01-source-inventory-before-phase02.json) | Preserved copy of the Prompt 01 registry inventory before regeneration |

## Behaviour changes users will notice

* Desktop `activate`/`open_menu` now try UIA patterns before the cyan-cursor tap; the cursor remains the fallback and
  `execution_strategy.desktop_order = "pointer_first"` restores the old order.
* Plans that type into a named Excel/Word document or click through Blender are rejected while an API/structured method is
  eligible; the planner is told which tool to use instead.
* New document/3D/editor tools; every write asks for approval, keeps a backup in `.jarvis-runtime/backups/documents/`
  and is never retried automatically.
