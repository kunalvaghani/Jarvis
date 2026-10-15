# Reproduction and diagnosis — 2026-10-15 IST

Initial production-source baseline **5 PASS, 8 FAIL in 7.92 seconds**, [XML](baseline.xml). Failures: release combined a 16 kHz buffer with a 48 kHz final block (6400 versus3200 samples); five invalid-setting variants were accepted; raw capture exception payload was reported; decoder join was unbounded. These are repaired without replacing the recognizer or changing endpoint defaults.

Duplicate-job baseline **1 FAIL in 1.20 seconds**, [XML](duplicate-baseline.xml): repeated final utterance ID dispatched three commands instead of two explicit requests. A monotonic finalized-ID guard rejects the duplicate and preserves the new utterance ID. Stop drains pending buffers; stalled decoder remains owned so recovery cannot create a duplicate or cancel an unrelated active task.

Three acoustic assertions remain BLOCKED, not failed or silently omitted: JRV-04-001 quiet-room command/WER/latency; JRV-04-002 background-TV false activation; JRV-04-003 long-pause endpoint intent. No labeled corpora and only1396MiB observed free GPU headroom. Fake transcript/numeric/proper-noun checks prove cleanup policy, not actual recognition of arbitrary speech.

Final executed assertions: [module XML](cases-and-contracts.xml), [full regression](../../completion-full-regression.xml). Historical intermediate failures are retained and not counted as final unresolved implementation failures.
