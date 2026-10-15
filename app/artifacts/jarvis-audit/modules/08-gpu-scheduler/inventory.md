# Prompt08 GPU scheduler/resource audit — 2026-10-15 IST

**30 catalog PASS,2 BLOCKED (JRV-08-002/012);0 FAIL/SKIPPED/NOT RUN.** Shared native speech ownership remains incomplete; no whole-system production certificate.

Repo `e9f6f735bc310d11e3cdecfbf95a85d96b170ec2`, branch `codex/jarvis-prove-fix-audit`; Windows/Python3.10.6, actual NVIDIA RTX3050 Laptop4096MiB, Ryzen7/32GB target. Existing dirty work preserved in app/, not its InsTAREELS alias. No personal delete/account write, new ability/install/download, global GPU environment change, driver reset, forced CUDA clear, commit or deployment. One native heavyweight request at a time; no microphone/speaker/GUI acceptance run.

| Claim | Actual path | Assertion / limit |
| --- | --- | --- |
| Physical polling / primary envelope | [gpu_scheduler.py](../../../../jarvis/gpu_scheduler.py):memory/allocation/configured | Missing GPU→CPU; partial offload;20% arithmetic margin over calibrated9b envelope, not universal physical OOM protection |
| Cross-process priority/ownership | Registry.state, Lease.acquire/close | Existing process fixtures,100 five-way turns, role/priority/owner identity validation, dead-owner reap, cancelled waiter preserves active owner |
| Native request lifecycle/cache | install | Hardware-probe failure cleanup, no retry, bounded wait, exact cache identity handoff/reuse, unowned changed cache untouched; no active-kernel preemption |
| Operational metadata | Registry.event/status, Lease.event | Allowed scalar fields, UUID/categorical failure, model label validation; state size/depth/queue bounds |
| Optional idle learning | [self_evolution.py](../../../../jarvis/self_evolution.py):SelfEvolution._resources_ok | Low or unknown resource readings defer work; idle/user-busy thresholds retained |
| Large coder selection | [repo_abilities.py](../../../../jarvis/repo_abilities.py):AbilityForge.pick_model | Initial preferred/fallback size + RAM margin; low-RAM fixture refuses both; unknown30b GPU footprint forces CPU, no native30b load |
| Speech | [speech.py](../../../../jarvis/speech.py), f5_speech.py, kokoro_speech.py, audio.py | No speech_worker.py in checkout; F5/Whisper outside shared coordinator.002/012 BLOCKED, not proved by Ollama mocks |
| Task requests | [brain.py](../../../../jarvis/brain.py):BrainClient | Existing owned worker/proxy paths use scheduler integration; no tool actions or model settings changed by this audit |


System map and existing GPU-priority, self-evolution, repo-abilities, crash-recovery guides inspected. Current policy: enabled/helper_gpu=false, primary12/codex9 layers, reserve512MiB, wait120s, warm1800s, CPU threads12. Configured F5 CUDA raises effective speech reserve from1024 to2048MiB. These are current config observations; historical October8 numbers remain dated. No actual user configuration was changed.

## Executed baselines and regressions

Corrected baseline: **28 PASS/4.62s**, [XML](existing-baseline-corrected.xml). An initial nonexistent test_resource_policy.py invocation collected no assertions: [collection error](existing-baseline.xml). New fault baseline:7 actual failing variants plus1 incorrect Forge class import in [initial XML](reproduced-failures.xml); corrected AbilityForge RAM repro [fails here](ram-reproduced.xml). Tight-headroom/32K-context20% margin [also failed](margin-reproduced.xml); smaller8K context already fit and is not treated as a defect. All accessible failures now have executed regression proof.

Final targeted: **219 PASS/4 explicit BLOCKED skips**, 47.18s,[XML](cases-and-contracts.xml). Full `python -m pytest tests -q --tb=short`: **2213 PASS/7 explicit BLOCKED skips**, 353.93s,[XML](full-regression.xml). Suites overlap; do not sum. Launcher `python -m jarvis.launcher --check`: **ready**, [redacted check](readiness.json). One pywinauto STA COM warning was reported; readiness is not live contention proof.

Targeted command: `.venv/Scripts/python.exe -m pytest tests/test_gpu_scheduler_audit.py tests/test_gpu_scheduler.py tests/test_self_evolution.py tests/test_repo_abilities.py tests/test_model_routing_audit.py tests/test_voice_tts_audit.py tests/test_audit_result_accounting.py -q --tb=short --junitxml=artifacts/jarvis-audit/modules/08-gpu-scheduler/cases-and-contracts.xml`.

## Matched state-I/O benchmark

Identical empty registry polls/OS locks,20warm +5cold samples per version. Cold recreates Registry only, not the process/disk/model cache. Baseline is saved pre-change source; no model allocation or network inference in this microbenchmark. Tracemalloc includes mock accounting.

| Build/mode | Samples | p50 ms | p95 ms | Atomic promotions | Traced peak bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| before_cold_read | 5 | 2.5372 | 2.7200 | 5 | 57766 |
| before_warm_read | 20 | 2.4942 | 2.6822 | 20 | 38688 |
| after_cold_read | 5 | 0.9945 | 1.0587 | 0 | 46375 |
| after_warm_read | 20 | 0.9007 | 1.4970 | 0 | 46913 |

[50 samples](benchmarks.csv), [summary](benchmark-summary.json). Retain no-change write elimination:20→0 warm atomic promotions and p95 **2.6822→1.4970ms**. Traced peak **38688→46913 bytes** increases slightly with bounded validation/read machinery; no memory reduction claimed. A preliminary fixed200001-character read allocated~245KB per tiny poll; bounded4096-character chunks avoid that overhead in the retained implementation. No A/B native inference or first-audio speedup inferred.

## Native measurements and scope

No model was resident at the initial observation. Cached installed9b GPU-cold invocation: TTFT **37.250s**, load_duration **34.831s**, full reply **37.516s**; following warm TTFT **0.515/0.437s**. [Cold observation](native-cold-observation.json). Later warm TTFT **0.656/0.562/0.453s**, [warm observation](native-local.json). Actual allocation4layers/16384context; sampled peak physical GPU **1341MiB**. Observer-process RSS is recorded separately, not Ollama/system peak RAM. Sampling can miss brief spikes. Registry readback is idle after each series; warm model remains cached, so lease release is not physical immediate eviction.

These sequential arithmetic probes establish actual transport/admission/cache behavior, not speech coexistence,30B safety, driver-reset recovery on real hardware, or broad answer quality. They ran during this audit before final metadata/error and small-config margin guards; normal default allocation/settings stayed identical. Final guard behavior is covered by the full regression. No forced shared-model unload or global environment tuning was used.

## Open blockers and risk

002: F5 arrival during9b generation cannot be certified because speech has no shared ownership/admission handshake.012: there is no stuck-TTS shared lease for this watchdog to restore safely. Real speech contention is therefore BLOCKED by missing implementation prerequisites. No unsafe timeout evicts a live owner or kills shared Ollama. Existing active inference can finish before higher priority queued work; cooperative callbacks are not kernel preemption. Other applications can allocate memory after polling.30B/RAM limits remain initial-size heuristics; peak activation/RAM stress and F5/Whisper behavior require separate safe work.

[32 case ledger](tests.jsonl), [failures](failures.md), [changes/decisions](changes.md), [compatibility](compatibility.md), [rollback](rollback.md), [exact files](files-changed.json), [scoped diff](source.patch).
