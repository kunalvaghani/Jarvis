# Phase 3 — Rollback and independent Codex verification checklist

No Codex review evidence exists for this phase.

## Rollback

```powershell
git revert 6f880332610cc1a5c483f702c5f33b43d1537aa0        # on claude; removes the modules, sidecars and integration edits
```

Runtime state created by Phase 3 is local and ignored by Git; remove only if you want a clean slate:

* `.jarvis-runtime/skills/skill_store.sqlite3*` — skill history (guides keep working without it).
* `.jarvis-runtime/skills/evolved/` — provisional evolved guides (each has `provenance.json`).
* `.jarvis-runtime/mcp/generated/` — generated MCP servers and `registry.json`. Removing `registry.json` unregisters all
  generated servers; `.jarvis/mcp.json` user configuration is never touched.
* Docker image `jarvis-mcp-runtime:1` (`docker image rm jarvis-mcp-runtime:1`).

Disable without reverting: generated servers are dropped from `mcp_bridge` when their registry entry has
`"enabled": false`; a living skill is excluded from selection with `SkillStore.set_state(skill_id, enabled=False)`.

## Checklist

1. [ ] `git diff <sha>~1 <sha> --stat` matches [files-changed.txt](files-changed.txt); `main` unchanged.
2. [ ] `python scripts/setup/setup_mcp_runtime.py` then `python -m pytest tests/test_phase03_living_skills.py -q` → 36 passed
   with Docker; without Docker/Blender the affected tests must skip with `BLOCKED:`.
3. [ ] Confirm MOCK authors are only fixture text/spec suppliers; verify that their output passes through `validate_skill`,
   `verify_execution`, `screen` and real container tests.
4. [ ] Read `skill_store.SkillStore.event`: unique `event_key`; `metrics(current_version=True)` uses `epoch_event_id`.
5. [ ] Read `skill_evolution.update_trust`: no path makes trust depend on model text.
6. [ ] Read `mcp_synthesis.server_config`: network none, read-only, cap-drop ALL, non-root, limits, single read-only mount.
7. [ ] Try a malicious spec (e.g. `import ctypes`) against `mcp_synthesis.screen` — must be rejected.
8. [ ] Run the full suite; check `docker ps -a --filter label=org.jarvis.mcp-generated` is empty afterwards.
9. [ ] Confirm no file was written under the Obsidian vault by Phase 3 code paths (sidecars only in `skills/`,
   `custom-skills/`, `.jarvis-runtime/skills/evolved/`).
10. [ ] Challenge limitation L1/L2: no live model-authored mutation is claimed.
