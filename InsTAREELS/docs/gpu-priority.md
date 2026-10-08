# GPU allocation by inference phase

Updated **2026-10-08, Asia/Kolkata**. Qwen3.5 9B planning, execution,
questions, research and local Codex now share a process-wide priority queue.
Whisper remains on CUDA. This RTX 3050 Laptop has **4,096 MiB VRAM**;
the installed Q4_K_M model is approximately 9.7B parameters and cannot fit
entirely in that GPU. Partial offload is the supported configuration.

## Handoff and resource ownership

[gpu_scheduler.py](../jarvis/gpu_scheduler.py) wraps actual loopback Ollama
inference sessions. Priority is planner, execution/coding, question, cleanup,
context, research, then background. The currently running inference finishes
before another receives the slot. Pending planners precede pending execution
turns; same-priority requests use arrival order. It does not interrupt an active
generation to run a higher-priority request. Parallel Codex workers serialize
their model turns while retaining their existing file ownership and checks.

Admission reads physical GPU usage and reserves at least 1,024 MiB for speech,
plus 512 MiB headroom. A conservative footprint envelope reduces GPU layers
for longer contexts or competing applications. Missing/multiple GPU readings
and unknown model footprints use CPU for native inference. The envelope is
calibrated to this computer, not a universal memory guarantee.

Native primary requests use at least 16,384 context tokens, normally 10–11
GPU layers under the observed microphone load, with a ceiling of 12. Larger
requested contexts remain larger and receive fewer layers. Warm requests retain
the smaller already-loaded layer allocation to avoid repeated cold reloads.
The same model stays warm for 30 seconds. A model/context change unloads the
last Jarvis cache once only after fresh name, digest, context and VRAM identity
checks. Other GPU applications and the shared Ollama service are not killed.
Resource requests do not replay inference or tool actions. Failed/absent coding
responses never trigger model preloading during cleanup.

Atomic local state and a short OS lock coordinate the existing processes.
Windows read handles can briefly block atomic promotion; only that local state
save retries for at most half a second. A permanent failure remains bounded
and preserves the last state. This repair followed an observed live sharing
violation; it never retries inference or external actions.
PID creation time protects against PID reuse; dead owners and cancelled waiters
release their entries. The queue deadline is bounded. Corrupt state is preserved
and fails closed. There is no additional service or dependency. Existing worker
shutdown/recovery handles process lifetime. The operational heartbeat exposes
only GPU role/model/queue/cache status. Local events under
`.jarvis-runtime/gpu/` contain allocation metadata, without prompts or output.

## Configuration and specialist models

[config.json](../config.json) contains:

```json
"gpu_scheduler": {
  "enabled": true,
  "helper_gpu": false,
  "primary_layers": 12,
  "codex_layers": 9,
  "speech_reserve_mb": 1024,
  "reserve_mb": 512,
  "wait_seconds": 120,
  "warm_seconds": 30
}
```

These settings govern actual intercepted requests; individual legacy `num_gpu`
fields are fallbacks when the scheduler is disabled. Set `primary_layers: 0`
for CPU primary turns. Set `codex_layers: 0` for CPU coding and allow its normal
alias preflight to synchronize the setting. Stop/Start Jarvis after configuration
changes. The shared base-model parameters and global Codex home are untouched.

Small Qwen 0.8B/0.5B cleanup/context/alert models stay on CPU by default:
a cold 0.8B helper completed in **4.172 seconds on CPU** versus **11.985 seconds
with GPU offload** for the same synthetic prompt. These are separate samples,
not a statistically controlled speed guarantee. `helper_gpu: true` enables
idle-only offload when reserved capacity permits; helpers still use CPU while
foreground work is active, queued or cached. Existing short helper deadlines
and fallback behavior remain; a cold GPU helper may exceed them.

Whisper already uses CUDA `int8_float16`. Installed Laya/PyTorch and Kokoro ONNX
are CPU builds/providers; Piper also retains its current path. They were not
converted to new GPU runtimes during this change. Their small specialist work
does not displace primary model turns. Optional disabled Hermes/anticipation
and legacy Claude adapters share the policy when enabled, but were not live
validated in this change.

## Codex

The installed Codex CLI runs locally against Ollama's OpenAI-compatible
Responses endpoint through the existing Jarvis proxy. Its Qwen alias now uses
**9 GPU layers and 32,768 context tokens**. The CLI's tool protocol, tools,
source guards, tests and checkpoint behavior are preserved. Ollama performs
GPU inference; the CLI itself has no local model inference to move to CUDA.
The hosted Codex desktop model is outside this local scheduler.

**Later October 8 repair:** the local Responses relay now finishes lease/cache
bookkeeping before forwarding terminal completion to Codex, which may otherwise
exit and close its owned proxy first. A failed cache-duration update preserves
the freshly observed model identity for its bounded local ownership window;
backend expiry is then unconfirmed. The [Python workload repair](codex-workloads.md)
records the newly observed failure, fault tests and subsequent live validation.

OpenAI-compatible requests do not support native `options.num_gpu` overrides;
the owned alias carries those Modelfile parameters. Alias preflight corrects
an outdated layer setting using existing weights. If its configured footprint
cannot fit after reservation, coding refuses before dispatch instead of
silently changing the API body or overcommitting speech memory. A successful,
observed alias gets a 30-second cache timer and the next phase can evict it.
External Ollama clients remain outside the queue and can change memory use.
See [Ollama memory/cache guidance](https://docs.ollama.com/faq) and
[OpenAI-compatible API limitations](https://docs.ollama.com/api/openai-compatibility),
checked with the Firecrawl plugin against Ollama 0.40.0 on October 8.

## Verification on October 8

[Final live GPU receipt](../artifacts/gpu-live-check.json) and
[retained earlier attempts](../artifacts/gpu-live-history.json) distinguish
synthetic inference from actual desktop/voice behavior. The successful native
proposal, execution answer, question, Responses answer and CPU helper
all retained healthy microphone capture/decoding. Independent model-status and
physical-memory sampling observed **3,392 MiB peak of 4,096 MiB**. Observed
primary/alias contexts were 16K/32K. Phase timings were 14.578, 9.985, 1.062,
7.657 and 4.734 seconds respectively. The warm question reused an existing
cache; these are not end-to-end spoken task benchmarks. Helper GPU was enabled
automatically in the [earlier optional helper receipt](../artifacts/gpu-helper-enabled-live-check.json)
before the measured CPU comparison changed its default; that GPU helper took
11.985 seconds with a diagnostic 90-second budget.

The [CPU helper comparison](../artifacts/gpu-helper-cpu-check.json) used the same
arithmetic prompt and the actual CPU-while-foreground-busy path. Its held
foreground slot was a fixture, with no external action. The [baseline](../artifacts/gpu-baseline-check.json)
compares CPU and several GPU settings; the operator stopped Jarvis during that
baseline, so it does not prove simultaneous Whisper residency. Historical 20
layer Codex measurements are not the current production default.

The [actual installed Codex receipt](../artifacts/gpu-codex-cli-check.json)
passed creation and editing through Write/Edit, behavioral tests, original
backup and unchanged exact CLI output `5`. It records nine coding inference
dispatches at nine GPU layers and seven completed adapter requests. This is
an actual local CLI fixture, separate from the simple Responses inference above.

[GPU vision](../artifacts/gpu-vision-check.json) correctly read a generated digit
using the native image-bearing request path in 9.984 seconds, with healthy
microphone capture and a 3,388 MiB physical GPU peak. The earlier fixture selected
the text-only template and failed; [that attempt](../artifacts/gpu-vision-history.json)
is preserved. No actual desktop image or user action was involved.

All **1,192 regression tests passed** in 200.716 seconds; this includes 25 GPU
allocation/fault tests and two actual loopback coding-proxy timeout tests.
The [full log](../artifacts/gpu-final-regression-tests.log),
[focused GPU log](../artifacts/gpu-focused-tests.log) and
[proxy fault log](../artifacts/gpu-proxy-fault-tests.log) record those scopes.
Fault checks cover priority across actual processes, crashes, cancellation,
state sharing failures, no preload after failed/absent responses and no replay.
[Configured readiness](../artifacts/gpu-readiness-check.json) reports `ready`.
[Repository/static audit](../artifacts/gpu-repository-audit.json) checked 348
authored Python files with zero errors and 80 retained warnings; local links,
parse checks and bundled skill checks passed. These are regression/readiness
results, separate from live feature checks.

[Final startup](../artifacts/gpu-startup-check.json) confirms healthy microphone
capture/decoding, action/question/speech workers, GPU operational metadata and
matching source/config recovery snapshots. The initial subprocess startup
fixture produced no healthy heartbeat; after observing no surviving Jarvis
launcher, the normal hidden launcher started successfully. That
[fixture failure](../artifacts/gpu-startup-history.json) is retained. Jarvis is
running with the completed changes. No new audible-speed confirmation,
arbitrary project success or every optional integration is claimed.

Reproduce from the application directory with its installed environment:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m jarvis.launcher --check
.venv\Scripts\python.exe verify_gpu_scheduler.py
.venv\Scripts\python.exe verify_codex_code.py
```

The live inference check requires running, healthy microphone capture. The CLI
check writes only an isolated Jarvis-owned coding fixture and verifies actual
creation/editing, generated tests, original backup and unchanged CLI output.
