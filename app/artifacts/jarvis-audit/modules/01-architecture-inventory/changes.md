# Retained changes and measured tradeoffs

Updated2026-10-15 IST. [Exact scoped runtime/manifest delta](source.patch), [source hashes](source-hashes.json). Runtime: `config_contract.py`, launcher.preflight, main.App, agent_events. Tests: architecture cases and truthful parameter accounting. QA scripts: inventory/benchmark/report and catalog reconciliation/report preservation. System map, README/doc index and artifact ledger are updated.

Keep: observed security/correctness faults repaired without new dependencies, services, provider names or permissions. Configuration cap2000000bytes,128 root fields, depth32 and100000 values. Unknown root fields warn; subsystem validators retain enum/budget authority. Lifecycle logs keep trace UUIDs and typed categories, not arbitrary source/response/credential payloads.

Alternating captured preimages/current code, five cold launches and twenty warm requests each: warm p95 15.649→15.985ms; cold process p95 814.959→803.933ms; sampled warm RSS p95 33841152→33841152 bytes. [Paired JSON](benchmark-paired.json), [CSV](benchmarks.csv). This is a small validation-cost tradeoff, not a startup speedup. Fixed fields remove the baseline synthetic secret-payload retention; zero external effects in fixtures. No model TTFT/GPU peak claim.

Initial sequential and paired-under-regression-load measurements remain saved. The latter showed larger jitter while the full suite was running and is not used to attribute a code speedup. The final paired comparison ran after that suite stopped. Cold baseline loading uses trusted captured module source in an isolated namespace, adding import-loader overhead; these numbers are bounded metadata fixtures, not full-app startup latency.

Full regression: **1897 tests passed**, no failed/error assertions. Architecture/neighbor contract XMLs remain separate overlapping runs. Python support, missing guide and live coverage prevent all-system production certification despite passing scoped tests.
