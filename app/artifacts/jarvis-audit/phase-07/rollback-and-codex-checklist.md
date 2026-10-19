# Phase 7 — Failure handling, rollback and independent Codex verification checklist

No Codex review evidence exists for this phase.

## Failure handling

| Situation | Behaviour |
| --- | --- |
| Jarvis needs the GPU during training | The trainer sees an active or pending lease, writes a checkpoint and exits `preempted` (verified at step 3 with a real `question` lease) |
| User cancels | Create `<run>/STOP` or press Ctrl+C. The trainer checkpoints and exits `cancelled`; `--resume` continues bit-for-bit (losses matched the uninterrupted run exactly) |
| VRAM/RAM/time budget exceeded | Checkpoint, then exit `resource_limit` / `time_budget` |
| Dataset, base model or configuration changed | Resume refuses (manifest/base/config hash mismatch) |
| Model-written code misbehaves | Static screen first; then a forked child in the network-less container with CPU, memory and wall limits; failure costs only that program |
| Proposer writes garbage | Rejected with the −1 format penalty, logged and never added to a dataset |
| Trained model is worse or slower | The sealed gate rejects it; the registry keeps it `experimental`; nothing in Jarvis uses it |

## Rollback

```powershell
git revert --no-edit 1a1e778 1d55c21 b6662ef caffdd8     # on claude, newest first
```

Nothing in production loads the new adapter, so no runtime rollback is needed. Local state (ignored by Git):
`.jarvis-runtime/azr/` (datasets, run checkpoints, merged export) and `.jarvis-runtime/models/registry.json`.
Existing model settings (`brain.trained_pc_checkpoint`, Ollama models) were not changed.

## Checklist

1. [ ] `python -m pytest tests/test_phase07_azr_training.py -q` → 21 passed (the sandbox test needs Docker and the `jarvis-mcp-runtime:1` image; otherwise it skips as BLOCKED).
2. [ ] Read `jarvis/azr_tasks.py`: `apply`/`execute` semantics; `check_abduction` checks every conflicting pair is ordered and every topological order reaches the goal.
3. [ ] Try to falsify: hand-craft a second correct abduction plan and confirm it is accepted; drop one dependency and confirm `missing_dependency`.
4. [ ] Read `jarvis/azr_sandbox.py` HARNESS: fork per program, RLIMIT_CPU/AS, wall kill, double execution, restricted builtins; the container flags are in `mcp_synthesis.server_config`.
5. [ ] Confirm the reward code (`jarvis/azr_reward.py`) depends only on the task and answer text, never on stored model answers.
6. [ ] Check `dataset/manifest.json`: leakage zero for ids and signatures; held-out induction families absent from train.
7. [ ] Recompute the gate comparison from `runs/gate-base/*.answers.jsonl` and `runs/gate-candidate*/` with `jarvis.azr_reward.score_all`.
8. [ ] Confirm the decision was taken under the policy committed **before** results were seen (`policy.json` `model_gate`; the only later evaluator change adds merged-model support, not thresholds).
9. [ ] Confirm no claim of improved intelligence rests on training loss (loss 0.58 → 0.09 while held-out accuracy reached only 6 %).
10. [ ] Confirm nothing was registered with Ollama and `config/config.json` model settings are unchanged.
