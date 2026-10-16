# Prompt 12 — ToolRegistry inventory (2026-10-15 IST)

Branch `audit/12-tool-registry`, based on `main` at `1dd5ea3` (clean tree at start). Windows 11 26200,
Python 3.10.6, AMD Ryzen 7 (16 logical CPUs), 31.3 GB RAM, RTX 3050 Laptop 4 GB. CPU-only work; no GPU, model,
network, account or OS mutation was used by any test or benchmark.

The [system map](../../../../docs/system-map.md) listed `actions.py`, `toolkits.py`, `tools.py`, `native_tools.py`
and `capabilities.py`. All exist. The real dispatch also runs through `agent_events.py` (policy and lifecycle
events), `desktop_actions.validate_desktop_step` and `desktop_tasks.write_new_file/modify_text_file`.

## Real entry points

| Entry | File | Role |
| --- | --- | --- |
| `ToolRegistry.execute` | `jarvis/tools.py` | The one dispatch path: task identity → scope (`allowed_tools`) → `check_policy` → `tool.started` event → **(new) argument contract** → `_execute` → event |
| `ToolRegistry.catalog/search` | `jarvis/tools.py`, `capabilities.py` | Planner-visible tools; credential-gated toolkit tools hidden when a goal is given |
| `toolkits.execute` | `jarvis/toolkits.py` | 83 toolkit/agent/utility/repository/REA/DeerFlow/Firecrawl operations; env-credential gate, approval for writes, `action_attempted` checkpoint before network writes |
| `native_tools.parse` | `jarvis/native_tools.py` | Ollama function call → one proposal; rejects extra/unknown fields |
| `check_policy`, `event` | `jarvis/agent_events.py` | `.jarvis/policy.json` deny rules (fail closed); metadata-only `agent-events.jsonl` |

Callers (all reach `ToolRegistry.execute`): `brain.dispatch`, `agent_session`, `agent_tools`, `hierarchical`
(DAG adapters), `knowledge_acquisition`, `actions` (direct tool command).

## Census

| Item | Count |
| --- | --- |
| Registered tools in this process | 107 (24 built-in, 83 toolkit) |
| Built-in tools with a typed field contract (new) | 24 / 24 |
| Tools marked `approval: user` | 20 |
| Toolkit tools gated on credentials | 21 (hidden from goal catalogues when unset) |
| Gmail API tools | Loaded only when Gmail is configured; not loaded in the test process |

## Advertised vs real (before this module)

| Claim | Evidence | Verdict |
| --- | --- | --- |
| Unknown tool names never execute | `_execute` checks `self.specs`; spy `actions` had zero calls | True |
| Path traversal rejected | `scoped_path` rejects absolute, drive, dot and escaping paths | True |
| Arguments validated before side effects | `create_file` without `folder` emitted a UI `tool` report, then raised `KeyError`; `open` with `value=123` reached `actions.execute` | **False → fixed** |
| Write tools need host approval | `_approve` is always called for toolkit writes; `delete_file` keeps only `value`/`folder` | True; approval-claim keys are now also stripped |
| Malformed service replies are safe errors | Non-object JSON from Slack/GitHub raised `AttributeError`, even after an approved Slack send | **False → fixed** |
| Concurrent writes are controlled | Two `append_file` calls could both pass compare-then-replace | **False → fixed** (per-file lock, in-process) |
| Traces never leak credentials | Events store no arguments, but the UI `tool` report echoed `?access_token=…` | **False → fixed** |
| Oversized/nested payloads bounded | JSON nested ~1,000 deep raised `RecursionError`, outside the `ValueError` handling | **False → fixed** |
