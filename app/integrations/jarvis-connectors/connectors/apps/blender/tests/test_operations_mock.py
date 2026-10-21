"""Behavioral bpy simulation. Not a substitute for real Blender integration tests."""
import types
import unittest
from blender_connector.operations import BlenderOperations

class Registry(dict):
    def __iter__(self):return iter(self.values())
    def new(self,*args):
        obj=FakeObject(args[0],args[1] if len(args)>1 else 'MESH')
        self[obj.name]=obj;return obj
    def remove(self,obj,**kwargs):self.pop(obj.name)

class FakeMesh:
    def __init__(self):
        self.name='Mesh';self.vertices=[types.SimpleNamespace(co=[0,0,0]),types.SimpleNamespace(co=[1,0,0]),types.SimpleNamespace(co=[0,1,0])]
        self.edges=[1,2,3];self.polygons=[types.SimpleNamespace(vertices=[0,1,2],use_smooth=False)]
        self.materials=[]
    def update(self):pass
    def copy(self):return self

class FakeObject:
    def __init__(self,name,typ='MESH'):
        self.name=name;self.type=typ;self.location=[0,0,0];self.rotation_euler=[0,0,0];self.scale=[1,1,1]
        self.data=FakeMesh() if typ=='MESH' else None
        self.parent=None;self.children=[];self.modifiers=[];self.constraints=[];self.hide_viewport=False;self.hide_render=False
        self.mode='OBJECT';self.users_collection=[];self.selected=False;self.color=[1,1,1,1]
        self.animation_data=None
    def select_set(self,value):self.selected=value
    def keyframe_insert(self,**kwargs):return True
    def keyframe_delete(self,**kwargs):return True
    def animation_data_clear(self):self.animation_data=None

class FakeScene:
    def __init__(self):
        self.name='Scene';self.objects=Registry();self.frame_current=1;self.frame_start=1;self.frame_end=250
        self.render=types.SimpleNamespace(fps=24,engine='CYCLES',filepath='',resolution_x=1920,resolution_y=1080,
             resolution_percentage=100,image_settings=types.SimpleNamespace(file_format='PNG'))
        self.unit_settings=types.SimpleNamespace(system='METRIC',scale_length=1.0)
        self.gravity=[0,0,-9.81];self.camera=None;self.timeline_markers=Registry()
        self.world=types.SimpleNamespace(color=[0,0,0]);self.collection=types.SimpleNamespace(objects=types.SimpleNamespace(link=lambda x:self.objects.update({x.name:x})))
    def frame_set(self,frame):self.frame_current=frame

class MockBlender:
    def __init__(self):
        scene=FakeScene();cube=FakeObject('Cube');scene.objects['Cube']=cube
        data=types.SimpleNamespace(filepath='',objects=scene.objects,scenes=Registry({'Scene':scene}),
              materials=Registry(),images=Registry(),actions=Registry(),collections=Registry())
        layer=types.SimpleNamespace(objects=types.SimpleNamespace(active=cube))
        self.context=types.SimpleNamespace(scene=scene,object=cube,view_layer=layer,
                   selected_objects=[],window=types.SimpleNamespace(scene=scene))
        self.data=data;self.app=types.SimpleNamespace(version_string='5.2.2',version=(5,2,2),binary_path='blender.exe',background=False)

class OperationsTests(unittest.TestCase):
    def setUp(self):self.b=MockBlender();self.ops=BlenderOperations(self.b)
    def test_health_and_version(self):
        self.assertEqual(self.ops.execute('health')['data']['version'],'5.2.2')
        self.assertEqual(self.ops.execute('version')['data']['version_tuple'],[5,2,2])
    def test_scene_summary(self):
        self.assertEqual(self.ops.execute('scene_summary')['data']['objects'],1)
        self.assertEqual(len(self.ops.execute('list_objects')['data']),1)
    def test_get_object_and_transform(self):
        self.assertEqual(self.ops.execute('get_object',{'name':'Cube'})['data']['type'],'MESH')
        self.ops.execute('set_transform',{'name':'Cube','location':[1,2,3]})
        self.assertEqual(self.ops.execute('get_object',{'name':'Cube'})['data']['location'],[1.,2.,3.])
        self.ops.execute('move_object',{'name':'Cube','offset':[1,0,-1]})
        self.assertEqual(self.ops.execute('get_object',{'name':'Cube'})['data']['location'],[2.,2.,2.])
        self.ops.execute('scale_object',{'name':'Cube','factor':[2,3,1]})
        self.assertEqual(self.ops.execute('get_object',{'name':'Cube'})['data']['scale'],[2.,3.,1.])
    def test_mesh_stats_and_vertices(self):
        self.assertEqual(self.ops.execute('get_mesh_stats',{'name':'Cube'})['data']['triangles'],1)
        self.ops.execute('set_vertex',{'name':'Cube','index':1,'coordinate':[2,0,0]})
        self.assertEqual(self.ops.execute('mesh_vertices',{'name':'Cube'})['data']['vertices'][1],[2.,0.,0.])
        self.ops.execute('transform_vertices',{'name':'Cube','indices':[0,2],'offset':[1,2,3]})
        self.assertEqual(self.ops.execute('mesh_vertices',{'name':'Cube'})['data']['vertices'][0],[1.,2.,3.])
    def test_visibility_and_shading(self):
        self.ops.execute('set_visibility',{'name':'Cube','viewport':True,'render':False})
        self.assertTrue(self.b.data.objects['Cube'].hide_viewport)
        self.ops.execute('smooth_shading',{'name':'Cube','smooth':True})
        self.assertTrue(self.b.data.objects['Cube'].data.polygons[0].use_smooth)
    def test_frame_and_fps(self):
        self.ops.execute('set_frame',{'frame':100})
        self.ops.execute('set_frame_range',{'start':20,'end':140,'fps':30})
        self.assertEqual(self.b.context.scene.render.fps,30)
        self.assertEqual(self.b.context.scene.frame_current,100)
    def test_invalid_parent(self):
        with self.assertRaises(ValueError):self.ops.execute('set_parent',{'child':'Cube','parent':'Cube'})
    def test_missing_objects(self):
        for a,p in [('get_object',{'name':'Missing'}),('delete_object',{'name':'Missing'}),('set_vertex',{'name':'Cube','index':200,'coordinate':[0,0,0]})]:
            with self.subTest(a=a),self.assertRaises(ValueError):self.ops.execute(a,p)
    def test_add_empty(self):
        d=self.ops.execute('add_empty',{'name':'Target','location':[1,0,1]})
        self.assertEqual(d['data']['name'],'Target')
    def test_delete_object(self):
        self.ops.execute('delete_object',{'name':'Cube'})
        self.assertEqual(self.ops.execute('list_objects')['data'],[])
    def test_batch_all_validation_before_mutating(self):
        bad=[{'action':'set_frame','params':{'frame':20}}, {'action':'delete_object','params':{'name':'Cube'}}]
        with self.assertRaises(PermissionError):self.ops.execute('batch',{'steps':bad})
        self.assertEqual(self.b.context.scene.frame_current,1)
    def test_batch_success(self):
        steps=[{'action':'set_frame','params':{'frame':10}},{'action':'set_fps','params':{'fps':25}}]
        result=self.ops.execute('batch',{'steps':steps})['data']
        self.assertEqual(result['completed'],2);self.assertFalse(result['partial'])
    def test_batch_partial_truth(self):
        steps=[{'action':'set_frame','params':{'frame':10}},{'action':'set_scene','params':{'name':'Missing'}}]
        result=self.ops.execute('batch',{'steps':steps})['data']
        self.assertEqual(result['completed'],1);self.assertTrue(result['partial'])
    def test_batch_limit(self):
        with self.assertRaises(ValueError):self.ops.execute('batch',{'steps':[{'action':'set_frame','params':{'frame':i}} for i in range(26)]})
    def test_keyframe(self):
        self.assertEqual(self.ops.execute('insert_keyframe',{'name':'Cube','frame':20})['data']['frame'],20)
    def test_risky_names_cannot_trigger_exec(self):
        for bad in ['eval','os.system','__class__','run_script','open_project']:
            with self.subTest(bad=bad),self.assertRaises(ValueError):self.ops.execute(bad,{})

if __name__=='__main__':unittest.main()
