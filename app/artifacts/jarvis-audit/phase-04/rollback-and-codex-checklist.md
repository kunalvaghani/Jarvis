# Phase 4 — Rollback and independent Codex verification checklist

No Codex review evidence exists for this phase.

## Rollback

```powershell
git revert <phase-04-commit-sha>     # on claude
```

Disable without reverting (`config/config.json`): `viking_memory.enabled: false` (no OpenViking server),
`exploration.enabled: false`, `reasoning_bank.enabled: false`.

Local state created by Phase 4 (ignored by Git; remove only for a clean slate): `.jarvis-runtime/reasoning_bank/`,
`.jarvis-runtime/openviking/` (index workspace, manifest, generated `ov.conf` with its local root key),
`.jarvis-runtime/exploration/`, the `.venv-openviking` environment, and the Ollama model `nomic-embed-text`
(`ollama rm nomic-embed-text`). The Obsidian vault is never written by Phase 4 code, so it needs no restore.

## Checklist

1. [ ] `git diff <sha>~1 <sha> --stat` matches [files-changed.txt](files-changed.txt); `main` unchanged.
2. [ ] With Chrome, Blender, `.venv-openviking` and `nomic-embed-text` present: `python -m pytest tests/test_phase04_learning_memory.py -q` → 21 passed; without them the affected tests skip with `BLOCKED:`.
3. [ ] Read `exploration.IsolatedBrowserEnv.reset` (fresh context, route abort) and `desktop_environment` (always refuses).
4. [ ] Read `learning_memory.sandbox_registry_factory`: approval only for `blender_task` inside the sandbox folder.
5. [ ] Read `reasoning_bank.ReasoningBank.induce`: success requires `status == completed` and non-empty verification.
6. [ ] Read `viking_memory.VikingMemory.start`: Ollama started via `knowledge_worker.ensure_server` first; `OLLAMA_*` passed through; refuses without the embedding model (H1).
7. [ ] Run the real-vault script on a copy of a vault and confirm the before/after hash and `verified_links`.
8. [ ] After the full suite, confirm no `openviking-server` process remains and Ollama's `OLLAMA_MODELS` is the user's store.
9. [ ] Challenge M1–M8 in [findings-and-limitations.md](findings-and-limitations.md).
