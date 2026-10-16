"""Publish Prompt 19 executed assertions; keep historical runs and live gates separate."""
from collections import Counter
import difflib
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
OUT=BASE/'artifacts/jarvis-audit';MOD=OUT/'modules/19-ability-forge'
PRE=BASE/'.jarvis-runtime/jarvis-audit/module19-pre'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(name):return json.loads((MOD/name).read_text())
def write(name,text):(MOD/name).write_text(text.strip()+'\n',encoding='utf-8')
def stats(name):
    tree=ET.parse(MOD/name);nodes=list(tree.iter('testcase'))
    return {'PASS':sum(n.find('skipped') is None and n.find('failure') is None and n.find('error') is None for n in nodes),
            'FAIL':sum(n.find('failure') is not None or n.find('error') is not None for n in nodes),
            'SKIPPED':sum(n.find('skipped') is not None for n in nodes),
            'seconds':sum(float(n.get('time','0')) for n in tree.iter('testsuite'))}


def main():
    from scripts.verification import audit_catalog
    baseline=stats('baseline.xml');target=stats('cases-and-contracts.xml');full=stats('full-regression.xml')
    assert full['PASS']>2700 and baseline['FAIL']==target['FAIL']==full['FAIL']==0
    frozen=load('full-start-source-hashes.json');assert all(sha(BASE/p)==h for p,h in frozen.items())
    env=load('environment.json');bench=load('benchmark-summary.json');ready=load('readiness.json')
    assert bench['equivalent'] and bench['external_effects']==0
    modules=json.loads((OUT/'module-map.json').read_text())
    modules[18].update(sources=['jarvis/repo_abilities.py','jarvis/ability_runner.py','jarvis/repo_learning.py',
        'jarvis/repository_skills.py','jarvis/repo_sandbox.py','jarvis/commands.py','jarvis/capabilities.py',
        'jarvis/actions.py','jarvis/repo_tools.py','docs/repo-abilities.md','docs/repository-skills.md'],
        test_candidates=['tests/test_ability_forge_audit.py','tests/test_repo_abilities.py','tests/test_repository_skills.py',
                         'tests/test_repository_skill_isolation.py','tests/test_capabilities.py','tests/test_toolkits.py'],
        status='FIXTURE VERIFIED; LIVE/HARDENING GATES OPEN',reason='32 dedicated catalog fixtures executed; no arbitrary downloaded-code/real-account/GUI/model acceptance')
    (OUT/'module-map.json').write_text(json.dumps(modules,indent=2)+'\n')
    audit_catalog.reconcile()
    catalog=[json.loads(s) for s in (OUT/'test-results.jsonl').read_text(encoding='utf-8').splitlines()]
    cases=[r for r in catalog if r['id'].startswith('JRV-19-')]
    assert len(cases)==32 and all(r['status']=='PASS' for r in cases)
    write('tests.jsonl','\n'.join(json.dumps(r,ensure_ascii=False) for r in cases))
    summary=json.loads((OUT/'summary.json').read_text());counts=summary['catalog_counts']
    nodes=list(ET.parse(MOD/'full-regression.xml').iter('testcase'))
    isolation=[n for n in nodes if 'test_repository_skill_isolation' in n.get('classname','')]
    iso_pass=sum(n.find('skipped') is None and n.find('failure') is None and n.find('error') is None for n in isolation)
    iso_skip=sum(n.find('skipped') is not None for n in isolation)
    skips=[{'node':n.get('classname','')+'::'+n.get('name',''),'reason':n.find('skipped').get('message','')} for n in nodes if n.find('skipped') is not None]
    write('full-regression-skip-reasons.json',json.dumps(skips,indent=2))
    before=bench['before']['warm'];after=bench['after']['warm']
    measured=f"Oversized-source rejection warm p50/p95 **{before['p50_ms']:.4f}/{before['p95_ms']:.4f} → {after['p50_ms']:.4f}/{after['p95_ms']:.4f} ms**, identical rejection on a400KB comment plus valid owned utility. Peak traced allocation **{before['python_peak_bytes']}→{after['python_peak_bytes']}B**. This measures the input guard, not ordinary build, model or speech latency."
    scope=f"Owned temporary proposals/registries/files, scripted model and permission callbacks, fake installer/transport faults; no real account data or dependency installation. The legacy regression uses a stdlib-only venv and hand-written utility. Command routing→approved owned fixture→real guarded child→file readback→disable/enable journey passed. An owned child exited27 after a durable external-write checkpoint; reload refused dispatch. Actual existing Docker kernel fixtures: **{iso_pass} PASS /{iso_skip} skipped**. No downloaded repository code, real ability installation, live account send, microphone/GUI, native30B/9B inference or GPU stress acceptance."
    matrix="""| Claim | Real entry point and evidence | Boundary |
| --- | --- | --- |
| New voice abilities | repo_learning.on_learned → AbilityForge.enqueue/run/build_repo → design/generate/static check → approval → test/promotion | actions constructs forge; active config enabled/auto_build true,30B preferred/9B fallback; model proposals are not built-in tools |
| Typed contracts | clean_spec inputs(text/file/url/number), output(text/file/both), package/network/approach validation; ability_runner result validation | output text is string, files list≤20; scalar string return remains compatible; no semantic quality oracle |
| Precedence | commands.parse immutable reflex and deterministic handlers → learned parse fallback; usable_triggers suppresses conflicts | built-in open preserved by executed command assertions, no built-in mutation |
| Review binding | strict boolean island result; deep copy for callback; code/scope SHA256 before/after callback; voice queue captures digest | queued scope changes fail closed; trusted direct install_approved API represents explicit caller approval, not an untrusted tool-result receipt |
| Test/promotion | version folders/code hash/registry replace, no post-consent model repairs; cancelled/stale tests cannot promote | pre-review stdlib test still runs with process audit hooks; packages/repo_code require consent first |
| Output rollback | failed output contract withdraws new version; prior approved hash-verified metadata restored | one previous version only; no execution/replay during rollback; missing/tampered previous code remains failed |
| External actions | fresh Actions._approve for each network invocation; durable uncertain_external_write before dispatch | all network calls conservatively treated as writes; crash/lost reply blocks later dispatch until external state is inspected and ability rebuilt/reviewed; no claim to prove arbitrary network semantics |
| Isolation | ability_runner uses isolated Python process/audit hooks, memory/time checks; separate RepositorySkills uses Docker | voice forge does not use Docker. Audit hooks are not a hostile-code sandbox; native code remains a hardening gate |
| Docker skills | static learn→ANALYZED→approved check→VALIDATED→approved activation→ACTIVE; per-call approval | fake failed Docker validation quarantines/no promotion; existing owned kernel tests separate from forge |
| Concurrency | shared owned process serialized, UUID work folders, lock-protected registry/log writes |5 concurrent requests×20 rounds,100 distinct work folders and100 runs; serialization intentionally sacrifices parallel ability throughput |
| Provenance | source repo/license/commit/version/codehash retained in registry; repo_code downloads immutable SHA with40MB/20k entries/64MB extraction bounds | legacy unpinned repo_code fetch refused; codehash is integrity, not authenticity/signature or a license compatibility certificate |
| Recovery/observability | registry persists version/approval/write checkpoint; JSONL events have forge-instance trace UUID and recognized credential redaction | process crash tested, not power-loss/fsync or multi-process transaction; correlation is per forge instance, not distributed tracing |
| Resources/privacy | pick_model checks available RAM and installed sizes; research queue yields to user; local HTTP client ignores environment proxy | fake outages/timeouts/RAM/GPU faults; actual knowledge_worker transport receives fake private payload only at127.0.0.1; no live cloud entitlement test |
| Lifecycle | compatible launchers, stable commands, disabled/forgotten files retained | no user file deletion, app restart, migration, runtime installation or publishing |
"""
    write('inventory.md',f"""# Prompt19 ability forge audit — 2026-10-16 IST

**32 catalog PASS /0 FAIL /0 BLOCKED /0 SKIPPED /0 NOT RUN**, fixture scope only. Baseline **{baseline}**; final focused **{target}**; full **{full}**. [All32 IDs and assertions](tests.jsonl), [commands](commands.txt), [focused XML](cases-and-contracts.xml), [full XML](full-regression.xml), [exact full skips](full-regression-skip-reasons.json).

{scope}

{matrix}

Read actual system-map and existing repo-abilities/repository-skills/repo-learning guides and source/config bindings. Architecture counts/configuration are claims, not live service proof. Existing dirty branch **{env['branch']}**, HEAD **{env['commit']}**, retained because a clean checkout would omit user/module14–18 work. Before-source snapshots preserved in ignored runtime storage. Order: contracts/approval→baseline→failure assertions→narrow fixes→official upstream→A/B→neighbors/journey→frozen full regression/readiness→ledger/report. No reset/commit/install/service start.

{measured} [50 samples](benchmarks.csv), [environment](environment.json), [changes](changes.md), [compatibility/live gates](compatibility.md), [rollback](rollback.md).
""")
    write('failures.md',f"""# Reproductions, fixes and remaining gates

Baseline:57 PASS in48.77s including owned Docker fixtures. First new sandboxed run:28 FAIL/3 PASS, mostly sandbox replacement restrictions; retained reproduced.xml, not product defect proof. Authorized reproduction:18 FAIL/13 PASS in3.01s. One failure was a fixture leading-newline mismatch; fixed canonical code comparison. Stale-approval assertion initially failed for the wrong reason (missing fake environment); it now provisions only an interpreter existence marker and proves no validation/installation call after mutation.

Product failures reproduced: truthy nonboolean scope/approval, missing fresh network approval, wrong output types, colliding second-resolution run folders/shared child ownership, cancellation/stale source, parser invoked after size rejection, malformed proposal exceptions, and unreviewed repair after consent. Repeated parametrizations overlap; not18 distinct defect claims. First focused59 PASS. Later run:1 FAIL/39 PASS/2 skips because cancellation fixture consumed its only scripted model response on a second build; reused its pending proposal. Mistyped tests/test_commands.py caused one collection-only failure, retained targeted-third.xml, no assertions/PASS credit.

Intermediate175 PASS/1 skip preceded rollback coverage. Final focused {target}; full {full}; runtime/test source freeze unchanged. Runtime output-contract failures now carry a categorical failure_kind; both actual child classification and host rollback are asserted. New ability fails closed; an update restores only a prior approved hash-verified version. Network uncertainty survives rollback. No automatic replay.

The first artifact check found broken relative links in the relocated historical Prompt18 report copy. Moved that unchanged archive back to the audit root, where its original links resolve, and regenerated the report/hash manifest. Final artifact checks verify403 current README/report links,12 file hashes and8 preimage pairs. Runtime/test sources were unchanged; documentation bookkeeping did not require another full suite.

Open production gates: the voice forge's Python audit hooks are bypassable and do not isolate hostile packages/native code; it is separate from the hardened Docker skill engine. Wheel-only installation is not a supply-chain authenticity guarantee; package versions/transitive artifacts are not consent-hash pinned. Fresh network approval is generic, not a domain/recipient capability sandbox. Some scalar malformed enum shapes can still raise a caught TypeError rather than AbilityError. Registry writes are atomic replacements within one process, without fsync/power-loss or multi-process CAS guarantees. Older/tampered registry structure is not a cryptographically signed approval receipt. Trace IDs correlate one forge instance; no distributed tracing certificate. Legacy source_commit may be absent; repo_code then refuses fetch until relearned. ZIP central directory parsing precedes the entry budget. Output typing does not prove useful/correct semantics.

Readiness **{ready['status']}**: {ready['missing']}. Python3.10 has reached upstream end-of-life; migration is separate required maintenance, not performed by this test pass. Existing global acoustic, vault, retrieval and other catalog blockers remain; no production-ready certificate.
""")
    write('changes.md',f"""# Retained changes and measured decision

repo_abilities.py: reject oversized code before AST allocation; validate bounded proposal lists/boolean scope/enums and constructor flags/numeric settings; strict boolean/deep-copy review and code/scope digest binding, including queued voice approval; codehash for pending update; no post-approval repair; cancel/revalidate before promotion; preserve source commit and fetch pinned/bounded repository archive. Serialize shared child execution and invocation bookkeeping; UUID scratch directories. Require fresh per-action network approval and persist conservative write uncertainty before dispatch. Validate output contracts, withdraw broken version and restore one prior approved/hash-verified metadata record without executing it; keep uncertainty through rollback. Redact recognized credentials in logs, add forge trace UUID and prevent local prompts using environment proxies. Existing command/config names retained; no dependency added.

ability_runner.py: reject non-string text and non-list/path-string outputs; report output_contract versus execution failure so the host can withdraw/rollback the version. Compatibility for a plain string return remains. No replacement of the existing separate Docker skills engine.

{measured} Initial-call cold p50/p95 **{bench['before']['cold']['p50_ms']:.4f}/{bench['before']['cold']['p95_ms']:.4f}→{bench['after']['cold']['p50_ms']:.4f}/{bench['after']['cold']['p95_ms']:.4f}ms**. Keep early return: identical rejection and valid-utility acceptance, fewer allocations, no new dependency. Five initial calls are labeled cold within an imported process; twenty subsequent calls warm. Construction/import/source allocation excluded. No valid-build throughput or GPU/TTFT/TTFA gain claimed. New serialization reduces potential throughput to preserve process ownership; approval adds deliberate interaction and the checkpoint adds disk I/O, not an unmeasured overall performance win.

New test_ability_forge_audit.py supplies32 actual catalog mappings, fault injection,5×20 concurrency, real owned child crash and runner typing, fake network privacy and metadata rollback. Existing legacy tests unchanged. Accounting allowlists/test updated; docs and root overview updated with dated scope. No visible UI change/new screenshot; art and attribution retained. [Exact files](files-changed.json), [patch](source.patch), [preimage hashes](source-hashes.json), [generated evidence](generated-files.json).
""")
    write('compatibility.md',f"""# Official upstream and compatibility — 2026-10-16 IST

[Checked URLs/release dates](upstream-checks.json). Installed Python3.10.6, pip26.2.1, Requests2.34.2, pytest8.4.2, psutil7.2.2; Docker CLI29.8.2; RTX3050 Laptop4096MiB/driver610.74; RAM{env['ram_bytes']}B. Actual commands in environment/commands evidence.

[pip26.2.1](https://pypi.org/project/pip/26.2.1/) released **2026-08-04**, currently listed latest and requiresPython≥3.10. Installed version retained. [pip binary-only option](https://pip.pypa.io/en/stable/cli/pip_install/#cmdoption-only-binary) documents refusing source distributions; binary-only is not package authenticity or sandboxing. No package upgrades/installers run.

[Python3.10.21](https://www.python.org/downloads/release/python-31021/) released **2026-08-12**; Python3.10 reached end-of-life **2026-10-01**. Current interpreter3.10.6 is older. A supported Python/environment migration needs separate compatibility/resource verification; no installer/system change made. [Version-matched audit-hook documentation](https://docs.python.org/3.10/library/sys.html#sys.addaudithook) explicitly excludes using these hooks as a hostile-code sandbox. Current code therefore keeps the guard-rail limitation explicit rather than claiming Docker isolation for voice abilities.

[Docker Desktop4.95.0 notes](https://docs.docker.com/desktop/release-notes/#4950) dated **2026-10-12** reviewed; engine startup/Enhanced Container Isolation fixes relevant to future maintenance. CLI version does not identify the Desktop app version; no claim that Desktop is current or upgraded. [Seccomp](https://docs.docker.com/engine/security/seccomp/) and [rootless security](https://docs.docker.com/engine/security/rootless/) reviewed as boundaries, not proof of those host modes. Existing isolated runtime tests:{iso_pass} PASS/{iso_skip} skipped. No image build/pull/OS setting change.

Source docs without a release date are recorded as documentation checked on the run date. Actual local/model/GPU voice acceptance remains BLOCKED by unavailable Ollama and lack of a separately authorized live human/account/ability trial. Those live gates are separate from32 automated mock/owned catalog PASS. Prior global dependency/security gates remain open. No new paid API requirement or giant model download.
""")
    write('rollback.md',"""# Rollback and deterministic resume

No audit commit. Preserve inherited dirty branch and user/module14–18 diffs. Compare source.patch and current SHA256 before restoring only this change from ignored .jarvis-runtime/jarvis-audit/module19-pre (app-relative paths encoded with __, root-README.md for parent). Never git reset all or overwrite user state/vault/recordings. New fields are additive; old code may ignore uncertain_external_write, so never downgrade against a live ability registry until pending external actions are inspected. No production data migrated or ability installed by this audit.

Runtime rollback stores one previous approved version; failed-type output restores its metadata only after verifying the old code hash. Nothing is executed or resent. Missing/tampered previous version remains failed. Failed approved validation preserves the already working version. Rebuild/review is required after changed code or an uncertain network result, following inspection of fresh external state. Voice queue consent hashes are ephemeral; restart cannot replay the old queued approval.

From app/ with existing .venv/Scripts/python.exe:
1. scripts/verification/verify_ability_forge_audit.py (bounded original preimage versus current A/B).
2. -m pytest tests/test_ability_forge_audit.py tests/test_repo_abilities.py tests/test_repository_skills.py tests/test_repository_skill_isolation.py tests/test_repo_learning.py tests/test_intent_direct_audit.py tests/test_capabilities.py tests/test_toolkits.py tests/test_audit_result_accounting.py -q --junitxml=artifacts/jarvis-audit/modules/19-ability-forge/cases-and-contracts.xml
3. Freeze jarvis/*.py and tests/test_*.py SHA256, then -m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/19-ability-forge/full-regression.xml; do not edit runtime/tests during acceptance.
4. -m jarvis.launcher --check (read-only); keep raw diagnostics in ignored runtime storage and publish only redacted summary.
5. scripts/verification/report_ability_forge_audit.py then scripts/verification/verify_ability_forge_artifacts.py; git diff --check.

Next unrun module/case: JRV-20-001. Earliest older unresolved: JRV-04-001. Global remaining-case-ids.txt records every exact incomplete ID; do not infer PASS from a related regression. Open live/hardening gates listed in compatibility.md and failures.md. Future runtime installation, ability activation, accounts, deployment require the prompt's explicit per-action authorization.
""")
    headline=f"**Ability-forge audit — 2026-10-16 IST:** Review now binds code/version/scope; network runs require fresh approval and a durable non-replay checkpoint. Wrong-type output withdraws the new version and can restore prior approved metadata without execution. Oversized code is rejected before parsing.\nVerification: **{full['PASS']:,} full regression PASS /{full['SKIPPED']} skips**; **32 Prompt19 catalog fixture PASS**. Voice abilities use process guard rails, not Docker isolation. Launcher **{ready['status']}**; live model/account/voice acceptance and supported Python migration remain open."
    for path,link in [(BASE/'README.md','artifacts/jarvis-audit/modules/19-ability-forge/inventory.md'),
                      (BASE.parent/'README.md','app/artifacts/jarvis-audit/modules/19-ability-forge/inventory.md'),
                      (BASE/'docs/system-map.md','../artifacts/jarvis-audit/modules/19-ability-forge/inventory.md'),
                      (BASE/'docs/repo-abilities.md','../artifacts/jarvis-audit/modules/19-ability-forge/inventory.md')]:
        value=path.read_text(encoding='utf-8');first,rest=value.split('\n',1)
        if '<!-- prompt19-audit -->' in rest:
            start=rest.index('<!-- prompt19-audit -->');end=rest.index('<!-- /prompt19-audit -->')+len('<!-- /prompt19-audit -->')
            rest=rest[:start]+rest[end:]
        path.write_text(first+'\n\n<!-- prompt19-audit -->\n'+headline+'\n[Evidence, limits and rollback]('+link+').\n<!-- /prompt19-audit -->\n\n'+rest.lstrip('\n'),encoding='utf-8')
    table='\n'.join('| '+str(m['number']).zfill(2)+' '+m['module']+' | '+', '.join(f'{k}: {v}' for k,v in Counter(r['status'] for r in catalog if r['id'].startswith(f"JRV-{m['number']:02}-")).items())+' |' for m in modules)
    report=f"""# Jarvis audit — Prompt19 — 2026-10-16 IST

{headline}

Repo **{env['commit']}**, branch **{env['branch']}**, dirty inherited changes preserved; no audit commit. [Environment](modules/19-ability-forge/environment.json). Baseline {baseline}; targeted {target}; full {full}. **381 runtime/test hashes unchanged during accepted full run.** [Exact output](modules/19-ability-forge/full-regression.xml), [skip reasons](modules/19-ability-forge/full-regression-skip-reasons.json), [readiness](modules/19-ability-forge/readiness.json).

{scope}

{measured}

[Source-map-to-code evidence matrix](modules/19-ability-forge/inventory.md), [changes/metrics](modules/19-ability-forge/changes.md), [exact files](modules/19-ability-forge/files-changed.json), [source diff](modules/19-ability-forge/source.patch), [upstream URLs/dates](modules/19-ability-forge/compatibility.md), [flaws/risk](modules/19-ability-forge/failures.md), [rollback/resume](modules/19-ability-forge/rollback.md).

Production readiness remains incomplete: audit hooks cannot isolate hostile native packages; wheel supply-chain/scope pinning and supported Python migration remain maintenance gates. No live inference/voice/account acceptance or deployment performed. All1,184 IDs: **{counts}**. [Exact ledger](test-results.jsonl), [remaining IDs](remaining-case-ids.txt). Next NOT RUN **JRV-20-001**; earliest unresolved **JRV-04-001**. Prompt19 fixture coverage is complete; the overall37-module production audit remains incomplete.

[Previous Prompt18 report](final-report-before-module19.md) preserves its original dates, metrics and limitations.

## Enumerated modules

| Module | Catalog status |
| --- | --- |
{table}

## Category and tier statistics

```json
{json.dumps({k:summary[k] for k in ('by_category','by_tier')},indent=2)}
```
"""
    (OUT/'final-report.md').write_text(report,encoding='utf-8')
    files=['jarvis/repo_abilities.py','jarvis/ability_runner.py','tests/test_ability_forge_audit.py',
        'scripts/verification/audit_catalog.py','tests/test_audit_result_accounting.py',
        'scripts/verification/verify_ability_forge_audit.py','scripts/verification/report_ability_forge_audit.py',
        'scripts/verification/verify_ability_forge_artifacts.py','README.md','docs/system-map.md','docs/repo-abilities.md','../README.md']
    changed=[];pairs=[];diff=[]
    for name in files:
        current=BASE/name;old=PRE/('root-README.md' if name=='../README.md' else name.replace('/','__'))
        changed.append({'path':name,'sha256':sha(current)})
        if old.exists():pairs.append({'path':name,'before':sha(old),'after':sha(current)})
        diff.extend(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True) if old.exists() else [],
            current.read_text(encoding='utf-8').splitlines(True),fromfile='before/'+name if old.exists() else '/dev/null',tofile='after/'+name))
    write('files-changed.json',json.dumps(changed,indent=2));write('source-hashes.json',json.dumps(pairs,indent=2));write('source.patch',''.join(diff))
    generated=['artifacts/jarvis-audit/'+s for s in ('final-report.md','final-report-before-module19.md','module-map.json','summary.json','test-results.jsonl','executed-tests.jsonl','remaining-case-ids.txt')]
    generated += [p.relative_to(BASE).as_posix() for p in MOD.iterdir() if p.is_file()]
    generated += ['artifacts/jarvis-audit/modules/19-ability-forge/'+s for s in ('generated-files.json','artifact-verification.json')]
    write('generated-files.json',json.dumps(sorted(set(generated)),indent=2))
    print(json.dumps({'module19':dict(Counter(r['status'] for r in cases)),'full':full,'catalog':counts},indent=2))


if __name__=='__main__':main()
