# Upgrade Phase 7 of 8 — AZR-inspired self-play tasks and safe local LoRA training

Date 2026-10-19 IST. Branch `claude` (commits in [commit.txt](commit.txt)). `main` was not modified.
No Codex review evidence exists for this phase.

**Verdict: the pipeline works end to end on the RTX 3050 4 GB. One trained checkpoint (merged form) qualified only
as *experimental*: a statistically significant but small held-out gain from a very low base (0 % → 5.5 %). It is
not promoted, not registered with Ollama (BLOCKED: no GGUF converter) and not used by Jarvis.**

Methodology, upstream study, dataset policy and licences: [methodology-and-provenance.md](methodology-and-provenance.md).
Failure handling, rollback and checklist: [rollback-and-codex-checklist.md](rollback-and-codex-checklist.md).
Raw evidence: [runs/experiment-record.json](runs/experiment-record.json), [runs/run-log.txt](runs/run-log.txt),
dataset copy [dataset/](dataset/) (manifest with hashes), sealed held-out set
[`evolution_eval/heldout/azr_tasks.jsonl`](../../../evolution_eval/heldout/azr_tasks.jsonl).
Large binaries (checkpoints with optimizer state, merged model) are kept locally in `.jarvis-runtime/azr/runs/phase07/`;
the packet keeps their metrics, configs and SHA-256 hashes. Paths `runs/<name>/...` in the experiment record
refer to that local folder.

## What was built

| Part | Files |
| --- | --- |
| B. Task engine (deduction / abduction / induction over a simulated computer state) | [`jarvis/azr_tasks.py`](../../../jarvis/azr_tasks.py) |
| B. Proposer with learnability (local qwen3.5:9b proposes, qwen3.5:0.8b solves, G = 4) | [`jarvis/azr_proposer.py`](../../../jarvis/azr_proposer.py) |
| C. Independent oracle and rewards; restricted execution | [`jarvis/azr_reward.py`](../../../jarvis/azr_reward.py), [`jarvis/azr_sandbox.py`](../../../jarvis/azr_sandbox.py) |
| D. Dataset curation (versioned, hashed, de-duplicated, leak-proof) | [`jarvis/azr_dataset.py`](../../../jarvis/azr_dataset.py), [`scripts/training/build_azr_dataset.py`](../../../scripts/training/build_azr_dataset.py) |
| E. Resource-aware LoRA SFT | [`scripts/training/train_azr_lora.py`](../../../scripts/training/train_azr_lora.py) |
| F. Generation, sealed model gate, export check, GRPO probe, registry | [`scripts/training/azr_generate.py`](../../../scripts/training/azr_generate.py), [`evolution_eval/model_gate.py`](../../../evolution_eval/model_gate.py), [`scripts/training/export_azr_adapter.py`](../../../scripts/training/export_azr_adapter.py), [`scripts/training/grpo_feasibility.py`](../../../scripts/training/grpo_feasibility.py), [`jarvis/model_registry.py`](../../../jarvis/model_registry.py) |
| Orchestration of the real runs | [`scripts/verification/phase07_azr_experiments.py`](../../../scripts/verification/phase07_azr_experiments.py) |

## Results (2026-10-19, RTX 3050 Laptop 4 GB, Python 3.10.6, torch 2.6.0+cu124)

| Check | Result | Classification |
| --- | --- | --- |
| Preflight related suites | 185 passed / 1 skipped | PASS |
| Phase 7 tests (generators, oracle with multiple correct answers, unsafe-program screen, hostile code in the sandbox, reward values, leak-free dataset, tamper-evident manifests, proposer ignores model answers, learnability formula, trainer bounds, foreground check, registry gating, unsealed gate refusal) | 21 passed | PASS |
| Dataset `azr-v1-20261019` | train 914 (409 ded / 404 abd / 101 ind incl. 15 proposer tasks), validation 90, held-out 165 (60/60/45); leakage 0 ids / 0 signatures; 0 unanswerable | PASS |
| Proposer (10 attempts per mode) | 15 accepted, 9 rejected (format penalty); every accepted task had solver solve rate 0 → r_propose 0 | PASS (pipeline); learnability signal absent |
| Existing PC adapter (`round-2`) still loads and generates with peft 0.18.1 | yes | PASS |
| Cancel at step 2 + exact resume | losses identical to an uninterrupted run (max diff 0.0) | PASS |
| Foreground preemption (real `question` lease) | trainer stopped `preempted` at step 3 with a checkpoint | PASS |
| Main LoRA SFT (120 steps × 8, 1 epoch) | 9.6 min, peak VRAM 1,994 MB, RSS ≤ 2.6 GB, loss 0.58 → 0.09 | PASS (ran within budget) |
| Held-out gate, adapter (unmerged) | 10/165 vs base 0/165 (+6.1 pts, CI [2.4, 9.7]) but latency 0.83 vs 0.48 s/task (ratio 1.74 > 1.5) | **REJECTED** (pre-registered latency budget) |
| Held-out gate, merged model (same policy) | 9/165 vs 0/165 (+5.5 pts, CI [2.4, 9.1]); induction 7/45 unseen families, deduction 2/60, abduction 0/60; 0.48 vs 0.55 s/task; 1,130 MB | **qualified_experimental** |
| Export compatibility (adapter vs merged, 24 prompts) | 20/24 identical greedy outputs (83 %); merged model reloads with transformers | Below the 95 % approval bar |
| GGUF / Ollama registration | no converter installed | BLOCKED |
| RLVR/GRPO feasibility (4 tasks × group 4) | 1.1 GB VRAM, ~6 s per step; all sampled answers wrong → zero reward variance → no update | NOT PURSUED (no learning signal yet) |
| Full regression (rerun) | **3,361 passed / 147 skipped / 0 failed** (16 min 52 s) | PASS |
| First full-regression attempt | stalled inside a UIA fixture test at about 63 % while the desktop was in active use; stopped via the task manager; not reproducible in isolation | Recorded defect (diagnostics added) |
| `python -m jarvis.launcher --check` | `ready` | PASS |

**Interpretation.** The base model scored 0/165 and could not produce a valid abduction plan at all (0/60
well-formatted). After SFT the adapter produces well-formed plans (60/60) but rarely correct ones. The measurable
gain is in induction on program families never seen in training (0 → 7/45; 2 more passed only the visible
examples). The training loss fell from 0.58 to 0.09 while held-out accuracy reached only about 6 %, so **loss is
not evidence of reasoning improvement**, and no broader claim of improved intelligence is made. The model is
not wired into `cognition.predict()`, the planner, the laya selector or `repo_abilities`.

**Latency finding.** The rejected adapter wrote *shorter* answers than the base (e.g. abduction 97 vs 228 tokens)
but cost about 2× per token, because unmerged LoRA layers add work at every step. The merged model removes that
overhead. The same, unchanged policy was applied to the merged model as a second candidate. Merging in BF16 changed
4/24 greedy outputs, which is why the export check is below the approval bar.

## Measurements

| Item | Base | Merged candidate | Adapter candidate |
| --- | --- | --- | --- |
| Held-out accuracy (Wilson 95 %) | 0.0 % [0, 2.3] | 5.5 % [2.9, 10.0] | 6.1 % [3.3, 10.8] |
| Deduction / abduction / induction | 0/60 · 0/60 · 0/45 | 2/60 · 0/60 · 7/45 | 2/60 · 1/60 · 7/45 |
| Format-valid abduction plans | 0/60 | — | 60/60 |
| Generation p50 per task (batched, greedy) | 0.48–0.55 s | 0.48 s | 0.83 s |
| Peak VRAM during evaluation | 1,130 MB | 1,130 MB | 1,258 MB |
| Training: peak VRAM / RSS / wall time | — | 1,994 MB / 2.6 GB / 9.6 min | same run |

The two base measurements (0.48 s and 0.55 s) come from two separate runs: the first and second gate evaluations.
The second was regenerated after the evaluator was re-sealed. The difference is run-to-run noise.

## Limitations

- Tiny absolute performance: even the qualified checkpoint solves only about 1 in 18 held-out tasks.
- All tasks are synthetic and authored by this phase's generators. Real Jarvis workloads were not evaluated with
  the trained model.
- The proposer and solver are different local models (teacher/student), not one self-playing model as in AZR, and
  the 0.8b solver solved none of the proposed tasks, so learnability gave no signal.
- Induction training data is small (101 tasks over 11 families) because of the near-duplicate caps.
- GRPO was only probed; with near-zero accuracy there is no reward variance to learn from.
- One full-regression attempt stalled inside a UIA fixture test while the desktop was in active use. It was not
  reproducible in isolation (68/68 passed) and the rerun passed. Stack-dump diagnostics were added to both UIA fixtures.

## Baseline harness

[metrics-before.json](metrics-before.json) → [metrics-after.json](metrics-after.json): intent routing 2,400/2,400, privacy routing 0 private marked public, DAG success 1.0, 97 tools, 20/20 skill goals. Latencies are unchanged within noise (Phase 7 adds no runtime path).
