# Memory repeat continuation — 2026-10-20
Pinned Claude `e5af0e700517bac5fb48dcebc8f6cc9c9df9a369` in a detached checkout. Production source is unchanged across 560 hashes.
Actual path: ToolRegistry.office_xlsx → existing skills worker → failure → harness task record → LearningMemory.learn_from_task → ReasoningBank SQLite → LearningMemory.lessons → BrainClient.request/_request/_request_once JSON wire → recording fake planner → ToolRegistry → independent openpyxl worker readback.
Real local file and SQLite operations; fake worker transport deliberately ignores hints. Task completion/trajectory is supplied by this harness, not full Actions/Brain orchestration. No model, voice, native GUI or account claim.
Read app/AGENTS.md and revised Prompt 37. Earlier discovery/contract inventories remain in [prior packet](../2026-10-20-independent-e5af0e7/inventory.md).
