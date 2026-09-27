# Jarvis Qwen trained weights

Exported 2026-09-27 from `Qwen/Qwen2.5-Coder-0.5B-Instruct`, revision
`ea3f2471cf1b1f0db85067f1ef93848e38e88c25`. Upstream:
[Qwen model card](https://huggingface.co/Qwen/Qwen2.5-Coder-0.5B-Instruct).
The upstream Apache-2.0 license is retained in the local merged-model directory.

`adapter/` contains the selected rank-8 LoRA weights and its checkpoint state.
`merged-model/` contains complete FP32 weights with the adapter merged into Qwen.
The model tensors and optimizer states are deliberately Git-ignored; they remain
on this machine and must be separately transferred to use on another machine.

[Export evidence](results.json) records the hashes and measured weight changes.
[Dataset](dataset.json) records the 86 training and 14 validation projects.
The selected adapter is the first corrective round. Six gradient rounds were
actually performed across the two phases; the selected checkpoint is earlier
because later rounds regressed. It passed 7/14 validation projects versus 1/14
for the original 0.5B base. Those projects were used to select checkpoints and
are not an untouched final test set.

This is a Python JSON-CLI coding candidate. It has not been trained for speech,
vision, conversation or desktop planning, and does not replace the configured
4B production coder. The trained route excludes experience-store recall.
See [training, inference, exact resume and limitations](../../docs/qwen-weight-training.md).

For continued optimization, resume the latest third-round corrective state
documented there; the champion's saved state belongs to its earlier first round.
