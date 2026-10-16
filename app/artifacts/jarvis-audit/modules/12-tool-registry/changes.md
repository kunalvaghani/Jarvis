# Prompt 12 — changes (2026-10-15 IST)

Exact diff: [source.patch](source.patch). Hashes: [source-hashes.json](source-hashes.json).
Pre-change copies: [before/](before/).

| File | Change |
| --- | --- |
| `jarvis/tools.py` (+105/−5) | Typed field contracts for all 24 built-in tools (`_FIELDS`, `validate_arguments`, `ToolArgumentError`), checked before any report or dispatch. Toolkit steps are checked by the existing `toolkits.validate_step`. Approval-claim keys (`approved`, `bypass_approval`, …) are stripped from every step. `redact()` for emitted reports. `failure_category()` added to `tool.failed` events. `ToolResult.call_id` correlates with `agent-events.jsonl`. Typed unavailability for a missing realtime provider. |
| `jarvis/toolkits.py` (+62/−32) | `ToolUnavailable(ValueError)` for missing credentials. Malformed parameters/replies become typed errors that say a write may have happened. Per-file lock around append compare/replace/readback (append split into `_append`; the scan loop moved unchanged into `_scan`). `RecursionError` handled when parsing arguments. |
| `jarvis/agent_events.py` (+6/−1) | `category` is an allowed categorical event field (`invalid_arguments`, `unavailable`, `cancelled`, `failed`). New error type names are allowed. |
| `jarvis/native_tools.py` (+1/−1) | Deeply nested argument JSON is a `ValueError`, so the planner's existing single re-ask applies. |
| `tests/test_tool_registry_audit.py` (new) | JRV-12-001…032 plus five named regression tests. |

**Compatibility:** `ToolArgumentError` and `ToolUnavailable` subclass `ValueError`, so every existing
`except ValueError` and `TaskFailure` path behaves as before. `ToolResult` gains a defaulted trailing field.
Valid steps produce byte-identical evidence (benchmark digest). No configuration, dependency, service or launcher
change was made.

**Kept out deliberately:** pattern redaction of tool *evidence* (it could corrupt files the planner later writes
back), rejecting unknown step keys (planner/DAG steps carry `expected`, `id`, `dep` and similar), and
cross-process file locking.
