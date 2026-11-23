"""Versioned, explicit educational vehicle assumptions; never team specifications.

Numbers are a reusable engineering model, not a fitted answer to A1/A2. Season
envelope dimensions come from retrieved official clauses. Every other number
is labelled assumed with a range; the solver, not this recipe, decides results.
"""
from .model.vehicle import VehicleCase


def build(target,regulations,source_refs):
    wb=regulations['limits']['maximum_wheelbase_m']*.98
    half=regulations['limits']['maximum_non_tyre_half_width_m']
    track=2*half-.4
    raw={'name':f'{target.year} F1-class educational surrogate (not exact {target.team_or_class} CAD)',
        'year':target.year,'representation':'assumed_parametric_double_wishbone_surrogate','source_refs':source_refs,
        'assumptions':[
            'Regulation-referenced envelope only; not a complete FIA legality or proprietary team reconstruction.',
            'Chassis mass, inertia, wheel/tire construction and suspension parameters are explicit assumed educational values.',
            'TMeasy semi-empirical tire parameters are generated from assumed bearing capacity, not measured F1 tire data.',
            'Lumped 500 kW engine and drivetrain are assumed; hybrid conversion/storage and real power-unit maps are not modeled.',
            'Aero coefficients/slopes are unmeasured illustrative values; no aerodynamic curve is inferred from exterior photos.',
            'Flat 2000 m road, prescribed 13 s settle/accelerate/turn/brake controls; maximum observed speed is not terminal speed or lap performance.',
            'Gravity 9.81 m/s2, air density 1.225 kg/m3 and friction 1.1 are fixed test assumptions, not measured conditions.',
            'All unexplained geometric offsets and component masses inherited from the BSD Chrono Sedan topology remain assumptions.'],
        'chassis_mass_kg':620.,'chassis_inertia_kg_m2':[180.,650.,700.],
        'wheelbase_m':wb,'track_m':track,'wheel_radius_m':.35,'wheel_width_m':.30,'wheel_mass_kg':12.,
        'spring_n_m':180000.,'damping_n_s_m':10000.,'tire_friction':1.1,
        'maximum_engine_power_w':500000.,'maximum_engine_torque_n_m':550.,'maximum_engine_speed_rad_s':1500.,
        'air_density_kg_m3':1.225,'reference_area_m2':1.5,
        'corner':{'front_downforce_coefficient':1.,'rear_downforce_coefficient':1.4,'drag_coefficient':.9,'front_flap_angle_deg':12.},
        'straight':{'front_downforce_coefficient':.4 if target.year==2026 else 1.,
                    'rear_downforce_coefficient':.5 if target.year==2026 else 1.4,
                    'drag_coefficient':.65 if target.year==2026 else .9,'front_flap_angle_deg':4. if target.year==2026 else 12.},
        'candidate_corner_front_delta_deg':target.front_delta_deg,'front_lift_slope_per_deg':.04,'drag_slope_per_deg':.004,
        'straight_zones':[{'x_min_m':8.,'x_max_m':30.,'y_min_m':-100.,'y_max_m':100.}] if target.year==2026 else [],
        'duration_s':13.,'timestep_s':.002,'sample_every':100,
        'controls':[{'time_s':t,'steering':s,'throttle':p,'braking':b} for t,s,p,b in
            [(0.,0.,0.,0.),(2.,0.,.8,0.),(7.,.15,.4,0.),(10.,0.,0.,.8)]]}
    import json
    return VehicleCase.model_validate_json(json.dumps(raw))


def uncertainty(case):
    raw=case.model_dump(mode='json')
    values={k:{'value':raw[k],'status':'ASSUMED','interval':[raw[k]*.8,raw[k]*1.2],
        'sensitivity_tested':False} for k in ('chassis_mass_kg','spring_n_m','damping_n_s_m','tire_friction',
        'maximum_engine_power_w','maximum_engine_torque_n_m','reference_area_m2')}
    return {'parameters':values,'aero_envelope':{'factors':[.9,1.1],'sensitivity_tested':True,
        'status':'ASSUMED joint envelope, not a probabilistic confidence interval'},
        'unknowns':['real team geometry','measured tire force/slip curves','verified aero map','hybrid efficiency','full regulatory compliance'],
        'universal_or_physical_validation':False}
