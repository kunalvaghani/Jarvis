"""Import every generated tool under simulated MCP decorator in absence of SDK."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
from blender_connector.catalog import ACTIONS

class FakeMCPServer:
    def __init__(self,name):self.name=name;self.tools={}
    def tool(self):
        def deco(func):
            if func.__name__ in self.tools:raise ValueError('Duplicate tool')
            self.tools[func.__name__]=func
            return func
        return deco
    def run(self):raise RuntimeError('must not start in test')

class MCPToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_discovery_and_signed_call(self):
        filename=Path(__file__).resolve().parents[1]/'server.py'
        spec=importlib.util.spec_from_file_location('jarvis_blender_server_test',filename)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        connector=module.BlenderConnector(allow_write=True)
        self.assertEqual(len(connector.describe()),len(ACTIONS)+3)
        result=connector.call('blender_bridge_health',{})
        self.assertTrue(result['isError']) # No bridge configured; never claim live health.
        with self.assertRaises(TypeError):
            connector.blender_add_cube(undefined_parameter='a')

if __name__=='__main__':unittest.main()
