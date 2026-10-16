# Reproductions and open contracts

Baseline: 17 passed. Eight new tests initially failed: denial still looked up location, old aircraft positions triggered, empty feed implied quiet skies, cancellation still opened the map, failed checkpoint still notified, camera pack accepted arbitrary hosts, ambiguous places silently centered, malformed config was accepted. reproduced.xml preserves actual failures.

First repair subset: 25 passed. Expanded set: 44 passed / 1 failed / 12 skips; the crash child used real time but restart used a future fixture clock. Aligning the child clock repairs that test. A shell quoting error prevented the result-classifier registration edit; its new regression correctly failed (71 passed / 1 failed / 12 skips). Corrected registration then passed. Final focused: 72 passed / 12 explicit blockers. An initial frontend output path was invalid, so that attempt did not run tests; frontend-unit.log records the corrected executed command.

The first full run was deliberately stopped before completion for an isolated benchmark and source revision; full-interrupted-for-benchmark.log is NOT a passing run. Only full-regression.xml/log after the final freeze authorize current full results.

- **JRV-27-003 BLOCKED:** Toronto/Ontario pack origins are restricted and license labels preserved. No full bundled-camera catalog/media-proxy provenance, redirect/DNS or live-frame/placeholder oracle was executed.
- **JRV-27-004 BLOCKED:** Similar-ranked distant names in the Nominatim primary response now require clarification. Fallback geocoders still choose a first result; complete ambiguity, shared rate limiting and query-cache policy remain incomplete.
- **JRV-27-009 BLOCKED:** No authoritative viewer-closed signal or configurable closed-map background budget. Existing enabled/autostart/poll interval controls are not equivalent to a closed-view lifecycle contract.
- **JRV-27-011 BLOCKED:** Primary flight position and response timestamps are filtered at 120s; military feed time and seen_pos each have a 120s window. Combined military age and cyclone/fire/weather/earthquake freshness need a common policy; no all-signal real-time guarantee.
- **JRV-27-015 BLOCKED:** Malformed/deep local API JSON is refused; partial flight vectors skip safely. Full typed schemas across military, cyclone, fire, weather, quake, geocoder and camera transports remain incomplete.
- **JRV-27-021 BLOCKED:** Location opt-outs gate lookup/alerts/summary, and a raw Ontario error body no longer leaks. No complete fake-secret/cloud/Groq/public-cache oracle; place queries still reach public geocoders, location/cache and alert text persist locally.
- **JRV-27-024 BLOCKED:** Pre-action/readback cancellation and late location-denial guards pass. Full task/view/location generation binding is absent; enabled_layers updates before browser acknowledgement and camera actions can retain stale view state.
- **JRV-27-025 BLOCKED:** No complete simulated renderer GPU allocation failure and RAM-pressure/core-command responsiveness matrix; no GPU load or stress test was performed.
- **JRV-27-027 BLOCKED:** Identical geographic projection A/B covers 20 warm and 5 initial iterations per version. Not five cold processes/full browser journeys with RSS/VRAM/audio/TTFT or real flight-feed latency.
- **JRV-27-030 BLOCKED:** Local read connection faults and notification crash checkpoints are covered. Full browser/Vite/feed worker disconnect recovery with task provenance remains incomplete.
- **JRV-27-031 BLOCKED:** Local God’s Eye API reads now cap JSON at 1 MiB and catch deep JSON. Geocoding, camera packs and USGS direct JSON paths lack equivalent uniform bounds/schema budgets.
- **JRV-27-032 BLOCKED:** Categorical worker/explain errors reduce raw-detail leakage and journals identify notification intent. Full cross-flow correlation, private transcript/readback and source-field redaction are not implemented.
