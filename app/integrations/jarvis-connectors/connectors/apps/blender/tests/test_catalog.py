import inspect
import math
import unittest
from blender_connector.catalog import ACTIONS,SAFE_BATCH,validate_action,MISSING
from blender_connector.operations import _vec,_safe_number,_path,BlenderOperations
from unittest.mock import patch
import tempfile
from pathlib import Path

class CatalogTests(unittest.TestCase):
    def test_action_count_and_uniqueness(self):
        self.assertEqual(len(ACTIONS),200)
        self.assertEqual(len(set(ACTIONS)),200)
        self.assertTrue({'mesh','scene','nodes','material','file','render','studio','assets'} <= {a.group for a in ACTIONS.values()})
    def test_every_action_has_real_handler(self):
        for name,spec in ACTIONS.items():
            with self.subTest(name=name):
                self.assertTrue(hasattr(BlenderOperations,'_do_'+spec.group))
                self.assertNotEqual(BlenderOperations.__dict__['_do_'+spec.group].__code__.co_consts,())
                self.assertIn(spec.risk,{'read','write','filesystem','destructive'})
    def test_all_action_names_have_dispatch_paths(self):
        import ast
        from pathlib import Path
        source=(Path(__file__).resolve().parents[1]/'blender_connector'/'operations.py').read_text()
        strings={node.value for node in ast.walk(ast.parse(source))
                 if isinstance(node,ast.Constant) and isinstance(node.value,str)}
        shorthand={'import_'+kind for kind in ('obj','fbx','gltf','stl','usd','alembic')}
        shorthand|={'export_'+kind for kind in ('obj','fbx','gltf','stl','usd','alembic')}
        self.assertFalse(set(ACTIONS)-strings-shorthand)
    def test_validate_defaults_all(self):
        for name,spec in ACTIONS.items():
            with self.subTest(name=name):
                provided={key:self._sample(field.kind) for key,field in spec.fields.items() if field.default is MISSING}
                self.assertEqual(set(validate_action(name,provided)),set(spec.fields))
    @staticmethod
    def _sample(kind):return {'str':'Hello','int':1,'float':1.0,'bool':True,'list':[],'dict':{},'json':'example'}[kind]
    def test_reject_unknown_action(self):
        with self.assertRaisesRegex(ValueError,'Unknown Blender action'):validate_action('exec_python',{})
    def test_reject_extra_arg(self):
        with self.assertRaisesRegex(ValueError,'Unknown parameter'):validate_action('add_cube',{'evil':'__import__'})
    def test_required_arg(self):
        with self.assertRaisesRegex(ValueError,'Missing required'):validate_action('rename_object',{})
    def test_type_confusion(self):
        cases=[('set_frame',{'frame':True}),('set_frame',{'frame':1.3}),('add_cube',{'size':float('nan')}),('add_cube',{'name':'x'*3000}),('add_mesh',{'name':'x','vertices':'oops','faces':[]})]
        for name,p in cases:
            with self.subTest(name=name,p=p),self.assertRaises(ValueError):validate_action(name,p)
    def test_json_custom_property_valid_and_nested_invalid(self):
        self.assertEqual(validate_action('set_custom_property',{'name':'Cube','key':'tag','value':['gold',42,True]})['value'],['gold',42,True])
        with self.assertRaises(ValueError):validate_action('set_custom_property',{'name':'Cube','key':'tag','value':[float('nan')]})
        with self.assertRaises(ValueError):validate_action('set_custom_property',{'name':'Cube','key':'tag','value':{'nested':object()}})
    def test_batch_excludes_risky_and_recursion(self):
        self.assertNotIn('batch',SAFE_BATCH)
        for name in ['delete_object','save_project','purge_orphans','render_still','import_fbx']:
            self.assertNotIn(name,SAFE_BATCH)
    def test_vec_validation(self):
        self.assertEqual(_vec([0,1,2]),(0.,1.,2.))
        for v in ([1,2],[1,float('nan'),2],[True,0,0],['2',1,0],[1,1,1,2]):
            with self.subTest(v=v),self.assertRaises(ValueError):_vec(v)
    def test_num_validation(self):
        for n in (-1,11,float('nan'),float('inf'),True):
            with self.subTest(n=n),self.assertRaises(ValueError):_safe_number(n,0,10,'foo')
    def test_filesystem_denied_without_root(self):
        with patch.dict('os.environ',{},clear=True),self.assertRaises(PermissionError):_path(str(Path(tempfile.gettempdir())/'a.blend'),'write')
    def test_filesystem_root_and_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'safe';root.mkdir()
            with patch.dict('os.environ',{'JARVIS_BLENDER_ALLOWED_ROOTS':str(root)}):
                self.assertEqual(_path(str(root/'work.blend'),'write',{'.blend'}),str(root/'work.blend'))
                with self.assertRaises(PermissionError):_path(str(root/'../evil.blend'),'write')
                with self.assertRaises(ValueError):_path('relative.blend','write')
                with self.assertRaises(ValueError):_path(str(root/'shell.py'),'write',{'.blend'})
                with self.assertRaises(FileNotFoundError):_path(str(root/'missing.blend'),'read',{'.blend'})
    def test_primitive_not_root(self):
        with self.assertRaises(ValueError):_path('http://evil/blend','read')

if __name__=='__main__':unittest.main()
