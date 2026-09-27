# Dedicated Qwen model and actual weight training

Updated 2026-09-27. This pipeline performs supervised gradient updates to LoRA
parameters on a dedicated Qwen2.5-Coder-0.5B-Instruct base. It does not use the
experience JSONL store as a substitute for training. LoRA freezes the original
base parameters and trains added adapter matrices; this is parameter training,
not full-parameter retraining or pretraining a foundation model from scratch.

The 0.5B model is chosen for the local RTX 3050's 4 GB VRAM. It is smaller than
the existing Ollama Qwen3.5:4b and must not be assumed to outperform it.

## Isolated setup

Run from the application directory, with Jarvis microphone/CUDA inference stopped
using the existing Stop control before training if it is running. Training never
stops shared processes or changes the speech/brain environments.

```powershell
python -m venv .venv-training
./.venv-training/Scripts/python.exe -m pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cu124
./.venv-training/Scripts/python.exe -m pip install -r requirements-training.txt
./.venv-training/Scripts/python.exe train_qwen_weights.py --rounds 3
```

[Training dependencies](../requirements-training.txt) are optional and isolated.
The original trainable weights download into `models/qwen-jarvis-base/`; cache
files go into `models/hf-training-cache/`. Model/adapter tensor files, optimizer
state files and the environment are kept locally and ignored
by Git. No paid cloud job, Hub upload, public dataset or model publication occurs.
The upstream base revision is recorded in every training report.

## Verified dataset and held-out evaluation

The [100-project coding curriculum](coding-curriculum.md) remains a historical
inference evaluation. Only the 69 passing source solutions qualify for this
training dataset. Fresh verification on 2026-09-27 re-executed all three cases
for each: **207/207 passed**. With fixed seed 20260927, 55 entire projects become
training examples and 14 become held-out evaluation projects. The other 31
failed projects are excluded rather than teaching their incorrect answers.
See the [verified dataset](../artifacts/qwen-training-dataset-check-20260927c/dataset.json).

Held-out project prompts and completions never enter gradient updates. Their first
two examples are included in inference prompts, as in the original curriculum;
the third is withheld. Training prompts and targets have a measured maximum of
787 tokens. BF16 is used on supported CUDA hardware, otherwise FP16 with gradient scaling. Targets are never silently truncated. Examples are ordered from
easy to hard each round, with completion-only loss, rank-8 attention adapters,
gradient checkpointing, batch size one and accumulation across four examples.

Baseline and every round execute the same 14 held-out project CLIs, checking
JSON values against three independent reference cases each. Each report records
loss, project pass counts, generated sources, individual checks, adapter hashes
and absolute parameter changes. The source-policy check and five-second subprocess
deadline reduce risk but are **not an OS security sandbox**. Evaluated outputs
are restricted to the controlled curriculum, not arbitrary downloaded code.

Each completed round saves safetensors plus optimizer/scaler/RNG state. To continue:
After all requested rounds, the selected adapter is also merged into a standalone
model under `merged-model/`, containing actual modified Qwen weight matrices.

```powershell
./.venv-training/Scripts/python.exe train_qwen_weights.py --resume artifacts/RUN/round-3 --rounds 3
./.venv-training/Scripts/python.exe qwen_jarvis_coder.py --checkpoint artifacts/RUN/round-3 --prompt "Write a Python function that adds two numbers."
```

Replace `RUN` with an actual saved run. Resume rejects changed dataset/base revisions.
[Local trained inference](../qwen_jarvis_coder.py) runs on CPU to leave the GPU
available for speech; it returns source JSON and does not execute it.

## Current status and limits

The dedicated Qwen base and CUDA PyTorch are checksum-verified. The isolated
training environment passes `pip check`. The first full GPU phase completed
three rounds over 55 projects: held-out passes were 3/14, 4/14 and 3/14, compared
with the original base's 1/14. Held-out loss changed from 0.535796 to 0.348724,
0.301998 and 0.279599 respectively. The selected first-phase checkpoint is round
2. Its merged model has a measured nonzero projection-matrix difference of
110.692795 from the original base. Peak allocated CUDA tensor memory was
2,510,329,856 bytes; this is not total driver-resident VRAM.

[First complete training report](../artifacts/qwen-weight-training-20260927-cuda/results.json).
The corrective phase trained 86 projects in two request formats, including 31
checked reference corrections. Its first round passed **7/14** held-out projects.
Its second round saved all gradient updates, then evaluation failed when model
output exhausted the Python AST parser. That output was preserved and rejected
without execution; the recovered round passed 4/14. Exact optimizer/RNG resume
completed the third corrective round, which passed 3/14. The source guards now
classify excessive parser nesting as a validation failure.

Across both phases, **six gradient rounds, 681 training examples and 171 optimizer
steps** updated 1,081,344 adapter parameters. This excludes the CPU preflight.
These are repeated examples from the fixed project set, not 681 different
projects. The selected champion is the first corrective round, with 7/14 held-out
passes versus the untrained base's 1/14. These 14 projects guide checkpoint
selection, so they are validation data rather than an untouched final test set.

The [champion export](../artifacts/qwen-jarvis-trained-20260927/results.json)
contains an adapter and a standalone FP32 merged model. The merged first
attention projection differs from the original by an absolute sum of 181.524460;
its model-file SHA256 is
`ef31768db3acbbdf853e701bbe4d2f0889daaf85da45d13708d6612acb2a5181`.
Tensor files are local and Git-ignored, so reports do not imply that a clone
contains the weights.

[Corrective phase and evaluation failure](../artifacts/qwen-weight-training-20260927-corrective/results.json),
[recovered second-round evaluation](../artifacts/qwen-weight-training-20260927-corrective/recovered-round-2-evaluation.json),
and [exact resumed training](../artifacts/qwen-weight-training-20260927-resumed/results.json)
preserve the evidence separately.

A CPU preflight also performed two optimizer updates on one project, changing
1,081,344 LoRA parameters; loss fell from 0.494906 to 0.414415. This compatibility
check is separate from the full phases. [Preflight evidence](../artifacts/qwen-gradient-preflight-20260927/results.json).

Lower loss does not guarantee more passing programs: round three of the first
phase regressed in task passes. Checkpoint selection prioritizes held-out passes,
then loss. The promotion flag compares against the untrained 0.5B base, not the
existing 4B production model. Production configuration remains unchanged during
evaluation. The Python dataset does not train vision, multilingual conversation
or desktop tool planning. Repeated training can overfit; failures can recur.

Sources: [Qwen model card](https://huggingface.co/Qwen/Qwen2.5-Coder-0.5B-Instruct),
[Hugging Face PEFT](https://huggingface.co/docs/peft/index).

## Live trained-model checks

The [fresh 100-project evaluation](../artifacts/qwen-trained-projects-20260927T153849Z/results.json)
completed on 2026-09-27 using the champion adapter on CUDA BF16, with one new
generation per project and no experience recall or execution-feedback repair.
These are 100 distinct standard-library Python JSON-CLI projects from the
easy-to-hard curriculum, not 100 complete multi-file applications.

| Check | Actual result |
| --- | --- |
| Fresh project generations | 100 generated; 31 passed all three cases |
| Training-project subset | 24/86 projects passed |
| Validation-project subset | 7/14 projects passed |
| Executable source | 95 programs ran; 5 were rejected before execution |
| Executed small cases | 112/285 passed; 15 planned cases were not executed |
| Larger cases | All 10 executed; 1/10 passed |
| New invoice task through Jarvis | 0/10 cases passed |
| Standalone merged-model sum smoke | 3/3 cases passed |

The larger inputs include 400-character string comparisons, coin change for
10,000, 100-item knapsack, a 5,000-item decreasing sequence, a 500-node graph,
a 100-by-100 grid, 1,000-bin histogram, 10,000 interior water columns, and a
1,000-item sliding window. Only edit distance passed its larger case. Generated
source and each failure are retained. Training/validation overlap is explicitly
labeled; regenerating seen projects is not evidence of generalization. This
benchmark has one generation and differs from the historical 4B curriculum's
bounded repair protocol, so its aggregate score is not a matched model comparison.

On 2026-09-27, the standalone merged FP32 model loaded without a PEFT adapter,
generated a new sum CLI, and passed **3/3** cases. The initial verification
command used an incorrect relative path; its harness error is preserved, and
the corrected execution tested the same generated source.
[Merged-weight smoke check](../artifacts/qwen-jarvis-trained-20260927/merged-model-smoke/results.json).
This one easy project establishes that the full exported weights run, not that
the candidate reliably handles larger work.

A separate invoice calculator went through the actual Jarvis `BrainClient` and
Python `code_edit` route, using the selected trained adapter on CPU FP32. It
received two examples and eight withheld follow-up cases, and passed **0/10**.
Its output referenced an undefined `item` and failed at runtime. Experience
recall and result-store updates were disabled; no execution-feedback repair was
applied. [Invoice transfer evidence](../artifacts/coding-transfer-20260927T154745Z/results.json).
This new task was not used for weight updates or checkpoint selection.

## Optional Jarvis integration

After obtaining a verified checkpoint, set `brain.trained_coder_checkpoint` in
`config.json` to its application-relative directory, such as
`artifacts/RUN/round-3`. Python `code_edit` requests then run the isolated trained
coder on CPU; other languages, planning, vision and conversation retain their
existing model selection. Existing source validation, bounded repair attempts,
write approvals and atomic file handling still apply. An invalid checkpoint
fails explicitly. Remove that optional configuration key to return Python coding
to the configured Ollama planner. The production configuration has not been
changed: the trained 0.5B candidate has not met the quality needed to replace
the existing 4B coder. The dedicated weights are available for explicit use and
continued training.

Verification on 2026-09-27: all 391 regression tests passed, including five new
trained-coder route/path/timeout/no-experience/parser-fault tests, and launcher readiness reported
`ready` with no missing dependencies. These are regression/readiness checks,
not proof of model training or improved coding.

The CPU option is explicit: `--device cpu` uses FP32 and eight CPU threads. The
full recorded run uses CUDA BF16. A partial CPU baseline was preserved separately
when the CUDA installation became available; its incomplete task count is not
used as the full baseline. No speech, vision or desktop behavior was live-tested
as part of the weight-training pipeline.

## Corrective weight-training phase

`--reference-corrections` adds 31 complete source targets derived from the trusted
local curriculum reference implementations. Every target passes its three case
checks before training. These checks show consistency with the reference oracle;
they are not independent proof that its algorithms handle every possible input.
The original 14 held-out projects remain unchanged and excluded from updates,
leaving **86 training projects and 14 held-out projects across the 100-project
catalogue**. Failed model answers are never used as correct targets.

To expand a previously trained adapter onto that changed dataset, use
`--initialize-adapter artifacts/RUN/round-3 --reference-corrections --rounds 3`.
This starts from the trained weights with fresh optimizer state. Exact `--resume`
requires identical dataset and base revision instead. A matching complete prior
run can supply the original untrained baseline, with its report path recorded.

`--jarvis-variant` trains each project with both the CLI prompt and the actual
Jarvis Python-edit request wrapper. The trained Python route skips the experience
store and learned-import heuristics; it retains ordinary syntax/interface checks
and bounded validation repairs. The raw GPU benchmark uses no experience store,
repair feedback, or retained source reuse. `verify_qwen_stress.py --all-projects`
generates 100 fresh programs and checks the ten larger inputs against those
retained generated programs, labeling training versus held-out projects.

Continue training from the latest state, while using the selected champion for
inference:

```powershell
./.venv-training/Scripts/python.exe train_qwen_weights.py --resume artifacts/qwen-weight-training-20260927-resumed/round-3 --reference-corrections --jarvis-variant --rounds 1
./.venv-training/Scripts/python.exe qwen_jarvis_coder.py --checkpoint artifacts/qwen-jarvis-trained-20260927/adapter --prompt "Write a complete Python JSON CLI that sums a list from stdin."
```

More rounds can reduce validation quality. Compare executable results before
promoting a new checkpoint. Training on failed output as if it were correct is
not supported; reference corrections must pass verification first.
