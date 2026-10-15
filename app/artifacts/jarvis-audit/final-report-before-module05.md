# Jarvis Prompts 02–04 audit — 2026-10-15 IST

**Accessible audit work for Prompts 02–04 is complete: 93 catalog cases PASS, 3 acoustic cases BLOCKED, 0 FAIL, 0 SKIPPED and 0 NOT RUN in this 96-case scope. Whole-system production readiness remains uncertified.** Every PASS links to executed fixture assertions; no live acoustic or account acceptance is inferred.

Full `pytest tests -q --tb=short --junitxml=artifacts/jarvis-audit/completion-full-regression.xml`: **2020 PASS, 3 BLOCKED acoustic skips, 322.67 seconds**. One pywinauto STA COM threading-mode UserWarning, no test failure. [Full output](completion-full-regression.xml). Targeted: **120 PASS/3 BLOCKED in 12.95 seconds**, [output](completion-targeted.xml). Runs overlap and must not be summed. Accounting tests exercise failed variants and reviewed BLOCKED classification in the full run.

## Checkout and evidence

Commit `e9f6f735bc310d11e3cdecfbf95a85d96b170ec2`, branch `codex/jarvis-prove-fix-audit`, Windows, Python 3.10.6, RTX 3050 Laptop 4096 MiB, 32 GB target RAM. GPU census: 2700 MiB used, 1396 MiB free; no new GPU workload. Existing dirty changes preserved; no commit, publish, deployment, model/package installation or external write. Readiness check and soak results are linked below and remain separate from live acceptance.

[02 source matrix and tests](modules/02-perception-cognition/inventory.md), [03 source matrix and tests](modules/03-intent-direct/inventory.md), [04 source matrix and tests](modules/04-voice-stt/inventory.md). Prompt 04's inferred voice_input.py is a text-policy helper; capture actually lives in audio.py/whisper_backend.py/main.py. Architecture docs are claims mapped to these entry points, not runtime proof.

## Repairs and decisions

02: retained stale-window/race fixes, finite typed admission and off-tick persistence; added deep-history recovery, escaped Unicode stats, stalled-sensor health, task UUID binding and stale-result/finish rejection. CPU-bound Python sensor test leaves cognition responsive; hard native-hang isolation is unresolved. Prior heap ranking optimization was reverted after regression.

03: retained four anchored intent rules and compound punctuation repair; bounded parser input to 100,000 characters and converted recursion/Unicode errors to categorical validation failures. Latest/most-recent document requests ask for filename/path/folder before model or opening. Stable reflexes, aliases and learned-command precedence are asserted with no model/network calls.

04: resample release audio before final enqueue; reject duplicate final utterance IDs while accepting explicit second requests; validate settings before hooks/capture; stop drains owned queues, decoder join bounded to two seconds. Stalled decoder retains ownership, preventing duplicate microphone creation. Generic typed fallback and categorical metadata/UUID health avoid raw exception payloads. Removed one redundant VAD pad copy; inference model, quantization and endpoint defaults unchanged.

## Equivalent paired CPU measurements

All values in milliseconds, P50 / P95. Twenty alternating warm samples and five fresh-process cold samples per build on this machine; CPU fixtures only. No peak-memory, GPU speed, WER, TTFT or first-audio claim. [02 CSV](modules/02-perception-cognition/benchmarks-completion-20261015.csv), [03 CSV](modules/03-intent-direct/benchmarks-completion-20261015.csv), [04 CSV](modules/04-voice-stt/benchmarks-completion-20261015.csv).

| Module/fixture | Before | After |
| --- | --- | --- |
| 02 warm_tick | 0.0218 / 0.0223 | 0.0218 / 0.0222 |
| 02 cold_startup | 729.9323 / 746.2925 | 753.3563 / 781.6046 |
| 03 warm_per_phrase | 1.8081 / 2.3539 | 0.8650 / 1.4643 |
| 03 cold_import_and_batch | 539.6400 / 548.6491 | 507.6145 / 543.8222 |
| 04 warm_capture | 1.9166 / 2.5797 | 2.0550 / 2.6735 |
| 04 cold_fixture_startup | 2102.0650 / 2129.9890 | 2042.0304 / 2124.6759 |

02 scheduling median 250 ms in both builds; sampled max 266 → 265 ms. Cold cognition initialization increased; no universal speedup claimed. 03 warm routing benefit is corpus-specific and includes formerly rejected routes. 04 capture timing increased slightly; correctness takes priority: expected 200 ms at 16 kHz now yields **3200 samples**, previously6400. Retain correctness fix; do not market speech latency improvement. Prior 02/03 raw samples were overwritten before archival; historical summaries remain in archived reports. Fresh CSVs are preserved.

## Exact catalog accounting and modules

All 1,184 unique IDs retained: **{'PASS': 144, 'FAIL': 0, 'BLOCKED': 3, 'SKIPPED': 0, 'NOT RUN': 1037}**. [Tier/category/run totals](summary.json), [all assertions and case scope](test-results.jsonl), [exact remaining IDs](remaining-case-ids.txt). Cases outside 02–04 retain previous evidence or NOT RUN; they are not silently promoted by unrelated regression tests. Module 01's earlier fixture coverage remains historical.

| Module | Name | Status |
| --- | --- | --- |
| 01 | architecture-inventory | PARTIAL |
| 02 | perception-cognition | FIXTURE COMPLETE |
| 03 | intent-direct | FIXTURE COMPLETE |
| 04 | voice-stt | LIVE ACOUSTIC VALIDATION BLOCKED |
| 05 | voice-tts | PARTIAL |
| 06 | questions-context | PARTIAL |
| 07 | model-routing | PARTIAL |
| 08 | gpu-scheduler | PARTIAL |
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

## Compatibility, risks and next validation

Firecrawl checked official current sources on 2026-10-15: [faster-whisper1.2.1](https://github.com/SYSTRAN/faster-whisper/releases) released2025-10-31; [CTranslate2v4.8.3](https://github.com/OpenNMT/CTranslate2/releases/tag/v4.8.3) released2026-10-13; installed1.2.1/4.6.0. New CTranslate2 includes a CUDA TopK edge-case fix; live native compatibility on this4GB system is unverified, so no blind upgrade. [Runtime prerequisites](https://github.com/SYSTRAN/faster-whisper) require CUDA12/cuDNN9 for recent releases. [Official Python status](https://devguide.python.org/versions/) lists3.10 EOL2026-10-01. [02 sources](modules/02-perception-cognition/compatibility.md), [03 sources](modules/03-intent-direct/compatibility.md), [04 installed/release matrix](modules/04-voice-stt/compatibility.md).

Next incomplete IDs: **JRV-04-001**, **JRV-04-002**, **JRV-04-003**. Provide dedicated GPU headroom and labeled quiet-room, background-TV and long-pause audio/reference timings, then execute actual Whisper inference and measure command accuracy/WER, false activations and endpoint latency. Text/fake-PCM tests cannot satisfy these acoustic assertions. No recordings, giant downloads or personal audio uploads were made. After this scope, the next unrun module/case is **05/JRV-05-001**. [Deterministic resume instructions](resume-02-04.md).

Further release risks: Python EOL, two environment dependency checks lacking pip, native parser/GIL hang containment, host ability isolation, live cloud/GUI/account contracts, arbitrary prose privacy and wider log redaction, long GPU contention and actual voice accuracy. [Security findings](security-findings.md). Fixtures observed zero unauthorized effects and uncertainty replay; this is bounded evidence, not universal proof.

## Files, rollback and verification

[Exact scoped file list](completion-files.json), per-module source patches/hashes and rollback: [02](modules/02-perception-cognition/rollback.md), [03](modules/03-intent-direct/rollback.md), [04](modules/04-voice-stt/rollback.md). Restore only reviewed hunks from captured preimages; never reset the dirty checkout or replay old task queues. Runtime metadata schema is additive; no new dependency/service. [Readiness](completion-readiness.json), [30-second synthetic soak](completion-soak.json), [verification record](completion-verification.json). Prior reports and XML remain in history folders; baseline failures are evidence, not final unresolved regressions.
