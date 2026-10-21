# Jarvis Blender Connector — validation report

**Build date:** 2026-10-21  
**Target Blender:** 5.2 LTS (5.2.2 is the current 5.2 LTS patch verified from Blender Foundation release information at build time).  
**MCP tool inventory:** 203 independently named tools = 200 Blender actions + 3 bridge utilities.  
**Source lineage:** Based on user-supplied YouTube/Spotify `BaseConnector` pattern and starter standalone stdio MCP pattern.

## Validation performed in the build environment

| Category | Result | Meaning |
|---|---|---|
| Python source compilation | PASS | Main modules, generated MCP tools and test scripts compile under Python 3.13 |
| Unit-test methods | **68 PASS, 0 failures** | Includes approximately 200 action-by-action schema/dispatch checks as subtests |
| Catalog completeness | PASS | All 200 advertised actions have a backend dispatch path (12 import/export variants use generated format routing) |
| Generated tool signatures | PASS | All 203 names discovered via simulated MCP decorators; every action has explicit typed parameters |
| HTTP client/bridge end-to-end (simulated Blender) | PASS | Real loopback HTTP request/response, job queue, pump, error path, job status, disconnect |
| Authentication, localhost binding, queue limits | PASS | Wrong bearer token rejected, port binds 127.0.0.1, 32 waiting-job cap, job ID uniqueness |
| Approval policy | PASS | File/destructive actions are denied without a host callback, denied on reject, permitted with explicit callback |
| Input / filesystem protection | PASS | Unknown command, extra parameters, invalid numerics and paths outside allowed roots rejected |
| Result honesty | PASS | Poll distinguishes queued/running/done/error; timeout does not retry; partial batches return partial |
| Real Blender 5.2 `bpy` execution | **NOT EXECUTED HERE** | Blender executable unavailable in this environment. Supplied Windows Blender integration runner must be executed. |
| Real MCP SDK stdio roundtrip | **NOT EXECUTED HERE** | `mcp` SDK could not be installed from isolated build environment; provided `client_smoke.py` runs it on Windows |
| Integration into user's installed Jarvis repo | **NOT EXECUTED HERE** | Complete Jarvis repository not supplied; integration prompt and illustrative manifest provided |

## Source coverage (offline tests only)

- Blender bridge (`bridge.py`): approximately **98%** statement coverage.
- Jarvis MCP child/client (`connector.py`): approximately **96%** statement coverage.
- Command catalog/validation (`catalog.py`): approximately **99%** statement coverage.
- Blender operation dispatcher (`operations.py`): approximately **24%** offline statement coverage. The remaining bpy-dependent paths require a real Blender runtime. **Do not confuse 200 catalog entries with 200 live-verified Blender commands.**

These are not correctness guarantees. Some effects of `bpy.ops` depend on Blender version, selection, context, enabled add-ons, graphics configuration and scene content. The included `tests/run_inside_blender.py` makes a disposable scene and checks more than 40 real operations including mesh, materials, geometry nodes, compositor, animation, rendering, OBJ/GLB export, OBJ import and .blend save. It writes `blender_live_test_results.json` with individual pass/fail diagnostics.

## Checks to run on your PC

```powershell
.\install_windows.ps1
.\run_live_tests.ps1 -BlenderExe 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
```

Then integrate using `CODEX_INTEGRATION_PROMPT.md` and rerun Jarvis's own YouTube, Spotify, MCP, Windows automation, scheduler, and regression suites.

## Security and product boundaries

No unrestricted script executor or unsafe `open_project`/`revert_project` over the live bridge is exposed. Those two operations can invalidate the bridge session; use the explicit launcher to load a .blend file. No cloud API or paid token usage is needed. Destructive/file actions require human authorization integrated into Jarvis, and file access is limited to approved roots.

**Overall status: packaged developer integration build, offline test PASS; pending real Blender/MCP/runtime validation.**
