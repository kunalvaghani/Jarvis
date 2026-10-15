"""Assertion-derived module 03 report and exact pending catalog ledger."""
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parents[2]
AUDIT = BASE/'artifacts/jarvis-audit'
OUT = AUDIT/'modules/03-intent-direct'
PRE = BASE/'.jarvis-runtime/jarvis-audit/module03-pre'


def write(name, text):
    (OUT/name).write_text(text, encoding='utf-8')


def main():
    from scripts.verification.audit_catalog import reconcile
    full = ET.parse(OUT/'full-regression.xml')
    nodes = list(full.iter('testcase'))
    assert nodes and all(n.find('failure') is None and n.find('error') is None and n.find('skipped') is None for n in nodes)
    for path in (BASE/'jarvis/intent_catalog.py', BASE/'jarvis/engine.py', BASE/'tests/test_intent_direct_audit.py'):
        assert (OUT/'full-regression.xml').stat().st_mtime >= path.stat().st_mtime
    targeted = list(ET.parse(OUT/'cases-and-contracts.xml').iter('testcase'))
    assert all(n.find('failure') is None and n.find('error') is None and n.find('skipped') is None for n in targeted)
    seconds = float(next(full.iter('testsuite')).get('time', '0'))
    reconcile()
    global_summary = json.loads((AUDIT/'summary.json').read_text())
    rows = [json.loads(line) for line in (AUDIT/'test-results.jsonl').read_text().splitlines()]
    cases = [r for r in rows if r['id'].startswith('JRV-03-')]
    assert len(cases) == 32
    for row in cases:
        if row['id'] == 'JRV-03-005' and row['status'] == 'NOT RUN':
            row['reason'] = 'Safe temporal-file routing is asserted, but actual newest-file ambiguity resolution or clarification has no complete executed assertion.'
    stats = Counter(r['status'] for r in cases)
    counts = {key:stats[key] for key in ('PASS','FAIL','BLOCKED','SKIPPED','NOT RUN')}
    pending = [r['id'] for r in cases if r['status'] != 'PASS']
    write('tests.jsonl', ''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in cases))
    write('remaining-case-ids.txt', '\n'.join(pending)+'\n')
    benchmark = json.loads((OUT/'benchmark-summary.json').read_text())
    for path in (BASE/'jarvis/commands.py', BASE/'jarvis/intent_catalog.py', BASE/'jarvis/engine.py'):
        assert (OUT/'benchmark-summary.json').stat().st_mtime >= path.stat().st_mtime
    patch = ''
    hashes = {}
    for name in ('intent_catalog.py', 'commands.py', 'engine.py'):
        current = BASE/'jarvis'/name
        before_path = PRE/name
        before = before_path.read_text(encoding='utf-8') if before_path.exists() else current.read_text(encoding='utf-8').replace(
            "            if not whole and index < len(clauses) - 1:\n                clause = clause.rstrip(',;').rstrip()  # punctuation before a spoken command boundary\n", '')
        hashes[name] = {'before':hashlib.sha256(before_path.read_bytes() if before_path.exists() else before.encode()).hexdigest(),
            'before_representation':'captured bytes' if before_path.exists() else 'reconstructed normalized text',
            'after':hashlib.sha256(current.read_bytes()).hexdigest()}
        patch += ''.join(difflib.unified_diff(before.splitlines(True), current.read_text(encoding='utf-8').splitlines(True),
            fromfile='module03-pre/'+name, tofile='jarvis/'+name))
    write('source.patch', patch)
    write('source-hashes.json', json.dumps(hashes, indent=2)+'\n')
    write('scoped-report.json', json.dumps({'date':'2026-10-15 IST', 'status':'PARTIAL', 'catalog_counts':counts,
        'targeted_pass':len(targeted), 'full_pass':len(nodes), 'full_seconds':seconds, 'next_case':pending[0]}, indent=2)+'\n')
    write('inventory.md', f'''# Module 03 intent/direct audit — 2026-10-15 IST

**PARTIAL:** {counts}. [Executed cases](tests.jsonl), [exact pending IDs](remaining-case-ids.txt). Eleven named scenarios have controlled routing/handler fixture assertions. JRV-03-005 remains NOT RUN: safe latest-file delegation is tested, but actual ambiguity resolution/clarification has no complete assertion. The additional fault/concurrency/security/performance matrix remains separately pending where no exact assertion exists. No production or live GUI certification.

Checkout commit `e9f6f735bc310d11e3cdecfbf95a85d96b170ec2`, branch `codex/jarvis-prove-fix-audit`; existing dirty work preserved. Main Python 3.10.6, Windows, RTX 3050 Laptop 4096 MiB/31.35 GiB RAM from prior inventory. No new dependency/model/GPU allocation.

| Claim | Real path / boundary | Evidence / limit |
| --- | --- | --- |
| Deterministic reflexes | `jarvis/commands.py:parse`, immutable REFLEX | Exact pause/volume up/open Chrome bypass canonical and learned interpretation. No LLM invoked by parsing. |
| Everyday canonical form | `jarvis/phrasing.py:canonical` | Leading synonyms/wrappers and existing composed-versus-verbatim writing policy; finite coverage, not arbitrary language understanding. |
| Built-in precedence | `jarvis/intent_catalog.py:match`, COMPILED tuple and fingerprint | Full-match rules before generic app handlers and learned abilities. Four narrowly anchored additions. |
| Alias/collision handling | `jarvis/names.py:rank_spelling`, `Actions._execute` open branch | VS Code aliases tested; exact configured Chrome launch goes through a fake process transport once. |
| Negative command | `commands._parse`, `Engine.feed` | Please do not open Chrome produces no dispatch; approval/negative policy preserved. |
| Compound request | `engine.Engine._feed` | Open Notepad, then type hello dispatches ordered commands and binds target Notepad; no actual typing. |
| Latest-file ambiguity | intent temporal-file rule → task planner | Avoids guessed app launch. Actual newest-file resolution and live ambiguity dialogue not verified. |
| Volume/unknown tool | `spotify.volume`, commands toolkit admission | 150 percent rejected before fake volume setter; unknown tool and exact unknown-command phrase refused. |
| Tab scope | built-in Windows command 329 | Corrected tab phrase maps to existing tab-close command; no real shortcut/browser closure. Existing approval/target checks remain. |

Dependency order: Engine final speech → deterministic parse/phrasing/catalog → registered Actions handlers → owned executors and approval/readback. The cognition tick observes this pipeline, rather than executing it.

Commands executed from app: `.venv/Scripts/python.exe -m pytest tests/test_intent_direct_audit.py tests/test_intent_testbook.py tests/test_natural_names.py tests/test_jarvis.py tests/test_audit_resilience.py -q --tb=short --junitxml=artifacts/jarvis-audit/modules/03-intent-direct/cases-and-contracts.xml` (**{len(targeted)} PASS**); full `-m pytest tests -q --tb=short --junitxml=artifacts/jarvis-audit/modules/03-intent-direct/full-regression.xml` (**{len(nodes)} PASS**, {seconds:.2f} seconds). [Targeted XML](cases-and-contracts.xml), [full XML](full-regression.xml).

Owned fixture journey: real Engine routes Chrome to real Actions open handling with fake Popen and fake foreground captures; exactly one executable dispatch. Negated input produces zero requests. Compound open/type preserves order and explicit target. No live app/account/desktop writes, personal deletes or dependency installs. Launcher `--check` readiness is recorded privately at `.jarvis-runtime/jarvis-audit/module03-pre/readiness-final.json`; readiness is not live feature acceptance.

Warm mixed-corpus per-phrase P95 {benchmark['before_warm_per_phrase']['p95_ms']:.4f} → {benchmark['after_warm_per_phrase']['p95_ms']:.4f} ms. Cold import plus 12-phrase batch P95 {benchmark['before_cold_import_and_batch']['p95_ms']:.2f} → {benchmark['after_cold_import_and_batch']['p95_ms']:.2f} ms. [CSV](benchmarks.csv), [raw corpus/routes](benchmark-summary.json). Sampling is model-free, RSS is not peak, audio/TTFT/GPU metrics N/A. Warm benefit comes partly from eliminating formerly rejected slow routes; it does not prove universal startup or speech speedup.

Next exact module case: **{pending[0]}**. Global unfinished cognition cases remain in the top-level ledger; moving to Prompt 03 does not mark them complete.
''')
    write('failures.md', '''# Baseline and diagnosis

Initial module assertions: **8 failed, 6 passed in 4.51 seconds**, [baseline XML](baseline.xml). Five implementation failures: temporal spreadsheet fell into generic app open, sound-down-notch and pause-current phrases were unknown, separator comma leaked into the Notepad target, and corrected tab-close phrase was unknown.

Three baseline failures were fixture errors: two tests omitted the fake desktop required for foreground capture, and one used the wrong Spotify volume function signature. They were corrected without production changes. A later compound test expected verbatim write_text despite the established compose_text policy for bare type hello; it now accepts the existing safe composed/verbatim route while still asserting order, content and bound target. That fixture correction is not a production fix.

Final targeted and full XML contain passing runs. No live Chrome, audio, shortcut or typing experiment took place. Generic fault/concurrency/security/resource catalog expectations lacking dedicated executed assertions remain NOT RUN. Unsupported Python 3.10, hard cognition parser-hang containment, task-ID agreement and repository ability isolation remain broader release risks.

The latest-file test's administrative case-ID label was removed during the full run because its body only proves safe routing, not complete ambiguity resolution. Its unchanged assertion body was rerun in the final targeted suite. The full XML may retain its earlier name; the reconciler authorizes case IDs only from the dedicated final targeted XML, so that incidental name cannot grant JRV-03-005 a PASS.
''')
    write('changes.md', '''# Exact scoped changes

- `jarvis/intent_catalog.py`: four anchored built-in patterns: latest/most-recent document references route to the planner, sound up/down a notch follows active media, pause what is playing routes to existing pause, and corrected tab-close phrase uses existing command 329.
- `jarvis/engine.py`: remove trailing comma/semicolon only before a split command boundary; preserve existing writing policy and final-transcript rules.
- `tests/test_intent_direct_audit.py`: real parser/Engine/Actions assertions with fake launch/desktop/audio transports, no live effects. No production change to commands.py, names.py, Spotify or permission gates.
- `scripts/verification/verify_intent_direct.py`, `report_intent_direct.py`, and reviewed case allowlist in `audit_catalog.py`: reproducible paired parser timings, assertion-derived report and exact result accounting.
- Root/app README, natural-language guide, docs index, module reports and global ledgers: dated behavior, fixture limits, metrics and rollback. Earlier module 02 artifacts remain intact.

No dependency, model, tool name, configuration schema, persistent service or approval change. [Runtime diff](source.patch), [source hashes](source-hashes.json). Engine preimage is reconstructed by removing only the two inserted boundary lines; existing dirty engine changes remain, rather than restoring HEAD.
''')
    write('compatibility.md', '''# Official compatibility check — 2026-10-15 IST

Firecrawl fetched [Python 3.10 regular-expression documentation](https://docs.python.org/3.10/library/re.html) live (`maxAge: 0`), documentation 3.10.22. Full matching covers an entire command; substring search is inappropriate for these new intent families. Existing compiled rule tuples reuse regex objects. No new regex package or model is required.

[Python version status](https://devguide.python.org/versions/) checked during module 02: Python 3.10 EOL 2026-10-01; Python 3.15 branch first release 2026-10-09. Those dates do not certify ML runtime compatibility. Installed main 3.10.6 remains a release risk; no interpreter migration or installation occurred. Built-in deterministic command routing needs neither CUDA nor GPU memory. External app/keymap/window availability remains an independent live acceptance prerequisite. Paired improvements are limited to the authored corpus.
''')
    write('rollback.md', '''# Safe rollback and resume

Intentionally Stop Jarvis before rollback. Preserve later edits. Review source.patch and restore only the four inserted catalog patterns and two Engine punctuation lines, or compare with the captured `module03-pre/intent_catalog.py`. commands.py was captured but not changed. The Engine preimage is reconstructed from the two audited inserted lines, preserving earlier dirty edits. Never reset/clean the repository or replay queued/uncertain actions. No data/schema migration occurred.

From app: `.venv/Scripts/python.exe -m pytest tests/test_intent_direct_audit.py tests/test_intent_testbook.py tests/test_natural_names.py tests/test_jarvis.py tests/test_audit_resilience.py -q`; full `-m pytest tests -q`; `-m jarvis.launcher --check`. Parser benchmark: `scripts/verification/verify_intent_direct.py` (archive measurements before repeat). Report: `-m scripts.verification.report_intent_direct`, which requires complete passing fresh XML. Exact unfinished IDs are in remaining-case-ids.txt and the global catalog. Continue the first pending generic module case with dedicated fault fixtures; prior JRV-02-008/JRV-02-010 remain unresolved.
''')
    modules = json.loads((AUDIT/'module-map.json').read_text())
    modules[2].update(status='PARTIAL', audit_status='PARTIAL', catalog_counts=counts,
        reason='Eleven named scenarios asserted; latest-file ambiguity and exact fault matrix pending')
    (AUDIT/'module-map.json').write_text(json.dumps(modules, indent=2)+'\n')
    archived = AUDIT/'final-report-before-module03.md'
    if not archived.exists():
        archived.write_bytes((AUDIT/'final-report.md').read_bytes())
    write('verification-summary.json', json.dumps({'full_pass':len(nodes), 'targeted_pass':len(targeted), 'catalog':counts}, indent=2)+'\n')
    final = f'''# Jarvis audit progress — 2026-10-15 IST

**Prompt 03 is PARTIAL; whole-system production readiness remains uncertified.** Eleven named intent scenarios have controlled routing/handler fixture assertions. Latest-file safe delegation is tested, but JRV-03-005 ambiguity resolution remains unproved. Module counts: **{counts}**. Targeted: **{len(targeted)} PASS**; established Jarvis full suite: **{len(nodes)} PASS in {seconds:.2f} seconds**. [Module inventory, source matrix and command evidence](modules/03-intent-direct/inventory.md), [case ledger](modules/03-intent-direct/tests.jsonl), [full XML](modules/03-intent-direct/full-regression.xml), [targeted XML](modules/03-intent-direct/cases-and-contracts.xml).

Commit `e9f6f735bc310d11e3cdecfbf95a85d96b170ec2`, branch `codex/jarvis-prove-fix-audit`; prior dirty work preserved, no publish/deployment/commit. Windows, main Python 3.10.6, RTX 3050 Laptop 4096 MiB and 31.35 GiB RAM from October 14 hardware census. No new model/GPU or dependency requirement. Launcher `--check` readiness is separate from live feature acceptance.

Full 1,184-case catalog: **{global_summary['catalog_counts']}**. [Category/tier totals](summary.json), [all cases](test-results.jsonl), [37 enumerated module statuses](module-map.json), [exact pending IDs](remaining-case-ids.txt). Do not sum overlapping test runs. Module 01 retains all 32 owned-fixture proofs; module 02 retains 18 PASS/14 NOT RUN, 108 targeted and 1,927 full passes; module 03 retains its counts above. Later modules remain pending as recorded.

Four anchored intent rules and safe compound-boundary punctuation repair address five baseline implementation failures. Three baseline fixture errors and one later writing-policy expectation were corrected separately and are not credited as product fixes. Existing zero-model reflexes, aliases, approvals, target checks and uncertain-write policy remain. [Failures](modules/03-intent-direct/failures.md), [exact changed files](modules/03-intent-direct/changes.md), [scoped patch](modules/03-intent-direct/source.patch), [rollback](modules/03-intent-direct/rollback.md).

Paired mixed-corpus warm P95 per phrase **{benchmark['before_warm_per_phrase']['p95_ms']:.4f} → {benchmark['after_warm_per_phrase']['p95_ms']:.4f} ms**; cold import/batch P95 **{benchmark['before_cold_import_and_batch']['p95_ms']:.2f} → {benchmark['after_cold_import_and_batch']['p95_ms']:.2f} ms**. Twenty alternating warm and five cold samples per build; RSS sampled, not peak. No universal speedup, model TTFT, audio latency or GPU improvement claimed. [Measurements](modules/03-intent-direct/benchmarks.csv), [upstream compatibility/date evidence](modules/03-intent-direct/compatibility.md). Module 02 timings and reverted heap candidate remain in the [previous report](final-report-before-module03.md).

No real launches, shortcuts, typing, sends, account writes, personal deletes, OS setting changes, installations or learned script execution occurred; owned fixtures use fake transports and metadata state. Live voice/GUI/cloud/account acceptance remains unrun. First incomplete global ID: **{global_summary['next_case']}**; first incomplete module 03 ID: **{pending[0]}**. Hard sensor/native hang containment, reasoner/actuator task identity, unsupported Python 3.10, two unchecked dependency environments and host ability isolation remain release risks. [Security findings](security-findings.md), [module 03 backlog](modules/03-intent-direct/remaining-case-ids.txt). No claim of production completion.
'''
    (AUDIT/'final-report.md').write_text(final, encoding='utf-8')
    print(json.dumps({'module03':counts, 'full_pass':len(nodes), 'targeted_pass':len(targeted), 'next':pending[0]}, indent=2))


if __name__ == '__main__':
    main()
