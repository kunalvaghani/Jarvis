# Core architecture and cognitive audit

2026-10-14 IST. Requested modules: `engine.py`, `cognition.py`, `deliberation.py`,
`context_hub.py`, `task_recovery.py`, `commands.py`. Supporting changes include
`experience.py`, `cloud_policy.py`, `gmail_writes.py`, `gmail_api.py`, `task_state.py`,
`brain.py`, `intent_catalog.py`, `actions.py`, `main.py` and the runtime manifest.

## Verified results

The requested [pytest/async suite](../tests/test_cognition_and_routing.py) passed
**30 tests in 10.09 seconds**. The affected established unittest suite passed
**92 tests** during development. The full-release/readiness results are recorded
below after completion. All provider tests use a real loopback HTTP simulator with
a fake test credential; no real Groq inference, deletion, email or WhatsApp send
was performed. No user recordings or desktop screenshots are included.

Final full regression: **1785 unittest cases passed in 286.841 seconds**. The final requested pytest suite separately passed **30 tests in 10.09 seconds**. No skips were reported. Launcher readiness passed (`ready`), and source compilation, documentation-link and whitespace checks passed. [Machine-readable release evidence](reports/cognition-validation.json) records results and final hashes.

## Findings and implemented fixes

| Finding | Fix | Evidence |
|---|---|---|
| Relative sleeps plus synchronous state writes drifted beyond 250 ms | Monotonic deadlines, no catch-up bursts, one owned coalescing persistence thread | Injected 180 ms storage delay and 20 simultaneous sensor events plus voice |
| Sensor scores/floods could outrank or evict voice/window events | Voice priority 1.0, active window .85, background capped .7; bounded priority-preserving ingress | 400-event overflow test retains voice then active window |
| Attention/workspace snapshots were not consistently locked; active task omitted from question context | Locked commits/snapshots, deterministic salience/age ordering; protected goal/task outside seven attention slots | 12-slot eviction and context-hub tests |
| Concurrent flush/shutdown could lose later statistics | Serialized metadata writes, coalesced latest state, bounded final dirty flush | 100 concurrent outcomes survive shutdown and reload |
| Statistics could mutate during iteration; malformed counters broke prediction | Locked updates, bounded history input and sanitized counts/duration | Concurrent snapshots and malformed-history tests |
| Paused tasks were counted as successes | Explicit paused/failed/cancelled result recognition | Uncertain-task result does not increase successes |
| Success estimates lacked intervals | Beta(1,1) posterior and exact equal-tailed 95% credible interval through existing SciPy | Historical 90/100 successes and no-history/malformed priors |
| Reflexes still traversed the general resolver/import chain | Immutable hash-table dispatch for exact pause/volume up/open Chrome | Learned override and canonical resolver forced to fail; reflexes still route |
| Core catalog collection was mutable | Immutable compiled tuple and SHA-256 catalog fingerprint | Registry immutability test; remaining built-in-first resolver order preserved |
| Implicit mailbox wording/format characters could escape the privacy vocabulary | NFKC/format-character normalization, conservative private-app words and explicit context fields | Captured provider POST bodies: zero calls/bytes for tested private, screen and PC cases |
| Bulk destructive compound task could reach planning before scope agreement | Pending scope approval and decision ledger, including heuristic failure fallback | Delete-all-and-email task never reaches the mocked task executor |
| External uncertainty depended on bounded checkpoint history | Durable per-operation/target pending markers plus Gmail journal linkage | Crash/restart blocks identical write; 35 unrelated reads cannot clear marker |
| Read recovery was not a shared five-attempt policy | Explicit read-only retry helper, cancellable backoff, wired into UI observation | Five transient read failures/attempt bounds; writes rejected before callback |
| Engine hypothesis state lacked serialization | Reentrant feed lock | Existing ASR/router regressions and new concurrent ingress coverage |
| Continuous memory decay repeatedly parsed timestamps/calculated scalar exponentials | Bounded cached ISO parsing and NumPy batches for 32+ timestamps | Scalar/batch equivalence and 2,000-timestamp timings |

The seven attention slots reside in `cognition.py`; `context_hub.py` exposes that
workspace rather than owning a second eviction store. No SQLite I/O existed inside
the cognitive tick: the removed synchronous loop I/O was JSON state persistence.
TaskState and Gmail effect journals remain synchronous/durable; they must commit
before an external write. Cognitive statistics may lag until their coalesced flush.

The persistence worker starts/stops with Cognition, has bounded two-second joins
per worker, and permits at most three dead-writer restarts per session. Existing
Watchdog health/recovery registers it, with Stop/Quit disabling restart. Health
fields appear in the cognitive snapshot. A statistics-storage failure never changes
an already successful external action into a retry. Persistent filesystem outages
can leave telemetry stale; no thread can force an OS filesystem call to return.

## Before/after benchmark

Same [benchmark script](../scripts/verification/verify_cognition.py): 3.2 seconds
of synthetic bursts at a 4 Hz target, injected 180 ms state-write delay, 300 exact
parser calls, and 2,000 timestamps. Machine-readable
[baseline](reports/cognition-baseline.json), [final upgraded](reports/cognition-upgraded.json)
and earlier [first upgraded](reports/cognition-upgraded-first.json) / [routing pilot](reports/cognition-upgraded-routing-pilot.json) samples preserve measurements
and source hashes. Small samples are controlled checks, not production distributions.

| Metric | Before | Final upgrade |
|---|---:|---:|
| Loop tick samples | 10 | 12 |
| Tick CPU median | 0.150 ms | 0.186 ms |
| Tick CPU p95 | 0.217 ms | 0.229 ms |
| Tick CPU maximum | 0.218 ms | 0.253 ms |
| Tick interval median | 264.607 ms | 249.915 ms |
| Tick interval p95 | 440.897 ms | 262.896 ms |
| Tick interval maximum | 452.962 ms | 264.717 ms |
| Exact parser median | 3.8941 ms | 0.0006 ms |
| Exact parser p95 | 5.3073 ms | 0.0008 ms |
| Exact parser maximum | 801.0803 ms | 0.0093 ms |
| Scalar decay batch | 1.1793 ms | 1.2467 ms |
| Vectorized decay batch | Unimplemented | 0.2916 ms |

The baseline scope string mistakenly said “warm parser calls”; its first resolver
call included lazy imports. The table preserves that cold maximum and does not
describe it as warm latency. CPU tick duration remains far below 250 ms. Scheduling
jitter still makes some wall-clock intervals exceed exactly 250 ms; Windows/Python
is not a hard real-time scheduler. The acceptance test permits 310 ms intervals
and separately verifies an asyncio heartbeat remains responsive. The result is
approximately 4 Hz under this controlled load, not zero jitter under arbitrary load.
Pointer queues and one pending flush avoid serialized tick payloads; this is not a
claim that all snapshots/JSON writes are literally zero-copy.

## Test coverage and practical limits

The suite covers actual central worker routing with a local simulated Groq endpoint:
public entanglement goes to the adapter; HTTP 429 and pre-output timeout invoke
the existing local answer path with `qwen3.5:9b`. Local generation is mocked so it
tests routing, not model quality. Existing partial-stream policy remains: interrupted
already-emitted cloud text pauses rather than generating a duplicate local answer.
Captured private/screen/PC cases send zero provider POST payloads. Static public
profile enrichment is omitted from outbound messages; explicit situation context
now forces local inference. A corresponding existing regression was strengthened
to check local refusal, then separately retain public language/profile exclusion.

Privacy remains conservative rule-based admission, not proof of perfect semantic
classification of all possible text. Unicode normalization handles the tested
format/fullwidth cases; unsupported ambiguity stays local. False positives can
route public discussions of private apps locally. Exact reflex protection covers
the three requested phrases; broader built-in commands retain their existing
priority over learned action commands. The hash fingerprint is audit metadata,
not a sandbox against an attacker who can rewrite Python source or globals.

The Bayesian intervals describe historical Bernoulli outcome counters with a
uniform prior. They do not establish real-world calibration, independence,
stationarity, or whether a model response is true. Existing historical counters
cannot retroactively distinguish every old incorrectly marked success.

Bulk-task scope approval does not waive individual delete/send/tool approval.
Single effects keep established confirmation behavior. Successful readback clears
only the matching pending write marker. Other reads and checkpoint truncation
cannot erase uncertainty. The five-attempt helper accepts only admitted read-only
operations and catches transient OS/timeout errors; it does not automatically
retry arbitrary ValueErrors, writes, clicks, or uncertain partially streamed output.
Existing inference-worker recovery budgets remain unchanged.

Initial development included a pytest reserved-parameter collection error and
fixtures missing the adapter's explicit loopback testing flag/app configuration.
Those were corrected; the initial 24 failures include fixture setup and deliberately
missing new APIs, so that count is not presented as 24 independently measured
production defects. The slow-tick, priority eviction, missing protected task,
prediction corruption and paused-success failures were reproduced against baseline.
The first full regression caught an incorrect fast-dispatch mapping for `Pause.`; the existing `click_control` semantics were restored. Two buddy mood tests also depended on host night-time despite expecting daytime. Their calendar fixture is now fixed to daytime; dedicated night/date tests still override it. Production buddy behavior was preserved.

No live microphone, speaker, arbitrary private-data corpus, 24-hour soak, hardware
sensor integration or GPU/VRAM benchmark was performed for this audit.

## Reproduction and rollback

From `app/`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements/testing.txt
.\.venv\Scripts\python.exe -m pytest tests/test_cognition_and_routing.py -q
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m jarvis.launcher --check
```

Pytest/pytest-asyncio are optional QA dependencies; NumPy/SciPy already belong to
the runtime requirements. Baseline/upgraded benchmark artifacts refuse overwrite;
preserve them before an intentional rerun. Source and config changes require a
Jarvis restart. `cognition.enabled=false` disables the cognitive loop/worker while
central task approvals, cloud privacy and durable write guards remain in force.
Rollback source changes as a coherent reviewed set if restoring earlier behavior;
never remove pending Gmail journals or uncertainty markers to bypass inspection.
