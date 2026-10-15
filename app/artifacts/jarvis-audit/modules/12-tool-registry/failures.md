# Prompt 12 — reproduced failures (2026-10-15 IST)

Each defect was reproduced against the pre-change code. [before-cases.xml](before-cases.xml) records **18 failed /
18 passed** for the new test file run against a copy of `main` with the four changed modules restored from
`HEAD`. Twelve of those failures are the defects below. The other six assert new behaviour (correlation IDs,
failure categories, typed unavailability).

| ID | Repro (fixture) | Before | Root cause | Fix |
| --- | --- | --- | --- | --- |
| F12-1 / JRV-12-004, 015 | `{'action':'create_file','value':'x.txt'}`; `{'action':'open','value':123}` | `KeyError: 'folder'` after a UI `tool` report; mistyped value dispatched as `Command('open', 123)` | Built-in tools had no field contract; fields read with `step[...]` after reporting | `validate_arguments` with per-tool required/optional string fields, size limits and nonempty value, run before any report or dispatch; raises `ToolArgumentError(ValueError)` |
| F12-2 / JRV-12-006 | Slack reply `[1]`; GitHub reply `["x"]`; missing `path` JSON key | `AttributeError`/`KeyError`, including after an approved Slack send | `json.loads(raw).get(...)` and `args[...]` were not guarded | `toolkits.execute` converts `KeyError/TypeError/AttributeError/RecursionError` into `ValueError`; for writes the message says the write may have happened |
| F12-3 / JRV-12-006 | `realtime_query` content `[1,2]` or `{bad` | List passed through to `realtime.query`; raw `JSONDecodeError` | No object check | Content must decode to a JSON object (typed error) |
| F12-4 / JRV-12-007 | 5 concurrent `append_file` calls with the replace step held at a barrier | Pre-change: updates raced (one run ended `base-B` with the other call failing `WinError 5`); without the barrier a later replace can overwrite an already-verified append | Compare, replace and readback were not one critical section | Per-resolved-path in-process lock around the whole append |
| F12-5 / JRV-12-012, 021 | `browse https://x.example/?access_token=FAKE…` | Token copied verbatim into the UI/transcript `tool` report | `report()` received raw values | `redact()` scrubs credential query parameters, Bearer/Basic values, known token prefixes and secret-named env values from the report. **Tool evidence is not rewritten**, so a later write cannot replace a real value with `[redacted]` |
| F12-6 / JRV-12-031 | `'['*5000` as realtime or toolkit content, or as native planner arguments | `RecursionError` escaped the `except ValueError` handling, including the native planner's retry loop | `json.loads` depth limit | `RecursionError` handled at all three parse sites |
| F12-7 / JRV-12-016 | `realtime_query` with no realtime provider | `AttributeError` | Direct attribute access | Typed `ToolUnavailable` |

## Residual risks (not fixed in this module)

- The append lock is per process. Two separate Jarvis processes, or an external editor, can still race. That
  case is detected by compare-before-replace but not serialized.
- `brain.recover_task` checkpoints `target=step["value"]` into the local TaskState file. A credential typed into
  a value can be stored on disk locally. It never leaves the PC, but it is not redacted (module 16/35 scope).
- Cross-process registry snapshots: specs are frozen at import, so a running process never picks up new
  built-ins. Repository/utility tool rows are reread per catalogue call, by design.
- Live GUI, Windows UI Automation, real accounts and live network calls were not exercised (see tests.jsonl).
