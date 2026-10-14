# Optional Groq hybrid inference — 2026-10-14 IST

Jarvis integrates `qwen/qwen3.8-27b` through its existing question worker. Cloud
inference is **disabled by default**; local Qwen, offline model configuration,
voice, memory, research, coding and permission-controlled automation stay usable.
No API key was created, copied from a connector, or committed. No real Groq
inference was performed. Deployment against the user's account remains unverified.

Groq currently documents this model as preview, with text/image input, a 131,072-token
context and 16,384 maximum output tokens. These are provider capabilities, not
Jarvis benchmark results. The model may change or be withdrawn, in which case
Jarvis keeps its local path. [Groq model documentation](https://console.groq.com/docs/model/qwen/qwen3.8-27b).

## Architecture and changes

The [architecture inspection](groq-architecture.md) maps three existing requests
before modification. There is no second task orchestrator: the gateway runs in
the persistent `knowledge_worker` process, ahead of local inference availability
checks. It can answer an eligible public question even if local inference is
temporarily unavailable. Every actual PC/file/account action still uses Jarvis's
existing local executor and approval/checkpoint policy.

| File | Responsibility |
| --- | --- |
| [cloud_policy.py](../jarvis/cloud_policy.py) | Strict config/env validation, local credentials, precompiled privacy/complexity screening and outbound-size checks |
| [cloud_quota.py](../jarvis/cloud_quota.py) | Shared SQLite/WAL reservations, conservative counters, idempotency, header reconciliation and clock/backoff guards |
| [groq_adapter.py](../jarvis/groq_adapter.py) | Fixed HTTPS endpoint, reusable requests client, bounded transport, SSE, JSON, validated function proposals and model metadata refresh |
| [hybrid_inference.py](../jarvis/hybrid_inference.py) | Existing-worker gateway, route reasons, minimal public payload, fallback and persistent controls |
| [model_performance.py](../jarvis/model_performance.py) | Small local table of explicit correctness feedback; completion is never a correctness label |
| [cloud_cli.py](../jarvis/cloud_cli.py) | Status/control, optional metadata refresh and doubly opted-in bounded smoke test |
| [knowledge_worker.py](../jarvis/knowledge_worker.py) | Cloud gateway at the existing question choke point; configured local path and availability contract retained |
| [question_client.py](../jarvis/question_client.py) | Stable cloud request ID across existing worker recovery, preventing duplicate remote dispatch |
| [commands.py](../jarvis/commands.py), [actions.py](../jarvis/actions.py) | Voice controls and immediate offline selection, bypassing a busy action queue |
| [launcher.py](../jarvis/launcher.py), [diagnostics.py](../jarvis/diagnostics.py) | Strict startup validation and explicitly non-live optional cloud status |
| [config.json](../config/config.json), [runtime manifest](../config/runtime_manifest.json) | Disabled defaults, compatibility, import/dependency/runtime declarations |
| [offline tests](../tests/test_groq.py), [fake server](../tests/fake_groq.py), [verification](../scripts/verification/verify_groq_routing.py) | Failure, concurrency, privacy, opt-in, route and latency checks |

No new host Python dependency, model download, GPU allocation, heavy classifier,
database service, standalone UI or persistent background service was added.
Existing GPU leases, speech reserve, priorities, CPU offload, warm residency and
bounded unload behavior remain in [gpu_scheduler.py](../jarvis/gpu_scheduler.py).
The [installed-model inventory](../artifacts/reports/groq-local-model-inventory.json)
records actual Ollama names, sizes and capabilities, including the Qwen primary,
tiny helpers, vision models, coder aliases, Llama and other local models.
Metadata inspection loaded/unloaded none of them. Manual local model preferences
are validated through existing `model_selection.installed_model`; arbitrary
installed names remain accepted. No new automatic local model race was added.

## Routing policy and representative results

**Partial-stream follow-up (2026-10-14 IST):** The user's recorded Groq answer
paused at 30,055.8 ms, consistent with the configured 30-second deadline. The prior
reader processed SSE one byte at a time, invoking cancellation policy checks at
that frequency. Input is now read in 512-byte blocks with bounded line/wire sizes;
the gateway polls the policy file at most every 100 ms and checks service closure
immediately. The default and current configured deadline are now 90 seconds,
still subject to the existing maximum of 120 seconds. Output-token and quota
limits were not increased. Partial route records now retain `interruption_reason`,
including a distinct output-token-limit code, instead of only the generic pause
label. No partial inference is retried or silently continued. Restart Jarvis when
idle to load the changed stream reader.
The offline regression passed 495 tests in 54.612 seconds on rerun; the first
attempt failed on a temporary Windows file lock in the GPU scheduler test.
New checks complete 2,000 simulated Unicode SSE events with fewer than 50 policy
reads, and distinguish partial output-token exhaustion while confirming one
dispatch and no replay. Startup readiness was `ready`. No live cloud inference
was executed, so production completion, speed and answer quality remain unverified.

Output limits can also truncate a response: Groq documents `max_completion_tokens`
as covering visible answer and reasoning tokens. This was not established as the
cause of the reported 30-second failure. See the
[official API reference](https://console.groq.com/docs/api-reference).

Direct commands still bypass inference. Existing tiny local cleanup/context and
realtime helpers retain their current roles. For question inference, the new fast
policy checks typed context, action provenance, sensitive paths/secrets, ambiguity,
public explanatory form and task complexity before availability/quota/utility.
It adds no classification LLM call. Unknown wording, multilingual wording outside
the reviewed rules, follow-ups and private context stay local.

**Public-question follow-up (2026-10-14 IST):** The recorded local route reported
`private_context_or_action`. Automatic saved conversation matching and catalogue
enrichment could make a standalone public question ineligible. With cloud enabled
and routing other than `local`, a self-contained complex public question now skips
automatic memory matching, recall and catalogue attachment. Its question is still
checked by the worker before dispatch. Explicitly supplied/selected history,
private requests, follow-ups, screen requests and web requests retain their existing
context handling. Basic questions retain the existing memory-selection behavior.
The automatic context is also absent if this public question later falls back
locally; conversation storage itself is preserved.

Cold or expired model metadata now gets a bounded wait of up to eight seconds
on eligible requests; failure still falls back locally. The initial UI label is
“Preparing answer,” and cloud streaming identifies Groq when it runs. A read-only
live model metadata check succeeded with the user's local credentials; no prompt,
inference request or API key was printed. This proves model access, not inference
speed, model quality, billing or quota entitlement.
Verification for this follow-up: 75 focused routing/conversation tests and 493
selected offline regression tests passed (54.793 seconds for the latter).
Startup readiness was `ready`; real cloud inference remains unchecked. Four new
tests cover cold metadata, automatic enrichment, privacy/offline exclusions and
fresh context despite historical answers.

| Request/context | Permitted result and reason |
| --- | --- |
| Open Chrome / turn down volume | Existing direct local executor |
| Explain quantum computing, no private context | Groq eligible only when enabled, free-account/quota confirmation, metadata and budget pass |
| Explain a basic public concept | Configured local answer model under `auto`; `public` preference may permit cloud |
| Private PDF, personal memory, Unreal project | Existing local question/RAG/coding workflow |
| General question with conversation/screen/catalog context | Local; context is preserved rather than silently uploaded |
| Ambiguous “continue that”, typo or unrecognized language | Local or existing clarification flow |
| Public complex question at critical/exhausted/unknown quota | Local |
| Manual `use local model qwen3.5:4b` | Exact installed model preference; no cloud override |

This is a conservative explainable question router, not a general semantic
classifier or a measured ranking of all installed models' accuracy. Cloud previews
do not gain automatic agent, desktop, repository or account context. Automatic
local switching remains role/configuration based, with resource management in the
existing scheduler; this extension does not retrain models or measure a new optimal
hardware-aware model-switch policy.

Only a self-contained public question and a short fixed instruction enter the
cloud payload. The Obsidian profile/situation automatically attached to a general
question is excluded. If history or relevant private observations are involved,
the complete request stays local. Supported reasoning settings are `none`, `low`,
`medium` and `high`; the gateway uses low for complex questions and hides reasoning
output. [Groq reasoning parameters](https://console.groq.com/docs/reasoning).

The transport supports multiturn message arrays, JSON object mode and finite-schema
validation of a single offered function proposal using Jarvis's existing validator.
These were tested against a fake server, not the real model. Function proposals
execute nothing by themselves. The automatic gateway is answer-only. Strict native
server JSON-schema output is not assumed for this preview.

Native vision transport permits one very small embedded PNG/JPEG only with an
exact byte-hash grant supplied by a trusted caller, bounded bytes/resolution and
an additional conservative visual-token reservation. A synthetic image passed
the fake-server check; unapproved images were refused before dispatch. No remote
image URL fetch or automatic screenshot upload is provided. A user-facing consent
flow for public screenshots is not implemented, so Jarvis screenshot questions
continue using local vision. [Provider vision documentation](https://console.groq.com/docs/vision).

## Quota and zero-cost protection

Defaults are 30 requests/minute, 1,000/day, 8,000 tokens/minute and 200,000/day,
with a 10% safety margin. Configured limits can be reduced, not raised above this
reviewed envelope. These are application ceilings, **not a guarantee of account
entitlement or $0 billing**. Verify the organization's actual plan/limits first.
The API/model endpoint does not prove billing state. Local confirmation fields
are user attestations; they cannot detect an undisclosed paid account or later
provider billing changes. Paid routing and automatic upgrades are not implemented.
[Groq limits and organization settings](https://console.groq.com/docs/rate-limits).

Before every dispatch, the adapter checks enabled/local-only/free policy, confirms
cached model availability, screens every outbound role/tool definition, estimates
input conservatively from UTF-8 bytes plus protocol allowance, reserves bounded
completion tokens, and atomically checks all four budgets under SQLite
`BEGIN IMMEDIATE`. Concurrent workers cannot spend the same reservation. Native
visual input adds a conservative allowance and may simply exceed the free budget.
No LLM counts tokens or authorizes spending.

A 250 ms in-memory snapshot is **advisory for routing only**. Every actual request
rechecks the shared ledger, so stale hints cannot authorize dispatch. Actual
API-reported total tokens reconcile the reservation; missing usage, timeout,
disconnect or worker death retains a conservative charge, never zero. An actual
usage report above the reservation temporarily makes the ledger `UNKNOWN` while
its actual charge remains in the rolling daily window; it automatically recovers
after that charge ages out and provider time is verified. A damaged or inconsistent
ledger still requires review.
Request IDs prevent another cloud dispatch after uncertain worker recovery.

Counters use conservative rolling 24-hour and 60-second windows, not local
midnight. Unfinished reservations remain conservative across restarts. Provider
Date/model metadata is needed to resolve significant clock changes. Reset headers
bound provider restrictions; lower returned limits reduce the local ceiling.
Request headers describe **daily requests**, while token headers describe
**minute tokens**; daily tokens remain local estimates. Header restrictions are
reconciled conservatively and include in-flight requests. HTTP 429 applies bounded
backoff; authentication/model failures also back off metadata refresh. No inference
retry loop occurs. Ordinary window expiration is reconsidered without restarting
Jarvis, while uncertain accounting/clock state stays local until resolved.

**Automatic daily recovery follow-up (2026-10-14 IST):** Hitting a quota never writes
`routing: local` or disables the configured cloud backend. Quota is reconsidered
for each eligible request; the existing asynchronous model/time refresh runs when
its metadata cache expires, even when quota previously forced a local answer. No
inference request is made merely to probe quota. Provider restrictions expire at
their reported reset times, and the local rolling daily ledger releases old usage
after 24 hours. This can recover later than a provider's calendar-day reset; it
does not assume that midnight in India restores every limit. A sticky historical
token-overrun flag now derives its pause from the durable overrun's timestamp,
avoiding both permanent fallback and a cross-worker flag-clearing race. Manual
offline selection remains manual and is not overridden by daily recovery.
The expanded offline regression passed 480 tests, including next-day/restart
recovery, provider-header expiry, overrun expiry and deliberate offline preference.
The follow-up readiness check found Docker/Ollama unavailable and LocalGithub
available; it reported `repair_required`. No real Groq inference or service startup
was performed for this follow-up. The earlier `ready` result remains historical.

`NORMAL`, `CONSERVE`, `CRITICAL`, `EXHAUSTED` and `UNKNOWN` are derived locally.
Medium tasks normally stay local; critical quota refuses cloud. All calls in the
same local database share budgets, but another application/organization member can
consume capacity unseen between provider responses. Enable only after confirming
an exclusively allocated organization-level quota, or retain offline mode.
Default disabled operation and this task's development used zero Groq inference
tokens. Runtime free-tier entitlement cannot be independently certified here.

## Failure safety, feedback and UI

Before any answer text is streamed, a cloud failure can return to the configured
local answer workflow. When hybrid mode is enabled and its configured model is
missing, existing installed-model fallback selection is reused. A manual local
preference never silently changes. Disabled-cloud behavior retains the original
missing-model contract. A partial cloud stream pauses as incomplete, without
automatically producing a second answer or replaying any tool action.

Existing island progress displays public cloud inference and local fallback. Updates
are throttled and do not add a floating interface. There is no new rendered UI or
live screenshot claim. Offline selection cancels current question generation and
persists immediately, even while an unrelated action task is running.

Useful commands:

- “Turn off cloud AI” / “Use only offline models.”
- “Enable cloud AI for public tasks” / “Use automatic model routing.”
- “Use local model qwen3.5:4b.”
- “Which model are you using?” / “How many Groq tokens are left today?”
- “Why did you choose this model?” / “How much time did the last model take?”
- “Last model answer was correct” / “Last model answer was wrong.”
- “Reset model routing preferences.”

**Typed-command repair (2026-10-14 IST):** These explicit controls work through
Ask, Do task, Enter and final voice input. They bypass chat generation, pending
reply handling and busy action queues. “Enable cloud AI for public tasks.” saves
the local routing preference and confirms “Public cloud routing preference saved.”
Both “enable” and normalized “turn on” are recognized. Questions explaining a
command and quoted command text do not change settings. Restart an already-running
Jarvis when idle to load this fix.

Verification: the selected offline regression passed 489 tests in 54.620 seconds,
including four new command-routing checks. Startup readiness was `ready`, with
Groq `optional_not_live_checked`; Docker, Ollama and LocalGithub were available.
The public routing preference was saved locally through the CLI. No real Groq
inference or GUI interaction was performed. The regression runner also now sets
its application import path when invoked directly as a script. See the
[current regression report](../artifacts/reports/groq-verification.json).

Enabling public routing by voice or typed input does not bypass disabled configuration, billing
confirmation, credentials, privacy or quota. Status distinguishes the last recorded
route and local rolling estimates from a live provider balance. Unmeasured accuracy
and savings are reported as unvalidated. Explicit correctness feedback is stored
locally by task class/model and may prefer local after repeated validated cloud
failures. Model confidence or HTTP success never labels factual accuracy. Resetting
feedback preserves the quota ledger. No automatic training or prompt/answer storage
occurs in routing statistics; normal Jarvis conversation memory still functions.

## Setup

Keep Groq disabled until the free account and organization limits are checked.
No credential is needed for normal offline Jarvis or these regression checks.
To configure later, from `app/`:

```powershell
New-Item -ItemType Directory -Force secrets
if (-not (Test-Path secrets/groq.json)) { Copy-Item config/groq-secrets.example.json secrets/groq.json }
```

Edit that ignored local copy privately with the real key, or set `GROQ_API_KEY`
in the process environment. Never paste credentials into chat or tracked config.
`secrets/` and `.jarvis-runtime/` remain ignored. Restrict access to the local secret
file with Windows account permissions; it is a plaintext local file, not a vault.

In `config/config.json` set `groq.enabled: true`, `account_plan: "free"`,
`free_tier_confirmed: true` and `dedicated_quota_confirmed: true` **only after
checking the account**. Confirm no other application/member spends that quota.
Keep `free_only: true`, `allow_sensitive_data: false`, `live_tests_enabled: false`.
All declared fields accept corresponding `GROQ_<FIELD>` environment overrides,
including the requested request/token/day/minute/timeout/model controls. Runtime
offline selection has precedence. API keys have no tracked configuration field.

```powershell
.venv/Scripts/python.exe -m jarvis.cloud_cli status
.venv/Scripts/python.exe -m jarvis.cloud_cli refresh-metadata
.venv/Scripts/python.exe -m jarvis.cloud_cli offline
.venv/Scripts/python.exe -m jarvis.launcher --check
```

Metadata refresh checks the supported-model endpoint and provider time only.
Routine routing refreshes asynchronously and never waits for network I/O. A cold
or expired metadata cache chooses local for that turn. Quitting closes the worker
and bounded helper threads; no Groq daemon restarts on its own.

For a separately authorized future live smoke test, explicitly enable
`GROQ_LIVE_TESTS_ENABLED=true` and invoke:

```powershell
.venv/Scripts/python.exe -m jarvis.cloud_cli live-smoke --authorize-live-free-request
```

This sends one fixed public text request with a 32-token output cap and no retries,
then reports API usage when available. Both opt-ins and all free-policy checks are
required. **It was not run during this task.**

Groq offers organization [Zero Data Retention controls](https://console.groq.com/settings/data-controls).
Enable and verify them in the account if desired. Jarvis cannot infer that ZDR is
enabled, and cloud inference is not equivalent to local processing. Groq retains
usage metadata and documents customer-data exceptions and ZDR behavior.
[Groq data policy](https://console.groq.com/docs/your-data).

## Verification and measured limits

The [routing report](../artifacts/reports/groq-routing-verification.json) contains
executed measurements from 2026-10-14 IST:

| Stage | Samples | p50 | p95 | p99 |
| --- | --- | --- | --- | --- |
| Privacy/feature classification | 1,200 | 0.0096 ms | 0.0263 ms | 0.0308 ms |
| Warm advisory quota lookup | 1,200 | 0.0089 ms | 0.0152 ms | 0.0231 ms |
| Warm route selection | 1,200 | 0.0101 ms | 0.1320 ms | 0.1582 ms |
| Authoritative durable reservation | 120 | 5.9890 ms | 8.3189 ms | 9.5217 ms |
| Local fake HTTP streaming first token | 100 | 8.8661 ms | 19.7751 ms | 34.4808 ms |
| Local fake HTTP full call | 100 | 15.8885 ms | 26.2515 ms | 42.0748 ms |

Routing met the common-path target; the authoritative durable reservation did not
meet a 1 ms target. It remains synchronous because dispatch must not outrun durable
accounting. Initial uncached quota reads measured about 3.21 ms p95 before adding
the advisory cache. Cold database initialization was 14.092 ms; gateway-init process
RSS increased by 684,032 bytes after imports. This is a small process snapshot,
not a full-app idle-memory/CPU benchmark. New components allocate no model tensors
or VRAM; real local switching/loading time and production cloud throughput/latency
were not measured. No advertised provider throughput is substituted for those.

All **232 route constraints passed**, including 150 existing independently written
action cases plus public/private, multilingual/typo, context, quota and offline
conditions. The [saved dataset](../tests/fixtures/groq-routing-cases.json) is a
policy-acceptance fixture, not a held-out general semantic or answer-accuracy score.
Mocks/fake HTTP verify text, streaming, JSON, typed proposals, usage, failures,
disconnects, cancellation, concurrency, clock changes, corruption, stable IDs,
manual preference, emergency offline selection and synthetic image grants.

The final selected regression count and readiness result are recorded in the
application README and [final verification](../artifacts/reports/groq-verification.json).
This is an explicit offline module suite, not unrestricted live account/desktop
test discovery. Existing natural-language command/permutation checks were included.
No real Groq call, microphone/GUI startup, paid account, production model quality,
large-image quota estimate or full live local model-switch benchmark was validated.
Privacy screening is deliberately conservative but pattern checks cannot establish
the semantic privacy of arbitrary prose; unknown content should stay local.

Reproduce the offline tests and benchmark from `app/`:

```powershell
$env:PYTHONPATH = "$PWD;$PWD\tests"
.venv/Scripts/python.exe -m unittest tests.test_groq -q
.venv/Scripts/python.exe -m scripts.verification.verify_groq_regression
.venv/Scripts/python.exe -m scripts.verification.verify_groq_routing
```

The regression runner forces cloud off even on an already configured machine.
The benchmark uses a loopback fake provider and temporary databases, with zero real
cloud tokens. It does not call billing, upgrade an account or load a new local model.
