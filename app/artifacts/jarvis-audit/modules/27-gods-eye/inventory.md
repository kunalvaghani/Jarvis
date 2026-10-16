# Prompt 27 God’s Eye audit — 2026-10-16 IST

**PARTIAL: 20 catalog fixture PASS / 12 BLOCKED.**

Synthetic coordinates/flight vectors, fake clocks/transports/browser action readback and notification sinks, isolated temporary journals, five independent fixture workers × 20 rounds, and an owned child exiting 23 after durable notification intent. No live geolocation, flight/camera/area feed, public camera-frame fetch, browser GUI journey, real notification/speech, credential setup, dependency installation or GPU workload. Three reviewed existing frontend unit files run in Node, without rendering a globe. Historical screenshots/attribution remain dated 2026-10-11; no new live screenshot is claimed.

| Claim | Actual implementation/entry | Evidence and limit |
| --- | --- | --- |
| Voice globe navigation | commands.parse → gods_eye.parse_command → Actions.execute → GodsEye.show/camera → BrowserWorker gods_eye actions | Authored Delhi coordinate, fly_to_location arguments, successful fake readback/last_view; actual rendered centering remains unverified |
| Location permissions | GodsEye.location_allowed/here/poll/alerts/summary | location_enabled false refuses lookup, shared realtime.auto_location false refuses lookup unless an explicit location is configured; opt-out gates stale summaries and alerts |
| Geocoding | GodsEye.geocode → Nominatim, local /api/geocode, Open-Meteo fallback | Primary ambiguous distant near-equal names ask for state/country; fallback ambiguity/rate/cache policy remains incomplete |
| Public cameras | gods_eye_cameras.toronto/ontario → runtime pack → CCTV_SOURCES_FILE | Exact HTTPS agency origins for new pack entries; provider/license labels retained; arbitrary hosts/userinfo/nonstandard ports refused. Full bundled proxy and live source availability not proved |
| Flights and area | GodsEye.poll → /api/flights, /api/military, receiver/cyclone/fire/weather/brief/USGS/traffic | Primary flight timestamps filtered; invalid vectors skip; empty/unavailable cannot establish quiet skies. Other signal freshness/schema gaps remain |
| Radius | nearby_distance → distance → poll | Conservative latitude rejection followed by exact great-circle comparison before rounding; inclusive configured km. Default remains 40 km (about 24.85 miles); boundary fixture explicitly configures 25 miles = 40.2336 km |
| Alerts and restart | GodsEye.alert → gods-eye-alerts.json → callback/card/memory | Lock, bounded checkpoint, atomic replace before callback; corrupt/failed storage refuses notification, owned crash restart refuses uncertain replay; six-hour policy can lose/suppress events, not exactly-once delivery |
| Read faults/cancellation | GodsEye.api/show/camera/poll | Local API 1 MiB/timeout/stop guards; pre-open and post-readback cancellation; cancelled state is not a success claim. Direct geocoder/camera/USGS JSON paths remain less bounded |
| Worker lifecycle | Actions.start/close; GodsEye.start/run/close; GodsEyeView.start/close | Existing enabled/autostart/interval behavior retained; no new service, dependency, user config edit or launcher change; closed-view budget and complete disconnect recovery absent |
| Frontend | bundled aircraftNearbyPolicy, cctvFocusPolicy, cctvFocusRequest | Existing pure unit assertions executed; not WebGL, live feeds, rendering, viewport virtualization or a camera-provenance acceptance test |

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

[Report](../../final-report.md) · [Executed assertions](cases-and-contracts.xml) · [Frontend output](frontend-unit.log) · [Scoped diff](source.patch)
