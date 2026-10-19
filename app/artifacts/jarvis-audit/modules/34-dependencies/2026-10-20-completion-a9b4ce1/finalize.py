"""Package observed evidence only; no installation, download or runtime repair."""
import csv
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
import tracemalloc
import types
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
APP = next(p for p in OUT.parents if (p / 'main.py').is_file())
ROOT = APP.parent
OLD = OUT.parent / '2026-10-20-independent-146ba83'
SHA = 'a9b4ce1e06cd384f6862bbea8c19cb99b97c42f6'
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip() == SHA
sys.path.insert(0, str(APP))

def write(name, value):
    (OUT / name).write_text(value.rstrip() + '\n', encoding='utf-8')

def dump(name, value):
    write(name, json.dumps(value, indent=2, ensure_ascii=False))

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

normalization = {}
for path in list(OUT.glob('*.xml')) + list(OUT.glob('*.txt')):
    original = digest(path)
    value = path.read_text(encoding='utf-8-sig')
    for source, target in [(str(APP), '%AUDIT_APP%'), ('D:\\Kunals GitHub Repo\\Jarvis\\app', '%INSTALL_APP%'),
                           (os.environ.get('USERPROFILE', 'NO_PROFILE'), '%USERPROFILE%')]:
        for spelling in {source, source.replace('\\', '/'), source.replace('\\', '\\\\')}:
            value = value.replace(spelling, target)
    path.write_text(value, encoding='utf-8')
    normalization[path.name] = {'before': original, 'saved': digest(path)}
dump('log-path-normalization.json', normalization)

runs = {}
records = []
for label in ['before-local-fixes', 'targeted-final', 'remaining-routes-final', 'baseline-replay', 'final-regression']:
    rows = []
    tree = ET.parse(OUT / (label + '.xml')).getroot()
    for case in tree.iter('testcase'):
        skip = case.find('skipped')
        status = ('FAIL' if case.find('failure') is not None or case.find('error') is not None
                  else 'SKIPPED' if skip is not None else 'PASS')
        rows.append({'id': case.get('name'), 'classname': case.get('classname'), 'status': status,
                     'seconds': float(case.get('time', 0)), 'reason': skip.get('message') if skip is not None else '',
                     'run': label, 'base_sha': SHA, 'source': 'base + local patch' if label != 'before-local-fixes' else 'base',
                     'evidence': label + '.xml'})
    runs[label] = {s: sum(r['status'] == s for r in rows) for s in ['PASS', 'FAIL', 'SKIPPED']}
    runs[label]['seconds'] = sum(float(s.get('time', 0)) for s in tree.iter('testsuite'))
    records.extend(rows)
assert runs['final-regression']['PASS'] == 227 and runs['final-regression']['FAIL'] == 0
write('executed-results.jsonl', '\n'.join(json.dumps(r) for r in records))
dump('baseline.json', {'date': '2026-10-20', 'base_sha': SHA, 'source': 'a9b4ce1 + source.patch and source-hashes.json',
     'runs': runs, 'headline_run': 'final-regression', 'overlapping_runs_not_summed': True,
     'test_process_peak_memory': 'NOT MEASURED', 'real_installs': 0, 'real_model_downloads': 0,
     'scope': 'Installed-dependency test runner, mocks/disposable fixtures; read-only native imports/metadata separately recorded.'})

source_paths = ['jarvis/repair_authorization.py', 'jarvis/launcher.py', 'jarvis/model_recovery.py',
                'scripts/setup/setup_brain.py', 'tests/test_prompt34_completion.py', 'tests/test_prompt34_remaining_routes.py']
dump('source-hashes.json', {p: digest(APP / p) for p in source_paths})
patch = subprocess.check_output(['git', 'diff', '--', 'app/jarvis/repair_authorization.py'], cwd=ROOT)
(OUT / 'source.patch').write_bytes(patch)
dump('prior-evidence-hashes.json', {p.name: digest(p) for p in OUT.parent.iterdir() if p.is_file()})
assert digest(OUT / 'test_dependency_boundaries.py') == digest(OLD / 'test_dependency_boundaries.py')

# Retain snapshot provenance rather than presenting the earlier inventory as a fresh rescan.
snapshot_names = ['environment-sbom.json', 'dependency-graph.json', 'lockfile-map.json', 'worker-interpreters.json',
                  'os-gpu-tools.json', 'cve-applicability.json']
for name in snapshot_names:
    (OUT / name).write_bytes((OLD / name).read_bytes())
dump('inventory-provenance.json', {'snapshot': '../' + OLD.name, 'snapshot_base': '146ba83',
     'copied_byte_identically': {name: digest(OUT / name) for name in snapshot_names},
     'fresh_checks': ['pip-checks.json', 'torch-import-readback.json', 'playwright-readback.json', 'launcher-check.txt'],
     'packages_changed': False})

# A fixed pure parser fixture compares pre-fix and current code, not installation/startup performance.
from jarvis import repair_authorization as current
prior = types.ModuleType('prompt34_prior_auth')
sys.modules[prior.__name__] = prior
exec(compile(subprocess.check_output(['git', 'show', SHA + ':app/jarvis/repair_authorization.py'], cwd=ROOT),
             '<pinned-prior-auth>', 'exec'), prior.__dict__)
fixture = 'fixture==1 --hash=sha256:' + 'a' * 64
measure = []
for label, module in [('before', prior), ('after', current)]:
    for _ in range(20):
        module.locked_requirements(fixture)
    samples = []
    tracemalloc.start()
    for _ in range(300):
        started = time.perf_counter_ns()
        assert module.locked_requirements(fixture) == ['fixture==1']
        samples.append((time.perf_counter_ns() - started) / 1e6)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    measure.append({'revision': label, 'source': SHA if label == 'before' else SHA + '+source.patch',
                    'fixture': 'pure valid hash-lock parser', 'samples': 300, 'p50_ms': statistics.median(samples),
                    'p95_ms': sorted(samples)[284], 'operation_traced_peak_bytes': peak})
with (OUT / 'benchmarks.csv').open('w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=list(measure[0])); writer.writeheader(); writer.writerows(measure)
dump('benchmark-provenance.json', {'warmup': 20, 'iterations': 300, 'fixture': fixture,
     'scope': 'Pure validator only. No model, install, startup, throughput or end-to-end latency claim.'})

previous = [json.loads(s) for s in (OLD / 'tests.jsonl').read_text(encoding='utf-8-sig').splitlines() if s.strip()]
updates = {
 4: ('PASS', 'Missing-model diagnosis/fallback and no-default-download fixtures pass; no live inference.'),
 5: ('BLOCKED', 'Fresh driver readback: bundled Chromium missing. No browser install or configured system-channel acceptance.'),
 11: ('BLOCKED', 'Original unapproved/low-disk admission reproduced as fixed. Authorized mutable-tag pull still has revision/byte-budget race; see handoff P34-R1.'),
 12: ('PASS', 'Offline/no-default-install and hash-lock/authorization guards pass with intercepted executors. Full clean offline rebuild remains BLOCKED under case 001.'),
 14: ('PASS', 'Injected unavailable local embed endpoint: real ReasoningBank learn/retrieve returns lexical fallback and reports unavailable embedding. Synthetic fixture, no model loaded.'),
 18: ('PASS', 'Synthetic XLSX macro and signature ZIP fixtures refused before worker/approval; bytes unchanged. Native proprietary workbook roundtrip remains BLOCKED.'),
 21: ('PASS', 'Unapproved/offline repair and model admission fixtures pass with no install/download executors. Does not certify approved immutable model transport.'),
}
cases = []
for row in previous:
    number = int(row['id'].rsplit('-', 1)[1])
    status, reason = updates.get(number, (row['status'], row['reason']))
    cases.append({'id': row['id'], 'status': status, 'reason': reason, 'date': '2026-10-20', 'base_sha': SHA,
                  'source': 'base + source.patch', 'previous_status': row['status'],
                  'evidence': 'executed-results.jsonl; final-regression.xml; inventory-provenance.json; ../../../../../docs/CLAUDE_HANDOFF.md'})
write('tests.jsonl', '\n'.join(json.dumps(row) for row in cases))

write('inventory.md', '''# Prompt 34 inventory — 2026-10-20

Isolated codex-review, base a9b4ce1e06cd384f6862bbea8c19cb99b97c42f6 plus local source.patch and new tests (source-hashes.json). The original checkout and user config were not edited. The user's latest policy authorizes safe local repairs and continued independent work; it supersedes earlier read-only/first-blocker stop instructions. Root/app AGENTS apply. Master contract was unavailable; supplied reconciliation contract and numbered prompt were read.

Ten installed environments are mapped by exact executable suffix and distribution metadata in environment-sbom.json, dependency-graph.json, lockfile-map.json and worker-interpreters.json. Those files are byte-identical earlier 2026-10-20 snapshots, not a new metadata scan; inventory-provenance.json identifies them. Fresh pip checks passed in all ten; pip-less UV workers used existing main pip with --python, without installing pip. Fresh brain/F5/training imports passed; F5/training report CUDA 12.4 available, brain is CPU. No tensor/kernel/model/training workload was run.

Snapshot: RTX 3050 Laptop 4096 MiB, driver 610.74, Node 24.14.0, npm 11.11.1, Ollama 0.40.0, Docker 29.8.2, WSL 2.6.1. nvcc not found on PATH is not proof toolkit absent. Eighteen local Ollama tags were previously enumerated; no inference. Pip cache/nine wheels are not a complete approved wheelhouse. No package/model/driver mutation. Private roots are aliased; suffixes retain interpreter routing.
''')
write('changes.md', '''# Completed local work

Hardened jarvis/repair_authorization.py: consume the full hashed lock entry (refuse trailing pip options/remote source injection), require finite numeric bounded expiry, restrict authorization IDs used in paths, require a real boolean network permission, enforce positive integer dependency budget, and claim single-use grants with a persistent native OS file lock. A thread race formerly admitted two consumers; the repaired regression admits one. Persistent lock files release ownership on process close/crash and are deliberately not unlinked.

Added fourteen authorization regressions and three embedding/XLSX fallback tests. Before local fixes: 13 FAIL / 1 PASS; final targeted run: 52 PASS. The first concurrency test synchronization needed correction, and a fallback test initially used the wrong ReasoningBank return shape; intermediate logs remain as development history, not app defects. Final relevant run after the final production edit: 227 PASS / 1 SKIPPED / 0 FAIL. Overlapping runs are not summed. Original four boundary tests are byte-identical and pass. Author-reported 3,511 results are historical, not our independent full-suite result.

Updated root workflow guidance, both READMEs, recovery guide and cumulative Claude handoff. No dependency version changed, no deployment/commit/merge, no real install/download. No UI change or screenshot applicable.
''')
write('failures.md', '''# Remaining limits and open review findings

No final executed regression failed. One skipped forced CUDA interruption test remains a release gate. Original P34-001 and P34-002 default unapproved admission reproductions now pass; full approved installer/download acceptance is not established.

P34-R1 (open source-review safety finding): setup_brain.approved_pull verifies digest and byte size for a registry tag, then pulls the mutable tag. The tag can change between checks; post-pull digest validation happens after download and cannot enforce the original byte budget. No registry exploit/download was attempted. Exact immutable transport needs implementation and injected race tests before approved downloads are release-ready.

P34-R2 (unverified compatibility risk): stage_environment builds a venv under a temporary name and renames it. Generated console scripts may embed the old absolute path. Import checks alone do not establish relocated executable correctness. No real install/rebuild was authorized; validate executables or redesign routing before promotion.

P34-R3 (unverified artifact race): lock and wheelhouse are checked then read again by pip. Hash requirements protect selected artifacts but do not freeze the reviewed lock against concurrent mutation. Snapshot/validate immutable artifacts at execution and test changes between check and launch. No exploit executed.

All remaining numbered-case acceptance limits and earlier prompt gaps are tracked in [Claude handoff](../../../../../docs/CLAUDE_HANDOFF.md). Continue safe independent work; these limits do not authorize installs, downloads, drivers or live side effects.
''')
write('cross-pillar-matrix.md', '''# Final relevant cross-system regression

| Seam | Fresh executed evidence | Acceptance limit |
|---|---|---|
| Recovery / manifest / paths | Launcher, recovery, health, baseline and original repair boundaries pass | Actual staged install/rollback not run |
| Model routing / F5 / Whisper / GPU | Model selection, Ollama, trained coder, F5 and scheduler regressions pass | Physical mic/TTS under pressure and forced CUDA interruption blocked |
| AZR / inference | Budget/lease guards pass; native torch imports pass | No actual training/checkpoint/preemption roundtrip |
| Pillar A/MCP / isolation | All ten pip checks pass; previous Prompt 33 309-pass evidence retained as historical | Plugin migration and concurrent package mutation not performed |
| Pillar B / embeddings | Unavailable local embedding fixture falls back to lexical retrieval | No live vector-quality evaluation |
| DGM / evaluator | Protected-source fixture passes | No candidate env migration |
| API-first fidelity / engines | DOCX guards, XLSX macro/signature byte preservation and Blender unsafe-input guards pass | Proprietary native roundtrip / installed Blender or Unreal acceptance blocked |
| Cloud / demonstration / recovery | Malicious cloud output inert; cancellation/restart no replay fixtures pass | No paid/cloud payload, real demonstration or account action |

Full per-test IDs and outcomes: executed-results.jsonl / final-regression.xml. These are fixture tests, not live acceptance certificates.
''')
write('compatibility.md', '''# Compatibility — before/after and installed runtimes

Pre-local-fix authorization fixture: 13 failures / 1 pass. Post-fix combined targeted suite: 52 passes; final relevant suite: 227 passes / 1 skip / no failures. Four original intercepted boundary reproductions pass unchanged. Native import and pip-check readbacks are separate from mocked regression evidence. torch 2.6.0+cpu in brain; torch/torchaudio 2.6.0+cu124 in F5; training torch 2.6.0+cu124. Driver visibility is not a complete ABI/inference certificate.

Bundled Playwright Chromium is absent (fresh readback); system Chrome route not certified. Launcher --check exits 1 / repair_required in the isolated checkout: env/assets absent there, Docker and Ollama endpoints unavailable there. Original installed environments were not copied. Snapshot local Ollama inventory does not establish current service readiness.

No clean hash-locked offline install, unsupported-major migration, incompatible-plugin install, uninstall, concurrent-worker package update or actual relocation test. Requirements remain partly ranged/unhashed. The reported caches are not a certified wheelhouse. Preserve separate F5/brain envs: differing transformer/torch groups can be intentional. See handoff for every remaining acceptance gate.
''')
write('security.md', '''# Security — scope and remaining gates

Final executor authorization tests reject trailing pip option injection, malformed IDs, invalid expiry and non-boolean network permission; concurrent grant consumers admit one. All real install/download executors in these tests are intercepted. Read-only pip checks/imports/driver metadata were executed; no credentials, private recording or unrelated desktop contents exported. App/profile roots in raw logs are aliased with original/saved hashes recorded.

Earlier same-day limited advisory review is carried with provenance, not presented as a fresh exhaustive vulnerability scan: [pypdf maintainer record](https://github.com/py-pdf/pypdf/security/advisories/GHSA-9m86-7pmv-2852) affects versions below 6.7.5; main 6.20.0 is outside that particular range. [Transformers reviewed record](https://github.com/advisories/GHSA-x9r9-c232-4q39) includes installed brain/training 4.57.6; F5 4.44.2 is outside its reported range. Source reachability remains unverified, not proven exploited or safe; no speculative upgrade or exploit performed. Review exact call paths and supported remediation in staged envs. Full CVE/license/transitive scan remains blocked.

Approved mutable-tag download and mutable lock execution still need final-boundary work (P34-R1/R3). Single-use grant lock passes thread and separate Windows process contention/crash-release probes (grant-process-readback.json). POSIX branch and adversarial local filesystem access were not independently executed.
''')
write('rollback.md', '''# Rollback / offline reproducibility

No package/model migration or uninstall occurred, so actual package rollback is NOT RUN. Source patch is reviewable and reversible; preserve new tests/evidence and revert only that patch if rejecting it, never reset user work. Do not claim a documented rollback plan is tested uninstall proof.

For authorized follow-up: produce complete per-interpreter Windows/native/CUDA hash locks and wheelhouse; snapshot the approved artifact set; stage without replacing running workers; verify imports, CLI entrypoints, dependency graph, ABI/fidelity and enabled/disabled routes; compare actual readback; preserve old env/weights and switch routing only after postconditions. Exercise failed promotion and restored routing in a disposable fixture, then authorize real promotion separately. Venv relocation must be addressed first. No blind deletion/recreation or download is authorized by this report.
''')
write('codex-findings-reconciliation.md', '''# Finding-by-finding reconciliation

| ID | Before | Current evidence | Status / revision |
|---|---|---|---|
| P34-001 | 146ba83 startup missing import admitted pip without consent | Original JRV-34-012 boundary passes unchanged in final run | Default behavior fixed in a9b4ce1; lock/grant boundary hardened by local source.patch |
| P34-002 | 146ba83 low disk/no consent admitted model setup | Original JRV-34-011 boundary passes unchanged | Default behavior fixed in a9b4ce1; approved immutable-download safety still open P34-R1 |
| P34-local authorization defects | a9b4ce1: 13 failures/1 pass in new malicious/concurrent tests | 52 targeted pass, final relevant 227 pass/1 skip | Fixed in uncommitted source.patch, hashes identify exact files |
| P34-R1 | Mutable tag after manifest check | Code review, no live exploit | OPEN: implement immutable bounded transport |
| P34-R2 | Renamed staging venv | Code review only | UNVERIFIED: executable relocation acceptance |
| P34-R3 | Mutable lock/wheelhouse between check and execution | Code review only | UNVERIFIED: immutable snapshot acceptance |

Stable original case catalog was available and joined; revised 001–022 dispositions are in tests.jsonl. No planned row promoted to live acceptance. Exact target, neighbor and cross-system IDs are in executed-results.jsonl. Local repairs have no commit SHA yet: use base + patch + hashes. Earlier author 3,511 suite is separate historical evidence.
''')
write('verdict.md', '''# Prompt 34 — safe local work completed; release NOT READY

2026-10-20, isolated codex-review base a9b4ce1 plus source.patch/new tests. Final relevant regression: **227 PASS / 0 FAIL / 1 SKIPPED** in 32.77 seconds. All ten installed env pip checks pass, and brain/F5/training native imports pass. Original unapproved install/download reproductions pass unchanged. Additional lock/authorization/concurrency defects were fixed locally.

Full module acceptance remains BLOCKED: immutable model revision/byte-budget transport, staged venv executable relocation, approved artifact snapshot, real clean offline install/rollback, CVE remediation reachability and live training/GPU/voice/engine/WSL gates are incomplete. No deployment. No package install, model download, driver change or actual model workload.

[Changes](changes.md) · [Cases](tests.jsonl) · [Results](baseline.json) · [Open findings](failures.md) · [Cumulative Claude handoff](../../../../../docs/CLAUDE_HANDOFF.md).
''')

recon = APP / 'artifacts/jarvis-audit/reconciliation/34-2026-10-20-completion-a9b4ce1'
recon.mkdir(exist_ok=True)
for name, origin in [('artifact-inventory.md', 'inventory.md'), ('patch-assessment.md', 'changes.md'),
                     ('unresolved.md', 'failures.md'), ('handoff.md', 'verdict.md')]:
    (recon / name).write_text('See [current packet](../../modules/34-dependencies/' + OUT.name + '/' + origin + ').\n', encoding='utf-8')
(recon / 'review-revisions.json').write_text(json.dumps({'base': SHA, 'fix_sha': None, 'local_patch_sha256': digest(OUT / 'source.patch')}, indent=2), encoding='utf-8')
with (recon / 'findings-ledger.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(['finding', 'status', 'revision'])
    for key, status in [('P34-001', 'FIXED default; local hardening'), ('P34-002', 'FIXED default; approved transport OPEN'),
                        ('P34-R1', 'OPEN'), ('P34-R2', 'UNVERIFIED'), ('P34-R3', 'UNVERIFIED')]:
        w.writerow([key, status, SHA + '+source.patch'])
for name, selected in [('repro-results.jsonl', 'targeted-final'), ('legacy-regressions.jsonl', 'baseline-replay'),
                        ('cross-pillar-regressions.jsonl', 'final-regression')]:
    (recon / name).write_text('\n'.join(json.dumps(r) for r in records if r['run'] == selected) + '\n', encoding='utf-8')
print(json.dumps({'final': runs['final-regression'], 'numbered_cases': len(cases), 'packet': OUT.name}))
