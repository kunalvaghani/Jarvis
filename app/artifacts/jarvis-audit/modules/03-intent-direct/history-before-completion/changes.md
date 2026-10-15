# Exact scoped changes

- `jarvis/intent_catalog.py`: four anchored built-in patterns: latest/most-recent document references route to the planner, sound up/down a notch follows active media, pause what is playing routes to existing pause, and corrected tab-close phrase uses existing command 329.
- `jarvis/engine.py`: remove trailing comma/semicolon only before a split command boundary; preserve existing writing policy and final-transcript rules.
- `tests/test_intent_direct_audit.py`: real parser/Engine/Actions assertions with fake launch/desktop/audio transports, no live effects. No production change to commands.py, names.py, Spotify or permission gates.
- `scripts/verification/verify_intent_direct.py`, `report_intent_direct.py`, and reviewed case allowlist in `audit_catalog.py`: reproducible paired parser timings, assertion-derived report and exact result accounting.
- Root/app README, natural-language guide, docs index, module reports and global ledgers: dated behavior, fixture limits, metrics and rollback. Earlier module 02 artifacts remain intact.

No dependency, model, tool name, configuration schema, persistent service or approval change. [Runtime diff](source.patch), [source hashes](source-hashes.json). Engine preimage is reconstructed by removing only the two inserted boundary lines; existing dirty engine changes remain, rather than restoring HEAD.
