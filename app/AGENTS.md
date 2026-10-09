# Jarvis maintenance requirements

For every Jarvis upgrade in this workspace:

- Keep `README.md` current in the same change: features, usage examples, setup, configuration, paths, architecture, integrations, limitations, troubleshooting, and dated verification results. Update the parent repository README when its overview changes. Include current UI images when available, distinguish rendered previews from live screenshots and upstream demos, preserve attribution, and verify repository-relative links. If there is no documentation impact, say so in the final report; do not invent results or add filler.
- Keep `Start Jarvis.cmd`, `Stop Jarvis.cmd`, `jarvis_bootstrap.py`, `jarvis/launcher.py`, `config/runtime_manifest.json`, and `jarvis/recovery.py` compatible with the change.
- Add new declared Python dependencies to the appropriate requirements file and runtime manifest. Register new long-running owned services with health checks and bounded recovery.
- Keep recovery silent: hidden processes, no repair popups, no spoken repair announcements. Write repair status to the transcript and `.jarvis-runtime/repairs.jsonl`.
- Respect intentional microphone stops and Quit/Stop Jarvis. Do not restart deliberately closed user apps or kill shared/unowned processes.
- Never replay a file write, shell command, click, shortcut, or other external action after an uncertain failure. Preserve task checkpoints and inspect the fresh state first. Only inference and read-only observations may be retried automatically.
- File deletion still requires explicit user approval. Recovery may restore Jarvis-owned source/configuration from known backups, preserving damaged copies, but must not delete user files or invent code patches for unknown bugs.
- Test new recovery paths with injected faults, including shutdown and retry backoff. Run the relevant regression suite and `python -m jarvis.launcher --check` after completing changes.
