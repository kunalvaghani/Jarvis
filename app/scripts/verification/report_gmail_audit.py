"""Publish Prompt23 executed fake-service evidence and explicit production blockers."""
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
OUT=BASE/'artifacts/jarvis-audit';MOD=OUT/'modules/23-gmail';PRE=BASE/'.jarvis-runtime/jarvis-audit/module23-pre'
BLOCKED={f'JRV-23-{n:03}' for n in (10,12,18,21,25,26,27,32)}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(n,s):(MOD/n).write_text(s.strip()+'\n',encoding='utf-8')
def stats(n):
    t=ET.parse(MOD/n);nodes=list(t.iter('testcase'))
    return {'PASS':sum(x.find('skipped') is None and x.find('failure') is None and x.find('error') is None for x in nodes),
      'FAIL':sum(x.find('failure') is not None or x.find('error') is not None for x in nodes),
      'SKIPPED':sum(x.find('skipped') is not None for x in nodes),'seconds':sum(float(x.get('time','0')) for x in t.iter('testsuite'))}

def main():
    from scripts.verification import audit_catalog
    combined=ET.Element('testsuites',name='Prompt23 executed main and supplemental suites')
    for n in ('focused-main-final.xml','catalog-supplements.xml'):combined.extend(list(ET.parse(MOD/n).getroot()))
    ET.ElementTree(combined).write(MOD/'cases-and-contracts.xml',encoding='utf-8',xml_declaration=True)
    baseline=stats('baseline.xml');target=stats('cases-and-contracts.xml');full=stats('full-regression.xml')
    assert baseline['FAIL']==target['FAIL']==full['FAIL']==0 and target['PASS']==68 and full['PASS']>2855
    frozen=read(MOD/'full-start-source-hashes.json');assert all(sha(BASE/p)==h for p,h in frozen.items())
    env=read(MOD/'environment.json');ready=read(MOD/'readiness.json');bench=read(MOD/'benchmark-summary.json')
    assert bench['equivalent'] and bench['real_mailbox_writes']==0
    modules=read(OUT/'module-map.json')
    modules[22].update(sources=['jarvis/gmail_api.py','jarvis/gmail_writes.py','jarvis/gmail_workflows.py','jarvis/file_drop.py',
      'jarvis/toolkits.py','jarvis/brain_worker.py','scripts/setup/connect_gmail_api.py','docs/gmail-api.md','docs/file-buddy.md'],
      test_candidates=['tests/test_gmail_audit.py','scripts/verification/test_gmail_audit.py','tests/test_gmail_api.py',
      'tests/test_gmail_actions.py','tests/test_gmail_commands.py','tests/test_gmail_writes.py','tests/test_gmail_workflows.py','tests/test_documents.py'],
      status='PARTIAL',reason='24 catalog fixture PASS/8 incomplete contracts BLOCKED; no live Gmail/profile/OAuth writes or account reads performed')
    (OUT/'module-map.json').write_text(json.dumps(modules,indent=2)+'\n');audit_catalog.reconcile()
    catalog=[json.loads(s) for s in (OUT/'test-results.jsonl').read_text(encoding='utf-8').splitlines()]
    cases=[r for r in catalog if r['id'].startswith('JRV-23-')]
    assert len(cases)==32 and Counter(r['status'] for r in cases)=={'PASS':24,'BLOCKED':8}
    assert {r['id'] for r in cases if r['status']=='BLOCKED'}==BLOCKED
    write('tests.jsonl','\n'.join(json.dumps(r,ensure_ascii=False) for r in cases));summary=read(OUT/'summary.json')
    nodes=list(ET.parse(MOD/'full-regression.xml').iter('testcase'))
    write('full-regression-skip-reasons.json',json.dumps([{'node':n.get('classname','')+'::'+n.get('name',''),
      'reason':n.find('skipped').get('message','')} for n in nodes if n.find('skipped') is not None],indent=2))
    gates='''- **JRV-23-010 BLOCKED:** One OAuth-selected account per base; no explicit multi-account identity broker or account-bound approval/journal. Separate fake clients are not complete account-switch isolation proof.
- **JRV-23-012 BLOCKED:** File attachments stay remote on reads, and attachment draft approval/journaling now have fixtures; a complete attachment secret-to-model oracle and attachment/body upload readback are absent.
- **JRV-23-018 BLOCKED:** Before-write cancellation and Stop during fresh observation are covered; complete TaskState cancellation semantics during readback are unproved.
- **JRV-23-021 BLOCKED:** Local interpreter context is bounded; no complete fake-cloud/private-context/log-redaction oracle across all mail and attachment flows.
- **JRV-23-025 BLOCKED:** No complete Gmail RAM/GPU-pressure admission and core-command responsiveness proof. Ordinary adapter operations use no GPU; composition does.
- **JRV-23-026 BLOCKED:** Uncertain outcomes refuse replay; successfully completed identical events have no durable event-ID deduplication contract. A new explicit approved request can repeat identical mail.
- **JRV-23-027 BLOCKED:** Draft-update CPU A/B is measured; complete OAuth/workflow cold-start/RSS/VRAM benchmark absent.
- **JRV-23-032 BLOCKED:** Journals omit body/subject and transport errors are categorical; complete private-data redaction and cross-flow correlation remain unproved.'''
    scope='''Owned in-memory Gmail mailboxes and fake OAuth/HTTP, isolated DPAPI-token placeholders, actual durable journal locks/checkpoints, an owned child exiting23 after its write-intent checkpoint, five independent fake-mailbox writes ×20 rounds, and existing headless Gmail-like DOM/document fixtures. No live mailbox/profile read, real draft/send/Trash/label/delete, token decryption, consent/refresh request, credential setup, account verification, service restart, install or model/GPU trial. The Chrome DOM fixture intercepts mail.google.com with authored local HTML; it is not live Gmail. The independently executed supplement adds exact-recipient drafts, insufficient-scope refusal and inert hidden HTML; it is outside the full tests-directory command and included in changed-file hashes.'''
    matrix='''| Claim | Real source / entry point | Executed proof / boundary |
| --- | --- | --- |
| Discovery / routing | toolkits optional catalogue→gmail_api.execute; Brain→gmail_workflows | Actual source-bound configured() gate; exact commands use API before desktop planning; no SMTP/Chrome fallback change |
| OAuth / scopes | connect_gmail_api manual flow, credentials / API | Existing readonly+compose+modify combined grant, no full mail.google.com scope; fake insufficient scope blocks refresh; fake refresh timeout20; one account per base, not per-operation downscoping |
| Account / transport | DPAPI per Windows user; API session Authorization, users/me, trust_envFalse, redirects disabled | Injected isolated sessions only; no token/private file read. No live identity binding; missing dependencies produce local Connect action |
| Search / summaries | run list→message_summary exact IDs and selected metadata | Mock unread/contact filtering and latest3 sender/subject/date grounding; GET-only, raced unread flags; no semantic body-summary quality claim |
| Pagination / rate limits | bounded list limits10 drafts/25 mail; next_page_available flag; API.call deadlines/2MB | No follow-page-token interface or exhaustive mailbox scan. HTTP429/timeout pauses without automatic replay; no new read retry/backoff cache |
| Read / untrusted mail | full MIME→bounded walk / MailText; content_is_untrusted | Named file attachments skipped; external ordinary text part supported. Script/style inert; hidden text can remain untrusted, not a sanitizer or universal prompt-injection oracle |
| Draft/send approvals | run→approved callback→before_write→single write→readback | Explicit False refuses; field changes during callback require new review; sent status/subject readback, exact recipients; no inferred name-to-address guesses |
| Draft freshness | pre-observe hash; fresh_draft after approval; cancellation check | Changed send/delete/update refused before write; direct send field mutation denied. Google offers no transactional compare-and-set; residual final-read/write race remains |
| Durable journal | execute guard→begin/accepted/complete; TaskState checkpoints | Pending survives child crash/new caller; malformed/type/oversize state fails closed; lock prevents concurrent same request. Successful-event dedupe and account identity binding remain absent |
| Attachments / FileBuddy | file_drop.send_email approval→draft_with_attachments guard | FileBuddy retains5-file drop admission; helper cap25, local raw budget24MiB, stat then bounded read; stable per-part hashes avoid random-MIME-boundary retry bypass; fake denial/success/lost-readback proof |
| Attachment upload limit | helper media upload path and metadata readback | Response now closes; only draft ID/subject verified, not complete uploaded file/body content. No new upload-size/provider-cap guarantee or hardened filesystem sandbox |
| Observability | hashed request file, operation/target/actual IDs, categorical transport diagnostics | No subject/body in journals; existing local transcripts may contain requested mail text. Not signed consent or power-loss/fsync proof |'''
    b=bench['before']['warm'];a=bench['after']['warm']
    measured=f"Same HTML-draft update CPU warm p50/p95 **{b['p50_ms']:.4f}/{b['p95_ms']:.4f} → {a['p50_ms']:.4f}/{a['p95_ms']:.4f} ms**, traced peak **{b['python_peak_bytes']} → {a['python_peak_bytes']} bytes**;50 calls, byte-identical MIME and result, one fake PUT/sample, zero real mailbox writes. Initial5 calls are not fresh-process cold starts. OAuth/network/browser/RSS/VRAM excluded. Reusing parsed draft info avoids a second decode; the new freshness guard adds one real GET after approval, so remote end-to-end latency may increase."
    write('inventory.md',f'''# Prompt23 Gmail audit — 2026-10-16 IST

**24 catalog PASS /8 BLOCKED /0 FAIL /0 SKIPPED /0 NOT RUN.** [32 exact IDs](tests.jsonl). Baseline {baseline}; combined focused {target}; full tests-directory {full}. Main65 PASS/8 skips plus separately executed3 PASS, aggregated without changing original suite outcomes. [Commands](commands.txt), [full XML](full-regression.xml), [all skips](full-regression-skip-reasons.json).

{scope}

{matrix}

{gates}

Actual checked-out system-map and linked Gmail/native/file-buddy documentation were read as dated claims, then checked against registrations, code, scope declarations and existing tests. Retained inherited dirty branch **{env['branch']}**, HEAD **{env['commit']}**; a fresh clean checkout would omit user/module21–22 work. No reset/commit. Run order: source/approval/recovery trace→baseline→reproduction→small guards→official upstream→equivalent benchmark→neighbors/faults→frozen full/readiness→catalog/docs. [Environment](environment.json), [changes](changes.md), [compatibility](compatibility.md), [rollback](rollback.md).

{measured} [Raw samples](benchmarks.csv), [scope](benchmark-summary.json).

Adapter changes intentionally invalidate the existing source-bound Gmail verification marker. It was not rewritten, credentials were not read, and no --verify-existing or OAuth setup ran. Review these diffs before separately authorizing the guide's local verification step. Historical live2026-10-09/10 results retain their dates; this audit provides no new live Gmail/voice acceptance. Existing artwork/screenshots preserved; no UI layout changed or new live-account screenshot taken.
''')
    write('failures.md',f'''# Reproductions and remaining risk

Baseline66 PASS in10.74s. Initial harness collection referred to the wrong existing test class; corrected to GmailWorkflowTests before product reproduction. Reproduction11 FAIL/19 PASS/8 explicit blockers in4.69s. Failed assertions overlap: draft send/delete/update changed during approval; explicit False consent ignored; malformed connection marker; damaged/missing/type-invalid journal state. Eleven failed assertions are not eleven distinct vulnerabilities.

First neighbor run113 PASS/8 skips in18.17s. Added approval field binding, post-observation cancellation, optional-dependency handling and attachment bounds: second137 PASS/8 skips in12.10s. Attachment-flow expansion third138 PASS/4 FAIL/8 skips in11.67s: all four failures were missing Mock import in the updated owned document fixture; fixed import, retaining existing assertions and adding actual denial/pending/verified attachment tests. Fourth143 PASS/8 skips in11.38s. Final main65 PASS/8 skips in3.72s, supplement3 PASS in0.74s; final combined {target}. Full {full}; all{len(frozen)} frozen runtime/test hashes unchanged.

{gates}

Other limits: draft freshness is read-then-write, not atomic Google CAS. Mutable args changed and restored entirely inside a trusted callback are not a signed user-event ledger. DPAPI and local journal files are trusted local state, not malicious-host confinement. Journal replacements are atomic per file, not fsync/power-loss transactions or atomic with TaskState. Corrupted journals now require inspection, not deletion/retry. Attachment helper is an internal trusted API; the public FileBuddy caller owns human approval. Its card reviews recipient/body/filenames, not a cryptographically bound file-content approval; selected files can change during approval, and the later part hash binds the journal to bytes read rather than to a signed human event. Large media uploads still have a120s deadline and use a separate response path; complete response/resource/provider attachment validation needs more work. Named files are never fetched by read, but normal external textual MIME parts can be read. Labels/Trash use Google's returned state; this is not a second independent GET after every label response. Private local transcript rendering and complete semantic prompt injection remain unproved.

Launcher **{ready['status']}**, missing **{ready['missing']}**. Source-bound Gmail remains withheld pending separately reviewed verification; no automatic activation or live profile check. No production-ready certificate.
''')
    write('changes.md',f'''# Retained changes / tradeoffs

- gmail_api.py: explicit False consent refused; argument snapshots bind approval, draft send/delete/update re-observe after approval and Stop is rechecked. Parsed draft info reused once. Bounded parameters parse before OAuth/session creation; malformed marker/search rows fail safely; missing OAuth deps give local guidance.
- gmail_writes.py: bounded64KiB journal read, exact operation/target/boolean-state checks; damaged state categorically refuses execution and preserves data. Existing request identity remains compatible.
- file_drop.py and attachment helper: existing standard approval card before draft; durable per-part identity journal prevents uncertain retry bypass from random MIME boundaries; bounded preflight reads and response cleanup. Selected file/recipient/body behavior retained; no automatic sends.
- New fake-service/security/concurrency/crash tests, explicit accounting, original-preimage benchmark and report/hash scripts. Document fixture now supplies an explicit fake approval. README, Gmail/FileBuddy guide and source-map updated; no dependency/configuration changes or UI redesign.

{measured}

Keep safety checks and measured CPU/allocation improvement. No private metadata cache, TTL guess, automatic send retry, dependency install or whole-workflow speed claim. [Exact files](files-changed.json), [hash pairs](source-hashes.json), [scoped diff](source.patch).
''')
    write('compatibility.md',f'''# Compatibility — checked2026-10-16 IST

Official sources inspected with Firecrawl; [URLs/dates/status](upstream-checks.json). [Google scopes](https://developers.google.com/workspace/gmail/api/auth/scopes) describes the combined capabilities; the app retains readonly/compose/modify, not full permanent-mail-delete scope or per-operation OAuth profiles. [Error guidance](https://developers.google.com/workspace/gmail/api/guides/handle-errors) recommends appropriate backoff; Gmail also cautions that HTTP200 does not mean delivery. Jarvis retains SENT/subject readback and no unknown-outcome resend. No new429 automatic retry.

[Messages.list](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list) documents pageToken/nextPageToken; this adapter only reports that more pages exist, not full traversal. [Draft creation](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.drafts/create) documents media endpoint/scopes (page updated2026-04-15); API version is v1, not a package release. Draft readback does not prove every uploaded attachment or eventual delivery.

Installed google-auth2.61.0, google-auth-oauthlib1.5.0, Requests2.34.2 on Python3.10.6. [google-auth PyPI](https://pypi.org/project/google-auth/) lists2.62.0 released2026-10-12; [oauthlib bridge](https://pypi.org/project/google-auth-oauthlib/) lists1.5.0 released2026-09-29. Existing requirements major ranges accommodate these installed versions. No upgrades installed or2.62 compatibility claim made. The attempted2.62 GitHub release URL returned404, while [fetched main changelog](https://raw.githubusercontent.com/googleapis/google-auth-library-python/main/CHANGELOG.md) led with2.48.0 dated2026-01-22. Current2.62 release-note coverage is therefore incomplete; registry dates and stale/missing notes are recorded separately, not invented.

Prior [module22 compatibility](../22-web-development/compatibility.md) records Python/Git/platform limits; none is resolved here. No new paid API or model requirement. Launcher {ready['status']} is dependency/configuration readiness, not live Gmail acceptance. Source-bound verification intentionally becomes stale after adapter edits; no token, consent or verification marker modified.
''')
    write('rollback.md','''# Scoped rollback / resume

Preserve inherited user/module21–22 work; no audit commit/reset. Compare current hashes/source.patch before restoring only this module from ignored .jarvis-runtime/jarvis-audit/module23-pre. Names replace / with __; root-README.md is the parent overview. Do not erase the checkout, token, mailbox, pending journal or later user edits.

Do not downgrade a live uncertain journal without inspection: older code can mishandle damaged markers and stale approval. Retain journal/actual IDs, inspect the mailbox under separately approved live access, then start a new reviewed request. Never remove pending files merely to retry. Source-bound Gmail remains unavailable until reviewed adapter verification; rollback does not automatically reauthorize/reverify it. No real mailbox/token/credential changes need rollback from this audit.

From app/ with existing .venv/Scripts/python.exe:
1. scripts/verification/verify_gmail_audit.py (immutable original preimage A/B).
2. -m pytest tests/test_gmail_audit.py tests/test_audit_result_accounting.py -q --junitxml=artifacts/jarvis-audit/modules/23-gmail/focused-main-final.xml
3. -m pytest scripts/verification/test_gmail_audit.py -q --junitxml=artifacts/jarvis-audit/modules/23-gmail/catalog-supplements.xml
4. Neighbors: test_gmail_api.py, test_gmail_actions.py, test_gmail_writes.py, test_gmail_workflows.py, test_gmail_commands.py, test_gmail_drafts.py, test_documents.py. Fakes/owned DOM only, never run the historical *_live.py scripts for this audit.
5. Freeze jarvis/*.py and tests/test_*.py SHA256 then -m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/23-gmail/full-regression.xml. No runtime/test edits during accepted run.
6. -m jarvis.launcher --check read-only; publish redacted summary only. Run report_gmail_audit.py, verify_gmail_artifacts.py and git diff --check.

Current BLOCKED JRV-23-010/012/018/021/025/026/027/032. Next NOT RUN JRV-24-001; earliest older unresolved JRV-04-001. Exact remaining IDs in artifacts/jarvis-audit/remaining-case-ids.txt. Live OAuth/profile/account writes and source activation require separate explicit action approval; do not infer it from passing fixtures.
''')
    headline=f"**Gmail audit — 2026-10-16 IST:** Approval now refuses False/changed fields, draft writes recheck freshness after approval, and damaged journals fail closed. FileBuddy attachment drafts now require approval and durable non-replay records. **24 Prompt23 fixture PASS /8 BLOCKED**; full regression **{full['PASS']:,} PASS /{full['SKIPPED']} skips /0 failures**, launcher **{ready['status']}**. No live Gmail trial. Adapter source verification is stale until separately reviewed; account isolation, complete privacy/resource/replay/observability contracts remain incomplete."
    for doc,link in [(BASE/'README.md','artifacts/jarvis-audit/modules/23-gmail/inventory.md'),(BASE.parent/'README.md','app/artifacts/jarvis-audit/modules/23-gmail/inventory.md'),
      (BASE/'docs/system-map.md','../artifacts/jarvis-audit/modules/23-gmail/inventory.md'),(BASE/'docs/gmail-api.md','../artifacts/jarvis-audit/modules/23-gmail/inventory.md'),(BASE/'docs/file-buddy.md','../artifacts/jarvis-audit/modules/23-gmail/inventory.md')]:
        text=doc.read_text(encoding='utf-8');first,rest=text.split('\n',1);rest=re.sub(r'<!-- prompt23-audit -->.*?<!-- /prompt23-audit -->\s*','',rest,flags=re.S)
        doc.write_text(first+'\n\n<!-- prompt23-audit -->\n'+headline+'\n[Evidence and rollback]('+link+').\n<!-- /prompt23-audit -->\n\n'+rest.lstrip('\n'),encoding='utf-8')
    table='\n'.join('| '+str(m['number']).zfill(2)+' '+m['module']+' | '+', '.join(f'{k}: {v}' for k,v in Counter(r['status'] for r in catalog if r['id'].startswith(f"JRV-{m['number']:02}-")).items())+' |' for m in modules)
    (OUT/'final-report.md').write_text(f'''# Jarvis audit — Prompt23 — 2026-10-16 IST

{headline}

HEAD **{env['commit']}**, branch **{env['branch']}**, inherited diffs preserved. [Environment](modules/23-gmail/environment.json). Baseline {baseline}; combined focused {target}; full tests-directory {full}. Full command excludes the separately executed3-test supplement. All **{len(frozen)} frozen runtime/test hashes unchanged**. [Full XML](modules/23-gmail/full-regression.xml), [skips](modules/23-gmail/full-regression-skip-reasons.json), [readiness](modules/23-gmail/readiness.json).

{scope}

{measured}

[Source-map matrix](modules/23-gmail/inventory.md), [changes/metrics](modules/23-gmail/changes.md), [exact files](modules/23-gmail/files-changed.json), [diff](modules/23-gmail/source.patch), [official URLs/dates](modules/23-gmail/compatibility.md), [risks/flaws](modules/23-gmail/failures.md), [rollback/resume](modules/23-gmail/rollback.md), [commands/results](modules/23-gmail/commands.txt).

{gates}

All1,184 IDs: **{summary['catalog_counts']}**. [Ledger](test-results.jsonl), [category/tier statistics](summary.json), [remaining IDs](remaining-case-ids.txt). Next NOT RUN **JRV-24-001**; earliest unresolved **JRV-04-001**. [Previous Prompt22 report](final-report-before-module23.md). No production-ready certificate; overall37-module audit remains incomplete.

## Enumerated modules

| Module | Catalog status |
| --- | --- |
{table}

## Category and tier statistics

```json
{json.dumps({k:summary[k] for k in ('by_category','by_tier')},indent=2)}
```
''',encoding='utf-8')
    files=['jarvis/gmail_api.py','jarvis/gmail_writes.py','jarvis/file_drop.py','tests/test_gmail_audit.py','tests/test_documents.py',
      'scripts/verification/audit_catalog.py','tests/test_audit_result_accounting.py','scripts/verification/verify_gmail_audit.py',
      'scripts/verification/report_gmail_audit.py','scripts/verification/verify_gmail_artifacts.py','scripts/verification/test_gmail_audit.py',
      'README.md','docs/gmail-api.md','docs/file-buddy.md','docs/system-map.md','../README.md']
    changed=[];pairs=[];patch=[]
    for n in files:
        p=BASE/n;old=PRE/('root-README.md' if n=='../README.md' else n.replace('/','__'));changed.append({'path':n,'sha256':sha(p)})
        if old.exists():pairs.append({'path':n,'before':sha(old),'after':sha(p)})
        patch.extend(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True) if old.exists() else [],p.read_text(encoding='utf-8-sig').splitlines(True),fromfile='before/'+n if old.exists() else '/dev/null',tofile='after/'+n))
    write('files-changed.json',json.dumps(changed,indent=2));write('source-hashes.json',json.dumps(pairs,indent=2));write('source.patch',''.join(patch))
    generated=['artifacts/jarvis-audit/'+s for s in ('final-report.md','final-report-before-module23.md','module-map.json','summary.json','test-results.jsonl','executed-tests.jsonl','remaining-case-ids.txt')]
    generated.extend(p.relative_to(BASE).as_posix() for p in MOD.iterdir() if p.is_file());generated.extend('artifacts/jarvis-audit/modules/23-gmail/'+s for s in ('generated-files.json','artifact-verification.json'))
    write('generated-files.json',json.dumps(sorted(set(generated)),indent=2))
    print(json.dumps({'module23':dict(Counter(r['status'] for r in cases)),'full':full,'catalog':summary['catalog_counts']},indent=2))

if __name__=='__main__':main()
