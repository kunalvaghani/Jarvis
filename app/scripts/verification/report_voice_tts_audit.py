"""Publish module05 from executed assertions; do not infer live acoustic success."""
import ast
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

BASE=Path(__file__).resolve().parents[2]
ROOT=BASE/'artifacts/jarvis-audit'
OUT=ROOT/'modules/05-voice-tts'
PRE=BASE/'.jarvis-runtime/jarvis-audit/module05-pre'
RUNTIME=('jarvis/speech.py','jarvis/f5_speech.py','jarvis/kokoro_speech.py','jarvis/runtime_health.py')
FILES=(*RUNTIME,'config/runtime_manifest.json','tests/test_voice_tts_audit.py','tests/test_f5_speech.py',
       'tests/test_natural_voice.py','tests/test_audit_result_accounting.py','tests/audit_contract_helpers.py',
       'scripts/verification/audit_catalog.py','scripts/verification/verify_voice_tts_audit.py',
       'scripts/verification/report_voice_tts_audit.py','README.md','docs/README.md','docs/f5-voice.md',
       'docs/natural-male-voice.md','docs/system-map.md')


def write(path,text):path.write_text(text,encoding='utf-8')


def read_run(name):
    tree=ET.parse(OUT/name);nodes=list(tree.iter('testcase'))
    assert nodes and not any(n.find('failure') is not None or n.find('error') is not None for n in nodes)
    skipped=[n for n in nodes if n.find('skipped') is not None]
    assert all('BLOCKED:' in n.find('skipped').get('message','') for n in skipped)
    return {'passed':len(nodes)-len(skipped),'blocked':len(skipped),
            'seconds':float(next(tree.iter('testsuite')).get('time',0))}


def main():
    full=read_run('full-regression.xml');targeted=read_run('cases-and-contracts.xml')
    assert full['blocked']==5 and targeted['blocked']==2
    for path in RUNTIME:
        assert (OUT/'full-regression.xml').stat().st_mtime >= (BASE/path).stat().st_mtime
    from scripts.verification.audit_catalog import reconcile
    reconcile()
    rows=[json.loads(s) for s in (ROOT/'test-results.jsonl').read_text(encoding='utf-8').splitlines()]
    cases=[r for r in rows if r['id'].startswith('JRV-05-')]
    counts={s:sum(r['status']==s for r in cases) for s in ('PASS','FAIL','BLOCKED','SKIPPED','NOT RUN')}
    assert len(cases)==32 and counts=={'PASS':30,'FAIL':0,'BLOCKED':2,'SKIPPED':0,'NOT RUN':0}
    for row in cases:
        row['scope']='Executed production-boundary fixtures; actual cached CUDA and CPU no-playback checks are additional evidence, not human acoustic acceptance'
    write(OUT/'tests.jsonl',''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in cases))
    write(OUT/'remaining-case-ids.txt',''.join(r['id']+'\n' for r in cases if r['status']!='PASS'))
    benchmark=json.loads((OUT/'benchmark-summary.json').read_text())
    live=json.loads((OUT/'live-worker.json').read_text());cpu=json.loads((OUT/'live-cpu-fallback.json').read_text())
    assert live['status']==cpu['status']=='PASS'
    ready=json.loads((PRE/'readiness-private.json').read_text(encoding='utf-8'))
    assert ready['status']=='ready' and not ready['missing'] and not ready['incomplete']
    write(OUT/'readiness.json',json.dumps({'date':'2026-10-15 IST','command':'python -m jarvis.launcher --check','exit_code':0,'status':ready['status'],
          'scope':ready['scope'],'service_statuses':{k:v['status'] for k,v in ready['services'].items()},'live_acoustic_acceptance':False},indent=2)+'\n')
    patch='';hashes={}
    for name in (*RUNTIME,'config/runtime_manifest.json'):
        path=BASE/name;before=PRE/path.name;assert before.is_file()
        patch+=''.join(difflib.unified_diff(before.read_text(encoding='utf-8').splitlines(True),path.read_text(encoding='utf-8').splitlines(True),fromfile='module05-pre/'+name,tofile=name))
        hashes[name]={'before':hashlib.sha256(before.read_bytes()).hexdigest(),'after':hashlib.sha256(path.read_bytes()).hexdigest(),'preimage':'Captured before module05, including earlier dirty work; diff normalizes line endings only'}
    write(OUT/'source.patch',patch);write(OUT/'source-hashes.json',json.dumps(hashes,indent=2)+'\n')
    changed=[{'path':'app/'+name,'sha256':hashlib.sha256((BASE/name).read_bytes()).hexdigest()} for name in FILES]
    changed.append({'path':'README.md','sha256':hashlib.sha256((BASE.parent/'README.md').read_bytes()).hexdigest()})
    write(OUT/'files-changed.json',json.dumps({'date':'2026-10-15 IST','scope':'Module05 scoped files; existing unrelated dirty work excluded. Shared files retain previous changes. No commit/deployment.','files':changed,
          'artifacts_directory':'app/artifacts/jarvis-audit/modules/05-voice-tts','shared_artifacts':['test-results.jsonl','summary.json','executed-tests.jsonl','module-map.json','remaining-case-ids.txt','security-findings.md','final-report.md']},indent=2)+'\n')
    module_map=json.loads((ROOT/'module-map.json').read_text())
    module_map[4].update(status='LIVE ACCEPTANCE BLOCKED',reason='30 catalog fixtures PASS; human pronunciation and shared STT/F5 contention unresolved. Real cached F5 and CPU no-playback paths passed.',catalog_counts=counts,
        sources=[*RUNTIME,'jarvis/piper_speech.py','jarvis/gpu_scheduler.py','jarvis/natural_voice.py','docs/f5-voice.md','config/config.json'],test_candidates=['tests/test_voice_tts_audit.py','tests/test_f5_speech.py','tests/test_speech.py','tests/test_natural_voice.py','tests/test_gpu_scheduler.py'])
    write(ROOT/'module-map.json',json.dumps(module_map,indent=2)+'\n')
    warm_before=benchmark['before_warm_reference_and_chunks'];warm_after=benchmark['after_warm_reference_and_chunks']
    cold_before=benchmark['before_cold_adapter_import'];cold_after=benchmark['after_cold_adapter_import']
    matrix=['| Claim | Actual source | Evidence / boundary |','| --- | --- | --- |']
    for label,path,symbol,proof in [
        ('Parent speech routing','jarvis/speech.py','Speech','Generation-bound queue, ready handshake, installed CPU fallback before text submission, no retry of failed submitted text'),
        ('F5 rendering','jarvis/f5_speech.py','render','Sequential cached-reference chunks, fixed quality settings, crossfade and post-inference cancellation'),
        ('Continuous output','jarvis/kokoro_speech.py','Player','Finite mono audio, 128-piece bound, cancellation under buffer lock and periodic playback heartbeat'),
        ('Worker protocol','jarvis/kokoro_speech.py','serve','64 requests, monotonic IDs, categorical errors, malformed-frame rejection and bounded EOF shutdown'),
        ('Hindi / final fallback','jarvis/piper_speech.py','play_reply','Existing streaming Piper path unchanged; installed component PCM synthesis verified'),
        ('Resource policy','jarvis/gpu_scheduler.py','configured','Qwen reservation only; STT and F5 are outside shared lease coordinator'),
        ('Health','jarvis/runtime_health.py','RuntimeHealth','Speech UUID/backend/queue/restart metadata; no spoken payload')]:
        tree=ast.parse((BASE/path).read_text(encoding='utf-8'))
        node=next(n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==symbol)
        matrix.append(f'| {label} | [{path}:{node.lineno}](../../../../{path}) | {proof} |')
    write(OUT/'inventory.md',f'''# Prompt05: F5-TTS / Kokoro / Piper — 2026-10-15 IST

**30 catalog PASS, 2 BLOCKED, 0 FAIL/SKIPPED/NOT RUN. Live acceptance remains blocked; this is not whole-system production certification.** All32 IDs have [executed-assertion or blocker evidence](tests.jsonl). JRV-05-004 needs a listening evaluation; JRV-05-010 lacks shared STT/F5 lease admission and controlled contention proof. Physical speaker/device churn and acoustic barge-in remain unverified beyond fixtures.

Commit `e9f6f735bc310d11e3cdecfbf95a85d96b170ec2`, branch `codex/jarvis-prove-fix-audit`; existing dirty work preserved. Windows, main/F5 Python3.10.6, Ryzen7/32GB target, RTX3050 Laptop4096MiB. GPU was idle at census; only one heavyweight GPU worker ran at a time. No account/OS mutation, sends, personal deletes, installation, model download or deployment. No new dependency/service or UI layout; no new screenshot/sample is fabricated.

## Source map and call order

The candidate `jarvis/speech_worker.py` does not exist. Actual flow: answer progress/final in main → Speech.stream/say → owned parent queue → F5 child in separate venv or installed CPU worker → renderer → Player callback → typed progress/health. Risk/Stop/ownership contracts were tested before native checks. Piper fallback follows existing English/Hindi models. F5 engine/reference/32-step quality configuration is retained.

{chr(10).join(matrix)}

## Executed checks

Existing baseline command: `.venv/Scripts/python.exe -m pytest tests/test_f5_speech.py tests/test_speech.py tests/test_natural_voice.py tests/test_answer_stream.py tests/test_gpu_scheduler.py -q --tb=short --junitxml=artifacts/jarvis-audit/modules/05-voice-tts/existing-baseline.xml`: **88 PASS in6.74s**. [Baseline](existing-baseline.xml). New adversarial baseline: **16 FAIL/1 BLOCKED in1.06s**; later interrupted-queue and missing-playback-heartbeat reproductions each failed. [Diagnosis and fixture corrections](failures.md).

Final dedicated command adds `tests/test_voice_tts_audit.py`, `test_runtime_health.py`, `test_recovery.py` and `test_audit_result_accounting.py` to the baseline modules: **{targeted['passed']} PASS / {targeted['blocked']} BLOCKED**, {targeted['seconds']:.2f}s JUnit time. [Targeted XML](cases-and-contracts.xml). Full `.venv/Scripts/python.exe -m pytest tests -q --tb=short --junitxml=artifacts/jarvis-audit/modules/05-voice-tts/full-regression.xml`: **{full['passed']} PASS / {full['blocked']} BLOCKED**, {full['seconds']:.2f}s JUnit time; one pywinauto STA COM UserWarning. Three skips belong to prior Prompt04, two to05. [Full XML](full-regression.xml). These overlapping runs are not summed.

Real `.venv/Scripts/python.exe -m scripts.verification.verify_voice_tts_audit --live`: **PASS**, one cached F5 CUDA model load; short+long ordered replies, Stop discards request3, new request4 succeeds. No speaker playback. Ready **{live['ready_seconds']:.3f}s**, first request audio **{live['first_request_audio_seconds']:.3f}s**, measured Stop acknowledgement **{live['stop_ack_seconds']:.4f}s** (rounded protocol timing, not acoustic stop). Peak Torch allocated/reserved **{live['peak_allocated_mb']:.2f}/{live['peak_reserved_mb']:.2f}MiB**. [Events/metrics](live-worker.json). Pilot remains separately labeled; it is not a pre-change native baseline.

Real `--live-cpu`: forced missing-reference options in an isolated Speech instance; installed Kokoro handled **2 replies/1 warm process**, and Piper produced **{cpu['piper_pcm_samples']} finite PCM samples**. No output stream; [evidence](live-cpu-fallback.json). This was a functional check under regression load, not a controlled latency comparison. `.venv-f5/Scripts/python.exe -m pip check`: no broken requirements; launcher `--check`: **ready**, [readiness](readiness.json). Dependency readiness is not acoustic acceptance.

## Equivalent CPU experiment

`.venv/Scripts/python.exe -m scripts.verification.verify_voice_tts_audit`: 20 alternating warm batches/build (40 requests/batch),5 cold child imports/build; same synthetic local PCM header and phrase corpus. [CSV](benchmarks.csv), [summary](benchmark-summary.json). Full chunk words/boundaries asserted; reference replacement invalidates cache. Warm P50/P95 **{warm_before['p50_ms']:.4f}/{warm_before['p95_ms']:.4f}→{warm_after['p50_ms']:.4f}/{warm_after['p95_ms']:.4f}ms**. Cold P50/P95 **{cold_before['p50_ms']:.4f}/{cold_before['p95_ms']:.4f}→{cold_after['p50_ms']:.4f}/{cold_after['p95_ms']:.4f}ms**. Keep the small metadata win; cold difference is not a demonstrated startup gain. RSS is sampled, not peak. This saves header work, not several seconds of F5 inference; no native before/after speedup, WER, listening-quality or2-second guarantee claimed.

[Exact files/decisions](changes.md), [official versions/release dates](compatibility.md), [scoped runtime patch](source.patch), [hashes](source-hashes.json), [rollback/resume](rollback.md), [remaining IDs](remaining-case-ids.txt). All prior scaffold reports are preserved in history-before-audit. Earlier02–04 results remain in [previous final report](../../final-report-before-module05.md).
''')
    write(OUT/'failures.md', '''# Reproduction, fixes and unresolved issues

- Existing suite baseline: [88 PASS](existing-baseline.xml). It did not cover the newly identified boundaries.
- [New boundary baseline](failure-baseline.xml):16 failing assertions and1 explicit acoustic blocker. Missing reference skipped speech; CUDA startup lacked CPU fallback; cancellation during text preparation queued old text; worker events leaked exception text or crashed on wrong JSON types; old-worker identity and cancellation-at-audio-enqueue guards were absent; audio shape/finiteness/duration, device-active state and playback backlog were unbounded. Several tests request a guarded API that did not exist before;16 assertions are not16 distinct field-observed bugs.
- First repair regression:60PASS/2FAIL/1BLOCKED, [XML](first-regression.xml). One fixture represented a running worker as immediate EOF without a ready frame; it now emits ready and keeps its fake pipe open. One old test required raw device error text; the privacy contract now asserts categorical failure with payload omitted. These fixture changes are not credited as extra product fixes.
- [Interruption baseline](interruption-baseline.xml): queued not-yet-playing speech survived interrupt; now queue/stream state is invalidated immediately.
- [Playback heartbeat baseline](playback-heartbeat-baseline.xml): ongoing audio emitted no progress after synthesis. A long reply could hit the watchdog while playing normally. Player now emits periodic metadata accepted by the parent.
- EOF and runtime failures never resubmit the failed payload. Worker ID high-water mark rejects replay; old process events cannot complete a new worker's request. Backend transitions wait for outstanding audio, with Stop/watchdog still effective. New native stderr is discarded rather than written with spoken/reference text to speech.log; old private logs remain untouched.

Unresolved acceptance: **JRV-05-004** requires labeled listening/pronunciation/voice-similarity evaluation. **JRV-05-010** remains BLOCKED: Qwen reservation exists but no shared STT/F5 lease gate or contention calibration exists, and the audit resource contract forbids launching two heavyweight GPU tests together. This is a known architecture/release limitation, not a passing arbitration claim. Physical device unplug/reopen, speaker underruns and acoustic interruption remain unverified. No native pre-change TTFA baseline or current WER was measured.

Final targeted/full XML are clean except explicit blockers; historical failing XML is retained as reproduction evidence and not silently described as a pass.
''')
    write(OUT/'changes.md', '''# Scoped implementation and keep/revert decisions

- `jarvis/speech.py`: ready handshake before text, startup deadline60s without Stop lock, installed pre-submission F5→Kokoro→Piper fallback; generation checks during preparation; pending interruption, backend drain, stale-process/typed-frame checks, bounded response metadata, categorical errors and Speech health UUID. Native stderr goes to DEVNULL. Runtime failed payloads are never retried; later new text/fragments may start a fresh worker.
- `jarvis/f5_speech.py`: typed reference configuration and categorical readiness;16-entry stat-keyed header-duration LRU; cache invalidation test; reject pathological words before upstream inference and malformed/oversized audio. Model, quality/reference settings and sequential crossfade algorithm remain.
- `jarvis/kokoro_speech.py`: validate/limit audio and queue, cancellation under enqueue lock, recoverable device failure, periodic playback heartbeat,64-request admission, monotonic ID non-replay, typed JSON/text and categorical errors; bounded quick-EOF drain and output cleanup. `piper_speech.py` unchanged.
- `jarvis/runtime_health.py`: existing snapshot includes safe Speech health, no new supervisor/service.
- Tests: new `test_voice_tts_audit.py`; readiness fixture in `audit_contract_helpers.py`; old F5 ready-pipe fixture and natural-voice error expectation; reviewed BLOCKED accounting fixture. Metadata/accounting and fake external transports are isolated; no real account or desktop writes.
- Harness/report: `verify_voice_tts_audit.py`, `report_voice_tts_audit.py`, `audit_catalog.py` reviewed module allowlist; READMEs, docs index/F5/Kokoro/system map, runtime manifest and audit ledgers. [Exact paths/hashes](files-changed.json).

Keep: correctness/privacy/Stop fixes and measured header-cache improvement; all final regressions passed. No model/pin/quantization/step reduction or unmeasured acoustic optimization promoted. Cold CPU metadata startup varies slightly; native first audio is still roughly5s on this fixture. Initial CPU/native pilot data is retained and not misrepresented as a pre-change GPU benchmark. No new dependency, paid API, service, generated executable ability or deployment.
''')
    write(OUT/'rollback.md', '''# Scoped rollback and deterministic continuation

Use normal Stop Jarvis before runtime rollback. Preserve current files/metadata. Review [source.patch](source.patch) and [byte hashes](source-hashes.json); captured preimages are `.jarvis-runtime/jarvis-audit/module05-pre/` and contain earlier dirty work. Restore only these reviewed hunks, not HEAD or a whole shared file. Manifest rollback removes speech_audit and restores only changed f5_speech fields; keep other module sections. Parent queue remains volatile; do not restore old speech or task queues or erase external-write uncertainty.

From app:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_voice_tts_audit.py tests/test_f5_speech.py tests/test_speech.py tests/test_natural_voice.py tests/test_runtime_health.py tests/test_answer_stream.py tests/test_recovery.py tests/test_gpu_scheduler.py tests/test_audit_result_accounting.py -q --tb=short --junitxml=artifacts/jarvis-audit/modules/05-voice-tts/cases-and-contracts.xml
.venv/Scripts/python.exe -m pytest tests -q --tb=short --junitxml=artifacts/jarvis-audit/modules/05-voice-tts/full-regression.xml
.venv/Scripts/python.exe -m jarvis.launcher --check
.venv/Scripts/python.exe -m scripts.verification.report_voice_tts_audit
```

Archive CSV/JSON/XML first before remeasurement. CPU benchmark command is `-m scripts.verification.verify_voice_tts_audit`; private preimages required. `--live` uses only cached F5 with offline flags and no playback; `--live-cpu` permits only a no-playback Kokoro child and local Piper PCM. Do not start simultaneous heavyweight models, download weights, install dependencies or open actual speakers as a test side effect.

Next module05 IDs: **JRV-05-004**, provide approved/labeled French/Hindi-name recordings and human listening rubric; **JRV-05-010**, design/test shared runtime admission with proper ownership/Stop policy and obtain a resource-safe controlled STT/F5 contention evaluation. Qwen reservation alone cannot substitute for that proof. Keep those IDs BLOCKED until actual assertions succeed. Whole-catalog next unrun module is06/JRV-06-001; prior04 acoustic blockers remain. Later modules are not completed by the full regression.

No config migration, dependency rollback, personal-file deletion or external write is necessary. Existing private logs may contain older spoken data; they were preserved and never published, not silently sanitized or erased. Shared host ability isolation and unsupported Python remain separate release issues.
''')
    summary=json.loads((ROOT/'summary.json').read_text())
    write(OUT/'scoped-report.json',json.dumps({'date':'2026-10-15 IST','status':'LIVE ACCEPTANCE BLOCKED','catalog_counts':counts,'targeted':targeted,'full':full,'native_gpu':'live-worker.json','native_cpu':'live-cpu-fallback.json','readiness':'ready','next_case':'JRV-05-004'},indent=2)+'\n')
    table='\n'.join(f"| {m['number']:02} | {m['module']} | {m['status']} |" for m in module_map)
    write(ROOT/'final-report.md',f'''# Jarvis audit through Prompt05 — 2026-10-15 IST

**Prompt05:30 catalog PASS,2 BLOCKED,0 FAIL/SKIPPED/NOT RUN. Production acceptance remains uncertified.** Full regression: **{full['passed']} PASS,5 explicit BLOCKED skips**, {full['seconds']:.2f}s JUnit time, one pywinauto STA COM threading warning. [Full XML](modules/05-voice-tts/full-regression.xml). Dedicated speech/neighbor suite: **{targeted['passed']} PASS,2 BLOCKED**, [XML](modules/05-voice-tts/cases-and-contracts.xml). Runs overlap; do not sum them.

## Environment and source proof

Commit `e9f6f735bc310d11e3cdecfbf95a85d96b170ec2`, branch `codex/jarvis-prove-fix-audit`; Windows, Python3.10.6, Ryzen7/32GB target, RTX3050 Laptop4096MiB. Existing dirty work preserved. No commit/deploy/install/model download, account send/write, personal delete or system-setting mutation. Only one heavyweight GPU model test at a time, speakers disabled. [Module05 source/config/binding matrix](modules/05-voice-tts/inventory.md), [exact files](modules/05-voice-tts/files-changed.json), [scoped patch/hashes](modules/05-voice-tts/source.patch). Candidate speech_worker.py is absent; actual parent Speech and F5/Kokoro/Piper entry points are documented.

## Repairs and retained tradeoffs

Safe F5 startup fallback now chooses installed Kokoro/Piper before any text submission; runtime submitted failures are not replayed. Generation and buffer-lock checks close Stop races, interruption clears pending replies, backend changes drain old output, and playback heartbeats prevent long-answer false stalls. Typed/bounded protocol and audio queues reject stale/malformed/duplicate work. New native diagnostics are discarded instead of recording private spoken/reference text; historical logs remain local and untouched. Header metadata cache reduces repeated WAV opens without changing quality/model/reference settings. [Failure reproductions](modules/05-voice-tts/failures.md), [changes/decisions](modules/05-voice-tts/changes.md), [rollback](modules/05-voice-tts/rollback.md).

Equivalent CPU header/chunk fixture,20 alternating warm and5 cold samples/build: warm P50/P95 **{warm_before['p50_ms']:.4f}/{warm_before['p95_ms']:.4f}→{warm_after['p50_ms']:.4f}/{warm_after['p95_ms']:.4f}ms**, cold **{cold_before['p50_ms']:.4f}/{cold_before['p95_ms']:.4f}→{cold_after['p50_ms']:.4f}/{cold_after['p95_ms']:.4f}ms**. [CSV](modules/05-voice-tts/benchmarks.csv). RSS sampled, not peak. Keep metadata gain/correctness; no cold-start or native speech speedup claimed.

Actual cached F5 CUDA: ready **{live['ready_seconds']:.3f}s**, first audio **{live['first_request_audio_seconds']:.3f}s**, peak allocated/reserved **{live['peak_allocated_mb']:.2f}/{live['peak_reserved_mb']:.2f}MiB**; ordered short/long requests, Stop and new request in one loaded worker passed. [Metrics/events](modules/05-voice-tts/live-worker.json). Actual Speech missing-reference→Kokoro:2 replies/1 warm child; separate Piper PCM:{cpu['piper_pcm_samples']} samples, [evidence](modules/05-voice-tts/live-cpu-fallback.json). No speaker/listening/WER or shared contention check. Native timing is a current component sample, not a paired pre-change improvement or2-second promise. F5 pip check passed; launcher **ready**, [readiness](modules/05-voice-tts/readiness.json).

## Catalog and enumerated modules

Full1184 unique IDs: **{summary['catalog_counts']}**. [Tier/category/run statistics](summary.json), [full case/assertion ledger](test-results.jsonl), [exact remaining IDs](remaining-case-ids.txt), [module05 cases](modules/05-voice-tts/tests.jsonl). Prior02–04:93PASS/3BLOCKED, unchanged runtime evidence; [previous final report](final-report-before-module05.md) preserves per-module baseline/metrics. Prior architecture32 fixture proofs remain. Other case IDs retain old evidence or NOT RUN; a passing unrelated regression does not certify them.

| Module | Name | Status |
| --- | --- | --- |
{table}

## Compatibility, known flaws and release risks

Official current sources checked by Firecrawl on2026-10-15: F5[1.1.22](https://github.com/SWivid/F5-TTS/releases/tag/1.1.22), released2026-07-23; Kokoro[0.6.1 publisher metadata](https://pypi.org/pypi/kokoro-onnx/json), released2026-08-19; Piper[1.8.0](https://github.com/OHF-Voice/piper1-gpl/releases/tag/v1.8.0), released2026-09-04; Torch[2.14.1 publisher metadata](https://pypi.org/pypi/torch/json), wheels2026-09-30. Installed F5/Kokoro remain1.1.21/0.4.9 with matched Torch/TorchAudio2.6.0+cu124 and Transformers4.44.2; Piper1.8.0 matches current. Newer packages were investigated, not blindly installed or claimed tested. [Version/date/source and keep rationale](modules/05-voice-tts/compatibility.md).

Module05 blockers: **JRV-05-004**, acceptable French/Hindi pronunciation/voice likeness needs a labeled human listening evaluation; **JRV-05-010**, STT/F5 lack shared lease admission and controlled contention proof. Qwen's reservation does not prove that missing gate. Physical device churn, acoustic playback/barge-in and underruns remain live-unverified. Protocol success does not imply naturalness. Main Python3.10 is[upstream EOL](https://devguide.python.org/versions/) since2026-10-01; native GIL-hang containment, host ability isolation, broader log/prose privacy and unrun integrations remain open. [Security findings](security-findings.md). No assertion establishes whole-system release safety.

## Resume and rollback

First incomplete global ID remains **JRV-04-001**; next incomplete module05 ID **JRV-05-004**; next unrun module **06/JRV-06-001**. [Module05 exact remaining IDs and commands](modules/05-voice-tts/rollback.md), [prior04 acoustic prerequisites](resume-02-04.md). Restore only scoped captured hunks, preserve dirty user work and uncertainty journals, never replay old queues. [Final source/link/accounting verification](modules/05-voice-tts/verification.json). No installation or live personal-data action was performed as an audit shortcut.
''')


if __name__=='__main__':main()
