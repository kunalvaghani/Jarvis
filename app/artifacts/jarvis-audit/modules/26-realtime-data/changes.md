# Changes/keep/revert

Retained correctness fixes:

- Use monotonic provider deadlines and reject backward/future cache ages; respect long Retry-After values.
- Check cancellation before retrying a GET and preserve cancelled status after a read interruption.
- Convert explicitly declared Fahrenheit temperatures before weather thresholds/summaries, retaining conversion metadata and original input.
- Attach weather/air observation age; handle ISO offsets, local-day rollover and short daily arrays.
- Refuse notification after corrupt or failed weather checkpoints; atomically persist intent before callback and refuse uncertain replay.
- Report an unavailable forecast instead of claiming quiet weather.
- Keep broad modelled-hazard suppression opt-in; default alert cadence is unchanged. Semantic dedupe remains incomplete.

For a 5,000-key projection, warm p50/p95 changed from 1.08445/1.19810 ms to 0.21575/0.22080 ms; temporary Python peak changed from 208744 to 2407 bytes, with identical first 40 fields. Replacing whole-dictionary materialization with an islice of40 entries retains identical projection order/content and reduces temporary work. No global private-query cache. Five initial samples/version are not cold process starts; no HTTP, model, RSS/VRAM, TTFT or audible-alert latency claim. Extra normalization and checkpoint validation are correctness costs, not benchmarked end-to-end speed gains. Unsupported declared temperature units refuse data; absent units assume the known Open-Meteo Celsius default. The broad modelled-hazard cooldown candidate was restricted to opt-in, default0, to preserve default alert cadence. If enabled (up to86400s), it can suppress distinct same-kind hazards or escalation inside that window; old alert keys may allow one initial notification when enabling it. Legacy severity escalation is still separate. Persist-before-notify may lose an alert on crash; it must not automatically replay. Runtime journals are trusted local files, not adversarial-process or power-loss containment.

- `docs/realtime-data.md`
- `docs/system-map.md`
- `jarvis/realtime.py`
- `jarvis/realtime_sources.py`
- `jarvis/weather_watch.py`
- `README.md`
- `../README.md`
- `scripts/verification/audit_catalog.py`
- `tests/test_audit_result_accounting.py`
- `jarvis/weather_units.py`
- `tests/test_realtime_audit.py`
- `scripts/verification/test_realtime_audit.py`
- `scripts/verification/verify_realtime_data_audit.py`
- `scripts/verification/report_realtime_data_audit.py`
- `scripts/verification/verify_realtime_data_artifacts.py`

Generated module/global artifacts in generated-files.json; diff is against module26 preimages, preserving inherited changes.
