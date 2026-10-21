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
        pkg=types.ModuleType('mcp');pkg.__path__=[]
        svr=types.ModuleType('mcp.server');svr.MCPServer=FakeMCPServer
        with patch.dict(sys.modules,{'mcp':pkg,'mcp.server':svr}):
            filename=Path(__file__).resolve().parents[1]/'server.py'
            spec=importlib.util.spec_from_file_location('jarvis_blender_server_test',filename)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            self.assertEqual(len(module.mcp.tools),len(ACTIONS)+3)
            result=await module.mcp.tools['blender_bridge_health']()
            self.assertFalse(result['reachable']) # Blender isn't running; truthful status
            self.assertEqual(result['commands'],len(ACTIONS))
            with self.assertRaises(TypeError):
                # Tool has concrete Python signature; rejects wrong argument instead of blindly executing a dict.
                await module.mcp.tools['blender_add_cube'](undefined_parameter='a')

if __name__=='__main__':unittest.main()
