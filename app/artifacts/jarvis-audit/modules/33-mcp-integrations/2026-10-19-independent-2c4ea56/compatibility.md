# Compatibility

Host Python 3.10.6 and existing installed utility interpreter; isolated audited source and disposable data. Protocol remains 2025-11-25, stdio only. Existing Docker image/SDK identity captured in protocol.json. No package, transport, model or launcher configuration change by Codex. New schema subset may reject unsupported advertised schemas intentionally; this is not full JSON Schema support. Legacy missing generated identity pins require explicit revalidation; no silent migration claim.

launcher-check.json remains repair_required for isolated missing environments/checkpoints, while Docker and configured local Ollama models are available. Claude's ready result was from the original environment and does not supersede this worktree result. Enabled/disabled direct server, namespace and no-retry fixture controls reran; full provider scopes/refresh/tenant and concurrent registration remain BLOCKED.
