# Architectural notes

## Matching existing connector contracts

The user's YouTube zip includes `youtube_connector/base.py` with `ConnectorInfo`, `ConnectorError`, `UnsupportedAction`, abstract `info`, `connect`, `close`, `health`, and `require_text`. The Spotify package uses the same base. This Blender package copied that exact base signature into `blender_connector/base.py`, so `BlenderConnector` directly subclasses it. If Jarvis already has its own centralized BaseConnector, Codex should replace the local import with Jarvis's actual interface, not keep duplicate base classes in production.

The prior notes/YouTube/Spotify connectors expose tools via `@mcp.tool` in `server.py`, using stdio. This Blender `server.py` is generated from the canonical action registry (`catalog.py`) to make each tool independently discoverable, with typed Python parameters. The generating script is checked in: `python generate_server.py`.

## Data plane

`server.py` (outside Blender) -> `BlenderConnector` async proxy -> `127.0.0.1:8769` JSON HTTP -> `Bridge.pending` -> `Bridge.pump()` inside the Blender timer -> `BlenderOperations.execute()` -> bpy. No Blender Python calls occur in the HTTP worker thread. Long operations may monopolize the Blender main loop. The pump handles one command per tick and reports `done`/`error`; `running` is not considered completed.

## Security boundary

The bridge token prevents unauthenticated use of the local API but **does not sandbox Blender's Python environment**. Running untrusted Python, untrusted extensions or .blend auto-execution can compromise the OS user. OS permissions are the final security boundary. Do not load arbitrary plugins or scripts as part of autonomous internet learning. The bridge itself has no arbitrary Python execution endpoint.

Approval risk is in `catalog.py`: `read`, `write`, `filesystem`, `destructive`. The MCP host must add a genuinely human-authorized callback to `BlenderConnector(..., approval_callback=...)` and must not delegate safety decisions to an untrusted LLM. Native bridge token access is privileged; do not share credentials.

## Tool contract

Successful standalone action: `{'action':'add_cube','data':{'name':'Cube'}}` wrapped by the async transport as `{'ok':true,'status':'done','job_id':'...','result':...}`. An exception becomes a job with `status='error'` and a short error message. A partial batch is **not** `ok=true`: client returns `{'ok':false,'status':'partial','result':...}`. A timeout returns `{'ok':false,'status':'queued'|'running', 'job_id':...}`; this is **not cancellation**.

## Resilience

- Avoid simultaneous competing changes: client serializes enqueue requests and Blender executes commands one at a time.
- For multi-step workflows inspect the object/result after each edit; don't depend on state inferred solely from a successful submit.
- Retry only idempotent reads after transient transport errors. Do not automatically resubmit writes after network timeouts.
- Maintain a local model-independent plan and persisted job references; recovery should query job status and Blender scene state after restart.
- Emit Dynamic Island statuses (`queued`, `running`, `done`, `partial`, `error`) after ToolRegistry authorizations and bridge results.
- The sample manifest is deliberately noncanonical until adapted to the actual Jarvis repository.

## Future extensions

Build specialist child modules for sculpting, UV texture painting, rigging/retargeting, Blender video sequencer, particle/physics nodes, asset catalogs, render farm queue, and safe external asset import. Every new action needs explicit typed schema, reliable data API/operator implementation, negative and real-Blender tests, and risk tags. Provide a planned tool rather than a universal arbitrary `execute_python` command.
