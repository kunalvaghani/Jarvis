"""Bounded, explicitly assumed vehicle comparison inputs; numbers are not facts.

The mechanical topology is a parameterized double-wishbone surrogate. It cannot
recover proprietary F1 internals or certify an exact car from exterior geometry.
"""
import hashlib
import json
from typing import Literal
from pydantic import Field, model_validator
from ..contracts import StrictModel, Finite


class AeroState(StrictModel):
    front_downforce_coefficient: Finite = Field(ge=0,le=8)
    rear_downforce_coefficient: Finite = Field(ge=0,le=8)
    drag_coefficient: Finite = Field(gt=0,le=5)
    front_flap_angle_deg: Finite = Field(ge=-15,le=45)


class Zone(StrictModel):
    x_min_m: Finite
    x_max_m: Finite
    y_min_m: Finite
    y_max_m: Finite

    @model_validator(mode='after')
    def bounds(self):
        if self.x_min_m>=self.x_max_m or self.y_min_m>=self.y_max_m:
            raise ValueError('zone bounds must be ordered')
        return self


class Control(StrictModel):
    time_s: Finite = Field(ge=0,le=60)
    steering: Finite = Field(ge=-1,le=1)
    throttle: Finite = Field(ge=0,le=1)
    braking: Finite = Field(ge=0,le=1)


class VehicleCase(StrictModel):
    name: str = Field(min_length=1,max_length=100)
    year: Literal[2025,2026]
    representation: Literal['assumed_parametric_double_wishbone_surrogate']
    source_refs: tuple[str,...] = Field(min_length=1,max_length=20)
    assumptions: tuple[str,...] = Field(min_length=3,max_length=30)
    chassis_mass_kg: Finite = Field(ge=200,le=2000)
    chassis_inertia_kg_m2: tuple[Finite,Finite,Finite]
    wheelbase_m: Finite = Field(ge=1,le=5)
    track_m: Finite = Field(ge=1,le=3)
    wheel_radius_m: Finite = Field(ge=.15,le=.6)
    wheel_width_m: Finite = Field(ge=.1,le=.6)
    wheel_mass_kg: Finite = Field(ge=2,le=50)
    spring_n_m: Finite = Field(ge=10000,le=2000000)
    damping_n_s_m: Finite = Field(ge=100,le=50000)
    tire_friction: Finite = Field(gt=.1,le=3)
    maximum_engine_power_w: Finite = Field(ge=10000,le=1500000)
    maximum_engine_torque_n_m: Finite = Field(ge=20,le=3000)
    maximum_engine_speed_rad_s: Finite = Field(ge=100,le=3000)
    air_density_kg_m3: Finite = Field(ge=.1,le=2)
    reference_area_m2: Finite = Field(gt=.1,le=10)
    corner: AeroState
    straight: AeroState
    candidate_corner_front_delta_deg: Finite = Field(ge=-10,le=10)
    front_lift_slope_per_deg: Finite = Field(ge=0,le=.5)
    drag_slope_per_deg: Finite = Field(ge=0,le=.2)
    straight_zones: tuple[Zone,...] = Field(max_length=10)
    duration_s: Finite = Field(ge=1,le=60)
    timestep_s: Finite = Field(ge=.0005,le=.002)
    sample_every: int = Field(ge=1,le=100)
    controls: tuple[Control,...] = Field(min_length=1,max_length=30)

    @model_validator(mode='after')
    def consistency(self):
        if any(v<=0 for v in self.chassis_inertia_kg_m2):raise ValueError('positive inertia required')
        x,y,z=self.chassis_inertia_kg_m2
        if x+y<z or x+z<y or y+z<x:raise ValueError('inertia violates triangle inequality')
        if self.year==2025 and self.straight_zones:raise ValueError('2025 front-wing model has no active-aero zones')
        if self.year==2026 and not self.straight_zones:raise ValueError('2026 requires explicit spatial Straight Mode zones')
        if self.candidate_corner_front_delta_deg==0:raise ValueError('comparison requires a real parameter change')
        angle=self.corner.front_flap_angle_deg+self.candidate_corner_front_delta_deg
        cl=self.corner.front_downforce_coefficient+self.front_lift_slope_per_deg*self.candidate_corner_front_delta_deg
        cd=self.corner.drag_coefficient+self.drag_slope_per_deg*self.candidate_corner_front_delta_deg
        if not -15<=angle<=45 or cl<0 or cd<=0:raise ValueError('candidate exceeds angle/coefficient limits')
        if self.front_lift_slope_per_deg==0 and self.drag_slope_per_deg==0:
            raise ValueError('parameter is disconnected from physics')
        times=[c.time_s for c in self.controls]
        if times[0]!=0 or times!=sorted(set(times)) or times[-1]>self.duration_s:
            raise ValueError('controls start at zero and have strictly increasing times within duration')
        steps=self.duration_s/self.timestep_s
        if abs(steps-round(steps))>1e-7 or round(steps)%self.sample_every:
            raise ValueError('sample grid must include the exact final time')
        if round(steps)//self.sample_every>3000:raise ValueError('trace exceeds 3000 samples')
        if any(not s.strip() or len(s)>1000 for s in self.assumptions):raise ValueError('bounded nonempty assumptions required')
        return self


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()


def scenario_digest(case):
    data=case.model_dump(mode='json') if isinstance(case,VehicleCase) else dict(case)
    # Identity/physical properties/scenario remain fixed; only the explicit
    # candidate Corner Mode front-flap delta differs between design revisions.
    data.pop('candidate_corner_front_delta_deg',None)
    return digest(data)


def mode(case,x,y):
    return 'straight' if case['year']==2026 and any(z['x_min_m']<=x<=z['x_max_m'] and z['y_min_m']<=y<=z['y_max_m']
                for z in case['straight_zones']) else 'corner'


def validate_result(case,result):
    """Independent control/scenario/parameter/trace consistency checks."""
    import math
    raw=case.model_dump(mode='json')
    if result.get('inputs')!=raw or result.get('solver')!='Chrono::Vehicle' or result.get('version')!='10.0.0':
        raise ValueError('actual solver identity or inputs differ')
    if result.get('physical_validation') is not False or result.get('full_A_acceptance_passed') is not False:
        raise ValueError('conditional run cannot promote full acceptance or physical validation')
    runs=result.get('runs',[])
    if len(runs)!=2 or [r.get('variant') for r in runs]!=['baseline','candidate']:
        raise ValueError('one baseline and one candidate required')
    scenario=scenario_digest(case)
    if result.get('scenario_sha256')!=scenario or any(r.get('scenario_sha256')!=scenario for r in runs):
        raise ValueError('immutable scenario changed')
    expected_count=round(case.duration_s/case.timestep_s)//case.sample_every+1
    for run in runs:
        samples=run.get('samples',[])
        if len(samples)!=expected_count:raise ValueError('trace incomplete')
        previous_energy=-1
        for i,row in enumerate(samples):
            expected_time=i*case.timestep_s*case.sample_every
            if abs(row['time_s']-expected_time)>1e-9:raise ValueError('time grid changed')
            x,y,z=row['position_m']
            selected=mode(raw,x,y)
            if row['mode']!=selected:raise ValueError('mode is not spatial-zone-driven')
            expected=raw[selected].copy()
            delta=case.candidate_corner_front_delta_deg if run['variant']=='candidate' and selected=='corner' else 0
            expected['front_flap_angle_deg']+=delta
            expected['front_downforce_coefficient']+=delta*case.front_lift_slope_per_deg
            expected['drag_coefficient']+=delta*case.drag_slope_per_deg
            if row['coefficients']!=expected or row['front_flap_angle_deg']!=expected['front_flap_angle_deg']:
                raise ValueError('unapproved coefficient/angle change')
            def finite(value):
                if isinstance(value,dict):return all(finite(v) for v in value.values())
                if isinstance(value,list):return all(finite(v) for v in value)
                return math.isfinite(value) if type(value) in (int,float) else True
            if not finite(row) or len(row['wheel_positions_m'])!=4:raise ValueError('invalid numerical trace')
            if (row['speed_m_s']<0 or row['mechanical_engine_power_w']<0
                    or row['mechanical_engine_energy_j']<previous_energy):raise ValueError('invalid energy/speed')
            previous_energy=row['mechanical_engine_energy_j']
        metrics=run['metrics']
        if (metrics['maximum_observed_speed_m_s']!=max(s['speed_m_s'] for s in samples)
                or metrics['maximum_observed_lateral_acceleration_m_s2']!=max(s['lateral_acceleration_m_s2'] for s in samples)
                or abs(metrics['mechanical_engine_energy_j']-samples[-1]['mechanical_engine_energy_j'])>1e-6):
            raise ValueError('reported metrics differ from native trace')
        if case.year==2026 and {s['mode'] for s in samples}!={'corner','straight'}:
            raise ValueError('both active-aero states must actually be exercised')
    return ['actual controlled baseline/candidate','unchanged scenario and power unit',
            'spatial mode trace and permitted coefficient change','complete finite trajectory and measured mechanical energy']
