from tests.layout_fixtures import fixture_path
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import psutil
from jarvis import launcher


class LauncherReadinessTests(unittest.TestCase):
    def test_timeout_is_reported_as_incomplete_not_missing_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (fixture_path(base/'config/runtime_manifest.json')).write_text(json.dumps({'main_imports': ['json'], 'brain_imports': ['json']}))
            python = base/'.venv/Scripts/python.exe'; python.parent.mkdir(parents=True); python.touch()
            model = base/'models/fixture/model.bin'; model.parent.mkdir(parents=True); model.touch()
            with patch.object(launcher, 'BASE', base), patch.object(launcher, 'check_imports',
                    side_effect=subprocess.TimeoutExpired(['python'], 60)):
                row = launcher.runtime_status({'model_path': 'models/fixture', 'speech': {'enabled': False}}, check_services=False)
            self.assertEqual(row['status'], 'check_incomplete')
            self.assertEqual(row['missing'], [])
            self.assertEqual(row['incomplete'], [{'component': 'main_imports', 'error_type': 'TimeoutExpired'}])

    def test_timed_out_import_tree_is_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); marker = base/'owned-pid.txt'
            (base/'slow_owned_import.py').write_text('import os,time\nfrom pathlib import Path\n'
                'Path("owned-pid.txt").write_text(str(os.getpid()))\ntime.sleep(30)\n')
            with patch.object(launcher, 'BASE', base), self.assertRaises(subprocess.TimeoutExpired):
                launcher.check_imports(sys.executable, ['slow_owned_import'], timeout=2)
            self.assertTrue(marker.exists(), 'Fixture never started; this would not verify process disposal')
            pid = int(marker.read_text())
            deadline = time.monotonic()+3
            while psutil.pid_exists(pid) and time.monotonic()<deadline: time.sleep(.05)
            self.assertFalse(psutil.pid_exists(pid), 'Owned interpreter survived its timed-out import check')
