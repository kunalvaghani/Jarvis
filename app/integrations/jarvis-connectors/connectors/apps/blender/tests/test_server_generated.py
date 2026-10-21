import ast
import unittest
from pathlib import Path
from blender_connector.catalog import ACTIONS,MISSING

SERVER=Path(__file__).resolve().parents[1]/'server.py'
class ServerGenerationTests(unittest.TestCase):
    def setUp(self):
        self.nodes=ast.parse(SERVER.read_text()).body
        klass=next(n for n in self.nodes if isinstance(n,ast.ClassDef))
        self.functions={n.name:n for n in klass.body if isinstance(n,ast.FunctionDef)}
    def test_every_command_exposed(self):
        self.assertEqual(set(self.functions),{'blender_'+a for a in ACTIONS}|{'blender_bridge_health','blender_wait_job','blender_job_status'})
    def test_individual_signed_mcp_tools(self):
        for name,action in ACTIONS.items():
            fn=self.functions['blender_'+name]
            with self.subTest(name=name):
                self.assertEqual({arg.arg for arg in fn.args.kwonlyargs},set(action.fields)|{'expected_scope','host_authorization'})
                self.assertEqual(len(fn.decorator_list),1)
                self.assertEqual(fn.decorator_list[0].func.id,'tool')
                self.assertTrue(any(k.arg=='access' for k in fn.decorator_list[0].keywords))
                self.assertIn(action.risk,ast.get_docstring(fn))
    def test_no_arbitrary_interpreter(self):
        content=SERVER.read_text()
        for bad in ['eval(', 'exec(', 'subprocess.run(', 'os.system(']:self.assertNotIn(bad,content)
    def test_no_duplicate_names(self):
        klass=next(n for n in self.nodes if isinstance(n,ast.ClassDef))
        names=[n.name for n in klass.body if isinstance(n,ast.FunctionDef)]
        self.assertEqual(len(names),len(set(names)))

if __name__=='__main__':unittest.main()
