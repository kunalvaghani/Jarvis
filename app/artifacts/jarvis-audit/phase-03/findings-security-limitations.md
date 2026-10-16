# Phase 3 — Pre-existing problems, defects found, security model and remaining blockers

## Step 1 scan of existing skill roots (before changes)

Raw scan: [skill-root-scan-before.json](skill-root-scan-before.json).

| Root | Skills | Finding | Disposition |
| --- | --- | --- | --- |
| `skills/` (bundled) | 10 loadable + `repository-assimilation/` | `repository-assimilation/` is an **empty, untracked local folder** (no `SKILL.md`; Git does not track empty folders). | Not deleted (local user state; deletion needs approval). Now reported as `SkillMemory.skill_warnings`, separate from guide errors so tests stay machine-independent. |
| `custom-skills/` | 0 | — | — |
| Vault `Jarvis Skills/Builtins` | 10 mirrors | Jarvis-owned copies written by `sync`; not loaded as separate skills, so no live duplicates. | No change |
| Vault `Learned` | 18 procedures | Valid metadata. | No change |
| Vault `Hermes` | 2 folders | `optional-skills/`, `skills/` are structural mirror folders, not skills. | No change |
| Vault `Personal` | 0 | — | — |
| DeerFlow public guides | 23 | 10 exceed the 8 KB bundled-guide limit. | Observation only: they are read by `deerflow_skill_read` with its own budget, not by `SkillMemory`. |
| Duplicate names across live roots | none | Existing loader already refuses duplicates (kept, tested). | — |
| Unknown tool bindings | none | — | — |

Pre-upgrade skill-related suites: **374 passed / 5 skipped** ([log](pre-upgrade-relevant.log)).

## Defects found and fixed during Phase 3

| ID | Defect | Root cause | Fix | Proof |
| --- | --- | --- | --- | --- |
| G1 | Living telemetry silently disabled on first use (`living_error` = "cannot commit - no transaction is active"). | `executescript` commits implicitly inside the explicit transaction. | Schema setup on its own plain connection; tests assert `living_error is None`. | P03_identity test |
| G2 | An invalid `.skill_id` file caused a new identity on every load. | Sidecar creation fell through to generation when the file existed but was invalid. | Invalid sidecars are preserved; SQLite mapping keeps identity stable. | P03_invalid_sidecar |
| G3 | Trust oscillated (trusted → provisional → demoted) on repeated maintenance runs without new evidence. | Incremental transitions from the current state. | Trust is a deterministic function of evidence since the active version (`epoch_event_id`). | P03_idle_maintenance (third run reports nothing) |
| G4 | After a real `mcp_call`, the generated server's container kept running until its lifetime fence. | `StdioClient.close()` terminated the Docker client before closing stdin; killing `docker run -i` does not stop the container. | MCP-spec stdio shutdown: close input (helper thread) → 1.5 s grace → terminate → kill; labelled generated containers are reaped after each bridge call. Existing 4 s bounded-shutdown test still passes. | P03_mcp_workflows asserts 0 leftover containers; `test_agent_runtime` |
| G5 | Hardened `docker run` argument list rejected by `mcp_bridge` (37 > 30 args). | Size bound. | Bound raised to 64; trusted/enabled/absolute-executable/exact-allowlist checks unchanged. | P03_mcp_workflows |
| G6 | Uncached ranked `context()` p50 rose to 45.8 ms (one transaction per skill). | Per-skill metric queries. | One grouped read (`all_metrics`), cached 5 s: 6.9 ms (quick check) / 18.2 ms (benchmark store with 200 extra events). Pre-Phase-3 `context()` was ~3 ms. | [before](living-benchmark-before-metrics-optimization.json) / [after](living-benchmark.json) |

## Security model (tested)

| Control | Where | Test |
| --- | --- | --- |
| Generated MCP code limited to allowlisted stdlib mechanism modules; AST blocks `os`/`subprocess`/`socket` imports, `open`, `eval`, `exec`, `__import__`, `getattr`/`setattr`, dunder access, `global`, classes, async, nested functions | `mcp_synthesis.screen` | P03_malicious_generated_code (6 cases), P03_spec_must_use_allowlisted_mechanism |
| Container: `--network none`, `--read-only`, `--cap-drop ALL`, `no-new-privileges`, user `65534:65534`, 32 PIDs, 256 MB, 0.5 CPU, `noexec` tmpfs, proxies cleared, `/usr/bin/timeout` lifetime fence, only `server.py` mounted read-only | `server_config` | P03_generated_server_container_has_no_network_or_host_files (real socket attempt → `no-network`, write → `read-only`) |
| Generated code cannot change approvals: registry/approval files live on the host; container sees only its own source | design + mount list | container probe |
| Registration requires runtime approval; every later `mcp_call` still requires approval and exact allowlist | `synthesize`, `mcp_bridge.execute` | P03_mcp_workflows (`mcp_register`, `mcp_call` approvals observed) |
| Wrong or hanging tools are never registered; tampering after approval → unhealthy → unregistered (previous approved version restored when one exists) | `run_tests`, `health`, `unregister` | P03_wrong_or_hanging, P03_mcp_workflows |
| Existing tools are discovered before generation | `discover_existing` | P03_mcp_existing_tool |
| Skill candidates: forbidden front matter, unregistered tool bindings, approval-waiving text, credentials and unsafe names rejected | `validate_skill` | P03_malicious_or_invalid_candidates (5 cases) |
| New skills are provisional; trust only from independent verified use; LLM text never establishes success | `verify_execution`, `update_trust` | P03_captured, P03_provisional_becomes_trusted |
| FIX cannot bind new tools, must be minimal, must pass real validation; Builtins/Obsidian guides only get proposals | `SkillEvolution.fix` | P03_fix_* (3 tests) |
| Evolution modes `audit_only` / `fix_only` / `autonomous` (OpenSpace semantics) | `SkillEvolution._allowed` | P03_audit_only |

A virtual environment is not treated as a sandbox anywhere in Phase 3; untrusted generated code runs only in Docker.

## Remaining limitations and blockers (not claimed as done)

| ID | Limitation | Status |
| --- | --- | --- |
| L1 | Mutation drafting by the local model is **not wired**: `SkillEvolution` and `synthesize` take an `author` callable; tests use fixed fixture authors (labelled MOCK). Their output is still validated and executed for real, but no live Qwen-authored skill or MCP spec was produced in this phase. | NOT RUN (live model) |
| L2 | Automatic end-to-end mutation from live tasks is not scheduled: idle maintenance updates trust and records FIX candidates, but validation fixtures for arbitrary tasks are not synthesized automatically, so FIX/CAPTURED/DERIVED run via the API with explicit validation steps. | Partial by design |
| L3 | "Semantic relevance" is lexical (token overlap with inflection handling) plus measured reliability; no local embedding model is installed, so no neural semantic ranking is claimed. | Open |
| L4 | Outcome attribution needs `tools:` bindings; guides without them get `selected` only. | Open |
| L5 | `verify_execution` only auto-validates fixture-safe adapters (documents, Blender, reads); desktop/browser/account workflows need human review. | By design |
| L6 | FIX for bundled/Obsidian/Hermes guides produces proposals only; no automatic rewrite of user or repository guides. | By design |
| L7 | Generated MCP tools are limited to stdlib-only computation; adapters needing third-party packages or network APIs are refused. | By design |
| L8 | First call of a generated MCP tool includes container start (~2.3 s p50). | Measured |
