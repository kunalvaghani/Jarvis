# Cognitive Awareness Engine evidence — 2026-10-23 IST

These receipts are for the `claude/cognitive-awareness` candidate. [Architecture, commands, configuration and limits](../../docs/cognitive-awareness.md).

| Receipt | What it is | Result |
|---|---|---|
| [baseline-focused-regression.txt](baseline-focused-regression.txt) | Pre-change cognition/anticipation/task/workflow subset, run before any source edit | **189 passed**, 22.58 s |
| [focused-regression.txt](focused-regression.txt) | The same subset plus `test_awareness`, autonomous queue, intent catalog/testbook/direct audit, buddy, catalog, architecture and launcher suites, after the change | **407 passed**, 57.59 s (34 awareness tests at that point) |
| [benchmark.json](benchmark.json) | `python scripts/awareness_benchmark.py`: admission latency with and without the engine, idle/active CPU, latency, flood, RSS | See the table in the architecture doc |
| [full-regression-first-run-3-failures.txt](full-regression-first-run-3-failures.txt) | First complete suite after the change | **3 failed** / 4,136 passed / 150 skipped. Two real bugs: `main.py` touched the self-model while awareness was disabled (UI-verification mode), and the Mind view refresh assumed the new widgets existed. Both fixed |
| [full-regression.txt](full-regression.txt) | Complete suite on the final code, run after those fixes | **4,141 passed / 150 gated skips / 0 failures**, one existing warning, 1,019.61 s (16 m 59 s) |
| [launcher-check.txt](launcher-check.txt) | `python -m jarvis.launcher --check` | **ready**, no missing or incomplete components (Groq optional, not live-checked) |

The final `test_awareness.py` has **36 tests**. An existing Blender test rewrites `artifacts/jarvis-audit/blender-connector/natural-language-fixture.json` on every suite run. That file was restored after each run, so its historical measurement is preserved.

## Scope

- All tests use simulated events, a controllable clock, owned temporary queues/stores and fixture model probes. One test drives the real `Actions` → `TaskIngress` worker → background lane end to end. **No live microphone, desktop/UI screenshot, overnight run, account connector or real compiler was used.**
- The benchmark samples real psutil, GetLastInputInfo and nvidia-smi on this PC, with a fixture model probe. It does not measure usefulness or real-world false-positive rates. There is no prior baseline for those.
- No package, model or driver was installed. The engine loads no model.
