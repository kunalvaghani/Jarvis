# Stage 1 / 7 — Defects found, repairs and unresolved issues

## Phase 8 re-audit findings

| ID | Finding | New or pre-existing | Root cause / module | Action | Verification |
| --- | --- | --- | --- | --- | --- |
| D8-1 | The Phase 5 cloud architect had no production caller; the `local_replan_then_cloud_architect` route was a label only | New in Phase 5 (incomplete integration) | `deliberation.py`, `brain.py`, `cloud_architect.py` | **Fixed:** failure evidence kept per task; Brain offers advice once after 3 distinct verified failures (when enabled); approval-gated tool `cloud_architect_consult` (privacy gate → exact-payload card → consent → consult); fails closed | 4 D8-1 tests; full regression |
| D8-2 | EEVEE router/prompt co-evolution runs only from the experiment script; the idle loop perturbs the router surface generically and never evolves slot prompts | New in Phase 6 (design limitation) | `prompt_evolution.py` | **Documented, not changed:** the prompt phase needs a local LLM solver and minutes of GPU time, which conflicts with the idle-only, preemptible budget. Slot prompts stay empty by default. | Phase 6 tests + real run |
| D8-3 | One full regression stalled inside a UIA fixture test while the desktop was in active use | Intermittent; first seen in Phase 7 | Phase 2/5 UIA tests | **Mitigated:** `faulthandler` stack dumps after 180 s; replay test never falls back to window handle 0. Not reproducible in isolation (68/68) | Two later full regressions completed |
| D8-4 | `SafeEvolutionManager.evaluate` (pre-existing) adds a detached worktree to the active repository when explicitly invoked | Pre-existing | `self_evolution.py` | **Documented, not changed:** no automatic caller; Pillar C never uses it; detached worktrees are not branches | — |
| D8-5 | Citation pattern in `documents.py` contained literal backspace characters instead of `\b`, so year citations never matched and reference-list chunks were not down-weighted | **Pre-existing** (commit `d29b164f`, 2026-10-12) | `documents.py:293` | **Fixed** | `test_P08_D8_5_*`; document suites 54 passed |
| D8-6 | Tool search p50 3.26 → 3.87 ms versus Phase 1 | New (growth from 85 to 98 tools and routes) | `capabilities.rank_tools` | **Accepted, reported:** sub-millisecond absolute; not optimised | performance.md |
| D8-7 | The Phase 6 qualified DAG proposal is stale: HEAD moved and the evaluator seal changed in Phase 7 | By design | `evolution_promotion` | **Expected:** deployment refuses a stale proposal; re-run the experiment on the current HEAD before deploying | Phase 6 promotion tests |
| D8-8 | `jarvis.deerflow_model` and `jarvis.hermes_worker` do not import in the main environment | Pre-existing, by design | run inside their own environments | none | module-import-check.json |
| D8-9 | Lint: unused `time` import in `deliberation.py`; unused `exc` in `toolkits.py` | Pre-existing | — | left untouched (unrelated to the upgrade) | ruff |

## Unresolved issues and how to reproduce them

1. **Live Groq consultation BLOCKED.** No authorization was given for a real provider call. Reproduce: enable
   `cloud_architect` and `groq` on a confirmed free plan, cause three verified local reasoning failures, then say
   "ask the cloud architect …". Expected: an approval card showing the exact payload.
2. **GGUF/Ollama export BLOCKED.** Reproduce: `.venv-training\Scripts\python.exe -m scripts.training.export_azr_adapter --adapter <checkpoint> --tasks evolution_eval\heldout\azr_tasks.jsonl --out <dir>`;
   the report shows `gguf_conversion: BLOCKED`.
3. **Merge fidelity 83 %.** The same command reports 20/24 identical greedy outputs (BF16 merge rounding), which is
   below the 95 % approval bar.
4. **Desktop GUI exploration BLOCKED** (no verified VM). Reproduce: `exploration.applications` accepts only sandboxed apps.
5. **Unreal editor Python on a project BLOCKED** (no disposable `.uproject`).
6. **Physical-click demonstration NOT RUN** (a UIA Invoke stands in for the human click).
7. **Intermittent UIA stall (D8-3).** Reproduce: run `python -m pytest tests -q` while actively using another
   window. If it recurs, the log now contains every thread's stack after 180 s.
8. **Small model capability.** The qualified checkpoint solves 9/165 held-out tasks; the GRPO probe shows no reward
   variance. Reproduce with `scripts/verification/phase07_azr_experiments.py --out <new dir>`.
9. **Authored held-out oracles.** Phase 6/7 benchmarks use authored or generated labels, not user data.
