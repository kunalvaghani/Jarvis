# Jarvis Blender child

The production entry point is `server.py`, a child of Jarvis's existing centralized BaseConnector. It composes the local `blender_connector` service; `upstream/` preserves the supplied reference package and original tests. The upstream example manifest/server is not production registration.

There are 200 catalog actions plus three scoped bridge/job helpers. Read the [installation, approvals, paths and rollback guide](../../../../../docs/blender-connector.md), [command inventory](COMMANDS.md), and [dated verification report](../../../../../artifacts/jarvis-audit/blender-connector/README.md). Not all advertised actions have full independent live acceptance; animation rendering and resource unpacking return explicit prerequisite failures.

Use the existing Jarvis environment for `client_smoke.py`. `run_live_tests.ps1` creates disposable factory-scene tests; `audit_live.py` records every action and its acceptance classification. No `bpy` wheel, paid API, cloud model or additional MCP SDK is required for builtin stdio.

Activation is pending explicit user approval; the active MCP configuration was preserved. A live Blender bridge needs a dedicated configuration path, unused port and selected allowed folders. Never replace another instance's scope or replay an uncertain edit/render. Stop the bridge inside its owning Blender instance, without killing the application.
