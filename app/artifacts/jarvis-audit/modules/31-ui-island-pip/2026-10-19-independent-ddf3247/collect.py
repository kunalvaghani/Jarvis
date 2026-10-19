"""Collect fresh Prompt 31 evidence. Does not edit application or prior audit files."""
import csv
import hashlib
import json
from pathlib import Path
import platform
import queue
import statistics
import subprocess
import sys
import threading
import time
import tracemalloc
import types
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
BASE = next(p for p in OUT.parents if (p / 'jarvis').is_dir() and (p / 'main.py').is_file())
ROOT = BASE.parent
sys.path.insert(0, str(BASE))
SHA = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
assert SHA == 'ddf3247fd3d5ee6b151287c6cba358e8707090c6'
OLD = '5b56f84c1604de87bb8845027dffb5ce5943243b'
FIX = '1dd3e9c841fba8f439be0d1116e9a0c91da8c447'
DATE = '2026-10-19 IST'
RUN = OUT.name
RECON = BASE / 'artifacts/jarvis-audit/reconciliation' / RUN


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data, encoding='utf-8')


def dump(path, value):
    write(path, json.dumps(value, indent=2) + '\n')


def doc(name, body):
    write(OUT / name, f'# Prompt 31 independent continuation — {DATE}\n\n{body.strip()}\n')


def read_xml(filename):
    rows = []
    for case in ET.parse(OUT / filename).iter('testcase'):
        issue = next((case.find(k) for k in ('failure', 'error', 'skipped') if case.find(k) is not None), None)
        status = 'PASS' if issue is None else 'SKIPPED' if issue.tag == 'skipped' else 'FAIL'
        rows.append({'id': case.get('classname') + '::' + case.get('name'), 'status': status,
                     'seconds': float(case.get('time', '0')), 'evidence': filename,
                     'message': issue.get('message', '') if issue is not None else ''})
    return rows


def counts(rows):
    return {s: sum(r['status'] == s for r in rows) for s in ('PASS', 'FAIL', 'SKIPPED')}


files = ['approval-reverification.xml', 'receipt-replay.xml', 'relevant-regression.xml',
         'ability-registry-regression.xml', 'cross-pillar-dependency-retest.xml', 'widget-journey.xml']
runs = {f: read_xml(f) for f in files}
dump(OUT / 'baseline.json', {'date': DATE, 'claude_pinned': SHA, 'fix_commit': FIX, 'previous_pin': OLD,
     'python': sys.version, 'interpreter': sys.executable, 'platform': platform.platform(),
     'scope': 'independent source unchanged; fixtures/native offscreen components, not whole-assistant acceptance',
     'runs': {f: counts(rows) for f, rows in runs.items()}, 'source_fix_applied_by_codex': False,
     'full_repository_regression': 'NOT RUN: renewed safety acceptance stop gate',
     'master_contract': 'unavailable in repository and exact Downloads companion path',
     'reconciliation_contract': 'Downloads/10_CODEX_FINDINGS_RECONCILIATION.md read-only Codex confirmation',
     'source_memory_measurement': 'per-operation synthetic traced allocation; no process/GPU soak measurement'})
write(OUT / 'executed-tests.jsonl', ''.join(json.dumps(r) + '\n' for rows in runs.values() for r in rows))

# Hash prior evidence without overwriting it. Python caches are not audit evidence.
prior_dirs = [BASE / 'artifacts/jarvis-audit/codex-independent-review',
              OUT.parent / '2026-10-19-independent-5b56f84', OUT.parent / '2026-10-19-claude-repair']
prior = {p.relative_to(BASE).as_posix(): sha(p) for directory in prior_dirs for p in directory.rglob('*')
         if p.is_file() and '__pycache__' not in p.parts}
prior.update({p.relative_to(BASE).as_posix(): sha(p) for p in OUT.parent.iterdir() if p.is_file()})
dump(OUT / 'prior-artifact-hashes.json', prior)
sources = ['main.py', 'jarvis/island_desk.py', 'jarvis/approval_receipt.py', 'jarvis/repo_abilities.py',
           'jarvis/ui_events.py', 'jarvis/tools.py', 'jarvis/actions.py', 'jarvis/demonstration.py',
           'jarvis/file_drop.py', 'jarvis/launcher.py', 'jarvis/recovery.py']
dump(OUT / 'source-hashes.json', {p: sha(BASE / p) for p in sources})

# Paired warm positive-control microbenchmark: exact earlier code vs pinned new code.
# No widget construction, real user input, model, network or external action.
from jarvis.island_desk import Approval
old_source = subprocess.check_output(['git', 'show', OLD + ':app/jarvis/island_desk.py'], cwd=ROOT, text=True)
module = types.ModuleType('jarvis._prompt31_prior')
module.__package__ = 'jarvis'
exec(compile(old_source, '<pinned-5b56f84-island_desk>', 'exec'), module.__dict__)


def operation(cls):
    result = {}
    card = cls(('fixture', 'public benchmark scope', result, threading.Event(), lambda: False))
    assert card.decide(True) is True and result['approved'] is True


samples = {'before': [], 'after': []}
for n in range(300):
    order = [('before', module.Approval), ('after', Approval)]
    if n % 2:
        order.reverse()
    for label, cls in order:
        start = time.perf_counter_ns()
        operation(cls)
        samples[label].append((time.perf_counter_ns() - start) / 1e6)
profiles = {}
for label, cls in [('before', module.Approval), ('after', Approval)]:
    tracemalloc.start()
    operation(cls)
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    values = sorted(samples[label])
    profiles[label] = {'commit': OLD if label == 'before' else SHA, 'n': len(values),
                       'p50_ms': statistics.median(values), 'p95_ms': values[int(len(values)*.95)],
                       'traced_peak_bytes': peak}
dump(OUT / 'resource-profile.json', {'scope': 'warm synthetic Approval construction/positive decision only; no render/voice latency',
                                    'profiles': profiles, 'samples_ms': samples})
with (OUT / 'benchmarks.csv').open('w', encoding='utf-8', newline='') as stream:
    writer = csv.writer(stream)
    writer.writerow(['revision', 'scenario', 'n', 'p50_ms', 'p95_ms', 'traced_peak_bytes', 'scope'])
    for row in profiles.values():
        writer.writerow([row['commit'], 'card_create_approve_positive_control', row['n'], row['p50_ms'],
                         row['p95_ms'], row['traced_peak_bytes'], 'synthetic; no end-user improvement claim'])

# Five concurrent synthetic event producers; terminal events must be retained.
from jarvis.ui_events import UIEventBuffer
buffer = UIEventBuffer()
def produce(task):
    for n in range(200):
        buffer.put(('answer_stream', {'task_id': task, 'phase': 'draft', 'text': 'x'*(n+1)}))
    buffer.put(('answer_error', {'task_id': task, 'status': 'cancelled'}))
threads = [threading.Thread(target=produce, args=(str(n),)) for n in range(5)]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()
trace = []
while True:
    try:
        kind, value = buffer.get_nowait()
        trace.append({'kind': kind, 'task_id': value['task_id'], 'characters': len(value.get('text', ''))})
    except queue.Empty:
        break
assert len([r for r in trace if r['kind'] == 'answer_error']) == 5
dump(OUT / 'event-trace.json', {'scope': 'five synthetic producers; no renderer/executor',
                               'coalesced': buffer.coalesced, 'events': trace})

previous_cases = OUT.parent / '2026-10-19-independent-5b56f84/tests.jsonl'
rows = [json.loads(line) for line in previous_cases.read_text(encoding='utf-8').splitlines() if line.strip()]
for row in rows:
    row['sha'] = SHA
    row['date'] = DATE
    if row['id'] == 'JRV-31-003':
        row.update(status='PASS', reason='Fresh offscreen real-Tk request/card readback/close-denial fixture PASS; no external executor.')
    elif row['id'] == 'JRV-31-013':
        row.update(status='FAIL', reason='P31-001 callback fix passes. P31-002 synthetic identical-text receipt replay accepted by both final requesters; no new-card decision.')
    elif row['id'] == 'JRV-31-020':
        row.update(status='FAIL', reason='Five-producer queue terminal events retained; final-requester receipt reuse still succeeds in synthetic injection. Full restart journey not run.')
    elif row['id'] == 'JRV-31-002':
        row.update(status='BLOCKED', reason='Widget text matches intended fixture scope; no uniform requester-owned request ID/tool/argument/identity/expiry binding. P31-002 remains.')
    elif row['id'] == 'JRV-31-015':
        row.update(status='BLOCKED', reason='Disposable UIA component passes this run. Physical focus-switch demonstration acceptance remains not run.')
write(OUT / 'tests.jsonl', ''.join(json.dumps(r) + '\n' for r in rows))
catalog = {r['id']: r for r in (json.loads(line) for line in (OUT.parent / 'tests.jsonl').read_text(encoding='utf-8').splitlines() if line.strip())}
write(OUT / 'catalog-join.jsonl', ''.join(json.dumps({'id': row['id'], 'current': row,
      'historical': catalog.get(row['id']), 'semantics': 'same original user case' if i < 12 else 'revised targeted case; same old ID has different semantics'}) + '\n'
      for i, row in enumerate(rows)))

doc('inventory.md', f'''Pinned **{SHA}** (`claude`) in `codex-review`; source repair **{FIX}**. Only fast-forwarded the audit branch. Original user config remains untouched. Prior README audit notes are preserved in previous-readme-notes.patch; previous packets remain unchanged. [Baseline/environment](baseline.json), [source hashes](source-hashes.json), [all executed rows](executed-tests.jsonl), [stable catalog join](catalog-join.jsonl).

Read the actual repair diff/record, Prompt 31, app/AGENTS.md, prior system/Phase 1–8 inventory and independent findings. Master contract remains unavailable; companion reconciliation reserves source repairs for Claude and Codex independent confirmation. No application source repair by Codex.

Pipeline: `Actions._approve` → `App.request_approval` → approval payload/`UIEventBuffer` → `IslandDesk.Approval` → widget or bound voice callback → shared answer/Event → requester. `Approval.token` is generated at card creation; `approval_digest` hashes kind + NUL + detail. UI decisions validate token. Both `App.request_approval` and `AbilityForge.ask` validate digest but never compare the token to a requester-owned expected ID. They also do not consume receipts in a requester-side one-use registry. That is the independently reproduced P31-002 gap.

Normal corrected UI callback behavior is verified independently. Forged-response tests model a response-seam replay; a remote attack path is not demonstrated. Remaining full identity/scope/expiry/Verify, physical secure-field/DPI/voice/UI crash and optional-worker acceptance requirements remain incomplete.''')
doc('failures.md', '''**P31-001: FIXED for the original callback/queue-head defect.** The unchanged original four tests pass; all nine repair tests pass (13 executions, including four duplicate scenarios). Source fix is 1dd3e9c. No claim that these establish the entire approval protocol.

**P31-002: FAIL — final requester does not bind a receipt to a unique pending request. Priority P1 for the mandated authorization acceptance gate; external exploitability UNVERIFIED.** A legitimate approved card A and a later card B have equal kind/detail and equal text digest, but different random tokens. Fault injection delivers A's saved answer into B's response. Both App.request_approval and AbilityForge.ask return True although B.done is False and no decision was made on B. UI rejects A's token when directly used against B; the requester omits that comparison. Two independent parameterized requester cases fail; three cancellation/expiration/UI-identity controls pass. [Fixture](test_receipt_replay.py), [actual failures](receipt-replay.txt), [XML](receipt-replay.xml). No real account/file/shell side effect occurred; optional simulated effect is a local list only.

This is a protocol/fault-injection finding, not proof an attacker can write the in-process response object. Do not claim remote exploitation. It falsifies the requested stale/forged-response rejection at the final acceptance seam and shows text identity alone cannot establish unique request identity.

**Environment failure:** relevant regression 303 PASS / 1 FAIL / 8 SKIPPED. Phase 8 flow A selected no xlsx API because the isolated checkout lacks .venv-skills. With already-installed interpreter paths routed read-only, the same full flow passes (1 PASS); audited source remains in this checkout. No installation or source weakening. Baseline and retest stay distinct. Prior Tcl/UIA instability was not reproduced in this combined run; that does not establish indefinite stability.

Full argument/identity/version/expiry receipts, a verified terminal UI event and physical secure-field/DPI/microphone/process-crash acceptance remain BLOCKED. Stop at Prompt 31; Prompt 32 not started.''')
doc('changes.md', '''No application code, config, dependencies, models, manifest or startup/shutdown scripts changed. Claude source repair is pinned, inspected and independently exercised. Codex added synthetic receipt-replay tests, two offscreen widget-journey cases, a read-only dependency-routing wrapper and this report builder/evidence packet. Current dated README notes describe results. No new screenshot or UI feature change. No commit/merge into claude/main or deployment.

Previous audit/reconciliation originals are preserved; this continuation has its own dated directory. P31-001 is not reopened. P31-002 has no source repair or fix SHA in this audit.''')
doc('cross-pillar-matrix.md', '''| Boundary | Fresh evidence | Limitation |
|---|---|---|
| Approval ↔ UI ↔ requester | original+repair tests PASS; real widget approve/close cases PASS; replay 2 FAIL | requester unique identity incomplete |
| API-first ↔ CAPTURED/FIX/lessons | Phase 8 flow A PASS with installed interpreter routing | fixture workbook and authored repair text |
| Cloud opt-in ↔ DGM ↔ untrusted input | Phase 5/8 and registry tests | fake cloud provider; no live consultation |
| GPU ↔ voice/training admission | scheduler and independent lease tests | no GPU saturation/mic/TTS journey |
| Show Me Once ↔ privacy/UIA | Phase 5 fixture and IR-001 tests | synthetic click/disposable native window, not physical focus-switch acceptance |
| Cursor ↔ API/UIA fallback | cursor/UI control regressions | no physical pointer interference trial |
| Cancellation/restart ↔ no replay | Phase 8 flow E; new cancellation control | no complete UI-worker crash journey |
| AZR ↔ UI/idle notifications | historical checkpoint/architecture assertions | new runtime responsiveness/notification soak NOT RUN |

Feature ON/OFF assertions in existing suites are component evidence. Complete per-route ON/OFF acceptance remains BLOCKED. Inspect executed-tests.jsonl for precise test IDs and skips; no invented catalog passes.''')
doc('benchmarks.md', '''benchmarks.csv and resource-profile.json compare the exact old 5b56f84 Approval class to pinned ddf3247 with 300 interleaved warm positive-control samples per version. Both construct and approve one synthetic safe card. This measures entropy/hash/receipt overhead, not event-to-render, voice latency or improved user performance. One traced operation per version reports temporary Python allocation, not RSS or GPU memory. No performance threshold or speedup claim. Real rendering/readback is separately captured in widget-readback files; no long-lived memory/flicker soak.''')
doc('compatibility.md', '''Existing Windows Python/runtime provenance is in baseline.json. No installation. The isolated launcher returns repair_required for missing .venv/.venv-brain, Whisper, F5, Laya and Harness assets. Docker 29.8.2, local Ollama and required Ollama models are available to the unrestricted health probe; Groq is not live tested.

run_installed_dependencies.py redirects only app_adapters.APP and two fixture SKILLS interpreter paths to the existing original installation. Workers run from the audited current working directory. No copied runtime database, credentials or package changes. The previously failing workbook flow then passes. This does not make the entire isolated launcher ready.

303 baseline passes include native disposable UIA/Tk components. Two new real offscreen Tk widget cases use synthetic invocation and no external executor. Native 200-percent interaction, secure desktop, real speech, concurrent training and process crash acceptance remain unavailable/unexecuted. Full repository regression is NOT RUN because authorization acceptance still fails.''')
doc('security.md', '''No real sends, deletes, account writes, physical input injection or private screen capture. Cloud-provider tests use recording fakes. Widget readback contains authored fixture text only. Real filesystem writes are limited to disposable test data and this audit packet; no external executor is attached to the widget journey.

P31-001 callback isolation is confirmed fixed. P31-002 demonstrates accepting a stale host-issued receipt for a new same-text request at two final requester seams. It requires synthetic access to the response seam; no external attacker entry point is established. The finding is narrower than arbitrary remote authorization bypass and broader than a widget rendering issue. Zero unauthorized acceptance under the specified injected replay cannot be claimed.

Existing private/unknown UIA snapshot and registry secret/approval tests pass. They do not establish exhaustive overlay/log privacy or correct final scope for every tool. Root .config user modifications are untouched.''')
doc('rollback.md', f'''No Codex source repair is installed. Preserve the dated packet and prior originals. No reset/revert of claude or user config is required. From app/, using the already-installed original Python interpreter:
```powershell
python -m pytest tests/test_prompt31_approval_binding.py -q
python -m pytest artifacts/jarvis-audit/modules/31-ui-island-pip/{RUN}/test_receipt_replay.py -q
python -m pytest artifacts/jarvis-audit/modules/31-ui-island-pip/{RUN}/test_widget_journey.py -q
python artifacts/jarvis-audit/modules/31-ui-island-pip/{RUN}/run_installed_dependencies.py tests/test_phase08_integration.py::test_P08_flow_A_api_first_capture_degrade_fix_lessons_and_bounded_diagnosis -q
python -m jarvis.launcher --check
```
Receipt replay is expected to fail on ddf3247. Use distinct output paths on later reruns to keep accepted evidence immutable. Proposed repair needs Claude implementation and independent post-fix testing; no patch is auto-applied.''')
doc('codex-findings-reconciliation.md', f'''| ID | Current status | Fix / evidence | Remaining |
|---|---|---|---|
| P31-001 | FIXED at original callback boundary | {FIX}; original four + nine repair test executions PASS | does not cover P31-002 |
| P31-002 | APPLIES / new FAIL | two requester replay assertions FAIL on {SHA} | no fix SHA; independent review after repair |
| IR-001 | prior narrow fix retained; fresh privacy PASS | tests/test_independent_review.py | real secure-input acceptance |
| IR-002 | prior narrow fix retained; fresh admission PASS | tests/test_independent_review.py | live GPU race/contention |
| IR-003 | prior fix retained, no new dedicated rerun in continuation | earlier packet | broader runtime acceptance |
| IR-004 | UNVERIFIED runtime; source retained | historical deep-path lab evidence | no fresh direct lab-specific reproduction |

Prior artifacts are hashed and unchanged. Prior checkpoint 36fbf3c, fix 32fdbfe and packet bc71fb7 remain historical. Exact new pin ddf3247 includes Claude repair 1dd3e9c. Source code repaired by Codex: none. Full old failure reconciliation remains incomplete. [New ledger](../../../reconciliation/{RUN}/findings-ledger.csv).''')
doc('sequence-diagrams.md', '''Current normal path:
```mermaid
sequenceDiagram
  participant R as Requester
  participant Q as UIEventBuffer
  participant D as IslandDesk / Approval
  R->>Q: kind, detail, answer, ready, cancelled
  Q->>D: construct card; random token and text digest
  D->>D: bind click/voice to displayed token
  D-->>R: approved + token + digest, ready
  Note over R: Checks digest, not unique pending token
```
Synthetic replay:
```mermaid
sequenceDiagram
  participant A as Prior approved card A
  participant I as Fault injector at response seam
  participant B as New same-text request B
  A-->>I: saved token A + text digest
  B->>B: construct card B (different token)
  I->>B: deliver saved A receipt; no B decision
  B->>B: digest matches; returns True
```
event-trace.json records five synthetic producers and terminal barriers; it does not include rendered private data. widget-readback files contain real offscreen widget text/ready/result, with synthetic input and no external executor. Accessibility/focus/DPI/process-crash full acceptance is BLOCKED.''')
doc('repair-handoff.md', '''P31-002 repair proposal (not applied): originate an unpredictable request ID before enqueueing the card, keep the expected receipt state in the requester, and have the UI preserve that ID. Accept a receipt only for the exact still-pending request and consume it once. Bind tool, immutable canonical arguments/digest, identity/scope, skill version, generation, issuance/expiry and cancellation independently of model text. A text hash alone cannot distinguish repeated equal requests. Apply the same protocol to App and learned-ability cards; preserve deny/lapse semantics and existing approved-scope executor checks.

Verify: both new replay assertions must pass, original stale/expired/unbound/voice/concurrent tests must remain green, and genuine same-text requests must each work after their own user decision. Also test forged/missing/wrong IDs, delayed/expired receipts, cancellation/restart and argument/version changes. This is a contract suggestion, not a validated code patch; independent receipt-seam attacker control remains unproven.''')
doc('verdict.md', f'''**NOT READY / BLOCKED — Prompt 31 continued, not fully complete. Prompt 32 NOT STARTED.**

Pinned claude **{SHA}**. Original **P31-001 callback defect is independently verified fixed** by source repair {FIX}: original four tests pass; nine repair tests pass (13 executions, four duplicate scenarios). Two real offscreen widget journeys approve/close-deny successfully; input is synthetic and no executor runs.

New **P31-002**: both final requesters accept replay of a prior approved receipt for a new identical-text request whose card received no decision. **2 FAIL / 3 positive/control PASS**. This is synthetic response-seam fault injection, not a demonstrated remote attack. Unique pending-request identity is still not checked at final acceptance; the mandatory forged/stale approval gate is unmet.

Relevant UI/voice/privacy/cross-pillar regression: **303 PASS / 1 FAIL / 8 SKIPPED**. Failure was the isolated utility-runtime path; same full workbook/skill flow passed with read-only installed interpreter routing (**1 PASS**). Neighbor ability/registry regression: **114 PASS**. Reruns/duplicate scenarios are not added to inflate unique counts. No full repository rerun after the renewed stop gate.

Launcher **repair_required** for missing isolated runtimes/assets. Remaining full secure-field/DPI/mic/training/UI crash/verified-terminal acceptance is BLOCKED/NOT RUN. No source repair by Codex, deployment, auto-merge or account action. Claude repair of P31-002 and independent verification are needed before completing Prompt 31 and moving to Prompt 32.''')

RECON.mkdir(parents=True, exist_ok=True)
for name, text in {
    'artifact-inventory.md': 'All prior originals are hashed in the current packet prior-artifact-hashes.json; previous independent/Claude repair evidence retained unchanged.',
    'patch-assessment.md': f'Inspected repair {FIX} and pinned {SHA}; callback isolation fixed. Digest-only final requester still accepts same-text receipt replay. No blind source patch application.',
    'unresolved.md': 'P31-002 synthetic response-replay acceptance fails; external exploitability unverified. Remaining full identity/scope/expiry and live acceptance gates incomplete.',
    'handoff.md': f'Continue from module packet {RUN}/verdict.md. P31-001 fixed; P31-002 needs Claude source repair and independent retest. Prompt 32 remains gated.'
}.items():
    write(RECON / name, '# Prompt 31 continuation reconciliation\n\n' + text + '\n')
dump(RECON / 'review-revisions.json', {'old_pin': OLD, 'fix_commit': FIX, 'new_pin': SHA, 'date': DATE})
with (RECON / 'findings-ledger.csv').open('w', encoding='utf-8', newline='') as stream:
    writer = csv.writer(stream)
    writer.writerow(['finding', 'sha', 'fix_commit', 'status', 'evidence', 'follow_up'])
    writer.writerow(['P31-001', SHA, FIX, 'FIXED_CALLBACK_BOUNDARY', 'approval-reverification.xml', 'retain all original regression scenarios'])
    writer.writerow(['P31-002', SHA, '', 'APPLIES_FAIL_SYNTHETIC', 'receipt-replay.xml', 'requester-owned unique identity; independent attacker path unverified'])
for name, keys in [('repro-results.jsonl', ['approval-reverification.xml', 'receipt-replay.xml']),
                   ('legacy-regressions.jsonl', ['relevant-regression.xml', 'ability-registry-regression.xml']),
                   ('cross-pillar-regressions.jsonl', ['cross-pillar-dependency-retest.xml'])]:
    write(RECON / name, ''.join(json.dumps(r) + '\n' for key in keys for r in runs[key]))
dump(OUT / 'packet-hashes.json', {p.relative_to(OUT).as_posix(): sha(p) for p in OUT.rglob('*')
                               if p.is_file() and p.name != 'packet-hashes.json' and '__pycache__' not in p.parts})
print(json.dumps({'pin': SHA, 'runs': {f: counts(r) for f, r in runs.items()}, 'verdict': 'NOT READY / BLOCKED'}))
