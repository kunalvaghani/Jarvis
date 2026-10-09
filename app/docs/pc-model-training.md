# PC context and dedicated Qwen training

Updated 2026-09-27. Jarvis now supplies fresh, bounded PC metadata to its plan,
replan, coding and PC-question inference. It uses configured project roots,
folder/file aliases and the existing SQLite file index. Project names, exact
paths, project markers, matching application names, processor architecture and
configured local-model names are reference data. File contents, credentials and
private-looking entries are excluded from this metadata feature.

Project discovery remains bounded to the configured roots and shallow levels.
Explicit container roots now include child project directories even when they
have no Git/package marker yet; drive roots still require project markers.
Dependency, model, training-environment and artifact directories are skipped.
The prompt contains up to 20 relevant entries. It does not inspect every file
or every document. Indexed file lookup is performed only for short name/location
requests, rather than scanning the whole index for a long coding goal. Existing
project and catalog actions revalidate destinations before opening them.

Examples: `open project FinanceAgent`, `open Downloads folder`,
`where is my Jarvis project?`, or `fix the parser in project Jarvis`.
The existing scoped source reader supplies code context when actually working
inside a selected project. This metadata feature does not bypass write,
deletion, shell-command or external-service approvals.

## Actual model training

[PC trainer](../scripts/training/train_pc_qwen.py) starts from the previously trained coding Qwen
adapter, using the same checksum-verified Qwen2.5-Coder-0.5B base. It performs
real LoRA forward/backward passes and AdamW optimizer updates. It saves a
separate PC adapter, preserving the coding checkpoint. The task is structured
name resolution, not unrestricted desktop action generation.

The corrected local dataset has 224 training examples and 32 withheld checks.
Two completed rounds performed **448 gradient examples and 112 optimizer steps**,
updating 1,081,344 LoRA parameters. Before PC training, the coding checkpoint
passed 4/32 checks. The first PC round passed 28/32; the second passed 32/32 when
ambiguous path lists are compared without regard to order. The original strict
second-round score is preserved as 31/32: its one discrepancy was path order,
not a missing or invented path. Selection used these validation checks.
Targets are derived from current metadata, with exact path-copying, missing
names, duplicate basenames and synthetic relocated paths. Real entries provide
the names; relocation examples are explicitly labeled synthetic. Withheld
request wording shares entity names with training, so this is not a test of
generalization to an entirely unseen PC. The dataset contains metadata only,
not file contents. Its artifacts are Git-ignored and remain local.

A first run was stopped when a fixture exposed incorrect handling of literal
project names beginning with “My” or ending with “Project”. That run is preserved
as superseded. Corrected targets are checked against each known entity before
any optimizer update. Only corrected runs count toward the reported results.

```powershell
./.venv-training/Scripts/python.exe -m scripts.training.train_pc_qwen --rounds 2
./.venv-training/Scripts/python.exe -m scripts.training.train_pc_qwen --resume artifacts/PC_RUN/round-2 --rounds 1
```

Replace `PC_RUN` with a completed local run. Exact resume restores optimizer and
Torch RNG state and reuses the identical saved dataset. To train against an
updated inventory, start a new run with `--initialize-adapter` pointing to the
previous PC adapter; this starts fresh optimizer state on the new dataset.

## Runtime and limitations

The selected adapter is configured at
`artifacts/training/qwen-pc-training-20260927T161836Z/round-2`. A full FP32 merged PC model
is also saved in that run's `merged-model/` directory. It has SHA256
`0d9de7464fb5da3071667e5a221031c77d8c549171fee006cf14abcddd0e49a6`
and a measured first-projection absolute weight difference of 202.485352 from
the original Qwen base. Adapter and full-weight files are local and Git-ignored.

Live metadata is active without a new model setting. An optional
`brain.trained_pc_checkpoint` can point to a saved PC adapter. For simple
open/show/find/locate plans, it invokes read-only inference through
[the isolated CPU resolver](../scripts/training/qwen_pc_resolver.py), with a 60-second deadline.
The returned schema and every path must agree with fresh exact-name candidates
and existing filesystem paths. Ambiguous matches remain ambiguous. Missing,
invalid, stale or timed-out predictions fall back to the fresh context. The
model never executes an action. Direct project-open commands continue using
the existing deterministic project resolver.

On 2026-09-27, fresh trained-model generations on real PC metadata passed
**11/13** requests, including project/folder lookups and a missing-project check.
The two incorrect results were rejected by live-path validation. An earlier
11/13 run lacking the runtime kind hint is preserved separately. These checks
used CUDA BF16; a real isolated CPU FP32 request also passed. The model is not
the authority on a path: fresh exact-name lookup remains the safe fallback.
Separately, **12/12** real project/folder metadata checks passed after a project
versus ordinary-folder disambiguation fix. An initial 10/12 check is retained.
All these checks were read-only; no application or user project was opened.

[Aggregate training evidence](../artifacts/reports/pc-training-summary-20260927.json),
[live metadata checks](../artifacts/reports/pc-context-live-checks-20260927.json), and
[actual CPU trained inference](../artifacts/reports/pc-trained-cpu-check-20260927.json)
contain dated aggregate evidence. The raw inventory, dataset, model responses
and paths remain in Git-ignored `artifacts/qwen-pc-*` directories.

The adapter learns how to use metadata; it cannot reliably memorize a changing
disk. Fresh context is essential when files move or new projects appear. Runtime
metadata refresh does not silently launch training. Repeated weight updates are
an explicit local training command. Speech, vision and the general 4B planner
are not replaced by this specialized 0.5B adapter.

PC questions use local inference and do not pass this context to web search.
Private metadata datasets and model tensors must not be published with the
repository. No cloud job, Hub upload or microphone restart is performed.

Regression verification on 2026-09-27: 398 tests passed, including metadata
freshness, ambiguity, training-label integrity, trained-result validation,
bounded timeout and private-context web isolation. Training results and live
path checks are recorded separately from these regression checks.
