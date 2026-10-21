"""Real Blender smoke suite. Execute using Blender 5.2+:
blender --background --factory-startup --python tests/run_inside_blender.py
Prints JARVIS_BLENDER_TEST_REPORT: <json> and exits 1 if any action fails.
This MUST be run on an actual Blender installation; ordinary unit tests cannot replace it.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import traceback

ROOT=Path(__file__).resolve().parent
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import bpy
from blender_connector.operations import BlenderOperations


def main():
    tmp=Path(tempfile.mkdtemp(prefix='jarvis-blender-integration-'))
    os.environ['JARVIS_BLENDER_ALLOWED_ROOTS']=str(tmp)
    ops=BlenderOperations()
    report={'version':bpy.app.version_string,'temporary_directory':str(tmp),'checks':[]}
    def step(action,**kwargs):
        try:
            result=ops.execute(action,kwargs)
            report['checks'].append({'name':action,'pass':True,'result':str(result)[:180]})
        except Exception as e:
            report['checks'].append({'name':action,'pass':False,'type':type(e).__name__,'error':str(e)[:350]})
        return report['checks'][-1]['pass']
    # Production-style workflow: model -> shade -> animate -> render -> export.
    step('health');step('scene_summary');step('list_objects');step('list_materials')
    step('add_cube',name='Jarvis_Test_Cube',location=[0,0,1],size=2.0)
    step('get_mesh_stats',name='Jarvis_Test_Cube');step('set_transform',name='Jarvis_Test_Cube',scale=[1,2,1])
    step('add_uv_sphere',name='Jarvis_Sphere',segments=16,rings=8,location=[3,0,0])
    step('add_cylinder',name='Jarvis_Cylinder',vertices=16,radius=1,depth=2,location=[-3,0,0])
    step('add_plane',name='Jarvis_Plane',size=8,location=[0,0,-1])
    step('create_material',name='Jarvis_Gold',color=[0.8,0.55,0.1,1.0],metallic=0.65,roughness=0.22)
    step('assign_material',name='Jarvis_Test_Cube',material='Jarvis_Gold')
    step('set_material',name='Jarvis_Gold',metallic=0.8,roughness=0.35)
    step('list_shader_nodes',material='Jarvis_Gold');step('get_material',name='Jarvis_Gold')
    step('add_bevel',name='Jarvis_Test_Cube',width=0.03,segments=2)
    step('add_subdivision',name='Jarvis_Sphere',levels=1,render_levels=1)
    step('list_modifiers',name='Jarvis_Sphere')
    step('smooth_shading',name='Jarvis_Sphere',smooth=True)
    step('new_collection',name='Jarvis_Test_Collection')
    step('move_to_collection',name='Jarvis_Test_Cube',collection='Jarvis_Test_Collection')
    step('list_collections');step('set_frame_range',start=1,end=24,fps=24)
    step('animate_transform',name='Jarvis_Test_Cube',frame=1,location=[0,0,1])
    step('animate_transform',name='Jarvis_Test_Cube',frame=24,location=[0,0,4])
    step('set_interpolation',name='Jarvis_Test_Cube',mode='LINEAR')
    step('add_text',name='Jarvis_Test_Text',body='JARVIS',size=0.5)
    step('add_bezier_curve',name='Jarvis_Test_Curve',points=[[0,0,0],[1,0,1],[1,1,2]])
    step('add_light',name='Jarvis_Test_Light',type='AREA',energy=450,location=[0,-2,5])
    step('add_camera',name='Jarvis_Test_Camera',location=[5,-7,5],rotation=[1.1,0,0.7])
    step('set_active_camera',name='Jarvis_Test_Camera')
    step('create_geometry_nodes',name='Jarvis_Sphere',group_name='Jarvis_TestGeo')
    step('list_geometry_nodes',name='Jarvis_Sphere')
    step('add_geometry_node',name='Jarvis_Sphere',node_type='GeometryNodeMeshCube')
    step('create_compositor');step('list_compositor_nodes')
    step('set_render_engine',engine='BLENDER_WORKBENCH')
    step('set_render_resolution',width=64,height=64,percentage=100)
    step('set_render_output',filepath=str(tmp/'render.png'))
    step('render_still',filepath=str(tmp/'render.png'))
    step('export_obj',filepath=str(tmp/'model.obj'),selected_only=False)
    step('import_obj',filepath=str(tmp/'model.obj'))
    step('export_gltf',filepath=str(tmp/'model.glb'),selected_only=False)
    step('save_project_copy',filepath=str(tmp/'jarvis_test.blend'))
    # Assert effects rather than trusting API returned without raising.
    report['effects']={
        'render_png_exists':(tmp/'render.png').is_file(),
        'obj_exists':(tmp/'model.obj').is_file(),
        'glb_exists':(tmp/'model.glb').is_file(),
        'blend_exists':(tmp/'jarvis_test.blend').is_file(),
        'cube_has_material':any(mat and mat.name=='Jarvis_Gold' for mat in bpy.data.objects['Jarvis_Test_Cube'].data.materials) if bpy.data.objects.get('Jarvis_Test_Cube') else False,
    }
    report['passed']=sum(x['pass'] for x in report['checks'])
    report['failed']=len(report['checks'])-report['passed']+sum(not v for v in report['effects'].values())
    target=Path(os.environ.get('JARVIS_BLENDER_LIVE_REPORT',str(ROOT/'blender_live_test_results.json')))
    target.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('JARVIS_BLENDER_TEST_REPORT:',str(target),flush=True)
    print(f"JARVIS_BLENDER_TEST_SUMMARY: {report['passed']}/{len(report['checks'])} checks, {len(report['effects'])} effects, {report['failed']} failures",flush=True)
    if report['failed']:raise SystemExit(1)

if __name__=='__main__':main()
