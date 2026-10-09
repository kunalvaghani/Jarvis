import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from jarvis.development_tools import DevelopmentTools, binary
from jarvis.development_browser import validate_tests

class ToolsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.tools=DevelopmentTools(self.root)
        self.addCleanup(self.tools.close)

    def test_real_command_exit_and_bounded_cancellation(self):
        result=self.tools.run(self.root,[sys.executable,'-c','print("ok")'],lambda:False)
        self.assertEqual(result['output'].strip(),'ok')
        self.assertEqual(result['exit_code'],0)
        start=time.monotonic()
        with self.assertRaises(ValueError):
            self.tools.run(self.root,[sys.executable,'-c','import time;time.sleep(20)'],lambda:False,.1)
        self.assertLess(time.monotonic()-start,3)
        self.assertIsNone(self.tools.command)

    def test_real_owned_preview_close_and_repair_does_not_restart(self):
        (self.root/'dist').mkdir()
        (self.root/'dist/index.html').write_text('<h1>Owned</h1>')
        url=self.tools.start_preview(self.root,'expo',lambda:False)
        process=self.tools.preview['process']
        self.assertTrue(self.tools.healthy())
        self.assertIn('127.0.0.1',url)
        process.kill();process.wait()
        self.assertFalse(self.tools.healthy())
        self.assertTrue(self.tools.repair())
        self.assertIsNone(self.tools.preview)
        self.assertTrue((self.root/'.jarvis-runtime/repairs.jsonl').exists())
        self.tools.close()
        with self.assertRaises(ValueError): self.tools.start_preview(self.root,'expo',lambda:False)

    def test_owned_scope_and_tests(self):
        with self.assertRaises(ValueError): binary(self.root,'vite')
        with self.assertRaises(ValueError): self.tools.inspect(self.root,'http://example.com',[],lambda:False)
        with self.assertRaises(ValueError): validate_tests([{'name':'bad','steps':[{'action':'eval','value':'secret'}]}])
        with self.assertRaises(ValueError): validate_tests([{'name':'bad','steps':[{'action':'press','value':'Control+O'}]}])
        self.assertEqual(validate_tests([{'name':'actual assertion','steps':[{'action':'assert_text','value':'Saved'}]}]),1)

    def test_dependency_change_uses_install_and_rejects_nonregistry_sources(self):
        manifest={'dependencies':{'react':'19.3.0'}}
        (self.root/'package.json').write_text(json.dumps(manifest))
        (self.root/'package-lock.json').write_text(json.dumps({'packages':{'':manifest}}))
        from unittest.mock import patch
        with patch.object(self.tools,'run',return_value={}) as run:
            self.tools.install(self.root,lambda:False)
            self.assertEqual(run.call_args.args[1][1],'ci')
            manifest['dependencies']['react']='19.2.3'
            (self.root/'package.json').write_text(json.dumps(manifest))
            self.tools.install(self.root,lambda:False)
            self.assertEqual(run.call_args.args[1][1],'install')
            manifest['dependencies']['react']='https://example.com/arbitrary.tgz'
            (self.root/'package.json').write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):self.tools.install(self.root,lambda:False)
            self.assertEqual(run.call_count,2)
