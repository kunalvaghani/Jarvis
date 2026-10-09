"""Behavioral coverage for relocation, recovery and hidden launch shortcuts."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

from jarvis.paths import APP_ROOT, artifact_path, config_file, linked, state_file
from jarvis.projects import Projects, project_paths
from jarvis.task_state import TaskState
from jarvis_bootstrap import restore_entrypoints


class ProjectStructureTests(unittest.TestCase):
    def test_config_values_keep_application_root_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            config_file(base).parent.mkdir()
            config_file(base).write_text(json.dumps({'files_root':'JarvisFiles','model_path':'models/speech'}))
            options = json.loads(config_file(base).read_text())
            self.assertEqual(base/options['files_root'], base/'JarvisFiles')
            self.assertEqual(base/options['model_path'], base/'models/speech')

    def test_memory_and_task_writes_work_in_fresh_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            project = base/'example'; project.mkdir()
            Projects(base, [base]).remember(project)
            self.assertIn(str(project), json.loads(state_file('project_memory.json',base).read_text()))
            task = TaskState(base); task.start('inspect a fixture','task')
            self.assertEqual(json.loads(state_file('task_state.json',base).read_text())['current']['goal'],'inspect a fixture')
            self.assertFalse((base/'task_state.json').exists())

    def test_future_outputs_use_groups_and_existing_groups_are_stable(self):
        for name,group in [('next-check.json','reports'),('next-preview.png','media'),
                           ('qwen-run-20990101','training'),('coding-transfer-20990101','training'),
                           ('development-dashboard','projects'),('development-research','research'),
                           ('worker.log','logs'),('stream-fixture.py','fixtures')]:
            with self.subTest(name=name):
                self.assertEqual(artifact_path(APP_ROOT,name),APP_ROOT/'artifacts'/group/name)
        self.assertEqual(artifact_path(APP_ROOT,'reports/next-check.json'),APP_ROOT/'artifacts/reports/next-check.json')
        with self.assertRaises(ValueError):artifact_path(APP_ROOT,'../outside.json')

    def test_dependency_metadata_in_other_projects_keeps_original_filename(self):
        from jarvis.repo_acquisition import acquire
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            project = base/'project'; project.mkdir()
            (project/'example.py').write_text('def add(a, b):\n    return a + b\n')
            requirements = b'packaging==24.2\n'
            (project/'requirements.txt').write_bytes(requirements)
            snapshot = acquire(str(project), base/'vault')
            self.assertIn('requirements.txt', snapshot['hashes'])
            self.assertEqual((Path(snapshot['source'])/'requirements.txt').read_bytes(), requirements)

    def test_bootstrap_restores_corrupt_path_helper_without_deleting_it(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for name in ('__init__.py','paths.py','recovery.py','launcher.py'):
                source=base/'jarvis'/name; saved=base/'.jarvis-runtime/sources/jarvis'/name
                source.parent.mkdir(parents=True,exist_ok=True);saved.parent.mkdir(parents=True,exist_ok=True)
                source.write_text('valid = True\n');saved.write_text('valid = True\n')
            (base/'jarvis/paths.py').write_text('def invalid(\n')
            restore_entrypoints(base)
            self.assertEqual((base/'jarvis/paths.py').read_text(),'valid = True\n')
            damaged=list((base/'.jarvis-runtime/damaged').glob('*paths.py'))
            self.assertEqual(len(damaged),1)
            self.assertEqual(damaged[0].read_text(),'def invalid(\n')

    @unittest.skipUnless(os.name=='nt','Windows directory junction behavior')
    def test_project_scan_skips_compatibility_junction(self):
        alias=APP_ROOT.parent/'InsTAREELS'
        if not alias.exists():self.skipTest('Compatibility junction is local and optional on fresh checkouts')
        self.assertTrue(linked(alias))
        self.assertEqual(alias.resolve(),APP_ROOT.resolve())
        projects=project_paths([APP_ROOT.parent])
        self.assertEqual(len(projects),len({str(p.resolve()).casefold() for p in projects}))
        self.assertEqual(config_file(alias).read_bytes(),config_file(APP_ROOT).read_bytes())

    @unittest.skipUnless(os.name=='nt','Windows hidden launch shortcuts')
    def test_start_and_stop_shortcuts_execute_only_fixture_bootstrap(self):
        if not (APP_ROOT/'.venv/Scripts/pythonw.exe').exists():self.skipTest('Local Python environment is not installed')
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            result=subprocess.run(['cmd','/c','mklink','/J',str(base/'.venv'),str(APP_ROOT/'.venv')],
                capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode:self.fail('Cannot construct the isolated launcher fixture: '+result.stderr.decode(errors='replace'))
            (base/'jarvis_bootstrap.py').write_text('import json,sys\nfrom pathlib import Path\n'
                'Path(__file__).with_name("stopped.json" if "--stop" in sys.argv else "started.json").write_text(json.dumps(sys.argv[1:]))\n')
            for shortcut,marker,expected in [('Start Jarvis.cmd','started.json',[]),('Stop Jarvis.cmd','stopped.json',['--stop'])]:
                shutil.copy2(APP_ROOT/shortcut,base/shortcut)
                result=subprocess.run(['cmd','/c',str(base/shortcut)],cwd=base,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
                self.assertEqual(result.returncode,0)
                deadline=time.monotonic()+10
                while not (base/marker).exists() and time.monotonic()<deadline:time.sleep(.05)
                self.assertTrue((base/marker).exists(),shortcut+' did not reach the fixture')
                self.assertEqual(json.loads((base/marker).read_text()),expected)
