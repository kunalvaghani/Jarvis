# Scoped rollback — module 04

Use normal Stop Jarvis before a reviewed runtime rollback. Preserve current changed files and metadata first. Apply only this module's reviewed hunks in [source.patch](source.patch) against [source hashes](source-hashes.json); do not use git reset/checkout HEAD over the existing dirty workspace.

Captured preimages: `.jarvis-runtime/jarvis-audit/module02-pre`, `module03-pre`, `module04-pre` and `completion-pre`. Completion-pre contains the prior Brain/Tools/Actions/TaskState/ScreenAwareness, including earlier user work. Engine and runtime-health preimages are labeled normalized reconstructions of scoped insertions; Whisper backend uses clean-at-voice-start HEAD provenance. Do not blindly restore whole shared files: later module fixes overlap. Runtime manifest preimage is in module04-pre/runtime_manifest.json; preserve other sections when reverting voice_input_audit.

Task UUID is additive; older checkpoints fall back to started_at identity. Do not restore/replay pending action queues, remove uncertainty journals or treat interrupted writes as safe retries. No dependency downgrade or personal-file deletion is necessary. Keep approval/privacy/Stop guards even when disabling cognition (`cognition.enabled=false`) or optional cleanup (`command_cleanup.enabled=false`).

After any rollback, rerun the scope command in inventory.md, full `pytest tests -q --tb=short`, and `python -m jarvis.launcher --check`. Re-measure before claiming timing gains. Current patch is preserved without deployment or forced process restarts.
