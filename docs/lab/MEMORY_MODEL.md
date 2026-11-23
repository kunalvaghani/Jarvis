# Current memory and proposed Lab attachment

2026-11-04 IST. Static schema/API audit; **no migration or private-memory population performed**.

| Existing owner | Data and source of truth | Read / write interface | Lab attachment and limitation |
|---|---|---|---|
| ObsidianMemory (`app/jarvis/obsidian_memory.py`) | Configured vault, Jarvis Index.json, activity notes; configured enable switch | `_index`, `task_context`, `program_matches`, `project_matches`, `recall`; `record`; `ensure_index` starts indexing work | Reuse vault/project/source context and facade entry point; do not run index/background workers in audit |
| MemoryCurator | Jarvis Memory.json canonical; readable Markdown projection; conversation summaries; categories person/preference/plan/goal/project/routine/fact | `add`, `relevant`, `context`, `observe`, `extract`, `summarise`, `save` | User-fact semantics must remain separate from literature and simulation; do not stuff Claim/Experiment into personal fact text |
| ConversationMemory | SQLite sessions and turns | `start_session`, `begin`, `finish`, `turns`, `matches` | Conversation history is not the scientific evidence graph |
| SkillMemory / SkillStore | Jarvis Procedures.json version 1; SQLite skill_records/events/versions/failures; stable skill identity, trust and lineage | `refresh`, `context`, `record`, `proposal`, living metrics; unique event keys prevent duplicate learning | Reuse procedure loading and success/failure history; trust (`provisional/trusted/demoted`) is not Lab scientific verification |
| ExperienceMemory | Existing task experience records and source conditions | Used by SkillMemory and task finish hooks | Reuse evidence context; inspect format before migration |
| ReasoningBank | Existing SQLite `items`, `relations`, `trajectories`, `compactions`; content hashes, evidence_json, conditions_json, source, embeddings | `learn`, `retrieve`, `feedback`, `compact`, `items`, `relations`; `_add` / `_relate` are internal | Best existing candidate for additive typed scientific records and explicit public API; no new Lab database; schema and retrieval compatibility must be proven first |
| Optional OpenViking | Optional index of existing vault | LearningMemory attaches `vault_hits`; disabled/unavailable fallback | Retrieval index, not a replacement authoritative graph |
| Neural Journal | Existing graph_versions, proposals, goals, signals, outbox, artifacts, shadow_routes, route_stats | `Registry(journal)`, dispatcher state, artifacts, outcome statistics | Execution authority and immutable traces; connect via IDs to scientific memory, not duplicated scientific facts |

`memory_v2.facade/ingest/context_pack` and resolver flags are declared but **off**. Declaration is not implementation. No general `unified_memory.add_node(kind, ...)` or Lab-ready fuzzy Component resolver was established from inspected source. Existing program/project name matching is not automatically valid for engineering part identities.

## Recommended additive design after Gate A

Keep existing stores and introduce a **facade, not a new store** in new `app/jarvis/discovery/memory.py`. Extend the existing ReasoningBank database with reversible, versioned scientific-node/edge tables or a reviewed kind-aware extension of its records, using the owner's connection/transaction policy. Choose one representation after a scratch-copy migration test; do not write both. If a public transaction/migration API is needed, minimally extend `reasoning_bank.py` and log it in MODIFICATIONS before changing it.

The facade joins references to existing source/project/procedure/neural-artifact IDs. Scientific source text must never be fed into the user's personal-fact extractor. Retention and compaction of scientific runs require explicit policy; the existing `compact(older_than_days=180)` is not permission to discard reproducibility artifacts.

Required master-prompt node kinds: Claim, Source, Hypothesis, Component, Parameter, Scenario, Experiment, RunArtifact, Capability, Tool, Skill, LearningEpisode. Spec §13.3 also calls for outcomes, uncertainty and artifact versions: keep them typed in these record contracts or propose explicit node kinds; do not silently lose them. Required relation kinds: derived_from, supports, contradicts, assumes, requires, affects, simulated_by, tested_in, supersedes, implemented_by, learned_in, uses_tool. Brain synapse modes remain execution modes; do not conflate them with scientific relations.

Aliases require stable target IDs, project/variant scope, normalized spelling, ambiguity rejection, original query/source and explicit fuzzy confidence. Reuse existing matching only where its tests prove these semantics; add a scoped resolver in a new file otherwise. Example `FW` must not silently resolve to a different model year's wing. Unknown values stay null; real measurements, solver outputs, cited claims and user preferences have separate provenance.

Memory population is **not run**: zero new Capability, Tool, Skill, Source or LearningEpisode records. First validate schema upgrades, rollback on isolated copies, secret rejection, deduplication and category-safe retrieval. Gate A must resolve the single-memory ownership conflict before migration into any live database.
