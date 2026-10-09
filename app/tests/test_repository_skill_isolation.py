"""Real kernel isolation checks; an unavailable runtime is an explicit skip."""
from pathlib import Path
import tempfile
import threading
import time
import unittest

from jarvis.repo_sandbox import RepositorySandbox
from jarvis.repository_skills import RepositorySkills


class RepositoryIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime=RepositorySandbox();status=cls.runtime.status(refresh=True)
        if not status['available']:raise unittest.SkipTest('Actual repository isolation unavailable: '+status['reason'])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'source';self.root.mkdir()

    def run_function(self,source,symbol='probe',arguments=None,timeout=15,cancelled=lambda:False):
        (self.root/'probe.py').write_text(source)
        entity={'module':'probe','symbol':symbol,'kind':'function','import_root':'.'}
        return self.runtime.run(self.root,{'entity':entity,'arguments':arguments or {}},cancelled,timeout)[0]

    def test_actual_nonroot_mount_cgroup_and_seccomp_probe(self):
        value,_=self.runtime.run(self.root,{'probe':True})
        self.assertEqual(value['uid'],65534)
        self.assertTrue(value['mounts_verified'] and value['cgroups_verified'] and value['seccomp_installed'])

    def test_repository_cannot_read_host_environment_or_home(self):
        source='import os\nfrom pathlib import Path\ndef probe():\n try: host_home=Path("/root/.ssh").exists()\n except PermissionError: host_home=False\n return {"environment":dict(os.environ),"host_home":host_home}\n'
        self.assertEqual(self.run_function(source),{'environment':{},'host_home':False})

    def test_enum_annotations_convert_json_inside_isolation(self):
        source='from __future__ import annotations\nfrom enum import Enum\nclass Mode(Enum):\n FAST="fast"\ndef probe(mode:Mode, modes:list[Mode]): return [mode.name,modes[0].name]\n'
        self.assertEqual(self.run_function(source,arguments={'mode':'fast','modes':['fast']}),['FAST','FAST'])

    def test_kernel_denies_shell_and_internet_socket(self):
        source='''def probe():
 import socket,subprocess
 result=[]
 for action in (lambda:subprocess.run(["/bin/sh","-c","echo bad"]),lambda:socket.socket(socket.AF_INET,socket.SOCK_STREAM)):
  try:action();result.append("unsafe-success")
  except OSError as error:result.append(error.errno)
 return result
'''
        self.assertEqual(self.run_function(source),[1,1])

    def test_readonly_source_and_external_root_write_blocked(self):
        source='''def probe():
 result=[]
 for name in ("/source/marker.txt","/unauthorized-marker.txt"):
  try:open(name,"w").write("bad");result.append("unsafe-success")
  except OSError:result.append("blocked")
 return result
'''
        self.assertEqual(self.run_function(source),['blocked','blocked'])
        self.assertFalse((self.root/'marker.txt').exists())

    def test_malicious_import_never_runs_during_analysis_and_is_blocked_in_execution(self):
        (self.root/'evil.py').write_text('from pathlib import Path\nPath("/source/marker.txt").write_text("bad")\ndef harmless(): return 1\n')
        registry=RepositorySkills(Path(self.temp.name)/'jarvis')
        registry.learn(str(self.root));self.assertFalse((self.root/'marker.txt').exists())
        skill=next(r for r in registry.search('.') if r['symbol']=='harmless')
        with self.assertRaisesRegex(ValueError,'PermissionError|OSError'):
            registry.check(skill['id'],{},lambda *a:None)
        self.assertEqual(registry.get(skill['id'])['state'],'QUARANTINED')
        self.assertFalse((Path(registry.get(skill['id'])['snapshot']['source'])/'marker.txt').exists())

    def test_async_execution_and_default_relative_package_imports(self):
        package=self.root/'pkg';package.mkdir();(package/'__init__.py').write_text('')
        (package/'helper.py').write_text('VALUE=7\n')
        (package/'work.py').write_text('from .helper import VALUE\nimport asyncio\nasync def sleep_value(delay:float=0):\n await asyncio.sleep(delay)\n return VALUE\n')
        entity={'module':'pkg.work','symbol':'sleep_value','kind':'function','import_root':'.'}
        self.assertEqual(self.runtime.run(self.root,{'entity':entity,'arguments':{}})[0],7)

    def test_missing_dependency_and_exception_contracts(self):
        with self.assertRaisesRegex(ValueError,'ModuleNotFoundError'):
            self.run_function('import nonexistent_jarvis_test_dependency\ndef probe(): return 1\n')
        with self.assertRaisesRegex(ValueError,'ZeroDivisionError'):
            self.run_function('def probe(): return 1/0\n')

    def test_memory_and_output_budgets(self):
        with self.assertRaisesRegex(ValueError,'MemoryError|CLI failed'):
            self.run_function('def probe(): return bytearray(400*1024*1024)\n')
        with self.assertRaisesRegex(ValueError,'output budget'):
            self.run_function('def probe(): return "x"*40000\n')

    def test_timeout_and_cancellation_stop_owned_container(self):
        source='import asyncio\nasync def probe(): await asyncio.sleep(30)\n'
        with self.assertRaisesRegex(ValueError,'timed out'):
            self.run_function(source,timeout=2)
        stop=threading.Event();errors=[]
        def work():
            try:self.run_function(source,cancelled=stop.is_set)
            except ValueError as error:errors.append(str(error))
        thread=threading.Thread(target=work);thread.start();time.sleep(1);stop.set();thread.join(12)
        self.assertFalse(thread.is_alive());self.assertTrue(errors)


if __name__=='__main__':unittest.main()
