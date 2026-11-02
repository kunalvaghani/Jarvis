# Brain progress

Master architecture: [ARCHITECTURE.md](ARCHITECTURE.md). Standing rules: [/CLAUDE.md](../../../CLAUDE.md).

## Phase 0: audit and baseline (read-only)

- [x] Read ARCHITECTURE.md (2026-11-02)
- [x] Read-only survey of the repo; draft [ADAPTER_MAP.md](ADAPTER_MAP.md)
- [x] Conflicts between ARCHITECTURE.md and the repo listed for the user (2026-11-02)
- [x] User decisions on the conflicts (package name, libraries, UI, overlap with upgrade v2, scenario accounts)
- [x] Static inventory `inventory/*.yaml` generated from ToolSpec, `execution_strategy.METHODS` and MCP allowlists
- [x] Scenario suite (30+) with machine-checkable acceptance
- [x] Legacy baseline recorded (run 1 partial, 90 receipts; run 2 deferred by the user to after implementation) (success, p50/p95 end-to-end and first action, model calls, retries, RAM/VRAM, cold start, crash restart)
- [x] `JARVIS_BRAIN_MODE` flag (default off) and documented rollback
- [x] Phase 0 report `reports/phase-0.md`, then stop for approval

## Phases 1–5: implemented and unit-tested (2026-11-02, branch `brain/phase-1-registry`)

The user asked to implement the brain first and run all live testing afterwards, so each phase's live gate is still open. Report: [reports/phases-1-5.md](reports/phases-1-5.md).

### Phase 1: capability registry and graph
- [x] Typed contracts: `Neuron`, `Synapse`, `Signal` (pydantic), with stable `kind.name@vN` ids (`jarvis/neural/contracts.py`)
- [x] Live registry rebuilt from ToolSpec, METHODS, the MCP allowlist and core neurons; live `tools/list` merged only for allowlisted tools (`registry.py`)
- [x] Growth: `propose` / `approve`, journaled. Read-only composites activate; everything else waits for the user
- [x] Sparse wiring from explicit contracts on specific types only; never auto-wired into destructive or external writes (`graph.py`)
- [x] Versioned graph snapshots in the SQLite journal (`journal.py`); Obsidian projection (`projection.py`)
- [x] Hard eligibility (`policy.py`) and explained shadow ranking (`router.py`); shadow hook in `Actions.execute` and `ToolRegistry.execute`
- [ ] Live gate: shadow agreement on the live suite (`cases.py --brain shadow`, then `python -m jarvis.neural replay`)

### Phase 2: signal bus and vertical slices
- [x] Per-goal acyclic plans checked against the capability graph (`execution.py`)
- [x] Durable dispatcher: outbox before side effects, idempotency keys, crash resume, bounded repair, deadline, cancel (`dispatcher.py`)
- [x] Slices: research → analysis → grounded report; repo inspect → patch → test on a scratch copy → apply → re-test (`compiler.py`, `adapters.py`)
- [ ] Live gate: B07 bug fix and a research question with the brain on

### Phase 3: orchestration
- [x] Brain `on` mode in `Actions.execute`: known workflows run through the brain; everything else is the legacy planner, unchanged
- [x] Runs under the existing queue and scheduler (unchanged); one desktop lock across goals; parallel waves within a goal (at most 4)
- [x] Deterministic exact-file workflow verified by the sealed `text_file_saved` verifier
- [ ] Live gate: legacy parity on the regression suite with `--brain on`

### Phase 4: plasticity
- [x] Verified outcomes only (`learning.observe`); live-suite oracles feed the shadow log (`judge_latest`)
- [x] `neural.learning` off / shadow (default) / on; offline `replay`; consolidation into proposed neurons
- [ ] Live gate: held-out improvement before `neural.learning` is set to on

### Phase 5: live neuron view
- [x] Local read-only web view (`viewer.py`, `python -m jarvis.neural viewer`): every activation is a journaled signal, no payloads
- [x] Electron/React evaluated: not added (a second Chromium for no gain; the user's rule 1.3)
- [ ] Live gate: watch a real goal fire in the view
