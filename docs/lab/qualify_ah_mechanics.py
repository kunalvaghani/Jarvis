"""Two canonical solver checks, never autonomous A–H case answers.

Runs exactly two approved CPU invocations; failed/uncertain calls remain charged.
"""
import hashlib
import json
import math
from pathlib import Path
import sys

APP=Path(__file__).resolve().parents[2]/'app'
sys.path.insert(0,str(APP))
from jarvis.discovery.adapters.mechanics import run,environment,SETUP
from jarvis.discovery.model.mechanics import MechanicsCase
from jarvis.neural.journal import Journal


def cases():
    body={'id':'mass','parent':None,'position_m':[0,0,2],'shape_center_m':[0,0,0],
          'shape':'sphere','size_m':[.05],'mass_kg':1,'joint':'free','axis':None,
          'initial_position':None,'damping':0,'source_refs':['canonical analytic verification; not hardware']}
    common={'units':'SI','bodies':[body],'gravity_m_s2':[0,0,-9.81],
            'duration_s':.2,'timestep_s':.001,'sample_every':1,
            'assumptions':['vacuum; no contact; explicit analytic golden test, not physical validation']}
    falling=MechanicsCase.model_validate_json(json.dumps(common))
    swinging=MechanicsCase.model_validate_json(json.dumps({**common,'duration_s':6,'sample_every':2,
        'bodies':[{**body,'joint':'hinge','axis':[0,1,0],'initial_position':.03,'shape_center_m':[0,0,-1]}]}))
    return falling,swinging


def main():
    root=APP/'.jarvis-runtime/lab-validation'
    with_journal=Journal(root/'ah-mechanics-golden.sqlite3')
    results=[]
    try:
        for index,case in enumerate(cases()):
            ref,report=run(case,journal=with_journal)
            rows=report['samples']
            if index==0:
                errors=[abs(row['positions_m']['mass'][2]-(2-9.81*row['t_s']**2/2)) for row in rows]
                maximum=max(errors)
                if maximum>1e-9:raise ValueError('free-fall analytic position mismatch')
                if abs(rows[-1]['qvel'][2]+9.81*case.duration_s)>1e-9:raise ValueError('free-fall velocity mismatch')
                metric={'max_position_error_m':maximum}
            else:
                crossings=[]
                for a,b in zip(rows,rows[1:]):
                    if a['qpos'][0]>=0>b['qpos'][0]:
                        crossings.append(a['t_s']+(b['t_s']-a['t_s'])*a['qpos'][0]/(a['qpos'][0]-b['qpos'][0]))
                if len(crossings)<3:raise ValueError('insufficient pendulum crossings')
                measured=sum(b-a for a,b in zip(crossings,crossings[1:]))/(len(crossings)-1)
                # First nonlinear correction keeps this check independent of the numerical solver.
                expected=2*math.pi*math.sqrt((1+.4*.05**2)/9.81)*(1+.03**2/16)
                error=abs(measured/expected-1)
                if error>1e-6:raise ValueError('pendulum analytic period mismatch')
                metric={'period_s':measured,'analytic_period_s':expected,'relative_error':error}
            results.append({'case':['analytic-free-fall','rigid-sphere-pendulum'][index],
                'passed':True,'run_ref':ref,'slot':report['slot'],'metrics':metric})
        proof={'worker_sha256':environment()['worker_sha256'],'solver':'mujoco','version':'3.17.0',
               'goldens':results,'physical_validation':False,'scope':'canonical numerical verification only'}
        path=SETUP/('golden-'+proof['worker_sha256']+'.json')
        with path.open('x',encoding='utf-8') as stream:json.dump(proof,stream,indent=2)
        print(json.dumps(proof,indent=2))
    finally:with_journal.close()


if __name__=='__main__':main()
