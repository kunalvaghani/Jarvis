# Hierarchical upgrade benchmarks and acceptance

**2026-10-15 audit follow-up:** [Prompt10](../artifacts/jarvis-audit/modules/10-dag-planning/inventory.md)
adds paired source-fingerprint timing/allocation measurements, exact catalog
assertions and regression/readiness evidence. These component fixtures are
separate from the historical 2026-10-14 native-model and controlled-I/O results
below. No new end-to-end model, speech or live account latency claim is made.

Measured 2026-10-14 IST. The [baseline](../artifacts/reports/hierarchical-baseline.json)
was collected before production edits. Existing uncommitted conversation/F5 work
was part of that baseline and was preserved. The dedicated branch is
`codex/hierarchical-dag-upgrade`.

## Comparable original/upgraded component runs

The same [driver](../scripts/verification/verify_hierarchical.py) runs both modes.
It uses six identical parser inputs in 100 batches, three authored five-step real
file workflows, two controlled safety scenarios, and five trials of three real
ToolRegistry file reads with an explicit **100 ms artificial delay per read**.
The authored workflow's planner/decision/verification oracles are controlled;
they do not measure model reasoning or real desktop success.

The [final idle upgraded run](../artifacts/reports/hierarchical-upgraded.json)
followed completion of live model inference. An earlier
[contended run](../artifacts/reports/hierarchical-upgraded-contended.json)
is preserved: its parser median was 4.947 ms and parallel median 0.172 s while
large-model planning was active. This exposed CPU contention rather than a
universal routing slowdown. Conditions cannot be perfectly identical on a shared
Windows laptop; process start and short file operations remain noisy.

| Metric | Original Jarvis | Upgraded Jarvis | Change / scope |
|---|---:|---:|---|
| Full application startup | Not measured | Not measured | No microphone/UI startup comparison. |
| Fresh-process imports of Actions/Brain/commands | 0.783 s | 0.740 s | -5.5%; one process trial, not application startup. |
| Routing median batch-average per input | 2.524 ms | 2.217 ms | -12.1%; 100 six-input batches. |
| Routing p95 batch-average per input | 3.704 ms | 3.775 ms | +1.9%; not an individual-command latency percentile. |
| Simple command full execution | Not measured | Not measured | Parser measurements do not establish app-launch latency. |
| Authored five-step file workflow median | 0.281 s | 0.328 s | +16.7%; existing sequential path preserved, no claim of universal speedup. |
| Controlled parallel workload median | 0.332 s | 0.132 s | **2.52× speedup**, -60.3%; artificial delay plus real scoped file reads. |
| Controlled parallel result correctness | 5/5 | 5/5 | All expected contents matched. |
| Authored file workflow success | 3/3 | 3/3 | Real effects plus controlled planning/verification oracles. |
| Authored workflow planner calls | 1 per task | 1 per task | Existing path unchanged. |
| Uncertain-effect safety scenario | Paused after 1 dispatch | Paused after 1 dispatch | No replay; resumed actions blocked pending inspection. |
| Cancellation safety scenario | Cancelled after 1 dispatch | Cancelled after 1 dispatch | No later task dispatch. |
| General recovery success rate | Not measured | Not measured | Controlled cases do not establish a population rate. |
| Peak benchmark-process working set | 38.934 MiB | 38.457 MiB | -1.2%; excludes worker processes, model server and GPU memory. |
| End benchmark-process RSS | 38.934 MiB | 38.328 MiB | -1.6%; not whole-machine peak RAM. |
| Benchmark-process CPU user + system time | 5.750 s | 6.234 s | +8.4%; complete benchmark lifetime, not utilization or power. |
| Peak VRAM / GPU utilization / power impact | Not measured | Not measured | Baseline idle GPU snapshot was 0 MiB / 0%; this is not peak use. |
| Voice first audio / microphone-to-speaker | Not measured | Not measured | Earlier F5 measurements remain [separate historical evidence](f5-voice.md). |
| Model first-token / warm-vs-cold model distribution | Not measured | Not measured | One actual planner check below; no comparative model latency set. |

The new parser maps battery and “show CPU usage” to existing deterministic status
handlers; previously battery fell through to a general question and the CPU phrase
was unparsed. Chrome/VS Code launch and Stop commands retain their kinds. “Read my
notes” remains ambiguous/unparsed. These observations are coverage, not a large
manually labeled semantic-accuracy evaluation.

Short sequential file work did not improve. Its observed 47 ms median increase
was reviewed alongside import timing and the preserved executor; there is no
reason to force such workflows through DAG planning. The measured advantage is
overlapping independent delayed I/O. Zero-delay dispatch can cost more in a pool
than serial direct calls.

## Actual local planner and real files

The [live result](../artifacts/reports/hierarchical-live.json) uses the installed
`qwen3.5:9b`, the existing owned Brain worker, native Ollama schema decoding,
production graph admission/scheduling, ToolRegistry and two synthetic local files.
No authored planner output substituted for the final live model result.

- Total task: **94.812 s**; planning/admission timing: **94.703 s**.
- Both file nodes ran successfully with empty dependency lists; each tool read
  took about **15–16 ms** in this run and contents matched independent readback.
- One final proposal was accepted. Earlier two live runs produced empty folder
  fields even after a bounded repair and were rejected before tool execution.
- The corrected tool-specific constrained schema requires a nonempty folder;
  the final proposal supplied `this folder` and completed without repair.

This proves one actual local-model/file integration, not reliable planning for
all possible user goals. Large-model generation dominates latency. Exact literal
read lists and compatible verified read-plan hits avoid planning entirely. Existing
model routing remains configured; no unverified small model replaced the planner.
Cloud/Groq calls were not made for this check. Native UI, external services and
Unreal Blueprint edits were not executed.
An additional [authored graph integration](../artifacts/reports/hierarchical-write-integration.json)
passed a real `read_file → create_file → read_file` chain through DAG/ToolRegistry/
Actions in **0.094 s**, creating only an isolated fixture file. Independent disk
contents were exactly `ready`; each step dispatched once. This uses an authored
plan, not model reasoning or a comparative performance baseline.
This live check preceded the final path-admission, timing and optional solver
corrections; those received regression checks, rather than another live semantic
model-quality trial. The read-only live result remains component evidence.

## Regression, recovery and security

The original full suite passed **1,750 tests in 292.424 s** before production
changes. An intermediate full run passed **1,764 tests in 284.330 s**. The corrected
targeted suite passed **233 tests**; its earlier invocation also named a nonexistent
`tests.test_agent_tools` module, causing one invocation error. That name was
removed; it was not an application regression.

The final DAG-specific suite passed **15 tests**. Cases/subtests cover:

- Missing tools, invalid schemas, duplicate IDs, forward dependencies, cycles,
  wrong permission declarations, impossible GPU reservations and invalid retries.
- Real overlap of independent reads and dependency gating using synchronization.
- Typed output lookup, absent lookup paths and task result isolation.
- Read retry backoff, deterministic verification failure and downstream blocking.
- Write failure with exactly one dispatch and no checkpoint replay.
- Cancellation/timeout worker draining, serialized effects, durable state before
  effects, interrupted restart blockers and repeated-run thread cleanup.
- Real Actions/ToolRegistry file reads and fresh readback; compatible macro reuse
  with no additional planner call; targeted missing-file replanning without
  repeating the successful independent read.
- Summary/comparison requests use the existing real local `think` adapter after
  collecting observations, rather than treating raw results as a completed
  analysis. Its interface/grounding is tested with a controlled model response;
  semantic output quality and live solver latency were not benchmarked.
- Existing policy denial before effects, battery/CPU reflex routing and genuine
  planning protocol activity under diagnostic stdout redirection.

**Final release checks:** **1,765 tests passed in 282.169 s**, including the final
path-admission, protocol, timing and semantic-solver corrections. Launcher readiness
reported **`ready`**, with no missing or incomplete dependencies/configured services.
The [machine-readable validation record](../artifacts/reports/hierarchical-validation.json)
contains final source hashes and links these component outcomes. No remaining test
failures were observed. This is regression/readiness evidence, not the unperformed
live production acceptance listed below.
Initial sandbox restrictions on temporary-file replacement and local service
access required unrestricted regression/readiness commands. No approval review
rejected the upgrade. Actual file fixtures stayed under owned runtime/scratch
directories; no user documents, account messages or external writes were used.

## Technical assessment and remaining production scope

The implemented core includes typed planning/validation, real registered adapters,
bounded parallel scheduling, resource conflicts, deterministic file verification,
read-only recovery, persistent checkpoints, safe restart rules, exact verified
read-plan caching, monotonic timing and feature rollback. Legacy commands, model
providers, memories, tools, UI/voice and specialized executors remain in place.

The following are intentionally limited rather than represented as complete:

- Arbitrary UI/MCP/terminal actions remain on existing approval/observation paths.
  They are not safe to parallelize from stale or incomplete plans.
- Retrieved facts and semantic whole-goal correctness are not proven by transport
  validation. A valid model graph may omit needed work.
- Automatic effectful macro reuse, arbitrary rollback and speculative actions
  from unfinished plans are disabled.
- The configured Unreal Editor launcher is preserved. No registered Blueprint
  compile/edit API was found, and no user UE project or authorized API endpoint
  was supplied; that native integration is not implemented or claimed.
- Additional model-role selection based on learned structured-planning reliability
  needs a labeled evaluation set. Existing installed-model/configuration/GPU/cloud
  policies were reused; no new model was downloaded or assumed suitable.
- Thread cancellation is cooperative; backend timeouts bound an uncooperative
  synchronous call. Resource reservations do not impose OS RAM/CPU limits.
- Thirty repeated executor runs verify thread cleanup in a bounded test, not a
  multi-hour soak test or proof against all leaks, orphaned third-party processes
  or hardware contention.
- Live microphone, speaker, browser-account, sending, UI, and specialized external
  integration acceptance remain unmeasured in this upgrade.

These are the production acceptance boundaries. Passing readiness and regression
does not certify every connected account, arbitrary autonomous task, or a universal
two-second response. [Rollback instructions](hierarchical-execution.md#checkpoints-caching-and-rollback)
restore the original executor without removing application data.
