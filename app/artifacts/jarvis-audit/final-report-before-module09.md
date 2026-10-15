# Jarvis audit through Prompt08 — 2026-10-15 IST

**Prompt08:30 catalog PASS,2 BLOCKED (002/012),0 FAIL/SKIPPED/NOT RUN.** Targeted **219 PASS/4 explicit BLOCKED skips**; full regression **2213 PASS/7 explicit BLOCKED skips**, 353.93s. [Targeted XML](modules/08-gpu-scheduler/cases-and-contracts.xml), [full XML](modules/08-gpu-scheduler/full-regression.xml); scopes overlap. Launcher **ready**, [redacted check](modules/08-gpu-scheduler/readiness.json). Whole-system production acceptance remains open.

Repo `e9f6f735bc310d11e3cdecfbf95a85d96b170ec2`, branch `codex/jarvis-prove-fix-audit`, Windows/Python3.10.6, actual RTX3050 Laptop4096MiB and Ryzen7/32GB target. Existing dirty work preserved. No real cloud/account write, personal delete, install/download, driver reset, forced CUDA clear, global model setting change, new ability, commit or deployment. One native heavyweight probe at a time. [Source-map-to-code matrix](modules/08-gpu-scheduler/inventory.md), [exact changed files](modules/08-gpu-scheduler/files-changed.json), [scoped preimage diff](modules/08-gpu-scheduler/source.patch).

Repairs cover malformed/unbounded GPU state, redundant poll writes, leaked admission on hardware-probe failure, duplicate acquisition, release/telemetry boundaries,20% primary-envelope margin with tight configured headroom and low/unknown-resource learning. [Baseline failures](modules/08-gpu-scheduler/failures.md), [changes/tradeoffs](modules/08-gpu-scheduler/changes.md), [risk/rollback](modules/08-gpu-scheduler/rollback.md).

Matched20warm/5cold state polls per build: warm p50/p95 **2.4942/2.6822→0.9007/1.4970ms**; atomic promotions **20→0**; traced peak **38688→46913 bytes**. [All50 samples](modules/08-gpu-scheduler/benchmarks.csv). Cold here recreates Registry, not model/disk cache. No model inference/RAM gain inferred.

Actual installed9b with no prior resident model: cold TTFT **37.250s**, provider load duration **34.831s**; final warm TTFT **0.656/0.562/0.453s**.4GPU layers/16K context; sampled physical peak **1341MiB**. [Cold](modules/08-gpu-scheduler/native-cold-observation.json), [warm/readback](modules/08-gpu-scheduler/native-local.json). These are unpaired synthetic arithmetic observations, not full voice/accuracy/peak-RAM acceptance. No forced model eviction for a benchmark.

F5/Whisper have no shared lease handshake: speech-arrival002 and stuck-TTS012 remain **BLOCKED**. Priority is queued/cooperative, not running-kernel preemption. Cache retention means admission release is not physical immediate VRAM free. Other applications may allocate after polling;30B peak RAM and native contention are unproved. [Official sources/releases/compatibility](modules/08-gpu-scheduler/compatibility.md); local Ollama0.40.0 is older than0.40.4 (12Oct2026), without an unapproved install.

## Catalog and modules

1184 unique IDs: **{'PASS': 265, 'FAIL': 0, 'BLOCKED': 7, 'SKIPPED': 0, 'NOT RUN': 912}**. [Case/assertion ledger](test-results.jsonl), [tier/category/run totals](summary.json), [module08 cases](modules/08-gpu-scheduler/tests.jsonl), [exact remaining IDs](remaining-case-ids.txt). [Preserved module01–07 report](final-report-before-module08.md) retains earlier metrics/baselines and live cloud/acoustic risks.

| Module | Name | Status |
| --- | --- | --- |
| 01 | architecture-inventory | PARTIAL |
| 02 | perception-cognition | FIXTURE COMPLETE |
| 03 | intent-direct | FIXTURE COMPLETE |
| 04 | voice-stt | LIVE ACOUSTIC VALIDATION BLOCKED |
| 05 | voice-tts | LIVE ACCEPTANCE BLOCKED |
| 06 | questions-context | FIXTURE COMPLETE |
| 07 | model-routing | FIXTURE COMPLETE / LIVE CLOUD BLOCKED |
| 08 | gpu-scheduler | PARTIAL / SHARED SPEECH COORDINATION BLOCKED |
| 09 | deliberation | PARTIAL |
| 10 | dag-planning | PARTIAL |
| 11 | skill-selection | PARTIAL |
| 12 | tool-registry | PARTIAL |
| 13 | desktop-control | PARTIAL |
| 14 | browser-playwright | PARTIAL |
| 15 | app-research | PARTIAL |
| 16 | memory | PARTIAL |
| 17 | rag-documents | PARTIAL |
| 18 | repo-learning | PARTIAL |
| 19 | ability-forge | PARTIAL |
| 20 | self-evolution | PARTIAL |
| 21 | native-coding | PARTIAL |
| 22 | web-development | PARTIAL |
| 23 | gmail | PARTIAL |
| 24 | whatsapp | PARTIAL |
| 25 | media | PARTIAL |
| 26 | realtime-data | PARTIAL |
| 27 | gods-eye | PARTIAL |
| 28 | sandbox-deerflow | PARTIAL |
| 29 | reverse-engineering | PARTIAL |
| 30 | harness-planners | PARTIAL |
| 31 | ui-island-pip | PARTIAL |
| 32 | service-recovery | PARTIAL |
| 33 | mcp-integrations | PARTIAL |
| 34 | dependencies | PARTIAL |
| 35 | security | PARTIAL |
| 36 | observability | PARTIAL |
| 37 | e2e | PARTIAL |

First remaining module08 IDs002/012; earliest global unresolved JRV-04-001. Next unexecuted catalog ID **JRV-09-002**; module09 work has prior isolated proofs and must not double count them. Resume/rollback linked above. No full production certification or universal two-second voice/memory-safety guarantee is claimed.
