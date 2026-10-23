# Project intelligence evidence — 2026-10-24 IST

These receipts are for the PIRAE candidate on `claude/cognitive-awareness`. [Architecture, commands, configuration and limits](../../docs/project-intelligence.md).

| Receipt | What it is | Result |
|---|---|---|
| [focused-regression-first-run-4-failures.txt](focused-regression-first-run-4-failures.txt) | First focused run after integration (project, awareness, cognition, queue, workflow, intent, buddy, catalog, architecture, launcher, diagnostics and UI suites) | **4 failed** / 533 passed / 7 skipped. All four came from the 800-scenario intent testbook: "create a new branch …" was taken as a project start, and "never delete file notes" stopped being a no-op. The rules were narrowed; the testbook now passes |
| [full-regression.txt](full-regression.txt) | Complete suite on the final code | **4,189 passed / 150 gated skips / 0 failures**, one existing warning, 1,104.22 s (18 m 24 s) |
| [launcher-check.txt](launcher-check.txt) | `python -m jarvis.launcher --check` | **ready**, no missing or incomplete components (Groq optional, not live-checked) |
| [benchmark.json](benchmark.json) | `python scripts/project_intel_benchmark.py` | Requirement change median 22.9 ms / p95 28.3 ms with 49 planned tasks; status question 7.9 ms; 2,000-file reference snapshot 1.15 s |

`tests/test_project_intel.py` has **48 tests**. The existing Blender test rewrites `artifacts/jarvis-audit/blender-connector/natural-language-fixture.json` on every suite run. It was restored after the run.

## Scope

- Tests use the real `TaskIngress`, scheduler, workflow graph and `DecisionManager`, temporary project roots and a **fake coding agent** that writes files. One test runs real `Actions` with its ingress and action worker threads; only `code_task` is a fixture there.
- **Not exercised:** the real coding agent, live voice, the native UI on screen (no screenshot), account connectors, a network-disabled runtime test, and a real overnight run.
- No package, model or driver was installed. PIRAE makes no model calls.
