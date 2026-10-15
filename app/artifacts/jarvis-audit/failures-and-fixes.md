# Failures and fixes — 2026-10-14 IST

Baseline: `python -m pytest tests/test_audit_resilience.py -q --junitxml=artifacts/jarvis-audit/baseline-tests.xml` ran 16 assertions: 8 failed, 8 passed. [Baseline XML](baseline-tests.xml) contains exact repro traces. Local paths in traces refer to owned synthetic fixtures.

| Fault | Cause / fix | Proof / rollback |
| --- | --- | --- |
| Attention overflow / amplification on clock rollback | `Percept.weight` allowed positive exp; clamp negative ages to zero | Four numeric-boundary assertions; restore pre-audit cognition.py |
| Fresh window blocked by 200 stale voices | Admission used raw salience while attention used age decay; both now use effective weight plus deterministic timestamp tie-break | Independent fresh-window rank changed false to true; stale-window fixture |
| Invalid statistics crash explanation/deliberation/idle gaps | Prediction normalized rows but other consumers bypassed it; shared locked validated copy now used | Four corrupt-history variants and 133 neighboring tests |
| Stop/reset races with feed | Only feed held lock; reset and activate now use same RLock | Barrier-controlled race test and no-dispatch-after-reset |
| Full pytest collection errors | Three legacy top-level sibling imports, then imported production `test_evidence` helper collected as test | Package fixture imports and helper alias; [collection failures](collection-failures.xml), [first full run](full-first-tests.xml), [final full run](full-tests.xml) |

Catalog fixture corrections: first order assertion assumed title-case names although production intentionally canonicalizes them; volume validation is in the executor, not parser; learned hook is `parse_learned`, not `parse`. Tests were corrected to assert the actual safety contract without weakening executor constraints. First attempts are preserved in catalog-first-tests.xml and private logs. These are test authoring mistakes, not claimed production fixes.

Native smoke failed before task execution: Windows `SetForegroundWindow` refused focus. [Native journey](native-journey.json) remains blocked, not passed. No OS security restriction was bypassed. Scoped source delta is [scoped-source.patch](scoped-source.patch), separate from the pre-existing dirty cognition upgrade.
