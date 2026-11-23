"""Capture/audit actual Phase E outputs without running solvers, models or remote APIs.

--capture reads only the dedicated qualification Journal/owned synthetic inputs.
--verify audits the portable evidence pack. It cannot authenticate execution on
another machine without the original Journal/receipts and is not a live rerun.
"""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];APP=ROOT/'app';sys.path.insert(0,str(APP))
PUBLIC=ROOT/'docs/lab/evidence';HOME=APP/'.jarvis-runtime/lab-validation/e-local-2026-11-04'

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--capture',action='store_true');parser.add_argument('--verify',action='store_true');args=parser.parse_args()
    from jarvis.discovery.acceptance import sha
    from jarvis.neural.contracts import artifact_ref
    assessment=json.loads((PUBLIC/'e-local-acceptance.json').read_text())
    subsets={r['case']:r['subcheck'] for r in assessment['cases'] if r['subcheck']}
    target=PUBLIC/'e-portable-outputs.json'
    if args.capture:
        from jarvis.neural.journal import Journal
        journal=Journal(HOME/'brain.sqlite3')
        try:
            refs=[r['report']['run_ref'] for r in subsets['D']['runs']]+[r['report']['solver_ref'] for r in subsets['E']['runs']]+[r['run_ref'] for r in subsets['F']['result']['trials']]
            rows=[]
            for ref in refs:
                raw=journal.get(ref)
                if artifact_ref(raw)!=ref:raise ValueError('actual raw artifact hash differs')
                rows.append({'ref':ref,'raw_utf8':raw,'byte_sha256':sha(raw.encode())})
            inputs={p.name:json.loads(p.read_text()) for p in [HOME/'study.json',HOME/'clock-0.json',HOME/'clock-1.json',HOME/'clock-2.json']}
            result={'date_local':'2026-11-04 Asia/Calcutta','scope':'Portable raw outputs/inputs, no live execution or scientific promotion',
                'assessment_byte_sha256':sha((PUBLIC/'e-local-acceptance.json').read_bytes()),'artifacts':rows,'inputs':inputs}
            with target.open('x',encoding='utf-8') as handle:json.dump(result,handle,indent=2,allow_nan=False)
            for index,row in enumerate(subsets['E']['runs']):
                with (PUBLIC/('e-divider-'+str(index)+'.cir')).open('x',encoding='ascii',newline='\n') as handle:handle.write(row['native_netlist'])
        finally:journal.close()
    if not (args.capture or args.verify):parser.error('choose --capture or --verify')
    pack=json.loads(target.read_text())
    if pack['assessment_byte_sha256']!=sha((PUBLIC/'e-local-acceptance.json').read_bytes()):raise ValueError('assessment bytes changed')
    raw={}
    for item in pack['artifacts']:
        if artifact_ref(item['raw_utf8'])!=item['ref'] or sha(item['raw_utf8'].encode())!=item['byte_sha256']:
            raise ValueError('portable output bytes changed')
        if item['ref'] in raw:raise ValueError('duplicate artifact')
        raw[item['ref']]=json.loads(item['raw_utf8'])
    from jarvis.discovery.model.relativity import ClockCase,calculate
    for index,row in enumerate(subsets['D']['runs']):
        result=raw[row['report']['run_ref']];expected=calculate(ClockCase.model_validate(pack['inputs']['clock-'+str(index)+'.json']))
        if {k:v for k,v in result.items() if k!='input_sha256'}!=expected:raise ValueError('clock analytic replay failed')
    from jarvis.discovery.adapters.divider import DividerInput,DividerVectors,verify,netlist
    for index,row in enumerate(subsets['E']['runs']):
        result=raw[row['report']['solver_ref']];spec=DividerInput.model_validate(result['input'])
        if not verify(spec,DividerVectors.model_validate(result['vectors'])).passed:raise ValueError('circuit independent oracle failed')
        # Initial Windows capture used CRLF; normalize line endings only and
        # compare every complete line with the solver's canonical LF netlist.
        if (PUBLIC/('e-divider-'+str(index)+'.cir')).read_text(encoding='ascii')!=netlist(spec):raise ValueError('native netlist changed')
    from jarvis.discovery.model.pendulum import Pendulum,independent_checks,compare_runs
    from jarvis.discovery.model.optimization import Study,candidates
    study=Study.model_validate(pack['inputs']['study.json']);baseline=None
    for trial in subsets['F']['result']['trials']:
        result=raw[trial['run_ref']];spec=Pendulum.model_validate(result['model']);independent_checks(spec,result)
        expected={**study.baseline.model_dump(),'length_m':candidates(study)[trial['number']]}
        if spec.model_dump()!=expected:raise ValueError('study design/scenario changed')
        if baseline is None:baseline=result
        else:compare_runs(baseline,result)
    outcome={'date_local':'2026-11-04 Asia/Calcutta','portable_artifacts_verified':len(raw),'native_netlists_verified':2,
             'new_solver_model_or_remote_calls':0,'full_acceptance_passed':False,'scope':'captured-output audit, not a live rerun'}
    print(json.dumps(outcome))

if __name__=='__main__':main()
