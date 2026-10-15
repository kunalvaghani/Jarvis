"""Publish assertion-derived scope completion; retain prior reports as history."""
import argparse
import ast
from collections import Counter
import copy
import difflib
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parents[2]
OUT = BASE/'artifacts/jarvis-audit'
MODULES = {2:'02-perception-cognition',3:'03-intent-direct',4:'04-voice-stt'}
SOURCES = {
    2:['jarvis/cognition.py','jarvis/screen_awareness.py','jarvis/task_state.py','jarvis/brain.py','jarvis/tools.py','jarvis/actions.py'],
    3:['jarvis/commands.py','jarvis/intent_catalog.py','jarvis/engine.py'],
    4:['jarvis/audio.py','jarvis/whisper_backend.py','main.py','jarvis/runtime_health.py'],
}
CLAIMS = {
    2:[('Attention and persistence','jarvis/cognition.py','Cognition','Bounded priority admission, stale-window eviction, Bayesian posterior, off-tick persistence and metadata errors'),
       ('Context binding','jarvis/context_hub.py',None,'Goal and active task outside seven attention slots'),
       ('Slow sensor isolation','jarvis/screen_awareness.py','ScreenAwareness','CPU-bound Python fixture remains outside attention tick; stalled read reported after 15 seconds'),
       ('Task identity','jarvis/task_state.py','TaskState','UUID on task start, checked planner/tool metadata, stale finish rejected')],
    3:[('Deterministic routing','jarvis/commands.py','parse','Bounded string input; immutable reflex lookup before learned interpretation'),
       ('Anchored built-ins','jarvis/intent_catalog.py',None,'Compiled full-match rules and built-in precedence'),
       ('Ordered final dispatch','jarvis/engine.py','Engine','Negation, final transcripts and compound boundary punctuation'),
       ('Ambiguous latest document','jarvis/brain.py','Brain','Asks for filename/path/folder before model or file opening')],
    4:[('Capture and decode','jarvis/audio.py','Listener','Owned capture/decoder, resampling before release, duplicate utterance rejection, bounded stop'),
       ('GPU loader/settings','jarvis/whisper_backend.py','settings','Validated finite options; categorical missing GPU/library/model failure; typed mode retained'),
       ('Cleanup policy','jarvis/command_cleanup.py','CommandCleanup','Finite local choice; negation/numbers/proper nouns preserved in authored corpus'),
       ('Worker ownership','main.py','App','Stuck decoder prevents duplicate microphone restart without cancelling active task'),
       ('Health','jarvis/runtime_health.py','RuntimeHealth','Metadata trace ID/error category, no decoder exception payload')],
}


def write(path, value):
    path.write_text(value,encoding='utf-8')


def archive(path):
    if path.exists():
        destination=path.parent/'history-before-completion'/path.name
        destination.parent.mkdir(exist_ok=True)
        if not destination.exists():shutil.copy2(path,destination)


def split_targeted():
    root=ET.parse(OUT/'completion-targeted.xml')
    nodes=list(root.iter('testcase'))
    assert len(nodes)==123 and sum(n.find('skipped') is not None for n in nodes)==3
    assert not any(n.find('failure') is not None or n.find('error') is not None for n in nodes)
    for number,name in MODULES.items():
        chosen=[]
        marker={2:'test_perception_cognition_audit',3:'test_intent_direct_audit',4:'test_voice_stt_audit'}[number]
        for node in nodes:
            label=node.get('classname','')+'::'+node.get('name','')
            if f'JRV-{number:02}-' in label or f'JRV_{number:02}_' in label or marker in label:
                chosen.append(node)
            elif number==4 and 'test_stalled_decoder_blocks_restart' in label:chosen.append(node)
        assert chosen
        suite=ET.Element('testsuite',name=name,tests=str(len(chosen)),failures='0',errors='0',
                         skipped=str(sum(n.find('skipped') is not None for n in chosen)),
                         time=str(sum(float(n.get('time',0)) for n in chosen)))
        suite.extend(copy.deepcopy(n) for n in chosen)
        path=OUT/'modules'/name/'cases-and-contracts.xml';archive(path)
        ET.ElementTree(suite).write(path,encoding='utf-8',xml_declaration=True)


def scoped_patch(number):
    folder=OUT/'modules'/MODULES[number]
    patch='';hashes={}
    for name in SOURCES[number]:
        current=BASE/name
        pre=BASE/'.jarvis-runtime/jarvis-audit'/('completion-pre' if number==2 and current.name!='cognition.py' else f'module{number:02}-pre')/current.name
        # Screen/task identity preimages were captured before completion; cognition
        # and intent use their earlier module preimages, preserving dirty work.
        if pre.is_file():
            raw=pre.read_bytes();before=raw.decode('utf-8');representation='captured preimage'
        elif name=='jarvis/engine.py':
            before=current.read_text(encoding='utf-8').replace("            if not whole and index < len(clauses) - 1:\n                clause = clause.rstrip(',;').rstrip()  # punctuation before a spoken command boundary\n",'')
            raw=before.encode();representation='normalized reconstruction removing only scoped boundary lines'
        elif name=='jarvis/whisper_backend.py':
            raw=subprocess.check_output(['git','show','HEAD:app/'+name],cwd=BASE)
            before=raw.decode('utf-8');representation='HEAD preimage; file clean at start of voice pass'
        elif name=='jarvis/runtime_health.py':
            addition="        from .audio import Listener\n        if isinstance(listener,Listener):\n            result['audio']['listener']=listener.health()\n"
            after=current.read_text(encoding='utf-8');assert addition in after
            before=after.replace(addition,'');raw=before.encode()
            representation='normalized reconstruction removing only three scoped telemetry lines'
        else:
            # runtime_health already contained earlier dirty work. Avoid falsely
            # presenting HEAD as a clean preimage of this task.
            hashes[name]={'after':hashlib.sha256(current.read_bytes()).hexdigest(),'before_representation':'no captured preimage; inspect completion telemetry change in working diff'}
            continue
        # Preserve byte hashes but compare normalized line endings; otherwise a
        # CRLF preimage versus read_text's LF would falsely replace whole files.
        patch+=''.join(difflib.unified_diff(before.replace('\r\n','\n').splitlines(True),current.read_text(encoding='utf-8').splitlines(True),fromfile='captured-before/'+name,tofile=name))
        hashes[name]={'before':hashlib.sha256(raw).hexdigest(),'after':hashlib.sha256(current.read_bytes()).hexdigest(),'before_representation':representation}
    archive(folder/'source.patch');archive(folder/'source-hashes.json')
    write(folder/'source.patch',patch);write(folder/'source-hashes.json',json.dumps(hashes,indent=2)+'\n')


def matrix(number):
    rows=['| Claim | Source | Proven scope |','| --- | --- | --- |']
    for claim,path,symbol,scope in CLAIMS[number]:
        source=BASE/path;assert source.is_file()
        tree=ast.parse(source.read_text(encoding='utf-8'))
        node=next((n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==symbol),None)
        line=node.lineno if node else 1
        rows.append(f'| {claim} | [{path}:{line}](../../../../{path}) | {scope} |')
    return '\n'.join(rows)


def publish(final=False):
    split_targeted()
    from scripts.verification.audit_catalog import reconcile
    reconcile()
    rows=[json.loads(s) for s in (OUT/'test-results.jsonl').read_text(encoding='utf-8').splitlines()]
    selected=[r for r in rows if int(r['id'].split('-')[1]) in MODULES]
    assert len(selected)==96 and Counter(r['status'] for r in selected)=={'PASS':93,'BLOCKED':3}
    module_map=json.loads((OUT/'module-map.json').read_text())
    full_summary=None
    if final:
        full=ET.parse(OUT/'completion-full-regression.xml');nodes=list(full.iter('testcase'))
        assert nodes and not any(n.find('failure') is not None or n.find('error') is not None for n in nodes)
        skipped=[n for n in nodes if n.find('skipped') is not None]
        assert len(skipped)==3 and all('BLOCKED:' in n.find('skipped').get('message','') for n in skipped)
        for number in SOURCES:
            for path in SOURCES[number]:assert (OUT/'completion-full-regression.xml').stat().st_mtime >= (BASE/path).stat().st_mtime
        full_summary={'passed':len(nodes)-len(skipped),'blocked':len(skipped),'seconds':float(next(full.iter('testsuite')).get('time',0)),
                      'warning':'One pywinauto STA COM threading-mode UserWarning in test_media_routes; no failure'}
        write(OUT/'completion-regression-summary.json',json.dumps(full_summary,indent=2)+'\n')
    for number,name in MODULES.items():
        folder=OUT/'modules'/name
        cases=[r for r in rows if r['id'].startswith(f'JRV-{number:02}-')]
        counts={s:sum(r['status']==s for r in cases) for s in ('PASS','FAIL','BLOCKED','SKIPPED','NOT RUN')}
        status='FIXTURE COMPLETE' if number!=4 else 'LIVE ACOUSTIC VALIDATION BLOCKED'
        module_map[number-1].update(status=status,reason=f'2026-10-15 executed fixture ledger: {counts}; live integrations remain separate',catalog_counts=counts)
        for filename in ('inventory.md','tests.jsonl','changes.md','failures.md','rollback.md','remaining-case-ids.txt','scoped-report.json'):archive(folder/filename)
        write(folder/'tests.jsonl',''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in cases))
        write(folder/'remaining-case-ids.txt',''.join(r['id']+'\n' for r in cases if r['status']!='PASS'))
        benchmark=json.loads((folder/'benchmark-summary.json').read_text())
        regression=f"Full repository regression: **{full_summary['passed']} PASS, {full_summary['blocked']} acoustic BLOCKED, {full_summary['seconds']:.2f} seconds**." if final else 'Full regression is still running; no completion claim yet.'
        write(folder/'inventory.md',f'''# Prompt {number:02} — 2026-10-15 IST

**{status}**. Catalog counts: **{counts}**. Every one of this module's 32 IDs is retained in [tests.jsonl](tests.jsonl). PASS means the concrete offline assertions listed per ID executed; it does not certify arbitrary inputs or real integrations. [Pending live IDs](remaining-case-ids.txt).

Commit `e9f6f735bc310d11e3cdecfbf95a85d96b170ec2`, branch `codex/jarvis-prove-fix-audit`, dirty work preserved. Windows, Python 3.10.6, Ryzen 7/32 GB target, RTX 3050 Laptop 4096 MiB; observed 2700 MiB occupied, 1396 MiB free. No heavyweight model run, service installation or external mutation.

{matrix(number)}

Dependency order: startup/configuration and risk/recovery contracts → bounded perception and task identity → deterministic intent/clarification → capture/decoder lifecycle and cleanup → shared ToolRegistry/Actions and full regression. Prompt 04 work already underway was preserved while completing the clarified 02–04 scope. Tools, approvals, independent questions and existing execution workers remain authoritative.

Executed command from app: `.venv/Scripts/python.exe -m pytest tests/test_audit_completion_cases.py tests/test_voice_stt_audit.py tests/test_intent_direct_audit.py tests/test_perception_cognition_audit.py -q --tb=short --junitxml=artifacts/jarvis-audit/completion-targeted.xml`: **120 PASS, 3 explicitly BLOCKED skips in 12.95 seconds**. [Module assertion subset](cases-and-contracts.xml), [complete targeted output](../../completion-targeted.xml). {regression} [Full XML](../../completion-full-regression.xml).

Before/after measurements: [raw CSV](benchmarks-completion-20261015.csv), [summary](benchmark-summary.json). Scope: {benchmark['scope']} Benchmarks preceded the full regression and used the same fixture/machine per build. No audio quality/first-token/first-audio or peak VRAM inference is possible from these CPU fixtures. RSS is sampled, not peak. Zero real sends, launches, typing, account writes, file deletions, system changes or learned-script executions. Native code that holds the GIL cannot be forcibly contained by these Python threads; live model quality remains unverified.

[Baseline failures](failures.md), [files and decisions](changes.md), [official compatibility](compatibility.md), [rollback](rollback.md). Prior module reports/XML are retained in `history-before-completion/`; their older partial status is historical. Earlier 02/03 raw benchmark CSVs were overwritten before archival; historical headline summaries survive in prior final reports, but original raw samples cannot be reconstructed. Current repeated measurements are archived explicitly.
''')
        failures={
            2:'''Original baseline: **9 PASS, 7 FAIL in 6.09 seconds**, [XML](baseline.xml): stale screen attention, four invalid-option variants, missing error diagnostics and unexecuted proposals counted as success. Existing privacy-neighbor expectation was corrected to categorical disk-error reporting. Heap candidate P95 worsened 0.023488→0.027676 ms and was reverted, [candidate CSV](benchmarks-heap-candidate.csv).

Completion identity baseline: **2 FAIL in 1.40 seconds**, [XML](identity-baseline.xml). Wrong model task metadata was accepted and an older task finish could affect a replacement task. Task UUID checks, identity-bound cancellation and owned finish IDs repair these paths; matching regression assertions now pass. Busy Python parser, malformed deep history, fault/recovery and private tool traces are exercised by completion cases. This does not isolate native code that holds the GIL.

An earlier unscoped pytest collected vendored repositories (2335 collection errors); it is not a Jarvis pass. Final validation explicitly uses pytest tests. Original raw 02 CSV was overwritten before archival; prior report headline measurements remain historical, fresh current CSV is archived.''',
            3:'''Original baseline **6 PASS, 8 FAIL in 4.51 seconds**, [XML](baseline.xml). Five implementation failures: latest spreadsheet matched app open; sound-down-notch and pause-current phrases rejected; separator comma contaminated Notepad target; corrected tab-close phrase rejected. Three fixture errors (desktop mocks and volume signature) were corrected separately, without credit as product fixes. A later compound expectation now accepts established compose/verbatim policy while checking order/content/target.

Completion adds an actual Actions→Brain ambiguity assertion for latest spreadsheet: paused checkpoint plus pending filename/path question, zero model/file opening. The initial stale-choice completion fixture called _clarify rather than actual _resolve_reply; corrected fixture checks the production reply boundary. Parser type/size/depth limits, concurrency, negation, learned shadow attempts, Stop, uncertainty and stale choices now pass. Original raw 03 CSV was overwritten before archival; preserved current samples are a new measurement, not reconstructed history.''',
            4:'''Initial production-source baseline **5 PASS, 8 FAIL in 7.92 seconds**, [XML](baseline.xml). Failures: release combined a 16 kHz buffer with a 48 kHz final block (6400 versus3200 samples); five invalid-setting variants were accepted; raw capture exception payload was reported; decoder join was unbounded. These are repaired without replacing the recognizer or changing endpoint defaults.

Duplicate-job baseline **1 FAIL in 1.20 seconds**, [XML](duplicate-baseline.xml): repeated final utterance ID dispatched three commands instead of two explicit requests. A monotonic finalized-ID guard rejects the duplicate and preserves the new utterance ID. Stop drains pending buffers; stalled decoder remains owned so recovery cannot create a duplicate or cancel an unrelated active task.

Three acoustic assertions remain BLOCKED, not failed or silently omitted: JRV-04-001 quiet-room command/WER/latency; JRV-04-002 background-TV false activation; JRV-04-003 long-pause endpoint intent. No labeled corpora and only1396MiB observed free GPU headroom. Fake transcript/numeric/proper-noun checks prove cleanup policy, not actual recognition of arbitrary speech.''',
        }
        write(folder/'failures.md',f'# Reproduction and diagnosis — 2026-10-15 IST\n\n{failures[number]}\n\nFinal executed assertions: [module XML](cases-and-contracts.xml), [full regression](../../completion-full-regression.xml). Historical intermediate failures are retained and not counted as final unresolved implementation failures.\n')
        file_list='\n'.join('- `'+p+'`' for p in SOURCES[number])
        write(folder/'changes.md',f'''# Scoped changes — 2026-10-15 IST

Runtime files (exact patches/preimage provenance in [source.patch](source.patch) and [source-hashes.json](source-hashes.json)):

{file_list}

Module 02 adds bounded perception/diagnostics and stale-window fixes, deep-history recovery, escaped stats, stalled sensor health and task identity binding in Brain/Tools/Actions/TaskState. Module 03 adds four anchored phrases, safe compound punctuation, parser type/size/depth validation and latest-document clarification in the shared Brain path. Module 04 repairs release-buffer resampling, duplicate dispatch and shutdown ownership; validates settings and exposes categorical health. These shared files intentionally cross module boundaries.

Tests: `tests/test_perception_cognition_audit.py`, `tests/test_intent_direct_audit.py`, `tests/test_voice_stt_audit.py`, `tests/test_audit_completion_cases.py`, `tests/audit_contract_helpers.py`, `tests/test_audit_result_accounting.py`. Existing cognition/routing privacy tests are reused as executable helpers, never merely referenced as a pass.

Harness/report: `scripts/verification/verify_perception_cognition.py`, `verify_intent_direct.py`, `verify_voice_stt_audit.py`, `audit_catalog.py`, `report_completion_02_04.py`; prior module report scripts are historical partial reporters and must not overwrite current completion reports. Documents: root/app README, docs index, cognitive architecture, natural language, fast conversation, push-to-write and system map; runtime_manifest and audit artifacts. [Complete scoped list](../../completion-files.json).

No new model/package/dependency/service; no real external action, installation or deployment. Capture/job ownership copies remain; only redundant padding copy removed. Correctness fixes retained despite small capture/cold-cognition timing increases. Existing dirty work preserved, no commit created.
''')
        write(folder/'rollback.md',f'''# Scoped rollback — module {number:02}

Use normal Stop Jarvis before a reviewed runtime rollback. Preserve current changed files and metadata first. Apply only this module's reviewed hunks in [source.patch](source.patch) against [source hashes](source-hashes.json); do not use git reset/checkout HEAD over the existing dirty workspace.

Captured preimages: `.jarvis-runtime/jarvis-audit/module02-pre`, `module03-pre`, `module04-pre` and `completion-pre`. Completion-pre contains the prior Brain/Tools/Actions/TaskState/ScreenAwareness, including earlier user work. Engine and runtime-health preimages are labeled normalized reconstructions of scoped insertions; Whisper backend uses clean-at-voice-start HEAD provenance. Do not blindly restore whole shared files: later module fixes overlap. Runtime manifest preimage is in module04-pre/runtime_manifest.json; preserve other sections when reverting voice_input_audit.

Task UUID is additive; older checkpoints fall back to started_at identity. Do not restore/replay pending action queues, remove uncertainty journals or treat interrupted writes as safe retries. No dependency downgrade or personal-file deletion is necessary. Keep approval/privacy/Stop guards even when disabling cognition (`cognition.enabled=false`) or optional cleanup (`command_cleanup.enabled=false`).

After any rollback, rerun the scope command in inventory.md, full `pytest tests -q --tb=short`, and `python -m jarvis.launcher --check`. Re-measure before claiming timing gains. Current patch is preserved without deployment or forced process restarts.
''')
        scoped_patch(number)
        write(folder/'scoped-report.json',json.dumps({'date':'2026-10-15 IST','status':status,'catalog_counts':counts,'full_regression':full_summary},indent=2)+'\n')
    write(OUT/'module-map.json',json.dumps(module_map,indent=2)+'\n')
    if final:
        archive(OUT/'final-report.md')
        stats=json.loads((OUT/'summary.json').read_text())
        table='\n'.join(f"| {m['number']:02} | {m['module']} | {m['status']} |" for m in module_map)
        metrics=[]
        keys={2:('warm_tick','cold_startup'),3:('warm_per_phrase','cold_import_and_batch'),4:('warm_capture','cold_fixture_startup')}
        for number,name in MODULES.items():
            b=json.loads((OUT/'modules'/name/'benchmark-summary.json').read_text())
            for key in keys[number]:metrics.append(f"| {number:02} {key} | {b['before_'+key]['p50_ms']:.4f} / {b['before_'+key]['p95_ms']:.4f} | {b['after_'+key]['p50_ms']:.4f} / {b['after_'+key]['p95_ms']:.4f} |")
        write(OUT/'final-report.md',f'''# Jarvis Prompts 02–04 audit — 2026-10-15 IST

**Accessible audit work for Prompts 02–04 is complete: 93 catalog cases PASS, 3 acoustic cases BLOCKED, 0 FAIL, 0 SKIPPED and 0 NOT RUN in this 96-case scope. Whole-system production readiness remains uncertified.** Every PASS links to executed fixture assertions; no live acoustic or account acceptance is inferred.

Full `pytest tests -q --tb=short --junitxml=artifacts/jarvis-audit/completion-full-regression.xml`: **{full_summary['passed']} PASS, 3 BLOCKED acoustic skips, {full_summary['seconds']:.2f} seconds**. One pywinauto STA COM threading-mode UserWarning, no test failure. [Full output](completion-full-regression.xml). Targeted: **120 PASS/3 BLOCKED in 12.95 seconds**, [output](completion-targeted.xml). Runs overlap and must not be summed. Accounting tests exercise failed variants and reviewed BLOCKED classification in the full run.

## Checkout and evidence

Commit `e9f6f735bc310d11e3cdecfbf95a85d96b170ec2`, branch `codex/jarvis-prove-fix-audit`, Windows, Python 3.10.6, RTX 3050 Laptop 4096 MiB, 32 GB target RAM. GPU census: 2700 MiB used, 1396 MiB free; no new GPU workload. Existing dirty changes preserved; no commit, publish, deployment, model/package installation or external write. Readiness check and soak results are linked below and remain separate from live acceptance.

[02 source matrix and tests](modules/02-perception-cognition/inventory.md), [03 source matrix and tests](modules/03-intent-direct/inventory.md), [04 source matrix and tests](modules/04-voice-stt/inventory.md). Prompt 04's inferred voice_input.py is a text-policy helper; capture actually lives in audio.py/whisper_backend.py/main.py. Architecture docs are claims mapped to these entry points, not runtime proof.

## Repairs and decisions

02: retained stale-window/race fixes, finite typed admission and off-tick persistence; added deep-history recovery, escaped Unicode stats, stalled-sensor health, task UUID binding and stale-result/finish rejection. CPU-bound Python sensor test leaves cognition responsive; hard native-hang isolation is unresolved. Prior heap ranking optimization was reverted after regression.

03: retained four anchored intent rules and compound punctuation repair; bounded parser input to 100,000 characters and converted recursion/Unicode errors to categorical validation failures. Latest/most-recent document requests ask for filename/path/folder before model or opening. Stable reflexes, aliases and learned-command precedence are asserted with no model/network calls.

04: resample release audio before final enqueue; reject duplicate final utterance IDs while accepting explicit second requests; validate settings before hooks/capture; stop drains owned queues, decoder join bounded to two seconds. Stalled decoder retains ownership, preventing duplicate microphone creation. Generic typed fallback and categorical metadata/UUID health avoid raw exception payloads. Removed one redundant VAD pad copy; inference model, quantization and endpoint defaults unchanged.

## Equivalent paired CPU measurements

All values in milliseconds, P50 / P95. Twenty alternating warm samples and five fresh-process cold samples per build on this machine; CPU fixtures only. No peak-memory, GPU speed, WER, TTFT or first-audio claim. [02 CSV](modules/02-perception-cognition/benchmarks-completion-20261015.csv), [03 CSV](modules/03-intent-direct/benchmarks-completion-20261015.csv), [04 CSV](modules/04-voice-stt/benchmarks-completion-20261015.csv).

| Module/fixture | Before | After |
| --- | --- | --- |
{chr(10).join(metrics)}

02 scheduling median 250 ms in both builds; sampled max 266 → 265 ms. Cold cognition initialization increased; no universal speedup claimed. 03 warm routing benefit is corpus-specific and includes formerly rejected routes. 04 capture timing increased slightly; correctness takes priority: expected 200 ms at 16 kHz now yields **3200 samples**, previously6400. Retain correctness fix; do not market speech latency improvement. Prior 02/03 raw samples were overwritten before archival; historical summaries remain in archived reports. Fresh CSVs are preserved.

## Exact catalog accounting and modules

All 1,184 unique IDs retained: **{stats['catalog_counts']}**. [Tier/category/run totals](summary.json), [all assertions and case scope](test-results.jsonl), [exact remaining IDs](remaining-case-ids.txt). Cases outside 02–04 retain previous evidence or NOT RUN; they are not silently promoted by unrelated regression tests. Module 01's earlier fixture coverage remains historical.

| Module | Name | Status |
| --- | --- | --- |
{table}

## Compatibility, risks and next validation

Firecrawl checked official current sources on 2026-10-15: [faster-whisper1.2.1](https://github.com/SYSTRAN/faster-whisper/releases) released2025-10-31; [CTranslate2v4.8.3](https://github.com/OpenNMT/CTranslate2/releases/tag/v4.8.3) released2026-10-13; installed1.2.1/4.6.0. New CTranslate2 includes a CUDA TopK edge-case fix; live native compatibility on this4GB system is unverified, so no blind upgrade. [Runtime prerequisites](https://github.com/SYSTRAN/faster-whisper) require CUDA12/cuDNN9 for recent releases. [Official Python status](https://devguide.python.org/versions/) lists3.10 EOL2026-10-01. [02 sources](modules/02-perception-cognition/compatibility.md), [03 sources](modules/03-intent-direct/compatibility.md), [04 installed/release matrix](modules/04-voice-stt/compatibility.md).

Next incomplete IDs: **JRV-04-001**, **JRV-04-002**, **JRV-04-003**. Provide dedicated GPU headroom and labeled quiet-room, background-TV and long-pause audio/reference timings, then execute actual Whisper inference and measure command accuracy/WER, false activations and endpoint latency. Text/fake-PCM tests cannot satisfy these acoustic assertions. No recordings, giant downloads or personal audio uploads were made. After this scope, the next unrun module/case is **05/JRV-05-001**. [Deterministic resume instructions](resume-02-04.md).

Further release risks: Python EOL, two environment dependency checks lacking pip, native parser/GIL hang containment, host ability isolation, live cloud/GUI/account contracts, arbitrary prose privacy and wider log redaction, long GPU contention and actual voice accuracy. [Security findings](security-findings.md). Fixtures observed zero unauthorized effects and uncertainty replay; this is bounded evidence, not universal proof.

## Files, rollback and verification

[Exact scoped file list](completion-files.json), per-module source patches/hashes and rollback: [02](modules/02-perception-cognition/rollback.md), [03](modules/03-intent-direct/rollback.md), [04](modules/04-voice-stt/rollback.md). Restore only reviewed hunks from captured preimages; never reset the dirty checkout or replay old task queues. Runtime metadata schema is additive; no new dependency/service. [Readiness](completion-readiness.json), [30-second synthetic soak](completion-soak.json), [verification record](completion-verification.json). Prior reports and XML remain in history folders; baseline failures are evidence, not final unresolved regressions.
''')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--final',action='store_true')
    publish(parser.parse_args().final)
