# Prompt 37 - fresh committed-source verification; release NOT READY

2026-10-20. Audited `e5af0e700517bac5fb48dcebc8f6cc9c9df9a369` in a fresh isolated checkout. Earlier reviewed production repairs are now integrated at `3fbfbf68b6e5cd964191db2c3245efbc2f5a3772`. **Fresh full relevant regression: 1907 PASS / 0 FAIL / 139 SKIPPED.** Focused baseline: 104 PASS. New portable process/UI journey: 1 PASS, separate from the full selection; initial development run exercises the same case and is not another unique PASS.

**JRV-37-021 now PASS at the requested mock-send scope:** real child exits 27, restart reloads the uncertain checkpoint, queued resume reaches actual App/Island/Desk/Tk consumers, both text fields say Task paused, planner is not called, speech sink receives one message and outbox remains one row. No real sends, audio or private desktop capture.

26 revised cases: **1 bounded process/mock/UI PASS / 25 BLOCKED**. Other live/native/account/training/verifier/provenance/service gates remain unresolved. Isolated readiness: repair_required. No production changes, installs, downloads, merge or deployment. [Case record](tests.jsonl) · [UI readback](ui-restart-journal.json) · [Proposed test](new-test.patch) · [Handoff](../../../../../docs/CLAUDE_HANDOFF.md).
