# Prompt 31 independent continuation — 2026-10-19 IST

Pinned **ddf3247fd3d5ee6b151287c6cba358e8707090c6** (`claude`) in `codex-review`; source repair **1dd3e9c841fba8f439be0d1116e9a0c91da8c447**. Only fast-forwarded the audit branch. Original user config remains untouched. Prior README audit notes are preserved in previous-readme-notes.patch; previous packets remain unchanged. [Baseline/environment](baseline.json), [source hashes](source-hashes.json), [all executed rows](executed-tests.jsonl), [stable catalog join](catalog-join.jsonl).

Read the actual repair diff/record, Prompt 31, app/AGENTS.md, prior system/Phase 1–8 inventory and independent findings. Master contract remains unavailable; companion reconciliation reserves source repairs for Claude and Codex independent confirmation. No application source repair by Codex.

Pipeline: `Actions._approve` → `App.request_approval` → approval payload/`UIEventBuffer` → `IslandDesk.Approval` → widget or bound voice callback → shared answer/Event → requester. `Approval.token` is generated at card creation; `approval_digest` hashes kind + NUL + detail. UI decisions validate token. Both `App.request_approval` and `AbilityForge.ask` validate digest but never compare the token to a requester-owned expected ID. They also do not consume receipts in a requester-side one-use registry. That is the independently reproduced P31-002 gap.

Normal corrected UI callback behavior is verified independently. Forged-response tests model a response-seam replay; a remote attack path is not demonstrated. Remaining full identity/scope/expiry/Verify, physical secure-field/DPI/voice/UI crash and optional-worker acceptance requirements remain incomplete.
