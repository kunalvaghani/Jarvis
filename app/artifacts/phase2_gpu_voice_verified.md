# Phase 2 GPU / models / voice / UI verification

**2026-10-15 IST · acceptance gate NOT PASSED.** The upgrades and fixture suite
are implemented. Live local model/synthesis checks completed, with a sampled
3322 MiB GPU peak, but F5 first PCM takes 4.717–4.741 seconds. The requested
sub-500 ms first-audio target is unmet. Live editor hotkeys and live Mind/DAG
display acceptance remain open. This filename is the requested deliverable;
it does not imply every feature or target is verified.

## Executed results

| Check | Result | Evidence / scope |
| --- | --- | --- |
| Requested suite, default fixture mode | **72 PASS, 7 explicit live skips**, 4.699 s | [JUnit](phase2-fixtures-final.xml); 79 collected cases |
| Same suite with live evidence | **76 PASS, 1 FAIL, 2 BLOCKED skips**, 5.738 s | [Acceptance JUnit](phase2-acceptance.xml); failure is F5 latency, not hidden by a skip |
| Expanded relevant regression | **475 PASS, 1 FAIL, 10 skips**, 87.940 s | [JUnit](phase2-regression-final.xml); GPU, models, speech, UI, documents, launcher/recovery, cognition, state and Groq fixtures |
| Failed regression isolated in a fresh process | **1 PASS**, 0.533 s | [WM_DROPFILES JUnit](phase2-wm-drop-isolated.xml); combined run failed during Tk initialization with `invalid command name "tcl_findLibrary"`; no all-green combined run is claimed |
| Live concurrent submissions | All five workers completed | [Probe metadata](phase2-live-evidence.json); CUDA Whisper/F5, CPU helpers and partially offloaded 9B. Turn admission serializes CUDA work |
| Sampled device VRAM | **3322 / 4096 MiB**, 585 samples over 227.203 s | [CSV](phase2-vram-trace.csv); below 3850 MiB in these samples, not an allocator high-water-mark guarantee |
| CUDA OOM count | **Not globally certified** | Completed synthetic worker calls surfaced no CUDA OOM. Framework allocator/log interception was not installed; evidence records global count as unknown |
| Laya ranking | **22 / 25 expected choices** | [Per-prompt metadata](phase2-live-evidence.json); five synthetic control families with five wording variants, not a universal accuracy benchmark. Three Cancel prompts selected `none`; two expected Cancel choices also had very low confidence |
| PC LoRA | Loaded and generated **2 tokens** | Existing local Qwen base + configured adapter, CPU `.venv-training`; not a fresh PC-resolution accuracy evaluation |
| Legacy Qwen alias | Loaded and generated **8 tokens** | Native Ollama route, 4096 context and four GPU layers; not a `/v1` Codex/Claude CLI end-to-end test |
| F5 CUDA synthesis | **4.741 / 4.717 s first PCM**, 2.549 s audio per take | Warm voice, synthetic nine-word sentence, no speaker loopback. Audible TTFA cannot be shorter than first PCM |
| Kokoro blend synthesis | **4.013 s first PCM**, 2.359 s audio | Real `am_michael:60,am_fenrir:40` synthesis, no listening assessment |
| Piper synthesis | **2.096 s first PCM**, 2.717 s audio | Installed English voice, no listening assessment |
| UI buffer flood | 10,000 cumulative events → **1 delivered snapshot** in each of seven runs | [Benchmark](phase2-ui-buffer-benchmark.json); headless buffer cost, not Tk FPS or audio latency |
| Launcher readiness | **`repair_required`**, 87.141 s | [Readiness JSON](phase2-readiness.json); Docker/Ollama unavailable at that separate check. F5/component checks returned without an incomplete flag. Probe-owned Ollama is stopped after testing |

Hardware observation: NVIDIA RTX 3050 Laptop GPU, 4096 MiB, driver 610.74;
Ollama client/server 0.40.0. These measurements are specific to this installation.
After probe cleanup, `nvidia-smi` reported **0 MiB used / 0% utilization**; no
probe GPU residency remained at that final observation.
The probe launches used existing local model caches and offline Hugging Face
loading. No paid/cloud inference, microphone recording or account actions ran.

## Changes and coverage

| Requested area | Implemented / exercised | Remaining boundary |
| --- | --- | --- |
| GPU saturation and ordering | Shared cross-process leases; planner > coding > question > cleanup among Ollama turns; native speech/recognition prioritized above those turns; deterministic queued-order torture fixture | No forced preemption of active kernels; no continuous human speech or all-model allocator trace |
| Memory reserve and handoff | 3850 MiB allocation ceiling, effective F5 reserve, CPU helpers, explicit context limits; native loads can evict only a digest/context/VRAM-bound Jarvis cache | Native load/workspace estimates cannot guarantee all allocator peaks; external apps remain outside admission |
| 30B → 9B fallback | Simulated available-RAM/tag inventory selects installed 9B; unsafe/unknown RAM defers inference | No live 30B allocation was attempted on this 4 GB GPU |
| F5 → Kokoro → Piper | Real backends synthesized separately; startup fallback and injected pre-PCM runtime failure preserve the sentence; parent rejects contradictory replay after observed commitment | Actual audible/uncertain failures are not replayed; cold backend switching is not instant; partial-audio continuation is not solved |
| Warm workers / PCM | Existing warm workers retained; bounded shared-memory PCM pools connected to capture and F5/Kokoro playback; callback continuity, buffer reclamation and cancellation fixtures | Metadata/locks are local to each owning process; copies/locks remain; no zero-overhead claim |
| Silence / hum | Existing CPU Silero VAD retained; silence fixture produces no recognition jobs beyond explicit warmup | Synthetic silence is not real room-hum/acoustic acceptance |
| Speech normalization | Number/currency/path/identifier/math expansion; adversarial CJK/URLs/tracebacks/tables/surrogates and 1000-word fake-render streams | Unicode-safe fake rendering does not establish real CJK pronunciation, prosody or long-stream acoustic quality |
| Opening lookahead | 6–8-word clause or eight-word head with lookahead; exact tail retention | Does not make current F5 inference meet 400/500 ms targets |
| Wake / barge-in / queueing | Wake-gated echo filtering and three sequential command submissions during synthetic output; existing task/speech queue regressions | No acoustic echo cancellation or real full-duplex microphone/speaker evaluation |
| Push-to-Write | Failed/partial `SendInput` forwards physical release; stale/closed timers invalidated; internal state cleared at Stop | No live Notepad/VS Code modifier injection; internal state is not proof of physical Windows key state |
| Island / Pip / media | Coalesced replaceable snapshots, ordered terminal/control/media events, 16 ms drain cadence with 6 ms cooperative batch budget; all 35 Pip emotions rendered; media fixtures exercised | No certified 60 on-screen FPS under native model load |
| Mind / DAG | Bounded node status label and nonblocking cognition/checkpoint reads; running → succeeded fixture and held-checkpoint-lock fixture | Live task-DAG UI acceptance remains blocked; the six-module cognitive graph remains the main visualization |
| Pip documents | Real 50-page PDF and DOCX extraction, graph/light indexing, retrieved page context; cited-answer contract with mocked model; corrupt PDF/binary handled; isolated native drop fixture passed | No live model-based citation-quality study or scanned-PDF OCR claim |
| Cloud stack | Existing Groq privacy/quota/routing regression fixtures included | Live cloud inference not exercised |

The [source and configuration guide](../docs/phase2-gpu-voice-ui.md) explains the
settings, limits, launch behavior and rollback. No dependencies or long-running
services were added. Existing deliberate Stop/microphone behavior and silent
recovery remain in force. No uncertain desktop/account effects were replayed.

## Reproduced key defects

[Baseline vs current fault results](phase2-key-fault-reproduction.json) execute
the committed baseline and current state machines with injected failures:

- Baseline masking failure raised before clearing tracked Alt/writing state;
  current code forwards the real release and clears those flags.
- A baseline timer could activate after Stop when the hold delay had already
  elapsed; current code checks closed state and hold generation before arming.

No VRAM fragmentation or acoustic clipping defect was independently established.
Finite PCM, amplitude bounds, chunk joins, backpressure and output failure are
covered by fixtures; these are not listening-quality measurements.

## Evidence handling and limitations

Initial sandbox model connections failed with WinError 10013. Live Ollama probes
were rerun outside that socket restriction. Existing WinRT fixture subprocesses
also timed out inside the sandbox; later native-access execution passed those
tests. Earlier files with `initial`, `sandbox` or `before-final-hardening` in their
names are superseded observations, not additional final acceptance passes.
The first Laya harness incorrectly compared its result dictionary to a choice
string; final evidence reads the actual `choice` field and retains all 25 outcomes.

The expanded regression's Tk failure remains recorded, alongside its successful
isolated rerun. No screenshot or zero-failure full-suite result was fabricated.
No microphone audio, reference transcript, credentials or unrelated desktop
content is included. [Final source hashes](phase2-source-hashes.json) identify the
reviewable files; performance numbers describe the probe scope, not every path
in the application.

![Rendered Pip and island fixture, not a live desktop screenshot](phase2-pip-rendered-preview.png)

The preview uses existing application artwork/renderers. Original source/reference
attribution remains in the [Pip](../docs/file-buddy.md) and
[island](../docs/dynamic-island.md) guides.

## Upstream configuration references

[Ollama FAQ](https://docs.ollama.com/faq) documents server environment inheritance,
Flash Attention, global KV-cache quantization, model/parallel limits and request
`num_ctx`/`keep_alive`. `q8_0` uses roughly half the `f16` KV-cache storage; this
does not halve model weights or prove unchanged quality for these workloads.
[Ollama chat API](https://docs.ollama.com/api/chat) describes request options.
