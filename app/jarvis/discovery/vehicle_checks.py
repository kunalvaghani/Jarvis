"""Independent physical/numerical checks over actual fixed-worker outputs."""
import hashlib,json,math
from pathlib import Path
from .model.vehicle import VehicleCase,validate_result


def inventory(value):
    if value['body_count']<10 or value['joint_count']<12:raise ValueError('missing physical bodies/joints')
    masses=value['body_masses_kg'];matrices=value['inertia_matrices_kg_m2']
    if len(masses)!=value['body_count'] or len(matrices)!=len(masses):raise ValueError('physical inventory incomplete')
    if any(not math.isfinite(m) or m<=0 for m in masses):raise ValueError('nonpositive actual body mass')
    if abs(sum(masses)-value['mass_kg'])>1e-7:raise ValueError('actual mass total differs')
    for a in matrices:
        if len(a)!=3 or any(len(row)!=3 for row in a):raise ValueError('3x3 inertia required')
        if any(not math.isfinite(v) for row in a for v in row):raise ValueError('nonfinite inertia')
        if any(abs(a[i][j]-a[j][i])>1e-9 for i in range(3) for j in range(3)):raise ValueError('asymmetric inertia')
        det=(a[0][0]*(a[1][1]*a[2][2]-a[1][2]*a[2][1])-a[0][1]*(a[1][0]*a[2][2]-a[1][2]*a[2][0])
             +a[0][2]*(a[1][0]*a[2][1]-a[1][1]*a[2][0]))
        if a[0][0]<=0 or a[0][0]*a[1][1]-a[0][1]**2<=0 or det<=0:raise ValueError('inertia is not positive definite')


def native(base,report):
    from .adapters.assets import local_bytes
    root=report['native_project']
    if not isinstance(root,str) or not root.startswith('.jarvis-runtime/discovery/vehicle-runs/'):
        raise ValueError('native model path outside owned worker outputs')
    if not report['native_sha256']:raise ValueError('native files missing')
    for name,digest in report['native_sha256'].items():
        if Path(name).name!=name:raise ValueError('native manifest traversal')
        raw=local_bytes(Path(base),root+'/'+name,1_000_000)
        if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('native physical file checksum differs')


def validate_prepared(case,report):
    if report.get('kind')!='prepared_vehicle' or report.get('inputs')!=case.model_dump(mode='json'):
        raise ValueError('actual prepared vehicle differs from input')
    if report.get('solver')!='Chrono::Vehicle' or report.get('version')!='10.0.0':raise ValueError('wrong physical backend')
    inventory(report['physical_inventory'])
    wheels=report['wheel_positions_m']
    if len(wheels)!=4 or any(len(p)!=3 or not all(math.isfinite(v) for v in p) for p in wheels):raise ValueError('four actual wheel positions required')
    if abs(max(p[0] for p in wheels)-min(p[0] for p in wheels)-case.wheelbase_m)>.15:raise ValueError('physical wheelbase differs from visual/case')
    return ['actual instantiated Chrono four-wheel assembly','positive actual masses and positive-definite inertia','actual body/joint inventory']


def study(case,report):
    from .adapters.chrono_vehicle_worker import study_cases
    cases=study_cases(case.model_dump(mode='json'))
    if set(report['reports'])!=set(cases):raise ValueError('study missing uncertainty/refinement executions')
    checks=[];maximum_residual=0.;equilibrium_error=0.
    for name,raw in cases.items():
        child=VehicleCase.model_validate_json(json.dumps(raw));result=report['reports'][name]
        validate_result(child,result)
        for run in result['runs']:
            inventory(run['physical_inventory']);samples=run['samples'];mass=run['physical_inventory']['mass_kg']
            if any(len(row['tire_forces_n'])!=4 or len(row['longitudinal_slip'])!=4 for row in samples):raise ValueError('missing contact/slip diagnostics')
            maximum_residual=max(maximum_residual,max(row['maximum_constraint_residual'] for row in samples))
            if any(row['constraint_residual_count']==0 for row in samples):raise ValueError('joint residuals unavailable')
            if maximum_residual>.005:raise ValueError('joint constraints exceed declared 0.005 mixed-coordinate tolerance')
            acceleration_at=min(c.time_s for c in child.controls if c.throttle>0)
            turning_at=min(c.time_s for c in child.controls if c.steering!=0)
            braking_at=min(c.time_s for c in child.controls if c.braking>0)
            settled=[row for row in samples if acceleration_at-.4<=row['time_s']<=acceleration_at]
            if not settled:raise ValueError('no stationary equilibrium window')
            for row in settled:
                weight=sum(f[2] for f in row['tire_forces_n']);error=abs(weight-mass*9.81)/(mass*9.81)
                equilibrium_error=max(equilibrium_error,error)
                if error>.05 or min(f[2] for f in row['tire_forces_n'])<=0:raise ValueError('gravity/contact equilibrium failed (5% weight balance)')
            before=min(samples,key=lambda r:abs(r['time_s']-turning_at))['speed_m_s']
            braking=min(samples,key=lambda r:abs(r['time_s']-braking_at))['speed_m_s']
            if before<2 or samples[-1]['speed_m_s']>=braking*.8:raise ValueError('acceleration/braking response failed')
            if max(abs(row['front_steering_angle_rad']) for row in samples)<.01 or run['metrics']['maximum_observed_lateral_acceleration_m_s2']<.05:
                raise ValueError('steering/turning not demonstrated')
            if max(abs(s) for row in samples for s in row['longitudinal_slip'])<1e-5:raise ValueError('no measured tire slip response')
    primary=report['reports']['primary'];refined=report['reports']['refined'];errors={}
    for a,b in zip(primary['runs'],refined['runs']):
        for key in a['metrics']:
            relative=abs(a['metrics'][key]-b['metrics'][key])/max(abs(b['metrics'][key]),1.)
            errors[a['variant']+':'+key]=relative
            if relative>.03:raise ValueError('timestep sensitivity exceeds declared 3% metric tolerance')
    return {'checks':['real 4-wheel contact/gravity equilibrium','positive actual inertia/masses','measured steering/acceleration/braking/turning',
        'finite tire force/slip response','actual joint residuals','half-step numerical comparison','declared joint aero uncertainty envelope'],
        'maximum_constraint_residual':maximum_residual,'constraint_residual_units':'mixed generalized Chrono constraint coordinates',
        'maximum_equilibrium_relative_error':equilibrium_error,'timestep_metric_relative_errors':errors,
        'physical_validation':False,'scope':'Numerical verification of declared educational model, not experimental F1 validation.'}
