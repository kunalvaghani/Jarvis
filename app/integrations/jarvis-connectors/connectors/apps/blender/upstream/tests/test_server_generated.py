import ast
import unittest
from pathlib import Path
from blender_connector.catalog import ACTIONS,MISSING

SERVER=Path(__file__).resolve().parents[1]/'server.py'
class ServerGenerationTests(unittest.TestCase):
    def setUp(self):
        self.nodes=ast.parse(SERVER.read_text()).body
        self.functions={n.name:n for n in self.nodes if isinstance(n,ast.AsyncFunctionDef)}
    def test_every_command_exposed(self):
        self.assertEqual(set(self.functions),{'blender_'+a for a in ACTIONS}|{'blender_bridge_health','blender_wait_job','blender_job_status'})
    def test_individual_signed_mcp_tools(self):
        for name,action in ACTIONS.items():
            fn=self.functions['blender_'+name]
            with self.subTest(name=name):
                self.assertEqual({arg.arg for arg in fn.args.args},set(action.fields))
                self.assertEqual(len(fn.decorator_list),1)
                self.assertEqual(fn.decorator_list[0].func.value.id,'mcp')
                self.assertEqual(fn.decorator_list[0].func.attr,'tool')
                self.assertIn(action.risk,ast.get_docstring(fn))
    def test_no_arbitrary_interpreter(self):
        content=SERVER.read_text()
        for bad in ['eval(', 'exec(', 'subprocess.run(', 'os.system(']:self.assertNotIn(bad,content)
    def test_no_duplicate_names(self):
        names=[n.name for n in self.nodes if isinstance(n,ast.AsyncFunctionDef)]
        self.assertEqual(len(names),len(set(names)))

if __name__=='__main__':unittest.main()
