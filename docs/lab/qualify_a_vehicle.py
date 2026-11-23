"""Controlled development fixture, NOT an autonomous A1/A2 attempt or asset."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
APP=ROOT/'app'
sys.path.insert(0,str(APP))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',action='store_true');p.add_argument('--attempt',type=int,default=1);p.add_argument('--reproduce',action='store_true');a=p.parse_args()
    if not 1<=a.attempt<=20:raise ValueError('bounded fixture attempt required')
    if not a.run:return print('Explicit --run required; no solver call')
    from tests.test_discovery_vehicle import case
    from jarvis.neural.journal import Journal
    from jarvis.discovery.adapters.chrono import run
    home=APP/f'.jarvis-runtime/lab-validation/a-vehicle-controlled-v{a.attempt}';home.mkdir(parents=True,exist_ok=False)
    (home/'scope.json').write_text(json.dumps({'scope':__doc__,'full_A_acceptance_passed':False}))
    journal=Journal(home/'brain.sqlite3')
    try:
        ref,result=run(case(),journal)
        summary={'controlled_fixture_passed':True,'full_A_acceptance_passed':False,'run_ref':ref,
                 'metrics':{r['variant']:r['metrics'] for r in result['runs']},'checks':result['checks'],
                 'worker_sha256':result['worker_sha256'],'native_project':result['native_project'],'slot':result['slot']}
        if a.reproduce:
            ref2,result2=run(case(),journal)
            if result['native_project']==result2['native_project']:raise ValueError('replication overwrote native artifacts')
            for first,second in zip(result['runs'],result2['runs']):
                for key,value in first['metrics'].items():
                    if abs(second['metrics'][key]-value)>1e-8*max(1,abs(value)):
                        raise ValueError('independent replication differs beyond tolerance')
            summary.update(reproduction_passed=True,reproduction_ref=ref2,reproduction_slot=result2['slot'])
    except Exception as exc:summary={'controlled_fixture_passed':False,'full_A_acceptance_passed':False,'error':type(exc).__name__+': '+str(exc)[:1600]}
    finally:journal.close()
    (home/'result.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))


if __name__=='__main__':main()
