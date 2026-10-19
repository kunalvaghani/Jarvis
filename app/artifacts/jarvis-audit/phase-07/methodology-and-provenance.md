# Phase 7 — AZR-inspired self-play and local LoRA training: methodology, provenance, licences

Date 2026-10-19 IST. Branch `claude`. No Codex review evidence exists for this phase.

## Pre-upgrade audit (verified on this machine)

| Item | Finding |
| --- | --- |
| Hardware | NVIDIA GeForce RTX 3050 Laptop GPU, 4,096 MiB, driver 610.74, BF16 supported; 31.3 GB RAM; 16 logical CPUs |
| `.venv-training` | Python 3.10.6, torch 2.6.0+cu124 (CUDA 12.4), transformers 4.57.6, peft 0.18.1, accelerate 1.12.0; `trl` **not installed** (not needed; GRPO probe is hand-written) |
| Trainable base | `models/qwen-jarvis-base` = original **Qwen/Qwen2.5-Coder-0.5B-Instruct** safetensors (BF16, revision `ea3f2471…`, SHA-256 pinned in `train_qwen_weights.BASE_SHA256`). The Ollama `qwen2.5:0.5b` file is a quantized inference artifact and is not used for training. |
| Existing adapters | PEFT LoRA r=8, α=16 (e.g. `brain.trained_pc_checkpoint` = `artifacts/training/qwen-pc-training-20260927T161836Z/round-2`, with `training-state.pt`). Inference compatibility re-checked in [runs/experiment-record.json](runs/experiment-record.json) (`existing_pc_adapter_compatibility`). |
| `cognition.predict()` | Laplace/Beta-posterior success estimate from procedure statistics plus rule-based effects; no learned model. Deduction tasks train the state-transition skill it would need. Nothing is wired into it in this phase. |
| Laya selector | `models/laya` (ModernBERT-large RL agent) used by `brain_worker` for `choose`; unchanged. |
| `repo_abilities` | Generates ability code with local models and validates it out of process; induction tasks train the small-function synthesis skill. Not wired in this phase. |
| `docker_runtime` / sandbox | The reviewed image `jarvis-mcp-runtime:1` (Linux, labelled) is present and is reused for induction execution. |
| `gpu_scheduler` | Process-shared lease registry; a lease cannot preempt a running CUDA kernel. Training therefore checks the registry between optimizer steps and stops (after a checkpoint) whenever Jarvis inference is active or queued. |
| Previous defects | None open from Phases 1–6. Related suites: 185 passed / 1 skipped ([log](pre-upgrade-relevant.log)). |
| Ollama export tooling | No GGUF converter (`gguf` package or llama.cpp) is installed, so Ollama registration is BLOCKED; nothing was installed. |

## Upstream study: Absolute Zero (LeapLabTHU/Absolute-Zero-Reasoner, MIT; arXiv 2505.03335)

| AZR element | What upstream does | Jarvis adaptation |
| --- | --- | --- |
| Task triplets | Programs p, inputs i, outputs o = p(i). Deduction predicts o from (p, i); abduction infers i from (p, o); induction synthesizes p from half the pairs plus a message and is checked on the hidden half | Same three reasoning modes over a **simulated computer state**. Deduction: (state, calls) → final state. Abduction: (state, desired state) → a dependency-respecting call DAG, judged by outcome. Induction: kept as program synthesis with visible/hidden cases |
| Proposer reward | Learnability r = 1 − r̄_solve, 0 if r̄_solve ∈ {0, 1}, from G solver rollouts | Same formula. The proposer is the local `qwen3.5:9b` and the solver the local `qwen3.5:0.8b` (G = 4, temperature 0.7) — a teacher/student split instead of one self-playing model |
| Solver reward / format | Binary correctness; composite −0.5 (wrong, formatted) / −1 (format error) | Same composite values in `jarvis/azr_reward.py` |
| Validity checks | Program integrity, forbidden modules, determinism (run twice) | AST screen (no imports, no `while`, no dunder or private access, no eval/exec/open…), execution twice in the container, outputs from execution only |
| Executor | Built-in Python executor described upstream as "very raw … research purposes only"; optional Sandbox-Fusion in Docker | Not used. Network-less, read-only, non-root container; one forked child per program with RLIMIT_CPU 2 s and RLIMIT_AS 160 MB, plus a 5 s wall kill |
| Training | veRL + vLLM, Task-Relative REINFORCE++ (separate baselines per task × role); 3B needs 2 × 80 GB GPUs | **Redesigned:** oracle-verified supervised LoRA SFT on a 0.5B model within 4 GB. RLVR/GRPO is only probed for feasibility (a few group-normalized updates) after SFT works |
| Safety observation | The "uh-oh moment" (concerning chains of thought from Llama-3.1-8B) | Proposals are data validated by a deterministic oracle; model text never becomes ground truth, and trained checkpoints stay experimental |

**Reused directly:** the task taxonomy, the learnability and composite reward formulas, and the determinism/safety
filter ideas. **Redesigned for 4 GB:** the training algorithm (SFT on verified targets instead of multi-GPU RL),
the executor (container instead of the raw executor), and the proposer/solver split (two small local models).
No AZR code is copied.

## Dataset (version `azr-v1-20261019`, schema 1)

* Generators are seeded; held-out, validation and train use disjoint seed ranges, and the held-out set is generated
  first. Any structure signature (tool skeleton or program family + constant) used by an earlier split is refused
  in later splits. Three induction families (`initials`, `rotate_k`, `count_k`) exist **only** in held-out data.
* Exact duplicates are removed by content hash; near-duplicates by signature (≤1 per deduction/abduction skeleton,
  ≤3 per induction family/constant).
* Answerability: deduction answers come from the simulation. Every abduction reference plan is accepted by the
  oracle in all valid orders (400/400 seeds checked). Every induction reference program passed its visible and
  hidden cases in the sandbox (0 dropped).
* Provenance on every record: generator, seed, env/oracle versions and answer source. Each split file is
  SHA-256 hashed in `manifest.json`; `load` refuses a file that does not match.
* Held-out tasks live in the sealed evaluator (`evolution_eval/heldout/azr_tasks.jsonl`); train/validation live in
  `.jarvis-runtime/azr/datasets/` and are copied into this packet.
* Proposer output: 15 accepted (10 attempts per mode), 9 rejected with reasons and the −1 format penalty.
  Every accepted proposal had solve rate 0.0 for the 0.8b solver (r_propose = 0); they are kept as train data
  because their answers are oracle-computed, and the zero learnability is recorded rather than hidden.

## Training pipeline

`scripts/training/train_azr_lora.py` (LoRA r=8, α=16, dropout 0.05 on q/k/v/o/gate/up/down; AdamW lr 2e-4 with
warm-up and linear decay; batch 1 × gradient accumulation 8; max length 896 tokens; gradient checkpointing; BF16
autocast). Explicit limits: VRAM 3,300 MB, process RSS 6,144 MB, 60 minutes, bounded steps. Checkpoints hold
adapter, optimizer, scheduler, torch/CUDA/Python RNG states, data order and position, written atomically; the two
newest are kept. Resume refuses a different base, dataset manifest or configuration. Stop reasons:
`completed`, `cancelled` (STOP file or Ctrl+C), `preempted` (Jarvis GPU lease active/pending), `resource_limit`,
`time_budget`. Training is started only by an explicit command; nothing starts it automatically.

## Evaluation and promotion

`evolution_eval/model_gate.py` (sealed with the rest of the evaluator) generates answers for the base model and the
candidate itself, greedy, in a bounded process. It scores both with the oracle and pairs them per task: seeded
bootstrap per mode and overall, with Wilson intervals for accuracies. It qualifies a checkpoint only as
`qualified_experimental`, requiring an overall gain ≥ 2 points with CI > 0, no mode regression, latency ≤ 1.5× base
and VRAM ≤ 3,500 MB. `jarvis/model_registry.py` keeps checkpoints `experimental`. Approval additionally needs a
merge-compatibility export check (≥ 95 % identical greedy outputs after merging) and an approval card, and even
then it changes no configuration, endpoint or Ollama model.

## Licences

| Component | Licence | Use |
| --- | --- | --- |
| Qwen2.5-Coder-0.5B-Instruct | Apache-2.0 (Qwen) | Base weights, trained locally; nothing redistributed beyond the local adapter |
| Absolute Zero Reasoner | MIT | Method only; no code copied |
| PEFT / transformers / torch | Apache-2.0 / Apache-2.0 / BSD-3 | Training stack already in `.venv-training` |
| qwen3.5 (Ollama, local) | Model licence per Ollama library entry | Local proposer/solver inference only |
