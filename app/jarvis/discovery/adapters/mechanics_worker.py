"""Owned fixed CPU worker. No generated code, XML input, plugin or external mesh."""
import json
import os
import sys
import time
import xml.etree.ElementTree as ET


def model_xml(case):
    root=ET.Element('mujoco',model='jarvis_primitive_assembly')
    ET.SubElement(root,'compiler',angle='radian')
    ET.SubElement(root,'option',timestep=str(case['timestep_s']),
                  gravity=' '.join(map(str,case['gravity_m_s2'])),integrator='RK4')
    world=ET.SubElement(root,'worldbody');nodes={None:world}
    for spec in case['bodies']:
        body=ET.SubElement(nodes[spec['parent']],'body',name=spec['id'],pos=' '.join(map(str,spec['position_m'])))
        nodes[spec['id']]=body
        if spec['joint']=='free':ET.SubElement(body,'freejoint',name=spec['id']+'_joint')
        elif spec['joint']!='fixed':
            ET.SubElement(body,'joint',name=spec['id']+'_joint',type=spec['joint'],
                axis=' '.join(map(str,spec['axis'])),damping=str(spec['damping']))
        # The shape offset determines COM and inertia about its joint; contact is not modeled.
        ET.SubElement(body,'geom',name=spec['id']+'_geom',type=spec['shape'],
            size=' '.join(map(str,spec['size_m'])),pos=' '.join(map(str,spec['shape_center_m'])),
            mass=str(spec['mass_kg']),contype='0',conaffinity='0')
    return ET.tostring(root,encoding='unicode')


def solve(case):
    started=time.process_time()
    import mujoco
    xml=model_xml(case);model=mujoco.MjModel.from_xml_string(xml);data=mujoco.MjData(model)
    for body in case['bodies']:
        if body['joint'] in ('hinge','slide'):
            j=mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_JOINT,body['id']+'_joint')
            data.qpos[model.jnt_qposadr[j]]=body['initial_position']
    ids={b['id']:mujoco.mj_name2id(model,mujoco.mjtObj.mjOBJ_BODY,b['id']) for b in case['bodies']}
    rows=[]
    for step in range(round(case['duration_s']/case['timestep_s'])+1):
        if step%100==0 and time.process_time()-started>=18:
            raise TimeoutError('owned mechanics CPU loop limit reached')
        if step:
            mujoco.mj_step(model,data)
        if step%case['sample_every']==0:
            mujoco.mj_forward(model,data)
            rows.append({'t_s':float(data.time),'qpos':data.qpos.tolist(),'qvel':data.qvel.tolist(),
                'positions_m':{name:data.xpos[i].tolist() for name,i in ids.items()}})
    return {'solver':'mujoco','version':mujoco.__version__,'cpu_s':time.process_time()-started,
            'mjcf':xml,'samples':rows,'contacts_modeled':False,'physical_validation':False,
            'evidence_status':'SIMULATION_PASSED_WITH_ASSUMPTIONS'}


def main():
    # The parent validates the strict schema; this fixed worker never accepts code or XML.
    raw=sys.stdin.buffer.read(32001)
    if len(raw)>32000:raise ValueError('bounded structured input required')
    case=json.loads(raw)
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
    def guard(event,args):
        if event in ('socket.connect','socket.sendto','socket.bind','subprocess.Popen','os.system','os.startfile'):
            raise PermissionError('owned numeric worker denies network and process creation')
    sys.addaudithook(guard)
    print(json.dumps(solve(case),allow_nan=False,separators=(',',':')))


if __name__=='__main__':main()
