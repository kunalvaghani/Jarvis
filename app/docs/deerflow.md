# DeerFlow and Jarvis — 2026-10-13–14 IST

<!-- prompt28-audit -->
**Sandbox/DeerFlow audit — 2026-10-16 IST:** Stronger mount/checkpoint/identity/write/timeout guards and media proof added. **20 catalog fixture PASS / 12 BLOCKED**; full regression **3,065 passed / 124 skipped / 0 failures**, launcher **ready**. Owned offline math, all seven literal media recipes and nonzero/no-replay/cleanup fixtures passed; format proof levels vary. General research/source-quality, approval/quota/privacy/resource/recovery and platform patch acceptance remain incomplete.
[Evidence, limitations and rollback](../artifacts/jarvis-audit/modules/28-sandbox-deerflow/inventory.md).
<!-- /prompt28-audit -->

The full ByteDance DeerFlow repository was downloaded locally, including backend,
frontend, public skills, tests and documentation. The reviewed revision is
`a5e71751d7a9f8f4a71ca458da3984fc1284d098` (DeerFlow 2, backend `2.2.0-dev`,
harness package `2.1.0`). The full-history checkout is at
`integrations/deer-flow-upstream`; a second shallow download is retained at
`integrations/deer-flow`. Both are ignored; the portable
[source manifest](../integrations/deerflow/source-manifest.json),
[MIT permission notice](../integrations/deerflow/LICENSE), integration code and
[resolved optional dependencies](../requirements/deerflow.txt) are tracked.

The upstream GitHub page was inspected using the Firecrawl connector; source
inspection then used the local checkout. Connector credentials are never exported
to Jarvis. Its existing Firecrawl tools still need `JARVIS_FIRECRAWL_KEY`.

## What DeerFlow does and how it fits

DeerFlow's embedded `DeerFlowClient` builds a LangGraph lead agent with model
selection, middleware, tools and optional subagents. Its full product includes
a web UI and gateway, persistent memory, skills, uploads, generated artifacts,
context summarization, task notes, sandbox execution, MCP integrations and
research/media/document workflows. Its result-verification code distinguishes
an agent's self-report from receipts and actual acceptance checks.

| Area | Jarvis before this update | Combined implementation |
| --- | --- | --- |
| Windows voice/UI/actions | Native voice, island, guarded desktop/browser tools | Existing Jarvis execution retained |
| Source research | Scoped sessions, read batches, local Qwen, limited parallel research | Adds the real embedded DeerFlow harness as a project research tool |
| Public web research | Public search/page tools and separately configured Firecrawl | Adds bounded DeerFlow research using the same public adapters, with source receipts and observed links |
| Skills | Jarvis, repository and Hermes skills | Adds exact-name access to all 23 DeerFlow public skill guides |
| Source evidence | Requested source-read gate and session events | Adds upstream receipt parsing, stable per-turn source IDs, output hashes and invalid-citation rejection |
| Local model compatibility | Imported Qwen template handling and inference admission | DeerFlow uses the same code through a LangChain adapter |
| Untrusted references | Existing scoped tools and policy checks | Adds upstream framework-tag and boundary-token neutralization for DeerFlow source results and guides |
| Memory/checkpoints | Existing Jarvis memory and safe task checkpoints | Preserved; DeerFlow uses an in-process checkpointer for its bounded request |
| Shell/sandbox/accounts | Existing guarded Jarvis workflows | Unrestricted upstream execution is excluded from this research adapter |

Public guides cover deep research, GitHub research, academic reviews, systematic
literature reviews, data analysis, charts, code documentation, consulting,
frontend/web design, newsletters, slides, podcasts, image/video/music generation,
skill creation/review/discovery, bootstrap and migration/deployment workflows.
Reading a guide does not establish that its required services, dependencies or
account credentials are available.

## Use

The normal planner discovers `deerflow_status`, `deerflow_skill_search`,
`deerflow_skill_read`, `deerflow_research` and `deerflow_web_research` through the shared registry.
Standard `skill_list` and `skill_read` also accept `folder=@deerflow`; list uses
task keywords or dot for all guides, and read uses an exact listed guide name.
These make the upstream workflows available to the existing skill mechanism
without importing their scripts. Mentioning DeerFlow selects the tools
through the capability router. Research requires an identified local project
folder; it offers only `read_file`, `list_files`, `search_files` and
`repository_map`, through Jarvis's normal scoped registry. It returns an answer
and actual successful source-read receipts. The answer remains a model report.

`deerflow_web_research` is a separate public-source tool. It receives a topic or
public URL with no local project context. It offers public search/page fetches
through Jarvis's existing adapters, using `JARVIS_FIRECRAWL_KEY` when separately
configured, otherwise the public search/page readers. Only that named Jarvis key
can enter this mode; unrelated credentials and Codex connector credentials are
excluded. Network destinations and redirects pass Jarvis's public-URL checks.
No account, browser interaction, upload or write tools are offered. Explicit
URLs are read before inference; a report with no source observations is withheld.
The page reader includes up to twenty observed HTTP(S) links without following them.

For a direct text check from `app/`:

```powershell
.venv/Scripts/python.exe -m jarvis.deerflow_cli --project examples --goal "Inspect this project's source and explain its entry points with source citations."
```

The default local model is `qwen3.5:4b`. CLI `--model` and `--timeout` select a
model and bounded deadline. The normal Jarvis tool can use an optional top-level
`deerflow` configuration object with `model` and `timeout_seconds` (default 180,
allowed 5–600 seconds; public web defaults to 300). This does not replace Jarvis's primary planner.

Each request starts one hidden owned worker in `.venv-deerflow`, passes bounded
JSON, and terminates the worker on cancellation/deadline. Research starts no
service and never restarts/replays actions or kills a shared model service.
The later [sandbox extension](deerflow-sandbox.md) adds background Docker availability
recovery. State/configuration stays under `.jarvis-runtime/deerflow`. Upstream
memory injection/extraction, skill evolution, subagents, task continuity and host
bash are disabled in this adapter. Jarvis retains its own implementations.

## Install and relocation

Jarvis's main Python 3.10 environment remains independent. The full harness and
its resolved dependencies run in optional Python 3.12, declared in the runtime
manifest. From `app/`, with Git and `uv` available:

```powershell
.venv/Scripts/python.exe -m scripts.setup.setup_deerflow
```

Setup can also use `.venv-hermes-bootstrap/Scripts/uv.exe`. It downloads the
complete repository if absent, selects the reviewed revision, and refuses to
silently reset an existing checkout at another revision. It installs the local
harness and extension contract packages using `requirements/deerflow.txt` and
performs an import check. Initial source, Python and dependency downloads need
network access. Recreate the optional environment after relocation; installed
local-package paths belong to the old checkout. Jarvis does not require this
environment to start.

## Measured checks and limitations

The matched benchmark uses three synthetic Python source-reading tasks with the
same local `qwen3.5:4b`: arithmetic, filtering and an exception. Each is one trial,
with a successful source read, expected-answer substring and source-path citation
required. Answers and times are saved. This inspectable heuristic is not a
general accuracy, coding, web research or AGI score.

Original Jarvis read each source but failed all three tasks by repeating reads.
The native provider expected `observations` while the session supplied
`completed`; the prompt also failed to explicitly acknowledge pre-reads. The
update supplies both names and receipts and asks the model to answer from
successful reads. The first updated run passed 3/3. Its timings overlapped
adapter diagnostics and do not establish a reliable speedup.

- [Original Jarvis baseline](../artifacts/reports/deerflow-ollama-baseline.json)
- [First updated Jarvis run](../artifacts/reports/deerflow-ollama-hybrid.json)
- [Initial DeerFlow adapter failure record](../artifacts/reports/deerflow-upstream-scoped.json)

The initial DeerFlow run failed all three checks before producing an answer:
the adapter's graph-node recursion budget was too small for DeerFlow's middleware
chain. This is an integration failure, not a measured task-accuracy score for
stock DeerFlow. The adapter was corrected to use a separate 100-node graph budget;
reads remain capped at 12 and the worker retains its wall-clock deadline.

The next adapter check exposed a missing `psutil` dependency from Jarvis's shared
model code, recorded in the [dependency-failure report](../artifacts/reports/deerflow-upstream-final.json).
It was installed and declared in the isolated requirements; those failures are
not a stock-DeerFlow accuracy measurement.

Final sequential runs on 2026-10-14 IST:

| Runtime/check | Tasks passed | Mean wall time per task |
| --- | --- | --- |
| Original Jarvis baseline | 0/3 | 101.896 s, failed repeated-read loops |
| First updated Jarvis run | 3/3 | 90.187 s, overlapped diagnostics |
| Updated Jarvis repeat | 2/3 | 56.682 s |
| DeerFlow harness with Jarvis source adapter | 3/3 | 75.990 s |

The [updated Jarvis repeat](../artifacts/reports/deerflow-ollama-final.json) gave
the wrong arithmetic answer (`39` instead of `37`) despite a successful read.
The [integrated DeerFlow run](../artifacts/reports/deerflow-upstream-integrated.json)
answered all three correctly. Both used the same local model. Updated Jarvis was
faster in these final trials; DeerFlow answered more correctly in this tiny set.
There are too few trials for a statistically reliable winner, warm/cache and
prompt effects differ, and a receipt never proves a model's arithmetic correct.
The DeerFlow exception answer used an upstream virtual file URL; a subsequent
operator prompt overlay now requests only the real observed relative paths.
The original saved response is preserved rather than rewritten.

The dynamic integration check passed on 2026-10-14: with no filename in the goal,
the real harness chose `observe/read_file`, read `sample.py` and correctly reported
the literal `314159`, through the normal Jarvis registry. It took 119.593 seconds.
The [original response and receipts](../artifacts/reports/deerflow-dynamic-read.json)
also preserve its inherited virtual file URL. A subsequent deterministic
normalizer resolves those links only to actual observed project-relative source
paths and rejects unknown sources; unit checks cover both cases. This is
postprocessing verification, not a new claim about the model following the
prompt overlay correctly.

The [source-link postprocessing check](../artifacts/reports/deerflow-source-link-check.json)
records the actual normalized result without changing the saved model response.

Public web integration on 2026-10-14: the first model turn returned an empty
response without a source call, preserved in the
[first-attempt report](../artifacts/reports/deerflow-web-first-attempt.json).
After explicit-URL pre-reading, an exclusive answer/call schema and the
source-evidence gate, the live check passed: it read `https://www.python.org/doc/`
through the public-page adapter and correctly identified `https://docs.python.org/`.
It took 96.454 seconds. The [answer and actual page receipt](../artifacts/reports/deerflow-web-read.json)
record this single live page check. General web search and separately configured
Firecrawl execution were not live-tested in this run.

Regression/readiness on 2026-10-13–14: the initial 169-test explicit suite passed;
the final expanded suite passed 173 agent, routing, toolkit, planning,
checkpoint/recovery and DeerFlow tests on 2026-10-14. Launcher
`python -m jarvis.launcher --check` reported `ready`. These checks are separate
from live model tasks. Automatic approval review rejected unrestricted test
discovery because it could include live Gmail, desktop and media actions;
explicit regression modules were used instead.

The research phase excluded sandbox, media, uploads and accounts. The subsequent
[sandbox/free-media extension](deerflow-sandbox.md) integrates confined offline
execution, explicit read-only input copies and seven local artifact recipes, with
its own dated live checks. The upstream frontend/gateway, external media providers,
browser sandbox, upstream subagents and account workflows remain outside this adapter.
There is no AGI claim. No UI was added, so there is no new screenshot.

## Reproduce the model measurements

```powershell
.venv/Scripts/python.exe -m scripts.verification.verify_deerflow_comparison --backend ollama --label trial
.venv/Scripts/python.exe -m scripts.verification.verify_deerflow_comparison --backend upstream --label trial
.venv/Scripts/python.exe -m scripts.verification.verify_deerflow_dynamic
.venv/Scripts/python.exe -m scripts.verification.verify_deerflow_web
```

`upstream` runs the real DeerFlow harness with scoped Jarvis reads and the same
local model compatibility code. It does not benchmark stock DeerFlow's default
toolset. Run sequentially without other inference; retain saved report labels.
Each task has a 240-second outer process deadline; DeerFlow has a 180-second
owned-worker deadline.
