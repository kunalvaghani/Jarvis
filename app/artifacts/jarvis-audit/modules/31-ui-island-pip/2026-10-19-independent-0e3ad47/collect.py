"""Fresh audit packet; writes only this run and its new reconciliation subfolder."""
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
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
BASE = next(p for p in OUT.parents if (p / 'main.py').is_file() and (p / 'jarvis').is_dir())
ROOT = BASE.parent
sys.path.insert(0, str(BASE))
SHA = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
assert SHA == '0e3ad4706b5120e5d0479d34333e5faa7b0931b5'
DATE = '2026-10-19 IST'
RUN = OUT.name
PREVIOUS = OUT.parent / '2026-10-19-independent-ddf3247'
RECON = BASE / 'artifacts/jarvis-audit/reconciliation' / RUN

def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')

def dump(path, value):
    write(path, json.dumps(value, indent=2) + '\n')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def doc(name, text):
    write(OUT / name, f'# Prompt 31 independent audit — {DATE}\n\n{text.strip()}\n')

def xml_rows(path):
    rows = []
    for node in ET.parse(path).iter('testcase'):
        issue = next((node.find(k) for k in ('failure', 'error', 'skipped') if node.find(k) is not None), None)
        rows.append({'id': node.get('classname') + '::' + node.get('name'),
                     'status': 'PASS' if issue is None else 'SKIPPED' if issue.tag == 'skipped' else 'FAIL',
                     'seconds': float(node.get('time', 0)), 'evidence': path.name,
                     'message': issue.get('message', '') if issue is not None else ''})
    return rows

def counts(rows):
    return {s: sum(row['status'] == s for row in rows) for s in ('PASS', 'FAIL', 'SKIPPED')}

runs = {p.name: xml_rows(p) for p in OUT.glob('*.xml')}
assert 'relevant-regression.xml' in runs
summary = {k: counts(v) for k, v in runs.items()}
native_path = OUT / 'native-current-protocol/native-island.json'
native = json.loads(native_path.read_text(encoding='utf-8')) if native_path.is_file() else None
dump(OUT / 'baseline.json', {'pin': SHA, 'date': DATE, 'python': sys.version, 'executable': sys.executable,
     'platform': platform.platform(), 'runs': summary, 'source_repairs_by_codex': [],
     'dependencies': 'existing original Python and read-only utility interpreter routing; no install',
     'memory_scope': 'synthetic queue traced allocations; no long-duration process/GPU memory profile',
     'full_repository_regression': 'NOT RUN; full relevant selected suite is recorded instead',
     'original_user_config': 'modified by user, untouched',
     'master_contract': 'unavailable in repository and exact Downloads companion path',
     'reconciliation_contract': '10_CODEX_FINDINGS_RECONCILIATION.md: Codex read-only confirmation',
     'native_fixture_current_protocol': native,
     'native_fixture_original': 'FAIL: old unbound denial call rejected; output retained in native-island.txt'})
write(OUT / 'executed-tests.jsonl', ''.join(json.dumps(r) + '\n' for rows in runs.values() for r in rows))
skipped = [r for rows in runs.values() for r in rows if r['status'] == 'SKIPPED']
doc('skipped-checks.md', 'Actual pytest SKIPPED rows; these are not feature passes.\n\n' + '\n\n'.join(
    f"- `{row['id']}`: {row['message']} ({row['evidence']})" for row in skipped))

# A fixed, pre-repair commit and current implementation, pure positive-control workload.
# Include each revision's own receipt helper when executing its class source.
import types
from jarvis import approval_receipt as current_receipt
from jarvis.island_desk import Approval
prior_sha = 'ddf3247fd3d5ee6b151287c6cba358e8707090c6'
def old_text(path):
    return subprocess.check_output(['git', 'show', prior_sha + ':app/' + path], cwd=ROOT, text=True)
prior_receipt = types.ModuleType('jarvis.approval_receipt')
exec(compile(old_text('jarvis/approval_receipt.py'), '<pinned-prior-receipt>', 'exec'), prior_receipt.__dict__)
prior_desk = types.ModuleType('jarvis._audit_prior_desk')
prior_desk.__package__ = 'jarvis'
saved_module = sys.modules['jarvis.approval_receipt']
try:
    sys.modules['jarvis.approval_receipt'] = prior_receipt
    exec(compile(old_text('jarvis/island_desk.py'), '<pinned-prior-desk>', 'exec'), prior_desk.__dict__)
finally:
    sys.modules['jarvis.approval_receipt'] = saved_module
def operation(new):
    answer = {'request': current_receipt.new_request_id()} if new else {}
    cls = Approval if new else prior_desk.Approval
    card = cls(('fixture', 'public benchmark scope', answer, threading.Event(), lambda: False))
    assert card.decide(True) is True and answer['approved'] is True
samples = {False: [], True: []}
for _ in range(20):
    operation(False)
    operation(True)
for n in range(300):
    for new in ((False, True) if n % 2 else (True, False)):
        start = time.perf_counter_ns()
        operation(new)
        samples[new].append((time.perf_counter_ns() - start) / 1e6)
benchmark = []
for new, values in samples.items():
    tracemalloc.start()
    operation(new)
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    benchmark.append({'commit': SHA if new else prior_sha, 'n': len(values), 'p50_ms': statistics.median(values),
                      'p95_ms': sorted(values)[int(len(values)*.95)], 'traced_peak_bytes': peak})
with (OUT / 'benchmarks.csv').open('w', encoding='utf-8', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=['commit', 'n', 'p50_ms', 'p95_ms', 'traced_peak_bytes'])
    writer.writeheader()
    writer.writerows(benchmark)
dump(OUT / 'paired-card-profile.json', {'scope': 'positive-control card/request-ID construction and decision; no UI or voice latency',
                                      'results': benchmark, 'samples_ms': {str(k): v for k, v in samples.items()}})

from jarvis.ui_events import UIEventBuffer
buffer = UIEventBuffer()
tracemalloc.start()
started = time.perf_counter()
def producer(task):
    for n in range(1000):
        buffer.put(('answer_stream', {'task_id': str(task), 'phase': 'draft', 'text': 'x'*(n+1)}))
    buffer.put(('answer_error', {'task_id': str(task), 'status': 'cancelled'}))
threads = [threading.Thread(target=producer, args=(n,)) for n in range(5)]
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
peak = tracemalloc.get_traced_memory()[1]
tracemalloc.stop()
assert len([r for r in trace if r['kind'] == 'answer_error']) == 5
dump(OUT / 'event-trace.json', {'scope': '5 synthetic producers, 5000 cumulative updates and 5 terminal events', 'events': trace})
dump(OUT / 'resource-profile.json', {'scope': 'bounded synthetic queue sample; not a memory-leak or render-latency proof',
     'elapsed_seconds': time.perf_counter()-started, 'peak_traced_bytes': peak, 'coalesced': buffer.coalesced,
     'retained_rows': len(trace), 'terminal_events': 5})

prior_roots = [BASE / 'artifacts/jarvis-audit/codex-independent-review'] + [p for p in OUT.parent.iterdir() if p.is_dir() and p != OUT]
prior_hashes = {p.relative_to(BASE).as_posix(): digest(p) for root in prior_roots for p in root.rglob('*')
                if p.is_file() and '__pycache__' not in p.parts}
prior_hashes.update({p.relative_to(BASE).as_posix(): digest(p) for p in OUT.parent.iterdir() if p.is_file()})
dump(OUT / 'prior-artifact-hashes.json', prior_hashes)
source_paths = ['main.py', 'jarvis/approval_receipt.py', 'jarvis/island_desk.py', 'jarvis/repo_abilities.py',
    'jarvis/ui_events.py', 'jarvis/file_drop.py', 'jarvis/buddy_engine.py', 'jarvis/demonstration.py',
    'jarvis/tools.py', 'jarvis/gpu_scheduler.py', 'jarvis/launcher.py', 'jarvis/recovery.py',
    'evolution_eval/gate.py', 'evolution_eval/policy.json']
dump(OUT / 'source-hashes.json', {p: digest(BASE / p) for p in source_paths})

case_reasons = [
 ('BLOCKED', 'Streaming/order component assertions and widget readback pass; no full live model-to-UI acceptance.'),
 ('BLOCKED', 'Unique request ID, text scope and TTL pass; canonical executed-argument/identity/version/generation binding is not uniform across tools.'),
 ('PASS', 'Offscreen real-Tk close/deny journey and original idempotence tests; synthetic input, no external executor.'),
 ('PASS', 'Authored PDF drop handler with explicit synthetic choice reads exact source file; native WM_DROPFILES transport separately tested. Not a physical drag.'),
 ('PASS', 'Inert .exe drop kept as data; subprocess/shell launch guards remain uncalled; source hash and vault unchanged.'),
 ('PASS', 'Exact 35-state registry plus renderer/animation component regressions.'),
 ('BLOCKED', '5000 updates/five producers retain terminal events; no long-duration native flicker/memory-leak acceptance.'),
 ('BLOCKED', 'Synthetic private/unknown UIA field exclusion passes; secure-field overlay acceptance not performed.'),
 ('BLOCKED', 'Cursor focus and no-replay component tests; physical mouse/focus acceptance not performed.'),
 ('BLOCKED', 'Renderer scale=2 and DPI geometry fixtures; no global screen-scaling change or native 200-percent acceptance.'),
 ('PASS', 'Synthetic Speech cancellation clears speaking, queued content and generation. Real microphone/F5 end-to-end state remains unverified.'),
 ('BLOCKED', 'Native compositor fallback and cancellation components do not establish UI-process crash/backend reconnect acceptance.'),
 ('PASS', 'P31-001 and P31-002 regressions, forged/wrong request IDs, expiry and cancellation pass at actual requesters; fixture-only.'),
 ('BLOCKED', 'DGM/registry approval and tamper fixtures pass; no complete model-text-to-live-proposal UI journey.'),
 ('BLOCKED', 'Scoped native UIA/synthetic demonstration tests; physical focus-switch recording with visible indicator/stop control not accepted.'),
 ('BLOCKED', 'Per-request identity passes; uniform queued skill-version/generation-to-final-executor binding remains incomplete.'),
 ('BLOCKED', 'Fake-provider opt-in/privacy/zero-outbound-denial assertions; complete live display-to-provider path not accepted.'),
 ('BLOCKED', 'Training lease/scheduler/admission fixtures pass; no fresh training saturation with microphone/F5/UI.'),
 ('BLOCKED', 'No shared authenticated Verify-to-UI terminal receipt; plain answer/action strings do not establish the required three-state verification contract.'),
 ('BLOCKED', 'Five producers and token/receipt replay prevention pass; full concurrent cancellation/restart lifecycle acceptance remains unverified.'),
 ('BLOCKED', 'Real workbook API/readback/captured-skill flow passes; complete result-to-Island/no-phantom-cursor UI journey not established.'),
 ('BLOCKED', 'Synthetic log/registry/snapshot canaries pass; exhaustive overlay/artifact privacy acceptance remains incomplete.')]
rows = [{'id': f'JRV-31-{n:03}', 'status': status, 'reason': reason, 'sha': SHA, 'date': DATE,
         'scope': 'PASS means the explicitly described component/fixture, never whole-assistant certification',
         'component_evidence': 'catalog-components.xml' if n in (4, 5, 6, 11) else 'approval-reverification.xml' if n in (3, 13) else 'relevant-regression.xml'}
        for n, (status, reason) in enumerate(case_reasons, 1)]
write(OUT / 'tests.jsonl', ''.join(json.dumps(r) + '\n' for r in rows))
old_catalog = {r['id']: r for r in (json.loads(line) for line in (OUT.parent / 'tests.jsonl').read_text(encoding='utf-8').splitlines() if line.strip())}
write(OUT / 'catalog-join.jsonl', ''.join(json.dumps({'current': row, 'prior': old_catalog.get(row['id']),
     'semantics': 'original preserved user case' if n < 12 else 'revised targeted case; do not inherit same-ID prior semantics'}) + '\n' for n, row in enumerate(rows)))

doc('inventory.md', f'''Pinned current `claude` **{SHA}** in isolated `codex-review`. Original user config is untouched. Prior audit notes were preserved before a fast-forward. No application source repair by Codex. Existing interpreter paths are routed read-only; source/workers remain in the pinned checkout. [Environment and counts](baseline.json), [source hashes](source-hashes.json), [actual test rows](executed-tests.jsonl), [stable catalog join](catalog-join.jsonl).

Actual shared path: Actions._approve → App.request_approval → UIEventBuffer → IslandDesk.Approval → token-bound click/voice → answer/Event → receipt_valid. Requesters now originate and retain unpredictable request ID and issue time; cards digest kind/detail/ID; requesters enforce their own TTL and cancellation. Old same-text receipts do not authorize new requests. AbilityForge uses the same protocol. Existing ToolRegistry and per-executor scope checks remain the owners of execution.

UI streams/task metadata still use their existing event channel, not a new verification registry. A uniform host-owned canonical executed-argument/identity/version/generation receipt and authenticated verified terminal UI event remain absent. Demonstration capture belongs to demonstration/UIA; file drop belongs to file_drop/documents; speech/GPU belong to their existing workers/scheduler. Pillar D is an offline pipeline, not an always-running UI worker.

Reviewed actual source diff, Claude repair packet, prior inventory/system map/Phase 1–8 reports and reconciliation contract. Master contract remains unavailable. Historical results retain their dates and scopes; previous packets were not overwritten.''')
doc('failures.md', '''**P31-001 FIXED:** stale/unbound callback and voice isolation retain the original passing reproduction. Fix commit 1dd3e9c.

**P31-002 FIXED at the reviewed replay boundary:** source repair 0e3ad47 creates a pending request ID before enqueueing, digests it with text scope, and validates requester-owned issue time/TTL/cancellation. Independent replay now leaves the second card undecided and returns False for both App and learned abilities. The old test's equal-digest setup condition was changed to distinct request IDs/digests; all actual replay-rejection and side-effect assertions are unchanged. See test_receipt_replay.py and approval-reverification.xml. No new P0/P1 runtime defect is claimed by this packet.

Remaining acceptance gaps are BLOCKED, not presumed passing: canonical executor argument/identity/version/generation binding, verified terminal UI receipt, full concurrent restart lifecycle, scoped demonstration display/stop acceptance, native secure-field/DPI, microphone/F5/GPU contention and UI process crash. See remaining-work.md and tests.jsonl. Any actual test FAIL remains visible in XML/summary; zero failures must not be inferred from a planned count.''')
doc('changes.md', '''Application code/config/dependencies/manifest/launch scripts unchanged by Codex. Audited Claude source repair 0e3ad47, including the bundled deterministic-benchmark evaluator rule and its new seal. Added adapted independent receipt and widget tests, executable/PDF/speech/35-emotion probes, read-only interpreter wrapper, profiles, current native fixture output and reports. README updates distinguish resolved findings from incomplete module acceptance. No installation, deployment, automatic merge, paid API, account action or private recording.''')
doc('cross-pillar-matrix.md', '''| Seam | New evidence scope | Remaining gate |
|---|---|---|
| UI ↔ approvals ↔ ToolRegistry/MCP | requester replay/expiry/forgery; registry and Phase 3 tests | uniform final scope/version receipt |
| API-first ↔ CAPTURED/FIX/lessons | actual disposable workbook/readback, SQLite and authored repair text | complete result-to-UI lifecycle |
| Cloud ↔ demonstrations | fake-provider opt-in/privacy; disposable UIA with synthetic click | live consent/display/focus acceptance |
| Evolution/DGM | full Phase 6 selected file; updated deterministic/non-timing rule and seal | earlier proposals need re-evaluation |
| AZR ↔ speech/GPU | Phase 7 oracle/sandbox/admission and speech/GPU fixtures | live saturation/responsiveness |
| Cursor ↔ UIA/DOM/fallback | existing focus and uncertain-write tests | physical mouse trial |
| Cancellation ↔ restart | TaskState/Phase 8 and new speech-cancel fixtures | actual UI worker crash/reconnect |

Feature ON/OFF coverage is bounded by individual test assertions. Full supported-route ON/OFF acceptance is not established. Skips remain SKIPPED in actual XML, with BLOCKED explanations where provided; no fixture is counted as live acceptance.''')
doc('compatibility.md', '''Windows Python/runtime details and exact selected executions are in baseline.json. Borrowed original Python and utility interpreter paths read-only; no environment/model/database copies. The isolated launcher still reports repair_required for missing local .venv/.venv-brain, Whisper, F5, Laya and Harness assets. Docker/Ollama service probe status is preserved in launcher-check.txt; Groq inference is not tested.

Fresh native fixtures are offscreen owned windows. Sample widget images, where present, are rendered previews, not desktop screenshots. No global display scaling, secure desktop, microphone recording, real speaker output, private screen capture or new GPU training was performed. These limits prevent full live acceptance. Full repository testing is separate from the full relevant suite selected here.''')
doc('security.md', '''Old receipt reuse, stale callbacks, forged/wrong IDs, expiry, deny/lapse and cancellation are checked against actual requesters with synthetic response delivery. A second same-text request gets a distinct requester-owned ID. No remote exploitation was established in the earlier finding, and no in-process arbitrary-code defense is claimed now.

Executable-drop probe uses inert bytes and denies subprocess/shell launch. PDF probe checks the exact source and no vault mutation. Registry/log/privacy tests use authored canaries. Native fixtures contain synthetic content only. No live sends, account writes, system setting changes or private recordings. Remaining full executor scope and end-to-end privacy/verification requirements are BLOCKED.''')
doc('rollback.md', f'''No Codex source repair is installed; no production rollback. Preserve prior packets, current source pin and user config. Run from app/ using the existing original Python:
```powershell
python -m pytest tests/test_prompt31_approval_binding.py tests/test_prompt31_receipt_replay.py -q
python -m pytest artifacts/jarvis-audit/modules/31-ui-island-pip/{RUN}/test_receipt_replay.py -q
python -m pytest artifacts/jarvis-audit/modules/31-ui-island-pip/{RUN}/test_catalog_components.py -q
python -m jarvis.launcher --check
```
Use run_installed_dependencies.py for the recorded relevant suite with its existing installed utility interpreter routing. The exact test list and results are retained in executed-tests.jsonl. New runs should have new output directories. No branch reset or automatic merge is prescribed.''')
doc('codex-findings-reconciliation.md', '''| Finding | Current conclusion | Exact repair/evidence |
|---|---|---|
| P31-001 | FIXED callback boundary | 1dd3e9c; unchanged original four tests and repair regressions |
| P31-002 | FIXED same-text receipt replay boundary | 0e3ad47; independent adapted replay plus forged/TTL/fresh-user cases |
| D-P31-F1 | bundled evaluator rule reviewed | 0e3ad47; Phase 6 deterministic/non-timing rejection tests; evaluator seal changed |
| IR-001 | narrow snapshot privacy fix retained | fresh independent private/unknown-field tests |
| IR-002 | narrow training-admission fix retained | fresh independent lease/admission tests |
| IR-003 | retained; no dedicated new recipe suite in this run | previous fixed-source evidence |
| IR-004 | source retained, no new dedicated deep-path acceptance | previous lab evidence; Phase 6 regression scope only |

No entire-system certificate. Source fix by Codex: none. Prior artifact hashes and source SHA preserve lineage. The first twelve old catalog IDs are joined; targeted 013–022 changed semantics in the revised prompt and inherit no old status.''')
doc('remaining-work.md', '''Required work before Prompt 31 can be called fully complete:

1. Bind canonical executed tool arguments, identity/scope, skill version and task generation at the final executor; current shared receipt binds displayed text and request ID only. Existing per-tool checks are not a uniform contract.
2. Wire distinct streaming, pending-verification and verified-completion UI states to host Verify evidence. Current plain answer/action strings and task status do not provide an authenticated terminal receipt.
3. Complete per-task concurrent cancellation/restart lifecycle and stale-notification tests across UI and optional workers; verify explicit cloud opt-in and queued version changes all the way to execution.
4. Validate visible scoped Show Me Once recording/stop controls, secure-field exclusion, native 200-percent usability, physical cursor/focus behavior, microphone/F5 cancellation and training contention, and owned UI-process crash/backend reconnection.
5. Complete full supported-route ON/OFF checks and remaining live journey acceptance. Keep unavailable checks BLOCKED. The read-only Codex reconciliation contract does not authorize implementing new source repairs in this audit; source implementation belongs to Claude, followed by independent verification.

These are acceptance/implementation gaps, not a claim that another security exploit was demonstrated. Prompt 32 remains gated by the user's requirement to finish Prompt 31 first.''')
doc('sequence-diagrams.md', '''Corrected request flow:
```mermaid
sequenceDiagram
  participant R as Requester
  participant Q as UIEventBuffer
  participant C as Approval card
  R->>R: generate request ID and issue time
  R->>Q: kind, detail, request ID, answer/Event
  Q->>C: capture ID; derive text+ID digest
  C->>C: token-bound user callback; TTL/cancel check
  C-->>R: receipt and ready Event
  R->>R: compare own ID digest; own TTL; cancellation
```
Replay of an earlier same-text receipt fails the new request's digest comparison. Event-trace.json shows five synthetic producers and retained terminal barriers; it is not a renderer or restart recording. Widget-readback files hold authored real-Tk output. Resource profiles and paired-card-profile state their exact synthetic scope.''')
status_lines = '\n'.join(f'- `{name}`: {value}' for name, value in summary.items())
doc('native-fixture.md', f'''The original scripts/verification/verify_island_desk.py failed its denial assertion because it calls decide(False) without the token now required by the repaired API. This is a stale verification harness call, not a permission bypass. Original output and preview files remain in this run's root.

An audit copy changes only that call to decide(False, displayed_token); all readiness/denial assertions remain unchanged. [Native readback](native-current-protocol/native-island.json): result available {native is not None}; all recorded checks true {bool(native and all(native['checks'].values()))}. No source file was edited by Codex. The checked-in verification script needs a maintainer update for the API.

![Rendered sample widget preview](native-current-protocol/island-desk-preview.png)

Current rendered preview from owned offscreen runtime widgets and authored data; not a desktop screenshot, live Spotify result or completed user task. Pink regions are the exporter's transparency key; the montage crops card edges. These artifacts do not prove native edge quality or 200-percent usability. Artwork is the repository's existing Pip/game/UI renderer; no upstream reference artwork is relabeled as a new screenshot.''')
doc('verdict.md', f'''**P31-001 and P31-002 independently verified FIXED at their reviewed boundaries. Prompt 31 remains PARTIAL / NOT READY / BLOCKED for full acceptance. Prompt 32 NOT STARTED.**

Pin: **{SHA}**. Approval re-verification: 36 PASS executions, including duplicate original/repair scenarios. Replay setup was adapted to requester-owned IDs; actual security assertions unchanged. Fresh selected results (do not add reruns to inflate unique counts):

{status_lines}

The original native verification script failed on its obsolete unbound denial call; that attempt is preserved. The token-bound audit adapter's native result is recorded separately in native-fixture.md, not silently substituted for the original run.

Both prior confirmed permission findings are closed for their reproduced scenarios; no new P0/P1 defect is asserted. Full module acceptance remains incomplete: canonical final argument/identity/version binding, authenticated verified terminal UI state, complete concurrency/restart and physical secure-field/DPI/voice/training/UI-crash checks. See remaining-work.md. Launcher readiness is preserved separately and may be repair_required for absent isolated assets.

No Codex application source change, automatic merge, deployment, installation or live account mutation. Existing data/code and prior audit packets are preserved. Locally passing regressions and rendered fixtures do not establish live production readiness.''')
RECON.mkdir(parents=True, exist_ok=True)
for name, text in {'artifact-inventory.md': 'Prior files are hashed in the current packet; original evidence retained.',
 'patch-assessment.md': 'Inspected 0e3ad47 source diff and evaluator policy/seal. No blind patch application. Both prior reproduced findings pass.',
 'unresolved.md': 'Full Prompt 31 implementation/live acceptance gaps remain; see remaining-work.md. No new P0/P1 asserted.',
 'handoff.md': f'Current module run {RUN}; both reproduced findings fixed; full Prompt 31 still partial. Do not start Prompt 32 until acceptance is complete.'}.items():
    write(RECON / name, '# Reconciliation continuation\n\n' + text + '\n')
dump(RECON / 'review-revisions.json', {'current_pin': SHA, 'previous_pin': prior_sha, 'fix_p31_001': '1dd3e9c', 'fix_p31_002': SHA})
with (RECON / 'findings-ledger.csv').open('w', encoding='utf-8', newline='') as stream:
    writer = csv.writer(stream)
    writer.writerow(['finding', 'current_pin', 'fix', 'status', 'evidence'])
    writer.writerow(['P31-001', SHA, '1dd3e9c', 'FIXED_REPRODUCED_BOUNDARY', 'approval-reverification.xml'])
    writer.writerow(['P31-002', SHA, SHA, 'FIXED_REPRODUCED_BOUNDARY', 'approval-reverification.xml'])
for name, keys in [('repro-results.jsonl', ['approval-reverification.xml']), ('legacy-regressions.jsonl', ['relevant-regression.xml']),
                   ('cross-pillar-regressions.jsonl', ['relevant-regression.xml'])]:
    write(RECON / name, ''.join(json.dumps(row) + '\n' for key in keys for row in runs[key]))
dump(OUT / 'packet-hashes.json', {p.relative_to(OUT).as_posix(): digest(p) for p in OUT.rglob('*')
                               if p.is_file() and p.name != 'packet-hashes.json' and '__pycache__' not in p.parts})
print(json.dumps({'pin': SHA, 'runs': summary, 'prior_findings': 'FIXED', 'module_acceptance': 'PARTIAL / NOT READY'}))
