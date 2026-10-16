# Prompt26 realtime audit — 2026-10-16 IST

**PARTIAL:20 fixture catalog PASS/12 BLOCKED.**

Authored HTTP/WS responses and clocks, isolated temporary journals, fake alert sinks, five small fixture threads x20 rounds, and an owned child exiting23 after notification intent persisted. No live feed, geolocation, credential read/setup, real speech/notification, account write, OS setting change, install or heavyweight model/GPU workload. Existing full-suite browser/process fixtures stay isolated. No visible UI layout change or new screenshot; historical artwork/attribution is preserved.

| Claim | Actual source/registration | Executed evidence and scope |
| --- | --- | --- |
|82 adapters | realtime_catalog.CATALOG, Provider rows→realtime_sources.endpoint/read |82 unique entries, endpoint construction for all82 with fixture operands/setup; provider-inventory.json enumerates IDs, modes, cadence, setup and official URLs; not82 live availability proofs |
| Read-only tools | commands/realtime.command→Actions/Realtime.controls; realtime_query→Realtime.query→Sources.fetch | Fixed provider IDs/endpoint constructors, GET/short read subscriptions; feed data never becomes executable authority |
| Current weather | Realtime.query(location binding)→Sources.fetch | Request coordinates and source_time included; current weather/air timestamps use published UTC offset, age0–900s; unknown timestamps stay unknown, other provider policies incomplete |
| Clock/cache | Sources timer/cache_times/next | Production provider-read cadence/Retry-After deadlines use monotonic time; fetched/source and alert-checkpoint timestamps remain wall UTC; injected clocks retained for deterministic tests. Backward/future cache ages cannot return fresh cached status |
| Retry/rate limits | Sources._get/read | At most2 GET attempts for eligible transient faults; one bounded1s/short429 wait; cancellation checked before retry; long numeric Retry-After no longer shortened to1h; date handling retained |
| Units | weather_units.normalize used by Sources, serious and legacy check/hazards | Explicit°F→°C metadata without mutating original payload; unsupported declared temperature units refuse; source defaults assumed°C only when absent; other unit systems are not generalized |
| Time/rules | weather_watch._moment/when/hazards | ISO Z/offset conversion into caller's aware timezone, fixed-offset local day IDs; missing daily entries and nonfinite hourly values skipped; no DST-aware timezone-database migration |
| Alert dedupe | Realtime.tick→save_seen; WeatherWatch.announce→_save/_load | Optional model_hazard_cooldown_seconds (default0, range0–86400) suppresses repeated modelled weather/air kinds per coordinate hash; off by default because distinct/escalating events may be hidden. Legacy per-day severity escalation preserved; corrupted/failed checkpoint stops notification, atomic replacement before callback |
| Restart | durable weather-alerts.json, existing realtime-alerts.json | Real owned child crash after checkpoint before callback completion, restart refuses same ID; at-most-once intent can lose notifications, no power-loss/fsync or hostile-filesystem guarantee |
| Empty/offline | Sources failure envelopes and stale cached data; WeatherWatch.summary | Two failed read attempts preserve stale cached payload/old fetched_at; absent forecast no longer produces “No bad weather expected” |
| Resource/lifecycle | existing idle Realtime worker/reader and weather watch | No new service/dependency; Start/Stop/bootstrap/launcher/recovery source unchanged. Existing reader CPU/RAM gates retained, full pressure/live acceptance incomplete |

- **JRV-26-002 BLOCKED:** Opt-in per-area suppression fixture passes; default cadence is preserved because a broad cooldown could hide a distinct or escalating hazard. Semantic event identity is not implemented.
- **JRV-26-005 BLOCKED:** Weather/air source-age and clock-rollback assertions passed; all82 source-time formats/reference cadences do not have a complete observation-freshness policy.
- **JRV-26-012 BLOCKED:** Provider records and labelled fallbacks stay distinct; no explicit disagreement/consensus comparison layer or quality oracle.
- **JRV-26-015 BLOCKED:** Malformed primary JSON, partial daily arrays and absent fields tested; complete typed schemas for all82 adapters, legacy weather, XML/SSE/WS combinations remain unproved.
- **JRV-26-021 BLOCKED:** No complete fake-secret/Groq/telemetry/public-cache/log oracle; legacy weather summaries can enter local memory and feed excerpts can enter local model context.
- **JRV-26-024 BLOCKED:** Cache clock rollback and stale weather tested; complete location/task generation binding across an in-flight query and pending notification is absent.
- **JRV-26-025 BLOCKED:** Existing CPU/RAM reader admission regressions pass; complete simulated RAM/GPU allocation pressure plus core-command responsiveness not proved. No stress/model test performed.
- **JRV-26-026 BLOCKED:** Repeated model samples deduplicate only under the opt-in suppression policy. Complete duplicate/uncertain-outcome semantics across providers and default modelled hazards remain unproved.
- **JRV-26-027 BLOCKED:** Identical5000-field projection CPU/tracemalloc A/B measured; not five cold processes plus20 full network/reader workflows with RSS/VRAM/audio/TTFT.
- **JRV-26-030 BLOCKED:** Read retries/cancellation and owned notification checkpoint crash covered; full HTTP/SSE/WS active-worker disconnect/provenance recovery matrix incomplete.
- **JRV-26-031 BLOCKED:** Primary1MiB read cap, bounded projections/arguments have tests; legacy WeatherWatch.get JSON body is not equivalently bounded, and all oversized/deep shape combinations remain unproved.
- **JRV-26-032 BLOCKED:** Checkpoint flags/IDs and categorical failures are observable; full correlation IDs and private metadata/transcript/exception redaction remain incomplete.

[Report](../../final-report.md) · [Provider inventory](provider-inventory.json) · [Assertions](cases-and-contracts.xml) · [Diff](source.patch)
