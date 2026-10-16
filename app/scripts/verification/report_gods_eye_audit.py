"""Publish executed Prompt 27 evidence without treating partial fixtures as live acceptance."""
from collections import Counter
from contextlib import redirect_stdout
import difflib
import io
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
from scripts.verification import report_whatsapp_audit as common
OUT=BASE/'artifacts/jarvis-audit';MOD=OUT/'modules/27-gods-eye';PRE=BASE/'.jarvis-runtime/jarvis-audit/module27-pre'
common.MOD=MOD
read,sha,write,stats=common.read,common.sha,common.write,common.stats
GATES={
3:'Toronto/Ontario pack origins are restricted and license labels preserved. No full bundled-camera catalog/media-proxy provenance, redirect/DNS or live-frame/placeholder oracle was executed.',
4:'Similar-ranked distant names in the Nominatim primary response now require clarification. Fallback geocoders still choose a first result; complete ambiguity, shared rate limiting and query-cache policy remain incomplete.',
9:'No authoritative viewer-closed signal or configurable closed-map background budget. Existing enabled/autostart/poll interval controls are not equivalent to a closed-view lifecycle contract.',
11:'Primary flight position and response timestamps are filtered at 120s; military feed time and seen_pos each have a 120s window. Combined military age and cyclone/fire/weather/earthquake freshness need a common policy; no all-signal real-time guarantee.',
15:'Malformed/deep local API JSON is refused; partial flight vectors skip safely. Full typed schemas across military, cyclone, fire, weather, quake, geocoder and camera transports remain incomplete.',
21:'Location opt-outs gate lookup/alerts/summary, and a raw Ontario error body no longer leaks. No complete fake-secret/cloud/Groq/public-cache oracle; place queries still reach public geocoders, location/cache and alert text persist locally.',
24:'Pre-action/readback cancellation and late location-denial guards pass. Full task/view/location generation binding is absent; enabled_layers updates before browser acknowledgement and camera actions can retain stale view state.',
25:'No complete simulated renderer GPU allocation failure and RAM-pressure/core-command responsiveness matrix; no GPU load or stress test was performed.',
27:'Identical geographic projection A/B covers 20 warm and 5 initial iterations per version. Not five cold processes/full browser journeys with RSS/VRAM/audio/TTFT or real flight-feed latency.',
30:'Local read connection faults and notification crash checkpoints are covered. Full browser/Vite/feed worker disconnect recovery with task provenance remains incomplete.',
31:'Local God’s Eye API reads now cap JSON at 1 MiB and catch deep JSON. Geocoding, camera packs and USGS direct JSON paths lack equivalent uniform bounds/schema budgets.',
32:'Categorical worker/explain errors reduce raw-detail leakage and journals identify notification intent. Full cross-flow correlation, private transcript/readback and source-field redaction are not implemented.'}


def marker(path,text):
    value=path.read_text(encoding='utf-8');value=re.sub(r'\n<!-- prompt27-audit -->.*?<!-- /prompt27-audit -->\n','',value,flags=re.S)
    first,rest=value.split('\n',1)
    path.write_text(first+'\n\n<!-- prompt27-audit -->\n'+text+'\n<!-- /prompt27-audit -->\n'+rest,encoding='utf-8')


def main():
    from scripts.verification import audit_catalog
    baseline,target,full=(stats(n) for n in ('baseline.xml','cases-and-contracts.xml','full-regression.xml'))
    assert baseline['PASS']==17 and target['PASS']==72 and target['SKIPPED']==12
    assert baseline['FAIL']==target['FAIL']==full['FAIL']==0
    frozen=read(MOD/'full-start-source-hashes.json');assert all(sha(BASE/p)==h for p,h in frozen.items())
    bench,env,ready=(read(MOD/n) for n in ('benchmark-summary.json','environment.json','readiness.json'))
    assert bench['equivalent'] and bench['real_external_actions']==0 and ready['status']=='ready'
    frontend=(MOD/'frontend-unit.log').read_text(encoding='utf-8-sig')
    assert re.search(r'(?:#|ℹ) fail 0',frontend),frontend[-1200:]
    frontpass=int(re.search(r'(?:#|ℹ) pass (\d+)',frontend)[1])
    modules=read(OUT/'module-map.json')
    modules[26].update(sources=['jarvis/gods_eye.py','jarvis/gods_eye_cameras.py','jarvis/gods_eye_view.py','docs/gods-eye.md','integrations/gods-eye-view-src/gods-eye-view-main'],
        test_candidates=['tests/test_gods_eye_audit.py','tests/test_gods_eye.py','tests/test_gods_eye_view.py','tests/test_gods_eye_cameras.py'],
        status='PARTIAL',reason='20 catalog fixture PASS / 12 incomplete contracts; no live globe/camera/feed acceptance')
    (OUT/'module-map.json').write_text(json.dumps(modules,indent=2)+'\n')
    with redirect_stdout(io.StringIO()):audit_catalog.reconcile()
    catalog=[json.loads(s) for s in (OUT/'test-results.jsonl').read_text(encoding='utf-8').splitlines()]
    cases=[r for r in catalog if r['id'].startswith('JRV-27-')]
    assert len(cases)==32 and Counter(r['status'] for r in cases)=={'PASS':20,'BLOCKED':12}
    assert {int(r['id'][-3:]) for r in cases if r['status']=='BLOCKED'}==set(GATES)
    write('tests.jsonl','\n'.join(json.dumps(r,ensure_ascii=False) for r in cases))
    write('remaining-case-ids.txt','\n'.join(f'JRV-27-{n:03}' for n in GATES));summary=read(OUT/'summary.json')
    gates='\n'.join(f'- **JRV-27-{n:03} BLOCKED:** {s}' for n,s in GATES.items())
    scope=('Synthetic coordinates/flight vectors, fake clocks/transports/browser action readback and notification sinks, isolated temporary journals, '
        'five independent fixture workers × 20 rounds, and an owned child exiting 23 after durable notification intent. '
        'No live geolocation, flight/camera/area feed, public camera-frame fetch, browser GUI journey, real notification/speech, credential setup, dependency installation or GPU workload. '
        'Three reviewed existing frontend unit files run in Node, without rendering a globe. Historical screenshots/attribution remain dated 2026-10-11; no new live screenshot is claimed.')
    matrix='''| Claim | Actual implementation/entry | Evidence and limit |
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
| Frontend | bundled aircraftNearbyPolicy, cctvFocusPolicy, cctvFocusRequest | Existing pure unit assertions executed; not WebGL, live feeds, rendering, viewport virtualization or a camera-provenance acceptance test |'''
    metrics=(f"For {bench['points']:,} authored points, warm p50/p95 changed from {bench['before']['p50_ms']:.5f}/{bench['before']['p95_ms']:.5f} ms "
        f"to {bench['after']['p50_ms']:.5f}/{bench['after']['p95_ms']:.5f} ms; peak temporary Python allocation "
        f"{bench['before']['peak_python_bytes']} → {bench['after']['peak_python_bytes']} bytes. Exact accepted coordinates/distances are identical.")
    write('inventory.md','# Prompt 27 God’s Eye audit — 2026-10-16 IST\n\n**PARTIAL: 20 catalog fixture PASS / 12 BLOCKED.**\n\n'+scope+'\n\n'+matrix+'\n\n'+gates+'\n\n[Report](../../final-report.md) · [Executed assertions](cases-and-contracts.xml) · [Frontend output](frontend-unit.log) · [Scoped diff](source.patch)')
    write('failures.md','# Reproductions and open contracts\n\nBaseline: 17 passed. Eight new tests initially failed: denial still looked up location, old aircraft positions triggered, empty feed implied quiet skies, cancellation still opened the map, failed checkpoint still notified, camera pack accepted arbitrary hosts, ambiguous places silently centered, malformed config was accepted. reproduced.xml preserves actual failures.\n\n'
        'First repair subset: 25 passed. Expanded set: 44 passed / 1 failed / 12 skips; the crash child used real time but restart used a future fixture clock. Aligning the child clock repairs that test. A shell quoting error prevented the result-classifier registration edit; its new regression correctly failed (71 passed / 1 failed / 12 skips). Corrected registration then passed. Final focused: 72 passed / 12 explicit blockers. An initial frontend output path was invalid, so that attempt did not run tests; frontend-unit.log records the corrected executed command.\n\n'
        'The first full run was deliberately stopped before completion for an isolated benchmark and source revision; full-interrupted-for-benchmark.log is NOT a passing run. Only full-regression.xml/log after the final freeze authorize current full results.\n\n'+gates)
    write('compatibility.md','''# Official upstream review — 2026-10-16 IST

Bundled God’s Eye package is 0.2.1, commit 591f299d11f38a612629a274463196d57ae3862e dated 2026-10-10, with a local update receipt dated 2026-10-11. [Official v0.2.1 release](https://github.com/bilawalsidhu/gods-eye-view/releases/tag/v0.2.1), published 2026-10-03, documents origin/Host checks, cost-bearing proxy throttles and security hardening. It matches the package release series, but main has many commits since the tag; neither latest-main parity nor all security fixes is certified. No source swap, npm install or application update ran.

Node v24.14.0 satisfies the bundled engine range. Installed Cesium 1.138.0 and Vite 6.4.3 are retained. [Cesium 1.146](https://github.com/CesiumGS/cesium/releases/tag/1.146), dated 2026-10-01, adds package organization changes; [Vite 8.3.4](https://github.com/vitejs/vite/releases/tag/v8.3.4), dated 2026-10-08, is newer than the bundled Vite major. No compatibility/security/build validation of those upgrades was executed, and no newer-version-equals-safe claim is made. Installed Python requests 2.34.2 remains unchanged. Dependency migration and full frontend production acceptance are open work.

[OpenSky REST/state-vector contract](https://openskynetwork.github.io/opensky-api/rest.html) distinguishes position update and last contact Unix timestamps; the integration now uses actual position age rather than fetch time alone. The 120-second guard is a local conservative policy, not a provider SLA or live latency measurement. ADS-B coverage, receiver gaps and public feed outages do not establish absence of aircraft or cause of a sound.

[Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/), checked today, requires at most one request per second, application identification, attribution and caching. The existing independent God's Eye geocoder lacks a complete shared cadence/cache implementation; ambiguity repair does not certify full policy compliance. Do not run bulk geocoding. No live geocode query was made in this audit.

Firecrawl retrieved public official docs/release metadata only; upstream-checks.json records URLs and cache provenance. Camera entries retain agency labels and license text, but this is not legal permission or live coverage validation for every bundled camera. No key/account setup, network camera access or private surveillance bypass occurred.
''')
    fixes='''Retained fixes:

- Validate booleans/radius/poll cadence; location denial fences lookup, cache summary and alerts.
- Filter old/unknown primary flight positions and stop treating empty samples as proof of quiet skies.
- Require clarification for similarly ranked distant primary place names; retain declared fallback limitations.
- Restrict new Toronto/Ontario camera-pack URLs to exact HTTPS agency origins and remove raw Ontario error bodies.
- Guard cancelled opening/readback and local JSON read size/time; keep generic errors categorical.
- Persist notification intent under a lock before callback; refuse notification after corrupt/failed storage and uncertain restart.
- Reject distant latitudes before exact great-circle math, retaining unrounded boundary decisions.

'''
    decisions=(metrics+' Keep the revised latitude prefilter. A first untraced single sample looked slower; repeated traced candidate-1 results were only slightly faster with greater temporary allocation. Candidate-1 samples are preserved. Validation was moved after cheap latitude rejection where safe, producing the retained result. '
        'Both versions then use exact distance; no approximate longitude box, antimeridian regression, model load or spatial-index dependency. Five initial iterations are not cold processes; no network/browser/audio/RSS/VRAM latency claim. '
        'Freshness refusal can hide unknown-age aircraft; API unavailability and incomplete coverage must stay visible. Persist-before-callback can lose an alert, and the six-hour key suppression is not semantic event/escalation tracking. Default radius stays 40 km; other hazard alert radii remain documented separate policies.\n\n')
    write('rollback.md','# Rollback\n\nPreserved dirty audit/12-tool-registry at commit 9bf5528e6d490fc3bbe92d0c62bcffae6c0946b6. Scoped preimages are in .jarvis-runtime/jarvis-audit/module27-pre; source.patch/source-hashes.json describe only this pass. Restore matching hunks after review, preserving inherited/user/later changes. Do not reset to HEAD or remove personal data.\n\nNo dependency, personal config or live server update occurred. Preserve gods-eye-alerts.json; do not clear it to replay uncertain notifications. Pause monitoring before rollback: old code lacks durable notification refusal, location opt-out and fresh-position guards. Re-run focused tests and readiness. No live rollback trial was performed.')
    write('commands.md','''# Commands and scope

From app/, using .venv/Scripts/python.exe:

- `-m pytest tests/test_gods_eye.py tests/test_gods_eye_view.py tests/test_gods_eye_cameras.py -q --junitxml=artifacts/jarvis-audit/modules/27-gods-eye/baseline.xml`
- `-m pytest tests/test_gods_eye_audit.py -q --junitxml=artifacts/jarvis-audit/modules/27-gods-eye/reproduced.xml`
- Repair runs in targeted-first.xml and targeted-second.xml.
- `-m pytest tests/test_gods_eye_audit.py tests/test_gods_eye.py tests/test_gods_eye_view.py tests/test_gods_eye_cameras.py tests/test_audit_result_accounting.py -q --junitxml=artifacts/jarvis-audit/modules/27-gods-eye/cases-and-contracts.xml`
- `scripts/verification/verify_gods_eye_audit.py` (paired before/after 25 iterations each; no full suite competing).
- Freeze 391 runtime/test files with verify_whatsapp_audit.freeze, OUT set to modules/27-gods-eye.
- `-m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/27-gods-eye/full-regression.xml` (full-regression.log).
- `-m jarvis.launcher --check` (readiness.json).
- `scripts/verification/report_gods_eye_audit.py`; `scripts/verification/verify_gods_eye_artifacts.py`.

From integrations/gods-eye-view-src/gods-eye-view-main: `node --test src/data/aircraftNearbyPolicy.test.mjs src/cctvFocusPolicy.test.mjs src/cctvFocusRequest.test.mjs`, output frontend-unit.log. Pure fixtures/source reads, no WebGL/GUI journey. The interrupted earlier full run is excluded. Outside-sandbox fixture runs allowed temporary atomic journal replacement, an owned child crash and existing isolated process/browser tests; no live notification or feed.
''')
    short=(f'**God’s Eye audit — 2026-10-16 IST:** Location opt-outs, primary-flight freshness, honest empty-feed answers, safer camera-pack origins, cancellation and durable notification checkpoints added. '
        f'**20 catalog fixture PASS / 12 BLOCKED**; full regression **{full["PASS"]:,} passed / {full["SKIPPED"]} skipped / 0 failures**, launcher **ready**. '
        'Closed-view budgets, complete signal freshness/privacy/schema/renderer acceptance remain incomplete. No live globe/camera/feed validation.')
    for path,link in [(BASE/'README.md','artifacts/jarvis-audit/modules/27-gods-eye/inventory.md'),(BASE.parent/'README.md','app/artifacts/jarvis-audit/modules/27-gods-eye/inventory.md'),
        (BASE/'docs/gods-eye.md','../artifacts/jarvis-audit/modules/27-gods-eye/inventory.md'),(BASE/'docs/system-map.md','../artifacts/jarvis-audit/modules/27-gods-eye/inventory.md')]:
        marker(path,short+'\n[Evidence, limitations and rollback]('+link+').')
        value=path.read_text(encoding='utf-8')
        value=value.replace('25-mile area alerts','configured-radius area alerts (40 km default)')
        value=value.replace('for 25 miles\n','within the configured radius (40 km by default)\n')
        value=value.replace('the 25-mile side-thread cache','the configured-radius side-thread cache')
        value=value.replace('40 km (25-mile) radius','40 km (about 24.85-mile) radius')
        path.write_text(value,encoding='utf-8')
    guide=BASE/'docs/gods-eye.md';text=guide.read_text(encoding='utf-8')
    text=text.replace('a 25-mile (40 km) radius','the configured radius (40 km by default)')
    text=text.replace('Watch radius (25 miles).','Watch radius in km (40 km is about 24.85 miles).')
    text=re.sub(r'\n## Audit configuration and boundaries — 2026-10-16 IST\n.*\Z','',text,flags=re.S)
    text+='\n## Audit configuration and boundaries — 2026-10-16 IST\n\n'
    text+=('`gods_eye.location_enabled` defaults to `true`; `false` prevents current-location lookup, poll, alert and summary use. The shared realtime `auto_location: false` is respected unless an explicit location is configured. No personal config was edited. '
        '`enabled`, `autostart` and `location_enabled` require booleans; `radius_km` accepts finite numbers 1–500 and `poll_seconds` 10–3600. Default 40 km is about 24.85 miles; exactly 25 miles requires 40.2336 km. Other hazard categories retain separate wider alert rules. '
        'Primary flight positions older than 120 seconds are excluded; empty/unavailable samples cannot establish clear skies or explain sirens. Other signal age/schema policies remain incomplete. '
        'Notification intent is saved atomically in `.jarvis-runtime/gods-eye-alerts.json` before callbacks, under the instance lock. Damaged/unwritable journals stop notification; do not delete them to force replay. Crash-time notifications can be lost. Six-hour suppression is a policy, not semantic event identity. '
        'New Toronto/Ontario pack entries require exact agency HTTPS origins; the full bundled camera proxy/catalog and synthetic-placeholder behavior have not been certified. The bundled renderer dependencies were not upgraded. '
        'The historical screenshots/results above remain historical. Current proof is fixture regression, selected Node unit checks and readiness, not live map centering, real feeds, camera licensing or real alerts.\n')
    guide.write_text(text,encoding='utf-8')
    pairs=[];patches=[];changed=[]
    for old in sorted(PRE.iterdir()):
        if not old.is_file():continue
        rel='../README.md' if old.name=='root-README.md' else old.name.replace('__','/');now=BASE/rel
        changed.append(rel);pairs.append(dict(path=rel,before=sha(old),after=sha(now)))
        patches.extend(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),now.read_text(encoding='utf-8').splitlines(True),fromfile='before/'+rel,tofile='after/'+rel))
    for rel in ['tests/test_gods_eye_audit.py','scripts/verification/verify_gods_eye_audit.py','scripts/verification/report_gods_eye_audit.py','scripts/verification/verify_gods_eye_artifacts.py']:
        changed.append(rel);patches.extend(difflib.unified_diff([], (BASE/rel).read_text(encoding='utf-8').splitlines(True),fromfile='/dev/null',tofile='after/'+rel))
    write('source.patch',''.join(patches));write('source-hashes.json',json.dumps(pairs,indent=2))
    write('files-changed.json',json.dumps([dict(path=p,sha256=sha(BASE/p)) for p in changed],indent=2))
    write('changes.md','# Changes and keep/revert decisions\n\n'+fixes+decisions+'\n'.join('- `'+p+'`' for p in changed)+'\n\nGenerated module/global outputs are listed in generated-files.json. No commit/reset or inherited diff was erased.')
    write('full-regression-skip-reasons.json',json.dumps([dict(node=n.get('classname','')+'::'+n.get('name',''),reason=n.find('skipped').get('message','')) for n in ET.parse(MOD/'full-regression.xml').iter('testcase') if n.find('skipped') is not None],indent=2))
    table='| Module/evidence | Status | PASS | BLOCKED | NOT RUN |\n| --- | --- | ---: | ---: | ---: |\n'
    for m in modules:
        counts=Counter(r['status'] for r in catalog if int(r['id'][4:6])==m['number']);label=f"{m['number']:02}-{m['module']}";link=f'modules/{label}/inventory.md'
        if (OUT/link).is_file():label=f'[{label}]({link})'
        table+=f"| {label} | {m['status']} | {counts['PASS']} | {counts['BLOCKED']} | {counts['NOT RUN']} |\n"
    report=f'''# Jarvis audit — Prompt 27, 2026-10-16 IST

**PARTIAL: 20 God’s Eye catalog fixture PASS / 12 BLOCKED. No production/live-feed acceptance.**

Preserved dirty branch `audit/12-tool-registry`, commit `9bf5528e6d490fc3bbe92d0c62bcffae6c0946b6`, canonical `app/`. Python {env['python'].split()[0]}, {env['platform']}, RAM {env['ram_bytes']} bytes; target RTX 3050 Laptop 4 GB from earlier census, no GPU workload. [Environment](modules/27-gods-eye/environment.json).

{scope}

## Source-map evidence

{matrix}

## Executed tests and measurements

Baseline: **17 passed**. Eight reproduced failures were fixed with regression assertions; [failure history](modules/27-gods-eye/failures.md). Final focused: **{target['PASS']} PASS / {target['SKIPPED']} explicit BLOCKED skips / 0 FAIL**. Selected Node unit subset: **{frontpass} passed / 0 failed**. Full Python tests-directory: **{full['PASS']} PASS / {full['SKIPPED']} skips / 0 FAIL in {full['seconds']:.3f}s** (JUnit suite time; console wall time in log), with one existing COM-threading warning. Launcher dependency/configuration readiness **{ready['status']}**; optional Groq not live checked. No renderer/GUI/flight-feed/camera/alert production acceptance follows from readiness.

{metrics} [Raw benchmark](modules/27-gods-eye/benchmarks.csv). Five initial iterations are not cold process starts. No browser/network/TTFT/audio/RSS/VRAM speed claim. [Keep/revert decisions](modules/27-gods-eye/changes.md).

All {len(frozen)} frozen runtime/test files unchanged during the accepted full run. [Hashes](modules/27-gods-eye/full-start-source-hashes.json), [full output](modules/27-gods-eye/full-regression.log), [XML](modules/27-gods-eye/full-regression.xml), [skip reasons](modules/27-gods-eye/full-regression-skip-reasons.json), [Node output](modules/27-gods-eye/frontend-unit.log), [commands](modules/27-gods-eye/commands.md), [changed files](modules/27-gods-eye/files-changed.json), [scoped diff](modules/27-gods-eye/source.patch), [official upstream URLs/dates](modules/27-gods-eye/compatibility.md), [retrieval metadata](modules/27-gods-eye/upstream-checks.json), [rollback](modules/27-gods-eye/rollback.md).

## Exact 1,184-case accounting

**{json.dumps(summary['catalog_counts'])}**. Every Prompt 27 case is represented by executed assertions or an explicit blocker. A narrower passed fixture cannot override an incomplete full-case contract. Prior evidence remains dated and linked.

{table}

Tier totals:
```json
{json.dumps(summary['by_tier'],indent=2)}
```
Category totals:
```json
{json.dumps(summary['by_category'],indent=2)}
```

## Remaining contracts and risk

{gates}

The camera wrapper is narrower than the full bundled proxy; published agency provenance is not blanket permission or current availability. Flight observations and fetch time differ, and all area signals lack a common complete freshness policy. The historical 40 km default is preserved rather than silently widened to 25 miles. Notifications are at-most-once intent with possible loss; six-hour suppression may hide distinct same-key events/escalation. Local journal locks/atomic replacement do not prove cross-process, hostile-filesystem or power-loss containment. Dependency major migrations, primary geocoder rate/cache compliance and full frontend production verification remain unfinished.

## Resume

Next incomplete module case **JRV-27-003**; global oldest unresolved **{summary['next_case']}**; next untouched module **28/JRV-28-001**. [Exact module IDs](modules/27-gods-eye/remaining-case-ids.txt), [global IDs](remaining-case-ids.txt). Complete camera provenance/placeholder proof and geocoding ambiguity/cadence/cache, then closed-view budget, uniform source age/schema, privacy/generation/resource/trace and browser-worker recovery. Follow commands.md, freeze source, run full/readiness and reconcile/verify. Real camera/geolocation/notification/account actions or dependency installations still need separate explicit authorization. [Previous Prompt 26 report](final-report-before-module27.md) preserves its independent evidence.
'''
    (OUT/'final-report.md').write_text(report,encoding='utf-8')
    generated={p.relative_to(BASE).as_posix() for p in MOD.iterdir() if p.is_file()}
    generated.update((OUT/n).relative_to(BASE).as_posix() for n in ('final-report.md','final-report-before-module27.md','module-map.json','test-results.jsonl','executed-tests.jsonl','summary.json','remaining-case-ids.txt'))
    generated.update((MOD/n).relative_to(BASE).as_posix() for n in ('generated-files.json','artifact-verification.json'))
    write('generated-files.json',json.dumps(sorted(generated),indent=2))
    print(json.dumps(dict(module27=Counter(r['status'] for r in cases),focused=target,full=full,frontend_pass=frontpass,global_catalog=summary['catalog_counts']),indent=2))


if __name__=='__main__':main()
