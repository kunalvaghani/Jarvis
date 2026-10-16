"""Publish Prompt25 executed assertions, scoped changes, measurements and open gates."""
from collections import Counter
from contextlib import redirect_stdout
import difflib
import json
import io
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
from scripts.verification import report_whatsapp_audit as common
OUT=BASE/'artifacts/jarvis-audit';MOD=OUT/'modules/25-media';PRE=BASE/'.jarvis-runtime/jarvis-audit/module25-pre'
common.MOD=MOD
read,sha,write,stats=common.read,common.sha,common.write,common.stats
GATES={
11:'Browser ownership/process cleanup has regression coverage; actual playing-tab close with unrelated tabs retained needs an owned DOM journey.',
13:'No complete network-outage workflow proof with bounded classification, trace and no uncertain fallback across every media path.',
14:'Owned media timeout fencing has regressions; complete browser/API/WinRT timeout matrix and provenance remains incomplete.',
15:'Search API/page payload shapes, recursion, response-size and malformed metadata handling are not completely bounded or validated.',
17:'No five independent full search/play requests x20 concurrency proof; native transport/UI search ownership remains shared.',
18:'Pre-URI and post-dispatch cancellation guards tested; complete TaskState cancellation/readback contract is unproved.',
19:'No durable playback mutation checkpoint/restart protocol. Native child timeout disposal is not crash-safe replay proof.',
21:'Untrusted titles remain data locally; complete Groq/telemetry/public-cache/trace secrecy oracle is absent.',
23:'Full opposed natural-language requests through routing and planner lack a no-effect negation proof.',
24:'Exact source-ID filtering passed; full native session/row identity replacement between planning and dispatch is unproved.',
25:'No complete RAM/GPU-pressure admission and core responsiveness fixture; no heavyweight inference or device-pressure mutation performed.',
26:'Uncertain playback no longer falls back to another service, and already-playing Spotify avoids activation; durable event-ID dedupe and YouTube tab reuse across repeated events remain unproved.',
27:'Identical31-song warm CPU/tracemalloc A/B measured; five real cold processes plus20 full workflows/RSS/VRAM/audio latency not measured.',
28:'No complete privileged like/save/queue/browser flow proof against forged tool approval claims.',
30:'Owned slow-child disposal and transport fencing covered; complete active native/browser connection-loss recovery with provenance is unproved.',
32:'Cards/transcripts contain titles/artists, transport exceptions can carry details; cross-flow IDs and complete private metadata redaction unproved.'}


def marker(path,text):
    value=path.read_text(encoding='utf-8')
    value=re.sub(r'\n<!-- prompt25-audit -->.*?<!-- /prompt25-audit -->\n','',value,flags=re.S)
    first,rest=value.split('\n',1)
    path.write_text(first+'\n\n<!-- prompt25-audit -->\n'+text+'\n<!-- /prompt25-audit -->\n'+rest,encoding='utf-8')


def main():
    from scripts.verification import audit_catalog
    baseline,target,full=(stats(n) for n in ('baseline.xml','cases-and-contracts.xml','full-regression.xml'))
    assert baseline['FAIL']==target['FAIL']==full['FAIL']==0 and target['PASS']==123
    frozen=read(MOD/'full-start-source-hashes.json');assert all(sha(BASE/p)==h for p,h in frozen.items())
    bench,env,ready=(read(MOD/n) for n in ('benchmark-summary.json','environment.json','readiness.json'))
    assert bench['equivalent'] and bench['real_external_actions']==0 and ready['status']=='ready'
    modules=read(OUT/'module-map.json')
    modules[24].update(sources=['jarvis/media_player.py','jarvis/spotify.py','jarvis/media_commands.py','jarvis/actions.py',
      'jarvis/island_media.py','jarvis/browser_worker.py','jarvis/media_ui.py','docs/media-player.md'],
      test_candidates=['tests/test_media_audit.py','tests/test_media_player.py','tests/test_spotify.py','tests/test_media_routes.py','tests/test_media_process_ownership.py'],
      status='PARTIAL',reason='16 catalog fixture PASS/16 BLOCKED; no new live media/account/volume trials')
    (OUT/'module-map.json').write_text(json.dumps(modules,indent=2)+'\n')
    with redirect_stdout(io.StringIO()):
        audit_catalog.reconcile()
    catalog=[json.loads(s) for s in (OUT/'test-results.jsonl').read_text(encoding='utf-8').splitlines()]
    cases=[r for r in catalog if r['id'].startswith('JRV-25-')]
    assert Counter(r['status'] for r in cases)=={'PASS':16,'BLOCKED':16}
    assert {int(r['id'][-3:]) for r in cases if r['status']=='BLOCKED'}==set(GATES)
    write('tests.jsonl','\n'.join(json.dumps(r,ensure_ascii=False) for r in cases))
    write('remaining-case-ids.txt','\n'.join(f'JRV-25-{n:03}' for n in GATES))
    summary=read(OUT/'summary.json')
    gates='\n'.join(f'- **JRV-25-{n:03} BLOCKED:** {s}' for n,s in GATES.items())
    scope=('Only authored search results, fake UI runners/URIs/Windows sessions/audio levels, real owned child timeout cleanup and existing isolated browser/server fixtures. '
           'No real song/video playback, pause/seek/volume/device setting, tab/window activation, account like/save/queue, credential read/setup, installation or model/GPU workload. '
           'Existing rendered sample media-card artwork remains dated and attributed; no new live screenshot claimed.')
    matrix='''| Map claim | Source/entry point | Actual evidence and limitation |
| --- | --- | --- |
| Fast dispatch | media_commands/commands→Actions→media_player.resolve/play | Named service stays explicit; deterministic selection and controls use zero model calls; full speech path not tested |
| YouTube play | youtube_search→choose_youtube→owned browser play_video | Actual fixture IDs; no unrelated top fallback, close-score competing IDs require channel/version; shorts <=45s excluded; live/unknown duration may be unavailable |
| Spotify play | URI search→UIA rows→choose_spotify→_activate→spotify_now | Song rows only; ties across title/artist ask; title+artist readback exact after NFC/case/space normalization; already-playing match avoids click |
| Native transport | spotify._control→_spotify_session→GSMTC | Explicit source-ID allowlist, one session required; pause/play idempotent and read back; multiple sessions refuse; Spotify browser not treated as native |
| Volume | spotify.volume→all active output sessions | Fake Spotify.exe mixer30% readback, Chrome unchanged; alternate-output regressions present, no live device selected |
| Active target | active_service→resolve | Only playing service or last started when both playing; paused available service preferred; not generic Windows transport of arbitrary apps |
| Uncertainty | PlaybackUncertain through play_youtube/play_spotify→play | Post-dispatch/unverified playback cannot fall back to another service; no persistent event-ID or write-intent record added |
| Untrusted metadata | Windows status and cards | Titles/artist are returned as data; no model command execution; complete private transcript/cloud redaction not proved |
| Lifecycle | _on_media_thread, island_media.MediaJobs, existing browser worker | Fresh MTA and bounded cancellation, real owned-child timeout regression; no new service or dependency |
| Config | config.media.default_service | youtube default, explicit youtube/spotify only, malformed defaults/unknown previous service refused; search1–300 characters |'''
    metrics=f"31-song selection warm p50/p95 {bench['before']['p50_ms']:.5f}/{bench['before']['p95_ms']:.5f}→{bench['after']['p50_ms']:.5f}/{bench['after']['p95_ms']:.5f}ms; Python peak {bench['before']['peak_python_bytes']}→{bench['after']['peak_python_bytes']}B, identical chosen row."
    write('inventory.md','# Prompt25 media audit — 2026-10-16 IST\n\n**PARTIAL:16 catalog fixture PASS/16 BLOCKED.**\n\n'+scope+'\n\n'+matrix+'\n\n'+gates+'\n\n[Report](../../final-report.md) · [Assertions](cases-and-contracts.xml) · [Diff](source.patch)')
    write('failures.md','# Reproduction, fixes and limitations\n\n'
      'Original sandbox baseline stalled after23 assertions and was stopped by exact owned pytest process identity; no pass count inferred. '
      'Outside-sandbox baseline70 PASS. New assertions reproduced13 FAIL/5 PASS/24 explicit blockers. '
      'First neighbors142 PASS/41 skips; later153 PASS/33 skips (includes WhatsApp blockers). '
      'A test fixture initially failed because its search field included the filler word Song while production clean_query removes it; corrected before accepted focused run. '
      'The first completed full run found2 failures/2969 PASS/89 skips in543.71s: island metadata fixtures used noncanonical placeholder Spotify IDs. '
      'Both fixture IDs were changed to the known package identity while preserving original memory-stream, multiple-session and missing-metadata assertions. '
      'Follow-up island/media neighbors58 PASS/16 skips; final full regression rerun on a fresh frozen source manifest. '
      'Final focused123 PASS/16 skips. [First completed full-run failures](full-before-fixture-fix.xml) and '
      '[interrupted pre-performance run](interrupted-full-before-performance.log) are preserved separately from final full output. No real playback occurred.\n\n'
      'Fixed arbitrary YouTube fallback, ambiguous video/song choice, album-as-song fallback, Spotify substring source spoofing, loss of non-Latin query tokens, '
      'cancellation before URI dispatch, invalid service selection, title-only Spotify verification and cross-service fallback after uncertain mutation. '
      'WinRT dependency failures are categorical.\n\n'+gates)
    compatibility='''# Official compatibility review — 2026-10-16 IST

Installed PyWinRT media/control/runtime3.2.1. [PyPI media-control listing](https://pypi.org/project/winrt-Windows.Media.Control/) currently lists3.2.1 and CPython3.10 Windows wheels. [Official3.2.1 notes](https://github.com/pywinrt/pywinrt/releases/tag/v3.2.1),2025-06-06, cover per-package versioning and circular-import repair; later Python3.14 wheels uploaded2025-09-20 are not a different base release. [Microsoft GSMTC contract](https://learn.microsoft.com/en-us/uwp/api/windows.media.control.globalsystemmediatransportcontrolssession?view=winrt-28000) defines source app IDs and requested transport operations; an accepted request still needs readback. Search excerpt reviewed, no latest Windows SDK installed.

Installed pycaw20260921 is older than [PyPI20260927](https://pypi.org/project/pycaw/), uploaded2026-09-26. [Official changelog](https://github.com/AndreMiras/pycaw/blob/main/CHANGELOG.md) describes Python3.10–3.14 packaging/minimum-version changes in20260926 and wheel smoke-validation metadata synchronization in20260927. No dependency installation authorized/performed; no assertion of testing the newer wheel. Current Python3.10.6/comtypes1.4.17/psutil7.2.2 retained. Live native-volume acceptance and future upgrade validation remain open.

[YouTube search.list](https://developers.google.com/youtube/v3/docs/search/list), updated2026-10-15 UTC, now describes1 unit in its Search Queries bucket and100 calls/day, maxResults0–50, type=video for video-only search. This differs from the guide's historical100-unit calculation; documentation updated without making a live quota request. No API key/account metadata inspected. Playwright1.63.0 retained; browser package upgrade remains the earlier module14/22 release gate.

Public research used Firecrawl; no private query, title, audio, account or screen data submitted. Current installed Spotify/YouTube UI builds and signed-in/alternate-output behavior were not independently verified. No paid API requirement added.
'''
    write('compatibility.md',compatibility)
    decisions=(metrics+' Query-token reuse avoids repeated normalization, no global private-query cache. Unicode retains combining marks, ASCII uses its fast normalization route. '
      'First all-character Unicode candidate regressed p50/p95(23.03035/28.57420→27.55910/32.42570ms); ASCII fast path supersedes it. '
      'The in-progress first full run was stopped and its log/hash snapshot preserved; no completion counted. '
      'Final benchmark has20warm+5initial samples/version, not cold-process/GUI/RSS/VRAM or first-audio results. '
      'Ties and exact artist formatting can cause conservative refusals; no live latency claim. '
      'Metadata filtering does not cryptographically authenticate source processes. Search payload shape/size, durable playback recovery, private logs and generic browser mutations remain open.\n\n')
    write('rollback.md','# Rollback\n\nDirty branch audit/12-tool-registry, commit9bf5528e6d490fc3bbe92d0c62bcffae6c0946b6 preserved. '
      'A clean HEAD worktree would omit inherited fixes, so scoped preimages are in .jarvis-runtime/jarvis-audit/module25-pre. '
      'Review source.patch and hashes; restore only matched module25 hunks and preserve later/user edits. New files listed in files-changed.json. '
      'No commit/reset/install/config/profile change. Do not restart media or replay uncertain playback while rolling back; inspect fresh state first. '
      'Re-run focused assertions and launcher --check after rollback. No live rollback trial.')
    commands='''# Executed commands

From app/, .venv/Scripts/python.exe:
- `-m pytest tests/test_media_player.py tests/test_spotify.py tests/test_media_routes.py tests/test_media_process_ownership.py -q --junitxml=artifacts/jarvis-audit/modules/25-media/baseline.xml`
- `-m pytest tests/test_media_audit.py -q --junitxml=artifacts/jarvis-audit/modules/25-media/reproduction.xml`
- Neighbor subsets in neighbors.xml and neighbors-final.xml add tests/test_whatsapp.py and tests/test_whatsapp_audit.py to media/routes/Spotify assertions.
- `-m pytest tests/test_island_desk.py tests/test_media_audit.py -q --junitxml=artifacts/jarvis-audit/modules/25-media/island-neighbors.xml` after correcting two synthetic source IDs.
- `-m pytest tests/test_media_audit.py tests/test_media_player.py tests/test_spotify.py tests/test_media_routes.py tests/test_audit_result_accounting.py -q --junitxml=artifacts/jarvis-audit/modules/25-media/cases-and-contracts.xml`
- `scripts/verification/verify_media_audit.py` (before and after ASCII fix)
- Freeze388 jarvis/*.py and tests/test_*.py SHA256 using verify_whatsapp_audit.freeze with OUT set to modules/25-media.
- `-m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/25-media/full-regression.xml` (full-regression.log)
- `-m jarvis.launcher --check` (readiness.json)
- `scripts/verification/report_media_audit.py`; `scripts/verification/verify_media_artifacts.py`
Fixture commands ran outside sandbox for Windows COM/owned-child/atomic/loopback constraints. Only this audit's exact owned pytest commands were stopped during incomplete runs. No live audio/OS/account mutations used.
'''
    write('commands.md',commands)
    short=(f'**Media audit — 2026-10-16 IST:** Unrelated/ambiguous selection refuses playback; Spotify song/source/artist checks, Unicode matching and uncertain-playback fallback guards added. '
      f'**16 Prompt25 fixture PASS/16 BLOCKED**; full regression **{full["PASS"]:,} PASS/{full["SKIPPED"]} skips/0 failures**, launcher **ready**. '
      'No live playback/volume trial. Durable event/tab dedupe, full privacy/resource/recovery contracts and pycaw upgrade validation remain incomplete.')
    for path,link in [(BASE/'README.md','artifacts/jarvis-audit/modules/25-media/inventory.md'),
                      (BASE.parent/'README.md','app/artifacts/jarvis-audit/modules/25-media/inventory.md'),
                      (BASE/'docs/media-player.md','../artifacts/jarvis-audit/modules/25-media/inventory.md'),
                      (BASE/'docs/system-map.md','../artifacts/jarvis-audit/modules/25-media/inventory.md')]:
        marker(path,short+'\n[Evidence, limits and rollback]('+link+').')
    guide=BASE/'docs/media-player.md'
    text=guide.read_text(encoding='utf-8').replace('Each search costs 100 quota units (`search.list`) plus 1 (`videos.list`). The default daily quota is 10,000 units, roughly 99 searches per day. When the quota runs out Jarvis falls back to keyless search automatically. Keys are never written to `config/config.json`.',
      'Current public contract (checked2026-10-16): [search.list](https://developers.google.com/youtube/v3/docs/search/list), updated2026-10-15, lists1 unit in the Search Queries bucket and100 calls/day. This supersedes the earlier100-unit/roughly99-search calculation. Actual project quotas were not inspected. HTTP quota refusal retains the existing keyless read fallback; keys stay outside config.json.')
    text=text.replace('Starting one service pauses the other, so two songs never play at once.',
      'Starting one service attempts to pause the other as a best-effort step. Failure is currently suppressed, so overlapping playback remains possible.')
    text=text.replace('It takes the first of the top six whose title clearly matches what you said.',
      'It scores up to six eligible results and requires a clear match. Competing near-equal video IDs require a channel or version before playback; unrelated top results are not played.')
    text=text.replace('the title must match and the state must be playing.',
      'the selected title and available artist text must match after Unicode/case/whitespace normalization, and the state must be playing. An exact already-playing match avoids another Play click.')
    text=text.replace("If that service can't find the song, Jarvis tries the other one. A named service is never switched.",
      'Before playback dispatch, a search failure can try the other service. An uncertain or unverified playback result stops without switching services. A named service is never switched.')
    guide.write_text(text,encoding='utf-8')
    pairs=[];patches=[];changed=[]
    for old in sorted(PRE.iterdir()):
        if not old.is_file():
            continue
        rel='../README.md' if old.name=='root-README.md' else old.name.replace('__','/')
        now=BASE/rel;pairs.append(dict(path=rel,before=sha(old),after=sha(now)));changed.append(rel)
        patches.extend(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),now.read_text(encoding='utf-8').splitlines(True),fromfile='before/'+rel,tofile='after/'+rel))
    for rel in ['tests/test_media_audit.py','scripts/verification/verify_media_audit.py','scripts/verification/report_media_audit.py','scripts/verification/verify_media_artifacts.py']:
        changed.append(rel);patches.extend(difflib.unified_diff([], (BASE/rel).read_text(encoding='utf-8').splitlines(True),fromfile='/dev/null',tofile='after/'+rel))
    write('source.patch',''.join(patches));write('source-hashes.json',json.dumps(pairs,indent=2))
    write('files-changed.json',json.dumps([dict(path=p,sha256=sha(BASE/p)) for p in changed],indent=2))
    write('changes.md','# Keep/revert and exact changed sources\n\n'+decisions+'\n'.join('- `'+p+'`' for p in changed)+
      '\n\nGenerated module/global artifacts are enumerated in generated-files.json. Source.patch uses module25 preimages, not HEAD, preserving inherited changes.')
    write('full-regression-skip-reasons.json',json.dumps([dict(node=n.get('classname','')+'::'+n.get('name',''),reason=n.find('skipped').get('message','')) for n in ET.parse(MOD/'full-regression.xml').iter('testcase') if n.find('skipped') is not None],indent=2))
    table='| Module/evidence | Status | PASS | BLOCKED | NOT RUN |\n| --- | --- | ---: | ---: | ---: |\n'
    for m in modules:
        c=Counter(r['status'] for r in catalog if int(r['id'][4:6])==m['number']);label=f"{m['number']:02}-{m['module']}";link=f'modules/{label}/inventory.md'
        if (OUT/link).exists():label=f'[{label}]({link})'
        table+=f"| {label} | {m['status']} | {c['PASS']} | {c['BLOCKED']} | {c['NOT RUN']} |\n"
    report=f'''# Jarvis audit — Prompt25, 2026-10-16 IST

**PARTIAL:16 media catalog fixture PASS/16 BLOCKED. Not production acceptance.**

Repo commit9bf5528e6d490fc3bbe92d0c62bcffae6c0946b6, preserved dirty audit/12-tool-registry, canonical app/. Python{env['python'].split()[0]}, {env['platform']}, RAM{env['ram_bytes']}bytes; target RTX3050 Laptop4GB from earlier census, no new GPU load. [Environment](modules/25-media/environment.json).

{scope}

## Source map evidence

{matrix}

## Executed verification and measurements

Baseline{baseline['PASS']} PASS/{baseline['FAIL']} FAIL/{baseline['seconds']:.3f}s. Focused{target['PASS']} PASS/{target['SKIPPED']} explicit BLOCKED skips/0 FAIL. Full suite **{full['PASS']} PASS/{full['SKIPPED']} skips/0 FAIL in{full['seconds']:.3f}s**. Existing COM-threading warning retained. Launcher dependency/configuration readiness **{ready['status']}**, optional Groq not live checked. Native media/account/production readiness is unverified.

{metrics} Keep query reuse plus ASCII fast path; Unicode candidate's earlier regression was superseded and full verification restarted. No UI/RSS/VRAM/cold-process/audio speed claim. [Measurements](modules/25-media/benchmarks.csv), [tradeoffs](modules/25-media/changes.md).

Frozen{len(frozen)} runtime/test files unchanged throughout accepted full run. [Source hashes](modules/25-media/full-start-source-hashes.json), [full output](modules/25-media/full-regression.log), [XML](modules/25-media/full-regression.xml), [skip reasons](modules/25-media/full-regression-skip-reasons.json), [reproductions](modules/25-media/failures.md), [commands](modules/25-media/commands.md), [changed files](modules/25-media/files-changed.json), [scoped diff](modules/25-media/source.patch), [rollback](modules/25-media/rollback.md).

Official URLs/release dates and retained dependencies: [compatibility](modules/25-media/compatibility.md). Pycaw20260921 is installed, newer20260927 not installed/tested. YouTube's public quota wording updated2026-10-15 supersedes historical guide calculations. No dependency or service added, Start/Stop/bootstrap/launcher/recovery sources unchanged.

## Exact1,184-case accounting

**{json.dumps(summary['catalog_counts'])}**. Every media case either has executed assertions or an explicit executed blocker; narrower checks do not override full-case blockers. Historical module measurements remain in their evidence links.

{table}

Tier totals:
```json
{json.dumps(summary['by_tier'],indent=2)}
```
Category totals:
```json
{json.dumps(summary['by_category'],indent=2)}
```

## Unresolved contracts and release risk

{gates}

Account like/save/queue actions are distinct from playback and not newly authorized by these fixtures. Allowlisted source IDs are metadata, not a hostile-process authentication boundary. Exact artist formatting can conservatively refuse valid alternate metadata. UI state can change after observation; no atomic search/activate transaction or durable playback journal was added. Privacy/payload/ownership gaps listed above prevent a production claim.

## Resume

Next incomplete module25 case **JRV-25-011**; global oldest unresolved **{summary['next_case']}**; next untouched module **26/JRV-26-001**. [Exact media IDs](modules/25-media/remaining-case-ids.txt), [global IDs](remaining-case-ids.txt). Resume with owned playing-tab closure fixtures, then HTTP/COM fault schema and durable provenance/replay contracts. Follow commands.md, freeze before full regression, run readiness, reconcile and verify artifacts. Live playback/device/account actions require separate explicit approval. [Previous report](final-report-before-module25.md) preserves module24 and earlier evidence.
'''
    (OUT/'final-report.md').write_text(report,encoding='utf-8')
    generated={p.relative_to(BASE).as_posix() for p in MOD.iterdir() if p.is_file()}
    generated.update((OUT/n).relative_to(BASE).as_posix() for n in ('final-report.md','final-report-before-module25.md','module-map.json','test-results.jsonl','executed-tests.jsonl','summary.json','remaining-case-ids.txt'))
    generated.add((MOD/'generated-files.json').relative_to(BASE).as_posix());write('generated-files.json',json.dumps(sorted(generated),indent=2))
    print(json.dumps(dict(module25=Counter(r['status'] for r in cases),full=full,global_catalog=summary['catalog_counts']),indent=2))


if __name__=='__main__':main()
