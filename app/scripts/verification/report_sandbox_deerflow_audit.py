"""Publish Prompt 28 executed evidence with explicit unfinished contracts."""
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
OUT=BASE/'artifacts/jarvis-audit';MOD=OUT/'modules/28-sandbox-deerflow';PRE=BASE/'.jarvis-runtime/jarvis-audit/module28-pre'
common.MOD=MOD
read,sha,write,stats=common.read,common.sha,common.write,common.stats
GATES={
5:'Offline confinement is tested, but untrusted-repository installer provenance and a separate explicit approval event are not enforced by a dedicated sandbox installer gate.',
8:'Wrong PNG structure and missing optional runtime are refused; all seven installed literal recipes were exercised. Uniform per-renderer missing-module/font/codec/voice readiness probes and precise unavailable-capability diagnostics are not implemented.',
9:'Per-container CPU limits are configured and RAM/PID limits inspected. No cross-process admission quota for multiple DeerFlow research/render jobs; each job still requests 2 CPUs/2 GiB independently.',
10:'Failed/unobserved sources cannot authorize a matching receipt. HTTP-200 paywalls, teaser text and incomplete extraction lack a comprehensive paywall/content-availability classifier.',
12:'Unknown/failed/mismatched source-call citations are rejected by existing tests. Resolved citation IDs do not verify claim entailment, source quality or factual correctness.',
15:'Non-object worker JSON now returns a controlled protocol error, and checkpoint/media validation is stronger. A complete typed schema for result/receipt/source/artifact/tool data is absent.',
21:'No host credential env or project mount is offered to the tested container, and public research omits the project field. No full fake-secret/cloud/Groq/telemetry/cache oracle; commands/diagnostics and selected input copies may contain private content locally.',
23:'Cancellation is deterministic, but there is no complete semantic negation oracle for natural-language research/sandbox goals. A model’s interpretation of “do not run X” is not a permission guarantee.',
25:'Per-container limits and bounded filesystem fixtures pass; no full host RAM-pressure/GPU-allocation failure versus responsive core-command test. No GPU workload ran.',
27:'A/B measures 20 warm and five initial inventory iterations with tracemalloc. Not five cold processes/full harness/container jobs with RSS/VRAM, TTFT/audio or general research/render latency.',
30:'Owned worker cancellation and real nonzero-container failure are covered. Full daemon/worker disconnect/crash recovery with task provenance, durable cleanup retry and cross-process leases remains incomplete.',
32:'Job IDs, state, image/container identity and output hashes exist. Raw command/diagnostic/error files and full model/research traces lack a complete private-data redaction/correlation/readback oracle.'}


def marker(path,text):
    value=path.read_text(encoding='utf-8');value=re.sub(r'\n<!-- prompt28-audit -->.*?<!-- /prompt28-audit -->\n','',value,flags=re.S)
    first,rest=value.split('\n',1);path.write_text(first+'\n\n<!-- prompt28-audit -->\n'+text+'\n<!-- /prompt28-audit -->\n'+rest,encoding='utf-8')


def main():
    from scripts.verification import audit_catalog
    baseline,target,full=(stats(n) for n in ('baseline.xml','cases-and-contracts.xml','full-regression.xml'))
    assert baseline['PASS']==30 and target['PASS']==84 and target['SKIPPED']==12
    assert baseline['FAIL']==target['FAIL']==full['FAIL']==0
    frozen=read(MOD/'full-start-source-hashes.json');assert all(sha(BASE/p)==h for p,h in frozen.items())
    bench,env,ready,live,optional,inventory,renderers=(read(MOD/n) for n in ('benchmark-summary.json','environment.json','readiness.json','container-fixture.json','optional-runtime.json','source-inventory.json','renderer-fixtures.json'))
    assert bench['equivalent'] and bench['real_external_actions']==0 and ready['status']=='ready'
    assert live['math']['observed']['answer']==4 and live['render']['verification']['format']=='PNG'
    assert live['math']['cleaned'] and live['render']['cleaned'] and live['failure']['cleaned'] and live['failure']['calls']==1
    assert len(renderers['rows'])==6 and all(r['status']=='PASS' and r['cleaned'] for r in renderers['rows'])
    modules=read(OUT/'module-map.json')
    modules[27].update(sources=['jarvis/deerflow.py','jarvis/deerflow_worker.py','jarvis/deerflow_sandbox.py','jarvis/docker_runtime.py','jarvis/deerflow_media.py','jarvis/deerflow_media_runner.py','jarvis/research_evidence.py','docs/deerflow.md','docs/deerflow-sandbox.md'],
        test_candidates=['tests/test_sandbox_deerflow_audit.py','tests/test_docker_sandbox.py','tests/test_deerflow.py'],status='PARTIAL',reason='20 catalog fixture PASS / 12 incomplete contracts; owned offline math/PNG/nonzero/cleanup checked, no general live research acceptance')
    (OUT/'module-map.json').write_text(json.dumps(modules,indent=2)+'\n')
    with redirect_stdout(io.StringIO()):audit_catalog.reconcile()
    catalog=[json.loads(s) for s in (OUT/'test-results.jsonl').read_text(encoding='utf-8').splitlines()];cases=[r for r in catalog if r['id'].startswith('JRV-28-')]
    assert len(cases)==32 and Counter(r['status'] for r in cases)=={'PASS':20,'BLOCKED':12}
    assert {int(r['id'][-3:]) for r in cases if r['status']=='BLOCKED'}==set(GATES)
    write('tests.jsonl','\n'.join(json.dumps(r,ensure_ascii=False) for r in cases));summary=read(OUT/'summary.json')
    write('remaining-case-ids.txt','\n'.join(f'JRV-28-{n:03}' for n in GATES))
    gates='\n'.join(f'- **JRV-28-{n:03} BLOCKED:** {s}' for n,s in GATES.items())
    scope=('Mock-based Docker, worker, restart and transport faults; isolated files/checkpoints; five concurrent writes × 20 rounds and an owned checkpoint-crash child. '
        'Separately, nine actual owned ephemeral containers used the installed reviewed image: synthetic 2+2/UID/isolation, all seven literal media recipes, and a nonzero exit with stop/no-replay and cleanup. Stock narration ran CPU ONNX with existing assets and was not played. '
        'No Desktop startup/restart, image pull/build, dependency installation, account operation, personal input mount, public research query, LLM inference, audible playback or GPU workload. '
        'Only the attested fixture containers were removed; generated files were preserved. Historical measurements and artwork remain dated; no new GUI screenshot is claimed.')
    matrix=f'''| Claim | Actual entry/source | Executed evidence and limit |
| --- | --- | --- |
| Research tools | ToolRegistry → deerflow.execute/request → owned deerflow_worker → scoped observe | {len(inventory['tools'])} registered tools; {len(inventory['skills'])} public guides; real harness registration/discovery, mocked worker faults and existing source-receipt assertions; no new live model/public research trial |
| Network separation | worker research/web_research/sandbox allowlists; SandboxJob.create | Public web route omits local project context; Docker NetworkMode=none inspected. No account/browser/host-exec tools in the research adapter; semantic prompt/approval gaps remain |
| Isolation | SandboxJob.create → RepositorySandbox.cli → local Linux Docker | Actual UID 65534, root read-only, no network, capabilities dropped, no-new-privileges, 2 GiB RAM/swap, 128 PID limit; mounts inspected against allowed destinations, no Docker socket; no hostile-daemon guarantee |
| Mounts | SandboxJob._local/create/stage_inputs/path | Reparse/link checks include application/job/skills/model ancestors; explicit copied inputs and no project mount; fake linked ancestor rejected before run. Not atomic handle-based containment against a hostile host mutating directories |
| Identity | immutable image ID, new state.container_id, owned() | New jobs pin full Docker ID; exec/kill/remove target inspected ID; replaced-ID test refuses. Legacy checkpoints without container_id still use image/label/name attestation |
| Budgets and recovery | execute/observe/_checkpoint/save; DockerService | Pending attempted/uncertain checkpoint fences different commands after restart; locked writes use exclusive create and shared 20-effect budget; 512K-character checkpoint bound and schema validation. Daemon startup remains existing managed behavior, not a new lazy-start policy |
| Timeouts/nonzero | Linux timeout + bounded Docker CLI + uncertainty checkpoint | Injected timeout kills attested owned job; real exit 7 stops its container, retains uncertainty and refuses replay; cleanup inspected. Complete logs/daemon-outage recovery remain incomplete |
| Media | deerflow_media.validate/execute/verify_artifacts | All {len(inventory['renderers'])} installed literal recipes exercised; chart PNG 1280×720, malformed PNG rejected. PNG uses Pillow structure checks; WAV PCM readback, bounded PPTX ZIP/CRC checks; PDF/MP4 envelope checks alone do not prove pages/codecs/frames |
| Outputs | SandboxJob.inventory → actual files; parent artifact_evidence | Bounded deterministic lexical traversal preserves first 200 paths/sizes, platform ordering and link exclusions; directory/depth/traversal budgets. Actual file evidence remains distinct from model prose |
| Lifecycle | owned worker/OwnedJob; DockerService; close/reap_orphans | Existing Start/Stop/bootstrap/launcher/recovery interfaces unchanged; no shared-engine stop, personal config edit, dependency or new service. Aggregate admission and cross-process job locks are not added |'''
    metrics=(f"For 3,000 synthetic files and identical first 200 inventory rows, warm p50/p95 changed from {bench['before']['p50_ms']:.5f}/{bench['before']['p95_ms']:.5f} ms "
        f"to {bench['after']['p50_ms']:.5f}/{bench['after']['p95_ms']:.5f} ms; peak temporary Python allocation {bench['before']['peak_python_bytes']} → {bench['after']['peak_python_bytes']} bytes.")
    write('inventory.md','# Prompt 28 sandbox/DeerFlow audit — 2026-10-16 IST\n\n**PARTIAL: 20 catalog fixture PASS / 12 BLOCKED.**\n\n'+scope+'\n\n'+matrix+'\n\n![Actual rendered synthetic Docker chart fixture](fixture-chart.png)\n\nSynthetic chart generated and inspected on 2026-10-16; not a desktop screenshot or model performance result.\n\n'+gates+'\n\n[Report](../../final-report.md) · [Assertions](cases-and-contracts.xml) · [Container receipt](container-fixture.json) · [Other recipe receipts](renderer-fixtures.json) · [Diff](source.patch)')
    write('failures.md','# Failure and repair history\n\nBaseline: 30 passed. Initial restricted-token execution hit Windows atomic-replace permission failures, preserved in reproduction-restricted-environment.xml; these are not all product failures. Re-running with approved temporary fixture permissions reproduced eight failing assertions. They cover pending-checkpoint continuation, write-budget omission, timeout cleanup, unbounded checkpoint load, linked mount ancestors, mutable image identity, nonexclusive writes and accepting a filename as media evidence.\n\n'
        'First repair run: 36 passed / 2 failed. The media fixture’s mocked __exit__ swallowed exceptions; return_value=False makes its rejection observable. The cleanup test expected a mutable name, updated to assert the inspected immutable ID. Next subset: 38 passed. Expanded suite: 81 passed / 1 failed / 12 skips because a fixture base directory was absent; helper now creates it. Final focused: 84 passed / 12 explicit blockers. Worker non-object JSON handling and falsy Docker-config validation were additionally repaired with regressions.\n\n'+gates)
    write('compatibility.md','''# Official upstream review — 2026-10-16 IST

[DeerFlow releases](https://github.com/bytedance/deer-flow/releases) lists v2.1.0 as the latest published release, 2026-09-24. Jarvis remains pinned to reviewed source a5e71751d7a9f8f4a71ca458da3984fc1284d098, backend 2.2.0-dev/harness 2.1.0. Installed optional Python 3.12.14 metadata identifies deerflow-harness 2.1.0 and deerflow-extension-api 0.2.5, with LangChain/LangGraph/Pydantic versions in optional-runtime.json. An initial lookup for distribution name “deerflow” failed because the installed distribution is named deerflow-harness; this was not a missing-runtime finding. Module discovery succeeds; no live harness/model correctness claim. No install or source update ran.

Installed Linux Docker engine 29.8.2 matches the 2026-09-30 release. [Official 29.x release notes](https://docs.docker.com/engine/release-notes/29/) list newer 29.9.0 (2026-10-08) and 29.9.1 (2026-10-14), including containerd/daemon security fixes. The shared engine was not upgraded or restarted; platform patch currency is an unresolved production risk. The installed reviewed image digest matches runtime_manifest.json and was reused with --pull never; no build/download occurred. This audit does not certify the daemon/kernel against container escape.

[Docker run contract](https://docs.docker.com/engine/containers/run/) documents memory plus swap, capability, user and network controls. Actual fixture inspection verifies applied settings, rather than assuming command flags are proof. The filesystem monitor is polling, not a hard volume quota; /tmp remains executable for the existing speech library and confined to its job. Apt packages are not fully frozen in the existing image build recipe. No new dependency was declared; main Pillow is already used by Jarvis and now supplies PNG structure verification.

Firecrawl retrieved only public official docs/release pages; upstream-checks.json records URLs and cache provenance. Source-call citation checks are not content entailment or paywall bypass. All research/model/provider/installer approval, per-recipe readiness and dependency-migration gaps remain explicit; no paid API, account setup or new ability was installed.
''')
    fixes='''Retained fixes:

- Reject linked mount ancestors and non-immutable/wrong-architecture image IDs; pin new container IDs and target inspected IDs for exec/kill/cleanup.
- Bound and validate checkpoint reads; pending calls become uncertain on resume and cannot dispatch a different effect.
- Lock sandbox writes, use exclusive file creation, and apply the 20-effect budget consistently.
- Kill only the attested job after uncertain exec/timeout; preserve state and refuse replay.
- Validate Docker config types, including falsy non-object input; classify non-object worker JSON as a protocol error.
- Verify expected media files from disk with explicit format-specific proof levels.
- Replace whole-tree inventory materialization with bounded lexical traversal, preserving original per-file parent/link/resolved-root checks.

'''
    decisions=(metrics+' Retain final traversal. The first candidate was slower despite lower peak allocation (candidate-1 samples preserved); redundant whole-application ancestor checks per file were replaced with the original per-file root/link checks, while validating application ancestors at traversal/directory boundaries. '
        'Platform Path sorting is retained, including Windows case ordering. Filesystem/antivirus timing varies; this is not a general render/container/model speedup. Five initial iterations are not cold processes. '
        'Budgets can refuse oversized/deep directories; symlink/path checks are best effort and do not prove handle-based race containment. Media validation adds I/O and does not establish semantic content correctness. Checkpoint refusal and uncertainty can require manual inspection; no replay/reset is a repair.\n\n')
    write('rollback.md','# Rollback\n\nPreserved dirty audit/12-tool-registry at commit 9bf5528e6d490fc3bbe92d0c62bcffae6c0946b6. Preimages: .jarvis-runtime/jarvis-audit/module28-pre. Review source.patch/source-hashes.json and restore matching hunks only, preserving inherited/user/later changes; no reset to HEAD or personal file deletion.\n\nNo dependency/platform/config update occurred. Owned fixture containers were already removed and output files preserved. Keep state.json and uncertain call records; do not clear/replay jobs. Pause affected tasks before rollback: older code lacks pending-call fencing, ancestor guards, strict write budgets, inspected-ID cleanup and media proof. Re-run focused/readiness after rollback. No live rollback trial was executed.')
    write('commands.md','''# Commands and evidence

From app/, .venv/Scripts/python.exe:

- `-m pytest tests/test_docker_sandbox.py tests/test_deerflow.py -q --junitxml=artifacts/jarvis-audit/modules/28-sandbox-deerflow/baseline.xml`
- `-m pytest tests/test_sandbox_deerflow_audit.py -q --junitxml=artifacts/jarvis-audit/modules/28-sandbox-deerflow/reproduced.xml` (approved fixture permission after restricted-token attempt).
- Repair subsets: targeted-first.xml and targeted-second.xml.
- `-m pytest tests/test_sandbox_deerflow_audit.py tests/test_docker_sandbox.py tests/test_deerflow.py tests/test_audit_result_accounting.py -q --junitxml=artifacts/jarvis-audit/modules/28-sandbox-deerflow/cases-and-contracts.xml`
- `scripts/verification/verify_sandbox_deerflow_audit.py` — paired inventory A/B, no Docker/model workload.
- `scripts/verification/verify_sandbox_deerflow_container.py` — three explicitly owned, installed-image offline synthetic jobs, inspected cleanup; no engine startup, pull/build, account or personal input.
- `scripts/verification/verify_sandbox_deerflow_renderers.py` — six remaining installed offline recipes, sequential synthetic fixtures and inspected cleanup; stock narration CPU only, no audible playback.
- Freeze 392 runtime/test hashes using verify_whatsapp_audit.freeze with OUT set to modules/28-sandbox-deerflow.
- `-m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/28-sandbox-deerflow/full-regression.xml` (full-regression.log).
- `-m jarvis.launcher --check` (readiness.json).
- `scripts/verification/report_sandbox_deerflow_audit.py`; `scripts/verification/verify_sandbox_deerflow_artifacts.py`.

Read-only engine/image inspection and optional Python package metadata are recorded separately. Full tests-directory execution uses isolated fixtures; it does not rerun the real-container script. No blanket live research/GPU/media/production acceptance.
''')
    short=(f'**Sandbox/DeerFlow audit — 2026-10-16 IST:** Stronger mount/checkpoint/identity/write/timeout guards and media proof added. '
        f'**20 catalog fixture PASS / 12 BLOCKED**; full regression **{full["PASS"]:,} passed / {full["SKIPPED"]} skipped / 0 failures**, launcher **ready**. '
        'Owned offline math, all seven literal media recipes and nonzero/no-replay/cleanup fixtures passed; format proof levels vary. General research/source-quality, approval/quota/privacy/resource/recovery and platform patch acceptance remain incomplete.')
    for path,link in [(BASE/'README.md','artifacts/jarvis-audit/modules/28-sandbox-deerflow/inventory.md'),(BASE.parent/'README.md','app/artifacts/jarvis-audit/modules/28-sandbox-deerflow/inventory.md'),
        (BASE/'docs/deerflow.md','../artifacts/jarvis-audit/modules/28-sandbox-deerflow/inventory.md'),(BASE/'docs/deerflow-sandbox.md','../artifacts/jarvis-audit/modules/28-sandbox-deerflow/inventory.md'),(BASE/'docs/system-map.md','../artifacts/jarvis-audit/modules/28-sandbox-deerflow/inventory.md')]:
        marker(path,short+'\n[Evidence, limitations and rollback]('+link+').')
    guide=BASE/'docs/deerflow-sandbox.md';text=guide.read_text(encoding='utf-8')
    text=re.sub(r'\n## Current audit boundaries — 2026-10-16 IST\n.*\Z','',text,flags=re.S)
    text+='\n## Current audit boundaries — 2026-10-16 IST\n\n'
    text+=('New jobs pin a full immutable container ID; exec, uncertain-failure kill and cleanup use the inspected ID. Legacy checkpoints without that field retain image/label attestation. Mount checks include linked ancestors; this is not race-proof containment against a hostile host/daemon. '
        'Checkpoints are bounded to 524,288 characters and validate effect state; pending attempted/uncertain effects stop further dispatch after resume. Writes are locked/exclusive and share the 20-effect budget. Individual exec timeouts accept finite numbers from 1 to 120 seconds. '
        'Inventory returns at most 200 rows with platform lexical ordering; a directory over 1,000 entries, depth over 32 or traversal over 5,000 entries refuses bounded inspection. The existing filesystem monitor is not a hard quota. '
        'Free-media results now include verification: PNG structure/dimensions, PCM WAV readback, bounded PPTX ZIP/CRC, or PDF/MP4 envelope only. These do not prove document layout, video codecs/frames or factual content. '
        'Current actual validation covers all seven literal recipes plus synthetic math and a nonzero command in the already-installed offline image; all nine owned containers were cleaned. Narration used existing stock assets on CPU without playback. No paid service, installer, shared engine change, LLM or GPU work ran. '
        'Aggregate job admission, installer approval provenance, paywall/claim support, complete privacy traces and daemon-disconnect recovery remain unfinished. Docker 29.8.2 is older than the official 29.9.1 release checked today; no platform update was attempted.\n\n'
        '![Actual rendered synthetic Docker chart fixture](../artifacts/jarvis-audit/modules/28-sandbox-deerflow/fixture-chart.png)\n\nSynthetic PNG rendered and inspected on 2026-10-16; not a desktop screenshot or general model benchmark. Historical 2026-10-14 results above remain historical.\n')
    guide.write_text(text,encoding='utf-8')
    pairs=[];patches=[];changed=[]
    for old in sorted(PRE.iterdir()):
        if not old.is_file():continue
        rel='../README.md' if old.name=='root-README.md' else old.name.replace('__','/');now=BASE/rel
        changed.append(rel);pairs.append(dict(path=rel,before=sha(old),after=sha(now)))
        patches.extend(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),now.read_text(encoding='utf-8').splitlines(True),fromfile='before/'+rel,tofile='after/'+rel))
    for rel in ['tests/test_sandbox_deerflow_audit.py','scripts/verification/verify_sandbox_deerflow_audit.py','scripts/verification/verify_sandbox_deerflow_container.py','scripts/verification/verify_sandbox_deerflow_renderers.py','scripts/verification/report_sandbox_deerflow_audit.py','scripts/verification/verify_sandbox_deerflow_artifacts.py']:
        changed.append(rel);patches.extend(difflib.unified_diff([], (BASE/rel).read_text(encoding='utf-8').splitlines(True),fromfile='/dev/null',tofile='after/'+rel))
    write('source.patch',''.join(patches));write('source-hashes.json',json.dumps(pairs,indent=2));write('files-changed.json',json.dumps([dict(path=p,sha256=sha(BASE/p)) for p in changed],indent=2))
    write('changes.md','# Changes and keep/revert decisions\n\n'+fixes+decisions+'\n'.join('- `'+p+'`' for p in changed)+'\n\nModule/global generated artifacts are listed in generated-files.json. No commit/reset or unrelated diff was erased.')
    write('full-regression-skip-reasons.json',json.dumps([dict(node=n.get('classname','')+'::'+n.get('name',''),reason=n.find('skipped').get('message','')) for n in ET.parse(MOD/'full-regression.xml').iter('testcase') if n.find('skipped') is not None],indent=2))
    table='| Module/evidence | Status | PASS | BLOCKED | NOT RUN |\n| --- | --- | ---: | ---: | ---: |\n'
    for m in modules:
        counts=Counter(r['status'] for r in catalog if int(r['id'][4:6])==m['number']);label=f"{m['number']:02}-{m['module']}";link=f'modules/{label}/inventory.md'
        if (OUT/link).is_file():label=f'[{label}]({link})'
        table+=f"| {label} | {m['status']} | {counts['PASS']} | {counts['BLOCKED']} | {counts['NOT RUN']} |\n"
    report=f'''# Jarvis audit — Prompt 28, 2026-10-16 IST

**PARTIAL: 20 sandbox/DeerFlow catalog fixture PASS / 12 BLOCKED. No general production acceptance.**

Preserved dirty branch `audit/12-tool-registry`, commit `9bf5528e6d490fc3bbe92d0c62bcffae6c0946b6`, canonical `app/`. Main Python {env['python'].split()[0]}, {env['platform']}, RAM {env['ram_bytes']} bytes; optional Python {optional['python'].split()[0]}. Target RTX 3050 Laptop 4 GB from earlier census; no GPU/LLM workload. [Environment](modules/28-sandbox-deerflow/environment.json), [optional package metadata](modules/28-sandbox-deerflow/optional-runtime.json).

{scope}

## Source-map evidence

{matrix}

## Executed assertions and measurements

Baseline **30 passed**. Focused **{target['PASS']} PASS / {target['SKIPPED']} explicit BLOCKED skips / 0 FAIL**. Full Python tests-directory **{full['PASS']} PASS / {full['SKIPPED']} skipped / 0 FAIL in {full['seconds']:.3f}s** (JUnit suite time; console wall time in log), one existing COM-threading warning. Launcher dependency/configuration readiness **{ready['status']}**, optional Groq not live checked. Actual installed-image offline fixture checks passed math=4, UID/isolation, all seven literal recipes with declared format proof levels, nonzero→uncertain/stopped/no replay, and cleanup of only owned containers. No current live DeerFlow LLM/research or general media quality acceptance claim.

{metrics} [Raw samples](modules/28-sandbox-deerflow/benchmarks.csv). Keep final traversal; first slower candidate is preserved. Five initial iterations are not cold process starts. No TTFT/audio/network/model/container/render/RSS/VRAM speed claim.

All {len(frozen)} frozen runtime/test files remained unchanged during the full run. [Hashes](modules/28-sandbox-deerflow/full-start-source-hashes.json), [full log](modules/28-sandbox-deerflow/full-regression.log), [XML](modules/28-sandbox-deerflow/full-regression.xml), [skip reasons](modules/28-sandbox-deerflow/full-regression-skip-reasons.json), [container receipt](modules/28-sandbox-deerflow/container-fixture.json), [other recipe receipts](modules/28-sandbox-deerflow/renderer-fixtures.json), [source inventory](modules/28-sandbox-deerflow/source-inventory.json), [repro/failure history](modules/28-sandbox-deerflow/failures.md), [commands](modules/28-sandbox-deerflow/commands.md), [changed files](modules/28-sandbox-deerflow/files-changed.json), [diff](modules/28-sandbox-deerflow/source.patch), [upstream URLs/dates](modules/28-sandbox-deerflow/compatibility.md), [retrieval metadata](modules/28-sandbox-deerflow/upstream-checks.json), [rollback](modules/28-sandbox-deerflow/rollback.md).

## Exact 1,184-case accounting

**{json.dumps(summary['catalog_counts'])}**. Every Prompt 28 case has executed assertions or an explicit blocker; narrower passed tests never override incomplete full-case contracts. Historical module evidence and metrics remain linked.

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

The Docker daemon/kernel is a trusted boundary, not a proven escape-proof sandbox. Latest platform security releases were researched but not installed. Link checks are not atomic filesystem-handle containment; legacy jobs lack pinned container IDs and locks are per instance/process. Pending effects refuse replay and may require manual inspection. Media proof levels differ: envelope checks do not establish full decodability or content correctness. Source receipts establish source-call provenance, not paywall access, claim support or comprehensive privacy. These gaps prevent production certification.

## Resume

Next incomplete module case **JRV-28-005**; global oldest unresolved **{summary['next_case']}**; next untouched module **29/JRV-29-001**. [Exact module IDs](modules/28-sandbox-deerflow/remaining-case-ids.txt), [global IDs](remaining-case-ids.txt). Complete approval provenance and process-wide admission, renderer readiness, paywall/source-quality/entailment, typed results, privacy/negation/resource/trace and disconnect cleanup contracts. Follow commands.md, freeze sources, run full/readiness, reconcile and verify artifacts. Shared-engine/platform/dependency installations, untrusted installers and real account actions require separate explicit authorization. [Previous Prompt 27 report](final-report-before-module28.md) preserves earlier results.
'''
    (OUT/'final-report.md').write_text(report,encoding='utf-8')
    generated={p.relative_to(BASE).as_posix() for p in MOD.iterdir() if p.is_file()}
    generated.update((OUT/n).relative_to(BASE).as_posix() for n in ('final-report.md','final-report-before-module28.md','module-map.json','test-results.jsonl','executed-tests.jsonl','summary.json','remaining-case-ids.txt'))
    generated.update((MOD/n).relative_to(BASE).as_posix() for n in ('generated-files.json','artifact-verification.json'));write('generated-files.json',json.dumps(sorted(generated),indent=2))
    print(json.dumps(dict(module28=Counter(r['status'] for r in cases),focused=target,full=full,container_fixture='PASS',global_catalog=summary['catalog_counts']),indent=2))


if __name__=='__main__':main()
