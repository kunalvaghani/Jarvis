# Parallel code intelligence evidence — 2026-10-24 IST

These receipts are for the PCIDE and Island input/choice-card candidate on `claude/parallel-code-intelligence`. [Architecture, commands, configuration and limits](../../docs/parallel-code-intelligence.md).

| Receipt | What it is | Result |
|---|---|---|
| [focused-regression.txt](focused-regression.txt) | PCIDE, project, awareness, coder/codex/native/workload, development, repo learning, web development, media, Island desk, queue, workflow, intent testbook/audit, architecture, launcher and cognition suites | **617 passed / 14 gated skips** |
| [full-regression-first-run-3-failures.txt](full-regression-first-run-3-failures.txt) | First complete suite on the integrated code | **3 failed** / 4,288 passed / 150 skipped. Three robustness defects: `send_input` called on stub apps without `take_input`; input history read an auto-created Mock attribute; choice dismissal assumed every Actions object has every pending field. All fixed |
| [full-regression.txt](full-regression.txt) | Complete suite on the final code | **4,291 passed / 150 gated skips / 0 failures**, one existing warning, 1,164.80 s (19 m 25 s) |
| [launcher-check.txt](launcher-check.txt) | `python -m jarvis.launcher --check` | **ready**, no missing or incomplete components |
| [benchmark.json](benchmark.json) | `python scripts/pcide_benchmark.py --live` | Table in the architecture doc. **The live GitHub section is BLOCKED by the unauthenticated API rate limit (HTTP 403, 0 remaining)** |

`tests/test_pcide.py` has 18 tests; `tests/test_island_desk.py` gained 5. The existing Blender test rewrites `artifacts/jarvis-audit/blender-connector/natural-language-fixture.json` on every suite run. It was restored after each run.

Running `test_island_desk.py` together with `test_notch.py` in one process intermittently fails to start a second Tk interpreter. The same failure happened on the **unmodified** baseline (1 of 2 runs), so it predates this change. Each file passes on its own, and the complete suite passed.

## Scope

- GitHub responses in the tests are recorded fixtures. Rendering uses headless Chrome on local fixture pages.
- **Not exercised:** the real Qwen coding agent, live GitHub or UI-library sites (rate-limited), real React/Vite builds, npm installs, live Island animation on screen (no screenshot), and an overnight run.
- **The Groq cloud model was audited and left unchanged:** it is not connected to coding.
- No package, model, driver or browser was installed.
