# Prompt 31 audit — 2026-10-19 IST

Prior independent base: `36fbf3ce925080f7f54afa87eaf1d9b88414142d`; fix commit `32fdbfe`; evidence checkpoint `bc71fb7`; current pinned claude `5b56f84c1604de87bb8845027dffb5ce5943243b` includes the fixes through PR #6. Historical originals remain unchanged; every available prior artifact is hashed in prior-artifact-hashes.json.

| Actual prior ID | Current state | Fresh verification | Follow-up |
|---|---|---|---|
| IR-001 P1 snapshot privacy | FIXED at reviewed boundary | four synthetic privacy tests PASS | secure native field/live disclosure BLOCKED |
| IR-002 P1 training admission | FIXED at reviewed boundary | eight synthetic lease/admission tests PASS | GPU admission race/live contention remains unverified |
| IR-003 P1 CRLF recipe hash | FIXED source retained | windows_commands suite PASS | no current whole-runtime deployment trial |
| IR-004 P2 long Windows paths | UNVERIFIED runtime, source retained | historical lab-final.xml only; no fresh lab test | repeat deep-path disposable lab reproduction |

This is partial reconciliation, not a renewed whole-system certificate. The original eight failed installation-sensitive tests were not all rerun here. New P31-001 remains APPLIES/P1 and has no fix commit. See [new ledger](../../../reconciliation/findings-ledger.csv).
