# Reproduction and diagnosis — 2026-10-15 IST

Original baseline **6 PASS, 8 FAIL in 4.51 seconds**, [XML](baseline.xml). Five implementation failures: latest spreadsheet matched app open; sound-down-notch and pause-current phrases rejected; separator comma contaminated Notepad target; corrected tab-close phrase rejected. Three fixture errors (desktop mocks and volume signature) were corrected separately, without credit as product fixes. A later compound expectation now accepts established compose/verbatim policy while checking order/content/target.

Completion adds an actual Actions→Brain ambiguity assertion for latest spreadsheet: paused checkpoint plus pending filename/path question, zero model/file opening. The initial stale-choice completion fixture called _clarify rather than actual _resolve_reply; corrected fixture checks the production reply boundary. Parser type/size/depth limits, concurrency, negation, learned shadow attempts, Stop, uncertainty and stale choices now pass. Original raw 03 CSV was overwritten before archival; preserved current samples are a new measurement, not reconstructed history.

Final executed assertions: [module XML](cases-and-contracts.xml), [full regression](../../completion-full-regression.xml). Historical intermediate failures are retained and not counted as final unresolved implementation failures.
