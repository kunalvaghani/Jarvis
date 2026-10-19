"""Build the independent audit package from fresh machine-readable evidence."""
import ast
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parents[2]
OUT = BASE / 'artifacts/jarvis-audit/codex-independent-review'
PIN = '36fbf3ce925080f7f54afa87eaf1d9b88414142d'
LIVE = {
    'startup': ['cold startup with original environments', 'warm startup', 'intentional microphone stop', 'owned worker crash and restart'],
    'voice': ['audible F5 synthesis', 'microphone word error rate', 'wake word and barge-in', 'audio device loss'],
    'planning': ['local model multi-step planning', 'adversarial model tool names'],
    'desktop': ['physical demonstration click', 'changed DPI and window layout replay', 'Blender disposable scene', 'Unreal disposable project'],
    'browser': ['browser crash during uncertain mutation'],
    'memory': ['cold real-vault hierarchical index', 'warm semantic retrieval', 'original note before-after hashes'],
    'training': ['bounded GPU training smoke', 'bit-exact checkpoint resume', 'held-out adapter comparison', 'deployed inference artifact identity'],
    'integrations': ['explicitly authorized non-sensitive free-tier consultation', 'read-only account integration smoke'],
    'performance': ['voice-to-output latency', 'model first-token latency and throughput', 'multi-hour bounded soak', 'GPU foreground preemption under training'],
}


def put(name, text):
    (OUT / name).write_text(text.strip() + '\n', encoding='utf-8')


def git(*args):
    return subprocess.run(['git', *args], cwd=BASE.parent, capture_output=True, text=True, timeout=30).stdout.strip()


def canonical(identifier):
    path, separator, test = identifier.partition('::')
    path = path.replace('\\', '/')
    path = 'tests/' + path.split('tests/', 1)[1] if 'tests/' in path else path
    return path + separator + test


def xml_identifier(case):
    parts = case.attrib['classname'].split('.')
    start = parts.index('tests')
    return 'tests/' + parts[start + 1] + '.py::' + '::'.join(parts[start + 2:] + [case.attrib['name']])


def main():
    run = json.loads((OUT / 'regression-results.json').read_text(encoding='utf-8'))
    tests = {}
    for row in run['tests']:
        row['id'] = canonical(row['id'])
        tests[row['id']] = row
    documents = json.loads((OUT / 'documents-results.json').read_text(encoding='utf-8'))
    for row in documents['tests']:
        row['id'] = canonical(row['id'])
        if row['status'] in ('PASS', 'FAIL'):
            row['method'] = 'real reviewed source; original utility interpreter; disposable documents/skills; author/approval callbacks simulated'
            tests[row['id']] = row
    # A final affected-suite rerun supersedes the matching rows, without counting duplicates.
    for filename in ('trainer-final.xml', 'reference-verified.xml', 'lab-final.xml', 'browser-final.xml'):
        final = ET.parse(OUT / filename)
        for case in final.findall('.//testcase'):
            testid = xml_identifier(case)
            failure = case.find('failure')
            error = case.find('error')
            skipped = case.find('skipped')
            tests[testid] = {'id': testid, 'status': 'FAIL' if failure is not None or error is not None else 'SKIPPED' if skipped is not None else 'PASS',
                'runtime_seconds': float(case.attrib['time']), 'executed_body': skipped is None and error is None,
                'actual_result': (failure.text if failure is not None else error.text if error is not None else 'Final affected-suite rerun; see ' + filename), 'evidence': filename,
                'method': 'synthetic fixtures or isolated Git; no training or GUI'}
    rows = list(tests.values())
    for domain, purposes in LIVE.items():
        for index, purpose in enumerate(purposes, 1):
            rows.append({'id': f'LIVE-{domain}-{index:02d}', 'domain': domain, 'purpose': purpose,
                         'status': 'NOT RUN', 'runtime_seconds': 0, 'executed_body': False,
                         'actual_result': 'Pending dedicated live acceptance; not inferred from fixture or historical results.',
                         'evidence': '13-unresolved-blockers.md', 'method': 'real application acceptance (pending)'})
    enriched = []
    source_cache = {}
    function_cache = {}
    for row in rows:
        path_text = row['id'].split('::')[0].replace('\\', '/')
        file = BASE / path_text
        fields = {'purpose': row.get('purpose', row['id'].split('::')[-1].split('[')[0].replace('_', ' ')),
                  'domain': row.get('domain', Path(path_text).stem.removeprefix('test_')),
                  'preconditions': 'See source fixtures, parameter values and skip reason; original interpreter reused.',
                  'environment': 'Windows; isolated codex-review worktree; Python 3.10.6',
                  'input': 'Source-defined synthetic/disposable fixtures; parametrization retained in unique ID.',
                  'expected_result': 'Source assertions hold; no inference of real feature acceptance.',
                  'related_source_files': path_text if file.is_file() else '', 'source_line': '', 'verification_evidence': row['evidence']}
        if file.is_file() and '::' in row['id']:
            if path_text not in source_cache:
                text = file.read_text(encoding='utf-8')
                tree = ast.parse(text)
                source_cache[path_text] = (text, {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)})
            text, functions = source_cache[path_text]
            name = row['id'].split('::')[-1].split('[')[0]
            node = functions.get(name)
            if node:
                fields['source_line'] = node.lineno
                if (path_text, name) not in function_cache:
                    function_cache[path_text, name] = [ast.get_source_segment(text, n) for n in ast.walk(node) if isinstance(n, ast.Assert)]
                asserts = function_cache[path_text, name]
                fields['expected_result'] = '; '.join(asserts[:3])[:1800] or 'See unittest assertions and source at recorded line.'
                fields['preconditions'] = 'Fixtures/arguments: ' + ', '.join(a.arg for a in node.args.args)
            if 'recorded_checkpoint' in name:
                row['method'] = 'historical artifact assertion; NOT a new training/evaluation run'
            elif any(w in name for w in ('mcp_workflows_register', 'generated_server_container', 'wrong_or_hanging_generated', 'sandbox_scores', 'correct_advice_is_verified')):
                row['method'] = 'real isolated Docker execution; providers/authors may be simulated'
            else:
                row['method'] = row.get('method', 'mixed fixture regression; see source')
        row.update(fields)
        row['root_cause_when_failed'] = row['actual_result'] if row['status'] == 'FAIL' else ''
        if row['status'] == 'FAIL' and 'Hermes catalog unavailable' in row['actual_result']:
            row['root_cause_when_failed'] = 'Worktree lacks the ignored Hermes installation manifest; existing census assertion assumes it is installed.'
        elif row['status'] == 'FAIL' and 'LocalGithub\\\\LocalGithub' in row['actual_result']:
            row['root_cause_when_failed'] = 'Default sibling LocalGithub path resolves to LocalGithub/LocalGithub in this nested review checkout; explicit installation path is needed.'
        enriched.append(row)
    counts = {s: sum(r['status'] == s for r in enriched) for s in ('PASS', 'FAIL', 'BLOCKED', 'SKIPPED', 'NOT RUN')}
    result = {'date': '2026-10-19 IST', 'audited_commit': PIN, 'review_branch': git('branch', '--show-current'),
              'planned': len(enriched), 'executed_bodies': sum(r['executed_body'] for r in enriched), 'counts': counts,
              'executed_checks': counts['PASS'] + counts['FAIL'],
              'genuine_full_assistant_e2e': 0, 'scope': 'Independent checkpoint, not complete live acceptance',
              'tests': enriched}
    put('05-test-results.json', json.dumps(result, indent=2))
    fields = ['id', 'domain', 'purpose', 'preconditions', 'environment', 'input', 'method', 'expected_result',
              'actual_result', 'verification_evidence', 'runtime_seconds', 'status', 'executed_body',
              'root_cause_when_failed', 'related_source_files', 'source_line']
    with (OUT / '04-test-matrix.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(enriched)
    header = f'# Independent Jarvis audit checkpoint — 2026-10-19 IST\n\nPinned `claude`: `{PIN}`. Isolated branch `codex-review`. This package reports actual execution, not a certification of the entire assistant.\n\n'
    docs = {}
    docs['01-architecture-audit.md'] = '''## Actual execution graph

User voice/typed input → audio/engine/commands → Actions/cognition → deterministic handlers or BrainClient/brain_worker → validated DAG/native planning → ToolRegistry → specialized executor → independent postcondition/checkpoint → TaskState/SkillMemory/ReasoningBank/Obsidian → speech/island output.

The new systems reuse this graph: execution_strategy ranks eligible adapters; skill_store/skill_evolution persist telemetry and candidates; exploration/learning_memory feed reasoning_bank; viking_memory indexes a source vault through a separate worker; evolution_lab snapshots into a separate Git repository and evolution_eval gates bounded literal mutations; AZR training is offline. cloud_architect returns untrusted advice after eligibility, privacy and consent. demonstration captures and validates a provisional workflow.

`source-inventory.json` contains hashes, imports, top-level symbols and line numbers for 736 Python files (inventory-time count; new audit files are recorded separately in the manifest). This is a static import graph including conditional imports, not proof every edge executes. The documentation system-map, self-evolution, cognitive-architecture and hierarchical-execution were read as claims, not acceptance evidence.

Permissions: ToolRegistry policy/allowlists and per-action approval are execution gates. Recovery must not replay uncertain external actions. New services require owned-process health checks. AST inventory, fixture regression, runtime readiness and live acceptance are separate evidence levels.

Inspected source boundaries include brain, cognition, capabilities, skill_memory/store/evolution, deliberation, demonstration, cloud_architect, execution_strategy/contracts, tools/toolkits, launcher/recovery, mcp_synthesis, viking_memory, reasoning_bank, AZR dataset/oracles/trainer, GPU validation, paths and evolution promotion. Remaining module interfaces are indexed, not individually behavior-certified.
'''
    inventory = json.loads((OUT / 'source-inventory.json').read_text(encoding='utf-8'))
    docs['02-feature-inventory.md'] = '''All discovered first-party modules follow. Imports and symbols are in source-inventory.json. Status is **discovered**, not live verified. Consult the test matrix for executed behavior; absence of a matching test remains a gap.

| Module | Bytes | SHA-256 | Interfaces |
|---|---:|---|---|
''' + '\n'.join(f"| {r['path']} | {r['bytes']} | {r['sha256']} | {', '.join(s['name'] for s in r['symbols'])} |" for r in inventory if r['path'].startswith('jarvis/'))
    docs['03-claude-claims-vs-evidence.md'] = '''| Claim | Independent evidence | Limit |
|---|---|---|
| No uncertain write replay | DAG/task recovery fixture assertions | No real account mutation crash test |
| Living skills telemetry and trust | Phase03 SQLite/discovery, real document CAPTURED/FIX/reuse and candidate rejection tests | Original utility interpreter explicitly routed; author/approval callbacks simulated |
| Generated MCP isolation | Real container tests and hostile/hanging server rejection | Authored specs; no live model gap-solving trial |
| ReasoningBank | Temporary SQLite strategy/anti-pattern/retrieval tests | Semantic embedding and real-vault checks deferred |
| Sealed retention gate | Disposable committed Git evaluator, regression/tamper/resource cases | Fixture benchmarks; no production promotion |
| AZR held-out improvement | Historical checkpoint assertion exists in Phase08 | Not independent retraining; not adopted as fresh evidence |
| Recorder stores no private fields | Independent synthetic private Text/toggle fixtures failed baseline | Narrow repair passes; physical click/DPI/dialog acceptance pending |
| Training defers for foreground inference | Independent unknown-state and pre-import tests failed baseline | Repairs tested without GPU; no mutual exclusion guarantee for races |
| Historical 3,000+ full regression pass totals | Not used as new results | This checkpoint runs a selected suite, not all repository tests |

No historical benchmark or completion claim is counted as a freshly executed live test. Public pytest JUnit format was checked through Firecrawl: https://docs.pytest.org/en/6.2.x/usage.html . No repository/private content was uploaded.
'''
    docs['06-bug-register.md'] = '''| ID | Severity | Root cause | Provenance | Status |
|---|---|---|---|---|
| IR-001 | P1 | demonstration.window_state copies private/unknown UIA Text and toggle names without is_password screening; snapshots are persisted by sessions | Added in Phase05 commit 105b97b | Fixed in isolated checkout; four failing synthetic cases now pass |
| IR-002 | P1 | trainer treats GPU-state read/JSON failures as idle, omits shared schema validation, and checks foreground only after loading GPU dependencies/model | Added in Phase07 commit caffdd8 | Fixed unknown-state handling plus pre-import admission; eight final synthetic cases pass |
| IR-003 | P1 | Windows recipe catalog and source were pinned with inconsistent newline conventions; Git autocrlf checkout breaks ordinary command routing | Pre-upgrade commit b54c0c1 | Normalize CRLF to LF before pinned-content checks; LF/CRLF and tamper tests plus cognition/STT retests |
| IR-004 | P2 | Isolated evolution Git worktree creation fails at Windows MAX_PATH on a deep source snapshot | Added in Phase06 commit 46c77cd | Per-command core.longpaths=true for owned Git subprocesses; lab-final.xml |

Baseline reproduction: reproductions-before.xml = 10 FAIL / 1 PASS. Additional early-admission reproduction: training-admission-before.xml = 1 FAIL. These demonstrate two root causes, not eleven independent defects. Retests: trainer-final.xml and reproductions-after.xml. No P0 or P3 defect was confirmed within this checkpoint. Suite failures must be read independently; they are not silently recategorized as passes.

The early limited sandbox run trainer-related-after.xml had two environment-induced failures (Git config writes and atomic registry replace denied). Its failures remain preserved; the outside-sandbox rerun is trainer-final.xml.
'''
    docs['07-security-findings.md'] = '''IR-001 is a local recording/privacy defect: rejecting a clicked password element did not screen the separate before/after state snapshot. Reused is_password now excludes true and unknown privacy states from text/toggle observations. Synthetic public text remains observable. Window titles and arbitrary non-password accessible names can still contain personal information: this change does not claim comprehensive PII removal.

IR-002 is a resource-safety defect: corrupt/unreadable state must defer optional training. The trainer now bounds the read, calls the scheduler's validate_state, distinguishes FileNotFoundError from unknown state and checks admission before dependency imports/output writes. Missing state retains idle compatibility; existing live/stale holder tests remain.

IR-003 preserves recipe hashes across LF/CRLF conversion; edited content still fails. IR-004 enables long paths per owned lab Git command without changing global configuration. reference-before.xml and reference-verified.xml preserve the pre-repair failures; lab-final.xml verifies the lab repair.

Cloud adversarial tests use fake providers and synthetic paths/tokens. No sensitive test strings were sent to a cloud model. MCP hostile code runs in reviewed isolated containers, not host execution. Evolution candidates use disposable Git repositories. No automatic deployment or merger is performed.

Unverified security scope: physical UI disclosure, all generated-tool privilege boundaries under concurrency, training/foreground race-free exclusion, and prompt injection through every live external service. Regex/static screens are not a general semantic privacy proof.
'''
    bench = json.loads((OUT / 'paired-benchmarks.json').read_text(encoding='utf-8'))
    docs['08-performance-benchmarks.md'] = '''Paired baseline/candidate measurements use exact baseline source loaded from Git and current repaired source. Each scenario has 500 warm samples per version, alternating order, plus one first-call pair. All data are synthetic. Standard deviation, p95, min/max and first-call observations are in paired-benchmarks.json. No confidence interval or general improvement claim is inferred from a single session.

| Scenario | Baseline median ms | Candidate median ms | Absolute delta ms | Relative delta |
|---|---:|---:|---:|---:|
''' + '\n'.join(f"| {name} | {m['baseline']['median_ms']:.6f} | {m['candidate']['median_ms']:.6f} | {m['absolute_delta_ms']:+.6f} | {m['relative_delta_percent']:+.2f}% |" for name, m in bench['measurements'].items()) + '''

These are safety-check overhead regressions. The lease first-call candidate includes importing the shared validator and must not be described as warm cost. UIA objects are synthetic; these timings omit COM latency. No 5–10 second assistant response target, training gain, acoustic latency, model throughput, real desktop task speed, sustained throughput or startup target has been proven. Concurrent regression activity and OS scheduling add measurement uncertainty.
'''
    docs['09-four-pillars-verification.md'] = '''| Pillar | Result | Remaining evidence |
|---|---|---|
| A: living skills/MCP | PARTIAL: real store/ranking, document capture/repair/reuse and Docker server lifecycle | Live model-authored workflows; author/approval callbacks simulated; arbitrary crash/retry acceptance |
| B: exploration/memory | PARTIAL: fixture ReasoningBank and cancellation/recovery | Live isolated exploration, semantic embeddings, fresh OpenViking source hashes and cold/warm benchmark |
| C: controlled evolution | PARTIAL: disposable Git archive/gate/promotion fixture tests | Real model prompt evolution, production-resource interaction, independently re-evaluated current candidate |
| D: AZR/LoRA | PARTIAL: real symbolic oracles, reward/dataset guards, container tests where executed | Fresh training/resume/adapter comparison; historical results not independent proof |

IR-002 repairs the trainer guard; it does not establish learned model improvement. No experimental model was promoted or wired into inference.
'''
    docs['10-execution-recovery-verification.md'] = '''API/code-first: initial document checks lacked the worktree-local utility environment. Explicit documents mode then routed interpreter paths (not source/runtime state) to the original installation and passed 46 disposable API/skill fixtures, including earlier eligibility failures. No native Office GUI trial. Unreal manifest presence is not editor execution proof.

Cloud architect: disabled/default, eligibility, consent, payload rejection, provider outages, inert hostile advice and container verification exercised with simulated providers. Live Groq NOT RUN. No provider-account changes made.

Show Me Once: snapshot privacy reproduced and repaired synthetically. Physical mouse input, UIA replay after changed layout, DPI, app switching and audible prompts NOT RUN. Recovery/retry tests exercise isolated action state and refuse uncertain replay; they do not prove live account write recovery.

Launcher `--check` was executed in the worktree. See launcher-check.json: repair_required due to absent worktree runtime environments and model files. The original checkout has environments, enumerated in environment.json. Local Docker/Ollama service presence is readiness only, not live feature acceptance.
'''
    docs['11-other-jarvis-capabilities.md'] = '''| Capability | Evidence scope |
|---|---|
| Voice | STT/TTS transport/audio fixtures; no microphone recording/playback |
| Planning | Typed DAG validator, scheduler, checkpoint and policy fixtures; no new LLM quality trial |
| Computer control | Tool contracts and selector/cancellation fixtures; no physical desktop acceptance |
| Browser | Mocked policy fixtures plus real headless loopback fill/click/DOM verification (browser-final.xml); no live account |
| Coding | Temporary-file/native coding fixtures; no new model-authored project |
| Memory | Isolated store/retrieval fixtures; no original vault mutation |
| Integrations | Registry contracts and disposable containers; live accounts NOT RUN |
| Recovery | Injected exceptions, cancellation, no-replay, owned supervisor fixtures |
| Security | Independent snapshot/trainer defects plus existing adversarial suites |
| Performance | Paired synthetic microbenchmarks only |

The selected suite exceeds the requested numerical target if enough bodies pass execution; the count does not imply every requested category has live coverage. Full application scenarios A–J remain pending acceptance work.
'''
    docs['12-code-fixes-and-diffs.md'] = '''Small repairs only: jarvis/demonstration.py screens snapshot descendants using existing privacy logic; scripts/training/train_azr_lora.py validates bounded lease state, defers unknown state and checks admission before model imports/output creation. windows_commands.py normalizes JSON line endings before verifying pinned hashes. evolution_lab.py enables Windows long paths for its Git subprocesses without changing global Git settings. New independent regression tests and audit/benchmark/report scripts retain evidence. No dependency, model, launcher entrypoint, service ownership, runtime manifest or user-facing UI change.

See source-fixes.patch, changed-files.txt, final-state.json and evidence-hashes.json. Patch baseline is the pinned SHA; final-state records the repair commit separately from the package revision. The initial selected run overlapped incremental repairs; regression-initial.* preserves it. The final regression.* run uses the exact committed repair source with no source edits during execution. Final affected-suite/document results supersede overlapping rows without duplicate counting. Eight installation-dependent failures remain.
'''
    docs['13-unresolved-blockers.md'] = '''This is a resumable checkpoint, not completion of the complete master directive. Remaining work is listed explicitly in 04-test-matrix.csv as LIVE-* NOT RUN rows.

The audit worktree does not contain the original environments/model caches. Do not copy secrets or runtime databases to make readiness green. Resolve read-only runtime dependency routing or provision isolated environments deliberately before document/OpenViking/model trials.

Read-only interpreter routing was completed for the document rerun. Eight final failures remain: one Hermes census assertion lacks ignored installation metadata; seven coding/assembly cases derive a nonexistent LocalGithub/LocalGithub default from the nested worktree location. Configure their installation paths before acceptance. Failed results remain FAIL, not silently skipped or passed.

First restricted attempts could not complete browser/Git/temp atomic-replace operations. They were stopped; empty regression.log and absence of completed result files are not passing evidence. The recorded selected run uses outside-sandbox disposable fixtures. The separately rerun headless loopback browser case passed (browser-final.xml); its duplicate manual live placeholder is replaced by the real test ID rather than counted twice. Inspect checkpoint/skip messages; skips are not feature passes.

No real microphone, physical click, GUI acceptance, external account mutation, fresh GPU training, deployed-artifact comparison or long-duration soak was performed. No exhaustive vulnerability scan or certification of every module. The trainer remains a cooperative, read-only lease observer; concurrent admission races are not resolved by the narrow guard repair.
'''
    docs['14-rollback-and-reproduction.md'] = f'''Audited SHA: `{PIN}`. Worktree: `D:/Kunals GitHub Repo/LocalGithub/Jarvis-codex-review`. Original checkout: clean when audit began; no source edits there. Review branch: `codex-review`; no merges into claude/main.

From app/, using the existing original `.venv/Scripts/python.exe` as interpreter:

```powershell
python scripts/verification/independent_audit.py inventory
python scripts/verification/independent_audit.py smoke
python scripts/verification/independent_audit.py regression
python scripts/verification/independent_audit.py security
python scripts/verification/independent_audit.py documents
python -m pytest tests/test_independent_review.py -q -p no:cacheprovider
python scripts/verification/independent_benchmarks.py
python -m jarvis.launcher --check
python scripts/verification/independent_report.py
```

Use distinct output folders or preserve an earlier packet before rerunning: scripts update their own report files and pytest basetemp is disposable. pytest needs normal process/Git permissions for disposable nested repositories. External account tests are not enabled. Real-app/performance/long-soak acceptance is listed rather than implemented as an unsafe automatic mode.

To reproduce the defects without reverting production: create another isolated checkout at the pinned SHA, copy only tests/test_independent_review.py there, and run the selected independent tests. Baseline evidence preserves the original 10 failures plus the later pre-import failure. To undo reviewed repairs, revert their reviewed commit on the review branch only, or discard the isolated worktree after deliberately preserving needed evidence. Never reset/restore the working claude or main checkout.
'''
    docs['15-final-verdict.md'] = f'''## A. Repository state

Audited `{PIN}`. Branch codex-review, isolated checkout. See revisions.json, final-state.json, changed-files.txt and source-fixes.patch. No main/claude source changes or automatic merge. Uncommitted original changes: none at start; final-state records the recheck.

## B. Test execution

Planned unique test IDs: **{len(enriched)}**. Completed checks (PASS/FAIL): **{result['executed_checks']}**; test bodies attempted including runtime skips: **{result['executed_bodies']}**. PASS **{counts['PASS']}**, FAIL **{counts['FAIL']}**, BLOCKED **{counts['BLOCKED']}**, SKIPPED **{counts['SKIPPED']}**, NOT RUN **{counts['NOT RUN']}**. Counts deduplicate final affected-suite reruns. Existing catalog wrappers can reuse assertions; unique IDs do not establish unique semantic coverage. Genuine full-assistant end-to-end tests completed: **0**. Real isolated component/container/Git flows are identified separately. Historical artifact assertions are not live training evidence.

## C–E. Pillars, upgrades and existing Jarvis

All four pillars are PARTIALLY VERIFIED within fixture/container scope; none receives a new live acceptance certification. API-first PARTIAL; cloud architect simulated-provider verification only; Show Me Once snapshot repair verified synthetically. Voice, planning, browser, coding, memory and recovery have selected regression evidence; physical computer control and live account integrations remain unverified. See 09–11.

## F. Defects

Three confirmed P1 root causes and one P2 portability defect repaired in isolation. No P0/P3 application defect independently confirmed in this checkpoint; remaining suite failures are reported verbatim for diagnosis, not erased. Baseline independent failures and final retests are preserved. See bug register and current failing rows.

## G. Performance

500 paired warm samples per version per scenario. Small positive overhead for added privacy/schema validation; first-call values and variance retained. No measured end-user improvement, model-training improvement or response-time target claim.

## H. Recommendation

**Safe for code review; not ready for deployment on this evidence.** Complete unresolved failure triage and dedicated live acceptance before deployment. This packet is a checkpoint, not the requested entire-system audit completed.
'''
    for name, body in docs.items():
        put(name, header + body)
    put('.gitignore', 'scratch*/\n__pycache__/')
    repaired = ['app/jarvis/demonstration.py', 'app/scripts/training/train_azr_lora.py',
                'app/jarvis/windows_commands.py', 'app/jarvis/evolution_lab.py']
    put('source-fixes.patch', git('diff', PIN, '--', *repaired))
    put('candidate-source-hashes.json', json.dumps({p: hashlib.sha256((BASE.parent / p).read_bytes()).hexdigest() for p in repaired}, indent=2))
    manifest = sorted(set(git('diff', '--name-only', PIN).splitlines() + git('ls-files', '--others', '--exclude-standard', '--full-name').splitlines()))
    put('changed-files.txt', '\n'.join(manifest))
    put('final-state.json', json.dumps({'audited_commit': PIN, 'review_head_at_report_generation': git('rev-parse', 'HEAD'),
        'repair_commit': git('log', '-1', '--format=%H', '--', *repaired),
        'claude_now': git('rev-parse', 'claude'), 'main_now': git('rev-parse', 'main'),
        'original_status': subprocess.run(['git', 'status', '--porcelain'], cwd='D:/Kunals GitHub Repo/Jarvis', capture_output=True, text=True).stdout,
        'date': '2026-10-19 IST'}, indent=2))
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file() and p.name != 'evidence-hashes.json'}
    put('evidence-hashes.json', json.dumps(hashes, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k != 'tests'}, indent=2))


if __name__ == '__main__':
    main()
