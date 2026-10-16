# Keep/revert and exact changed sources

31-song selection warm p50/p95 22.29480/24.01100→20.82265/21.25810ms; Python peak 8619→8583B, identical chosen row. Query-token reuse avoids repeated normalization, no global private-query cache. Unicode retains combining marks, ASCII uses its fast normalization route. First all-character Unicode candidate regressed p50/p95(23.03035/28.57420→27.55910/32.42570ms); ASCII fast path supersedes it. The in-progress first full run was stopped and its log/hash snapshot preserved; no completion counted. Final benchmark has20warm+5initial samples/version, not cold-process/GUI/RSS/VRAM or first-audio results. Ties and exact artist formatting can cause conservative refusals; no live latency claim. Metadata filtering does not cryptographically authenticate source processes. Search payload shape/size, durable playback recovery, private logs and generic browser mutations remain open.

- `docs/media-player.md`
- `docs/system-map.md`
- `jarvis/media_player.py`
- `jarvis/spotify.py`
- `README.md`
- `../README.md`
- `scripts/verification/audit_catalog.py`
- `tests/test_audit_result_accounting.py`
- `tests/test_island_desk.py`
- `tests/test_media_player.py`
- `tests/test_media_audit.py`
- `scripts/verification/verify_media_audit.py`
- `scripts/verification/report_media_audit.py`
- `scripts/verification/verify_media_artifacts.py`

Generated module/global artifacts are enumerated in generated-files.json. Source.patch uses module25 preimages, not HEAD, preserving inherited changes.
