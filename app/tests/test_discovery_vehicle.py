"""Controlled development fixtures; never autonomous F1 acceptance evidence."""
import copy
import pytest
from jarvis.discovery.model.vehicle import VehicleCase,digest,mode,scenario_digest,validate_result
from jarvis.discovery.vehicle_flow import neurons


def case_data(year=2026):
    return {'name':'Controlled numerical fixture, not an F1 acceptance asset','year':year,
        'representation':'assumed_parametric_double_wishbone_surrogate','source_refs':['controlled-source'],
        'assumptions':['Assumed topology, not recovered internals','Assumed tire law','Assumed coefficient aero'],
        'chassis_mass_kg':650.,'chassis_inertia_kg_m2':[200.,700.,800.],
        'wheelbase_m':3.4,'track_m':1.8,'wheel_radius_m':.35,'wheel_width_m':.3,'wheel_mass_kg':12.,
        'spring_n_m':500000.,'damping_n_s_m':10000.,'tire_friction':1.2,
        'maximum_engine_power_w':500000.,'maximum_engine_torque_n_m':400.,'maximum_engine_speed_rad_s':1100.,
        'air_density_kg_m3':1.2,'reference_area_m2':1.5,
        'corner':{'front_downforce_coefficient':1.,'rear_downforce_coefficient':1.5,'drag_coefficient':1.,'front_flap_angle_deg':10.},
        'straight':{'front_downforce_coefficient':.3,'rear_downforce_coefficient':.4,'drag_coefficient':.6,'front_flap_angle_deg':2.},
        'candidate_corner_front_delta_deg':2.,'front_lift_slope_per_deg':.05,'drag_slope_per_deg':.01,
        'straight_zones':[{'x_min_m':.5,'x_max_m':100.,'y_min_m':-100.,'y_max_m':100.}] if year==2026 else [],
        'duration_s':3.,'timestep_s':.002,'sample_every':20,
        'controls':[{'time_s':0.,'steering':0.,'throttle':.8,'braking':0.}]}


def case(year=2026):
    import json
    return VehicleCase.model_validate_json(json.dumps(case_data(year)))


@pytest.mark.parametrize('change',[
    {'chassis_mass_kg':None}, {'chassis_inertia_kg_m2':[1.,1.,100.]},
    {'candidate_corner_front_delta_deg':0.}, {'front_lift_slope_per_deg':0.,'drag_slope_per_deg':0.},
    {'straight_zones':[]}, {'controls':[{'time_s':1.,'steering':0.,'throttle':1.,'braking':0.}]},
    {'sample_every':71}, {'source_refs':[]}, {'tire_friction':float('nan')},
])
def test_invalid_or_disconnected_physics_rejected(change):
    import json
    with pytest.raises(ValueError):VehicleCase.model_validate_json(json.dumps({**case_data(),**change}))


def test_era_and_spatial_mode_semantics():
    a=case(2025).model_dump(mode='json');b=case().model_dump(mode='json')
    assert mode(a,1,0)=='corner'
    assert mode(b,0,0)=='corner'
    assert mode(b,1,0)=='straight'
    assert mode(b,1,101)=='corner'
    assert scenario_digest(case())==digest({k:v for k,v in b.items() if k!='candidate_corner_front_delta_deg'})


def test_vehicle_nodes_are_flagged_and_have_explicit_typed_contracts():
    assert not neurons({'lab':{'enabled':False,'sim':True}})
    rows=neurons({'lab':{'enabled':True,'sim':True}})
    assert len(rows)==2
    assert all(r.contract=='explicit' and r.resource_cost['gpu_vram_mb']==0 for r in rows)


def synthetic_report(c):
    """Synthetic trace only exercises the pure verifier, not an execution receipt."""
    raw=c.model_dump(mode='json');runs=[]
    for variant in ('baseline','candidate'):
        samples=[]
        for i in range(76):
            t=i*.04;x=t
            selected=mode(raw,x,0);aero=raw[selected].copy()
            delta=c.candidate_corner_front_delta_deg if variant=='candidate' and selected=='corner' else 0
            aero['front_flap_angle_deg']+=delta
            aero['front_downforce_coefficient']+=delta*c.front_lift_slope_per_deg
            aero['drag_coefficient']+=delta*c.drag_slope_per_deg
            samples.append({'time_s':t,'position_m':[x,0,.3],'mode':selected,'coefficients':aero,
                'front_flap_angle_deg':aero['front_flap_angle_deg'],'speed_m_s':1.,'lateral_acceleration_m_s2':0.,
                'mechanical_engine_power_w':10.,'mechanical_engine_energy_j':10*t,'wheel_positions_m':[[0,0,0]]*4})
        runs.append({'variant':variant,'scenario_sha256':scenario_digest(c),'samples':samples,
            'metrics':{'maximum_observed_speed_m_s':1.,'maximum_observed_lateral_acceleration_m_s2':0.,'mechanical_engine_energy_j':30.}})
    return {'solver':'Chrono::Vehicle','version':'10.0.0','inputs':raw,'runs':runs,
        'scenario_sha256':scenario_digest(c),'physical_validation':False,'full_A_acceptance_passed':False}


def test_consistent_synthetic_trace_can_only_be_conditional():
    c=case();r=synthetic_report(c)
    assert validate_result(c,r)
    r['full_A_acceptance_passed']=True
    with pytest.raises(ValueError):validate_result(c,r)


@pytest.mark.parametrize('corruption',['scenario','straight_angle','metrics','time','mode','energy','truncate'])
def test_independent_verifier_rejects_corrupted_trace(corruption):
    c=case();r=synthetic_report(c);s=r['runs'][1]['samples']
    if corruption=='scenario':r['runs'][1]['scenario_sha256']='f'*64
    elif corruption=='straight_angle':s[-1]['coefficients']['front_flap_angle_deg']+=2
    elif corruption=='metrics':r['runs'][0]['metrics']['maximum_observed_speed_m_s']=99
    elif corruption=='time':s[-1]['time_s']=2.99
    elif corruption=='mode':s[-1]['mode']='corner'
    elif corruption=='energy':s[-1]['mechanical_engine_energy_j']=-1
    else:s.pop()
    with pytest.raises(ValueError):validate_result(c,r)
