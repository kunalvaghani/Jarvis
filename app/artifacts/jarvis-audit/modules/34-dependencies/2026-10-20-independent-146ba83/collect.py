"""Collect Prompt 34 evidence; never executes installs, downloads or model inference."""
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc
import types
from unittest.mock import patch
import xml.etree.ElementTree as ET

OUT=Path(__file__).resolve().parent
APP=next(p for p in OUT.parents if (p/'main.py').is_file())
sys.path.insert(0,str(APP))
from jarvis import launcher
SHA='146ba831e7ae5df1a953b0f910288c41c9ab4689'
OLD='cd8861ce720ade303485ee2023430dd8c6b4f0ba'
def dump(name,data): (OUT/name).write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def write(name,text): (OUT/name).write_text(text.rstrip()+'\n',encoding='utf-8')
def git(*args): return subprocess.check_output(['git',*args],cwd=APP)
assert git('rev-parse','HEAD').decode().strip()==SHA

# Preserve outcome content while keeping private filesystem roots out of exported logs.
normalization={}
for path in list(OUT.glob('*.xml'))+list(OUT.glob('*.txt')):
    content=path.read_text(encoding='utf-8')
    original=hashlib.sha256(path.read_bytes()).hexdigest()
    for source,target in [(str(APP),'%AUDIT_APP%'),('D:\\Kunals GitHub Repo\\Jarvis\\app','%INSTALL_APP%'),(os.environ.get('USERPROFILE','NO_PROFILE'),'%USERPROFILE%')]:
        for spelling in {source,source.replace('\\','/'),source.replace('\\','\\\\')}:
            content=content.replace(spelling,target)
    path.write_text(content,encoding='utf-8')
    normalization[path.name]={'pre_normalization_sha256':original,'saved_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
dump('log-path-normalization.json',{'scope':'Only app/install/profile root spellings normalized; assertions/results untouched.','files':normalization})

results=[];runs={}
for label in ['baseline','boundaries','retention']:
    root=ET.parse(OUT/(label+'.xml')).getroot();subset=[]
    for case in root.iter('testcase'):
        skipped=case.find('skipped')
        status='FAIL' if case.find('failure') is not None or case.find('error') is not None else 'SKIPPED' if skipped is not None else 'PASS'
        subset.append({'id':case.get('name'),'classname':case.get('classname'),'status':status,
                       'reason':skipped.get('message') if skipped is not None else '',
                       'seconds':float(case.get('time',0)),'sha':SHA,'run':label,'evidence':label+'.xml'})
    results+=subset
    runs[label]={s:sum(r['status']==s for r in subset) for s in ['PASS','FAIL','SKIPPED']}
    runs[label]['seconds']=sum(float(s.get('time',0)) for s in root.findall('testsuite'))
totals={s:sum(r['status']==s for r in results) for s in ['PASS','FAIL','SKIPPED']}
dump('baseline.json',{'date':'2026-10-20','sha':SHA,'prior_comparison':OLD,'runs':runs,'totals':totals,
    'source_tree':'isolated codex-review','interpreter':'%INSTALL_APP%/.venv/Scripts/python.exe','test_process_peak_memory':'NOT MEASURED',
    'benchmark_memory':'operation-local tracemalloc only','install_or_download_execution':0,'log_paths':'normalized; see log-path-normalization.json'})
write('executed-results.jsonl','\n'.join(json.dumps(r) for r in results))

sourcepaths=['jarvis/launcher.py','jarvis/model_recovery.py','jarvis/paths.py','jarvis/diagnostics.py','jarvis/model_selection.py',
    'jarvis/ollama_models.py','jarvis/f5_speech.py','jarvis/speech.py','jarvis/app_adapters.py','jarvis/gpu_scheduler.py',
    'jarvis_bootstrap.py','config/runtime_manifest.json','scripts/setup/setup_brain.py','scripts/models/download_model.py']
dump('source-hashes.json',{name:hashlib.sha256((APP/name).read_bytes()).hexdigest() for name in sourcepaths})
dump('prior-evidence-hashes.json',{p.relative_to(APP).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
    for p in OUT.parent.iterdir() if p.is_file()})
dump('disk-readback.json',dict(zip(['total','used','free'],shutil.disk_usage(APP))))
tools=json.loads((OUT/'os-gpu-tools.json').read_text(encoding='utf-8'))
if tools['nvcc']['executable'] is None:
    tools['nvcc']['probe']={'status':'NOT FOUND ON PATH','limitation':'Does not prove toolkit absent; installed PyTorch wheels bundle their own CUDA runtime.'}
dump('os-gpu-tools.json',tools)
sbom=json.loads((OUT/'environment-sbom.json').read_text(encoding='utf-8'))
envs=sbom['environments']
versions={e['environment']:{p['name'].lower():p['version'] for p in e.get('packages',[])} for e in envs}
dump('compatibility-versions.json',{name:{key:values.get(key) for key in ['torch','torchaudio','transformers','mcp','pydantic','playwright','pypdf']}
    for name,values in versions.items()})

# Local pip parser only: no InstallCommand.run, index lookup, dependency resolution or filesystem mutation.
try:
    from pip._internal.commands import create_command
    parsed=[]
    with patch.dict(os.environ,{'PIP_NO_INDEX':'1'}):
        for isolated in [False,True]:
            options,_=create_command('install',isolated=isolated).parse_args([])
            parsed.append({'isolated':isolated,'PIP_NO_INDEX':'1','effective_no_index':bool(options.no_index)})
    dump('pip-offline-option-probe.json',{'scope':'Existing pip argument parser only; zero installs/index requests','observations':parsed})
except Exception as exc:
    dump('pip-offline-option-probe.json',{'status':'BLOCKED','error_type':type(exc).__name__})

# Paired installed-dependency readiness fixture: missing runtimes, no subprocess/service checks.
previous=types.ModuleType('jarvis.audit_old_launcher');previous.__package__='jarvis';previous.__file__=str(APP/'jarvis/launcher.py')
exec(compile(git('show',OLD+':app/jarvis/launcher.py'),'<fixed-prior-launcher>','exec'),previous.__dict__)
measure=[]
with tempfile.TemporaryDirectory() as folder:
    base=Path(folder);(base/'config').mkdir()
    (base/'config/runtime_manifest.json').write_text(json.dumps({'main_imports':['json'],'brain_imports':['json']}))
    config={'model_path':'models/fixture','brain':{'enabled':False},'speech':{'enabled':False}}
    for label,module,revision in [('before',previous,OLD),('after',launcher,SHA)]:
        with patch.object(module,'BASE',base):
            for _ in range(20): module.runtime_status(config,check_services=False)
            samples=[];tracemalloc.start()
            for _ in range(300):
                start=time.perf_counter_ns();row=module.runtime_status(config,check_services=False)
                samples.append((time.perf_counter_ns()-start)/1e6)
                assert row['status']=='repair_required'
            _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
        measure.append({'revision':label,'sha':revision,'fixture':'read-only missing-runtime readiness; no services/processes','samples':300,
            'p50_ms':statistics.median(samples),'p95_ms':sorted(samples)[284],'traced_peak_bytes':peak})
with (OUT/'benchmarks.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(measure[0]));w.writeheader();w.writerows(measure)
dump('benchmark-provenance.json',{'before':OLD,'after':SHA,'warmup':20,'iterations':300,
    'scope':'Same fixed readiness fixture; no repair, subprocess, service call, inference or optimization. Not startup/installation latency.'})

transformers_review=[{'environment':name,'version':values['transformers'],'version_in_reviewed_range':(4,49,0)<=tuple(int(n) for n in values['transformers'].split('.')[:3])<=(5,8,1)}
    for name,values in versions.items() if 'transformers' in values]
dump('cve-applicability.json',{'checked_date':'2026-10-20','exhaustive_scan':False,
    'transformers_GHSA_x9r9_c232_4q39':{'source':'https://github.com/advisories/GHSA-x9r9-c232-4q39','reviewed_range':'>=4.49.0, <=5.8.1',
        'installed_versions':transformers_review,'reachability':'UNVERIFIED; no load_custom_generate/custom_generate reference found in audited app source; local_files_only present in training scripts',
        'patch_action':'None; no blind major upgrade or exploit executed.'},
    'pypdf_GHSA_9m86_7pmv_2852':{'source':'https://github.com/py-pdf/pypdf/security/advisories/GHSA-9m86-7pmv-2852','reviewed_affected_range':'<6.7.5',
        'installed_main':versions.get('.venv',{}).get('pypdf'),'scope':'6.20.0 is outside this specific affected range; not a clean bill for every pypdf advisory.'}})

original=[json.loads(s) for s in (OUT.parent/'tests.jsonl').read_text(encoding='utf-8-sig').splitlines() if s.strip()]
mapping={
1:('BLOCKED','No clean/offline installation authorized; ranges/unhashed requirements do not prove reproducibility.'),
2:('BLOCKED','Actual separate F5/brain/main interpreter metadata and routing tests captured; different-Python-version fault not run.'),
3:('BLOCKED','Driver/CUDA-wheel metadata captured; no actual ABI/inference mismatch rollout fixture.'),
4:('PASS','Missing-model selection/disabled fallback regressions PASS, and local installed tags enumerated; automatic restoration is separately FAIL.'),
5:('BLOCKED','Playwright distribution observed; missing browser binary case not executed.'),
6:('BLOCKED','No dependency upgrade performed; existing baseline does not prove an upgrade contract.'),
7:('BLOCKED','Two public advisory ranges reviewed against metadata; no exhaustive CVE/reachability/remediation test or upgrade.'),
8:('BLOCKED','No unsupported-major candidate tested; existing version inventory only.'),
9:('BLOCKED','Node/npm --version pass; broken project CLI manifest fault not injected.'),
10:('PASS','10 actual top-level installed venvs probed with Python -I and distribution metadata; source interpreter references saved. No claim all are necessary/minimal.'),
11:('FAIL','P34-002: low-disk unapproved recovery still launches mocked model setup; no disk-budget gate.'),
12:('FAIL','P34-001: missing dependency invokes pip --isolated install without approval, including offline env fixture.'),
13:('BLOCKED','Different installed MCP/pydantic groups inventoried; no incompatible plugin installation/migration attempted.'),
14:('BLOCKED','No new embedding-unavailable retrieval fixture; previous phase evidence is historical.'),
15:('BLOCKED','Local-files-only training sources inspected; exact quantized-Ollama-as-LoRA-source fault not executed.'),
16:('BLOCKED','No real training/preemption run; selected budget/admission guards PASS only.'),
17:('BLOCKED','Blender bad-code/argument guard PASS; wrong ordinary-Python bpy invocation/reroute case not executed.'),
18:('BLOCKED','DOCX tracked-change/signature refusal PASS; proprietary XLSX macro/signature route not established here.'),
19:('BLOCKED','WSL version only; no distro started or Windows/WSL path/permission execution.'),
20:('BLOCKED','No installed package patched while workers ran; metadata/source isolation only.'),
21:('FAIL','Unapproved package/model repair command paths remain enabled; no global offline/authorization gate proven.'),
22:('PASS','GPU scheduler low/unknown-resource admission and fallback fixtures PASS. Physical mic/TTS survival and forced CUDA interruption remain BLOCKED.')}
cases=[]
for i,(status,reason) in mapping.items():
    ident=f'JRV-34-{i:03}'
    cases.append({'id':ident,'status':status,'reason':reason,'sha':SHA,'date':'2026-10-20',
        'original_status':next((r['status'] for r in original if r['id']==ident),'UNAVAILABLE'),
        'evidence':'executed-results.jsonl; environment-sbom.json; boundaries.xml; retention.xml'})
write('tests.jsonl','\n'.join(json.dumps(r) for r in cases))

write('inventory.md',f'''# Prompt 34 inventory — 2026-10-20

Pinned claude/audit `{SHA}`, isolated codex-review; same SHA as the final Prompt 33 confirmation. User explicitly moved to 34; Prompt 33 remaining live/migration/concurrency limits carry forward. Current app AGENTS, Prompt 34 and supplied independent read-only reconciliation contract apply. Master contract unavailable. Original checkout user config and all prior evidence preserved.

Actual inventory: 10 original-install environments (main, brain, deerflow, F5, harness, Hermes, Hermes-bootstrap, OpenViking, skills, training), queried by exact install-relative executable with -I and standard distribution metadata. See environment-sbom.json (names, versions, requires), dependency-graph.json, lockfile-map.json and worker-interpreters.json. %INSTALL_APP% is the user's installed app; %AUDIT_APP% is this separate reviewed checkout. Aliases protect private absolute roots while retaining per-worker executable suffixes. Requirement ranges, direct pins and resolved integration files are distinguished from a fully hash-locked installer. No new environments were created or installed.

Node 24.14.0, npm 11.11.1, Ollama 0.40.0, Docker 29.8.2 and WSL 2.6.1 read back. GPU is RTX 3050 Laptop / 4096 MiB, driver 610.74; nvcc not found on PATH does not prove toolkit absence. F5/training torch 2.6.0+cu124 versus brain 2.6.0+cpu; F5 transformers 4.44.2 versus brain/training 4.57.6. These are metadata, not a CUDA ABI/inference certificate. 18 local Ollama tags enumerated; no model loaded or pulled. WSL version queried only, no distro startup. Pip cache inventory saved, but completeness for offline restoration unproven.

Inspected launcher/runtime/model recovery/setup scripts, requirements, routing, system-map and relevant test/historical phase evidence. New actual startup repair boundary tests fail despite existing regression success. No application source fix by Codex; read-only contract reserves repair to Claude. No global/local package install, download, driver change, cloud payload, inference, training or live UI/microphone capture.
''')
write('failures.md','''# Confirmed blockers

## P34-001 — P1: startup repair installs packages without approval

launcher.run calls prepare_runtime automatically. A failed dependency import leads directly to runtime_command([project_python, -m, pip, --isolated, install, -r, requirements/runtime.txt]); no approval context is required. Independent JRV-34-012 uses a disposable complete-runtime fixture, injects a failed import, and intercepts every runtime command. Pip installation is attempted despite no approval and offline environment flags. unapproved-install-trace.json records the exact sanitized command sequence; zero real commands/installs executed. Existing-installed control issues only a read-only import check.

--isolated also affects pip environment configuration; the existing pip argument-parser readback in pip-offline-option-probe.json records effective no-index behavior without installing. Regardless of network availability, implicit environment mutation lacks the requested consent gate. Fix SHA NONE / APPLIES OPEN.

## P34-002 — P1: missing-model recovery starts download setup without approval/disk budget

ModelRecovery.repair starts download in a background thread. download opens an owned log and launches setup_brain --ollama-only without an approval or disk-space preflight. The setup script tries local cache restoration then calls Ollama /api/pull for missing tags; Whisper setup similarly streams model weights with no available-space budget check. The independent JRV-34-011 low-disk fixture intercepts Popen and injects one byte free; it still records one setup launch with no approval. No real setup child, provider call or weight download occurred. Deliberate shutdown control prevents launch. unapproved-model-trace.json is the exact intercepted evidence. The observed native effect is command admission, not a reproduced disk exhaustion. Fix SHA NONE / APPLIES OPEN.

STOP on two P1s under Prompt 34. No package upgrade or source repair by Codex. Existing positive regressions do not waive the new boundary failures.
''')
write('repair-handoff.md','''# Claude dependency repair handoff

At 146ba83, reproduce test_dependency_boundaries.py unchanged. P34-001: separate read-only readiness from installation; absent dependencies should report repair_required until explicit bounded repair authorization exists. Preserve the old working environment and stage replacements from a locked approved artifact set. Do not silently use pip --isolated to override offline settings. No network/package operation should start merely because an import failed.

P34-002: missing-model recovery must default to diagnosis/installed-compatible fallback, not an implicit download. Require approved model identity/revision/source, byte/disk/RAM/VRAM budget and offline/network policy at the final setup/download executor; reject unknown/insufficient budget before launch. Do not treat a configured tag as download consent. Preserve partial artifacts and active user work; no blanket deletion/recreation or silent provider substitution.

Keep the ordinary installed-runtime and deliberate-shutdown controls passing. Run target failures, the 50 baseline and 112 passing retention checks plus applicable model routing/fidelity/manifest regressions. Then prepare exact fix SHA for independent confirmation. Do not silently execute setup/install scripts to fix this audit. Source repairs remain on Claude under the supplied read-only independent-confirmation contract. No module 35 or deployment.
''')
write('cross-pillar-matrix.md','''# Cross-system retention

| Seam | Fresh evidence | Limit |
|---|---|---|
| Model routing / F5 / Whisper / GPU admission | GPU/F5/model selection retention suites PASS | No new real voice/GPU training or forced-kernel preemption |
| AZR training / ABI | Training budget and foreground lease guard PASS | No trainable model loading or CUDA ABI roundtrip |
| Pillar A/MCP / dependency isolation | Installed versions and worker routes inventoried; previous same-SHA 309 PASS is historical | No plugin package mutation/install |
| Pillar B / embedding | SBOM and original OpenViking environment enumerated | Missing-embedding route not executed |
| DGM / fixed evaluator | Protected-source retention control PASS | No candidate env migration |
| API-first document fidelity | DOCX signature/tracked-change and Blender rejection controls PASS | XLSX macro/native and installed-engine interpreter acceptance not established |
| Recovery / venv manifest | Baseline 50 PASS, 2 positive boundaries PASS | Unapproved install/download admission FAIL |

One retention skip explicitly blocks forcible stuck-CUDA-kernel interruption; selected lease checks do not prove it. Full final acceptance stopped at P1.
''')
write('compatibility.md','''# Compatibility and reproducibility

Read actual installed distributions/executable versions; no assumptions that the isolated worktree contains copied environments/assets. Launcher check remains repair_required there even though the original install has ten environments. CPU brain and CUDA F5/training groups are distinct; version metadata alone does not prove ABI/device correctness. nvcc missing on PATH is not proof bundled CUDA runtimes are missing.

Lockfile map shows ranged/unhashed project requirements plus integration resolved/Node lockfiles. Pip HTTP cache and nine locally built wheels are an inventory, not a complete offline wheelhouse. Clean rebuild, offline installation, unsupported-major migration, package mutation while workers run and tested uninstall/rollback are BLOCKED because no such changes were authorized. No dependencies changed; no before/after migration success invented.

The supported safe journey exercised is installed-runtime readiness and local metadata/model-tag inventory, with explicit isolated missing-environment diagnostics. It does not certify a clean install or full live application startup. Whole relevant release checks stopped after P1 reproduction.
''')
write('offline-reproducibility.md','''# Offline reproduction plan / current blockers

Preserve working envs and installed models. Build reviewed per-interpreter/platform/CUDA constraints and a complete hash-verified wheelhouse in an explicitly authorized staging environment; include exact Python build, native wheels and browser artifacts. Resolve transitive distributions and licenses, test with indexes disabled, compare package/import/SBOM snapshots, run compatibility/fidelity/ABI tests, then seek approval for promotion. Keep old interpreter/weights until replacement passes. Do not deduplicate environments solely because two share a version: F5 and brain have intentionally incompatible transformer/torch groups.

No clean install, upgrade, uninstall, WSL distro launch or destructive recreation occurred here; those acceptance steps remain BLOCKED. Missing models/packages must produce a clear blocker without downloads. Currently P34-001/002 violate the executor admission part of that boundary.
''')
write('security.md','''# Security / advisory applicability

Two P1 consent/resource/offline-admission blockers are independently reproduced with mocked executors. No real package mutation, cloud request, model pull, exploit, private recording or unrelated process target. Exported app/profile root paths are normalized; package metadata URLs omitted.

Non-exhaustive advisory review: the [pypdf maintainer advisory](https://github.com/py-pdf/pypdf/security/advisories/GHSA-9m86-7pmv-2852) identifies affected versions below 6.7.5; installed main pypdf 6.20.0 is outside that specific range. This is not a general pypdf security certificate. The [reviewed Transformers record](https://github.com/advisories/GHSA-x9r9-c232-4q39) reports pre-consent custom-generation code downloads for versions 4.49.0 through 5.8.1. Installed brain/training 4.57.6 is in that range; F5 4.44.2 is outside. The record lists no patched version. Audited app source search found no load_custom_generate/custom_generate call, and local training paths use local_files_only; full reachability/exposure remains UNVERIFIED. No exploit or speculative upgrade performed. Exact metadata/range assessment is in cve-applicability.json. A complete dependency/CVE/lock/license review remains BLOCKED, not waived.
''')
write('changes.md','''# Codex changes

Added read-only inventory/SBOM/graph probes, intercepted dependency-boundary tests, raw normalized XML/traces, reports, fixed-fixture benchmark and reconciliation. Updated both READMEs with dated results and limits. No application source, package, model, driver, configuration, UI/artwork or service policy change. No source repair, commit, merge, deployment, install or uninstall. Original user config and historical module evidence remain untouched. No screenshot is applicable.
''')
write('rollback.md','''# Rollback status

No package/source/model migration took place, so no uninstall rollback was executed or needed. The new evidence folder and its README paragraphs are the only Prompt 34 additions. Preserve earlier audit work and never reset the original user checkout. A future migration must stage beside the old env, validate/pin interpreter/native wheels/model revisions, retain old assets and switch only after approved postconditions. Revert the switch rather than deleting/recreating envs blindly. Tested upgrade/uninstall/rollback path remains BLOCKED until explicitly authorized; a written plan is not execution proof.
''')
write('codex-findings-reconciliation.md',f'''# Reconciliation at {SHA}

P34-001 P1 → JRV-34-012 failing intercepted prepare_runtime regression → APPLIES/OPEN → fix SHA NONE. P34-002 P1 → JRV-34-011 failing low-disk model-repair command regression → APPLIES/OPEN → fix SHA NONE. Positive controls, baseline and neighbor IDs are in executed-results.jsonl and raw XML. The wider JRV-34-021 offline requirement is FAIL for the same roots, not a third independent defect.

Original module catalog was available and joined by stable ID for revised cases 001–022. Planned originals were not converted to executed PASS. Previous Prompt 33 same-SHA reported fixes remain independently verified; full module acceptance there was partial. Older source/phase/author results remain historical. Master contract unavailable; supplied reconciliation read-only contract applied. Claude repair handoff is concrete; independent final release checks stop at the P1 boundary.
''')
write('verdict.md',f'''# Prompt 34 — NOT READY / BLOCKED

2026-10-20, independent isolated codex-review at `{SHA}`. **{totals['PASS']} PASS / {totals['FAIL']} FAIL / {totals['SKIPPED']} SKIPPED** across {len(results)} checks: baseline 50 PASS; retention 112 PASS/1 SKIP; boundary 2 PASS/2 FAIL.

**P34-001 P1:** failed startup import admits pip installation without approval. **P34-002 P1:** missing-model recovery admits download setup without approval/disk budget. Both executors were intercepted; zero real installs, downloads or model setup children. STOP on P1.

Actual inventory covers 10 installed Python envs, source worker routes, dependency metadata/lockfiles/cache, OS/GPU/Node/WSL/Docker/Ollama versions and 18 local model tags. No inference or WSL distro started. Clean reproducibility, CUDA ABI/live voice/training, comprehensive CVE remediation and migration rollback remain BLOCKED. Launcher repair_required in the isolated worktree. Benchmark is synthetic readiness overhead versus a fixed prior commit, not install/startup improvement.

[Findings](failures.md) · [Claude repair handoff](repair-handoff.md) · [22 cases](tests.jsonl) · [Inventory](inventory.md) · [Raw run provenance](baseline.json).

No source repair by Codex under the supplied independent read-only contract. No dependency upgrade, deployment or module 35.
''')

recon=APP/'artifacts/jarvis-audit/reconciliation/34-2026-10-20-independent-146ba83';recon.mkdir(exist_ok=True)
for name,origin in [('artifact-inventory.md','inventory.md'),('patch-assessment.md','changes.md'),('unresolved.md','failures.md'),('handoff.md','repair-handoff.md')]:
    text=(OUT/origin).read_text(encoding='utf-8')
    text=re.sub(r'\]\(([^)]+)\)',lambda m:'](../../modules/34-dependencies/'+OUT.name+'/'+m[1]+')',text)
    (recon/name).write_text(text,encoding='utf-8')
(recon/'review-revisions.json').write_text(json.dumps({'audit':SHA,'claude':git('rev-parse','claude').decode().strip(),'fix_sha':None},indent=2))
with (recon/'findings-ledger.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.writer(f);w.writerow(['finding','priority','status','sha','fix_sha','test'])
    w.writerow(['P34-001','P1','OPEN',SHA,'NONE','JRV-34-012']);w.writerow(['P34-002','P1','OPEN',SHA,'NONE','JRV-34-011'])
for name,label in [('repro-results.jsonl','boundaries'),('legacy-regressions.jsonl','baseline'),('cross-pillar-regressions.jsonl','retention')]:
    (recon/name).write_text('\n'.join(json.dumps(r) for r in results if r['run']==label)+'\n',encoding='utf-8')
print(json.dumps({'sha':SHA,'totals':totals,'runs':runs,'environments':len(envs),'original_catalog_rows':len(original)},indent=2))
