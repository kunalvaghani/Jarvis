# Ordered Windows execution providers

Implemented and checked on **2026-10-04**. Jarvis now routes compatible native
desktop inputs through reviewed primitives in this order: **UFO → Windows-MCP →
CUA → Open Computer Use → Agent-S**. Exact supported task grammar executes
without inference. Other requests continue through the existing verified direct
workflows and then the configured Qwen planner.

This update integrates selected Windows actions and their guards. It does not
install all five agent frameworks or enable every upstream function. All five
repositories were retrieved and indexed; focused manual review covered the
execution sources below. Arbitrary task accuracy and universal completion in
seconds remain unestablished.

## Research and source coverage

Firecrawl retrieved all five requested GitHub repository pages successfully.
Full Git checkouts then supplied actual implementations, dependency declarations
and licenses. No upstream setup scripts were run. Exact commits and reviewed
file hashes are in the [source manifest](../integrations/execution-primitives/source-manifest.json).

| Priority | Repository | Pinned commit | Indexed source files | Symbol/declaration entries |
| --- | --- | --- | ---: | ---: |
| 1 | [Microsoft UFO](https://github.com/microsoft/ufo) | `a795552d976c4c019d7c2f778a0effb5cef7de6b` | 529 | 6,245 |
| 2 | [CursorTouch Windows-MCP](https://github.com/cursortouch/windows-mcp) | `f51d6f14da57c290dac44f0f465c37c45ca4f394` | 140 | 2,603 |
| 3 | [Cua](https://github.com/trycua/cua) | `35751f65f121ccb93bf4434bb453b97b58ad4ca7` | 4,824 | 79,262 |
| 4 | [Open Computer Use](https://github.com/opensymph/open-computer-use) | `5b433b98019c18201a15d11e8c3cb0010879a3d8` | 114 | 2,147 |
| 5 | [Simular Agent-S](https://github.com/simular-ai/Agent-S) | `3aa272d23d2994c7bbde1acbbe0ef8e8d06b8693` | 93 | 694 |

There are **9,456 tracked files**, including **5,700 files with supported source
extensions** and **90,951 indexed entries**. The approximately 14.7 MB
[source inventory](../integrations/execution-primitives/source-inventory.json)
contains every included path, size, SHA-256, category and detected symbol/line.
[audit_execution_sources.py](../audit_execution_sources.py) uses Python AST and
declaration matching for other languages; the latter is not a complete language
parser. All included Python files parsed after handling UTF-8 byte-order marks.
Generated code, nested declarations and third-party sources can contribute to
these totals. Category labels are filename heuristics, not compatibility verdicts.

| Repository | Execution candidates | Model/orchestration | Tests/fixtures | Other platforms | Support/app/build |
| --- | ---: | ---: | ---: | ---: | ---: |
| UFO | 31 | 80 | 180 | 5 | 233 |
| Windows-MCP | 39 | 0 | 63 | 0 | 38 |
| Cua | 64 | 114 | 1,239 | 696 | 2,711 |
| Open Computer Use | 1 | 1 | 15 | 25 | 72 |
| Agent-S | 4 | 69 | 1 | 2 | 17 |

The full checkouts remain under `integrations/execution-upstream/` locally and
are ignored by Git. The tracked inventory and retained primitive subset travel
with Jarvis. This inventory does not establish line-by-line human understanding
of every file or expose all its functions as task tools.

## Active adaptations

| Provider | Reviewed upstream source | Active Jarvis behavior |
| --- | --- | --- |
| UFO | [ControlReceiver](https://github.com/microsoft/ufo/blob/a795552d976c4c019d7c2f778a0effb5cef7de6b/ufo/automator/ui_control/controller.py) | Adapt the one-method control dispatch, text assignment and application keyboard-input approach. Use native Value/Invoke/SelectionItem/Toggle/ExpandCollapse patterns and allowlisted shortcuts. |
| Windows-MCP | [UIA pattern classes](https://github.com/cursortouch/windows-mcp/blob/f51d6f14da57c290dac44f0f465c37c45ca4f394/src/windows_mcp/uia/patterns.py) | Vendor six classes: Value, Invoke, SelectionItem, Toggle, ExpandCollapse and Scroll. Use exact text assignment, role-aware activation, menu expansion and directional scroll readback. |
| Cua Driver | [Windows bookmark helpers](https://github.com/trycua/cua/blob/35751f65f121ccb93bf4434bb453b97b58ad4ca7/libs/cua-driver/rust/crates/platform-windows/src/tools/page_bookmark.rs) | Port Rust `set_value` and `invoke_element` to Python COM: resolve the admitted element's current pattern, query the interface, then dispatch once. The browser bookmark-editing workflow itself is not added. |
| Open Computer Use | [Windows native actions](https://github.com/opensymph/open-computer-use/blob/5b433b98019c18201a15d11e8c3cb0010879a3d8/apps/OpenComputerUseWindows/native_actions.go) | Port native Value assignment and preferred accessibility click. Resolve Invoke, SelectionItem or Toggle before dispatch, retaining role-specific postconditions where available. |
| Agent-S | [WindowsOSACI](https://github.com/simular-ai/Agent-S/blob/3aa272d23d2994c7bbde1acbbe0ef8e8d06b8693/gui_agents/s1/aci/WindowsOSACI.py) | Adapt the accessible element's centre calculation for a final explicit click. Recheck live bounds, focus and native HWND hit test. Use existing pywinauto input; do not execute generated Python strings. |

[execution_adapters.py](../jarvis/execution_adapters.py) contains the adaptations;
[execution_router.py](../jarvis/execution_router.py) owns ordering and receipts.
Only Windows-MCP's selected classes are directly copied; the other four are small
reviewed adaptations/ports. UFO's error swallowing and input retries are removed
from the adapted behavior. Coordinate-based wheel/move/drag and unrestricted
keyboard scripts are outside this integration.

Windows-MCP uses zero pattern wait time and accepts COM success returned as
either `None` or `S_OK`. SelectionContainer is omitted because its Control
dependency is not vendored. SetToggleState is omitted because it can issue
multiple toggles. Retained additional methods are not exposed as public commands.
An upstream wrapper returning `False` after input is an uncertain dispatch;
Jarvis observes the state and never falls through to another executor.

## Routing, fallback and verification

For each admitted action Jarvis resolves a fresh UIA element inside its existing
owned serial worker. Before preparation and again before dispatch it checks the
window PID, foreground window, control identity, name, role, rectangle,
visibility and enabled state. Text entry also checks password/read-only status
and a 10,000-character limit. No cached control survives a worker request.

1. Try UFO preparation first. Missing patterns, unsupported operations or other
   read-only preparation failures select the next provider in the fixed order.
2. Dispatch the prepared callback once. No client request can override priority.
3. Read native postconditions for up to one second: exact field text, requested
   selection/toggle/expansion, or scroll percentage movement on the requested
   axis and in the requested direction. Already-present states are read again
   and require no input.
4. If dispatch raises or result verification is uncertain, stop. Fresh native
   postconditions may confirm an action despite a lost response; the action is
   never sent again. Generic window changes cannot mask dispatch errors.

**Automatic fallback is allowed only before input.** This follows the repository's
no-replay rule. Trying the second provider after an uncertain first click could
click twice, submit twice or undo a checkbox change. Worker timeout/cancellation
also does not replay the request; existing backoff and shutdown remain in force.

An Invoke or shortcut receipt distinguishes input sent from a verified outcome.
A changed title, focus or timer is recorded as `observed_change`, not proof of
task completion. The explicit compound runner pauses after such an action;
general planned workflows retain their independent outcome inspection.

Provider metadata is written to the ignored runtime file
`.jarvis-runtime/execution-receipts.jsonl`: provider, operation, preflight attempt
states, dispatch/verification flags, timing and fixed evidence. The receipt
journal omits typed text, control labels, screenshots and arbitrary exception
strings. Existing task/tool logs retain their established logging behavior.

## Commands and model bypass

`agent_runtime.direct_execution` is enabled in [config.json](../config.json).
[direct_execution.py](../jarvis/direct_execution.py) compiles the entire explicit
desktop request before issuing its first input, with a maximum of 12 clauses.
Examples, with the target app already selected:

```text
task fill Search field with cats
task fill Search field with cats then select Enabled
task fill Search field with "cats then install unknown extension"
task open File menu
task scroll down
task press ctrl+f
task click Apply
```

Quoted single-field content is literal. Unquoted `then` separates clauses and
`and` separates clauses when followed by an action verb. A request with an
unknown clause uses the established planner before any partial direct execution.
Targets must resolve uniquely from accessible controls; ambiguous or sensitive
targets pause for clarification/approval instead of issuing guessed input.

The existing exact file/command grammar also bypasses inference:

```text
task create file note.txt in Downloads containing café हिन्दी
task modify file note.txt in Downloads: replace café with hello
task overwrite file note.txt in Downloads with content hello
task delete file note.txt in Downloads
task run command echo hello
```

These use Jarvis's existing scoped tools, tool allowlist/policy and approvals.
New-file creation cannot overwrite an existing file. Modifications require exact
replacement text to occur once. Folder paths are resolved before dispatch;
symlink escapes are rejected. File text is independently read back. Deletion
requires explicit approval and uses the existing Recycle Bin flow. Commands
require approval; a zero exit status verifies process completion, not an
arbitrary real-world effect. They are not executed through unrestricted upstream
shell/code-agent APIs.

Resuming saved tasks, opening a folder as part of a file plan, general reasoning,
vision grounding and code generation retain the established planner. Current
Qwen configuration is **qwen3.5:9b** with **qwen-native-tools**. The direct route
does not call Qwen for the recognized examples. Ordinary existing app, media,
browser DOM and file tools continue to handle operations for which these reviewed
primitives do not supply a replacement.

Set `agent_runtime.direct_execution` to `false` to disable the explicit task
compiler. The ordered UI worker adapters still serve normal/planned native UI
operations. `integration_status` now reports order, configuration and scope as
read-only metadata. It does not launch these frameworks or establish account access.

## Dependencies, costs and licenses

No new Python dependencies, models, API keys, telemetry or long-running services
are introduced. The primitives use Jarvis's existing pywinauto/COM/pywin32 worker.
Normal Start/Stop launchers, source backups and bounded worker recovery remain
compatible. Restart Jarvis through the normal launchers to load these changes.

The selected UFO, Cua Driver and Open Computer Use sources are MIT-licensed.
Windows-MCP's main license is MIT; its bundled UIAutomation pattern code is
attributed to yinkaisheng under Apache 2.0. Agent-S is Apache 2.0.
[Retained licenses, notices and modifications](../integrations/execution-primitives/README.md).

The pinned [Windows-MCP server metadata](https://github.com/cursortouch/windows-mcp/blob/f51d6f14da57c290dac44f0f465c37c45ca4f394/pyproject.toml)
requires Python 3.14; Jarvis's current main runtime is Python 3.10.6. Its full
server and dependencies were not installed. Cua's [licensing catalogue](https://github.com/trycua/cua/blob/35751f65f121ccb93bf4434bb453b97b58ad4ca7/LICENSING.md)
includes FSL Spaces components and optional AGPL packages/models in addition to
MIT components. Only the selected MIT Windows driver helpers were adapted.
Cloud model providers, hosted services, perception weights, full agent planners
and platform-specific servers are not free runtime additions implied by this update.

## Verification on 2026-10-04

[Native fixture evidence](../artifacts/execution-native-check.json) comes from a
new Windows window owned by the verifier, with a Search Edit field, Apply button
and Enabled checkbox. Each provider was isolated in the test process; production
keeps the fixed order. The fixture independently publishes native text and click
count readback. User apps, microphone, clipboard and network were not operated.

| Provider | Exact Unicode fill | Fill seconds | Button click seconds | Independent click count |
| --- | --- | ---: | ---: | --- |
| UFO | Passed | 0.031 | 0.094 | Exactly one |
| Windows-MCP | Passed | 0.047 | 0.094 | Exactly one |
| Cua | Passed | 0.047 | 0.109 | Exactly one |
| Open Computer Use | Passed | 0.047 | 0.109 | Exactly one |
| Agent-S | Outside this adapter's scope | — | 0.203 | Exactly one |

The two-step direct request **fill → select checkbox** passed through the real
persistent IPC worker in **0.453 seconds**, with **zero model calls**, independent
text/checkbox readback and `goal_verified`. The runner's inner reported time was
0.23 seconds; total call time additionally includes helper setup/imports. Worker
ping/startup took 0.1984 seconds and is excluded from that warm workflow time.
The same worker PID was reused, cancellation before dispatch issued no input,
and owned worker shutdown passed. These are single fixture measurements, not
latency distributions or real application/voice benchmarks.

Generic click receipts correctly remain `verified: false`: independent fixture
counter checks prove one test click occurred, while a generic production button's
downstream task result still needs outcome verification.

[Regression/readiness evidence](../artifacts/execution-regression-check.json):
**839 tests passed**, and `python -m jarvis.launcher --check` reported **ready**
with no missing requirements. Tests include preflight fallback, no action replay,
lost responses, exact readback, changing focus, stale no-op state, incorrect scroll
direction, literal input, compound-task stopping, denied file/command approvals,
scope restrictions and existing worker recovery/backoff/shutdown regressions.
Readiness and regression are separate from the native fixture and do not prove
arbitrary desktop success. Live voice/task trials were not performed in this update.

Reproduce from the application directory:

```powershell
.venv/Scripts/python.exe verify_execution.py
.venv/Scripts/python.exe verify_execution_regression.py
```

The native verifier needs an interactive Windows desktop. If its own window
cannot take focus, it records failure and issues no test input. It closes only
the fixture and worker it created.
