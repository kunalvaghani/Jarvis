# Jarvis Blender Connector — 200 Blender actions + 3 MCP bridge tools

## What this is

A **local, open-source-compatible Blender automation bridge** built to match the supplied `BaseConnector` lifecycle (`info`, `connect`, `close`, `health`) and the standalone MCP connector pattern used by the prior YouTube and Spotify packages. It provides **203 named MCP tools**: **200 allowlisted Blender actions** and **3 bridge/job tools**. No cloud API, API key, token billing, LLM inference, or external service is needed for the Blender connector.

**Target:** Blender **5.2 LTS**, Windows 10/11, Python **3.12+** for the Jarvis MCP process. A subset should run on Blender 4.5 LTS; version differences are not all validated. Blender's internal Python executes `bpy` actions. The separate MCP subprocess uses only the standard library to communicate with Blender over `127.0.0.1`, and the `mcp` Python SDK to expose tools.

**Not a claim of total Blender feature parity:** Blender has a huge context-sensitive API. Sculpt strokes, all 5.2 physics nodes, motion matching, complex NLA retargeting, Grease Pencil drawing, detailed video editing, hair grooming, and arbitrary third-party add-on controls are **not** universally automated by this package. Extend the catalog/operations with explicit allowlisted functionality after verifying real Blender behavior. There is **no generic arbitrary Python execution tool** by design.

## Architecture

```text
Jarvis natural language intent + approvals
    -> ToolRegistry / MCPBridge (existing Jarvis code)
    -> server.py: 203 explicit blender_* MCP tools (stdio)
    -> BlenderConnector(BaseConnector) child (client validation + approval)
    -> 127.0.0.1:8769 authenticated JSON HTTP transport
    -> Blender main-thread timer queue (start_blender_bridge.py)
    -> BlenderOperations dispatch (allowlisted, parameter-validated bpy calls)
    -> Job ID -> status/error/result -> Jarvis follow-up / Dynamic Island
```

**Why the main-thread queue?** Most `bpy` operations must run on Blender's main thread, not in the HTTP worker threads. A short timer moves a bounded number of queued jobs to the main thread. Rendering and imports may block Blender's UI during execution; `blender_job_status` and `blender_wait_job` avoid incorrectly resubmitting work.

## Windows installation

1. Install Blender from the [official Blender 5.2 LTS page](https://www.blender.org/releases/5-2/). You need Blender installed locally. Do not pip-install the `bpy` package into your Jarvis MCP venv.
2. Extract `jarvis_blender_connector` wherever you keep Jarvis connectors. Open **PowerShell** in that folder.
3. Install the MCP-side dependencies and run the **offline** checks:

```powershell
.\install_windows.ps1
```

If you already installed dependencies and want only offline tests:

```powershell
.\install_windows.ps1 -SkipMCP
```

4. Start Blender with the included safe launcher. Supply your **actual Blender executable** and explicitly approved file directories:

```powershell
.\launch_blender.ps1 `
  -BlenderExe 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' `
  -AllowedRoots @('C:\Users\YOUR_USER\Documents\Blender', 'D:\3D_Projects')
```

Replace those sample directories with existing locations on your PC. **Do not set an unrestricted entire drive as an allowed root** unless you understand the risk. Set a dedicated project/export directory for safest operation.

Alternative: open Blender and use **Scripting → Text Editor → Open `start_blender_bridge.py` → Run Script**. If launched this way, `JARVIS_BLENDER_ALLOWED_ROOTS` must already exist in Blender's process environment; with no roots, file read/write operations fail closed. If the bridge is already running on port 8769, stop it first via `stop_blender_bridge.py`. Two Blender processes cannot use the same port concurrently.

The bridge writes a generated random authentication token to `~/.jarvis/blender-bridge.json`. The Jarvis MCP sidecar reads this file automatically. **Do not commit or share that file**; keep file permissions private. When the bridge is stopped cleanly, its matching token file is deleted.

5. Run the **real Blender integration tests**, not just the offline tests:

```powershell
.\run_live_tests.ps1 -BlenderExe 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
```

This creates a temporary test scene and renders/exports a 64×64 preview in a temporary directory. Results are written to `blender_live_test_results.json` in the connector folder. Investigate **any** failed test before enabling the tool in Jarvis.

6. Add the **actual** Jarvis `MCPBridge` entry following `connector_manifest.example.json` **as an illustration**. The correct registry schema must be verified against your real Jarvis codebase; this standalone ZIP does **not** modify Jarvis automatically. Startup should register `blender_*` tools and always use the existing Jarvis confirmation, security, scheduler, model-router, memory, telemetry, and error-recovery components.

## Command catalog

See [COMMANDS.md](COMMANDS.md) for **all 203 commands**, types, defaults, approval class and user-friendly examples. Categories: inspection, scene, mesh/modeling, modifiers/constraints, materials/shaders, geometry nodes and compositor, studio (camera/light/rig/text/curves), animation, render, projects/import/export, physics, and assets.

Common actions:

```text
"Jarvis, create a cube named TableTop at (0,0,1)."
    -> blender_add_cube(name='TableTop', location=[0,0,1])
"Add bevel width 0.05 to TableTop."
    -> blender_add_bevel(name='TableTop', width=0.05)
"Create a gold material, metallic 0.8 and roughness 0.25."
    -> blender_create_material(name='Gold', color=[0.8,0.55,0.1,1], metallic=0.8, roughness=0.25)
"Assign Gold to TableTop."
    -> blender_assign_material(name='TableTop', material='Gold')
"Create a geometry node group on TableTop."
    -> blender_create_geometry_nodes(name='TableTop', group_name='TableNodes')
"Animate the table from z=0 to z=2 over frames 1 through 48."
    -> blender_animate_transform(...,frame=1,location=[0,0,0]); blender_animate_transform(...,frame=48,location=[0,0,2])
"Render 1080p with Cycles, preview at 25%, and tell me when it finishes."
    -> blender_set_render_engine; blender_set_render_resolution; blender_render_preview; blender_job_status
"Save as D:\3D_Projects\Table.blend."
    -> REQUIRES Jarvis filesystem approval + allowed root
```

## Approval and access controls

- **No arbitrary Python**, no `bpy.ops` string execution, no shell, no remote Internet fetch, and no auto-downloading assets. Only names in `catalog.py` are accepted.
- The HTTP bridge binds exclusively to `127.0.0.1`, checks a random bearer token, has a bounded queue, size-limited requests, and 10-minute completed-job retention.
- **Destructive** (delete, purge, apply modifier, etc.) and **filesystem** (save, import, export, render-to-file) commands are **denied by the client** until Jarvis provides an `approval_callback` that checks an actual user confirmation. Do not make an always-true callback in production.
- File operations also require `JARVIS_BLENDER_ALLOWED_ROOTS`, resolved against symlinks to avoid directory traversal, and require the expected extension where applicable.
- **Batches:** at most 25 operations, only risk-class `write` actions, all schema-validated before execution. Blender cannot guarantee transactional rollback. On a mid-batch failure the result has `partial=true`, and Jarvis must inspect the state before further actions.
- **Long-running jobs:** timeouts never imply cancellation. Poll job IDs; do not blindly retry saves, renders or edits.
- **Automatic scripts in untrusted .blend files:** follow [Blender's scripting security guidance](https://docs.blender.org/manual/en/latest/advanced/scripting/security.html); Blender Python is not sandboxed. The connector intentionally does not expose live open/revert project because reloading the file can destroy the in-process bridge. Use your approved Blender launcher with an explicit project instead.
- Prevent exposing project files and private material paths to a cloud model without consent; all connector operations themselves are local.

## Troubleshooting

- `Blender bridge not configured`: start `start_blender_bridge.py` inside the Blender instance or from the included launcher, with the same Windows user as Jarvis.
- `PermissionError: JARVIS_BLENDER_ALLOWED_ROOTS`: relaunch Blender with `launch_blender.ps1 -AllowedRoots ...`. Restart required for changed environment variables.
- `Jarvis approval required`: wire the child connector into the existing Jarvis ToolRegistry permission layer; the standalone MCP server will **not** silently authorize destructive/file actions.
- `Bridge job remains running`: Blender UI may be blocked by rendering or simulation. Do **not** retry. Poll status and check output files after completion.
- `Operation failed: poll() / context`: Blender UI context differs. Use the built-in data API commands when available and run live tests on your installed Blender version.
- `Port in use`: another Blender bridge is already running. Run `stop_blender_bridge.py` from that Blender instance or start a different port using `-Port` and ensure the Jarvis MCP sidecar reads the matching config.
- `MCP SDK import`: use the isolated `venv-blender` and `pip install -r requirements.txt`; the server supports `MCPServer` (v2) or `FastMCP` (v1). The protocol smoke client uses v2 by default.

## Limitations and testing status

Offline tests exercise a **simulated bpy subset**, transport, 200-command schema, error cases, authorization and tool signatures. They do **not** prove every bpy call works in Blender. Live Blender and actual MCP package installation weren't available in the authoring environment; run the provided checks to verify actual integration before enabling Jarvis. See [TEST_REPORT.md](TEST_REPORT.md), [CODEX_INTEGRATION_PROMPT.md](CODEX_INTEGRATION_PROMPT.md) and [ARCHITECTURE.md](ARCHITECTURE.md).
