# Phase 4 — Commands, results and classification

Run from `app/` on 2026-10-17/18 IST, `.venv/Scripts/python.exe` (Python 3.10.6), branch `claude`.

```powershell
# Preflight (before Phase 4 source changes)
.venv/Scripts/python.exe -m pytest tests/test_screen.py tests/test_screen_awareness.py tests/test_memory_index.py tests/test_memory_audit.py tests/test_memory_weather.py tests/test_obsidian_memory.py tests/test_experience_memory.py tests/test_experience.py tests/test_knowledge.py tests/test_knowledge_acquisition.py tests/test_app_research_audit.py tests/test_skill_memory.py tests/test_self_evolution.py tests/test_self_evolution_audit.py tests/test_phase01_baseline.py tests/test_phase02_execution_strategy.py tests/test_phase03_living_skills.py tests/test_desktop_actions.py -q
# Environments (separate; nothing added to .venv)
py -3.10 -m venv .venv-openviking; .venv-openviking/Scripts/python.exe -m pip install --isolated -r requirements/openviking.txt
ollama pull nomic-embed-text
# Phase 4 tests and measurements
.venv/Scripts/python.exe -m pytest tests/test_phase04_learning_memory.py -q
.venv/Scripts/python.exe scripts/verification/phase04_memory_benchmark.py --out artifacts/jarvis-audit/phase-04/memory-benchmark.json
# Real-vault read-only index measurement (scratch workspace; vault hashed before/after): see real-vault-index.json
# Regression
.venv/Scripts/python.exe -m jarvis.launcher --check
.venv/Scripts/python.exe -m pytest tests -q --junitxml=artifacts/jarvis-audit/phase-04/full-regression.xml
.venv/Scripts/python.exe scripts/verification/phase_baseline.py --label phase04-after --out artifacts/jarvis-audit/phase-04/metrics-after.json
```

Baseline note: no separate `phase_baseline` file was recorded before the Phase 4 edits. The pre-Phase-4 reference is
[Phase 3's metrics-after.json](../phase-03/metrics-after.json), recorded on the same commit (`6f88033`) immediately before
Phase 4 work began. Before Phase 4 there was no exploration capability (exploration success baseline: not applicable) and
lesson retrieval used token overlap (precision@1 0.583 on the authored oracle).

| Check | Result |
| --- | --- |
| Preflight relevant suites | 367 passed / 9 skipped ([log](pre-upgrade-relevant.log)) |
| `tests/test_phase04_learning_memory.py` | 21 passed (real isolated browser, Blender 4.4.3, OpenViking 0.5.0 server, local embeddings) |
| Full regression | **3,277 passed / 147 skipped / 0 failed**, 887 s ([log](full-regression.log), [xml](full-regression.xml)). An earlier start was stopped at 4% because Docker Desktop was not running after a reboot ([launcher-check-before-docker-start.json](launcher-check-before-docker-start.json)); Docker was started with Jarvis's own `DockerService` and the suite rerun in full. |
| Launcher `--check` | **ready** ([json](launcher-check.json)) |
| Processes after the full run | no `openviking-server` left running; Ollama `OLLAMA_MODELS` = `D:\Ollama\models` ([processes-after-regression.txt](processes-after-regression.txt); the listed shell/python lines are the probe itself) |

## Classification against the Phase 4 brief

| # | Required validation | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Safe application exploration on disposable fixtures | PASS (real) | isolated browser fixture; Blender sandbox curriculum |
| 2 | Cancellation and interruption | PASS | cancelled episode dispatches nothing |
| 3 | Restart recovery and checkpoints | PASS | in-flight step becomes uncertain, never replayed; damaged state ignored |
| 4 | UIA/API state verification | PASS for DOM/API (real); desktop UIA exploration BLOCKED (M1) | fresh DOM readback; Blender second-process readback |
| 5 | Successful and failed lesson extraction | PASS | strategy + anti-pattern, idempotent, verification-gated |
| 6 | Retrieval relevance and contradiction handling | PASS | precision@1 0.917 vs 0.583; contradiction/supersession/retraction tests |
| 7 | Obsidian source preservation | PASS (real vault + fixtures) | full-tree hash identical before/after |
| 8 | Incremental indexing and reindexing | PASS (real server) | unchanged → no work; changed file → version 2; removal |
| 9 | Memory corruption and recovery | PASS | damaged bank DB, damaged manifest, damaged exploration state |
| 10 | Idle CPU/RAM/VRAM behaviour | MEASURED (RAM, latency); GPU contention NOT RUN | server RSS ~442 MB; idle-gated maintenance |
| 11 | Compatibility with Phases 1–3 | see full regression | — |
| — | Desktop GUI exploration in a VM | BLOCKED | no verified VM backend |
| — | Live model-authored lessons / goals | NOT RUN | M3 |
