"""Simulated registration and invocation; not a real MCP wire protocol test."""
import importlib.util
import inspect
import sys
import types
from pathlib import Path
import unittest
from unittest.mock import AsyncMock

class FakeFastMCP:
    def __init__(self,name):self.name=name;self.registered={}
    def tool(self):
        def decorator(fn):
            if fn.__name__ in self.registered:raise AssertionError('Duplicate tool')
            self.registered[fn.__name__]=fn
            return fn
        return decorator

class MCPWrapperTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved={x:sys.modules.get(x) for x in ('mcp','mcp.server','mcp.server.fastmcp')}
        for name in cls.saved:sys.modules[name]=types.ModuleType(name)
        sys.modules['mcp.server.fastmcp'].FastMCP=FakeFastMCP
        src=Path(__file__).resolve().parents[1]/'upstream_server.py'
        spec=importlib.util.spec_from_file_location('youtube_generated_server_test',str(src))
        module=importlib.util.module_from_spec(spec)
        sys.modules[spec.name]=module
        spec.loader.exec_module(module)
        cls.module=module
    @classmethod
    def tearDownClass(cls):
        for name,module in cls.saved.items():
            if module is None:sys.modules.pop(name,None)
            else:sys.modules[name]=module
        sys.modules.pop('youtube_generated_server_test',None)
    async def test_all_tools_registered_uniquely(self):
        registered=self.module.mcp.registered
        self.assertEqual(len(registered),103)
        self.assertEqual(len(registered),len(set(registered)))
    async def test_callable_tool_signatures(self):
        sig=inspect.signature(self.module.mcp.registered['youtube_set_volume'])
        self.assertIn('percent',sig.parameters)
        self.assertEqual(str(sig.parameters['percent'].annotation),"'float'")
    async def test_backwards_compatible_alias_uses_real_method(self):
        old=self.module.connector.next_video
        self.module.connector.next_video=AsyncMock(return_value={'ok':True,'video_id':'test'})
        try:
            result=await self.module.mcp.registered['youtube_next']()
            self.assertTrue(result['ok'])
            self.module.connector.next_video.assert_awaited_once()
        finally:self.module.connector.next_video=old
    async def test_new_command_passes_arguments(self):
        old=self.module.connector.seek
        self.module.connector.seek=AsyncMock(return_value={'ok':True})
        try:
            await self.module.mcp.registered['youtube_seek'](42.5)
            self.module.connector.seek.assert_awaited_once_with(seconds=42.5)
        finally:self.module.connector.seek=old
