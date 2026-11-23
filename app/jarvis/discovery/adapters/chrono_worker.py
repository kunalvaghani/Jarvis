"""Fixed trusted CPU-only Chrono canonical checks. No generated code execution.

Vehicle API sequence follows Project Chrono 10's BSD-licensed JSON example;
upstream license/provenance is retained with the isolated environment.
This canonical sedan check is not an F1 engineering model or Test A success.
"""
import json
import importlib.machinery
import importlib.util
import math
import os
from pathlib import Path
import sys


def main():
    prefix=Path(sys.executable).parent
    # Conda activation is process-local DLL discovery only, never host PATH edits.
    # SDL compatibility shims use native LoadLibrary internally, so Python's
    # add_dll_directory alone does not give them activation's search path.
    os.environ['PATH']=str(prefix/'Library/bin')+os.pathsep+os.environ.get('PATH','')
    dlls=[os.add_dll_directory(str(p)) for p in (prefix/'Library/bin',prefix/'DLLs') if p.is_dir()]
    # The vendor __init__ opportunistically imports every optional module,
    # including GPU modules. Load only the two CPU submodules via a namespace.
    package=prefix/'Lib/site-packages/pychrono'
    spec=importlib.machinery.ModuleSpec('pychrono',loader=None,is_package=True)
    spec.submodule_search_locations=[str(package)]
    sys.modules['pychrono']=importlib.util.module_from_spec(spec)
    from pychrono import core as chrono
    import pychrono.vehicle as veh
    data=prefix/'Library/data'
    chrono.SetChronoDataPath(str(data)+os.sep)
    veh.SetVehicleDataPath(str(data/'vehicle')+os.sep)
    request=json.loads(sys.stdin.read(16001))
    if request.get('operation') in ('vehicle','study','prepare') and set(request)=={'operation','case','run_id'}:
        sys.path.insert(0,str(Path(__file__).resolve().parent))
        from chrono_vehicle_worker import run,run_study
        result=(run_study(request['case'],chrono,veh,prefix,request['run_id']) if request['operation']=='study'
            else run(request['case'],chrono,veh,prefix,request['run_id'],prepare_only=request['operation']=='prepare'))
        print('JARVIS_CHRONO_RESULT='+json.dumps(result,allow_nan=False),flush=True)
        return
    if request!={'operation':'canonical'}:raise ValueError('Only the reviewed canonical operation is available')
    results=[]
    for dt in (.001,.0005):
        system=chrono.ChSystemNSC()
        system.SetGravitationalAcceleration(chrono.ChVector3d(0,0,0))
        body=chrono.ChBody();body.SetMass(2.0);body.SetInertiaXX(chrono.ChVector3d(1,1,1));system.AddBody(body)
        accumulator=body.AddAccumulator()
        for _ in range(round(.1/dt)):
            body.EmptyAccumulator(accumulator)
            body.AccumulateForce(accumulator,chrono.ChVector3d(4,0,0),body.GetPos(),False)
            system.DoStepDynamics(dt)
        x=body.GetPos().x;vx=body.GetPosDt().x
        if not all(math.isfinite(v) for v in (x,vx)):raise ValueError('nonfinite canonical dynamics')
        results.append({'timestep_s':dt,'duration_s':.1,'x_m':x,'vx_m_s':vx,'analytic_x_m':.01,
                        'analytic_vx_m_s':.2,'position_error_m':abs(x-.01)})
    if (abs(results[0]['vx_m_s']-.2)>1e-9 or abs(results[1]['vx_m_s']-.2)>1e-9
            or results[0]['position_error_m']>.00011
            or results[1]['position_error_m']>results[0]['position_error_m']*.51):
        raise ValueError('force integration or timestep refinement failed')
    vehicle=veh.WheeledVehicle(veh.GetVehicleDataFile('sedan/vehicle/Sedan_Vehicle.json'),chrono.ChContactMethod_NSC)
    vehicle.Initialize(chrono.ChCoordsysd(chrono.ChVector3d(0,0,.5),chrono.ChQuaterniond(1,0,0,0)))
    vehicle.GetSystem().SetCollisionSystemType(chrono.ChCollisionSystem.Type_BULLET)
    for axle in vehicle.GetAxles():
        for wheel in axle.GetWheels():
            tire=veh.ReadTireJSON(veh.GetVehicleDataFile('sedan/tire/Sedan_TMeasyTire.json'))
            vehicle.InitializeTire(tire,wheel,chrono.VisualizationType_NONE)
    terrain=veh.RigidTerrain(vehicle.GetSystem(),veh.GetVehicleDataFile('terrain/RigidPlane.json'))
    terrain.Initialize()
    controls=veh.DriverInputs();controls.m_steering=0;controls.m_throttle=0;controls.m_braking=0
    for _ in range(500):
        t=vehicle.GetSystem().GetChTime();vehicle.Synchronize(t,controls,terrain);terrain.Synchronize(t)
        vehicle.Advance(.002);terrain.Advance(.002)
    pos=vehicle.GetPos();position=[pos.x,pos.y,pos.z]
    wheels=sum(len(axle.GetWheels()) for axle in vehicle.GetAxles())
    if wheels!=4 or not all(math.isfinite(v) for v in position) or not -.2<position[2]<1.0:
        raise ValueError('canonical four-wheel static vehicle failed')
    result={'solver':'Chrono::Vehicle','version':'10.0.0','passed':True,
            'analytic_checks':results,'canonical_vehicle':{'model':'upstream sedan, not F1',
            'wheels':wheels,'duration_s':vehicle.GetSystem().GetChTime(),'position_m':position},
            'gpu_simulation':False,'physical_validation':False,'full_A_acceptance_passed':False}
    print('JARVIS_CHRONO_RESULT='+json.dumps(result,allow_nan=False),flush=True)


if __name__=='__main__':main()
