# Prompt 12 — rollback

All changes are on branch `audit/12-tool-registry` and are uncommitted as of this report. There are no
configuration flags, data migrations or persisted-format changes. New `agent-events.jsonl` rows only add an
optional `category` field, which older readers ignore.

Undo the source changes (from the repository root):

```powershell
git checkout -- app/jarvis/tools.py app/jarvis/toolkits.py app/jarvis/agent_events.py app/jarvis/native_tools.py
Remove-Item app/tests/test_tool_registry_audit.py
```

Alternatively, restore the saved copies in [before/](before/) for `tools.py`, `toolkits.py` and
`agent_events.py`, and reverse the one-line `native_tools.py` hunk in [source.patch](source.patch)
(`git apply -R app/artifacts/jarvis-audit/modules/12-tool-registry/source.patch`).

Then run `python -m pytest tests/test_tools.py tests/test_toolkits.py tests/test_native_tools.py
tests/test_agent_runtime.py tests/test_audit_catalog.py` (pre-change baseline: 109 passed) and
`python -m jarvis.launcher --check`. Restart Jarvis once so the running process loads the restored source.
