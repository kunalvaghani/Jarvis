# Ollama output and Jarvis timeouts

**Later follow-up on 2026-10-04:** the independent question worker still used
non-streaming inference and a 180-second process deadline after this planning
repair. [Streaming island answers](streaming-answers.md) replaces that question
path with activity-based waiting and partial output display. Measurements below
remain historical evidence from the preceding repair.

Diagnosed and updated **2026-10-04, Asia/Kolkata**. The existing local Ollama
server can produce output. Jarvis's missing model alias was restored, and its
planning HTTP/worker deadlines now agree. CPU latency, GPU discovery failures,
large model loading and interrupted requests still matter; this update does not
establish that the original long C++ request will complete within any fixed time.

## Confirmed observations

| Observation | Evidence and implication |
| --- | --- |
| Screenshot selects Qwen3-Coder | Local `/api/show` identifies the installed `qwen3-coder:latest` as **30.5B, Q4_K_M**. `ollama list` reports approximately **18 GB** of assets; the [official model catalogue](https://ollama.com/library/qwen3-coder) lists the 30B package at approximately 19 GB. |
| GPU has 4 GB VRAM | `nvidia-smi` identifies an RTX 3050 Laptop GPU with 4,096 MiB, driver 610.74. The full 30B model cannot fit entirely in this GPU. CPU/RAM offload and context overhead are relevant to its loading time. |
| Jarvis uses CPU inference | Its workers use `num_gpu: 0` to preserve GPU capacity for Whisper. Live `/api/ps` confirmed **zero VRAM** for the tested Qwen3.5 model. This is intentional, rather than evidence that the GPU is unsupported. [Ollama GPU support](https://docs.ollama.com/gpu) includes the RTX 3050. |
| RAM is limited relative to multiple large models | The machine has **31.35 GiB physical RAM**. Available RAM was 17.1 GiB at the first inspection and 8.06 GiB during a later loaded-model snapshot. These are changing snapshots, not constant usable capacity or a confirmed out-of-memory crash. |
| Jarvis's configured tag was missing | `/api/show` returned **404** for `qwen3.5:9b`, while `qwen3.5:latest` identified the already-installed **9.7B Q4_K_M** model with the previously verified digest. Missing tags are a separate configuration issue; the saved 120-second failure alone does not establish when this tag disappeared. |
| A real Jarvis inference timed out | Saved task metadata records `planning_timing`, failure after approximately **121.75 seconds**, and HTTP `read timeout=120`. No task actions were replayed. |
| Ollama had competing server starts | Rotated logs contain repeated port-11434 bind conflicts and server exit loops. A later check found one healthy listener and API version **0.35.1**. Historical bind errors do not prove the current server is still conflicted. |
| GPU discovery and model loads were interrupted | Recent server logs contain `GPU discovery watchdog timed out` and cancelled loads before the inference runner became available. These establish discovery/loading trouble, not its underlying driver cause. |
| A restart interrupted our follow-up | Ollama's desktop/server shutdown was logged at **08:28:03 IST**, followed by a new app/server at approximately **08:28:06–07**. The diagnostic request lost its connection during that shutdown. The failed result remains in the check history. |

[Sanitized read-only diagnostic snapshot](../artifacts/ollama-diagnostics.json)
contains model metadata, hardware, current loaded state, historical error counts
and task timing flags. It contains no user prompts, chat database, screenshots or
recordings. Log counts can span older sessions and are not all current errors.

The most likely explanation for the original spinner is a combination of slow
large-model loading/inference and queued or cancelled requests. A spinner alone
does not distinguish loading, prompt processing and generation. The original
30B C++ generation was not replayed during this investigation, so its exact
failure mechanism remains unconfirmed.

## Repairs made

Restored the exact configured tag from the existing model:

```powershell
ollama cp qwen3.5:latest qwen3.5:9b
```

This is an alias copy: no weights were downloaded, no model was deleted, and
the shared `latest` tag remains. The restored tag's digest is
`6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7`.
Jarvis keeps Qwen3.5:9b as its selected planner, coder, decision and vision model.

[config.json](../config.json) now sets `brain.timeout_seconds: 300`.
[inference_limits.py](../jarvis/inference_limits.py) shares a bounded planning
budget between native HTTP calls, normal structured planning generation and the
owned BrainClient worker. The HTTP deadline is **300 seconds**; the outer worker
allows **330 seconds**, including 30 seconds for startup/transport. User values
remain bounded to 5–600 seconds for planning; invalid/non-finite values are
rejected. The unconfigured defaults remain 120/150 seconds for compatibility.

Previously the HTTP layer could stop at 120 seconds even though another layer
was still waiting. The new allowance accommodates slower CPU planning; it does
not improve token speed, guarantee completion, disable cancellation or retry
external actions. Coding retains its separate **900-second** allowance. Ordinary
question and dedicated vision transports retain their existing separate limits.
No new dependencies, GPU assignment or background service were added.

Restart Jarvis through its normal Stop/Start launchers to load the new settings
and code. Jarvis was intentionally stopped during this investigation and was not
automatically restarted. The active shared Ollama app/server was not killed by
the diagnostic or repair scripts.

## Practical Ollama use on this machine

For the next chat, select **qwen3.5:9b** and start with a **4K context**. The local
standard `/api/chat` path was verified with this model. Use one active generation
while testing, and let loading finish before cancelling or restarting the app.
Keep one Ollama server on port 11434; repeated manual `ollama serve` launches
while the app's server is active can produce the recorded bind conflicts.

The 30B coder's larger weights and RAM/VRAM requirements make it a poor choice
for a quick responsiveness test on a 4 GB GPU. The current Jarvis model remains
9B; no smaller model was silently substituted. Large prompts, high context sizes
and simultaneous GUI/Jarvis generations can increase memory pressure and queue
time. Ollama documents how [context, concurrent requests and residency affect
memory and queuing](https://docs.ollama.com/faq).

If output stalls again, check `ollama ps` and the current server log while leaving
the request running. [Ollama troubleshooting](https://docs.ollama.com/troubleshooting)
documents the Windows log locations. A current runner crash or GPU discovery
error needs its own diagnosis; increasing a timeout cannot repair such a failure.

## Verification

[Latest synthetic output check](../artifacts/ollama-output-check.json), on the
existing Ollama 0.35.1 server:

| Check | Result | Measured time |
| --- | --- | ---: |
| Jarvis text helper, CPU, 2K context, 16-token cap | Returned exactly `OK` | First response text **8.948 seconds** |
| Warm standard `/api/chat`, same small request | Returned exactly `OK` | **0.347 seconds** |
| Native tool proposal, CPU, 4K context | Correctly proposed opening Notepad; **not executed** | **21.775 seconds** |

The earlier initial response took **23.317 seconds**, before the warmed standard
chat check. [Check history](../artifacts/ollama-output-check-history.json) preserves
that success and the follow-up interrupted by server shutdown. These are single
synthetic measurements with short prompts, not throughput distributions, full
C++ generation, desktop task completion or live voice checks. The full latest
sequence took 31.220 seconds; its timings describe different request scopes.

[Regression/readiness](../artifacts/ollama-regression-check.json): **843 tests
passed**; launcher readiness returned **ready**, no missing requirements, with
`qwen3.5:9b` and `qwen-native-tools`. New checks cover shared deadlines, bounds,
invalid settings and configured native/non-native HTTP budgets. Existing worker
cancellation/recovery and no-replay tests remain included.

Reproduce from the application directory, with Ollama already running:

```powershell
.venv/Scripts/python.exe capture_ollama_diagnostics.py
.venv/Scripts/python.exe verify_ollama_output.py
.venv/Scripts/python.exe verify_ollama_regression.py
```

The output verifier performs inference only and never executes its native
proposal. Its requests can contend with another active local generation, so
timing is meaningful only with the recorded request scope and server state.
