"""Read-only Phase E evidence oracles. No executor, router, score overrides or promotion.

Full acceptance is deliberately stricter than a verified bounded demonstration.
Unimplemented scenarios cannot earn points from a transport/registry check.
"""
from __future__ import annotations
import hashlib
import json

CASES = {
    'A1': 'Licensed 2025 F1 acquisition, editable vehicle, Chrono handling/aero comparison',
    'A2': '2026 identity plus two-state front/rear active aero and zone-driven control',
    'B': 'Lawful multi-view reconstruction, scale checks, native source and load simulation',
    'C': 'Sourced real modules, new folding mechanism and isolated levitation hypothesis',
    'D': 'Cited time-travel survey, competing branches, conditional verified numerical visualization',
    'E': 'Sourced controller circuit/logic, native connectivity, changed-condition functional checks',
    'F': 'Bounded improvement, fixed scenario, rejection history, process interruption/resume and approval limit',
    'G': 'Unknown tool learned autonomously, golden-gated registration and faster fresh-session reuse',
    'H': 'Current flags-on/off regressions, paired live control accuracy/latency and idle resource checks',
}
GAPS = {
    'A1': 'Conditional class-surrogate Chrono workflow exists; full acquired-asset mechanical binding, eight independent maneuvers and autonomous live acceptance remain unmet.',
    'A2': 'Conditional two-state zone-driven active aero exists; full acquired-2026-asset identity, mechanical binding, eight maneuvers and autonomous live acceptance remain unmet.',
    'B': 'Only authored ideal-pendulum geometry exists; reference-driven reconstruction case not executed.',
    'C': 'No sourced flying-car assembly/propulsion/folding-wing workflow; case not executed.',
    'D': 'Conditional SR clocks are a subset; full cited forward/backward survey and theory visualization remain unmet.',
    'E': 'Ideal DC divider is a subset; sourced controller/HDL, ERC/testbench and temperature-dependent models remain unmet.',
    'F': 'Local bounded study evidence does not establish arbitrary autonomous design optimization or live approval UI.',
    'G': 'Earlier reviewed installed-tool qualification is operator-assisted; autonomous unknown-tool acquisition remains unmet.',
    'H': 'Guarded regressions alone do not establish paired live PC/browser accuracy/latency or measured idle VRAM.',
}
WEIGHTS = {'classification':15,'provenance':10,'editable_geometry':15,'appropriate_solver':20,
           'numerical_verification':15,'parameter_control':10,'bounded_autonomy':10,'durability_regressions':5}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def artifact(journal, ref):
    from ..neural.contracts import artifact_ref
    if not isinstance(ref,str) or not ref.startswith('artifact://sha256/'):
        raise ValueError('Journal artifact reference required')
    text=journal.get(ref)
    if text is None or ref!=artifact_ref(text):
        raise ValueError('artifact bytes differ from content address')
    return json.loads(text)


def trace(journal, goal_id, producer, verifier):
    """Require the real compiled plan, fired/succeeded nodes and independent verdict.

    This is an audit of trusted local Journal records, not an authenticity claim
    against an attacker who controls both code and the SQLite database.
    """
    goal=journal.goal(goal_id)
    if not goal or goal['state']!='verified':raise ValueError('independently verified goal required')
    plan=json.loads(goal['plan']);steps={s['step_id']:s for s in plan['steps']}
    check=steps[plan['goal_verifier']]
    if check['neuron']!=verifier or producer==verifier:raise ValueError('wrong independent verifier')
    producers=[s for s in steps.values() if s['neuron']==producer]
    if len(producers)!=1:raise ValueError('unambiguous producer required')
    binding=check['bind'].get('report',{})
    if binding.get('step')!=producers[0]['step_id'] or binding.get('port')!='report':
        raise ValueError('verifier not bound to executed producer report')
    signals=journal.signals(goal_id,limit=500)
    if len(signals)>=500:raise ValueError('trace is incomplete')
    reports={}
    for node,port in ((producer,'report'),(verifier,'verdict')):
        if not any(s['type']=='neuron.fired' and s.get('target_node')==node for s in signals):
            raise ValueError('node never fired')
        if not any(s['type']=='neuron.succeeded' and s.get('source_node')==node for s in signals):
            raise ValueError('node never completed')
        rows=journal.rows('SELECT state,result_ref FROM outbox WHERE goal_id=? AND node_id=?',(goal_id,node))
        if len(rows)!=1 or rows[0]['state']!='done':raise ValueError('completed actual adapter outbox required')
        if not any(s['type']=='neuron.succeeded' and s.get('source_node')==node and s.get('payload_ref')==rows[0]['result_ref'] for s in signals):
            raise ValueError('completion signal differs from adapter outbox')
        packet=artifact(journal,rows[0]['result_ref']);reports[port]=artifact(journal,packet[port])
    if reports['verdict'].get('passed') is not True:raise ValueError('verdict did not pass')
    request=artifact(journal,producers[0]['bind']['request']['const'])
    return {'goal_id':goal_id,'request':goal['text'],'request_input':request,'neuron_path':[s['target_node'] for s in signals if s['type']=='neuron.fired'],
            'report':reports['report'],'verdict':reports['verdict'],'operator_assisted':True,'microphone_used':False}


def clocks(journal, goal_ids, base):
    from .model.relativity import ClockCase,calculate
    from .adapters.assets import local_bytes
    rows=[]
    for identity in goal_ids:
        row=trace(journal,identity,'discovery.theory.dilation@v1','discovery.verify.dilation@v1')
        report=row['report'];result=artifact(journal,report['run_ref'])
        raw=local_bytes(base,row['request_input']['value'],limit=16000)
        if sha(raw)!=result['input_sha256'] or ClockCase.model_validate_json(raw).model_dump(mode='json')!=result['inputs']:
            raise ValueError('clock source changed')
        if report['result']!=result:raise ValueError('clock result differs from actual artifact')
        if not journal.rows('SELECT ref FROM discovery_theory_runs WHERE ref=?',(report['run_ref'],)):
            raise ValueError('actual theory receipt required')
        expected=calculate(ClockCase.model_validate(result['inputs']))
        if {k:v for k,v in result.items() if k!='input_sha256'}!=expected:raise ValueError('clock independent replay differs')
        rows.append({**row,'result':result})
    if len(rows)!=3 or len(set(goal_ids))!=3 or [r['result']['inputs']['beta'] for r in rows]!=[0,.6,.8]:
        raise ValueError('distinct baseline and two changed-speed cases required')
    if len({r['result']['inputs']['coordinate_time_s'] for r in rows})!=1:raise ValueError('clock interval changed')
    return {'status':'PASSED_SUBCHECK','scope':'Conditional flat-spacetime SR only; full D remains unmet','runs':rows}


def circuit(journal, goal_ids):
    from .adapters.divider import DividerInput,DividerVectors,verify,netlist
    from .adapters.ngspice import environment,IMAGE
    state=environment()
    if not state['ready']:raise ValueError('reviewed ngspice environment changed')
    rows=[]
    for identity in goal_ids:
        row=trace(journal,identity,'discovery.electronics.divider@v1','discovery.verify.divider@v1')
        report=row['report'];result=artifact(journal,report['solver_ref'])
        if row['request_input']!=result['input']:raise ValueError('circuit request changed')
        if {k:v for k,v in report.items() if k not in ('solver_ref','request_digest')}!=result:
            raise ValueError('divider report differs from actual artifact')
        receipts=journal.rows('SELECT worker_sha256,image_id FROM discovery_solver_runs WHERE ref=?',(report['solver_ref'],))
        if len(receipts)!=1 or receipts[0]!=dict(worker_sha256=state['worker_sha256'],image_id=IMAGE):
            raise ValueError('actual current sandbox receipt required')
        spec=DividerInput.model_validate(result['input']);checked=verify(spec,DividerVectors.model_validate(result['vectors']))
        if not checked.passed or checked.netlist_sha256!=result['netlist_sha256']:raise ValueError('independent circuit oracle failed')
        rows.append({**row,'result':result,'native_netlist':netlist(spec)})
    if len(rows)!=2 or len(set(goal_ids))!=2:raise ValueError('two distinct circuit trials required')
    left,right=[r['result'] for r in rows]
    if left['input']!={'supply_v':5.0,'upper_ohm':1000.0,'lower_ohm':1000.0} or right['input']!={**left['input'],'supply_v':9.0}:
        raise ValueError('fixed-resistor changed-voltage cases differ')
    return {'status':'PASSED_SUBCHECK','scope':'Ideal DC resistors only; no temperature/logic/controller claim','runs':rows}


def optimization(journal, goal_id, first_ref, crash_exit, queue_states):
    from .model.optimization import Studies
    row=trace(journal,goal_id,'discovery.optimization.advance@v1','discovery.verify.optimization@v1')
    report=row['report'];actual=artifact(journal,report['receipt_ref'])
    if actual!=report['result']:raise ValueError('optimization receipt differs')
    studies=Studies.__new__(Studies);studies.j=journal
    expected=studies.describe(actual['study_id'])
    if actual!=expected or len(actual['trials'])!=3 or actual['trials'][0]['run_ref']!=first_ref:
        raise ValueError('study replay or preserved baseline differs')
    if crash_exit!=23 or queue_states!=['COMPLETED']*3:raise ValueError('owned child interruption/queue completion not evidenced')
    if not actual['objective_met'] or actual['best']['error_s']>=actual['baseline_error_s']:
        raise ValueError('no bounded improvement')
    if not any(t.get('decision')=='REJECTED_CONSTRAINT' for t in actual['trials']):raise ValueError('constraint rejection not retained')
    if actual['physical_validation'] is not False:raise ValueError('physical proof claim forbidden')
    return {'status':'PASSED_SUBCHECK','scope':'Actual bounded ideal-pendulum study and owned child restart only','trace':row,'result':actual}


def catalogue(subchecks):
    """Fixed full-case omissions cannot be overridden by user-supplied pass flags."""
    unknown=set(subchecks)-{'D','E','F'}
    if unknown:raise ValueError('no implemented oracle for supplied case')
    cases=[]
    for key,requirement in CASES.items():
        support=subchecks.get(key)
        if support is not None and support.get('status') not in ('PASSED_SUBCHECK','FAILED'):
            raise ValueError('explicit bounded oracle outcome required')
        status=('FAILED' if support['status']=='FAILED' else 'PARTIAL') if support else 'UNMET'
        cases.append({'case':key,'requirement':requirement,'status':status,
                      'reason':GAPS[key],'subcheck':support})
    return {'cases':cases,'full_acceptance_passed':False,'mandatory_gates':{'G':'UNMET','H':'UNMET'},
            'certified_full_acceptance_score':0,'possible_points':sum(WEIGHTS.values()),'rubric_weights':WEIGHTS,
            'score_policy':'Zero full-acceptance points certified. Bounded subchecks do not substitute for full A1-F evidence; G/H are separate mandatory gates.',
            'scientific_or_release_acceptance':False}


def verify_regression(current, baseline):
    if current['source_sha256_before']!=current['source_sha256_after'] or current['errors'] or current['collection_errors']:
        raise ValueError('incomplete/source-changing regression')
    failures={r['test'] for r in current['reports'] if r['outcome']=='failed'}
    if sum(r['outcome']=='failed' for r in current['reports'])!=current['failed']:
        raise ValueError('regression failure count differs from actual reports')
    prior=set(baseline['remaining_failure_ids'])
    return {'new_failure_ids':sorted(failures-prior),'resolved_failure_ids':sorted(prior-failures),
            'remaining_failure_ids':sorted(failures),'passed':current['passed'],'failed':current['failed'],'skipped':current['skipped'],
            'H_passed':False,'scope':'guarded regression only; no paired live control or idle-resource proof'}
