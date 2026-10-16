# Changes and keep/revert decisions

Retained fixes:

- Validate booleans/radius/poll cadence; location denial fences lookup, cache summary and alerts.
- Filter old/unknown primary flight positions and stop treating empty samples as proof of quiet skies.
- Require clarification for similarly ranked distant primary place names; retain declared fallback limitations.
- Restrict new Toronto/Ontario camera-pack URLs to exact HTTPS agency origins and remove raw Ontario error bodies.
- Guard cancelled opening/readback and local JSON read size/time; keep generic errors categorical.
- Persist notification intent under a lock before callback; refuse notification after corrupt/failed storage and uncertain restart.
- Reject distant latitudes before exact great-circle math, retaining unrounded boundary decisions.

For 5,010 authored points, warm p50/p95 changed from 11.04285/11.21980 ms to 4.41580/4.47420 ms; peak temporary Python allocation 304 → 304 bytes. Exact accepted coordinates/distances are identical. Keep the revised latitude prefilter. A first untraced single sample looked slower; repeated traced candidate-1 results were only slightly faster with greater temporary allocation. Candidate-1 samples are preserved. Validation was moved after cheap latitude rejection where safe, producing the retained result. Both versions then use exact distance; no approximate longitude box, antimeridian regression, model load or spatial-index dependency. Five initial iterations are not cold processes; no network/browser/audio/RSS/VRAM latency claim. Freshness refusal can hide unknown-age aircraft; API unavailability and incomplete coverage must stay visible. Persist-before-callback can lose an alert, and the six-hour key suppression is not semantic event/escalation tracking. Default radius stays 40 km; other hazard alert radii remain documented separate policies.

- `docs/gods-eye.md`
- `docs/system-map.md`
- `jarvis/gods_eye.py`
- `jarvis/gods_eye_cameras.py`
- `README.md`
- `../README.md`
- `scripts/verification/audit_catalog.py`
- `tests/test_audit_result_accounting.py`
- `tests/test_gods_eye.py`
- `tests/test_gods_eye_audit.py`
- `scripts/verification/verify_gods_eye_audit.py`
- `scripts/verification/report_gods_eye_audit.py`
- `scripts/verification/verify_gods_eye_artifacts.py`

Generated module/global outputs are listed in generated-files.json. No commit/reset or inherited diff was erased.
