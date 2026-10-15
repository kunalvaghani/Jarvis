# Reproductions and unresolved work

Initial dedicated baseline: **9 passed, 7 failed** in 6.09 seconds, [unmodified-source XML](baseline.xml). Failures: old screen retained after window switch; NaN/boolean/string rate and string enabled option; missing tick-error diagnostics; proposed-but-unexecuted task learned as success. Four invalid-option variants count as four assertions, not four distinct bugs.

First neighboring run: 59 passed, one failed because its old test expected raw disk-error text. The privacy contract now keeps only the exception type; the assertion was updated to verify payload omission, while preserving the single action call assertion. Final targeted XML contains the passing run.

Heap selection candidate failed the performance keep criterion: warm tick P95 0.023488 → 0.027676 ms; reverted before final validation. [Candidate raw data](benchmarks-heap-candidate.csv).

An initial full-regression attempt was interrupted after reverting that candidate; it produced no complete XML and is not counted as a passing run. Final full-regression.xml is the completed retained-source run.

An unscoped `pytest -q` attempt accidentally collected vendored repositories and failed collection (2335 errors, 15 skips, 186.56 seconds); missing independent dependencies included blockbuster, deerflow and pydantic. It is not a Jarvis test pass. Raw evidence is retained privately at `.jarvis-runtime/jarvis-audit/module02-pre/unscoped-collection-errors.xml`; no packages were installed. The final regression explicitly selects `pytest tests`, Jarvis's established suite. Vendored projects require their own declared environments and validation.

Open: CPU/native-parser hard-hang containment, task-ID disagreement enforcement, complete cognition trace correlation, remaining catalog fault/semantic/resource journeys. Stalled-thread telemetry and rejection of arbitrary serializers do not establish those broader guarantees. Live microphone/GPU/GUI/cloud/account validation was not run; native UIA foreground restrictions from the earlier audit still apply. Python 3.10 EOL remains a release risk.
