"""Pure contracts/build checks; no mechanics proof slots or solver invocation."""
import copy
import json
import xml.etree.ElementTree as ET
import pytest
from jarvis.discovery.model.mechanics import MechanicsCase,validate_result
from jarvis.discovery.adapters.mechanics_worker import model_xml


def raw():
    return {'units':'SI','bodies':[{'id':'moving','parent':None,'position_m':[0,0,2],
        'shape_center_m':[0,0,-1],'shape':'sphere','size_m':[.05],'mass_kg':1,
        'joint':'hinge','axis':[0,1,0],'initial_position':.1,'damping':0,
        'source_refs':['synthetic unit fixture']}],
        'gravity_m_s2':[0,0,-9.81],'duration_s':1,'timestep_s':.001,'sample_every':10,
        'assumptions':['fixture; not measured hardware']}


@pytest.mark.parametrize('field,value', [('mass_kg',None),('mass_kg',0),('mass_kg',float('nan')),
    ('axis',[0,0,0]),('size_m',[.05,.06]),('shape_center_m',[0,0,10000]),
    ('parent','missing'),('initial_position',None),('source_refs',[])])
def test_unresolved_invalid_or_unbounded_physics_rejected(field,value):
    value0=raw();value0['bodies'][0][field]=value
    with pytest.raises(ValueError):MechanicsCase.model_validate_json(json.dumps(value0))


def test_no_xml_plugins_code_or_arbitrary_meshes():
    for field in ('xml','plugin','script','mesh_file','approved'):
        value=raw();value[field]='untrusted'
        with pytest.raises(ValueError):MechanicsCase.model_validate_json(json.dumps(value))
    value=raw();value['bodies'][0]['id']='bad"/><include file="x'
    with pytest.raises(ValueError):MechanicsCase.model_validate_json(json.dumps(value))


def test_native_model_has_real_joint_offset_mass_and_explicit_no_contact():
    case=MechanicsCase.model_validate_json(json.dumps(raw()))
    root=ET.fromstring(model_xml(case.model_dump(mode='json')))
    geom=root.find('.//geom');joint=root.find('.//joint')
    assert geom.attrib['pos']=='0.0 0.0 -1.0' and geom.attrib['mass']=='1.0'
    assert geom.attrib['contype']=='0' and joint.attrib['type']=='hinge'
    assert root.find('option').attrib['integrator']=='RK4'


def test_cycles_duplicate_ids_sample_and_step_budget_fail_closed():
    for mutate in (
        lambda v:v['bodies'].append(copy.deepcopy(v['bodies'][0])),
        lambda v:v.update(duration_s=10,timestep_s=.0001,sample_every=1),
        lambda v:v.update(duration_s=.0015),
        lambda v:v.update(duration_s=.011,sample_every=10),
        lambda v:v['bodies'][0].update(parent='moving')):
        value=raw();mutate(value)
        with pytest.raises(ValueError):MechanicsCase.model_validate_json(json.dumps(value))


def test_nonfinite_wrong_version_and_missing_trajectory_are_not_verified():
    case=MechanicsCase.model_validate_json(json.dumps(raw()))
    for report in ({'solver':'mujoco','version':'wrong'},
                   {'solver':'mujoco','version':'3.17.0','samples':[]}):
        with pytest.raises(ValueError):validate_result(case,report)
