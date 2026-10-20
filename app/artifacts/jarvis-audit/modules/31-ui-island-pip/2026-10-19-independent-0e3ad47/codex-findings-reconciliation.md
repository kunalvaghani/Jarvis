# Prompt 31 independent audit — 2026-10-19 IST

| Finding | Current conclusion | Exact repair/evidence |
|---|---|---|
| P31-001 | FIXED callback boundary | 1dd3e9c; unchanged original four tests and repair regressions |
| P31-002 | FIXED same-text receipt replay boundary | 0e3ad47; independent adapted replay plus forged/TTL/fresh-user cases |
| D-P31-F1 | bundled evaluator rule reviewed | 0e3ad47; Phase 6 deterministic/non-timing rejection tests; evaluator seal changed |
| IR-001 | narrow snapshot privacy fix retained | fresh independent private/unknown-field tests |
| IR-002 | narrow training-admission fix retained | fresh independent lease/admission tests |
| IR-003 | retained; no dedicated new recipe suite in this run | previous fixed-source evidence |
| IR-004 | source retained, no new dedicated deep-path acceptance | previous lab evidence; Phase 6 regression scope only |

No entire-system certificate. Source fix by Codex: none. Prior artifact hashes and source SHA preserve lineage. The first twelve old catalog IDs are joined; targeted 013–022 changed semantics in the revised prompt and inherit no old status.
