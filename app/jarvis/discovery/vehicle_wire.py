"""Compact SI request transport. Every number remains model/user supplied.

Array positions and units are a fixed public contract. Expansion changes names,
not values, and never supplies a missing number or a simulation result.
"""
import json

GROUPS={
 'body':('chassis_mass_kg','chassis_inertia_kg_m2'),
 'wheels':('wheelbase_m','track_m','wheel_radius_m','wheel_width_m','wheel_mass_kg'),
 'support':('spring_n_m','damping_n_s_m','tire_friction'),
 'engine':('maximum_engine_power_w','maximum_engine_torque_n_m','maximum_engine_speed_rad_s'),
 'air':('air_density_kg_m3','reference_area_m2'),
}


def schema():
    def vector(n,description):return {'type':'array','minItems':n,'maxItems':n,'items':{'type':'number'},'description':description}
    properties={
        'format':{'type':'string','enum':['vehicle-si-v1'],'description':'Explicit assumed double-wishbone surrogate; never exact proprietary engineering data.'},
        'name':{'type':'string','maxLength':100},'year':{'type':'integer','enum':[2025,2026]},
        'source_refs':{'type':'array','minItems':1,'maxItems':20,'items':{'type':'string'},'description':'Actual retained Source IDs from source tools, not URLs or invented IDs.'},
        'assumptions':{'type':'array','minItems':3,'maxItems':30,'items':{'type':'string'},'description':'Explicitly mark guessed/inferred mechanical, tire, engine and aero data.'},
        'body':vector(4,'[chassis mass kg, Ixx kg*m², Iyy kg*m², Izz kg*m²]; positive physically consistent inertia'),
        'wheels':vector(5,'[wheelbase m, track m, wheel radius m, width m, wheel mass kg]'),
        'support':vector(3,'[spring N/m, damping N*s/m, tire friction coefficient]'),
        'engine':vector(3,'[maximum mechanical power W, torque N*m, speed rad/s]'),
        'air':vector(2,'[air density kg/m³, aerodynamic reference area m²]'),
        'aero':{'type':'object','additionalProperties':False,'required':['corner','straight','delta_deg','slopes'],
            'properties':{'corner':vector(4,'[front downforce Cl, rear downforce Cl, Cd, front flap angle deg]'),
                'straight':vector(4,'[front downforce Cl, rear downforce Cl, Cd, front flap angle deg]'),
                'delta_deg':{'type':'number','description':'Only candidate Corner Mode front-flap delta; nonzero, within -10..10 deg.'},
                'slopes':vector(2,'[front Cl per degree, Cd per degree]; explicit assumed surrogate, not CFD')}},
        'scenario':{'type':'object','additionalProperties':False,'required':['duration_s','dt_s','sample_every','zones','controls'],
            'properties':{'duration_s':{'type':'number','minimum':1,'maximum':60},
                'dt_s':{'type':'number','minimum':.0005,'maximum':.002},'sample_every':{'type':'integer','minimum':1,'maximum':100},
                'zones':{'type':'array','maxItems':10,'items':vector(4,'[xmin m, xmax m, ymin m, ymax m] spatial Straight Mode rectangle; [] for 2025, nonempty for 2026')},
                'controls':{'type':'array','minItems':1,'maxItems':30,'items':vector(4,'[time s, steering -1..1, throttle 0..1, braking 0..1]; starts at t=0, increasing times')}}}}
    return {'type':'object','additionalProperties':False,'required':list(properties),'properties':properties}


def expand(data):
    if not isinstance(data,dict):raise ValueError('vehicle object required')
    if 'format' not in data:return data  # Existing full typed SI files remain supported.
    required=set(schema()['required'])
    if set(data)!=required or data['format']!='vehicle-si-v1':raise ValueError('exact vehicle-si-v1 fields required')
    def vector(value,n):
        if not isinstance(value,list) or len(value)!=n or any(type(v) not in (float,int) for v in value):
            raise ValueError('complete numeric vector of length '+str(n)+' required; missing values cannot be invented')
        return value
    body=vector(data['body'],4)
    out={k:data[k] for k in ('name','year','source_refs','assumptions')}
    out.update(representation='assumed_parametric_double_wishbone_surrogate',chassis_mass_kg=body[0],chassis_inertia_kg_m2=body[1:])
    for group in ('wheels','support','engine','air'):
        keys=GROUPS[group];out.update(zip(keys,vector(data[group],len(keys))))
    aero=data['aero'];scenario=data['scenario']
    if not isinstance(aero,dict) or set(aero)!={'corner','straight','delta_deg','slopes'}:raise ValueError('exact aero fields required')
    if not isinstance(scenario,dict) or set(scenario)!={'duration_s','dt_s','sample_every','zones','controls'}:raise ValueError('exact scenario fields required')
    keys=('front_downforce_coefficient','rear_downforce_coefficient','drag_coefficient','front_flap_angle_deg')
    for state in ('corner','straight'):out[state]=dict(zip(keys,vector(aero[state],4)))
    slope=vector(aero['slopes'],2)
    out.update(candidate_corner_front_delta_deg=aero['delta_deg'],front_lift_slope_per_deg=slope[0],drag_slope_per_deg=slope[1],
        duration_s=scenario['duration_s'],timestep_s=scenario['dt_s'],sample_every=scenario['sample_every'])
    if not isinstance(scenario['zones'],list) or not isinstance(scenario['controls'],list):raise ValueError('explicit zone and control lists required')
    out['straight_zones']=[dict(zip(('x_min_m','x_max_m','y_min_m','y_max_m'),vector(z,4))) for z in scenario['zones']]
    out['controls']=[dict(zip(('time_s','steering','throttle','braking'),vector(c,4))) for c in scenario['controls']]
    return out


def parse(raw):
    from .model.vehicle import VehicleCase
    return VehicleCase.model_validate_json(json.dumps(expand(json.loads(raw)),allow_nan=False))
