# Reviewed Windows execution primitives

Jarvis uses selected primitives and ports from five pinned public repositories in
the user's requested order. [Integration, behavior and evidence](../../docs/execution-providers.md).

| Priority | Project | Retained license | Integration |
| --- | --- | --- | --- |
| 1 | Microsoft UFO | [MIT](licenses/UFO-MIT.txt) | Adaptation of single control dispatch and application keyboard input |
| 2 | CursorTouch Windows-MCP | [MIT](licenses/Windows-MCP-MIT.txt) and [Apache 2.0](licenses/UIAutomation-Apache-2.0.txt) | Six selected UIA pattern classes; original UIAutomation author **yinkaisheng** |
| 3 | Cua Driver | [MIT](licenses/CUA-MIT.txt) and [driver notices](licenses/CUA-Driver-THIRD-PARTY-NOTICES.md) | Python ports of Windows Value/Invoke pattern resolution |
| 4 | Open Computer Use | [MIT](licenses/Open-Computer-Use-MIT.txt) | Python ports of Windows native Value/preferred accessibility click |
| 5 | Simular Agent-S | [Apache 2.0](licenses/Agent-S-Apache-2.0.txt) | Adapted WindowsACI centre calculation, using existing guarded input |

Copyright and permission notices are retained in these linked files. Cua's driver
notices include Interface-Agent, trope-cua and yabai attribution; their unrelated
cursor, background-input and macOS implementations are not activated by this port.
The UIAutomation license file contains the standard Apache 2.0 terms, with the
original author's attribution also in both generated Python file headers.

[source-manifest.json](source-manifest.json) records exact commits, selected source
paths, hashes and modifications. [source-inventory.json](source-inventory.json)
indexes **5,700 source files** and **90,951 symbol/declaration entries** across all
five checkouts. This is a machine inventory with heuristic categories; it does
not mean every declaration was manually reviewed, copied or made executable.

[windows_mcp_patterns.py](windows_mcp_patterns.py) is the retained source artifact.
The identical runtime copy is [jarvis/upstream_windows_patterns.py](../../jarvis/upstream_windows_patterns.py),
covered by Jarvis's existing source recovery snapshots. Only the adapter's named
operations are exposed; retained class methods such as Collapse/AddToSelection
and SetScrollPercent are not new public Jarvis commands.

Rebuild from the exact local upstream checkouts with:

```powershell
.venv/Scripts/python.exe audit_execution_sources.py
.venv/Scripts/python.exe vendor_execution_primitives.py
```

The full checkout directory `../execution-upstream/` is ignored by Git. Its five
original Git repositories remain locally available for further source review.
Runtime does not depend on these checkouts and never executes their setup scripts.
