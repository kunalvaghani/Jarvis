# Brain progress

Master architecture: [ARCHITECTURE.md](ARCHITECTURE.md). Standing rules: [/CLAUDE.md](../../../CLAUDE.md).

## Phase 0: audit and baseline (read-only)

- [x] Read ARCHITECTURE.md (2026-11-02)
- [x] Read-only survey of the repo; draft [ADAPTER_MAP.md](ADAPTER_MAP.md)
- [x] Conflicts between ARCHITECTURE.md and the repo listed for the user (2026-11-02)
- [ ] User decisions on the conflicts (package name, libraries, UI, overlap with upgrade v2, scenario accounts)
- [ ] Static inventory `inventory/*.yaml` generated from ToolSpec, `execution_strategy.METHODS` and MCP allowlists
- [ ] Scenario suite (30+) with machine-checkable acceptance
- [ ] Legacy baseline recorded (success, p50/p95 end-to-end and first action, model calls, retries, RAM/VRAM, cold start, crash restart)
- [ ] `JARVIS_BRAIN_MODE` flag (default off) and documented rollback
- [ ] Phase 0 report `reports/phase-0.md`, then stop for approval
