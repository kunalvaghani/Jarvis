"""Build this audit's evidence packet without changing application sources.

Run from app/ with its existing Python runtime. Synthetic queue profiling only;
no model, screenshot, user-input capture, account action or external write.
"""
import csv
import hashlib
import json
import platform
from pathlib import Path
import queue
import statistics
import subprocess
import sys
import threading
import time
import tracemalloc
import xml.etree.ElementTree as ET

BASE = next(p for p in Path(__file__).resolve().parents if (p / 'jarvis').is_dir() and (p / 'main.py').is_file())
ROOT = BASE.parent
OUT = Path(__file__).resolve().parent
RECON = BASE / 'artifacts/jarvis-audit/reconciliation'
sys.path.insert(0, str(BASE))
DATE = '2026-10-19 IST'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding='utf-8')


def doc(name, body):
    write(OUT / name, f'# Prompt 31 audit — {DATE}\n\n{body}\n')


def dump(path, value):
    write(path, json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def xml_rows(name):
    rows = []
    for case in ET.parse(OUT / name).iter('testcase'):
        fail = case.find('failure')
        error = case.find('error')
        skip = case.find('skipped')
        issue = fail if fail is not None else error if error is not None else skip
        rows.append({'id': case.get('classname') + '::' + case.get('name'),
                     'status': 'FAIL' if fail is not None or error is not None else 'SKIPPED' if skip is not None else 'PASS',
                     'seconds': float(case.get('time', 0)), 'evidence': name,
                     'message': issue.get('message', '') if issue is not None else ''})
    return rows


def counts(rows):
    return {status: sum(r['status'] == status for r in rows) for status in ('PASS', 'FAIL', 'SKIPPED')}


def profile():
    from jarvis.ui_events import UIEventBuffer
    from jarvis.island_buddy import EMOTIONS
    buffer = UIEventBuffer()
    tracemalloc.start()
    start = time.perf_counter()
    # Each producer owns its task identity. Final/error events are barriers.
    def producer(task):
        for n in range(200):
            buffer.put(('answer_stream', {'task_id': task, 'phase': 'draft', 'text': 'x' * (n + 1)}))
        buffer.put(('answer_error', {'task_id': task, 'status': 'cancelled'}))
    workers = [threading.Thread(target=producer, args=(str(n),)) for n in range(5)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    trace = []
    delays = []
    while True:
        try:
            before = time.perf_counter_ns()
            kind, value = buffer.get_nowait()
            delays.append((time.perf_counter_ns() - before) / 1e6)
            trace.append({'kind': kind, 'task_id': value['task_id'], 'characters': len(value.get('text', ''))})
        except queue.Empty:
            break
    elapsed = time.perf_counter() - start
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    terminal = [r for r in trace if r['kind'] == 'answer_error']
    assert len(terminal) == 5 and len({r['task_id'] for r in terminal}) == 5
    dump(OUT / 'event-trace.json', {'scope': 'synthetic UIEventBuffer only; no Tk render or executor',
                                   'events': trace, 'terminal_states': len(terminal), 'coalesced': buffer.coalesced})
    result = {'scope': 'same pinned commit, synthetic five-producer queue; not event-to-render latency',
              'elapsed_seconds': elapsed, 'tracemalloc_peak_bytes': peak,
              'dequeue_p50_ms': statistics.median(delays), 'dequeue_p95_ms': sorted(delays)[int(len(delays)*.95)],
              'emotions': list(EMOTIONS), 'emotion_count': len(EMOTIONS), 'retained_rows': len(trace)}
    dump(OUT / 'resource-profile.json', result)
    with (OUT / 'benchmarks.csv').open('w', newline='', encoding='utf-8') as stream:
        fields = ['commit', 'scenario', 'metric', 'value', 'scope']
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for key in ('elapsed_seconds', 'tracemalloc_peak_bytes', 'dequeue_p50_ms', 'dequeue_p95_ms'):
            writer.writerow(dict(commit=SHA, scenario='five_producer_queue', metric=key, value=result[key], scope=result['scope']))
    return result


SHA = git('rev-parse', 'HEAD')
assert SHA == '5b56f84c1604de87bb8845027dffb5ce5943243b'
assert git('branch', '--show-current') == 'codex-review'
old = BASE / 'artifacts/jarvis-audit/codex-independent-review'
historical = [{'path': p.relative_to(BASE).as_posix(), 'sha256': digest(p), 'bytes': p.stat().st_size}
              for p in sorted(old.rglob('*')) if p.is_file()]
dump(OUT / 'prior-artifact-hashes.json', historical)
prior_module = OUT.parent
dump(OUT / 'prior-module-hashes.json', {p.name: digest(p) for p in sorted(prior_module.iterdir()) if p.is_file()})
prior_catalog = {row['id']: row for row in map(json.loads, filter(str.strip, (prior_module / 'tests.jsonl').read_text(encoding='utf-8').splitlines()))}
source_paths = ['main.py', 'jarvis/actions.py', 'jarvis/island.py', 'jarvis/island_desk.py',
                'jarvis/ui_events.py', 'jarvis/tools.py', 'jarvis/demonstration.py',
                'jarvis/file_drop.py', 'jarvis/buddy_engine.py', 'jarvis/island_buddy.py',
                'jarvis/evolution_promotion.py', 'jarvis/skill_evolution.py', 'jarvis/cloud_architect.py',
                'jarvis/gpu_scheduler.py', 'jarvis/launcher.py', 'jarvis/recovery.py']
dump(OUT / 'source-hashes.json', {p: digest(BASE / p) for p in source_paths})
baseline = xml_rows('baseline.xml')
normal = xml_rows('baseline-unrestricted.xml')
retest = xml_rows('baseline-failure-retest.xml')
target = xml_rows('final-targeted.xml')
repro = xml_rows('approval-final.xml')
environment = {'date': DATE, 'head': SHA, 'branch': 'codex-review', 'python': sys.version,
               'executable': sys.executable, 'platform': platform.platform(),
               'source_mutations': [], 'original_user_config_preserved': True,
               'master_contract': 'unavailable in repository and exact companion Downloads path',
               'reconciliation_contract': 'C:/Users/kunal/Downloads/10_CODEX_FINDINGS_RECONCILIATION.md',
               'prior_review_base': '36fbf3ce925080f7f54afa87eaf1d9b88414142d',
               'prior_fix_commit': '32fdbfe', 'current_merge': SHA,
               'restricted_baseline': counts(baseline), 'unrestricted_baseline': counts(normal),
               'isolated_failure_retest': counts(retest), 'targeted_final': counts(target),
               'approval_final': counts(repro), 'full_repository_regression': 'NOT RUN: unresolved P1 stop gate',
               'source_fix_sha': None, 'timing': 'per-case seconds retained in XML; no baseline process RSS measurement'}
dump(OUT / 'baseline.json', environment)
write(OUT / 'executed-tests.jsonl', ''.join(json.dumps({'run': group, **r}) + '\n'
      for group, rows in [('restricted-baseline', baseline), ('baseline', normal), ('isolated-retest', retest),
                          ('targeted-final', target), ('approval-final', repro)] for r in rows))
metrics = profile()

cases = [
 ('BLOCKED', 'Streaming/coalescing fixture evidence exists; no complete live brain-to-render journey.'),
 ('BLOCKED', 'Exact text card exists; immutable request/tool/argument digest/identity/expiry receipt is absent from shared Approval payload.'),
 ('PASS', 'Fixture-only: DeskWidgetTests.test_inline_approval_does_not_block_game_or_task_and_close_denies; no real external executor.'),
 ('BLOCKED', 'No native PDF drop journey executed in this packet; synthetic document ingestion regression passed.'),
 ('NOT RUN', 'Executable drop negative case not run; source routes dropped files as data, not subprocess execution.'),
 ('PASS', f'Pip renderer/animation regressions passed; actual emotion registry contains {metrics["emotion_count"]} states.'),
 ('BLOCKED', 'Synthetic queue/profile and existing coalescing fixtures pass; no long-lived Tk render/memory soak.'),
 ('BLOCKED', 'IR-001 synthetic password/unknown-state snapshots pass; secure native field overlay acceptance not run.'),
 ('BLOCKED', 'Cursor focus/no-replay fixtures pass; no physical-pointer/focus acceptance.'),
 ('BLOCKED', 'PIL geometry tested at scale 2 and other scales; no native 200-percent DPI interaction acceptance.'),
 ('BLOCKED', 'No microphone/F5 cancellation journey executed.'),
 ('BLOCKED', 'No actual owned UI-process crash/reconnect injection executed.'),
 ('FAIL', 'P31-001: stale callback approves successor; three final synthetic permission assertions FAIL.'),
 ('BLOCKED', 'Registry denies model approval fields in fixtures; DGM proposal text-to-live-card journey not executed.'),
 ('BLOCKED', 'Demonstration suite had one initial failure then isolated PASS; no physical focus-switch recording journey.'),
 ('BLOCKED', 'No queued card-to-skill-version atomic binding demonstrated.'),
 ('BLOCKED', 'Fake-provider consent/privacy assertions pass; no UI display-to-outbound-call integration proof.'),
 ('BLOCKED', 'Training lease admission and scheduler fixtures pass; no training/voice/UI saturation experiment.'),
 ('BLOCKED', 'IslandDesk.notify clears answer phase for plain answer/action strings; no authenticated Verify-to-UI terminal receipt.'),
 ('FAIL', 'Five-producer queue retains synthetic terminal events; approval reuse remains reproducible (P31-001).'),
 ('BLOCKED', 'No complete API success-to-Island/no-cursor journey executed.'),
 ('BLOCKED', 'Registry output and snapshot synthetic secret fixtures pass; no exhaustive overlay/log output privacy proof.'),
]
write(OUT / 'tests.jsonl', ''.join(json.dumps({'id': f'JRV-31-{n:03}', 'status': status,
      'scope': 'fixture/component evidence only; see executed-tests.jsonl for exact pytest IDs',
      'reason': reason, 'sha': SHA, 'date': DATE}) + '\n' for n, (status, reason) in enumerate(cases, 1)))
write(OUT / 'catalog-join.jsonl', ''.join(json.dumps({'id': f'JRV-31-{n:03}',
      'prior': prior_catalog.get(f'JRV-31-{n:03}'), 'current_status': status,
      'semantics': 'original retained user case' if n <= 12 else 'revised targeted case; do not inherit old same-ID semantics or results'}) + '\n'
      for n, (status, reason) in enumerate(cases, 1)))

doc('inventory.md', f'''Pinned current `claude` **{SHA}** in the clean, existing `codex-review` worktree. Fast-forward only; original user `app/config/config.json` remains modified and untouched. Runtime is borrowed read-only from the original `.venv`; ignored environments/models were not copied. [Environment/counts](baseline.json), [source hashes](source-hashes.json), [case catalog](tests.jsonl), [actual executions](executed-tests.jsonl).

Actual path: `main.App.report/request_approval` → `UIEventBuffer` → `App` Tk event drain → `IslandDesk`/`Island`/Pip. `Actions._approve` waits for a strict True and rechecks cancellation. `Approval` stores `(kind, detail, answer dict, threading.Event, cancelled)` with a 180-second lifetime starting at card construction. The buttons call `IslandDesk.decide(True/False)` against the current queue head. No UUID/digest/identity receipt is present in that shared payload. ToolRegistry is `jarvis/tools.py`, not a second UI executor.

Other seams: `file_drop.DropTarget` queues WM_DROPFILES paths for Tk polling; `file_drop.handle` asks a data-use question. `demonstration.DemonstrationSession` owns scoped hook/session state. `skill_evolution`, `evolution_promotion`, `cloud_architect`, `gpu_scheduler` remain the implementation owners. Pillar D training is an offline pipeline, not a running UI worker.

Reviewed system map, Phase 1–8 index entries and final handoff matrix, original independent verdict/security/bug register/patch, and reconciliation companion. These are historical claims until specifically re-executed. The previous module-root JSONL has 32 NOT RUN cases. [Stable-ID join](catalog-join.jsonl) preserves the first twelve original user cases and identifies revised targeted IDs 013–022 as changed semantics; no historical status is promoted to a fresh result. The old module-root packet is preserved, hashed in prior-module-hashes.json; this new run uses a dated subdirectory. `00_MASTER_CONTRACT.md` was not found. Reconciliation says Codex confirms in read-only mode and reserves source repair for Claude; no application source repair was applied.

**STOP:** unresolved P1 permission defect [P31-001](failures.md). Prompt 31 is incomplete, NOT READY; Prompt 32 has not started.''')
doc('failures.md', '''**P31-001 — P1 / APPLIES: stale approval callback can authorize the next request.** Repeated legacy `lambda: desk.decide(True)` approves card A, removes it, then approves B. If A expires or is removed first, the same callback approves B. An unbound direct decision also succeeds. This is synthetic callback dispatch into actual `IslandDesk`/`Approval`, with separate answer/event objects; no account/file mutation was attempted. The observed unauthorized effect is B's approval result becoming True. External executor side effects were not tested.

Root cause: `IslandDesk.__init__` binds buttons without card identity; `IslandDesk.decide` pops the queue head. Request identity, signed/host-owned argument digest and final-boundary receipt remain separate missing requirements. [Final reproduction](approval-final.xml): **3 FAIL / 1 positive-control PASS**. Source repair: NOT APPLIED; no fix SHA. Minimum repair proposal: bind each rendered callback to its immutable card/request identity; reject stale/unbound decisions; independently bind execution to tool, arguments, identity, version, expiry and cancellation. Re-run this reproduction plus adversarial final-executor tests after Claude's source repair.

Initial test-authoring run `reproduction-before.xml` had callback-introspection errors; it is not defect proof. `reproduction-before-corrected.xml` demonstrated stale/unbound approval but included an overstrict positive-control assertion. Final `test_approval_binding.py` corrects that assertion. Earlier paths under tests/ were moved into this packet to avoid adding intentional failures to the default application suite.

Restricted baseline: 24 failures, including denied fixture atomic replacements and WinRT subprocess timeouts. Outside sandbox: 248 PASS / 2 FAIL / 8 SKIPPED. Failures were a transient Tcl/Tk library lookup and a demonstration capture returning None. Both passed in isolation (2 PASS); this does not erase the initial failures or establish combined-suite stability. No source was changed to hide them.

Other acceptance blockers: missing unified verified UI terminal receipt, full immutable approval scope binding, optional-worker integration and real secure-field/DPI/cancellation/crash acceptance. Full relevant regression acceptance remains unmet; no next-module execution.''')
doc('changes.md', '''Application source, dependencies, configuration, service manifest and launch/stop scripts: unchanged. Added only a reproducible failing audit fixture, this packet builder, execution records, source/prior-artifact hashes, reconciliation ledger and dated README audit notes. No runtime/UI feature change or new screenshot; no private desktop capture.

Branch advanced cleanly from bc71fb7 to the pinned current claude merge before testing. No branch reset, merge into claude/main, commit or deployment was performed. Source fix SHA is null. Source repairs are reserved for Claude by the companion reconciliation contract; do not mistake an audit stop for a repaired permission boundary.''')
doc('cross-pillar-matrix.md', '''| Seam | Fresh evidence | Remaining gate |
|---|---|---|
| UI ↔ approval ↔ executor/MCP | registry fixtures; approval reproduction FAIL | immutable scope receipt and stale-event rejection |
| streaming ↔ GPU/voice | buffer + scheduler fixtures | actual F5/mic/GPU contention and render |
| screen ↔ Show Me Once ↔ CAPTURED | privacy fixtures pass; native disposable UIA component retest pass | real scoped user consent/focus/capture journey |
| idle exploration/evolution/training ↔ UI | source inventory only | notification rate/foreground responsiveness |
| cursor ↔ UIA/DOM/API fallback | cursor focus/no-replay fixtures pass | physical/native end-to-end acceptance |
| cancellation ↔ recovery | shared cancellation fixtures | process restart/approval invalidation live checks |
| cloud escalation | mocked provider eligibility/consent/privacy | display/action boundary and independent terminal receipt |

Feature ON/OFF component assertions are retained where existing tests implement them. No blanket ON/OFF route claim; unavailable complete route coverage is BLOCKED. All 22 stable user case IDs are in tests.jsonl.''')
doc('compatibility.md', '''Windows Python 3.10 runtime/version provenance is in baseline.json. The current app is checked out without its ignored per-feature environments/models. `python -m jarvis.launcher --check` ran both restricted and unrestricted. The unrestricted result is repair_required: isolated .venv/.venv-brain, Whisper/F5/Laya/Harness assets are missing. Docker 29.8.2, local Ollama and configured Ollama models were available to the unrestricted probe; the restricted probe could not reach them. No installs, service starts or model downloads were performed.

Existing Tk fixtures exercised disposable application widgets, not the user's Jarvis UI. One combined-suite Tk initialization failed but passed alone. Native 200-percent scaling, secure desktop, real speech, GPU training contention and UI worker crash acceptance remain BLOCKED/NOT RUN. Full repository regression is NOT RUN after the mandatory P1 stop gate. No Python/dependency migration is implied.''')
doc('security.md', '''P31-001 is an unresolved approval-isolation failure; zero unauthorized approvals cannot be claimed. Separate answer dict/event objects prove stale decision crossed the request boundary. No real send, deletion, account write, command execution or private screen capture was performed. No cloud provider inference ran; cloud tests use a fake adapter. Launcher service probes only query local health.

Fresh independent snapshot tests retain IR-001 private/unknown field screening. Registry adversarial/redaction tests retain local mock coverage. These do not establish total PII redaction across overlay/logs or final-boundary authorization for all tools. No paid API or credentials were required. Only authored fixture text is in event traces; no screenshot or recording is included.''')
doc('rollback.md', '''No application repair is installed, so no production rollback is required. Leave historical originals untouched. Review the added audit files and README notes separately; do not reset the original claude checkout or overwrite its config. Keep the failing fixture for the next independent review. No commits or merges were created by this audit.

From app/, use the existing original `.venv/Scripts/python.exe` interpreter:
```powershell
python -m pytest artifacts/jarvis-audit/modules/31-ui-island-pip/2026-10-19-independent-5b56f84/test_approval_binding.py -q
python -m pytest tests/test_independent_review.py tests/test_windows_commands.py tests/test_buddy.py tests/test_tool_registry_audit.py -q
python -m jarvis.launcher --check
python artifacts/jarvis-audit/modules/31-ui-island-pip/2026-10-19-independent-5b56f84/build_packet.py
```
The reproduction is expected to fail on pinned SHA. Test commands need normal fixture/process permissions; restricted failures are retained separately. Packet builder updates only this packet and the new reconciliation directory; do not use it to overwrite an accepted historical packet.''')
doc('codex-findings-reconciliation.md', '''Prior independent base: `36fbf3ce925080f7f54afa87eaf1d9b88414142d`; fix commit `32fdbfe`; evidence checkpoint `bc71fb7`; current pinned claude `5b56f84c1604de87bb8845027dffb5ce5943243b` includes the fixes through PR #6. Historical originals remain unchanged; every available prior artifact is hashed in prior-artifact-hashes.json.

| Actual prior ID | Current state | Fresh verification | Follow-up |
|---|---|---|---|
| IR-001 P1 snapshot privacy | FIXED at reviewed boundary | four synthetic privacy tests PASS | secure native field/live disclosure BLOCKED |
| IR-002 P1 training admission | FIXED at reviewed boundary | eight synthetic lease/admission tests PASS | GPU admission race/live contention remains unverified |
| IR-003 P1 CRLF recipe hash | FIXED source retained | windows_commands suite PASS | no current whole-runtime deployment trial |
| IR-004 P2 long Windows paths | UNVERIFIED runtime, source retained | historical lab-final.xml only; no fresh lab test | repeat deep-path disposable lab reproduction |

This is partial reconciliation, not a renewed whole-system certificate. The original eight failed installation-sensitive tests were not all rerun here. New P31-001 remains APPLIES/P1 and has no fix commit. See [new ledger](../../../reconciliation/findings-ledger.csv).''')
doc('sequence-diagrams.md', '''Actual current flow:
```mermaid
sequenceDiagram
  participant X as Actions / ToolRegistry
  participant A as App.request_approval
  participant Q as UIEventBuffer
  participant D as IslandDesk
  X->>A: kind, detail, cancelled
  A->>Q: answer dict + ready Event
  Q->>D: approval payload
  D->>D: append Approval with 180s lifetime
  Note over D: Approve callback has no card identity
  D->>D: pop current head, decide(True)
  D-->>A: ready Event + approved boolean
  A-->>X: approved and not cancelled
```
Failure sequence:
```mermaid
sequenceDiagram
  participant C as Old callback for A
  participant D as IslandDesk
  participant B as Request B
  C->>D: decide(True)
  D->>D: remove and approve A
  C->>D: stale decide(True)
  D->>B: approved=True (wrong request)
```
[Synthetic queue event trace](event-trace.json) preserves five terminal events; it is not a render/readback recording. Real GUI focus, secure-input, 200-percent scaling and process-crash evidence remain BLOCKED. Existing test XML contains fixture widget/readback assertions, accurately separate from full live acceptance.''')
doc('verdict.md', '''**NOT READY / BLOCKED — Prompt 31 not fully complete. Prompt 32 NOT STARTED.**

Confirmed unresolved P1 approval request-isolation defect P31-001: three failing assertions and one passing positive control. The companion reconciliation directs Codex to confirm read-only and reserves source repairs for Claude; the mandatory P1 gate stops advancement. No application repair was applied and no fix SHA exists.

Fresh baseline outside sandbox: **248 PASS / 2 FAIL / 8 SKIPPED**; both failed components passed separately (**2 PASS**), leaving combined-suite stability unproven. Focused neighbor/reproduction run: **85 PASS / 3 FAIL**. Final relocated approval reproduction: **1 PASS / 3 FAIL** (same cases, not additional unique coverage). Restricted baseline **225 PASS / 24 FAIL / 9 SKIPPED** is retained as a separate environment-limited run. Do not add reruns to inflate unique counts.

Launcher: **repair_required** for missing isolated runtimes/assets. Full repository regression, full user journey, complete feature ON/OFF and all live safety acceptance: **NOT RUN/BLOCKED**. No deployment, merge, installation, real account mutation, physical-input injection or private recording occurred.

Next permitted phase: Claude repairs request-bound approval and verifies final-executor scope; independently rerun P31-001, complete baseline instability triage and remaining Prompt 31 acceptance, then reconsider the stop gate before Prompt 32.''')

RECON.mkdir(parents=True, exist_ok=True)
write(RECON / 'artifact-inventory.md', '# Prior evidence inventory\n\nEvery available original file: [SHA-256 inventory](../modules/31-ui-island-pip/2026-10-19-independent-5b56f84/prior-artifact-hashes.json). Original verdict, test matrix/results, defect/security register, source patch, changed files, runtime environment, benchmarks, execution logs and scripts were found. Prior evidence was not modified.\n')
dump(RECON / 'review-revisions.json', environment)
with (RECON / 'findings-ledger.csv').open('w', newline='', encoding='utf-8') as stream:
    writer = csv.writer(stream)
    writer.writerow(['finding', 'prior_base', 'current_sha', 'fix_commit', 'status', 'fresh_test', 'remaining'])
    for ident, status, test in [('IR-001', 'FIXED_BOUNDARY', 'test_independent_review.py privacy cases'),
                                ('IR-002', 'FIXED_BOUNDARY', 'test_independent_review.py lease/admission cases'),
                                ('IR-003', 'FIXED_BOUNDARY', 'test_windows_commands.py'),
                                ('IR-004', 'UNVERIFIED', 'NOT RUN deep lab'),
                                ('P31-001', 'APPLIES', 'test_approval_binding.py 3 FAIL')]:
        writer.writerow([ident, environment['prior_review_base'], SHA, '32fdbfe' if ident.startswith('IR') else '', status, test,
                         'Independent live/cross-pillar acceptance incomplete; see module verdict'])
write(RECON / 'patch-assessment.md', '# Patch assessment\n\nThe four reviewed repairs are already ancestors of the pinned current claude merge. No blind patch application. Source hashes and original patch hash are retained. No new source fixes were applied; reconciliation reserves source repair for Claude. New approval defect is not repaired by the old patch.\n')
for name, rows in [('repro-results.jsonl', repro), ('legacy-regressions.jsonl', normal), ('cross-pillar-regressions.jsonl', target)]:
    write(RECON / name, ''.join(json.dumps(r) + '\n' for r in rows))
write(RECON / 'unresolved.md', '# Unresolved\n\nP31-001 permission isolation remains P1. Full legacy/cross-pillar reconciliation and live safety acceptance incomplete; original eight installation failures not all re-executed. IR-004 lacks a fresh runtime reproduction. Full master contract unavailable. Prompt 32 gated.\n')
write(RECON / 'handoff.md', '# Handoff\n\nCurrent independent audit pinned 5b56f84 on codex-review. No source repairs. Start with [Prompt 31 verdict](../modules/31-ui-island-pip/2026-10-19-independent-5b56f84/verdict.md) and its final failing approval fixture. Source repair is reserved for Claude, then obtain a fresh independent verification against its exact resulting SHA. Do not merge/deploy or advance to Prompt 32 while the gate is unmet.\n')
dump(OUT / 'packet-hashes.json', {p.relative_to(OUT).as_posix(): digest(p) for p in sorted(OUT.rglob('*'))
                               if p.is_file() and p.name != 'packet-hashes.json' and '__pycache__' not in p.parts})
print(json.dumps({'sha': SHA, 'baseline': counts(normal), 'targeted': counts(target), 'approval': counts(repro),
                  'emotion_count': metrics['emotion_count'], 'verdict': 'NOT READY / BLOCKED'}))
