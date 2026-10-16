"""Publish executed Prompt24 evidence without converting partial checks into catalog PASS."""
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(BASE))
OUT = BASE/'artifacts/jarvis-audit'; MOD = OUT/'modules/24-whatsapp'
PRE = BASE/'.jarvis-runtime/jarvis-audit/module24-pre'
BLOCKERS = {
1: 'Read/check commands route into reply/draft flows; an independently scoped read-only friend lookup is not proved.',
4: 'Duplicate display names now fail closed and ask for a unique saved name; UIA rows expose no stable contact/account ID for a meaningful disambiguation choice.',
6: 'Minimized-window restoration and correct native foreground need an explicitly authorized owned UI fixture; no live window was focused.',
7: 'Incoming-call watcher and composing task lack a complete draft-preserving arbitration protocol.',
8: 'Group detection is heuristic; exact group membership/recipients are not included in the send approval.',
10: 'No dedicated delete-chat workflow; generic planner deletion approval/non-action proof is absent.',
11: 'Outgoing calls are not implemented here. Incoming-call replacement/Stop guards passed but cannot prove outgoing-call cancellation.',
12: 'Fresh recipient/compose checks passed; row selection still retains a UIA element across search/choice, and full native UI-redesign re-grounding is unproved.',
17: 'Text journal serializes sends, but no complete five-request x20 search/approval/window workflow proof; shared prompt stack and watcher remain potential contention boundaries.',
18: 'Cancellation after answered approval and before Enter passed; complete TaskState cancellation during readback remains unproved.',
21: 'Drafting uses local Ollama and journal omits plaintext, but cards/transcripts include private text. Complete cloud/telemetry/cache secrecy oracle absent.',
22: 'Unicode/quotes and a >500-character body preview passed; long contact/title/path journey lacks executed proof (contact admission caps at200).',
25: 'No complete RAM/GPU-pressure admission plus core-command responsiveness fixture; no heavyweight model test ran.',
26: 'Uncertain identical text sends refuse replay; a new explicitly approved request can repeat a completed send. Event-ID dedupe, attachments and calls lack a common durable protocol.',
27: 'Equivalent normalization CPU/tracemalloc A/B only; not five cold processes plus20 complete UI requests with RSS/VRAM and audio latency.',
29: 'Public request flags/schema validated; watcher config still lacks complete typed enum/range validation with diagnostics.',
30: 'Text disconnect/crash checkpoint proved; complete watcher/COM worker disconnect recovery with task provenance is unproved.',
32: 'Hash-only text journals and readback fixtures passed; cross-flow correlation, exception and transcript redaction are incomplete.'}


def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write(name, text): (MOD/name).write_text(text.strip()+'\n', encoding='utf-8')
def stats(name):
    tree = ET.parse(MOD/name); nodes = list(tree.iter('testcase'))
    return dict(PASS=sum(n.find('skipped') is None and n.find('failure') is None and n.find('error') is None for n in nodes),
                FAIL=sum(n.find('failure') is not None or n.find('error') is not None for n in nodes),
                SKIPPED=sum(n.find('skipped') is not None for n in nodes),
                seconds=sum(float(n.get('time', 0)) for n in tree.iter('testsuite')))


def marker(path, text):
    value = path.read_text(encoding='utf-8')
    value = re.sub(r'\n<!-- prompt24-audit -->.*?<!-- /prompt24-audit -->\n', '', value, flags=re.S)
    first, rest = value.split('\n', 1)
    path.write_text(first+'\n\n<!-- prompt24-audit -->\n'+text+'\n<!-- /prompt24-audit -->\n'+rest, encoding='utf-8')


def main():
    from scripts.verification import audit_catalog
    main_xml = MOD/'focused-final.xml'
    # Preserve independently executed main output before aggregating the real supplement.
    if not main_xml.exists(): main_xml.write_bytes((MOD/'cases-and-contracts.xml').read_bytes())
    combined = ET.Element('testsuites', name='Prompt24 executed focused and independent supplemental checks')
    for path in (main_xml, MOD/'catalog-supplements.xml'):
        combined.extend(list(ET.parse(path).getroot()))
    ET.ElementTree(combined).write(MOD/'cases-and-contracts.xml', encoding='utf-8', xml_declaration=True)
    baseline, target, full = (stats(n) for n in ('baseline.xml', 'cases-and-contracts.xml', 'full-regression.xml'))
    assert baseline['FAIL'] == target['FAIL'] == full['FAIL'] == 0
    frozen = read(MOD/'full-start-source-hashes.json')
    assert all(sha(BASE/p) == h for p, h in frozen.items())
    ready, bench, env = (read(MOD/n) for n in ('readiness.json', 'benchmark-summary.json', 'environment.json'))
    assert ready['status'] == 'ready' and bench['equivalent'] and bench['real_external_actions'] == 0
    modules = read(OUT/'module-map.json')
    modules[23].update(sources=['jarvis/whatsapp.py', 'jarvis/whatsapp_writes.py', 'jarvis/messengers.py',
        'jarvis/actions.py', 'jarvis/commands.py', 'jarvis/knowledge_worker.py', 'docs/whatsapp.md'],
        test_candidates=['tests/test_whatsapp.py', 'tests/test_whatsapp_audit.py', 'scripts/verification/test_whatsapp_audit.py'],
        status='PARTIAL', reason='14 catalog fixture PASS/18 BLOCKED. No live WhatsApp/Telegram account or native window actions.')
    (OUT/'module-map.json').write_text(json.dumps(modules, indent=2)+'\n')
    audit_catalog.reconcile()
    catalog = [json.loads(s) for s in (OUT/'test-results.jsonl').read_text(encoding='utf-8').splitlines()]
    cases = [r for r in catalog if r['id'].startswith('JRV-24-')]
    assert Counter(r['status'] for r in cases) == {'PASS':14, 'BLOCKED':18}
    assert {int(r['id'][-3:]) for r in cases if r['status']=='BLOCKED'} == set(BLOCKERS)
    write('tests.jsonl', '\n'.join(json.dumps(r, ensure_ascii=False) for r in cases))
    summary = read(OUT/'summary.json')
    gates = '\n'.join(f'- **JRV-24-{n:03} BLOCKED:** {reason}' for n, reason in BLOCKERS.items())
    write('remaining-case-ids.txt', '\n'.join(f'JRV-24-{n:03}' for n in BLOCKERS))
    scope = ('All sends/keys/UIA/LLM transports use authored fakes, isolated journals and one owned child exiting23. '
             'No personal chat read, message/call/file send, delete, account write, native window activation, '
             'credential read/setup, installation, service restart or heavyweight inference. '
             'The full suite includes pre-existing owned headless browser/local-server fixtures. '
             'No new screenshot: existing sample card artwork remains labelled as rendered preview.')
    matrix = '''| Claim | Source / actual path | Evidence / limitation |
| --- | --- | --- |
| Dispatch | commands.parse→whatsapp.parse_command→Actions.execute | whatsapp_send/reply preserved; bounded request_data runs before TaskState/window activity |
| Preview and approval | approve_and_send / auto_reply→Prompt / ask; Actions.submit→answer_prompt | Exact recipient/text card, edits then fresh approval; expired/boolean answers refused, resolver serialized, cancellation wins wait return |
| Identity | match_contacts→find_contact→open_row→is_open | Discovery stays phonetic; write identity now NFC/casefold literal, no fuzzy alias; ambiguous repeated names fail closed, no stable ID |
| Typing/send | send_approved_text→type_draft→press_send | Recheck empty compose/recipient/focus, exact normalized text, Enter once, fresh status Sent/Delivered/Read; Pending is uncertain, no partial-draft deletion |
| Recovery | whatsapp_writes.text_send→TaskState.checkpoint | Hash-only journal before typing; text-send desktop lock; damaged/pending checkpoint refuses replay after actual child crash; successful new approved requests may repeat |
| Calls | Watcher.run→call_controls→handle_call→press | Fresh caller/kind and Stop checked; changed caller denied; outgoing-call flow and same-caller ring-instance identity absent |
| Local composition | draft→knowledge_worker.chat→127.0.0.1:11434 | Structured untrusted history, system instruction stays separate, client closes; no complete transcript/cloud privacy oracle |
| Other apps | messengers.send / send_telegram | Telegram optional; other named apps honestly refuse. Signed-in Telegram and file-attachment paths are not covered by new text journal |
| Watcher/config | config.whatsapp→Actions.start_whatsapp_watch | enabled/watch_messages/auto_draft_replies/watch_calls true; groups/muted false,max5,poll2s; shared prompts, config typing and native contention remain open |
| Runtime contract | existing manifest jarvis.whatsapp and dependency group | No new long-running service/dependency; launcher readiness passed; Start/Stop/bootstrap/recovery source unchanged |'''
    write('inventory.md', '# Prompt24 — WhatsApp audit, 2026-10-16 IST\n\n**PARTIAL: 14 catalog PASS /18 BLOCKED.** '
          'These are fixture proofs, not production/live-account acceptance.\n\n'+scope+'\n\n'+matrix+'\n\n'
          +'## Unresolved catalog contracts\n\n'+gates+'\n\n[Complete report](../../final-report.md) · [Executed assertions](cases-and-contracts.xml) · [Source diff](source.patch)')
    write('failures.md', '# Failures and limits\n\nBaseline17 PASS. Actual reproduction:10 FAIL/2 PASS/24 explicit skips, '
          'including absent cancellation API on press_send. The initial test import error was corrected before this reproduction. '
          'First fix iteration29 PASS/24 skips. A subsequent sandbox run failed9 temporary atomic-replacement/child fixtures '
          '(WinError5); the outside-sandbox isolated neighbors passed73/25, then106/17. '
          'Final focused77/17, independent supplement2/1. No failed assertion is removed from historical XML.\n\n'
          'Fixed: expired/boolean/racing approval, unreadable-compose treated as empty, display-name collapse, '
          'stale target/draft/focus before Enter, false Pending success, unsafe partial-draft deletion, '
          'different-caller approval reuse, malformed public input and missing accessibility dependency. '
          'Durable text journal adds crash/timeout refusal; earlier implementation had no persistent boundary.\n\n'+gates)
    compatibility = '''# Compatibility, checked2026-10-16 IST

Installed **comtypes1.4.17**, Python3.10.6 on Windows26200. [PyPI1.4.17](https://pypi.org/project/comtypes/1.4.17/) lists release2026-09-21, Windows and Python>=3.9; current project listing and [official release notes](https://github.com/enthought/comtypes/releases/tag/1.4.17) identify1.4.17 as latest. Notes include message-loop API consolidation, GetEvents diagnostics and a structure-packing error fix. No package installed; implementation improvements retained instead. This does not certify every UIA COM binding or native WhatsApp build.

[Microsoft UIA element acquisition](https://learn.microsoft.com/en-us/dotnet/framework/ui-automation/obtaining-ui-automation-elements), displayed2021-09-15 (retrieval metadata updated2026-03-30), advises scoped searches; [ElementNotAvailableException](https://learn.microsoft.com/en-us/dotnet/api/system.windows.automation.elementnotavailableexception?view=windowsdesktop-10.0) documents closed/removed elements. These contracts support fresh observation; they do not prove WhatsApp selectors. Public sources retrieved with Firecrawl. A local PyPI JSON attempt failed DNS; it supplied no release evidence.

No public WhatsApp Desktop release/build census obtained; historical2.2639.100.0 remains dated2026-10-10, not current proof. No WhatsApp API dependency or paid API added. No GPU allocation/model download. Installed requests2.34.2/pytest8.4.2/psutil7.2.2 unchanged. Full COM/GUI/live acceptance and Python patch-version migration remain outside this check.
'''
    write('compatibility.md', compatibility)
    write('rollback.md', '# Rollback\n\nPreserved dirty branch audit/12-tool-registry at commit9bf5528e6d490fc3bbe92d0c62bcffae6c0946b6. '
          'No clean worktree was substituted because it would omit inherited audited changes. No commit/reset/install made. '
          'Review source.patch against preimages in .jarvis-runtime/jarvis-audit/module24-pre; restore only matched scoped hunks '
          'after verifying source-hashes.json. New files are enumerated in files-changed.json. Preserve later/user edits. '
          'Keep uncertain WhatsApp journals intact; suspend sending during rollback since earlier code cannot enforce this new guard. '
          'Do not clear pending checkpoints or replay actions to test rollback. Human inspection of the actual chat is required. '
          'Re-run focused fixtures and launcher --check after any rollback. No live GUI rollback trial performed.')
    metrics = f"Normalization batch1000 warm p50/p95 {bench['before']['p50_ms']:.5f}/{bench['before']['p95_ms']:.5f} → {bench['after']['p50_ms']:.5f}/{bench['after']['p95_ms']:.5f}ms; Python peak {bench['before']['peak_python_bytes']}→{bench['after']['peak_python_bytes']}B, outputs identical."
    changes = '# Changes and keep/revert\n\n'+metrics+' Precompiled whitespace expression retained: small measured safe win. '
    changes += ('Five initial samples/version are not cold process trials. No TTFT/audio/RSS/VRAM or live send speed claim. '
                'Safety reads, locks and atomic checkpoints add work and may increase actual UI latency; no comparable end-to-end latency baseline. '
                'Fail-closed name collisions can refuse the same person listed under both Chats and Contacts. '
                'Uncertain checkpoint may precede any actual typing; conservative false blocks require inspection. '
                'Journal trusted local filesystem, no power-loss fsync/hostile-user sandbox guarantee, account/phone IDs absent. '
                'Final UI read and Enter are not an atomic transaction. File sends/call clicks are outside the new durable text guard.\n\n')
    command_lines = '''From app/, using .venv/Scripts/python.exe:
- `-m pytest tests/test_whatsapp.py -q --junitxml=artifacts/jarvis-audit/modules/24-whatsapp/baseline.xml`
- `-m pytest tests/test_whatsapp_audit.py -q --junitxml=artifacts/jarvis-audit/modules/24-whatsapp/reproduction.xml`
- `-m pytest tests/test_whatsapp.py tests/test_whatsapp_audit.py tests/test_gmail_writes.py tests/test_documents.py tests/test_task_recovery.py tests/test_audit_result_accounting.py -q --junitxml=artifacts/jarvis-audit/modules/24-whatsapp/neighbors-final.xml`
- `-m pytest tests/test_whatsapp.py tests/test_whatsapp_audit.py tests/test_audit_result_accounting.py -q --junitxml=artifacts/jarvis-audit/modules/24-whatsapp/cases-and-contracts.xml` (main preserved in focused-final.xml)
- `-m pytest scripts/verification/test_whatsapp_audit.py -q --junitxml=artifacts/jarvis-audit/modules/24-whatsapp/catalog-supplements.xml`
- `scripts/verification/verify_whatsapp_audit.py`; then `scripts/verification/verify_whatsapp_audit.py --freeze`
- `-m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/24-whatsapp/full-regression.xml` (full-regression.log)
- `-m jarvis.launcher --check` (readiness.json)
- `scripts/verification/report_whatsapp_audit.py`; `scripts/verification/verify_whatsapp_artifacts.py`
Journal/browser/loopback/owned-child fixtures required outside-sandbox execution after WinError5 in isolated temporary files. No live account or personal-window permissions were used.
'''
    write('commands.md', command_lines)
    short = (f'**WhatsApp audit — 2026-10-16 IST:** Fresh recipient/draft checks, expiring serialized approval, bounded request parsing and durable text-send non-replay checkpoints added. '
             f'**14 Prompt24 fixture PASS /18 BLOCKED**; full regression **{full["PASS"]:,} PASS /{full["SKIPPED"]} skips /0 failures**, launcher **ready**. '
             'No live WhatsApp action. Stable contact IDs, groups, outgoing calls, attachments and complete privacy/resource contracts remain incomplete.')
    marker(BASE/'README.md', short+'\n[Evidence and rollback](artifacts/jarvis-audit/modules/24-whatsapp/inventory.md).')
    marker(BASE.parent/'README.md', short+'\n[Evidence and rollback](app/artifacts/jarvis-audit/modules/24-whatsapp/inventory.md).')
    marker(BASE/'docs/system-map.md', short+'\n[Evidence and rollback](../artifacts/jarvis-audit/modules/24-whatsapp/inventory.md).')
    marker(BASE/'docs/whatsapp.md', short+'\n[Evidence and rollback](../artifacts/jarvis-audit/modules/24-whatsapp/inventory.md).\n\n'
           'Current behavior supersedes historical matching/send statements below: repeated display names refuse automatic selection; '
           'phonetic discovery never authorizes a different literal chat name. Texts are bounded to2000 characters, recipient queries to200, '
           'command JSON to8192. Unreadable compose state stops; a mismatched partial draft remains for inspection. '
           'Sent/Delivered/Read UI status is required; Pending is uncertain. Text checkpoint files live under '
           '`.jarvis-runtime/whatsapp/writes/` with hashed recipient/text and pending state, no plaintext. '
           'An uncertain identical text cannot be sent again automatically; no automatic journal reset. '
           'Successful explicit new approvals may repeat text. This guard covers text sends/replies, not file attachments or call clicks. '
           'Private text is still visible in local cards/transcripts; complete redaction is unproved. Historical images/results keep their original dates.')
    pairs=[]; patches=[]; changed=[]
    for old in sorted(PRE.iterdir()):
        if not old.is_file(): continue
        rel = '../README.md' if old.name=='root-README.md' else old.name.replace('__', '/')
        now = BASE/rel
        pairs.append(dict(path=rel, before=sha(old), after=sha(now)))
        patches.extend(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True), now.read_text(encoding='utf-8').splitlines(True),
                                          fromfile='before/'+rel, tofile='after/'+rel))
        changed.append(rel)
    new = ['jarvis/whatsapp_writes.py', 'tests/test_whatsapp_audit.py', 'scripts/verification/test_whatsapp_audit.py',
           'scripts/verification/verify_whatsapp_audit.py', 'scripts/verification/report_whatsapp_audit.py', 'scripts/verification/verify_whatsapp_artifacts.py']
    for rel in new:
        assert (BASE/rel).is_file()
        patches.extend(difflib.unified_diff([], (BASE/rel).read_text(encoding='utf-8').splitlines(True), fromfile='/dev/null', tofile='after/'+rel))
    changed += new
    write('source.patch', ''.join(patches)); write('source-hashes.json', json.dumps(pairs, indent=2))
    write('files-changed.json', json.dumps([dict(path=p, sha256=sha(BASE/p)) for p in changed], indent=2))
    write('changes.md', changes+'\n'.join('- `'+p+'`' for p in changed)+
          '\n\nGenerated audit artifacts, including reconciled global ledgers and the preserved prior report, are enumerated in generated-files.json. Source.patch is relative to module24 preimages, not repository HEAD; it preserves inherited user changes.')
    write('full-regression-skip-reasons.json', json.dumps([dict(node=n.get('classname','')+'::'+n.get('name',''),
          reason=n.find('skipped').get('message','')) for n in ET.parse(MOD/'full-regression.xml').iter('testcase') if n.find('skipped') is not None], indent=2))
    (MOD/'module-results.json').write_text(json.dumps(dict(baseline=baseline, focused=target, full=full,
           catalog=Counter(r['status'] for r in cases), readiness=ready['status']), indent=2))
    modules_table = '| Module / evidence and historical metrics | Status | PASS | BLOCKED | NOT RUN |\n| --- | --- | ---: | ---: | ---: |\n'
    for module in modules:
        counts = Counter(r['status'] for r in catalog if int(r['id'][4:6])==module['number'])
        label = f"{module['number']:02} {module['module']}"
        relative = f"modules/{module['number']:02}-{module['module']}/inventory.md"
        if (OUT/relative).is_file(): label = f'[{label}]({relative})'
        modules_table += f"| {label} | {module['status']} | {counts['PASS']} | {counts['BLOCKED']} | {counts['NOT RUN']} |\n"
    report = f'''# Jarvis audit — Prompt24, 2026-10-16 IST

**PARTIAL. 14 WhatsApp catalog fixture PASS /18 BLOCKED. No production acceptance.**

Commit `9bf5528e6d490fc3bbe92d0c62bcffae6c0946b6`, dirty preserved branch `audit/12-tool-registry`, app/ canonical checkout. Python{env['python'].split()[0]}, {env['platform']}, RAM{env['ram_bytes']} bytes. Target RTX3050 Laptop4GB retained from prior census; no new GPU workload. Installed comtypes{env['packages']['comtypes']}. [Environment](modules/24-whatsapp/environment.json).

{scope}

## Source map and behavior

{matrix}

## Executed results

- Baseline: {baseline['PASS']} PASS, {baseline['FAIL']} FAIL, {baseline['seconds']:.3f}s.
- Focused main:77 PASS/17 explicit skips; independent supplement2 PASS/1 BLOCKED. Aggregated executed assertions:{target['PASS']} PASS/{target['SKIPPED']} explicit skips/{target['FAIL']} FAIL.
- Full tests directory:{full['PASS']} PASS/{full['SKIPPED']} skips/{full['FAIL']} FAIL in{full['seconds']:.3f}s; independent supplement is additional, not part of this full count. [Full output](modules/24-whatsapp/full-regression.log), [XML](modules/24-whatsapp/full-regression.xml), [skip reasons](modules/24-whatsapp/full-regression-skip-reasons.json).
- Launcher dependency/configuration readiness:{ready['status']}; optional Groq was not live checked. This is not WhatsApp GUI/account readiness.
- Frozen runtime/test files:{len(frozen)}, verified unchanged during full run. [Hashes](modules/24-whatsapp/full-start-source-hashes.json).
- {metrics} [Samples](modules/24-whatsapp/benchmarks.csv). Keep small normalization improvement; additional safety reads/checkpoints cost work. No full UI/RSS/VRAM/cold-process speed claim.

[Reproduction and fixes](modules/24-whatsapp/failures.md) · [Commands](modules/24-whatsapp/commands.md) · [Exact changed files](modules/24-whatsapp/files-changed.json) · [Diff](modules/24-whatsapp/source.patch) · [Upstream URLs/dates](modules/24-whatsapp/compatibility.md) · [Rollback](modules/24-whatsapp/rollback.md).

## Catalog accounting across all37 modules

Exactly1,184 unique IDs. **{json.dumps(summary['catalog_counts'])}**. Narrower tests never overwrite full-contract blockers. All17 main blockers and the supplementary long-title blocker are explicit executed skips; no case silently dropped. Historical modules retain their earlier evidence scope.

{modules_table}

Tier totals:
```json
{json.dumps(summary['by_tier'], indent=2)}
```

Category totals:
```json
{json.dumps(summary['by_category'], indent=2)}
```

## Remaining WhatsApp contracts and risk

{gates}

Text journal is a trusted local-process boundary, not hostile-filesystem or power-loss durability proof. No stable account/phone identity, no atomic UI compare-and-send, same-caller replacement can be ambiguous. File attachments and Telegram/calls do not share text journaling. Local transcript privacy remains incomplete. Do not clear pending records or replay uncertain sends to verify them.

## Resume

Next incomplete module24 case **JRV-24-001**; global oldest unresolved **{summary['next_case']}**, next untouched module **25/JRV-25-001**. Exact WhatsApp IDs: [remaining-case-ids.txt](modules/24-whatsapp/remaining-case-ids.txt); global [remaining IDs](remaining-case-ids.txt). Resume by reading module24 inventory, failures and source hashes; implement a scoped read-only conversation/identity fixture, then address the listed contracts. Re-run the focused and independent commands, freeze sources and repeat full/readiness before reconciling. A live read/send/call still needs separate explicit per-action authorization. [Preserved previous module23 report](final-report-before-module24.md) retains earlier per-module evidence/benchmarks and rollback.
'''
    (OUT/'final-report.md').write_text(report, encoding='utf-8')
    generated = {p.relative_to(BASE).as_posix() for p in MOD.iterdir() if p.is_file()}
    generated.update((OUT/n).relative_to(BASE).as_posix() for n in ('final-report.md', 'final-report-before-module24.md',
                     'module-map.json', 'test-results.jsonl', 'summary.json', 'executed-tests.jsonl', 'remaining-case-ids.txt'))
    generated.add((MOD/'generated-files.json').relative_to(BASE).as_posix())
    write('generated-files.json', json.dumps(sorted(generated), indent=2))
    print(json.dumps(dict(module24=Counter(r['status'] for r in cases), global_catalog=summary['catalog_counts'], full=full), indent=2))


if __name__=='__main__': main()
