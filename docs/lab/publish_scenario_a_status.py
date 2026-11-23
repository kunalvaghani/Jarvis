"""Refresh dated documentation from actual receipts, preserving historical blocks."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
PUBLIC=ROOT/'docs/lab/evidence'


def block(path,text,marker='SCENARIO A WORKFLOW'):
    raw=path.read_text(encoding='utf-8');start=f'<!-- {marker} BEGIN -->';end=f'<!-- {marker} END -->'
    value=start+'\n'+text.strip()+'\n'+end
    if start in raw:
        a=raw.index(start);b=raw.index(end,a)+len(end);raw=raw[:a]+value+raw[b:]
    else:
        head,sep,body=raw.partition('\n');raw=head+'\n\n'+value+'\n'+body
    path.write_text(raw,encoding='utf-8')


def main():
    cases=[json.loads((PUBLIC/f'scenario-{case}-attempt-{attempt}-audit.json').read_text(encoding='utf-8')) for case,attempt in [('a1',19),('a2',5)]]
    resume_path=PUBLIC/'scenario-a1-attempt-20-audit.json'
    resume=json.loads(resume_path.read_text(encoding='utf-8')) if resume_path.exists() else None
    regression_path=PUBLIC/'scenario-a-final-regression.json'
    regression=json.loads(regression_path.read_text(encoding='utf-8')) if regression_path.exists() else None
    checks=(f"Full guarded regression: **{regression['passed']:,} passed / {regression['failed']} failed / {regression['skipped']} skipped**; source stable."
        if regression else '**Current whole-project regression is still running; no terminal full-regression claim.**')
    reused=(f"Fresh-process A1 reuse passed in {resume['seconds']:.3f}s, zero model calls and no new solver slots ({resume['chrono_slots_before']}→{resume['chrono_slots_after']})."
        if resume else 'Fresh-process corrected A1 reuse is awaiting its independent audit.')
    for name,prefix in [('README.md','docs/lab/'),('app/README.md','../docs/lab/'),('app/docs/CLAUDE_HANDOFF.md','../../docs/lab/'),
                         ('docs/lab/PROGRESS.md',''),('docs/lab/MODIFICATIONS.md',''),('docs/lab/INTEGRATION_PLAN.md',''),('docs/lab/A_ACCEPTANCE.md','')]:
        value=f'''**Scenario A workflow repair — 6 November 2026 IST.** Corrected A1 (2025) and A2 (2026) pass the assignment's explicitly permitted **conditional F1-class surrogate** scope in {cases[0]['seconds']:.3f}s / {cases[1]['seconds']:.3f}s. Both traverse 13 independently checked stages through the existing brain/Journal, call real CPU Chrono::Vehicle and require zero model calls or operator engineering inputs. Exact team CAD, physical validation and original full A remain unmet.

{checks} Strict configured typing passes 79 files; read-only readiness reports ready. {reused} Shipped Lab flags remain false; Chrono 27/50, other grants unchanged; the old repair campaign remains paused. No installs, paid usage, service starts, account writes or shared-model/quota changes.

The first A1 pass was withdrawn after final evidence inspection caught a 2026 regulation whose publication date contained 2025. Index/PDF season checks now distinguish regulation identity from publication/copyright dates, with an adversarial regression test. Failed and superseded receipts remain intact. [Correction record]({prefix}evidence/scenario-a-season-correction.json).

[Architecture, exact inputs, current audits, native outputs and limitations]({prefix}SCENARIO_A_WORKFLOW.md). Remaining: authenticated engineering asset import/reference reconstruction, calibration/real validation, general unknown-tool learning G and paired live control/resource H acceptance. Current fixed routine emits stage progress, rechecks saved evidence, bounds read retries and blocks uncertain writes; it does not implement arbitrary self-modifying repairs.'''
        if name=='app/README.md':
            value+=f'\n\nActual generated envelope mesh diagnostic (not a screenshot or exact team CAD); native templates retain their Chrono BSD attribution.\n\n![Jarvis-generated 2025 class surrogate mesh diagnostic]({prefix}evidence/scenario-a-corrected-2026-11-06/A1/side.png)'
        block(ROOT/name,value)
    path=ROOT/'docs/lab/SCENARIO_A_WORKFLOW.md';raw=path.read_text(encoding='utf-8')
    start=raw.index('## Verification status');end=raw.index('Primary implementation references:',start)
    text='## Verification status — corrected source\n\n'+checks+' '+reused+' Strict configured typing: 79 files. Read-only readiness: ready, no service starts.\n\n'
    text+='The source-selection defect and withdrawn A1 evidence are retained in the [correction record](evidence/scenario-a-season-correction.json). Final source: `'+cases[0]['source_sha256']+'`. The earlier interrupted full run is not certified.\n\n'
    text+='| Case | Independent status | Duration | Model calls | Solver slots | Source edition |\n|---|---|---:|---:|---|---|\n'
    for case,attempt in zip(cases,[19,5]):
        text+=f"| [{case['case']}](evidence/scenario-{case['case'].lower()}-attempt-{attempt}-audit.json) | Conditional surrogate pass | {case['seconds']:.3f}s | {case['model_calls']} | {case['chrono_slots_before']}→{case['chrono_slots_after']} | {case['regulation']['publication_date']}, issue {case['regulation']['edition']} |\n"
    text+='\nEach audit retains the exact submitted input, stage timings, actual solver identity/worker hash, source URL/hash, generated-vs-acquired parts, numerical checks and output hashes. Both generated 11 separated visual components and native physical JSON; neither acquired an engineering asset. No prepared asset IDs, URLs, JSON, physics numbers or code were supplied during execution.\n\n'
    text+='| Case | Maximum observed speed, baseline → candidate (m/s) | Maximum lateral acceleration (m/s²) | Shaft work (J) | Max joint residual | Max timestep metric error |\n|---|---|---|---|---|---|\n'
    for case in cases:
        a,b=case['metrics']['baseline'],case['metrics']['candidate'];p=case['physics'];fmt=lambda k:f'{a[k]:.6f} → {b[k]:.6f}'
        text+=f"| {case['case']} | {fmt('maximum_observed_speed_m_s')} | {fmt('maximum_observed_lateral_acceleration_m_s2')} | {fmt('mechanical_engine_energy_j')} | {p['maximum_constraint_residual']:.8f} | {max(p['timestep_metric_relative_errors'].values()):.4%} |\n"
    text+='\nJoint residuals use mixed Chrono generalized coordinates. Deltas are small relative to numerical/input uncertainty; they do not establish a real performance improvement. Full precision, parameter intervals and aero-envelope results remain in each actual report. Cross-year performance is not a controlled isolation of regulations: dimensions and declared season models differ.\n\n'
    for case in cases:
        c=case['case'];base=f'evidence/scenario-a-corrected-2026-11-06/{c}'
        text+=f"{c}: [actual report]({base}/report.md), [native/visual artifact hashes]({base}/bundle_manifest.json), [solver inputs]({base}/solver_configuration.json), [raw CSV]({base}/raw_output.csv), [physical model]({base}/physical_model.json), [Chrono license]({base}/LICENSE-CHRONO.txt).\n\n"
    text+='Actual Jarvis-generated 2026 numerical diagnostic, driven by recorded solver traces (not a screenshot or physical validation):\n\n![Actual 2026 baseline/candidate trace diagnostic](evidence/scenario-a-corrected-2026-11-06/A2/dynamics.png)\n\n'
    text+='The deterministic route supports a single season, standard road scenario and explicit numeric degree deltas. Unsupported custom environment, named-track, radian or word-valued parameter requests stay with the general brain instead of silently using default constraints. Aero modes switch coefficients instantaneously; actuator travel/lag/energy is not modeled. There is no full animation/workbench or photo reconstruction claim.\n\n'
    text+='Recovery tests cover bounded failed reads, corrupt artifacts, invalid native physics, missing provenance, false completion and uncertain writes without replay. Fresh-process reuse revalidates the retained Journal/files; it is not a new solver result. All A–H, microphone/GUI, production and physical validation remain outside this proof. Shared CPU and invocation limits still stop additional work when exhausted.\n\n'
    path.write_text(raw[:start]+text+raw[end:],encoding='utf-8')
    status=PUBLIC/'a-live-status.json';data=json.loads(status.read_text(encoding='utf-8'));data['current_workflow']={'date':'2026-11-06','scope':'Conditional surrogate only; original full A unmet',
        'A1':'scenario-a1-attempt-19-audit.json','A2':'scenario-a2-attempt-5-audit.json','correction':'scenario-a-season-correction.json','full_A_passed':False}
    status.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
