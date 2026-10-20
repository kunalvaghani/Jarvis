# Jarvis custom connectors

`BaseConnector` is the parent class for local MCP connectors that Jarvis calls through its existing
[MCP bridge](../../jarvis/mcp_bridge.py). Each app or task gets a small child class. The child
declares typed tools, and the base class handles the rest:

| The base provides | So a child does not need to |
| --- | --- |
| JSON schemas inside the subset that Jarvis's [call contract](../../jarvis/mcp_contract.py) accepts (checked when the class is defined) | write schemas or hit "unsupported schema keyword" refusals |
| Strict argument validation: no type coercion, no extra fields, enforced ranges and lengths | defend against malformed calls |
| Read/write access policy: write tools stay hidden unless the connector is started with `--allow-write` | gate dangerous tools |
| Bounded, type-checked results: an oversized or wrongly typed result fails instead of being cut off silently. The limit (`max_result_chars`, 9,500) applies to the whole result as Jarvis receives it. Use `fits()` to trim lists | worry about flooding the model or about Jarvis's 10,000-character bridge cutoff |
| `ToolError` for expected failures. Unexpected crashes return a generic message, and the traceback goes only to stderr | leak paths or stack traces |
| `ConfinedRoot`: one approved folder, bare file names only, no links or subfolders, size caps, create-only writes | hand-roll path-traversal checks |
| Two stdio runtimes: the official SDK v2 `MCPServer` when installed, otherwise a built-in stdlib runtime with the same behavior | depend on the SDK to run or test |
| CLI configuration (`add_arguments`), because Jarvis passes arguments and only *named* environment variables | invent a config format |

Adapted from `jarvis_custom_connector_starter` (local notes example). Its illustrative
`connectors` manifest is replaced here by Jarvis's real `.jarvis/mcp.json` format.

## Layout

```text
jarvis-connectors/
  jarvis_connector/        parent package: BaseConnector, tool, Param, ToolError, ConfinedRoot, runtimes
  connectors/apps/         app connectors, one folder each:
    youtube/               read-only YouTube search and lookup, registered in Jarvis as server "youtube"
  connectors/notes/        task child: list_notes, read_note, search_notes (+ demo_notes/)
  connectors/template/     copy this to start a new child (read tools + an opt-in write tool)
  tests/                   unit, raw-protocol subprocess and end-to-end Jarvis bridge tests
  evals/                   live local-model evaluations (qwen3.5:9b via Ollama)
  client_smoke.py          official SDK v2 client check (optional)
  mcp.example.json         example entry for app/.jarvis/mcp.json
  requirements.txt         optional SDK runtime dependency (mcp>=2,<3)
```

## Writing a child connector

```python
from typing import Annotated
from jarvis_connector import BaseConnector, Param, ToolError, tool

class GitConnector(BaseConnector):
    """Read-only inspection of one approved repository."""
    name = 'jarvis-git'

    @classmethod
    def add_arguments(cls, parser):
        parser.add_argument('--repo', required=True)

    def configure(self, options):
        self.repo = options.repo

    @tool()
    def recent_commits(self, limit: Annotated[int, Param('How many.', minimum=1, maximum=50)] = 10) -> list[dict]:
        """List recent commits in the approved repository."""
        ...

    @tool(access='write')
    def create_branch(self, name: Annotated[str, Param(min_length=1, max_length=80)]) -> dict:
        """Create a branch (only exposed with --allow-write; Jarvis approves every call)."""
        ...

if __name__ == '__main__':
    import sys; sys.exit(GitConnector.main())
```

Rules the base enforces when the class is defined: every tool has a docstring and type hints. Parameter
types are `str`, `int`, `float`, `bool`, `list[...]` or `dict`. There is no `Optional`/`Union` and no
`None` default. Tool names are `[A-Za-z][A-Za-z0-9_]{0,63}`. If a child overrides a tool method
without `@tool`, that tool is removed. See [connectors/template/server.py](connectors/template/server.py)
for the full checklist.

Write tools should verify their postcondition (read back what they wrote), refuse to overwrite
unless that is the job, and use least-privilege credentials. App connectors such as Blender or
Unreal must run their code inside the app (for example `bpy` inside Blender) or talk to an
editor-side bridge. They cannot import the app's API from an unrelated Python process.

## Running and testing

The built-in runtime needs only the Python standard library, so Jarvis's own `.venv` (Python 3.10)
can run it:

```powershell
cd "app\integrations\jarvis-connectors"
..\..\.venv\Scripts\python.exe connectors\notes\server.py --list-tools        # print the catalog
..\..\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider        # 48 tests
```

To use the official SDK v2 runtime (optional), use a **separate** Python 3.11+ venv. Do not install
it into Jarvis's `.venv`, and do not mix it with SDK v1's `FastMCP`.

```powershell
py -3.11 -m venv .venv-connectors
.\.venv-connectors\Scripts\python.exe -m pip install -r requirements.txt
.\.venv-connectors\Scripts\python.exe client_smoke.py --runtime sdk
```

`--runtime auto` (the default) uses the SDK when it can be imported and otherwise uses the built-in
runtime. Pin `--runtime builtin` or `--runtime sdk` in Jarvis config so behavior does not change
when packages change.

## Registering a connector with Jarvis

Jarvis reads `app/.jarvis/mcp.json` ([format and rules](../../jarvis/mcp_bridge.py)). Copy the
entry from [mcp.example.json](mcp.example.json), replace the paths with absolute paths, and set
`"enabled": true` only after the tests pass. Requirements:

- `command` must be an absolute path to a `.exe`. Scripts such as `.cmd` and `.ps1` are refused.
- `allow_tools` is an exact list of tool names. A write tool must appear in it *and* the connector
  must be started with `--allow-write`.
- Connector settings go in `args` (for example `--root`). Jarvis gives the child only a minimal
  environment plus variables listed in `env_names`. Use `env_names` for credentials; never put
  secret values in the file.

Jarvis then uses `mcp_status`, `mcp_list_tools` (`value` = server name) and `mcp_call` with
`{"name": "search_notes", "arguments": {"query": "Blender material"}}`. Every server start and call
requires approval, and arguments are checked against the advertised schema before they reach the
connector. Results are untrusted text and are never treated as instructions.

## Verification (2026-10-20, Windows 11, Jarvis `.venv` Python 3.10.6)

| Check | Result |
| --- | --- |
| Connector suite: base contract, notes, template, raw stdio protocol, end-to-end Jarvis bridge, 41 YouTube tests | 89 passed, 1 skipped (this Windows account cannot create symlinks), with `JARVIS_LIVE_YOUTUBE=1` |
| Live YouTube through Jarvis `ToolRegistry` → `mcp_bridge` → connector | PASS |
| qwen3.5:9b using the YouTube tools directly | 9/9 |
| qwen3.5:9b in a harness that mirrors Jarvis's one-step planner format (not the full Brain) | 8/10 in three of three trials; two prompts are answered from memory without a tool call |
| Official SDK v2 runtime (`--runtime sdk`) and `client_smoke.py` | NOT RUN: `mcp` 2.x is not installed |

Details, run history and open items:
[youtube-connector evidence](../../artifacts/jarvis-audit/youtube-connector/2026-10-20/README.md).

These checks do not make a connector a security sandbox. Run connectors with the narrowest
folder and OS access the task needs.
