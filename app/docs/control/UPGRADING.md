# Upgrading the control backends

1. Check the current versions: `npm view agent-desktop version` and `npm view agent-browser version`, or the GitHub releases of `vercel-labs/agent-desktop` and `vercel-labs/agent-browser`. Read the changelog for envelope changes. Jarvis parses envelope v2.5 and fails closed on unreadable output, which counts as "may have acted".
2. Take the new asset names and `sha256:` digests from `https://api.github.com/repos/vercel-labs/<tool>/releases/latest`. Update the `Pins` list in `scripts/install_control_backends.ps1` and the `VERSION` constants in `jarvis/control/pc/runner.py` and `jarvis/control/web/agent_browser_backend.py`.
3. Run the script. It stops on any checksum mismatch and leaves nothing behind.
4. Re-read the bundled guidance:
   - `agent-desktop skills get desktop`, `... skills get platform` and `... skills get ffi`;
   - the agent-browser `skill-data/core` docs at the new tag (the standalone exe ships none).
5. Re-record the envelope fixtures in `tests/fixtures/agent_desktop` and `tests/fixtures/agent_browser`, as described in their tests. Use a fresh Notepad and example.com only, and strip personal text before committing.
6. Re-check the agent-browser policy action names against `cli/src/native/actions.rs` at the new tag. A renamed action would silently stop being denied. `tests/test_control_agent_browser.py` checks the names Jarvis relies on.
7. Run `pytest tests/test_control_*.py tests/test_neural_registry.py`, then `cases.py control --pc shadow --web shadow`. Switch defaults only after the A/B rule in `COMPARISON.md` passes again.

Rollback at any time: `JARVIS_PC_BACKEND=legacy` and `JARVIS_WEB_BACKEND=legacy`. To roll back a version, keep the old folder, since each version installs into its own `agent-desktop-<ver>` or `agent-browser-<ver>` folder, and point `JARVIS_AGENT_DESKTOP` or `JARVIS_AGENT_BROWSER` at the old exe.
