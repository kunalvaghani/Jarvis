# Blender integration audit — 2026-10-21 IST

Candidate branch: `codex/blender-integration`, based on main `32011da` (Spotify PR #9 merged). **Not activated, merged, pushed or certified for full automation.** Active `.jarvis/mcp.json` is unchanged. [Setup/rollback](../../../docs/blender-connector.md) · [203-name inventory](../../../integrations/jarvis-connectors/connectors/apps/blender/COMMANDS.md) · [Machine-readable coverage](command-coverage.json).

## Results and their limits

| Check | Result | Evidence |
|---|---|---|
| Unchanged Jarvis baseline | 1,810 passed; 431.091 s | [Log](baseline-unittest.log) |
| Integrated full unittest | 1,827 passed; 399.887 s | [Log](after-unittest.log) |
| Full regression after persistent provider transport | 1,827 passed; 417.467 s | [Log](final-unittest.log) |
| Final source unittest, including memory/discovery fixes | **1,831 passed; 415.539 s** | [Log](final-source-unittest.log) |
| Final whole-project pytest | **3,747 passed, 150 existing gated skips, 1 warning; 1,195.15 s** | [Log](full-pytest.log) |
| All initially failed areas rerun | 77 passed, 1 existing blocked skip; 41.90 s | [Log](failure-rerun.log) |
| Existing Blender API/live launcher regression | 3 passed; 9.80 s | [Log](legacy-blender-regression.log) |
| Final focused safety/provider/MCP/skill regression checkpoint | 114 passed; 41.99 s, including 21 Blender tests and later receipt/path/publication/skill deltas | [Log](final-targeted.log) |
| Adapted supplied package | 68 passed; 10.560 s | [Log](adapted-package-tests.log) |
| Original supplied package | 68 run, one Windows-path error | [Original log](upstream-baseline.log) |
| Original supplied live smoke | Crashed at first cube due to helper `name` collision | [Original log](upstream-live-baseline.log) |
| Repaired live PowerShell smoke | 44 action checks and 5 output/material effects passed | [JSON](live-smoke.json), [log](live-smoke.log) |
| Real MCP client discovery | Exactly 203 tools; builtin protocol 2025-11-25 | [Client receipt](client-smoke.json), [schemas](catalog-wire.json) |
| Blender action audit | All 200 invoked; 198 completed, 2 explicit safe failures | [Detailed JSON](live-action-audit.json), [log](live-action-audit.log) |
| Independent action effect assertions | 104 VERIFIED IN BLENDER; 96 UNTESTED for complete acceptance, including the 2 disabled actions | [Detailed JSON](live-action-audit.json) |
| Bridge helpers | All 3 VERIFIED IN BLENDER via actual scoped host/stdio jobs; wait helper completed | [Host E2E](live-host-e2e.json) |
| Node type compatibility | All 89 allowlisted shader/geometry/compositor node types instantiated through the adapted version aliases | [Detailed JSON](live-action-audit.json) |
| Export/project validation | OBJ/FBX/glTF/STL reopened and mesh vertices checked; `.blend` reopened with Subject mesh | [Effects](live-action-audit.json) |
| Tiny Cycles output validation | CPU and RTX 3050 OptiX rendered 64×64 PNGs; reopened size and nonzero RGB checked | [JSON](cycles-render.json), [log](cycles-render.log) |
| Launcher readiness | `repair_required`: Docker and Ollama unavailable | [Receipt](launcher-check.json) |

No existing Jarvis test was removed or skipped. The supplied snapshot is retained unchanged under `upstream/`; adapted copies preserve its 68 test cases while updating Windows fixture paths, scope request fields and the actual parent/tool shape. Original baseline failures are retained. The original full-suite checkpoints predate the final skill guide and safety deltas. A later checkpoint passed 1,831 unittest cases in 427.473 s. Final frozen-source runs passed 1,831 unittest and 3,747 pytest cases, including shared Blender executable discovery. The final pytest run has no failures; 150 existing prerequisite/acceptance-gated cases remain skipped, and one previously skipped Blender live test now runs. Three fixed-count assertions from a run collected before guide addition are preserved in the pre-skill log. The guide census retains its original count and adds an explicitly dated current snapshot. Unit/transport fixtures use simulated operations and approvals and are not bpy correctness evidence.

“UNTESTED” in the per-action acceptance matrix includes 94 actions that **did execute successfully in Blender** but lack the same depth of independent effect assertions. Successful return values alone were deliberately not promoted to full verification. All assertions use disposable factory scenes and locally generated assets; no user projects were opened. The two deliberate failures are animation rendering and resource unpacking, whose multi-file writes are not sufficiently constrained. Existing output overwrites are also refused. Open/revert project is not advertised. No specialist sculpt/VSE/retargeting feature was invented.

## Engine, live output and performance

Engine: **Blender 5.2.2 LTS**, hash **d13f752e3b9c**, build 2026-09-15; [installation receipt](installed-blender.json). No Blender 4.5 engine was tested. The version-migration changes were checked against official documentation using Firecrawl: [Python API changes](https://developer.blender.org/docs/release_notes/5.0/python_api/), [compositor migration](https://developer.blender.org/docs/release_notes/5.0/migration/compositor_migration/), [release notes](https://developer.blender.org/docs/release_notes/). Documentation research is distinct from executed checks.

Actual disposable Blender previews, not UI screenshots or upstream reference images:

![CPU Cycles factory-scene PNG, 64 by 64](cpu-preview.png)
![OptiX Cycles factory-scene PNG, 64 by 64](gpu-preview.png)

CPU render: 313 ms; OptiX render: 1,947 ms. These tiny single-sample measurements include cold backend costs; they do not imply GPU rendering is slower for production workloads. PNGs were independently reopened; Blender-only GPU allocator peaks were unavailable; the separately sampled device aggregates are reported below.

The real host benchmark parsed **120 synthetic natural-language requests**, used actual ToolRegistry/MCP/Blender execution and independent object readbacks, and read medium/large grid geometry (15,876 and 251,001 vertices). Approvals were synthetic test callbacks inside a temporary host configuration; no end-user approval UI or microphone was exercised. The final run also used all three bridge helpers. The original short-lived run was preserved before optimizing the existing persistent transport:

| Host transport | Parse p50/p95/p99 | Completion p50/p95/p99 |
|---|---|---|
| New child per call | 0.230 / 0.349 / 0.439 ms | 1,411 / 1,822 / 1,946 ms |
| Persistent child, final | 0.235 / 0.422 / 0.479 ms | 155 / 327 / 346 ms |

Exact final parsing/dispatch/completion distributions: [final real host benchmark](live-host-e2e.json). Comparison: [short-lived run](live-host-short-lived.json), [first persistent run](live-host-persistent-initial.json). Observed final peak Blender RSS: **420,626,432 bytes (~401 MiB)**. Peak process CPU sample: **917.4%** in psutil's per-core convention (~9.2 logical cores), not 917% of total machine capacity. Tests ran amid other local verification work; these are observations for these fixtures, not performance guarantees. A separate [11-sample NVIDIA probe](gpu-resources.json) observed whole-device GPU utilization up to 1% and device memory up to 498 MiB versus a 405 MiB baseline during a tiny render. These are device aggregates that include desktop workloads and can miss transients; Blender-only GPU memory was unavailable, never assumed zero. Physical voice latency, island frame responsiveness and arbitrary production scene cost remain unmeasured.

## Compatibility repairs and safeguards

- Real centralized BaseConnector composition and typed signatures; upstream example manifest is not used.
- Blender-only bounded 203-tool catalog admission; three default candidate schemas, at most six within 9,000 characters; all exact names remain callable.
- Final-only deterministic explicit commands, existing offline planner path for ambiguous Blender goals, existing policy and approvals.
- Fresh scope/project approval, private per-child proof, fixed loopback origin, no proxy/redirect, recursive finite JSON checks, scope pinning and exclusive atomic scope publication.
- Separate existing persistent owner for Spotify and Blender; crash/backoff repair never replays an action or restarts Blender. Receipt observers stop when idle/on Quit, retain interrupted references across restart and only observe explicitly accepted jobs.
- Versioned node aliases, valid compositor Image interface/output and edit-bone name lifetime repair; existing layered action channelbag path exercised.
- Root-contained resources and file paths, extension checks, overwrite refusal, bounded queues/workers and explicit context/version failures. File/scene metadata remains untrusted and cannot authorize code or install add-ons.

## Unfinished acceptance and activation

**Automatic approval review rejected enabling the persistent trusted write-capable sidecar before acceptance.** The active MCP config is unchanged; enabling requires explicit user approval. This report and the prepared registration helper make that decision reviewable.

Remaining gates: 96 action acceptance classifications, Blender 4.5 compatibility, real Blender crash/restart project recovery (MCP child crash/no-replay is fixture-tested), simultaneously competing real agents, physical STT/voice and overlapping media, actual local ambiguous Qwen planning, end-user approval UI/Dynamic Island responsiveness, general undo/backup semantics, symlink/junction races under hostile filesystem mutation and measured GPU peaks. Root containment was fixture-tested, including a [real Windows junction escape](junction-containment.json) that was blocked; this is not a universal race-proof filesystem sandbox. Docker/Ollama block full launcher readiness. No packages, models, drivers, third-party add-ons or paid APIs were installed or required.

The [initial broader pytest run](full-pytest-before-discovery-census-fixes.log) (3,740 pass / 5 fail / 151 existing skips) exposed old guide-count/census expectations and a hardcoded Blender executable path. The original log is retained; targeted fixes pass 77 cases with 1 existing skip, and existing legacy Blender live regression passes all 3 checks. The final complete pytest rerun is green (3,747 pass / 150 existing skips); the guide count increased legitimately from ten to eleven, and the historical census was preserved with a dated current snapshot. A root-directory diagnostic collected compatibility-junction aliases and is marked invalid; canonical test runs execute from `app/`.

Next action: review the candidate and source patch, approve activation, select dedicated folders/instance scope, and complete remaining live acceptance using disposable scenes. [Rollback instructions](../../../docs/blender-connector.md#rollback) preserve other providers and never kill a user-owned Blender.

## Review artifacts

[Source patch](source.patch) · [Changed file tree](changed-files.txt) · [Candidate file hashes](candidate-sha256.json) · [Supplied source hashes](supplied-source-sha256.json) · [Active configuration preservation](activation-state.json). The patch contains the integration source/documentation; test logs and generated evidence are separate artifacts. Raw and LF-normalized hashes distinguish Windows newline conversion from source changes.
