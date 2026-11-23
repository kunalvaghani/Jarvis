"""Fixed CPU double-wishbone surrogate builder and controlled aero comparison.

The JSON topology is derived from Project Chrono's BSD-licensed Sedan examples.
It is explicitly an assumed parametric mechanism, never recovered F1 internals.
No user code, plugins, external meshes or arbitrary file paths are executed.
"""
import hashlib
import json
import math
from pathlib import Path
import re
import time


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False,separators=(',',':')).encode()).hexdigest()


def inventory(system):
    bodies=[b for b in system.GetBodies() if not b.IsFixed()]
    return {'body_count':len(bodies),'joint_count':len(list(system.GetLinks())),
        'mass_kg':sum(b.GetMass() for b in bodies),'body_masses_kg':[b.GetMass() for b in bodies],
        'inertia_matrices_kg_m2':[[[b.GetInertia()[i,j] for j in range(3)] for i in range(3)] for b in bodies]}


def run(case,chrono,veh,prefix,run_id,prepare_only=False):
    started=time.process_time()
    app=Path(__file__).resolve().parents[3]
    if not isinstance(run_id,str) or not re.fullmatch('[a-f0-9]{32}',run_id):raise ValueError('trusted bounded run identity required')
    root=app/'.jarvis-runtime/discovery/vehicle-runs'/digest(case)/run_id
    root.mkdir(parents=True,exist_ok=False)  # uncertain or completed output is never overwritten
    data=prefix/'Library/data/vehicle'
    template_hashes={}
    def read(relative):
        raw=(data/relative).read_bytes();template_hashes[relative]=hashlib.sha256(raw).hexdigest()
        return json.loads(re.sub(r'//[^\n]*','',raw.decode()))
    def clean(value):
        if isinstance(value,dict):return {k:clean(v) for k,v in value.items() if k!='Visualization'}
        if isinstance(value,list):return [clean(v) for v in value]
        return value
    chassis=clean(read('sedan/chassis/Sedan_Chassis.json'))
    c=chassis['Components'][0];c['Mass']=case['chassis_mass_kg'];c['Moments of Inertia']=case['chassis_inertia_kg_m2']
    c['Centroidal Frame']['Location']=[0,0,.3]
    suspension=clean(read('sedan/suspension/Sedan_DoubleWishbone.json'))
    scale=case['track_m']/(2*.7979)
    def scale_points(value,key=''):
        if isinstance(value,dict):return {k:scale_points(v,k) for k,v in value.items()}
        if isinstance(value,list) and len(value)==3 and (key=='COM' or key.startswith('Location')):
            return [value[0],value[1]*scale,value[2]]
        return value
    suspension=scale_points(suspension)
    suspension['Spring']['Spring Coefficient']=case['spring_n_m']
    suspension['Shock']['Damping Coefficient']=case['damping_n_s_m']
    wheel=clean(read('sedan/wheel/Sedan_Wheel.json'));wheel['Mass']=case['wheel_mass_kg']
    # Explicit assumed solid-wheel inertia, not a measured tire/wheel construction.
    r=case['wheel_radius_m'];m=case['wheel_mass_kg'];w=case['wheel_width_m']
    wheel['Inertia']=[m*(3*r*r+w*w)/12,m*r*r/2,m*(3*r*r+w*w)/12]
    tire=clean(read('sedan/tire/Sedan_TMeasyTire.json'))
    tire['Design'].update({'Unloaded Radius [m]':r,'Width [m]':w})
    tire['Coefficient of Friction']=case['tire_friction']
    tire['Design']['Rim Radius [m]']=min(tire['Design']['Rim Radius [m]'],r*.8)
    tire.pop('Load Index',None)
    tire['Maximum Bearing Capacity [N]']=case['chassis_mass_kg']*9.81
    assembly=clean(read('sedan/vehicle/Sedan_Vehicle.json'))
    assembly['Chassis']['Input File']='chassis.json'
    assembly['Wheelbase']=case['wheelbase_m']
    for i,axle in enumerate(assembly['Axles']):
        axle['Suspension Input File']='suspension.json'
        axle['Suspension Location'][0]=case['wheelbase_m']*(.5 if i==0 else -.5)
        for side in ('Left','Right'):
            axle[f'{side} Wheel Input File']='wheel.json';axle[f'{side} Brake Input File']='brake.json'
    assembly['Steering Subsystems'][0]['Input File']='steering.json'
    assembly['Steering Subsystems'][0]['Location'][0]=case['wheelbase_m']/2-.188
    assembly['Driveline']['Input File']='driveline.json'
    files={'vehicle.json':assembly,'chassis.json':chassis,'suspension.json':suspension,'wheel.json':wheel,'tire.json':tire,
           'brake.json':clean(read('sedan/brake/Sedan_BrakeSimple.json')),
           'steering.json':clean(read('sedan/steering/Sedan_RackPinion.json')),
           'driveline.json':clean(read('sedan/driveline/Sedan_Driveline2WD.json')),
           'transmission.json':clean(read('sedan/powertrain/Sedan_AutomaticTransmissionSimpleMap.json'))}
    files['engine.json']={'Name':'Explicit assumed engine','Type':'Engine','Template':'EngineSimple',
        'Maximum Engine Torque':case['maximum_engine_torque_n_m'],
        'Maximum Engine Power':case['maximum_engine_power_w'],
        'Maximum Engine Speed':case['maximum_engine_speed_rad_s']}
    terrain_json=clean(read('terrain/RigidPlane.json'))
    terrain_json['Patches'][0]['Geometry']['Dimensions']=[2000,2000,2]
    terrain_json['Patches'][0]['Contact Material']['Coefficient of Friction']=case['tire_friction']
    files['terrain.json']=terrain_json
    for name,value in files.items():(root/name).write_text(json.dumps(value,indent=2),encoding='utf-8')
    (root/'assumed-inputs.json').write_text(json.dumps(case,indent=2),encoding='utf-8')
    (root/'template-provenance.json').write_text(json.dumps({'origin':'Project Chrono 10.0.0 Sedan JSON topology',
        'license':'BSD-3-Clause','template_sha256':template_hashes,
        'limitations':'Assumed geometry and mechanical subcomponents; not actual F1 engineering data.'},indent=2),encoding='utf-8')
    veh.SetVehicleDataPath(str(root)+str(__import__('os').sep))
    native_hashes={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files}
    scenario=dict(case);scenario.pop('candidate_corner_front_delta_deg');scenario_hash=digest(scenario)
    results=[]
    for variant in ('baseline','candidate'):
        vehicle=veh.WheeledVehicle(str(root/'vehicle.json'),chrono.ChContactMethod_NSC)
        vehicle.Initialize(chrono.ChCoordsysd(chrono.ChVector3d(0,0,.5),chrono.ChQuaterniond(1,0,0,0)))
        system=vehicle.GetSystem();system.SetCollisionSystemType(chrono.ChCollisionSystem.Type_BULLET)
        system.SetGravitationalAcceleration(chrono.ChVector3d(0,0,-9.81))
        engine=veh.ReadEngineJSON(str(root/'engine.json'))
        transmission=veh.ReadTransmissionJSON(str(root/'transmission.json'))
        vehicle.InitializePowertrain(veh.ChPowertrainAssembly(engine,transmission))
        wheels=[]
        for axle in vehicle.GetAxles():
            for wh in axle.GetWheels():
                tire_instance=veh.ReadTireJSON(str(root/'tire.json'))
                vehicle.InitializeTire(tire_instance,wh,chrono.VisualizationType_NONE)
                wheels.append(wh)
        terrain=veh.RigidTerrain(system,str(root/'terrain.json'));terrain.Initialize()
        body=vehicle.GetChassisBody();accumulator=body.AddAccumulator()
        if prepare_only:
            (root/'baseline-components.json').write_text(vehicle.ExportComponentList(),encoding='utf-8')
            hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file()}
            return {'kind':'prepared_vehicle','solver':'Chrono::Vehicle','version':'10.0.0',
                'inputs':case,'physical_inventory':inventory(system),'native_project':root.relative_to(app).as_posix(),
                'native_sha256':hashes,'wheel_positions_m':[[w.GetPos().x,w.GetPos().y,w.GetPos().z] for w in wheels],
                'cpu_s':time.process_time()-started,'physical_validation':False,'full_A_acceptance_passed':False}
        controls=veh.DriverInputs();samples=[];energy=0.;dt=case['timestep_s'];last_velocity=None
        for step in range(round(case['duration_s']/dt)+1):
            if step%100==0 and time.process_time()-started>100:raise TimeoutError('100 CPU-second vehicle loop cap')
            t=step*dt;pos=vehicle.GetPos();vel=body.GetPosDt()
            selected='straight' if case['year']==2026 and any(z['x_min_m']<=pos.x<=z['x_max_m'] and z['y_min_m']<=pos.y<=z['y_max_m'] for z in case['straight_zones']) else 'corner'
            aero=dict(case[selected])
            delta=case['candidate_corner_front_delta_deg'] if variant=='candidate' and selected=='corner' else 0
            aero['front_flap_angle_deg']+=delta
            aero['front_downforce_coefficient']+=delta*case['front_lift_slope_per_deg']
            aero['drag_coefficient']+=delta*case['drag_slope_per_deg']
            speed=math.hypot(vel.x,vel.y);q=.5*case['air_density_kg_m3']*speed*speed*case['reference_area_m2']
            power=max(0.,engine.GetMotorSpeed()*engine.GetOutputMotorshaftTorque())
            acceleration=0. if last_velocity is None else math.hypot(vel.x-last_velocity[0],vel.y-last_velocity[1])/dt
            # Lateral acceleration is the velocity change normal to horizontal travel.
            lateral=0. if last_velocity is None or speed<1e-6 else abs(-vel.y*(vel.x-last_velocity[0])+vel.x*(vel.y-last_velocity[1]))/(speed*dt)
            if step%case['sample_every']==0:
                points=[[wh.GetPos().x,wh.GetPos().y,wh.GetPos().z] for wh in wheels]
                tire_forces=[];slips=[];rotations=[]
                for wh in wheels:
                    tire=wh.GetTire();force=tire.ReportTireForce(terrain).force
                    tire_forces.append([force.x,force.y,force.z]);slips.append(tire.GetLongitudinalSlip())
                    rot=wh.GetSpindle().GetRot();rotations.append([rot.e0,rot.e1,rot.e2,rot.e3])
                residuals=[]
                for link in system.GetLinks():
                    residual=link.GetConstraintViolation()
                    residuals.extend(abs(residual.GetItem(i)) for i in range(residual.Size()))
                rot=body.GetRot()
                values=[t,pos.x,pos.y,pos.z,speed,power,energy,lateral,acceleration,*[v for point in points for v in point]]
                if not all(math.isfinite(v) for v in values) or abs(pos.x)>950 or abs(pos.y)>950 or not -.2<pos.z<2:
                    raise ValueError('vehicle left valid numerical/terrain domain')
                samples.append({'time_s':t,'position_m':[pos.x,pos.y,pos.z],'speed_m_s':speed,
                    'lateral_acceleration_m_s2':lateral,'mechanical_engine_power_w':power,'mechanical_engine_energy_j':energy,
                    'mode':selected,'front_flap_angle_deg':aero['front_flap_angle_deg'],'coefficients':aero,
                    'wheel_positions_m':points,'wheel_quaternions_wxyz':rotations,
                    'body_quaternion_wxyz':[rot.e0,rot.e1,rot.e2,rot.e3],
                    'tire_forces_n':tire_forces,'longitudinal_slip':slips,
                    'front_steering_angle_rad':vehicle.GetSteeringAngle(0,veh.LEFT),
                    'maximum_constraint_residual':max(residuals,default=0.),
                    'constraint_residual_count':len(residuals)})
            if step==round(case['duration_s']/dt):break
            control=next(c for c in reversed(case['controls']) if c['time_s']<=t)
            controls.m_steering=control['steering'];controls.m_throttle=control['throttle'];controls.m_braking=control['braking']
            terrain.Synchronize(t);vehicle.Synchronize(t,controls,terrain)
            body.EmptyAccumulator(accumulator)
            forward=body.GetRot().Rotate(chrono.ChVector3d(1,0,0))
            for sign,key in ((1,'front_downforce_coefficient'),(-1,'rear_downforce_coefficient')):
                force=chrono.ChVector3d(-q*aero['drag_coefficient']*.5*vel.x/max(speed,1e-9),
                    -q*aero['drag_coefficient']*.5*vel.y/max(speed,1e-9),-q*aero[key])
                point=body.GetPos()+forward*(sign*case['wheelbase_m']/2)
                body.AccumulateForce(accumulator,force,point,False)
            energy+=power*dt;last_velocity=(vel.x,vel.y)
            vehicle.Advance(dt);terrain.Advance(dt)
        (root/f'{variant}-components.json').write_text(vehicle.ExportComponentList(),encoding='utf-8')
        metrics={'maximum_observed_speed_m_s':max(r['speed_m_s'] for r in samples),
                 'maximum_observed_lateral_acceleration_m_s2':max(r['lateral_acceleration_m_s2'] for r in samples),
                 'mechanical_engine_energy_j':energy}
        results.append({'variant':variant,'scenario_sha256':scenario_hash,'samples':samples,'metrics':metrics,
            'physical_inventory':inventory(system)})
    native_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file()}
    return {'solver':'Chrono::Vehicle','version':'10.0.0','inputs':case,'runs':results,
            'scenario_sha256':scenario_hash,'native_project':root.relative_to(app).as_posix(),
            'native_sha256':native_hashes,'cpu_s':time.process_time()-started,
            'limitations':['Assumed double-wishbone topology, tire law and drivetrain; not recovered F1 internals.',
                'TMeasy force-model tire fitted from assumed bearing capacity, not measured F1 tire data.',
                'Aero is an explicit coefficient/slope surrogate, not CFD or independently validated aero.',
                'Prescribed controls on flat terrain; observed speed is not demonstrated terminal top speed or lap performance.',
                'Mechanical engine energy excludes fuel conversion, battery and hybrid-system losses.'],
            'evidence_status':'SIMULATION_PASSED_WITH_ASSUMPTIONS','physical_validation':False,
            'full_A_acceptance_passed':False}


def study_cases(case):
    """Declared finite numerical refinement and joint aero-uncertainty envelope."""
    import copy
    cases={'primary':copy.deepcopy(case),'refined':copy.deepcopy(case)}
    cases['refined']['timestep_s']=case['timestep_s']/2
    for name,factor in (('aero_low',.9),('aero_high',1.1)):
        child=copy.deepcopy(case)
        for mode in ('corner','straight'):
            for key in ('front_downforce_coefficient','rear_downforce_coefficient','drag_coefficient'):
                child[mode][key]*=factor
        cases[name]=child
    return cases


def run_study(case,chrono,veh,prefix,run_id):
    started=time.process_time();cases=study_cases(case);reports={}
    for name,child in cases.items():
        if time.process_time()-started>95:raise TimeoutError('aggregate CPU study budget exhausted')
        child_id=hashlib.sha256((run_id+name).encode()).hexdigest()[:32]
        reports[name]=run(child,chrono,veh,prefix,child_id)
    cpu=time.process_time()-started
    if cpu>100:raise TimeoutError('aggregate 100 CPU-second study limit exceeded')
    return {'kind':'conditional_vehicle_study','reports':reports,'cpu_s':cpu,
        'uncertainty_method':'Joint +/-10% assumed aero coefficient envelope, not statistical confidence or full uncertainty coverage',
        'refinement':'Half the primary timestep; unchanged controls, road and physical parameters',
        'physical_validation':False,'full_A_acceptance_passed':False}
