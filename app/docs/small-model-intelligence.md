# Small-model-first Jarvis

Updated 2026-10-22 IST. Candidate implementation on `codex/small-model-intelligence`, based on `df713f1`. Results below distinguish public component benchmarks from complete application acceptance.

## Runtime behavior

Existing explicit command handlers, direct execution grammars and fast workflows still run before inference. The existing ToolRegistry, native function schemas, connector prerequisites, scoped permissions, memory retrieval, procedural skills, optional cloud privacy gate, checkpoints and independent goal verification remain authoritative. The hierarchy changes local planning proposals, not tool execution authority. Coding backends, vision verification and optional harness/cloud routing keep their configured paths.

`brain.model_hierarchy` accepts only `enabled` (boolean), `execution_model` (`qwen3.5:2b` or `qwen3.5:4b`) and `reasoning_model` (`qwen3.5:9b`). Disable it to retain configured-model selection. The underlying `brain.planner`, `decision`, `coder` and `screen_model` remain 9B, so the launcher's planner field describes the configured fallback. The small executor is optional at startup: if absent, installed 9B handles the request without downloading anything.

This machine's checked-in configuration selects **2B**, based on its faster observed execution and unchanged exact-read outcomes in the bounded comparison. 4B remains configurable for evaluation. This selection is provisional pending broad live task quality acceptance; omitting the hierarchy object retains a 4B compatibility preference with installed-9B fallback.

The deterministic policy admits bounded routine text planning, and sends coding/debugging, research, Blender/Unreal, unfamiliar requests, visual input, validation failures and unconfirmed tool outcomes to 9B. It does not call a classifier model or trust the model's confidence. Verified aggregate history can suspend small-model admission by task family. These conservative cold-start rules and their threshold are policy choices; probabilistic calibration and equal intelligence have not been demonstrated.

An invalid small-model native proposal receives one local 9B correction before any external dispatch. Completed steps, observed results, memory and skill context remain in the request. No tool call is replayed by this fallback. Native 9B planning retains its existing bounded inference correction. JSON planning now also checks its entire response against the offered schema. A task checkpoint records route attribution, with a separate bounded attribution list surviving the rolling observation log. No raw goals, tool arguments or private content enter `.jarvis-runtime/model-outcomes.sqlite3`.

After a confirmed verified recovery step, a routine goal can return to student planning while retaining its historical failures. New rejection feedback, an unconfirmed outcome or a complex original goal still requires 9B. Whole-goal and visual verification keep their configured model; this can still incur switching cost in the complete Brain loop, which the component timing harness does not measure.

The existing deferred catalog and capability index continue retrieving relevant tools from the full registry. A small model does not get a reduced permanent capability set. Unavailable adapters still require configuration/discovery, and changing the model cannot make an unconfigured connector executable.

## GPU and model residency

The priority lease scheduler now admits bounded partial offload for 2B/4B, instead of treating them as unknown CPU-only models. Existing speech reservations, CPU fallback for unknown hardware, context bounds, foreground priority and owned-cache identity checks still apply. Small models can use the configured warm interval only after GPU admission. Switching unloads only the last positively identified Jarvis-owned resident cache; shared models and processes are never killed. The layer formulas are conservative admission envelopes, not claims of measured full-model VRAM residency.

The authorized 2B download initially failed twice over IPv6. Fetching the official manifest and blobs over IPv4 succeeded; every blob's byte count and SHA256 matched before the new manifest was registered in the configured Ollama cache. This downloaded inference GGUF/projector data only. No training weights, package, driver or cloud credentials were installed.

## Teacher procedures and offline training

Verified 9B tasks can add `teacher_procedure` to existing SkillMemory entries. The compiler requires successful completed steps and a whole-goal proof, excludes shell/input/deletion recipes, replaces target/path/content bindings with typed current-request slots, and includes failure conditions and fresh verification requirements. Existing SkillMemory indexes and retrieves these references immediately, with its negative experiences and reliability checks. A template cannot replay historical IDs, grant approval or execute itself. Original bounded task records retain tool arguments, results and verification under the existing local memory/privacy rules; templates do not export those payloads.

The existing self-evolution idle skill-maintenance path assesses verified procedure/family counts. Its readiness result requires curation and consent, never starts training or promotes a model. Existing repository learning, isolated evolution evaluation, approval, security, checkpoint and recovery mechanisms remain in place.

Optional offline pipeline: [student_lora.py](../scripts/training/student_lora.py). Default invocation only prepares a user-curated JSONL dataset:

```powershell
.\.venv\Scripts\python.exe scripts/training/student_lora.py --examples <curated-public.jsonl> --out <new-candidate-directory>
```

Each example needs `input`, `target`, `family`, `verification`, `teacher_model: "qwen3.5:9b"`, `reviewed: true`, `verified: true` and `privacy: "public"`. Private examples are refused unless that explicit run supplies `--allow-private`; runtime records are never automatically collected for training. Review these claims against real verification evidence before curating. Whole procedure families are deterministically separated between train and held-out data; duplicates and empty splits are rejected.

An explicit `--train --base <local-original-base> --base-manifest <manifest.json>` uses the isolated training environment, local files only and CPU LoRA, keeping the 4 GB GPU available. The manifest must name the official 2B/4B trainable base, pin a 40-character commit revision, and list SHA256 for **every** base/tokenizer/config file. Quantized Ollama GGUF is not a training base. The pipeline checks model architecture, installed support and RAM headroom before allocating weights, stops between bounded work units for foreground activity/STOP/resource limits, retains its candidate adapter, and evaluates baseline versus candidate on exact held-out targets. Any previously correct held-out case becoming wrong blocks review. Passing is only `review_required`; full regression/application evaluation and explicit approval are still required to promote.

**Actual Qwen3.5 LoRA training is unexecuted.** The installed training environment is Transformers 4.57.6 / PEFT 0.18.1 / Torch 2.6.0+cu124 and lacks the Qwen3.5 implementation. The official [2B configuration](https://huggingface.co/Qwen/Qwen3.5-2B/raw/main/config.json) identifies `Qwen3_5ForConditionalGeneration`; the pipeline checks that exact architecture rather than pretending a generic causal loader supports it. An approved isolated dependency update and checksum-pinned trainable base are prerequisites. No such update/download/training was authorized or performed.

## Measurements and acceptance

Latest serial desktop-schema comparison (`final-native-planning/`, 18 cases per configuration):

| Scope | 9B p50 / p95 | 2B-first p50 / p95 | Expected tool |
|---|---:|---:|---:|
| Routine Windows / YouTube / Spotify, six proposals each | 10.72 / 13.41 s | 4.17 / 13.39 s | 6/6 each; all six hierarchy calls used 2B |
| All nine categories, eighteen proposals each | 9.36 / 13.41 s | 9.59 / 30.37 s | 16/18 each |
| Actual scoped file execution, six tasks each | 14.86 / 21.33 s | 9.94 / 16.86 s | 6/6 independently verified each |

Routine planning median improved about 61%, and the bounded real-tool file median about 33%. **Mixed-workload median was slightly worse and p95 more than doubled.** Four observed model transitions had Ollama load timers p50 7.19 s / p95 19.81 s; this is not isolated switch overhead. The file harness exercises model→ToolRegistry→byte oracle. The desktop schema benchmark predates the subsequent headless compatibility and CPU-embedding fixes; desktop schema semantics are unchanged. No old-source checkout or equal-intelligence claim is implied.

Routine GPU snapshot medians were 2,600 MB (9B) and 1,734 MB (hierarchy); mixed maxima 2,600 / 2,598 MB because difficult tasks still use 9B. Aggregate Ollama-process RSS medians were 7,897 / 5,682 MB and system-used-RAM medians 23,349 / 21,066 MB. These include shared host activity and multiple Ollama processes; they are neither exclusive Jarvis usage nor allocator peaks. See `final-derived-metrics.json` for definitions.

Live checks added on 2026-10-22 IST:

- Both configurations saved and independently reopened a disposable Blender scene: PublicCube, eight vertices, six polygons, location `[1,2,3]`. Times 22.65 / 25.66 s; both used 9B. Unreal returned installed build 5.8.2 in 6.90 / 7.00 s; **only its manifest was inspected**, not an editor/project workflow.
- The injected invalid-inference recovery probe retained a verified prerequisite and read only the unfinished file: 1/1 each, 10.59 / 10.48 s. This is a deliberate inference fault, not a natural-failure recovery rate.
- Complete Actions→Brain→DAG→ToolRegistry runs passed a single-file read, two-file workflow and unfamiliar documented-device task: **3/3 each**. The single-file request initially failed because 9B emitted empty operands. Strict operand constraints and an exact literal-read compiler fixed it; repeated single reads completed in 0.172 / 0.063 s without inference. Workflow/unfamiliar paths retained 9B. Concurrent host verification means these are functional timings, not isolated performance estimates.
- Exact public YouTube playback passed in pinned Chrome `Default`, then paused. YouTube and Spotify play/pause/status passed through Actions and ToolRegistry with Windows media readbacks, zero model calls and original playback states restored. Initial named YouTube search stopped on ambiguity; exact-video acceptance does not certify all search queries or expanded MCP/OAuth tools.
- Installed Kokoro→configured GPU Whisper recognized the generated public sentence correctly: synthesis 10.06 s, recognition load 50.61 s, decode 1.94 s. This is synthetic local PCM, not physical microphone/speaker, acoustic WER or audible latency acceptance.
- A verified public 9B trace compiled into parameterized SkillMemory and was retrieved under a changed target query (`teacher-student-proof.json`). General execution transfer remains unproved. One public export is explicitly unreviewed, not a curated training set.
- `live-procedure-transfer/` additionally retrieved that parameterized procedure and supplied it to actual 2B, which read a different public filename through ToolRegistry; exact new bytes matched. This single bounded execution does not prove general transfer or that the procedure caused a quality gain.
- CPU embedding semantic retrieval passed; its Ollama snapshot reports `size_vram: 0`. Optional OpenViking/LiteLLM embedding resource paths remain separate.

All four simultaneous planner/Whisper/Kokoro submission probes completed (two 9B, two hierarchy); 722 shared-host GPU samples reached 3,444 MB. Whisper decoded synthetic silence while Kokoro synthesized public text; no microphone or speaker was used. Some decode calls, including scheduler wait, took 37–48 seconds. Completion and sampled headroom do not establish acceptable voice latency or absence of all allocator failures.

An actual native App startup/close check passed in the existing UI-verification mode, without starting the microphone. Complete development regression later finished **3,925 passed / 150 skipped / two failures** (2,195.33 s): transient Tk library-file access and an evolution evaluator descendant still holding `err.txt` during Windows cleanup. The Tk file exists and fresh App startup passed. The evaluator now waits for the entire killed tree; resource limits, tests and promotion thresholds are unchanged. Its protected source must be committed and its existing seal verified before accepting evolution proposals. Coding guard failures now supply concrete safe recovery tool names instead of a generic retry instruction; scope and immutable-test enforcement are unchanged.

The repaired evolution case passed three repeats. A subsequent affected-module run passed 60 tests with another Tk initialization failure. The HUD fixture now uses the actual application's single-interface lifecycle, preserves its captured initial hidden-state assertion, and passed three fresh-process runs (5/5 each); production styling is unchanged. Coding generation now separates the command schema from the other tool schemas, preventing irrelevant `start` fields before generation without removing any tool. The final paired coding run is `live-coding-strict-schema/`; earlier interrupted diagnostic worktrees are retained and are not counted as completed tasks.

Later coding diagnostics found and fixed automatic Python bytecode dirtying the worker. The final paired check is now `live-coding-verified-worker/`. Assigned assembly workers also avoid repeated unchanged-write reasoning: only after every implementation file has changed, no command is running and fresh independent contract validation passes may the worker finish without another inference. The parent still validates the assembled project before copying any result. Standalone tasks and failing contracts retain their original completion/repair gates. **47 worker/workload/HUD regressions passed**, including actual failed checks before repair, immutable test assertions and real LocalGithub assembly. Interrupted diagnostics are not accepted task completions.

Affected regression before the DAG repair: **387 passed / 2 skipped**; DAG/native/planner follow-up: **98 passed**. The complete application-suite rerun after the live fix is `final-candidate-full-tests.txt`; consult its final verdict, not progress dots. Launcher reports **ready** for dependencies/configured services; optional cloud inference remains unchecked. Earlier development full run: **3,917 passed / 150 skipped / one native-UI fixture failure**, subsequently hardened and checked separately.

[student_system_live.py](../scripts/verification/student_system_live.py) reproduces complete file, synthetic speech, media, public coding and research checks in new output directories. It does not export private media titles or capture the microphone.

LoRA `review_required` does **not** satisfy existing ModelRegistry sealed promotion/export gates. Merged reload, serving export, sealed regression evidence and explicit activation approval remain unexecuted. No adapter was promoted.

### Historical exploratory comparisons

Evidence is under [the dated packet](../artifacts/jarvis-audit/small-model/2026-10-21/). Its folder uses the UTC start date; this report uses IST. The native matrix uses identical nine public first-step requests for Windows, YouTube, Spotify, Blender, Unreal, coding, research, autonomous file work and an unfamiliar capability. It runs real local inference and independently checks expected tool selection, while dispatching no app actions. Literal argument preservation is recorded separately. Two repetitions per case are exploratory, not a robust quality study. Warm/cold order, model switching and concurrent regression load affect these measurements.

| Configuration | Samples | Planning p50 | Planning p95 | Expected tool selected |
|---|---:|---:|---:|---:|
| Configured 9B | 18 | 9.52 s | 20.38 s | 16/18 |
| Direct 4B candidate | 18 | 6.89 s | 26.04 s | 18/18 |
| 4B-first + 9B hierarchy | 18 | 10.97 s | 36.90 s | 17/18 |
| Direct 2B candidate | 18 | 4.08 s | 7.67 s | 18/18 |

The mixed 4B-first hierarchy regressed p50/p95 despite faster routine proposals. Switching costs matter. These are configuration comparisons on the candidate runtime, not a checkout of the old source or a before/after voice benchmark. No equal-intelligence or overall dramatic speedup claim follows from them.

[small_model_benchmark.py](../scripts/verification/small_model_benchmark.py) records Ollama loading, prompt processing and output generation timings, route choice, errors and GPU snapshots. Later runs also record model residency and benchmark-process RSS. Snapshot VRAM is not peak VRAM, benchmark-process RSS is not whole-system model RAM, and load time alone does not isolate switching overhead. Use `--executor` to compare both students and `--cases` to select a subset.

[student_execution_benchmark.py](../scripts/verification/student_execution_benchmark.py) pairs 9B and the hierarchy on public files in an owned directory, dispatches through the actual ToolRegistry, and grades exact bytes independently. It includes one read, a coding prerequisite and a two-read workflow. It does not run the full voice/Brain application loop.

The bounded live checks above do not establish comprehensive app coverage, Unreal editor/project outcomes, general complex coding quality, long autonomous/unfamiliar competence, physical speech, sustained resources or natural-failure recovery reliability. These remain separate gates in [CLAUDE_HANDOFF.md](CLAUDE_HANDOFF.md). No UI layout changed; no screenshot is fabricated.
