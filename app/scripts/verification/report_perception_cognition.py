"""Publish evidence from executed module 02 assertions, never infer case passes."""
from collections import Counter
import difflib
import ast
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parents[2]
AUDIT = BASE/'artifacts/jarvis-audit'
OUT = AUDIT/'modules/02-perception-cognition'
PRE = BASE/'.jarvis-runtime/jarvis-audit/module02-pre/cognition.py'


def write(name, value):
    (OUT/name).write_text(value, encoding='utf-8')


def main():
    from scripts.verification.audit_catalog import reconcile
    reconcile()
    rows = [json.loads(line) for line in (AUDIT/'test-results.jsonl').read_text(encoding='utf-8').splitlines()]
    cases = [r for r in rows if r['id'].startswith('JRV-02-')]
    assert len(cases) == 32
    counts = Counter(r['status'] for r in cases)
    summary = json.loads((AUDIT/'summary.json').read_text())
    benchmark = json.loads((OUT/'benchmark-summary.json').read_text())
    source = BASE/'jarvis/cognition.py'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == benchmark['source_sha256']['after']
    full = ET.parse(OUT/'full-regression.xml')
    full_cases = list(full.iter('testcase'))
    full_seconds = float(next(full.iter('testsuite')).get('time', '0'))
    assert full_cases and all(t.find('failure') is None and t.find('error') is None and t.find('skipped') is None for t in full_cases)
    assert (OUT/'full-regression.xml').stat().st_mtime >= source.stat().st_mtime
    subset = list(ET.parse(OUT/'cases-and-contracts.xml').iter('testcase'))
    assert all(t.find('failure') is None and t.find('error') is None and t.find('skipped') is None for t in subset)
    for row in cases:
        row['source_paths'] = ['jarvis/cognition.py', 'jarvis/engine.py', 'jarvis/context_hub.py',
            'jarvis/actions.py', 'jarvis/self_evolution.py', 'jarvis/task_state.py', 'jarvis/cloud_policy.py']
        if row['status'] == 'NOT RUN':
            row['reason'] = {
                'JRV-02-008': 'Stalled tick and arbitrary-object conversion fixtures exist, but no end-to-end hard CPU-bound sensor hang/degradation assertion. Thread isolation cannot contain a native extension holding the GIL.',
                'JRV-02-010': 'No explicit reasoner-to-actuator task-ID agreement assertion or complete identity protocol proved; queue cancellation generations are not equivalent.',
                'JRV-02-027': '20 warm/5 cold samples per build executed in benchmark-summary.json; not authorized as a dedicated catalog assertion by the reconciler.',
                'JRV-02-032': 'Metadata-only tick/storage diagnostics tested; full cognition-to-action correlation and redaction journey not proved.'
            }.get(row['id'], 'Related regression coverage exists but this exact end-to-end catalog expectation has no dedicated executed assertion yet.')
    write('tests.jsonl', ''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in cases))
    remaining = [r['id'] for r in cases if r['status'] != 'PASS']
    write('remaining-case-ids.txt', '\n'.join(remaining)+'\n')
    patch = ''.join(difflib.unified_diff(PRE.read_text(encoding='utf-8').splitlines(True),
        source.read_text(encoding='utf-8').splitlines(True), fromfile='module02-pre/cognition.py', tofile='jarvis/cognition.py'))
    write('source.patch', patch)
    write('source-hashes.json', json.dumps(benchmark['source_sha256'], indent=2)+'\n')
    stats = {key: counts[key] for key in ('PASS','FAIL','BLOCKED','SKIPPED','NOT RUN')}
    write('scoped-report.json', json.dumps({'date':'2026-10-15 IST', 'status':'PARTIAL',
        'catalog_counts':stats, 'regression_cases':len(full_cases), 'targeted_cases':len(subset),
        'regression_seconds':full_seconds, 'next_case':remaining[0], 'scope':'Owned offline fixtures, no live account/UI/model acceptance'}, indent=2)+'\n')
    matrix = [
        ('Voice ingress/order', 'jarvis/engine.py', 'feed', 'Engine final segments dispatch immediately; attention is observational.'),
        ('Sensor ingress', 'jarvis/actions.py', '__init__', 'filtered report accepts string alert messages; it does not parse sensor content as commands.'),
        ('Bounded attention', 'jarvis/cognition.py', 'perceive', '200 retained percepts/inbox entries; voice 1.0, screen .85, sensor <=.7; seven ranked slots.'),
        ('Window lifecycle', 'jarvis/cognition.py', 'perceive_window', 'Atomic old-window removal, empty-title invalidation and publication race filter.'),
        ('Shared context', 'jarvis/context_hub.py', 'situation', 'Local working memory enrichment; explicit private payload rejected by fake cloud boundary.'),
        ('Idle preemption', 'jarvis/self_evolution.py', 'note_activity', 'Cooperative cancellation; does not forcibly stop a non-cooperative native call.'),
        ('Tick/persistence', 'jarvis/cognition.py', 'run', 'Monotonic deadlines; owned coalescing writer; diagnostics for errors, duration, overrun and stale heartbeat.'),
        ('Screen observation', 'jarvis/screen_awareness.py', 'observe', 'Separate current-window/suggestion workflow, not tool execution on the cognitive tick.'),
        ('Weather adapter', 'jarvis/weather_watch.py', 'check', 'External read adapter; real provider/network not exercised by this module.'),
        ('Recovery', 'jarvis/task_state.py', '__init__', 'Restarted running state becomes interrupted; uncertainty remains a resume blocker.')]
    lines = ['# Module 02 inventory — 2026-10-15 IST', '',
        f'**PARTIAL:** {stats}. No whole-system production certification. [Cases](tests.jsonl), [remaining IDs](remaining-case-ids.txt).', '',
        'Checkout commit `e9f6f735bc310d11e3cdecfbf95a85d96b170ec2`, existing branch `codex/jarvis-prove-fix-audit`; prior dirty work preserved. Windows main Python 3.10.6; RTX 3050 Laptop 4096 MiB and 31.35 GiB RAM from the October 14 inventory. No dependency, model or GPU allocation added.', '',
        '| Claim / boundary | Implementation | Evidence / limit |', '| --- | --- | --- |']
    for label, path, symbol, detail in matrix:
        text = (BASE/path).read_text(encoding='utf-8')
        match = re.search(r'^\s*def '+re.escape(symbol)+r'\(', text, re.M)
        line = text[:match.start()].count('\n')+1 if match else 1
        if path == 'jarvis/actions.py' and symbol == '__init__':
            action_class = next(n for n in ast.parse(text).body if isinstance(n, ast.ClassDef) and n.name == 'Actions')
            line = next(n.lineno for n in action_class.body if isinstance(n, ast.FunctionDef) and n.name == symbol)
        lines.append(f'| {label} | `{path}:{line}` `{symbol}` | {detail} |')
    lines += ['', 'Dependency order: sensor/Engine ingress → cognition attention → context_hub → independent Actions workers → outcome statistics; TaskState and approval gates govern writes. Tick metrics do not certify executor identity, actual sensor/parser isolation, voice naturalness or cloud availability.', '',
        f'Executed commands from app: `.venv/Scripts/python.exe -m pytest tests/test_perception_cognition_audit.py tests/test_cognition.py tests/test_cognition_and_routing.py tests/test_self_evolution.py tests/test_audit_resilience.py -q --junitxml=artifacts/jarvis-audit/modules/02-perception-cognition/cases-and-contracts.xml` ({len(subset)} PASS); full `-m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/02-perception-cognition/full-regression.xml` ({len(full_cases)} PASS).', '',
        'Owned user journey: Engine wake → final open command captured, voice ranked above weather without losing weather; two final commands retain order. Destructive task proposal reaches the real approval boundary with a fake executor that must remain uncalled. These are fixture journeys, not live microphone or desktop interaction.', '',
        'External side effects: zero live sends, account writes, personal deletes, OS changes or installs; only owned fixture/runtime metadata writes. No new long-running service. Existing start/close, writer recovery budget and Stop semantics retained.', '',
        'Launcher `-m jarvis.launcher --check` returned `ready`, scope `dependencies_and_configured_services`; saved at private `.jarvis-runtime/jarvis-audit/module02-pre/readiness-final.json`. It does not certify live voice/accounts or overall production. Compileall and git whitespace checks passed.', '',
        'Next exact unresolved case: **'+remaining[0]+'**. Later module audits must finish every remaining ID rather than infer success from neighboring tests.']
    write('inventory.md', '\n'.join(lines)+'\n')
    write('failures.md', '''# Reproductions and unresolved work

Initial dedicated baseline: **9 passed, 7 failed** in 6.09 seconds, [unmodified-source XML](baseline.xml). Failures: old screen retained after window switch; NaN/boolean/string rate and string enabled option; missing tick-error diagnostics; proposed-but-unexecuted task learned as success. Four invalid-option variants count as four assertions, not four distinct bugs.

First neighboring run: 59 passed, one failed because its old test expected raw disk-error text. The privacy contract now keeps only the exception type; the assertion was updated to verify payload omission, while preserving the single action call assertion. Final targeted XML contains the passing run.

Heap selection candidate failed the performance keep criterion: warm tick P95 0.023488 → 0.027676 ms; reverted before final validation. [Candidate raw data](benchmarks-heap-candidate.csv).

An initial full-regression attempt was interrupted after reverting that candidate; it produced no complete XML and is not counted as a passing run. Final full-regression.xml is the completed retained-source run.

An unscoped `pytest -q` attempt accidentally collected vendored repositories and failed collection (2335 errors, 15 skips, 186.56 seconds); missing independent dependencies included blockbuster, deerflow and pydantic. It is not a Jarvis test pass. Raw evidence is retained privately at `.jarvis-runtime/jarvis-audit/module02-pre/unscoped-collection-errors.xml`; no packages were installed. The final regression explicitly selects `pytest tests`, Jarvis's established suite. Vendored projects require their own declared environments and validation.

Open: CPU/native-parser hard-hang containment, task-ID disagreement enforcement, complete cognition trace correlation, remaining catalog fault/semantic/resource journeys. Stalled-thread telemetry and rejection of arbitrary serializers do not establish those broader guarantees. Live microphone/GPU/GUI/cloud/account validation was not run; native UIA foreground restrictions from the earlier audit still apply. Python 3.10 EOL remains a release risk.
''')
    write('changes.md', '''# Scoped changes

- `jarvis/cognition.py`: bounded typed percept admission without arbitrary serialization, surrogate replacement, finite numeric/boolean configuration checks, stale-window invalidation and race filtering, tick/error/overrun/stall metadata, payload-free persistence errors, avoid copying the drained inbox, and distinguish unexecuted proposals from attempted failures using task-start readback.
- `tests/test_perception_cognition_audit.py`: owned scenario, fault, concurrency, security and lifecycle assertions; no live sends or OS mutations. Existing `tests/test_cognition_and_routing.py`: expect private-safe disk error type.
- `scripts/verification/verify_perception_cognition.py`, `report_perception_cognition.py`: paired measurements, assertion-derived evidence and rollback patch. `audit_catalog.py`: explicitly authorize this reviewed test module's case IDs; parameter failures still dominate passes.
- `config/runtime_manifest.json`, app/root README, docs index and cognitive guide: behavior, diagnostics, limitations and dated verification. All prior changes remain in place. No dependency changes.
- `docs/system-map.md` links diagnostic limits; `artifacts/jarvis-audit/security-findings.md` updates only the repaired proposal-learning boundary while retaining broader open risks. Catalog ledgers, summary, module map and final report regenerated from executed assertions; previous final report archived.

The heap candidate was reverted. Final performance differences are small; correctness fixes are retained without claiming a model, audio or universal latency improvement. Review [scoped runtime diff](source.patch) and [hashes](source-hashes.json).
''')
    write('compatibility.md', '''# Compatibility — checked 2026-10-15 IST

Firecrawl retrieved these official primary sources live (`maxAge: 0`); no private repository text was uploaded:

- [Python 3.10 threading contract](https://docs.python.org/3.10/library/threading.html), documentation 3.10.22: Events support cooperative timed waiting; threads cannot be forcibly stopped/interrupted; the GIL limits CPU-bound thread isolation. No hard native-parser containment is claimed.
- [Python 3.10 heapq](https://docs.python.org/3.10/library/heapq.html), documentation 3.10.22: nlargest ordering matches reverse sorting, but implementation choice requires measurement. Candidate reverted after paired regression.
- [Official Python version status](https://devguide.python.org/versions/): 3.10 EOL **2026-10-01**; 3.15 first release **2026-10-09**, 3.14 **2025-10-07**. Those are branch first-release dates, not an assurance that all Jarvis ML environments support them. Installed main 3.10.6 is unsupported. No automatic interpreter/package migration, installation or model download occurred.

This change uses existing standard-library primitives and existing SciPy posterior calculation. It does not require a newer PyTorch/CUDA/SciPy or model release. Existing environment/dependency compatibility and separate F5 environment evidence remain in module 01. Two environments still lack pip for dependency checks. Windows scheduling is not hard real-time. No GPU/TTFT/first-audio benchmark applies to this model-free attention fixture.
''')
    write('rollback.md', '''# Rollback and deterministic continuation

Intentionally stop the owned Jarvis app before rollback. Preserve newer edits. Compare `source.patch` with `.jarvis-runtime/jarvis-audit/module02-pre/cognition.py`, then restore only the selected cognition hunks or that preimage if no later changes intervene. Never use git reset/clean or restore HEAD over prior dirty audit work. Keep all runtime/task state and uncertainty journals intact. No schema migration, permission change or replay queue was added.

To rerun: from app use `.venv/Scripts/python.exe -m pytest tests/test_perception_cognition_audit.py tests/test_cognition.py tests/test_cognition_and_routing.py tests/test_self_evolution.py tests/test_audit_resilience.py -q`; full `-m pytest tests -q`; `-m jarvis.launcher --check`. Benchmark: `scripts/verification/verify_perception_cognition.py` (preserve old artifacts first). Reconcile and publish: `-m scripts.verification.audit_catalog --reconcile`, then `-m scripts.verification.report_perception_cognition`. Publisher refuses a benchmark/source hash mismatch or an incomplete/failing full XML.

Continue at JRV-02-008 with bounded owned sensor-worker fault fixtures, then JRV-02-010 task identity. `remaining-case-ids.txt` is the exact module backlog; the top-level file preserves every pending ID across all 37 modules. Do not convert related regression coverage or benchmark samples into a catalog PASS without a dedicated executed assertion. Account/GUI/hardware prerequisites require separately scoped live acceptance. Whole-system release remains uncertified.
''')
    modules = json.loads((AUDIT/'module-map.json').read_text())
    modules[1].update(audit_status='PARTIAL', status='PARTIAL', catalog_counts=stats,
        reason='Bounded repairs and fixture proofs executed; unresolved hard-hang/identity and exact catalog journeys remain')
    (AUDIT/'module-map.json').write_text(json.dumps(modules, indent=2)+'\n', encoding='utf-8')
    previous = AUDIT/'final-report-before-module02.md'
    if not previous.exists():
        previous.write_bytes((AUDIT/'final-report.md').read_bytes())
    totals = summary['catalog_counts']
    final = f'''# Jarvis audit progress — 2026-10-15 IST

**Prompt 02 is PARTIAL; whole-system production readiness is uncertified.** Module 02: {stats}. Final targeted regression: **{len(subset)} PASS**; full regression: **{len(full_cases)} PASS in {full_seconds:.2f} seconds**. [Module inventory and exact entry points](modules/02-perception-cognition/inventory.md), [case ledger](modules/02-perception-cognition/tests.jsonl), [targeted XML](modules/02-perception-cognition/cases-and-contracts.xml), [full XML](modules/02-perception-cognition/full-regression.xml).

Repo commit `e9f6f735bc310d11e3cdecfbf95a85d96b170ec2`, branch `codex/jarvis-prove-fix-audit`; existing dirty work preserved, no commits or deployment performed. Windows, main Python 3.10.6, RTX 3050 Laptop 4096 MiB, 31.35 GiB RAM (hardware census October 14). No GPU/model workload was launched by module 02.

Launcher `-m jarvis.launcher --check`: **ready**, scope `dependencies_and_configured_services` (private readback `.jarvis-runtime/jarvis-audit/module02-pre/readiness-final.json`). Compileall and whitespace checks passed. This is readiness validation, not real account/UI/voice acceptance.

Full 1,184-case catalog: **{totals}**. [Exact totals by category and tier](summary.json), [all case IDs and evidence](test-results.jsonl), [all pending IDs](remaining-case-ids.txt). Do not add overlapping regression runs as unique tests. All 37 modules remain enumerated in [module-map.json](module-map.json); module 01 has all 32 owned-fixture proofs, module 02 is partial, later modules retain their recorded pending status.

## Fixes and results

Old window observations now leave attention atomically, including empty-title switches and publication races. Invalid cognitive configuration fails explicitly. Text admission bounds labels/content and rejects arbitrary object conversion; malformed surrogate text can persist. Tick errors, overruns and stalled heartbeat are observable without exception payloads. Pending proposals do not inflate successful task history; attempted failures followed by recovery offers still count. Existing bounded writer recovery and intentional Stop semantics remain unchanged. No real sends, account writes, personal-file deletes, OS mutations or installations occurred.

The baseline reproduced 7 failed assertions / 9 passed. [Failures and reverted candidate](modules/02-perception-cognition/failures.md), [exact changed files](modules/02-perception-cognition/changes.md), [scoped diff](modules/02-perception-cognition/source.patch), [rollback](modules/02-perception-cognition/rollback.md).

Same-fixture final warm tick P95: **{benchmark['before_warm_tick']['p95_ms']:.6f} → {benchmark['after_warm_tick']['p95_ms']:.6f} ms**. Cold constructor/import P95: **{benchmark['before_cold_startup']['p95_ms']:.3f} → {benchmark['after_cold_startup']['p95_ms']:.3f} ms** (5 samples per build); 20 alternating warm samples per build. With 180 ms injected storage delay, maximum tick interval: **{benchmark['before_schedule']['max_ms']:.3f} → {benchmark['after_schedule']['max_ms']:.3f} ms** (12 intervals/build). Small/noisy differences establish no universal speedup. Slower heap candidate reverted. RSS is sampled, not peak; no model TTFT, audio latency or GPU gain claimed. [CSV](modules/02-perception-cognition/benchmarks.csv), [raw measurements](modules/02-perception-cognition/benchmark-summary.json).

## Known limits and continuation

Next incomplete ID: **{summary['next_case']}**. Hard CPU/native sensor-hang containment, reasoner/actuator task-ID mismatch, remaining exact fault/semantic/resource journeys and full cognition correlation/redaction remain unproved. Stalled-tick detection is diagnostic; it does not forcibly terminate a hung native call or authorize replay. Cooperative idle preemption is not GPU preemption. Live voice/UI/cloud/account validation was not run; earlier native UIA foreground restriction remains. [Module backlog](modules/02-perception-cognition/remaining-case-ids.txt).

Release risks also include unsupported Python 3.10, two environment dependency checks without pip, ability host isolation and incomplete repository-wide security/live acceptance. [Official upstream dates and compatibility](modules/02-perception-cognition/compatibility.md), [existing security findings](security-findings.md), [previous architecture report](final-report-before-module02.md). No whole-system completion or production deployment is claimed.
'''
    (AUDIT/'final-report.md').write_text(final, encoding='utf-8')
    print(json.dumps({'module02':stats, 'targeted_pass':len(subset), 'full_pass':len(full_cases), 'next':remaining[0]}, indent=2))


if __name__ == '__main__':
    main()
