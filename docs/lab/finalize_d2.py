"""Publish bounded local D2 evidence and dated documentation, with no service calls."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
PRIVATE=ROOT/'app/.jarvis-runtime/lab-validation'
PUBLIC=ROOT/'docs/lab/evidence'
KEYS=('date_local','passed','failed','skipped','errors','collection_errors','exit_code','seconds',
      'source_sha256_before','source_sha256_after','fingerprint_scheme','isolation','output_policy')

def publish(name):
    result=json.loads((PRIVATE/name).read_text(encoding='utf-8'))
    out={k:result[k] for k in KEYS if k in result}
    assert out['source_sha256_before']==out['source_sha256_after'], 'source changed during checks'
    return result,out

focused,summary=publish('d2-final-focused-frozen.json')
assert summary['passed']==255 and not summary['failed'] and not summary['errors']
(PUBLIC/'d2-final-focused.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
static={'date_local':'2026-11-04 Asia/Calcutta','neural_mypy':{'passed':True,'files':18,'command':'app/.venv/Scripts/python.exe -B -m mypy --config-file mypy.ini jarvis/neural (cwd app)'},
        'readiness':{'status':'ready','scope':'dependencies_and_configured_services','missing':[],'incomplete':[],
                     'live_inference_checked':False,'services_started':False},
        'cpu_choice_readback':{'selected_ref':'red','confidence':0.9848,'method':'existing local Laya; no cloud backup; abstains below threshold',
                               'attempts':1,'cpu_admission_units_retained':5,'C3_scratch_calls':0},
        'source_sha256':summary['source_sha256_after']}
(PUBLIC/'d2-static-and-choice.json').write_text(json.dumps(static,indent=2)+'\n',encoding='utf-8')

terminal=PRIVATE/'d2-full-final.json'
full_text='The frozen-source whole-project regression is running; its terminal result and exact-ID comparison are pending.'
if terminal.exists():
    full,out=publish(terminal.name)
    assert out['source_sha256_after']==summary['source_sha256_after'], 'focused/full source differs'
    baseline=json.loads((PUBLIC/'d-full-final.json').read_text(encoding='utf-8'))
    prior=set(baseline['remaining_failure_ids'])
    failures={r['test'] for r in full['reports'] if r['outcome']=='failed'}
    out.update(new_failure_ids=sorted(failures-prior),resolved_failure_ids=sorted(prior-failures),
               remaining_failure_ids=sorted(failures),discovery_failure_ids=sorted(x for x in failures if 'test_discovery_' in x))
    (PUBLIC/'d2-full-final.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
    full_text=(f"Final frozen-source whole-project regression: **{out['passed']:,} passed / {out['failed']} failed / {out['skipped']} skipped**, "
               f"{out['seconds']:.3f} s including setup; {len(out['new_failure_ids'])} new failure IDs, "
               f"{len(out['resolved_failure_ids'])} resolved IDs and {len(out['discovery_failure_ids'])} Discovery failures against the pre-D2 baseline. "
               "The exact failure comparison and unchanged source hashes are retained in the terminal receipt. This does not make the pre-existing defects green.")

common=("D2 adds15 explicit existing-service adapters, bringing the built-in Lab inventory to42. It reuses Google Files, owned extension sessions, scouts, public search, already-resident CPU Laya and the durable C4 queue; no second brain/store/router/queue or new dependency. "
        "The approved Doc and Sheet are created and fully read back; both create slots are consumed. Actual Drive source, scoped long-read, corrected public portal cleanup and CPU choice pass through final-text brain ingress. "
        "Initial Doc paragraph mismatch and portal credential-guard refusal remain in history; fixes use known-ID reconciliation and unchanged safe-line extraction, without duplicate creation or weakening the guard. "
        "No microphone was used. No install/download, paid use, global activation or shared-service change. Shipped flagsfalse, act/learning-shadow/legacy control and PAUSED_BY_USER repair state remain unchanged.\n\n"
        f"Final focused checks: **255 passed / zero failures/skips**, {summary['seconds']:.3f} s including setup, unchanged expanded source fingerprint. Domain/wiring47 passes; strict neural mypy18 files and actual read-only host readiness pass. "+full_text+"\n\n"
        "Open gates: live microphone/spoken and approval UI, authenticated scientific portals, long overnight behavior, prior42 defects, G/H and live PC/browser accuracy/latency, full A–H/scientific/release and physical validation. No scientific promotion is implied. Free-local counters remain SciPy22/50, Blender16/50, ngspice37/50. C3 scratch grants stay exhausted. No commit/push from mixed work.")

def insert_after_title(path,block):
    text=path.read_text(encoding='utf-8-sig')
    start='<!-- D2 CURRENT BEGIN -->';end='<!-- D2 CURRENT END -->'
    if start in text:
        first,tail=text.split(start,1);text=first+tail.split(end,1)[1].lstrip('\n')
    title,rest=text.split('\n',1)
    path.write_text(title+'\n\n'+start+'\n'+block+'\n'+end+'\n\n'+rest.lstrip('\n'),encoding='utf-8')

for name in ('PROGRESS.md','ACCEPTANCE_RESULTS.md','INTEGRATION_PLAN.md','NEXT_STEPS.md','MODIFICATIONS.md'):
    links='[D2 scope, commands and evidence](D2_SERVICES.md) · [Focused receipt](evidence/d2-final-focused.json)'
    if terminal.exists():links+=' · [Terminal comparison](evidence/d2-full-final.json)'
    extra=''
    if name=='MODIFICATIONS.md':
        extra='\n\nNew modules: discovery/d2.py, model/delivery.py, adapters/delivery.py, lab_reads.py, lab_jobs.py; new test_discovery_delivery.py, service skill and request examples. Existing seams: Actions routing/refusal/preview, neural service/compiler composition, owned descriptor/wiring inventory and count expectations, runtime manifest. Existing application/launcher/recovery entrypoints remain compatible; no shipped activation. All earlier mixed edits retained.'
    if name=='NEXT_STEPS.md':
        extra='\n\nNext action: arrange separately scoped live spoken/approval-UI and signed-portal/long-run qualification after the terminal comparison. Retain both external file IDs and used create grants; read-only reconciliation only under the consumed two-create grant. Do not restart paused repair trials or reset any quota.'
    insert_after_title(ROOT/'docs/lab'/name,'## Current D2 adapters — 2026-11-04 IST\n\n'+common+'\n\n'+links+extra+'\n\nEarlier entries below are historical checkpoints; their counts/open-D2 statements describe that earlier source.')

handoff='## D2 existing-service adapters — 2026-11-04 IST\n\n'+common
handoff+='\n\nBranch lab/phase-d2-adapters preserves mixed earlier work. Source fingerprint: '+summary['source_sha256_after']+'. Approval grants and private goals remain in app/.jarvis-runtime/lab-validation/d2-live-root. Two creates consumed: report delivery-aaa68516f2dc8ab6353774c12f7a9aa7d84fb5285e8b58c8a3a2039f4ef8c7b0 and table delivery-00a0b563f8d6b217e91c0e434a5754006a9b9a1b5e1d880acd335f4018dd5935. Never recreate them.\n\n'
handoff+='[D2 scope/use/remaining gates](../../docs/lab/D2_SERVICES.md) · [Google receipt](../../docs/lab/evidence/d2-google-live.json) · [Corrected portal receipt](../../docs/lab/evidence/d2-portal-corrected.json). Next action: scoped live microphone/approval-UI, authenticated portal and durable long-run acceptance after terminal comparison; keep pre-existing defects separate. Earlier phase entries are historical.'
insert_after_title(ROOT/'app/docs/CLAUDE_HANDOFF.md',handoff)

for relative,prefix in (('README.md','docs/lab/'),('app/README.md','../docs/lab/')):
    readme=('**Discovery Lab D2 — 2026-11-04 IST:** 15 new typed service neurons (42 built-in total) reuse existing Google Files, owned browser reads, scouts, local CPU choice and durable jobs. Approved Doc/Sheet creation and full readback pass; scoped long reading, corrected public portal reading and resident CPU choice also pass through final-text brain ingress. **255 focused tests pass**, neural typing/readiness pass. '+full_text+' Shipped Lab flags remain off; microphone/approval-UI, signed-portal/overnight and full scientific/release gates remain open. '
            f'[D2 usage, verified outputs and limits]({prefix}D2_SERVICES.md) · [Progress]({prefix}PROGRESS.md). Earlier phase entries below are historical.')
    insert_after_title(ROOT/relative,readme)

report=ROOT/'docs/lab/D2_SERVICES.md'
insert_after_title(report,'## Current terminal status\n\n'+full_text+f"\n\nFocused:255 passed, {summary['seconds']:.3f} s including setup; source `{summary['source_sha256_after']}`. [Focused receipt](evidence/d2-final-focused.json) · [Static/choice evidence](evidence/d2-static-and-choice.json)"+(' · [Terminal comparison](evidence/d2-full-final.json)' if terminal.exists() else ''))
print(json.dumps({'focused':summary['passed'],'full_terminal':terminal.exists(),'docs_updated':9}))
