"""Publish bounded Phase E receipts and dated documentation; no live actions."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];PRIVATE=ROOT/'app/.jarvis-runtime/lab-validation';PUBLIC=ROOT/'docs/lab/evidence'
KEYS=('date_local','passed','failed','skipped','errors','collection_errors','exit_code','seconds','source_sha256_before','source_sha256_after','fingerprint_scheme','isolation','output_policy')

def publish(name,target):
    raw=json.loads((PRIVATE/name).read_text(encoding='utf-8'));out={k:raw[k] for k in KEYS if k in raw}
    assert out['source_sha256_before']==out['source_sha256_after'],'source changed during verification'
    (PUBLIC/target).write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    return raw,out

baseline,_=publish('e-baseline.json','e-baseline.json')
focused,summary=publish('e-focused-final.json','e-focused-final.json')
_,domain=publish('e-oracles-final.json','e-oracles-final.json')
assert baseline['passed']==255 and summary['passed']==269 and not summary['failed'] and not summary['errors']
terminal=PRIVATE/'e-full-final.json'
full_text='The final frozen-source whole-project regression is running; terminal exact-ID comparison is pending.'
if terminal.exists():
    from sys import path
    path.insert(0,str(ROOT/'app'))
    from jarvis.discovery.acceptance import verify_regression
    raw,out=publish(terminal.name,'e-full-final.json')
    assert out['source_sha256_after']==summary['source_sha256_after'],'focused/full source differs'
    comparison=verify_regression(raw,json.loads((PUBLIC/'d2-full-final.json').read_text()))
    out.update(comparison)
    (PUBLIC/'e-full-final.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    full_text=(f"Final guarded whole-project regression: **{out['passed']:,} passed / {out['failed']} failed / {out['skipped']} skipped**, "
               f"{out['seconds']:.3f} s including setup. Exact-ID comparison with D2: {len(out['new_failure_ids'])} new, "
               f"{len(out['resolved_failure_ids'])} resolved, {len(out['remaining_failure_ids'])} remaining failures; "
               f"{len([x for x in out['remaining_failure_ids'] if 'test_discovery_' in x])} Discovery failures. Source hashes unchanged. This is not live H acceptance.")

def insert(path,body):
    text=path.read_text(encoding='utf-8-sig');start='<!-- E CURRENT BEGIN -->';end='<!-- E CURRENT END -->'
    if start in text:
        first,rest=text.split(start,1);text=first+rest.split(end,1)[1].lstrip('\n')
    title,rest=text.split('\n',1)
    path.write_text(title+'\n\n'+start+'\n'+body+'\n'+end+'\n\n'+rest.lstrip('\n'),encoding='utf-8')

common=('**Phase E harness implemented; full A1–H acceptance remains UNMET.** New acceptance oracles/one-shot live harness reuse final-text Engine/Actions/brain, actual compiled plans/outbox/Journal/LabMemory, existing ngspice sandbox and C4 queue. No product neurons or second brain/router/store/queue; inventory remains42/38 templates. '
        'Actual bounded D/E/F subchecks pass: three conditional clocks, two native DC circuits, three fixed-scenario SciPy trials with retained hard rejection, owned worker exit23 after checkpoint/fresh-process resume, zero-budget stop and denied write gates. These operator-assisted subsets do not pass the full cases. A1/A2/B/C/G/H remain unmet; D/E/F remain partial. **0/100 full-acceptance points certified**, not an accuracy estimate; mandatory G/H remain unmet.\n\n'
        'User-approved partial audit Doc and conditional study Sheet were created exactly once and read back. Original pre-client credential-base failure and uncertain goals/slots are retained; a verified pre-SENT boundary allowed the same authorized two creates using the existing app account. No ambiguous provider write replay, credential copying, sharing/deletion/folders or paid use. No new model call/install/download/shared-service start/global activation. Counters: SciPy25/50, Blender16/50, ngspice39/50; exhausted C3 grants unchanged. Shipped Lab flagsfalse, act/learning-shadow/legacy control and PAUSED_BY_USER repair state unchanged.\n\n'
        f"Baseline255 focused passes. Final focused: **269 passed / zero failures/skips**, {summary['seconds']:.3f} s including setup; oracle14 passes. Strict neural mypy18 files/read-only host readiness pass. Portable audit checks8 original outputs and2 native netlists without new solver calls. "+full_text+'\n\n'
        'Unexecuted: full vehicle/reference/hybrid/controller/research cases, autonomous unknown-tool G, paired live PC/browser accuracy/latency and idle-resource H, microphone/approval UI and long overnight/full scientific/release acceptance. No scientific promotion. No commit/push or stable-release tag from mixed work.')

for name in ('PROGRESS.md','ACCEPTANCE_RESULTS.md','INTEGRATION_PLAN.md','NEXT_STEPS.md','MODIFICATIONS.md'):
    extra=''
    if name=='MODIFICATIONS.md':
        extra='\n\nExisting-file modification: app/config/runtime_manifest.json adds only an explicit Phase E harness/output/limit declaration; the existing manifest contract requires it, so a new file alone would not update runtime inventory. Existing Actions/compiler/service/launcher/recovery/flags/requirements were not changed by E. New files: app/jarvis/discovery/acceptance.py, app/benchmarks/live/discovery_lab.py, app/tests/test_discovery_acceptance.py, Phase E evidence/reproduction/export/documentation helpers. Baseline255 → final269 focused passes. Rollback: stop invoking the benchmark, preserve evidence/remote IDs and used grants; no production activation to undo. README/handoff/progress/acceptance/plan/guide/report updated as required.'
    if name in ('NEXT_STEPS.md','INTEGRATION_PLAN.md'):
        extra='\n\nNext action: implement missing A1/A2 vehicle, B reference-reconstruction and C hybrid workflows; extend D/E beyond their bounded subsets, then execute full cases plus G and paired live H with concrete permissions. Keep current proof artifacts and all used slots. Do not reset the Phase E one-shot run or reuse its two-create grant.'
    links='[Case matrix, actual outputs, commands and limits](E_ACCEPTANCE.md) · [Focused receipt](evidence/e-focused-final.json) · [Live bounded audit](evidence/e-local-acceptance.json)'
    if terminal.exists():links+=' · [Terminal comparison](evidence/e-full-final.json)'
    insert(ROOT/'docs/lab'/name,'## Phase E qualification — 2026-11-04 IST\n\n'+common+'\n\n'+links+extra+'\n\nEarlier entries are historical checkpoints, not current full-acceptance claims.')

handoff='## Phase E qualification — 2026-11-04 IST\n\n'+common
handoff+='\n\nBranch lab/phase-e-acceptance; mixed ownership preserved. New oracles and benchmark harness add no runtime neurons. Frozen expanded source: '+summary['source_sha256_after']+'. Harness is separately pinned in e-current-audit/e-local-acceptance because v2 source fingerprints do not include benchmarks/live. Original live oracle hash and current replay hash are both retained. Local dedicated Journal: app/.jarvis-runtime/lab-validation/e-local-2026-11-04; never reset markers. Google deliveries: delivery-dc0e3e7984366c9fce0e4e2b00feff3d44601391e33cf09e233be6b30a52b363 and delivery-3da7c2fc642e689fb66742dd3c2e74839bb78b4ad80d0dae5630085a342c69de; two create slots consumed; inspect known IDs only.\n\n'
handoff+='[Case matrix/reproduction and next work](../../docs/lab/E_ACCEPTANCE.md) · [Google success](../../docs/lab/evidence/e-google-reconciled.json). Next: missing A1/A2/B/C workflows, fuller D/E, then autonomous G and paired live H, without resuming the paused repair campaign. Historical42 defects remain separately recorded. Small oracle runs emitted a post-success pyreadline finalizer warning; receipts/exit codes remain0. No fixes or gate definitions weakened to inflate acceptance.'
insert(ROOT/'app/docs/CLAUDE_HANDOFF.md',handoff)

for name,prefix in (('README.md','docs/lab/'),('app/README.md','../docs/lab/')):
    body=('**Discovery Lab Phase E — 2026-11-04 IST:** acceptance harness implemented with actual bounded clock, native DC circuit and durable pendulum-study checks; approved partial audit Doc/Sheet created and read back. **Full A1–H acceptance is UNMET**, with G/H unmet and D/E/F partial. **269 focused tests pass**; neural typing/readiness pass. '+full_text+' Shipped Lab flags remain off; no new dependencies or services. '
          f'[Case matrix, verified outputs and reproduction]({prefix}E_ACCEPTANCE.md) · [Progress]({prefix}PROGRESS.md). Earlier phase results below are historical.')
    insert(ROOT/name,body)

insert(ROOT/'docs/lab/USER_GUIDE.md','## Phase E evidence audit — 2026-11-04 IST\n\nUse `app/.venv/Scripts/python.exe -B app/benchmarks/live/discovery_lab.py --inspect` from the repository root to audit the dedicated saved Journal. Use `app/.venv/Scripts/python.exe -B docs/lab/reproduce_e.py --verify` to check eight portable outputs and two native netlists without rerunning solvers. These commands grant no installation/model/remote-write permission. `--run-local` is one-shot; never reset its markers. [Current case matrix and output links](E_ACCEPTANCE.md). Full A1–H remains unmet, D/E/F partial, G/H unmet; do not mistake a verified bounded goal for full science acceptance.')
insert(ROOT/'docs/lab/BRAIN_AND_MEMORY_REPORT.md','## Phase E audit scope — 2026-11-04 IST\n\nPhase E adds a benchmark and independent evidence oracles, not a product capability or second router/store. The built-in Lab count remains42 and workflow templates38. Actual D/E/F proof uses existing registered neurons and authoritative Journal/LabMemory; the case matrix reports missing full workflows rather than inventing neurons or promoting evidence. [Scope and current outcomes](E_ACCEPTANCE.md).')
insert(ROOT/'docs/lab/E_ACCEPTANCE.md','## Current terminal verification\n\n'+full_text+'\n\n[Focused receipt](evidence/e-focused-final.json) · [Current frozen-oracle replay](evidence/e-current-audit.json)'+(' · [Terminal exact-ID comparison](evidence/e-full-final.json)' if terminal.exists() else ''))
static={'date_local':'2026-11-04 Asia/Calcutta','source_sha256':summary['source_sha256_after'],'strict_neural_mypy_files':18,'strict_neural_mypy':'passed',
        'read_only_readiness':'ready; no missing/incomplete dependencies/configured services; no live inference/startup',
        'slots':{'scipy':25,'blender':16,'ngspice':39,'limit_each':50,'phase_e_google_creates':2},
        'shipped_lab_flags':'all false','repair_campaign':'PAUSED_BY_USER','new_models_installs_downloads_paid_calls':0}
(PUBLIC/'e-static.json').write_text(json.dumps(static,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'focused':summary['passed'],'full_terminal':terminal.exists(),'phase_e_acceptance':'UNMET','docs_updated':11}))
