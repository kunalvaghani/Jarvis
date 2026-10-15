"""Publish Prompt08 from executed fixture, native observation and readiness evidence."""
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET

BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
ROOT=BASE/'artifacts/jarvis-audit';OUT=ROOT/'modules/08-gpu-scheduler'
PRE=BASE/'.jarvis-runtime/jarvis-audit/module08-pre'
RUNTIME=('jarvis/gpu_scheduler.py','jarvis/self_evolution.py','jarvis/repo_abilities.py')
FILES=(*RUNTIME,'config/runtime_manifest.json','scripts/verification/audit_catalog.py',
       'scripts/verification/verify_gpu_scheduler_audit.py','scripts/verification/report_gpu_scheduler_audit.py',
       'tests/test_gpu_scheduler_audit.py','tests/test_audit_result_accounting.py','README.md',
       'docs/gpu-priority.md','docs/self-evolution.md','docs/repo-abilities.md','docs/system-map.md')


def write(path,text):path.write_text(text,encoding='utf-8')


def run(name):
    tree=ET.parse(OUT/name);nodes=list(tree.iter('testcase'))
    assert nodes and not any(n.find('failure') is not None or n.find('error') is not None for n in nodes)
    skipped=[n for n in nodes if n.find('skipped') is not None]
    assert all('BLOCKED:' in n.find('skipped').get('message','') for n in skipped)
    return {'passed':len(nodes)-len(skipped),'blocked':len(skipped),'seconds':float(next(tree.iter('testsuite')).get('time',0))}


def main():
    targeted,full=run('cases-and-contracts.xml'),run('full-regression.xml')
    for name in RUNTIME:assert (OUT/'full-regression.xml').stat().st_mtime >= (BASE/name).stat().st_mtime
    modules=json.loads((ROOT/'module-map.json').read_text())
    modules[7].update(status='PARTIAL / SHARED SPEECH COORDINATION BLOCKED',reason='30 catalog PASS,2 BLOCKED: F5/Whisper do not implement shared leases. Bounded scheduler/learning fixes and sequential real9b observations completed.',
        sources=[*RUNTIME,'jarvis/brain.py','jarvis/speech.py','jarvis/f5_speech.py','jarvis/kokoro_speech.py','jarvis/audio.py','docs/gpu-priority.md'],
        unresolved_candidates=['jarvis/speech_worker.py (absent; actual speech subprocess uses kokoro_speech.py and f5_speech.py)'],
        test_candidates=['tests/test_gpu_scheduler_audit.py','tests/test_gpu_scheduler.py','tests/test_self_evolution.py','tests/test_repo_abilities.py','tests/test_voice_tts_audit.py'])
    write(ROOT/'module-map.json',json.dumps(modules,indent=2)+'\n')
    from scripts.verification.audit_catalog import reconcile
    reconcile()
    rows=[json.loads(s) for s in (ROOT/'test-results.jsonl').read_text().splitlines()]
    cases=[r for r in rows if r['id'].startswith('JRV-08-')]
    counts=Counter(r['status'] for r in cases)
    assert len(cases)==32 and counts=={'PASS':30,'BLOCKED':2}
    for row in cases:row['scope']='Production-boundary isolated fixtures;001/010 additionally inspect captured real sequential cached9b observations.002/012 require missing shared speech lease protocol. No physical contention/acoustic success inferred.'
    write(OUT/'tests.jsonl',''.join(json.dumps(r)+'\n' for r in cases))
    write(OUT/'remaining-case-ids.txt',''.join(r['id']+'\n' for r in cases if r['status']!='PASS'))
    summary=json.loads((ROOT/'summary.json').read_text())
    bench=json.loads((OUT/'benchmark-summary.json').read_text())['results']
    cold=json.loads((OUT/'native-cold-observation.json').read_text());warm=json.loads((OUT/'native-local.json').read_text())
    assert cold['status']==warm['status']=='PASS' and cold['initial_gpu_cold'] and not cold['prior_resident_names']
    ready=json.loads((PRE/'readiness-private.json').read_text(encoding='utf-8-sig'))
    assert ready['status']=='ready' and not ready.get('missing') and not ready.get('incomplete')
    write(OUT/'readiness.json',json.dumps({'date':'2026-10-15 IST','command':'python -m jarvis.launcher --check','exit_code':0,
        'status':ready['status'],'scope':ready.get('scope'),'services':{k:v['status'] for k,v in ready.get('services',{}).items()}},indent=2)+'\n')
    diff='';hashes={}
    for name in (*RUNTIME,'config/runtime_manifest.json','scripts/verification/audit_catalog.py'):
        path,old=BASE/name,PRE/Path(name).name
        assert old.is_file()
        diff+=''.join(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),path.read_text(encoding='utf-8').splitlines(True),fromfile='module08-pre/'+name,tofile=name,n=1))
        hashes[name]={'before':hashlib.sha256(old.read_bytes()).hexdigest(),'after':hashlib.sha256(path.read_bytes()).hexdigest()}
    write(OUT/'source.patch',diff);write(OUT/'source-hashes.json',json.dumps(hashes,indent=2)+'\n')
    files=[{'path':'app/'+name,'sha256':hashlib.sha256((BASE/name).read_bytes()).hexdigest()} for name in FILES]
    files.append({'path':'README.md','sha256':hashlib.sha256((BASE.parent/'README.md').read_bytes()).hexdigest()})
    write(OUT/'files-changed.json',json.dumps({'scope':'Module08 scoped files; earlier dirty work preserved. No commit/install/deployment.',
        'files':files,'artifacts_directory':'app/artifacts/jarvis-audit/modules/08-gpu-scheduler',
        'shared_artifacts':['final-report.md','module-map.json','test-results.jsonl','executed-tests.jsonl','summary.json','remaining-case-ids.txt','security-findings.md']},indent=2)+'\n')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=BASE,text=True).strip()
    branch=subprocess.check_output(['git','branch','--show-current'],cwd=BASE,text=True).strip()
    before,after=bench['before_warm_read'],bench['after_warm_read']
    table='\n'.join(f'| {name} | {value["samples"]} | {value["p50_ms"]:.4f} | {value["p95_ms"]:.4f} | {value["atomic_promotions"]} | {value["peak_python_bytes"]} |' for name,value in bench.items())
    matrix='''| Claim | Actual path | Assertion / limit |
| --- | --- | --- |
| Physical polling / primary envelope | [gpu_scheduler.py](../../../../jarvis/gpu_scheduler.py):memory/allocation/configured | Missing GPU→CPU; partial offload;20% arithmetic margin over calibrated9b envelope, not universal physical OOM protection |
| Cross-process priority/ownership | Registry.state, Lease.acquire/close | Existing process fixtures,100 five-way turns, role/priority/owner identity validation, dead-owner reap, cancelled waiter preserves active owner |
| Native request lifecycle/cache | install | Hardware-probe failure cleanup, no retry, bounded wait, exact cache identity handoff/reuse, unowned changed cache untouched; no active-kernel preemption |
| Operational metadata | Registry.event/status, Lease.event | Allowed scalar fields, UUID/categorical failure, model label validation; state size/depth/queue bounds |
| Optional idle learning | [self_evolution.py](../../../../jarvis/self_evolution.py):SelfEvolution._resources_ok | Low or unknown resource readings defer work; idle/user-busy thresholds retained |
| Large coder selection | [repo_abilities.py](../../../../jarvis/repo_abilities.py):AbilityForge.pick_model | Initial preferred/fallback size + RAM margin; low-RAM fixture refuses both; unknown30b GPU footprint forces CPU, no native30b load |
| Speech | [speech.py](../../../../jarvis/speech.py), f5_speech.py, kokoro_speech.py, audio.py | No speech_worker.py in checkout; F5/Whisper outside shared coordinator.002/012 BLOCKED, not proved by Ollama mocks |
| Task requests | [brain.py](../../../../jarvis/brain.py):BrainClient | Existing owned worker/proxy paths use scheduler integration; no tool actions or model settings changed by this audit |
'''
    write(OUT/'inventory.md',f'''# Prompt08 GPU scheduler/resource audit — 2026-10-15 IST

**30 catalog PASS,2 BLOCKED (JRV-08-002/012);0 FAIL/SKIPPED/NOT RUN.** Shared native speech ownership remains incomplete; no whole-system production certificate.

Repo `{commit}`, branch `{branch}`; Windows/Python{platform.python_version()}, actual NVIDIA RTX3050 Laptop4096MiB, Ryzen7/32GB target. Existing dirty work preserved in app/, not its InsTAREELS alias. No personal delete/account write, new ability/install/download, global GPU environment change, driver reset, forced CUDA clear, commit or deployment. One native heavyweight request at a time; no microphone/speaker/GUI acceptance run.

{matrix}

System map and existing GPU-priority, self-evolution, repo-abilities, crash-recovery guides inspected. Current policy: enabled/helper_gpu=false, primary12/codex9 layers, reserve512MiB, wait120s, warm1800s, CPU threads12. Configured F5 CUDA raises effective speech reserve from1024 to2048MiB. These are current config observations; historical October8 numbers remain dated. No actual user configuration was changed.

## Executed baselines and regressions

Corrected baseline: **28 PASS/4.62s**, [XML](existing-baseline-corrected.xml). An initial nonexistent test_resource_policy.py invocation collected no assertions: [collection error](existing-baseline.xml). New fault baseline:7 actual failing variants plus1 incorrect Forge class import in [initial XML](reproduced-failures.xml); corrected AbilityForge RAM repro [fails here](ram-reproduced.xml). Tight-headroom/32K-context20% margin [also failed](margin-reproduced.xml); smaller8K context already fit and is not treated as a defect. All accessible failures now have executed regression proof.

Final targeted: **{targeted['passed']} PASS/{targeted['blocked']} explicit BLOCKED skips**, {targeted['seconds']:.2f}s,[XML](cases-and-contracts.xml). Full `python -m pytest tests -q --tb=short`: **{full['passed']} PASS/{full['blocked']} explicit BLOCKED skips**, {full['seconds']:.2f}s,[XML](full-regression.xml). Suites overlap; do not sum. Launcher `python -m jarvis.launcher --check`: **ready**, [redacted check](readiness.json). One pywinauto STA COM warning was reported; readiness is not live contention proof.

Targeted command: `.venv/Scripts/python.exe -m pytest tests/test_gpu_scheduler_audit.py tests/test_gpu_scheduler.py tests/test_self_evolution.py tests/test_repo_abilities.py tests/test_model_routing_audit.py tests/test_voice_tts_audit.py tests/test_audit_result_accounting.py -q --tb=short --junitxml=artifacts/jarvis-audit/modules/08-gpu-scheduler/cases-and-contracts.xml`.

## Matched state-I/O benchmark

Identical empty registry polls/OS locks,20warm +5cold samples per version. Cold recreates Registry only, not the process/disk/model cache. Baseline is saved pre-change source; no model allocation or network inference in this microbenchmark. Tracemalloc includes mock accounting.

| Build/mode | Samples | p50 ms | p95 ms | Atomic promotions | Traced peak bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
{table}

[50 samples](benchmarks.csv), [summary](benchmark-summary.json). Retain no-change write elimination:20→0 warm atomic promotions and p95 **{before['p95_ms']:.4f}→{after['p95_ms']:.4f}ms**. Traced peak **{before['peak_python_bytes']}→{after['peak_python_bytes']} bytes** increases slightly with bounded validation/read machinery; no memory reduction claimed. A preliminary fixed200001-character read allocated~245KB per tiny poll; bounded4096-character chunks avoid that overhead in the retained implementation. No A/B native inference or first-audio speedup inferred.

## Native measurements and scope

No model was resident at the initial observation. Cached installed9b GPU-cold invocation: TTFT **{cold['samples'][0]['ttft_seconds']:.3f}s**, load_duration **{cold['samples'][0]['metrics']['load_duration']/1e9:.3f}s**, full reply **{cold['samples'][0]['seconds']:.3f}s**; following warm TTFT **{cold['samples'][1]['ttft_seconds']:.3f}/{cold['samples'][2]['ttft_seconds']:.3f}s**. [Cold observation](native-cold-observation.json). Later warm TTFT **{'/'.join(f"{r['ttft_seconds']:.3f}" for r in warm['samples'])}s**, [warm observation](native-local.json). Actual allocation4layers/16384context; sampled peak physical GPU **{warm['sampled_peak_gpu_used_mb']}MiB**. Observer-process RSS is recorded separately, not Ollama/system peak RAM. Sampling can miss brief spikes. Registry readback is idle after each series; warm model remains cached, so lease release is not physical immediate eviction.

These sequential arithmetic probes establish actual transport/admission/cache behavior, not speech coexistence,30B safety, driver-reset recovery on real hardware, or broad answer quality. They ran during this audit before final metadata/error and small-config margin guards; normal default allocation/settings stayed identical. Final guard behavior is covered by the full regression. No forced shared-model unload or global environment tuning was used.

## Open blockers and risk

002: F5 arrival during9b generation cannot be certified because speech has no shared ownership/admission handshake.012: there is no stuck-TTS shared lease for this watchdog to restore safely. Real speech contention is therefore BLOCKED by missing implementation prerequisites. No unsafe timeout evicts a live owner or kills shared Ollama. Existing active inference can finish before higher priority queued work; cooperative callbacks are not kernel preemption. Other applications can allocate memory after polling.30B/RAM limits remain initial-size heuristics; peak activation/RAM stress and F5/Whisper behavior require separate safe work.

[32 case ledger](tests.jsonl), [failures](failures.md), [changes/decisions](changes.md), [compatibility](compatibility.md), [rollback](rollback.md), [exact files](files-changed.json), [scoped diff](source.patch).
''')
    write(OUT/'failures.md','''# Failure baselines and disposition — 2026-10-15 IST

Seven initial actual failing variants: every unchanged poll rewrote state; hardware-probe exception leaked an active admission; three malformed owner/cache shapes were accepted or raised an unhelpful TypeError; oversized state was accepted; unknown resource readings admitted optional learning. One initial test imported nonexistent Forge; corrected to AbilityForge, which then genuinely failed to reject an unfittable fallback. Separate32K/small-reserve test demonstrated a20% envelope overrun exceeding capacity. Baseline XMLs are retained; current runs are distinct.

Repairs validate bounded persisted state before liveness/mutation, skip unchanged writes, protect probe failures with lease cleanup, retain a primary-envelope margin floor, defer uncertain optional learning and require initial fallback size+margin to fit. Additional assertions cover duplicate lease acquisition, fake secret metadata, forged priorities, cross-process ownership and partial/failed transport non-replay. An initial nonexistent resource-policy test filename was a collection error and counts no assertions.

Open implementation blockers002/012: F5/Whisper are outside the shared lease coordinator. No live speech-arrival/stuck-TTS proof, forced driver reset, native30B stress, simultaneous uncontrolled GPU load, physical immediate free guarantee or kernel preemption was attempted. Prior speech acceptance blockers remain. Physical polling and initial model-size estimates cannot guarantee future capacity against external allocators.
''')
    write(OUT/'changes.md','''# Scoped changes and keep/revert decisions — 2026-10-15 IST

Keep validated state size/depth/node/queue bounds; role/priority, owner token/PID/time and cache field checks. Preserve malformed files and refuse admission. Keep the OS lock while omitting a redundant atomic promotion when canonical state is unchanged; real queue/owner/cache mutations remain atomic. The measured fixture shows fewer disk writes and lower p95; traced allocation slightly increases, so no RAM gain claimed.

Move physical probing inside failure cleanup; categorical failure events correlate with lease UUIDs. Lock release bookkeeping, reject duplicate active acquisition and unknown policy fields. Validate model labels and filter event fields without serializing prompts, paths, approval claims or errors. Do not reclaim live owners on arbitrary age. Known cache identity handoff/reuse and no uncertain external-action replay remain unchanged.

The primary-model envelope subtracts max(configured reserve,available/6), allowing a20% estimate overrun within measured available capacity. Defaults on this4GB/F5 configuration keep their prior allocation. This is fixture arithmetic, not a safety promise for unknown models or concurrent external allocators. Preserve existing num_ctx/keep_alive/quantization/global environment settings: native cold/warm observations have no matched before/after accuracy/latency baseline to justify retuning them.

Optional learning now defers unknown resource readings, and initial ability model selection checks fallback size+RAM margin. Existing model_chat fixtures remain supported. No new dependency/service, ability installation, permission bypass, UI layout or image introduced. Shared speech-coordinator integration is not represented as solved; it needs a separate lifecycle design and native contention validation.
''')
    write(OUT/'compatibility.md','''# Compatibility / official checks — 2026-10-15 IST

Actual Ollama0.40.0, installed cached Qwen3.5:9b, Python3.10.6, NVIDIA RTX3050 Laptop4096MiB. Official [latest Ollama release](https://github.com/ollama/ollama/releases/tag/v0.40.4) is0.40.4,12Oct2026 at19:00 (timezone not established); notes mention reuse of verified manifests/loaded models. No installation/download authorized/performed; newer runtime/native performance remains unvalidated here. Existing runtime completed both native series. Prior Python support-window concern remains separate work.

Official [FAQ](https://docs.ollama.com/faq) documents context/parallelism memory costs and keep_alive cache retention. Current application overrides differ from default provider values. [Loaded-model API](https://docs.ollama.com/api/ps) supplies size_vram/context/expiry fields used for fresh identity checks; example numbers in documentation are not measurements of this machine. No date is stated on those guides. [Captured source checks](upstream-checks.json).

No quantization, CUDA library, PyTorch/Whisper runtime, global parallelism or driver change. No brittle manual CUDA clear. Real cold/warm samples use the existing API/GPU scheduler; defaults remain compatible in executed scope, not certified across optional integrations or a future release.
''')
    write(OUT/'rollback.md','''# Scoped rollback / resume

No new commit. Never git-reset/checkout whole shared files over earlier dirty work. Stop Jarvis normally if applying rollback, inspect source.patch/source-hashes.json, reverse only these module08 hunks, reconcile README/manifest and preserve subsequent edits. Local preimages: .jarvis-runtime/jarvis-audit/module08-pre/. Preserve quota/history, credentials, learning files and existing GPU state; malformed state is not silently deleted. Do not kill shared services or forcibly unload unrelated model caches.

Reproduce the targeted command in inventory.md, `python -m pytest tests -q --tb=short`, and `python -m jarvis.launcher --check`. `python scripts/verification/verify_gpu_scheduler_audit.py` runs saved-before/current CPU state polls. `--native` runs three sequential installed9b synthetic requests and read-only memory sampling; it defers if another GPU model is resident and never downloads or forces a cold cache. Cold may be unavailable on rerun; retain/relabel observations instead of fabricating a cold measurement. Do not run another heavyweight GPU test concurrently. Reporter: `python scripts/verification/report_gpu_scheduler_audit.py` requires completed successful XML/readiness and retained native observations.

Incomplete module08 IDs: JRV-08-002,JRV-08-012 (shared F5/Whisper lease lifecycle missing). Earliest global unresolved JRV-04-001. Next module09; its first NOT RUN case is calculated in the final report because some later-module cases already have earlier proofs. Filter test-results.jsonl for status NOT RUN to resume deterministically. Exact global remaining IDs are ../../remaining-case-ids.txt. No live owner may be revoked merely to make a watchdog test pass.
''')
    archive=ROOT/'final-report-before-module08.md'
    if not archive.exists():write(archive,(ROOT/'final-report.md').read_text(encoding='utf-8'))
    modules_table='\n'.join(f'| {m["number"]:02d} | {m["module"]} | {m["status"]} |' for m in modules)
    next_unrun=next(r['id'] for r in rows if r['status']=='NOT RUN')
    write(ROOT/'final-report.md',f'''# Jarvis audit through Prompt08 — 2026-10-15 IST

**Prompt08:30 catalog PASS,2 BLOCKED (002/012),0 FAIL/SKIPPED/NOT RUN.** Targeted **{targeted['passed']} PASS/{targeted['blocked']} explicit BLOCKED skips**; full regression **{full['passed']} PASS/{full['blocked']} explicit BLOCKED skips**, {full['seconds']:.2f}s. [Targeted XML](modules/08-gpu-scheduler/cases-and-contracts.xml), [full XML](modules/08-gpu-scheduler/full-regression.xml); scopes overlap. Launcher **ready**, [redacted check](modules/08-gpu-scheduler/readiness.json). Whole-system production acceptance remains open.

Repo `{commit}`, branch `{branch}`, Windows/Python{platform.python_version()}, actual RTX3050 Laptop4096MiB and Ryzen7/32GB target. Existing dirty work preserved. No real cloud/account write, personal delete, install/download, driver reset, forced CUDA clear, global model setting change, new ability, commit or deployment. One native heavyweight probe at a time. [Source-map-to-code matrix](modules/08-gpu-scheduler/inventory.md), [exact changed files](modules/08-gpu-scheduler/files-changed.json), [scoped preimage diff](modules/08-gpu-scheduler/source.patch).

Repairs cover malformed/unbounded GPU state, redundant poll writes, leaked admission on hardware-probe failure, duplicate acquisition, release/telemetry boundaries,20% primary-envelope margin with tight configured headroom and low/unknown-resource learning. [Baseline failures](modules/08-gpu-scheduler/failures.md), [changes/tradeoffs](modules/08-gpu-scheduler/changes.md), [risk/rollback](modules/08-gpu-scheduler/rollback.md).

Matched20warm/5cold state polls per build: warm p50/p95 **{before['p50_ms']:.4f}/{before['p95_ms']:.4f}→{after['p50_ms']:.4f}/{after['p95_ms']:.4f}ms**; atomic promotions **20→0**; traced peak **{before['peak_python_bytes']}→{after['peak_python_bytes']} bytes**. [All50 samples](modules/08-gpu-scheduler/benchmarks.csv). Cold here recreates Registry, not model/disk cache. No model inference/RAM gain inferred.

Actual installed9b with no prior resident model: cold TTFT **{cold['samples'][0]['ttft_seconds']:.3f}s**, provider load duration **{cold['samples'][0]['metrics']['load_duration']/1e9:.3f}s**; final warm TTFT **{'/'.join(f"{r['ttft_seconds']:.3f}" for r in warm['samples'])}s**.4GPU layers/16K context; sampled physical peak **{warm['sampled_peak_gpu_used_mb']}MiB**. [Cold](modules/08-gpu-scheduler/native-cold-observation.json), [warm/readback](modules/08-gpu-scheduler/native-local.json). These are unpaired synthetic arithmetic observations, not full voice/accuracy/peak-RAM acceptance. No forced model eviction for a benchmark.

F5/Whisper have no shared lease handshake: speech-arrival002 and stuck-TTS012 remain **BLOCKED**. Priority is queued/cooperative, not running-kernel preemption. Cache retention means admission release is not physical immediate VRAM free. Other applications may allocate after polling;30B peak RAM and native contention are unproved. [Official sources/releases/compatibility](modules/08-gpu-scheduler/compatibility.md); local Ollama0.40.0 is older than0.40.4 (12Oct2026), without an unapproved install.

## Catalog and modules

1184 unique IDs: **{summary['catalog_counts']}**. [Case/assertion ledger](test-results.jsonl), [tier/category/run totals](summary.json), [module08 cases](modules/08-gpu-scheduler/tests.jsonl), [exact remaining IDs](remaining-case-ids.txt). [Preserved module01–07 report](final-report-before-module08.md) retains earlier metrics/baselines and live cloud/acoustic risks.

| Module | Name | Status |
| --- | --- | --- |
{modules_table}

First remaining module08 IDs002/012; earliest global unresolved JRV-04-001. Next unexecuted catalog ID **{next_unrun}**; module09 work has prior isolated proofs and must not double count them. Resume/rollback linked above. No full production certification or universal two-second voice/memory-safety guarantee is claimed.
''')
    security=ROOT/'security-findings.md';prior=security.read_text(encoding='utf-8') if security.exists() else ''
    if '## Prompt08 —' not in prior:write(security,prior+'\n## Prompt08 — 2026-10-15 IST\n\nBounded owner/cache state, role-priority integrity, metadata filtering, probe-failure cleanup, duplicate acquisition and low-resource learning repaired with fixtures. Shared F5/Whisper ownership002/012 remains blocked; no timeout kills a live/shared owner. Calibrated20% arithmetic margin is not universal physical capacity proof. See modules/08-gpu-scheduler/inventory.md.\n')
    print(json.dumps({'targeted':targeted,'full':full,'module08':dict(counts),'catalog':summary['catalog_counts'],'readiness':ready['status']}))


if __name__=='__main__':main()
