# Final source build and bounded live verification

2026-10-22 IST. Branch `codex/small-model-intelligence`, baseline `df713f1`. This is the existing Windows Python application, started with `app/Start Jarvis.cmd`; no replacement executable, package installation, model activation or publication is required. The authorized official Ollama Qwen3.5 2B inference model is installed; machine configuration selects it for routine execution. 9B remains the reasoning/coding/vision model. 4B remains configurable.

Build verification: **3,936 passed / 150 gated skips / zero failures**, 1,155.80 seconds. The final focused run passed **104 tests**. [Complete log](release-complete-build-tests.txt) · [focused log](release-read-speech-regression-final.txt) · [source manifest](source-manifest.json) · [machine-readable build checks](release-build-checks.json). All **325** inventoried source/config/test files match their hashes; compilation passed. The earlier 3,932/150 checkpoint predates the last literal-read and speech-alias changes.

[Final launcher check](release-final-launcher-check.json): **ready** for installed dependencies/configured local services; optional cloud and hosted LocalGithub services remain unchecked. [Final actual native App startup/owned close](release-ui-startup.json): **passed**, microphone stayed stopped, no screenshot or private desktop export. [Normal evaluator seal](release-evaluator-seal.json): **matched committed evaluator**, `1b1354e38a80b3809f03fe3173cb3bf7d5b7b97fa0503afd0379cfbff8828616`. No candidate/model promotion or activation was performed.

## Measured comparison

Latest quiet controls compare the same public tasks with 9B-only and student-first configuration on the candidate runtime. They are not a checkout-and-run comparison against the original source. Two repeats per category are exploratory; p50 is the median and p95 the nearest rank. Fixed run order and unequal initial model residency contribute to differences; these are not matched cold/warm estimates. First-proposal accuracy does not mean the external task completed.

| Test | 9B-only p50 / p95 | 2B-first p50 / p95 | Verified outcome |
|---|---:|---:|---|
| Routine Windows / YouTube / Spotify first proposals, 6 each | 10.85 / 34.22 s | 3.72 / 10.85 s | Expected tool 6/6 each; all student-first routine calls used 2B |
| Mixed nine-category first proposals, 18 each | 9.02 / 34.22 s | 9.72 / 59.70 s | Tool 16/18, exact literal 14/18 each; no external dispatch |
| Real model→ToolRegistry public file tasks, 6 each | 15.84 / 20.86 s | 16.36 / 58.14 s | Completed / exact bytes 6/6 each; 8 dispatched reads each |
| Routine subset of those file tasks, 2 each | 15.84 / 19.18 s | 6.89 / 10.91 s | Exact bytes 2/2 each |
| Injected invalid inference after an already verified prerequisite, 1 each | 10.40 s | 9.99 s | Remaining file completed; prerequisite not repeated |

Routine proposal median improved **66%**. Mixed proposal median worsened **8%**, p95 **74%**. Mixed real-tool latency also regressed; the older packet's 33% median improvement did not reproduce. One natural student rejection in the real-file matrix escalated to 9B, retained progress, then returned remaining execution to 2B. Neither that case nor the deliberate fault probe establishes a recovery rate. **Equal intelligence and an overall system speedup are not demonstrated.**

Direct-model first proposals (18 each): 9B **9.02/34.22 s**, 4B **6.42/20.54 s**, 2B **3.41/15.16 s**; expected tools **16/18, 17/18, 18/18**, exact literals **14/18, 17/18, 16/18**. The 4B-first real-file control verified **6/6 each** but regressed **14.90/37.62 → 21.55/72.20 s**. 2B remains selected; these fixtures do not justify replacing 9B on difficult work.

Three observed hierarchy model transitions had Ollama load timers **7.51/49.50 s** p50/p95, not isolated switching overhead. File dispatch p50/p95 was **12.36/38.57 ms** versus **12.03/12.26 ms**. Routine post-inference GPU medians were **2,180/1,341 MB**; mixed GPU p95 **2,195/2,193 MB**. Aggregate Ollama RSS medians were **6,472/5,224 MB**, system-used RAM **23,013/21,832 MB**. Shared-host snapshots are not exclusive model consumption or allocator peaks. Raw load/prefill/generation timings, token rates and definitions are in [release-metrics.json](release-metrics.json), [native rows](release-native-planning/rows.jsonl), [2B file rows](release-file-2b/rows.jsonl), [4B file rows](release-file-4b/rows.jsonl) and [injected recovery rows](release-recovery/rows.jsonl).

## Actual live checks

| Capability / boundary | Observed result and limit |
|---|---|
| Native Windows commands | [6/6 Engine→status dispatcher→OS reads](windows-direct-live.json), zero inference; CPU, memory and Windows version |
| Full Brain files / workflow / unfamiliar task | [3/3 each configuration](full-brain-live-fixed/results.json), actual Actions/Brain/DAG/ToolRegistry with independent public-byte checks; unfamiliar documented-device fixture is not general novel-task competence |
| Literal scoped read | [4/4 complete](release-full-brain-read-verified-fixed/results.json), exact public contents verified, zero inference, 0.063–0.125 s. This is deterministic execution, not evidence that 2B reasoned successfully |
| Blender | [Both configurations](live-applications-final/summary.json) created/saved/reopened a real disposable scene; PublicCube, 8 vertices, 6 polygons, location `[1,2,3]`. Both retained 9B |
| Unreal | Same application packet inspected installed 5.8.2 build manifest only; editor/project manipulation is not supported by the existing inspect-only adapter and was not accepted |
| YouTube | [Exact public video](live-youtube-exact/results.json) independently verified playing in pinned Chrome Default, then paused. Earlier ambiguous query correctly stopped |
| YouTube / Spotify controls | [Live state changes and fresh SMTC readback](live-media-existing-sessions/results.json); original state restored; zero inference. Does not certify all search queries, OAuth or staged expanded connectors |
| Coding | [1/1 each configuration](live-coding-verified-worker/results.json), actual configured native 9B backend, assigned file scope, frozen unit tests, LocalGithub combined validation, independent AST/test oracle and completed TaskState. 298.22/348.99 s under concurrent host checks; no speedup claim |
| Research | [1/1 each](live-public-research-fixed/results.json), actual official Python documentation fetch and sourced dump/dumps answer. Bounded terminology/source checks plus manual answer inspection; no general semantic-quality score. 105.16/233.17 s under concurrent host checks |
| Generated speech command | [Configured Kokoro→GPU Whisper→Engine→CPU status→reply synthesis](live-speech-command-loop-fixed.json), zero LLM calls. Public generated PCM only, no microphone/speaker playback. 27.265 s including 17.329 s recognizer loading; dispatch 0.203 s |
| Voice/model contention | [4/4 concurrent submissions](live-voice-model-contention/results.json), 722 GPU samples max 3,444 MB. Some Whisper wait/decode calls took 37–48 s. Completion is not acceptable voice latency or an acoustic accuracy result |
| Teacher procedure transfer | [Indexed verified 9B procedure→actual 2B→new public target](live-procedure-transfer/results.json), exact bytes matched. Input TaskState envelope reconstructed from verified public trace; one case does not establish causal/general transfer gains |
| Embeddings | [Semantic retrieval check](cpu-embedding-semantic-check.txt) passed; [direct nomic API observation](embedding-cpu-observation.json) reports zero VRAM. Optional OpenViking/LiteLLM resource paths remain separate |

The late native-loop test initially passed 9B **2/2** and failed hierarchy **0/2**: 2B supplied the entire request as a filename; 9B repeated it. Exact `Read filename.ext in this folder.` now compiles directly, preserves the operand, binds the selected folder, rejects traversal/symlinks, and compares fresh disk/tool contents. An intermediate direct-path run correctly paused before its independent read verifier was added. [Original failure](release-full-brain-read-desktop/results.json), [intermediate failure](release-full-brain-read-literal-fixed/results.json) and repaired evidence remain distinct. The speech test initially transcribed “shows CPU usage” and timed out; a narrow read-only CPU alias repaired it. [Original speech failure](live-speech-command-loop.json) is retained. No action was blindly replayed after an uncertain write/click.

Other live-discovered repairs include stricter DAG read operands, source-bound plain-text scraper receipt verification, native command argument schemas, concrete rejected-tool recovery guidance, prevention of owned Python bytecode dirtying coding workers, and successful-contract completion of assigned assembly workers. Evolution resource cleanup waits for killed descendants before touching their output files. Promotion thresholds, held-out evaluator data, tool approvals, immutable tests and file ownership guards remain enforced. Test-only native-window/HUD lifecycle and aircraft-clock fixes preserve the original assertions.

## Remaining acceptance gates

Physical microphone/speaker acceptance remains **unverified by the user's explicit choice on 2026-10-22**; intentional microphone stop/Quit was respected. Unreal editor/project outcomes, broad coding/research/autonomy quality, sustained resources, statistically calibrated escalation and natural-failure recovery reliability remain open. The larger mixed-workflow tail is a measured limitation, not a completed performance objective.

The optional offline LoRA pipeline is implemented but actual training is unexecuted. Installed Transformers 4.57.6 lacks Qwen3.5 support; approved checksum-pinned original trainable weights and an authorized isolated dependency update are prerequisites. No private data was trained on, and no package/training-weight download, adapter activation or cloud inference occurred. Curated review, held-out comparisons, merged reload, serving export, sealed ModelRegistry promotion and explicit activation approvals remain separate gates. Idle maintenance reports readiness; it never starts training during foreground work.

Existing P31–P35/UI/security/release findings remain in the [cumulative handoff](../../../../docs/CLAUDE_HANDOFF.md). Completed implementation and bounded live checks are distinct from comprehensive release acceptance. No screenshot or full-system intelligence equivalence is fabricated.

## Reproduction

From `app/`, with the existing environments and authorized installed models, choose a **new** output directory for each run:

```powershell
.venv\Scripts\python.exe -m pytest tests -q --tb=short
.venv\Scripts\python.exe -m jarvis.launcher --check
.venv\Scripts\python.exe scripts/verification/small_model_benchmark.py --models qwen3.5:9b qwen3.5:4b qwen3.5:2b hierarchy --executor qwen3.5:2b --repeat 2 --out .jarvis-runtime/new-native-control
.venv\Scripts\python.exe scripts/verification/student_execution_benchmark.py --executor qwen3.5:2b --repeat 2 --out .jarvis-runtime/new-file-control
.venv\Scripts\python.exe scripts/verification/student_system_live.py --mode files --out .jarvis-runtime/new-full-brain-files
```

Additional live modes `coding`, `research`, `voice`, `contention`, `transfer`, `media` and `youtube_exact` have different side effects and scopes; inspect [the verification source](../../../../scripts/verification/student_system_live.py) before invoking them. The [architecture guide](../../../../docs/small-model-intelligence.md) describes configuration, training consent and retained safeguards. Verification does not authorize publishing or model promotion.
