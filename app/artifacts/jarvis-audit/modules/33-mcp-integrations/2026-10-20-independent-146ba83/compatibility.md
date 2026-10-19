# Compatibility and readiness

Python 3.10.6 host with existing original utility interpreters routed read-only; reviewed source/data stay isolated. MCP stdio protocol 2025-11-25 and existing labelled image/SDK unchanged. No dependency/model/protocol installs. Bounded schema subset intentionally rejects unsupported schemas; arbitrary JSON Schema support is not claimed.

Changed behavior: configured account labels are unverified display values. An unchanged credential can use its approved snapshot. A changed credential requires fresh approval unless an independently registered read-only verifier proves the same principal/workspace and sufficient scopes. No production verifier is registered, so default refusal is expected and tested.

Isolated launcher-check.json still reports repair_required for missing environments/checkpoints. Docker/Ollama availability is readiness only. Author ready/full-suite evidence came from another environment and does not supersede this result. No native approval UI/live provider integration certificate.
