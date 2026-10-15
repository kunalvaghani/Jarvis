# Reproduction and diagnosis — 2026-10-15 IST

Original baseline: **9 PASS, 7 FAIL in 6.09 seconds**, [XML](baseline.xml): stale screen attention, four invalid-option variants, missing error diagnostics and unexecuted proposals counted as success. Existing privacy-neighbor expectation was corrected to categorical disk-error reporting. Heap candidate P95 worsened 0.023488→0.027676 ms and was reverted, [candidate CSV](benchmarks-heap-candidate.csv).

Completion identity baseline: **2 FAIL in 1.40 seconds**, [XML](identity-baseline.xml). Wrong model task metadata was accepted and an older task finish could affect a replacement task. Task UUID checks, identity-bound cancellation and owned finish IDs repair these paths; matching regression assertions now pass. Busy Python parser, malformed deep history, fault/recovery and private tool traces are exercised by completion cases. This does not isolate native code that holds the GIL.

An earlier unscoped pytest collected vendored repositories (2335 collection errors); it is not a Jarvis pass. Final validation explicitly uses pytest tests. Original raw 02 CSV was overwritten before archival; prior report headline measurements remain historical, fresh current CSV is archived.

Final executed assertions: [module XML](cases-and-contracts.xml), [full regression](../../completion-full-regression.xml). Historical intermediate failures are retained and not counted as final unresolved implementation failures.
