"""Bounded rigid pendulum using installed SciPy, with independent credibility checks.

Uniform solid sphere on an ideal massless rigid connector, one revolute DOF.
No fluid drag, flexible-body stress, contact, motor, thermal or material model.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from typing import Literal
from pydantic import Field, model_validator
from jarvis.discovery.contracts import Finite, Identifier, StrictModel


class Pendulum(StrictModel):
    project_id: Identifier = 'pendulum-demo'
    length_m: Finite = Field(default=1.0, ge=0.1, le=5.0)
    radius_m: Finite = Field(default=0.05, ge=0.005, le=0.2)
    mass_kg: Finite = Field(default=1.0, ge=0.01, le=20)
    gravity_m_s2: Finite = Field(default=9.81, ge=0.1, le=20)
    damping_nm_s: Finite = Field(default=0.0, ge=0, le=1)
    initial_angle_rad: Finite = Field(default=0.2, ge=-0.8, le=0.8)
    duration_s: Finite = Field(default=8.0, ge=2, le=20)
    dt_s: Literal[0.01, 0.02, 0.04, 0.05, 0.1] = 0.02

    @model_validator(mode='after')
    def resolved(self):
        if self.radius_m > self.length_m/5:
            raise ValueError('bob radius exceeds this adapter geometry domain')
        period = 2*math.pi*math.sqrt((self.length_m**2+0.4*self.radius_m**2)/(self.gravity_m_s2*self.length_m))
        if self.dt_s > period/40 or abs(self.duration_s/self.dt_s-round(self.duration_s/self.dt_s))>1e-8:
            raise ValueError('time grid must resolve at least 40 samples per small-angle cycle and have a whole sample count')
        return self


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def design(spec):
    return {name:getattr(spec,name) for name in ('length_m','radius_m','mass_kg','damping_nm_s')}


def scenario(spec):
    return {name:getattr(spec,name) for name in ('gravity_m_s2','initial_angle_rad','duration_s','dt_s')}


def independent_checks(spec: Pendulum, result):
    """Check equations, energy, units/geometry and an independent elliptic-period reference."""
    from scipy.special import ellipk
    samples=result['samples'];I=spec.mass_kg*(spec.length_m**2+0.4*spec.radius_m**2)
    expected_count=round(spec.duration_s/spec.dt_s)+1
    if len(samples)!=expected_count:
        raise ValueError('solver time grid missing samples')
    energies=[];crossings=[]
    for i,row in enumerate(samples):
        if set(row)!={'t_s','theta_rad','omega_rad_s','x_m','z_m'} or any(type(v) not in (int,float) or not math.isfinite(v) for v in row.values()):
            raise ValueError('invalid finite SI trajectory')
        if abs(row['t_s']-i*spec.dt_s)>1e-8:
            raise ValueError('time grid or time units changed')
        theta=row['theta_rad'];omega=row['omega_rad_s']
        if abs(row['x_m']-spec.length_m*math.sin(theta))>1e-9 or abs(row['z_m']+spec.length_m*math.cos(theta))>1e-9:
            raise ValueError('trajectory violates geometry/length constraint')
        energies.append(0.5*I*omega**2+spec.mass_kg*spec.gravity_m_s2*spec.length_m*(1-math.cos(theta)))
        if i and samples[i-1]['theta_rad']>0>=theta:
            a=samples[i-1];crossings.append(a['t_s']+(row['t_s']-a['t_s'])*a['theta_rad']/(a['theta_rad']-theta))
    if abs(samples[0]['theta_rad']-spec.initial_angle_rad)>1e-10 or abs(samples[0]['omega_rad_s'])>1e-10:
        raise ValueError('initial conditions changed')
    scale=max(abs(energies[0]),spec.mass_kg*spec.gravity_m_s2*spec.length_m*1e-12)
    drift=max(abs(e-energies[0]) for e in energies)/scale
    if spec.damping_nm_s==0 and drift>1e-6:
        raise ValueError('conservative energy check failed')
    if spec.damping_nm_s>0 and any(b-a>scale*1e-6 for a,b in zip(energies,energies[1:])):
        raise ValueError('passive damping increased energy')
    # Independent finite-difference ODE residual, with a declared time-grid error bound.
    max_residual=0.0
    for a,b,c in zip(samples,samples[1:],samples[2:]):
        acceleration=(c['omega_rad_s']-a['omega_rad_s'])/(2*spec.dt_s)
        intended=-(spec.mass_kg*spec.gravity_m_s2*spec.length_m*math.sin(b['theta_rad'])+spec.damping_nm_s*b['omega_rad_s'])/I
        max_residual=max(max_residual,abs(acceleration-intended))
    bound=0.03+max(abs(r['theta_rad']) for r in samples)*(spec.gravity_m_s2/spec.length_m)**2*spec.dt_s**2
    if max_residual>bound:
        raise ValueError('independent governing-equation residual failed')
    period=4*math.sqrt(I/(spec.mass_kg*spec.gravity_m_s2*spec.length_m))*float(ellipk(math.sin(spec.initial_angle_rad/2)**2))
    observed=sum(b-a for a,b in zip(crossings,crossings[1:]))/(len(crossings)-1) if len(crossings)>1 else None
    if observed is not None and spec.damping_nm_s==0 and abs(observed-period)/period>0.002:
        raise ValueError('period differs from independent nonlinear reference')
    return {'inertia_about_pivot_kg_m2':I,'undamped_period_reference_s':period,'measured_period_s':observed,
            'relative_energy_change':drift,'max_ode_residual_rad_s2':max_residual,
            'checks':['finite SI grid','initial conditions','rigid length','energy/passive damping','ODE residual','elliptic period reference']}


def solve(spec: Pendulum, *, max_step=None, cancelled=lambda:False):
    import scipy
    from scipy.integrate import solve_ivp
    if cancelled():raise ValueError('pendulum cancelled before solver dispatch')
    I=spec.mass_kg*(spec.length_m**2+0.4*spec.radius_m**2)
    started=time.process_time()
    def ode(t,state):
        if cancelled() or time.process_time()-started>5:
            raise ValueError('pendulum cancelled or CPU budget exhausted')
        return [state[1],-(spec.mass_kg*spec.gravity_m_s2*spec.length_m*math.sin(state[0])+spec.damping_nm_s*state[1])/I]
    count=round(spec.duration_s/spec.dt_s)
    times=[i*spec.dt_s for i in range(count+1)]
    step=spec.dt_s if max_step is None else max_step
    if type(step) not in (int,float) or not math.isfinite(step) or not 0<step<=spec.dt_s:
        raise ValueError('refinement must use a finite smaller step')
    solution=solve_ivp(ode,(0.0,spec.duration_s),(spec.initial_angle_rad,0.0),t_eval=times,
                       method='DOP853',rtol=1e-9,atol=1e-11,max_step=step)
    if not solution.success:raise ValueError('SciPy did not complete integration')
    samples=[{'t_s':float(t),'theta_rad':float(theta),'omega_rad_s':float(omega),
              'x_m':spec.length_m*math.sin(theta),'z_m':-spec.length_m*math.cos(theta)}
             for t,theta,omega in zip(solution.t,solution.y[0],solution.y[1])]
    result={'solver':'scipy.integrate.solve_ivp','solver_version':scipy.__version__,'method':'DOP853',
            'model':spec.model_dump(mode='json'),'design_sha256':sha(design(spec)),
            'scenario_sha256':sha(scenario(spec)),'samples':samples,'cpu_s':time.process_time()-started,
            'evidence_status':'SIMULATION_PASSED_WITH_ASSUMPTIONS',
            'assumptions':['uniform solid sphere','massless rigid connector','one revolute joint','no contact/air/thermal/material-strength model'],
            'physical_validation':False}
    result['metrics']=independent_checks(spec,result)
    return result


def compare_runs(baseline, candidate):
    if baseline['scenario_sha256']!=candidate['scenario_sha256']:
        raise ValueError('controlled comparison requires the same scenario and initial conditions')
    old=baseline['metrics']['measured_period_s'];new=candidate['metrics']['measured_period_s']
    return {'baseline_design_sha256':baseline['design_sha256'],'candidate_design_sha256':candidate['design_sha256'],
            'fixed_scenario_sha256':baseline['scenario_sha256'],'baseline_period_s':old,'candidate_period_s':new,
            'period_difference_s':None if old is None or new is None else new-old,
            'evidence_status':'SIMULATION_PASSED_WITH_ASSUMPTIONS','physical_validation':False}
