"""Compact transport cannot invent, reorder or drop physical values."""
import copy,json
import pytest
from jarvis.discovery.vehicle_wire import expand,parse,schema
from tests.test_discovery_vehicle import case_data,case


def compact():
    d=case_data()
    return {'format':'vehicle-si-v1','name':d['name'],'year':d['year'],'source_refs':d['source_refs'],'assumptions':d['assumptions'],
        'body':[d['chassis_mass_kg'],*d['chassis_inertia_kg_m2']],
        'wheels':[d[k] for k in ('wheelbase_m','track_m','wheel_radius_m','wheel_width_m','wheel_mass_kg')],
        'support':[d[k] for k in ('spring_n_m','damping_n_s_m','tire_friction')],
        'engine':[d[k] for k in ('maximum_engine_power_w','maximum_engine_torque_n_m','maximum_engine_speed_rad_s')],
        'air':[d[k] for k in ('air_density_kg_m3','reference_area_m2')],
        'aero':{'corner':[d['corner'][k] for k in ('front_downforce_coefficient','rear_downforce_coefficient','drag_coefficient','front_flap_angle_deg')],
            'straight':[d['straight'][k] for k in ('front_downforce_coefficient','rear_downforce_coefficient','drag_coefficient','front_flap_angle_deg')],
            'delta_deg':d['candidate_corner_front_delta_deg'],'slopes':[d['front_lift_slope_per_deg'],d['drag_slope_per_deg']]},
        'scenario':{'duration_s':d['duration_s'],'dt_s':d['timestep_s'],'sample_every':d['sample_every'],
            'zones':[[z[k] for k in ('x_min_m','x_max_m','y_min_m','y_max_m')] for z in d['straight_zones']],
            'controls':[[c[k] for k in ('time_s','steering','throttle','braking')] for c in d['controls']]}}


def test_compact_roundtrip_preserves_every_input_exactly_and_full_files_still_work():
    assert expand(compact())==case_data()
    assert parse(json.dumps(compact()))==case()
    assert parse(json.dumps(case_data()))==case()
    assert set(schema()['required'])==set(compact())


@pytest.mark.parametrize('corruption',['missing','short','bool','nan','extra','bounds','scenario_extra'])
def test_invalid_compact_values_fail_before_dispatch(corruption):
    d=compact()
    if corruption=='missing':d.pop('body')
    elif corruption=='short':d['wheels'].pop()
    elif corruption=='bool':d['body'][0]=True
    elif corruption=='nan':d['engine'][0]=float('nan')
    elif corruption=='extra':d['claim_approved']=True
    elif corruption=='bounds':d['engine'][0]=-1.
    else:d['scenario']['change_physics']=True
    with pytest.raises(ValueError):parse(json.dumps(d))
