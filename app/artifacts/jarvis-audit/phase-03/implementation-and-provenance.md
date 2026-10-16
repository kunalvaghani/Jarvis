# Phase 3 — Implementation notes, upstream provenance and license review

Date 2026-10-17 IST. Branch `claude`. Predecessor commits: Phase 1 `e847b00`, Phase 2 `16d9b4d`.

## Upstream sources actually inspected

| Source | Revision inspected | License | How it was used |
| --- | --- | --- | --- |
| [HKUDS/OpenSpace](https://github.com/HKUDS/OpenSpace) | `38277815ed44a53d757973c2bc4454c3b6426698` (2026-08-13) | MIT | **Design reference only; no code copied.** Adopted: the `.skill_id` sidecar format (`<name>__imp_<8 hex>`, `openspace/cloud/local_mapping.py`), the `EvolutionType` FIX/DERIVED/CAPTURED semantics and parent rules (`skill_engine/types.py`), the selected/applied/completed/fallback counters (`skill_engine/store.py` `total_*` columns), provisional → trusted lifecycle with separate `enabled` flag (README "Controlled Skill Evolution"), the CAPTURED contract requiring execution + separate validation refs (`skill_engine/capture_contract.py`), and validator rules (safe slug, forbidden high-risk front matter `allowed-tools`, `hooks`, `shell`, …; `skill_engine/evolution/validator.py`). OpenSpace ranks with a cloud embedding model (`text-embedding-3-small`); Jarvis does **not**, to keep skill data local. |
| [CharlesQ9/Alita](https://github.com/CharlesQ9/Alita) | `2a37fc0647dbcc15e4ae12a5d5fdb586c2116831` (2025-08-30) | none published | Repository contains only `README.md` and `Figures/` — **no source code**. `mcp_synthesis.py` is an original adapter inspired by the published architecture (paper arXiv 2505.20286: MCP brainstorming → script generation → environment execution → MCP packaging/reuse). No Alita module is claimed or imitated. |
| [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) | tag `v2.3.0` (`2118f14f`), PyPI `mcp==2.3.0` | MIT | Installed **only inside** the container image `jarvis-mcp-runtime:1`; generated servers use `mcp.server.mcpserver.MCPServer` (v2 replaced `FastMCP`). SDK 2.3.0 lists `2025-11-25` among `HANDSHAKE_PROTOCOL_VERSIONS` (`src/mcp-types/mcp_types/version.py`), so the existing `mcp_bridge` exact-version check is kept unchanged. Host Python 3.10 environments are not modified (SDK v2 needs ≥ 3.11). |

Package list of the built image: [mcp-runtime-image.json](mcp-runtime-image.json) (29 packages, image
`sha256:0438d6be…`). Built from the already reviewed `jarvis-repository-runtime:1` (Python 3.13.16).

## Architecture (extends, does not replace)

```mermaid
flowchart LR
    Roots[skills/ · custom-skills/ · vault Personal · Evolved] --> SM[SkillMemory.refresh]
    SM --> Store[(skill_store.sqlite3<br/>records · events · versions · failures)]
    SM -->|context(goal)| Rank[skill_score relevance × living_score evidence]
    Rank --> Brain[BrainClient skill_context]
    Rank -->|selected per running task| Store
    TS[TaskState.on_finish] --> Finish[finish_outcomes: applied / completed_verified / fallback / failed]
    Finish --> Store
    Store --> Trust[update_trust: deterministic per active version]
    Idle[SelfEvolution idle loop] --> Maint[skill_maintenance: trust + FIX candidates + island card]
    Evo[SkillEvolution CAPTURED / FIX / DERIVED] -->|validate_skill + verify_execution via ToolRegistry| Evolved[.jarvis-runtime/skills/evolved]
    Gap[capability gap] --> Syn[mcp_synthesis] -->|discover → spec → template → AST screen → Docker tests → approval| Reg[(generated registry.json)]
    Reg --> Bridge[mcp_bridge.configurations] --> TR[ToolRegistry mcp_call + per-call approval]
```

### Files

| File | Role |
| --- | --- |
| `jarvis/skill_store.py` (new) | SQLite authority: `skill_records` (OpenSpace-compatible names + `trust_state`, `enabled`, lineage, `compatibility_json`, `source_task_id`, `epoch_event_id`), `skill_events` (UNIQUE `event_key` = sha256(task, skill, event)), `skill_versions`, `skill_failures`; `.skill_id` sidecars for Jarvis-owned roots only; damaged DB preserved and replaced. |
| `jarvis/skill_evolution.py` (new) | `living_score`, `finish_outcomes`, deterministic `update_trust`, `degraded`, `validate_skill`, `verify_execution`, `SkillEvolution.capture/fix/derive/rollback`. |
| `jarvis/mcp_synthesis.py` (new) | Discovery, spec validation, fixed-template generation, AST screen, container config, real MCP tests, approval-gated registration, health, unregister/restore, reaping. |
| `jarvis/skill_memory.py` | Evolved root, identity registration, `skill_warnings`, disabled filtering, living ranking, `selected` events, finish telemetry inside `record`. |
| `jarvis/mcp_bridge.py` | Merges approved generated servers; argument bound 30 → 64; MCP-spec stdio shutdown (close input → bounded grace → terminate/kill); reaps labelled generated containers after calls. |
| `jarvis/self_evolution.py` | `skill_maintenance` in the idle loop (every 10 min when idle and resources allow). |
| `jarvis/task_state.py`, `jarvis/actions.py` | `running_identity()` and its wiring as the telemetry task provider. |
| `scripts/setup/setup_mcp_runtime.py` (new) | Builds `jarvis-mcp-runtime:1`. |
| `skills/*/.skill_id` (10 new files) | Stable identities for bundled skills (OpenSpace convention). |

### Telemetry semantics

* `selected`: a skill body was put into planner context while a task was running (`running_identity`).
* `applied`: the finished task used at least one tool the skill binds (`tools:` metadata). Skills without tool bindings
  **cannot be attributed** and receive no outcome events (limitation; OpenSpace uses an LLM judgment instead).
* `completed_verified`: applied, task `completed`, `goal_verified` checkpoint evidence present and no recorded failures.
* `fallback`: selected but bound tools unused, or the task completed only after recovery.
* `failed` (+ cause): applied and the task did not complete; causes from deterministic text classification.
* Every event is unique per (task, skill, event): repeated finish hooks, retries and crash recovery cannot double-count
  (tested by recording the same finished task three times).

### Trust lifecycle (deterministic in evidence since the active version)

* Imported guides (bundled/custom/personal): `trusted`, or `provisional` when their two latest attributable outcomes failed.
* Evolved guides: start `provisional`; `trusted` after `completed_verified` in **two tasks other than the source task**
  with the latest outcome verified; `demoted` when the latest outcome is an attributable failure. A FIX or rollback opens a
  new evidence epoch. Permission denials, cancellations, unavailable tools and timeouts are not attributable.
* `enabled` is independent of trust; disabled guides are never selected.
* Trust affects ranking only; it never grants approval, binds tools or bypasses ToolRegistry checks.
