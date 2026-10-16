"""Publish Prompt26 executed fixtures and explicitly qualified provider coverage."""
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
OUT=BASE/'artifacts/jarvis-audit';MOD=OUT/'modules/26-realtime-data';PRE=BASE/'.jarvis-runtime/jarvis-audit/module26-pre'
common.MOD=MOD
read,sha,write,stats=common.read,common.sha,common.write,common.stats
GATES={
2:'Opt-in per-area suppression fixture passes; default cadence is preserved because a broad cooldown could hide a distinct or escalating hazard. Semantic event identity is not implemented.',
5:'Weather/air source-age and clock-rollback assertions passed; all82 source-time formats/reference cadences do not have a complete observation-freshness policy.',
12:'Provider records and labelled fallbacks stay distinct; no explicit disagreement/consensus comparison layer or quality oracle.',
15:'Malformed primary JSON, partial daily arrays and absent fields tested; complete typed schemas for all82 adapters, legacy weather, XML/SSE/WS combinations remain unproved.',
21:'No complete fake-secret/Groq/telemetry/public-cache/log oracle; legacy weather summaries can enter local memory and feed excerpts can enter local model context.',
24:'Cache clock rollback and stale weather tested; complete location/task generation binding across an in-flight query and pending notification is absent.',
25:'Existing CPU/RAM reader admission regressions pass; complete simulated RAM/GPU allocation pressure plus core-command responsiveness not proved. No stress/model test performed.',
26:'Repeated model samples deduplicate only under the opt-in suppression policy. Complete duplicate/uncertain-outcome semantics across providers and default modelled hazards remain unproved.',
27:'Identical5000-field projection CPU/tracemalloc A/B measured; not five cold processes plus20 full network/reader workflows with RSS/VRAM/audio/TTFT.',
30:'Read retries/cancellation and owned notification checkpoint crash covered; full HTTP/SSE/WS active-worker disconnect/provenance recovery matrix incomplete.',
31:'Primary1MiB read cap, bounded projections/arguments have tests; legacy WeatherWatch.get JSON body is not equivalently bounded, and all oversized/deep shape combinations remain unproved.',
32:'Checkpoint flags/IDs and categorical failures are observable; full correlation IDs and private metadata/transcript/exception redaction remain incomplete.'}


def marker(path,text):
    value=path.read_text(encoding='utf-8');value=re.sub(r'\n<!-- prompt26-audit -->.*?<!-- /prompt26-audit -->\n','',value,flags=re.S)
    first,rest=value.split('\n',1);path.write_text(first+'\n\n<!-- prompt26-audit -->\n'+text+'\n<!-- /prompt26-audit -->\n'+rest,encoding='utf-8')


def main():
    from scripts.verification import audit_catalog
    mainxml=MOD/'focused-main-final.xml'
    if not mainxml.exists():mainxml.write_bytes((MOD/'cases-and-contracts.xml').read_bytes())
    combined=ET.Element('testsuites',name='Prompt26 executed focused tests and independent catalog qualification')
    for p in (mainxml,MOD/'catalog-supplements.xml'):combined.extend(list(ET.parse(p).getroot()))
    ET.ElementTree(combined).write(MOD/'cases-and-contracts.xml',encoding='utf-8',xml_declaration=True)
    baseline,target,full=(stats(n) for n in ('baseline.xml','cases-and-contracts.xml','full-regression.xml'))
    assert baseline['FAIL']==target['FAIL']==full['FAIL']==0 and target['PASS']==127
    frozen=read(MOD/'full-start-source-hashes.json');assert all(sha(BASE/p)==h for p,h in frozen.items())
    bench,env,ready=(read(MOD/n) for n in ('benchmark-summary.json','environment.json','readiness.json'))
    assert bench['equivalent'] and bench['real_external_actions']==0 and ready['status']=='ready'
    modules=read(OUT/'module-map.json')
    modules[25].update(sources=['jarvis/realtime.py','jarvis/realtime_sources.py','jarvis/realtime_catalog.py','jarvis/weather_watch.py','jarvis/weather_units.py','docs/realtime-data.md'],
      test_candidates=['tests/test_realtime_audit.py','scripts/verification/test_realtime_audit.py','tests/test_realtime.py','tests/test_memory_weather.py'],
      status='PARTIAL',reason='20 catalog fixture PASS/12 BLOCKED;82 registered endpoints constructed, not82 live integrations')
    (OUT/'module-map.json').write_text(json.dumps(modules,indent=2)+'\n')
    with redirect_stdout(io.StringIO()):audit_catalog.reconcile()
    catalog=[json.loads(s) for s in (OUT/'test-results.jsonl').read_text(encoding='utf-8').splitlines()]
    cases=[r for r in catalog if r['id'].startswith('JRV-26-')]
    assert Counter(r['status'] for r in cases)=={'PASS':20,'BLOCKED':12}
    assert {int(r['id'][-3:]) for r in cases if r['status']=='BLOCKED'}==set(GATES)
    write('tests.jsonl','\n'.join(json.dumps(r,ensure_ascii=False) for r in cases));summary=read(OUT/'summary.json')
    write('remaining-case-ids.txt','\n'.join(f'JRV-26-{n:03}' for n in GATES))
    gates='\n'.join(f'- **JRV-26-{n:03} BLOCKED:** {s}' for n,s in GATES.items())
    scope=('Authored HTTP/WS responses and clocks, isolated temporary journals, fake alert sinks, five small fixture threads x20 rounds, '
      'and an owned child exiting23 after notification intent persisted. No live feed, geolocation, credential read/setup, real speech/notification, '
      'account write, OS setting change, install or heavyweight model/GPU workload. Existing full-suite browser/process fixtures stay isolated. '
      'No visible UI layout change or new screenshot; historical artwork/attribution is preserved.')
    matrix='''| Claim | Actual source/registration | Executed evidence and scope |
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
| Resource/lifecycle | existing idle Realtime worker/reader and weather watch | No new service/dependency; Start/Stop/bootstrap/launcher/recovery source unchanged. Existing reader CPU/RAM gates retained, full pressure/live acceptance incomplete |'''
    metrics=f"For a 5,000-key projection, warm p50/p95 changed from {bench['before']['p50_ms']:.5f}/{bench['before']['p95_ms']:.5f} ms to {bench['after']['p50_ms']:.5f}/{bench['after']['p95_ms']:.5f} ms; temporary Python peak changed from {bench['before']['peak_python_bytes']} to {bench['after']['peak_python_bytes']} bytes, with identical first 40 fields."
    write('inventory.md','# Prompt26 realtime audit — 2026-10-16 IST\n\n**PARTIAL:20 fixture catalog PASS/12 BLOCKED.**\n\n'+scope+'\n\n'+matrix+'\n\n'+gates+'\n\n[Report](../../final-report.md) · [Provider inventory](provider-inventory.json) · [Assertions](cases-and-contracts.xml) · [Diff](source.patch)')
    write('failures.md','# Reproduction and remaining flaws\n\nBaseline70 PASS. Actual new reproduction8 FAIL/32 explicit blockers: failed/damaged legacy checkpoint, backward-clock fresh-cache reuse, Fahrenheit heat false positive, ISO Z/local-day formatting, unavailable forecast quiet claim, short daily arrays and a retry after cancellation. '
      'First neighbors78 PASS/32 skips; expanded neighbors97 PASS/19 skips. A Unicode fixture initially selected the English-only dictionary adapter; corrected to the registered Unicode-capable Wikipedia URI. '
      'Pre-flag full regression3005 PASS/98 skips/0 FAIL in571.51s is preserved as full-before-cooldown-flag.xml/log. Broad modelled-hazard suppression was then made opt-in because it can hide distinct/escalating events. '
      'Final focused127 PASS/11 explicit skips; separate executed qualification blocks full all-provider freshness, yielding12 catalog blockers. No fixture test skip is a live-service pass.\n\n'+gates)
    compatibility='''# Compatibility and official review — 2026-10-16 IST

Installed requests2.34.2 and websocket-client1.9.2 match current [Requests PyPI](https://pypi.org/project/requests/) and [websocket-client PyPI](https://pypi.org/project/websocket-client/) listings. [Requests notes](https://requests.readthedocs.io/en/latest/community/updates/) date2.34.2 to2026-05-14 (header typing adjustment). [WebSocket1.9.2 notes](https://github.com/websocket-client/websocket-client/releases/tag/v1.9.2),2026-08-31, repair close/run_forever concurrency. No package install; implementation fixes retained. Python3.10.6/psutil7.2.2 unchanged, no new dependency.

[Open-Meteo forecast contract](https://open-meteo.com/en/docs), checked2026-10-16, documents Celsius default/Fahrenheit option, current/hourly/daily units, timezone auto and a fixed utc_offset_seconds throughout a response; DST transitions inside the forecast range are not resolved automatically. [Free API terms/pricing](https://open-meteo.com/en/pricing) list non-commercial use,600/minute and10,000/day, without an uptime guarantee. Existing300s weather cadence is retained; aggregate shared-IP quota/adaptive provider budgets remain unproved. Unit/offset behavior is fixture validation, not current forecast validation.

[RFC9110 Retry-After](https://www.rfc-editor.org/rfc/rfc9110.html#name-retry-after),2022-06, permits delay seconds or an HTTP date. Long cooldowns are scheduled rather than actively slept. Cancellation checks fence the second GET; socket reads still have existing bounded waits. No ETag/Last-Modified conditional GET, new circuit-breaker framework or all-provider schema migration added.

Firecrawl retrieved only public generic documentation/package metadata. The82 provider official URLs/setup requirements are preserved in provider-inventory.json; these are endpoint-registration/fixture evidence, not82 day-of-run upstream availability/terms/credentials validations. No personal IP, coordinates, query, credentials, feed subscription, safety advisory or model inference was sent live. Use official local warning services for real safety decisions; this audit is software-fixture QA.
'''
    write('compatibility.md',compatibility)
    decisions=metrics+' Replacing whole-dictionary materialization with an islice of40 entries retains identical projection order/content and reduces temporary work. No global private-query cache. '
    decisions+=('Five initial samples/version are not cold process starts; no HTTP, model, RSS/VRAM, TTFT or audible-alert latency claim. '
      'Extra normalization and checkpoint validation are correctness costs, not benchmarked end-to-end speed gains. Unsupported declared temperature units refuse data; absent units assume the known Open-Meteo Celsius default. '
      'The broad modelled-hazard cooldown candidate was restricted to opt-in, default0, to preserve default alert cadence. If enabled (up to86400s), it can suppress distinct same-kind hazards or escalation inside that window; old alert keys may allow one initial notification when enabling it. '
      'Legacy severity escalation is still separate. Persist-before-notify may lose an alert on crash; it must not automatically replay. Runtime journals are trusted local files, not adversarial-process or power-loss containment.\n\n')
    write('rollback.md','# Rollback\n\nDirty audit/12-tool-registry at commit9bf5528e6d490fc3bbe92d0c62bcffae6c0946b6 preserved. '
      'Clean HEAD worktree would omit inherited audited fixes; scoped preimages are in .jarvis-runtime/jarvis-audit/module26-pre. '
      'Review source.patch and source-hashes.json; restore only matched module26 hunks, preserving user/later changes. New files in files-changed.json. '
      'No commit/reset/install or personal config change. Keep existing notification checkpoints; do not clear them/replay alerts to test rollback. '
      'Older code lacks optional weather-model suppression and damaged-file refusal, so pause monitoring while reviewing any rollback. Re-run focused/readiness after rollback; no live rollback trial.')
    write('commands.md','''# Executed commands

From app/, .venv/Scripts/python.exe:
- `-m pytest tests/test_realtime.py tests/test_memory_weather.py -q --junitxml=artifacts/jarvis-audit/modules/26-realtime-data/baseline.xml`
- `-m pytest tests/test_realtime_audit.py -q --junitxml=artifacts/jarvis-audit/modules/26-realtime-data/reproduction.xml`
- Combined realtime/weather subsets in neighbors.xml and neighbors-iteration2.xml.
- `-m pytest tests/test_realtime_audit.py tests/test_realtime.py tests/test_memory_weather.py tests/test_audit_result_accounting.py -q --junitxml=artifacts/jarvis-audit/modules/26-realtime-data/cases-and-contracts.xml` (preserved main in focused-main-final.xml)
- `-m pytest scripts/verification/test_realtime_audit.py -q --junitxml=artifacts/jarvis-audit/modules/26-realtime-data/catalog-supplements.xml`
- `scripts/verification/verify_realtime_data_audit.py`
- Freeze390 runtime/tests SHA256 using verify_whatsapp_audit.freeze with OUT set to modules/26-realtime-data.
- `-m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/26-realtime-data/full-regression.xml` (full-regression.log)
- `-m jarvis.launcher --check` (readiness.json)
- `scripts/verification/report_realtime_data_audit.py`; `scripts/verification/verify_realtime_data_artifacts.py`
Outside-sandbox fixture execution supports temporary atomic files, owned child crash and existing isolated process/browser checks; no live feeds, geolocation, speech or notifications. Supplement is independent, not part of full tests-directory count.
''')
    short=(f'**Realtime/weather audit — 2026-10-16 IST:** Monotonic read cadence, explicit temperature units/source age, timezone/day handling and fail-closed notification checkpoints added. Modelled-hazard suppression is opt-in (default 0); default cadence is preserved. '
      f'**Prompt 26: 20 fixture PASS / 12 BLOCKED**; full regression **{full["PASS"]:,} PASS / {full["SKIPPED"]} skips / 0 failures**, launcher **ready**. '
      '82 registered endpoints constructed with fixtures; no live API, geolocation or alert trial. All-provider freshness/schema/privacy/resource/trace contracts remain incomplete.')
    for path,link in [(BASE/'README.md','artifacts/jarvis-audit/modules/26-realtime-data/inventory.md'),(BASE.parent/'README.md','app/artifacts/jarvis-audit/modules/26-realtime-data/inventory.md'),
                      (BASE/'docs/realtime-data.md','../artifacts/jarvis-audit/modules/26-realtime-data/inventory.md'),(BASE/'docs/system-map.md','../artifacts/jarvis-audit/modules/26-realtime-data/inventory.md')]:
        marker(path,short+'\n[Evidence, limitations and rollback]('+link+').')
    guide=BASE/'docs/realtime-data.md';text=guide.read_text(encoding='utf-8')
    text=text.replace('subscribe to paid plans or substitute another provider without configuration.',
      'subscribe to paid plans. Built-in read fallbacks name the actual provider and primary failure; they are not consensus checks.')
    text=text.replace('Five services require a configured `realtime.endpoints` entry:',
      'Endpoint overrides are available through `realtime.endpoints` for:')
    text=text.replace('The first four require your own\nserver; GBFS requires a public feed',
      'SearXNG, RSSHub and OpenTripPlanner require your own\nserver; OSRM has a public demo default, and GBFS requires a public feed')
    text=text.replace('Their adapters are available, but no endpoint or dataset is invented.',
      'Their adapters are registered; OSRM has a public demo default in the current source, while the other listed services need explicit setup. This is not live availability proof.')
    text=re.sub(r'\n## Current reliability boundaries — 2026-10-16 IST\n.*\Z','',text,flags=re.S)
    text+='\n## Current reliability boundaries — 2026-10-16 IST\n\n'
    text+=('Weather/air source-age checks use current timestamps and the published offset; they do not validate every provider freshness SLA. Temperature°F is converted to°C with explicit metadata before weather summaries/thresholds. '
      'ISO offsets and Z are handled in the caller timezone; Open-Meteo fixed-offset responses are not DST-aware across transitions. '
      'Optional `realtime.model_hazard_cooldown_seconds` accepts integers 0–86400 and defaults to 0 (off), preserving current alert cadence. If enabled, it suppresses repeated modelled weather/air hazard kinds per coordinate hash; distinct same-kind events or escalation may be hidden. This is not a semantic event tracker. No personal configuration was edited. '
      'The separate legacy weather watcher retains per-day severity escalation, uses atomic checkpoints and refuses notification after corrupt/failed storage. Persist-before-notify can lose an alert at crash time, but must not replay an uncertain notification. '
      'Unknown/damaged checkpoints require review, not deletion. No ETag/conditional-request layer or complete all-provider circuit-breaker/schema migration was added.\n')
    guide.write_text(text,encoding='utf-8')
    pairs=[];patches=[];changed=[]
    for old in sorted(PRE.iterdir()):
        if not old.is_file():continue
        rel='../README.md' if old.name=='root-README.md' else old.name.replace('__','/');now=BASE/rel
        pairs.append(dict(path=rel,before=sha(old),after=sha(now)));changed.append(rel)
        patches.extend(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),now.read_text(encoding='utf-8').splitlines(True),fromfile='before/'+rel,tofile='after/'+rel))
    for rel in ['jarvis/weather_units.py','tests/test_realtime_audit.py','scripts/verification/test_realtime_audit.py','scripts/verification/verify_realtime_data_audit.py','scripts/verification/report_realtime_data_audit.py','scripts/verification/verify_realtime_data_artifacts.py']:
        changed.append(rel);patches.extend(difflib.unified_diff([], (BASE/rel).read_text(encoding='utf-8').splitlines(True),fromfile='/dev/null',tofile='after/'+rel))
    write('source.patch',''.join(patches));write('source-hashes.json',json.dumps(pairs,indent=2));write('files-changed.json',json.dumps([dict(path=p,sha256=sha(BASE/p)) for p in changed],indent=2))
    fixes=('Retained correctness fixes:\n\n'
      '- Use monotonic provider deadlines and reject backward/future cache ages; respect long Retry-After values.\n'
      '- Check cancellation before retrying a GET and preserve cancelled status after a read interruption.\n'
      '- Convert explicitly declared Fahrenheit temperatures before weather thresholds/summaries, retaining conversion metadata and original input.\n'
      '- Attach weather/air observation age; handle ISO offsets, local-day rollover and short daily arrays.\n'
      '- Refuse notification after corrupt or failed weather checkpoints; atomically persist intent before callback and refuse uncertain replay.\n'
      '- Report an unavailable forecast instead of claiming quiet weather.\n'
      '- Keep broad modelled-hazard suppression opt-in; default alert cadence is unchanged. Semantic dedupe remains incomplete.\n\n')
    write('changes.md','# Changes/keep/revert\n\n'+fixes+decisions+'\n'.join('- `'+p+'`' for p in changed)+'\n\nGenerated module/global artifacts in generated-files.json; diff is against module26 preimages, preserving inherited changes.')
    write('full-regression-skip-reasons.json',json.dumps([dict(node=n.get('classname','')+'::'+n.get('name',''),reason=n.find('skipped').get('message','')) for n in ET.parse(MOD/'full-regression.xml').iter('testcase') if n.find('skipped') is not None],indent=2))
    table='| Module/evidence | Status | PASS | BLOCKED | NOT RUN |\n| --- | --- | ---: | ---: | ---: |\n'
    for m in modules:
        counts=Counter(r['status'] for r in catalog if int(r['id'][4:6])==m['number']);label=f"{m['number']:02}-{m['module']}";link=f'modules/{label}/inventory.md'
        if (OUT/link).is_file():label=f'[{label}]({link})'
        table+=f"| {label} | {m['status']} | {counts['PASS']} | {counts['BLOCKED']} | {counts['NOT RUN']} |\n"
    report=f'''# Jarvis audit — Prompt26, 2026-10-16 IST

**PARTIAL: 20 realtime catalog fixture PASS / 12 BLOCKED. No production/live-feed acceptance.**

Commit `9bf5528e6d490fc3bbe92d0c62bcffae6c0946b6`, preserved dirty branch `audit/12-tool-registry`, canonical `app/`. Python {env['python'].split()[0]}, {env['platform']}, RAM {env['ram_bytes']} bytes; target RTX 3050 Laptop 4 GB from earlier census, no new GPU workload. [Environment](modules/26-realtime-data/environment.json).

{scope}

## Source-map and registration evidence

{matrix}

## Executed results and measurements

Baseline: {baseline['PASS']} PASS / {baseline['FAIL']} FAIL in {baseline['seconds']:.3f}s. Focused main: 127 PASS / 11 BLOCKED skips; an independent executed freshness qualification adds 1 BLOCKED. Aggregated assertions: {target['PASS']} PASS / {target['SKIPPED']} explicit skips / 0 FAIL. Full tests-directory: **{full['PASS']} PASS / {full['SKIPPED']} skips / 0 FAIL in {full['seconds']:.3f}s**; durations here are JUnit suite times, with console wall time retained in the log. The independent supplement is additional. Launcher dependency/configuration readiness: **{ready['status']}**; optional Groq was not live checked. This does not certify current provider data, credentials, service uptime or real warning delivery.

{metrics} [Raw samples](modules/26-realtime-data/benchmarks.csv). Keep islice projection, no query retention/cache side effect. No complete cold/network/model/RSS/VRAM speed claim.

All {len(frozen)} frozen runtime/test files unchanged during full run. One existing COM-threading warning is retained. [Manifest](modules/26-realtime-data/full-start-source-hashes.json), [full output](modules/26-realtime-data/full-regression.log), [XML](modules/26-realtime-data/full-regression.xml), [skip reasons](modules/26-realtime-data/full-regression-skip-reasons.json), [reproduction/fixes](modules/26-realtime-data/failures.md), [commands](modules/26-realtime-data/commands.md), [changed files](modules/26-realtime-data/files-changed.json), [diff](modules/26-realtime-data/source.patch), [upstream URLs/dates](modules/26-realtime-data/compatibility.md), [retrieval metadata](modules/26-realtime-data/upstream-checks.json), [rollback](modules/26-realtime-data/rollback.md).

## Exact 1,184-case accounting

**{json.dumps(summary['catalog_counts'])}**. Every module26 case has executed assertions or an explicit executed blocker. Narrower weather-age tests do not certify all-provider freshness. Prior modules retain their dated evidence/metrics.

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

Modelled-hazard cooldown is opt-in (default0, maximum86400s), a suppression policy rather than official event identity. If enabled, it can suppress a distinct hazard or escalation and old-format keys can allow one initial notification. Default cadence is preserved; no personal configuration was edited. Persist-before-notify can lose notifications. Legacy weather requests and all82 schemas are not uniformly bounded/typed. Trusted local atomic files are not a hostile-filesystem or power-loss proof. These gaps prevent a production guarantee; consult official services for real safety decisions. No private/live meteorological judgment was made here.

## Resume

Next incomplete module26 case **JRV-26-002**; global oldest unresolved **{summary['next_case']}**; next untouched module **27/JRV-27-001**. [Exact module IDs](modules/26-realtime-data/remaining-case-ids.txt), [global IDs](remaining-case-ids.txt). Resume with semantic modelled-hazard event identity/escalation and per-provider observation/reference freshness policies with recorded stale fixtures, then disagreement/schema/privacy/location-generation/resource/trace gates. Follow commands.md, freeze sources, run full/readiness and reconcile/verify. Separate approval is still required for real notifications/account writes/installs. [Previous module25 report](final-report-before-module26.md) preserves earlier evidence.
'''
    (OUT/'final-report.md').write_text(report,encoding='utf-8')
    generated={p.relative_to(BASE).as_posix() for p in MOD.iterdir() if p.is_file()}
    generated.update((OUT/n).relative_to(BASE).as_posix() for n in ('final-report.md','final-report-before-module26.md','module-map.json','test-results.jsonl','executed-tests.jsonl','summary.json','remaining-case-ids.txt'))
    generated.update((MOD/n).relative_to(BASE).as_posix() for n in ('generated-files.json','artifact-verification.json'))
    write('generated-files.json',json.dumps(sorted(generated),indent=2))
    print(json.dumps(dict(module26=Counter(r['status'] for r in cases),full=full,global_catalog=summary['catalog_counts']),indent=2))


if __name__=='__main__':main()
