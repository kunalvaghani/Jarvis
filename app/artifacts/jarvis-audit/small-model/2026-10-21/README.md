# Small-model intelligence evidence

Started 2026-10-21 UTC / 2026-10-22 IST. Baseline repository commit `df713f1`; candidate branch `codex/small-model-intelligence`. [Architecture and limits](../../../../docs/small-model-intelligence.md).

Latest authoritative report: [FINAL_BUILD.md](FINAL_BUILD.md), with [derived quiet metrics](release-metrics.json). `release-*` comparisons supersede the earlier `final-*` performance headlines: routine work improved, mixed latency regressed. The final complete application verdict is `release-complete-build-tests.txt`; the earlier green 3,932/150 checkpoint predates the last scoped-read/speech fixes. `release-full-brain-read-verified-fixed/` and `live-speech-command-loop-fixed.json` record the final zero-inference integration checks, with preceding failures retained.

Earlier development evidence follows; its dates, measurements and limitations retain their original scope.

Earlier primary evidence (2026-10-22 IST):

- `final-native-planning/`: eighteen native proposals each; routine p50/p95 10.72/13.41 → 4.17/13.39 s (6/6 correct each), mixed 9.36/13.41 → 9.59/30.37 s (16/18 each). **Mixed tail latency regressed.** `final-derived-metrics.json` contains derived resource/switch statistics; raw rows retain load/prefill/generation timing.
- `final-owned-file-execution/`: actual model→ToolRegistry public reads, 6/6 verified each, p50/p95 14.86/21.33 → 9.94/16.86 s. `final-recovery-probe/`: deliberate invalid-inference injection, verified prerequisite preserved, 1/1 each; not natural recovery reliability.
- `live-applications-final/`: real Blender creation/reopen/geometry assertions passed for both configurations. Unreal read only the installed 5.8.2 manifest. Earlier `live-applications*` failures explain the missing-folder native schema correction and subsequent test scope-alias correction.
- `full-brain-host-live/` and `dag-read-diagnosis/`: whole Brain exposed empty DAG read operands in both configurations. `full-brain-live-fixed/`: same six actual Actions/Brain/DAG tasks passed after stricter arguments and deterministic exact-read compilation. Routine single read now calls no model. Public proposals/receipts are recorded; fixture private runtime directories are excluded from Git.
- `live-youtube-exact/`: actual exact public video in Chrome Default, independently verified playing and then paused. `live-media-existing-sessions/`: YouTube and Spotify state change, independent fresh readback, original state restoration, zero inference. Initial `live-public-playback/` failed; public YouTube query was ambiguous. Search refusal is preserved, not recast as success.
- `live-synthetic-speech/`: installed Kokoro and GPU Whisper recognized generated public PCM. No microphone or speaker capture. `live-voice-model-contention/` records actual concurrent submissions separately; completion does not mean acceptable audible latency.
- `live-public-research/`: both paused on a confirmed text-vs-JSON receipt verifier defect. `research-readonly-diagnosis.txt` confirmed actual successful page retrieval. `live-public-research-fixed/` records the repeated sourced tasks after repair. `research-fix-regression.txt`: 99 passed, including wrong-source/no-match/empty receipt rejection.
- `live-coding-workloads/`: initial configured 9B workload plans failed ownership validation before edits. `live-coding-narrow-scope/`: fresh paired arithmetic task clarifies read-only documentation, retains frozen tests and runs an independent execution oracle; consult its result for acceptance.
- `teacher-student-proof.json`: real public verified 9B trace compiled and indexed; changed-target retrieval passed. General transfer execution remains untested. `public-teacher-candidates.jsonl` is explicitly unreviewed; no fine-tuning occurred. `cpu-embedding-semantic-check.txt` passed; `embedding-cpu-observation.json` reports CPU residency (`size_vram:0`).
- `final-source-affected-regression.txt`: 387 passed / 2 skipped before the final live fixes. `live-dag-fix-regression-final.txt`: 98 passed; `research-fix-regression.txt`: 99 passed. `final-candidate-full-tests.txt` is the complete application rerun; later final checks must identify their own source scope. The accidentally unscoped vendored-project collection run is excluded from Git and is not an application-suite result.
- `live-candidate-launcher-check.json`: ready for installed dependencies/configured services, optional cloud unchecked. `documentation-links.json`: all checked links resolve. No new executable packaging or dependency installation is required; Jarvis keeps its existing Python/Start Jarvis launcher.

Earlier development checkpoints follow; their timings and verdicts retain their original scope.

- `native-planning/`: same nine public first-step fixtures, two repetitions, configured 9B versus direct 4B versus 4B-first hierarchy. Real local native inference; no external app actions. Expected tool and literal argument checks are separate.
- `native-planning-2b/`: installed 2B on the same eighteen fixtures. Download authorization was supplied by the user. Every official manifest blob hash and byte count matched before registration (`2b-ipv4-download.txt`). The earlier upstream IPv6 failure log is redacted.
- `owned-file-execution/`: two paired repetitions of one-read, coding-prerequisite and two-read workflow tasks. Real inference plus actual ToolRegistry; only reads of newly owned public fixture files. Exact-byte oracle: baseline **6/6**, 2B-first **6/6**. These are component end-to-end tasks, not a full Brain/voice run. Concurrent regression load and model warm/cold order affect timing.
- `focused-tests.txt`: **72 passed**, first host-context focused run. The preceding sandbox run's **21 temporary-file atomic-replace failures / 51 passes** were environment-specific; production checks were not relaxed.
- `focused-tests-final.txt`: **82 passed**, expanded routing/GPU/teacher/privacy/preparation coverage at that checkpoint.
- `integration-tests.txt`: planner, task state, procedural memory, cloud privacy and GPU integration, **165 passed / 2 skipped**.
- `learning-tests.txt`: idle self-evolution and existing offline AZR compatibility, **49 passed**.
- `launcher-check.json`: host dependency/configuration check **ready**, optional Groq not live checked. Its configured planner remains 9B; it does not certify live small-model quality.
- `full-regression.txt`: complete-suite run output; consult its final line for completion rather than inferring a pass from progress dots. Final results are recorded in the architecture report and cumulative handoff after completion.

Raw model durations are Ollama seconds converted from nanoseconds. Reported p95 uses nearest rank. Snapshot VRAM is not a peak; no whole-system RAM/speech-contention certification is implied. No actual LoRA run or adapter promotion occurred. Existing live application, security and recovery acceptance gates remain separate.
