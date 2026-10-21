# Blender child connector — 2026-10-21 IST

This candidate integrates the supplied package into Jarvis's existing architecture on `codex/blender-integration`, based on merged Spotify main `32011da`. It is not enabled, merged or pushed. Active YouTube/Spotify configuration is unchanged. [Evidence](../artifacts/jarvis-audit/blender-connector/README.md) · [203-command inventory](../integrations/jarvis-connectors/connectors/apps/blender/COMMANDS.md).

## Architecture and compatibility

The production [`BlenderConnector`](../integrations/jarvis-connectors/connectors/apps/blender/server.py) subclasses the existing centralized `jarvis_connector.BaseConnector`. The copied local service is composition only; its `base.py` contains error/info types, with no second production parent hierarchy. Lifecycle info/connect/close/health remains available. The supplied package is preserved under `upstream/` with hashes and original tests; its example manifest/server are reference material, not Jarvis configuration.

Typed static methods expose 200 catalog operations plus `blender_bridge_health`, `blender_job_status` and `blender_wait_job`. The existing MCP bridge accepts up to 256 entries only for the reviewed Blender approval binding; other servers retain the 100-entry limit. Discovery returns three detailed candidate schemas by default, at most six within 9,000 characters, with query/category ranking and exact-name access. This does not place all 203 schemas into a local model's prompt. Existing Qwen/offline planning remains the planner for ambiguous work. The bundled `blender-modeling` guide is selected through existing capability/SkillMemory routing and synchronized as untrusted capability guidance, never permission or stored executable actions. Routine explicit commands such as `create a cube named Table in Blender`, `list objects in Blender` and `show scene in Blender` route deterministically through ToolRegistry. Final speech is required. Multi-step plans must inspect state between edits; no model-generated Python endpoint exists.

The existing persistent MCP owner is reused with separate Spotify/Blender children and independent lifecycle state. Watchdog may repair an owned child or its read-only receipt observer, with bounded backoff. It never starts/restarts/kills Blender itself and never replays scene actions. Actions.close stops both Blender-owned workers. Blender timer execution stays on Blender's main thread; HTTP threads only validate/enqueue/read receipts. Render operations can still block Blender's own UI.

## Installation, discovery and explicit activation

Use Jarvis's existing Python environment. Builtin MCP and loopback transport need only the standard library; do not install a `bpy` wheel, download models or install another MCP package for this runtime. The benchmark uses the already declared `psutil`. The installed engine was discovered as `D:\blender.exe`, Blender 5.2.2 LTS, build `d13f752e3b9c`. No Blender 4.5 executable was tested.

The same read-only installation discovery is used by the existing API launcher and setup CLI, preserving valid configured executables and finding the installed fallback without rewriting user configuration. From `app/`, discover installations and run real stdio discovery:

```powershell
.venv\Scripts\python.exe scripts\setup\discover_blender.py
.venv\Scripts\python.exe integrations\jarvis-connectors\connectors\apps\blender\client_smoke.py
```

Choose existing dedicated project/output folders, an unused port and a unique private configuration file for **each Blender instance**. The launcher refuses an existing scope file. Start the reviewed bridge in a disposable scene first:

```powershell
& integrations\jarvis-connectors\connectors\apps\blender\launch_blender.ps1 `
  -BlenderExe 'D:\blender.exe' `
  -AllowedRoots @('D:\3D_Projects\JarvisTest') `
  -BridgeConfig 'D:\3D_Projects\JarvisTest\bridge-8769.json' -Port 8769
```

The example project directory must exist. Select project/output roots narrowly. Optional `-ProjectPath` chooses one existing `.blend`; auto-execution is disabled. Loading arbitrary/untrusted scenes or add-ons is not authorized by tool discovery. To attach to a bridge already started with this reviewed code, use its explicit configuration path and inspect the displayed scope/project. A second instance requires a different port **and** configuration path. The bridge refuses to overwrite another scope file and the client refuses mismatched scope IDs.

**Activation is pending user approval.** Automatic approval review rejected persistently enabling the write-capable registration before acceptance. After that approval, the following helper backs up `.jarvis/mcp.json` privately, preserves all other entries and registers the 203-name allowlist:

```powershell
.venv\Scripts\python.exe scripts\setup\register_blender_connector.py `
  --bridge-config 'D:\3D_Projects\JarvisTest\bridge-8769.json'
```

The helper does not launch Blender or install anything. Never commit the bridge token/config file or private project data. Its bearer token is privileged local access; Blender Python and same-user processes are not sandboxed by the connector.

## Approval, paths and job behavior

Every operation passes existing Jarvis ToolRegistry policy and host approval. Writes additionally require a fresh approval showing the exact call and a freshly observed Blender scope/project. A private per-child HMAC proof binds the approved normalized arguments to that scope. The model's `host_authorization` is replaced by the host; scene text and material metadata cannot grant approval. The child fails closed without a valid host proof. There is no production auto-approve callback. Synthetic approvals in benchmark/test code apply only to their own disposable scenes.

Filesystem operations require explicitly selected allowed roots, resolved-path containment and expected extensions. Redirects and HTTP proxies are disabled. Writes to existing outputs are refused, including intentional overwrites: use a new filename. `render_animation` and `unpack_resources` return explicit prerequisite failures; their multi-file outputs cannot currently enforce these guarantees. Open/revert project is not advertised. Exporters may create adjacent files within the selected output directory. General transactional rollback is not promised. Native Blender undo/backup behavior varies by context; make a new project copy before a risky workflow.

Mutations return **queued**, not verified completion. A durable receipt records `scope_id` and `job_id` under `.jarvis-runtime/blender/jobs.json`, with bounded read-only polling and existing island state notifications. Done/error/partial/unready are distinct; failed polling stops after five failures with backoff. Monitoring stops while idle, on Quit and after 30 minutes; keep the original receipt for later manual inspection. Retained Blender job results expire after ten minutes when completed. Never repeat a creation/save/render after an uncertain timeout. Poll the original ID with its original scope. Restart/relink does not make old jobs safe to repeat. Completed outputs must be inspected independently.

Queue admission is capped at 32 and retained jobs at 256; HTTP workers at 16, request bodies at 256 KiB and client JSON responses at 2 MiB. Catalog numeric/collection bounds and Blender-side geometry limits reject invalid/oversized inputs; finite numbers are required recursively. Large evaluated scenes or user imports can still consume substantial resources. Approval displays compute cost context; bounded defaults are not a universal memory guarantee.

Jarvis's schema subset does not support nullable unions. Optional vectors use `[]` to mean unchanged; optional booleans use `unchanged`, `true`, `false`; optional scalar numbers use an empty string or numeric text. JSON-valued custom properties/attributes use an object envelope `{"value": ...}`. Batch payloads use canonical catalog parameter values, not these top-level omission sentinels. Unknown or ambiguous object names return concrete candidates and do not edit a fuzzy match. Node socket/type/context failures are explicit.

## Verification and limitations

Blender 5.2 compositor groups use an Image interface socket and `NodeGroupOutput`. Versioned node aliases replace removed compositor identifiers and Glossy BSDF; geometry subdivision uses `GeometryNodeSubdivideMesh`. Layered action channelbags are exercised. `add_bone` copies its name before leaving Edit Mode, avoiding access to invalidated edit-bone memory. All 89 allowlisted node types instantiate in the tested 5.2.2 engine through the adapter.

Fresh evidence includes baseline/post-change unittest runs, the adapted 68-test package suite, real 203-tool stdio discovery, 44 live smoke actions, a 200-action live execution audit, reopened project/mesh files and tiny CPU/OptiX PNG renders. Coverage classifications and exact results are in the audit, not inferred from unit coverage. The 120-request host benchmark uses synthetic text and approvals, real Blender and independent object readbacks; it does not certify microphone recognition, local LLM planning quality or island frame rates. It inspected a 15,876-vertex medium mesh and a 251,001-vertex large mesh. Blender-only GPU allocator peaks were unavailable. The audit separately records sampled whole-device utilization/memory, without attributing all desktop GPU usage to Blender.

The standard launcher readiness check still reports Docker/Ollama unavailable; therefore live local ambiguous planning and full assistant readiness are unverified. Blender 4.5, real crash/restart with user scenes, simultaneous competing real agents, end-user approval UI interaction, script trust for third-party scenes and full undo/backup semantics remain acceptance gates. Advanced sculpt strokes, retargeting, full VSE editing and arbitrary add-on scripting were not invented or advertised as completed features.

Run regressions from the canonical `app/` directory; repository-root pytest collection can traverse the compatibility junction and produce invalid duplicate-module diagnostics. Reproduce the disposable live and host checks with:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
& integrations\jarvis-connectors\connectors\apps\blender\run_live_tests.ps1 `
  -BlenderExe 'D:\blender.exe' -ReportPath 'artifacts\jarvis-audit\blender-connector\live-smoke.json'
.venv\Scripts\python.exe scripts\benchmarks\blender_e2e.py --blender 'D:\blender.exe'
```

## Rollback

If activated later, run `.venv\Scripts\python.exe scripts\setup\register_blender_connector.py --disable`, then restart Jarvis. This only disables the Blender entry and privately backs up configuration. Stop the bridge by running `stop_blender_bridge.py` **inside its owning Blender instance**; it stops its HTTP service, not the application. Do not kill unrelated Blender processes. If needed, restore the appropriate private pre-Blender configuration backup after review, preserving any subsequent unrelated changes. No Blender project, model, environment or user file is removed by this integration.
