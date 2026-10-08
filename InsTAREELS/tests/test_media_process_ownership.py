import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

import psutil
from jarvis.harness_process import OwnedJob
from jarvis.island_media import MediaJobs


class MediaProcessOwnershipTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows venv redirector ownership')
    def test_timeout_disposes_actual_owned_redirector_child_without_replaying(self):
        spawn = subprocess.Popen
        safety_job = OwnedJob()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / 'pid.txt'
            script = root / 'owned_slow_media.py'
            script.write_text('import os,time\nfrom pathlib import Path\n'
                              'Path("pid.txt").write_text(str(os.getpid()))\ntime.sleep(30)\n')
            children = []
            def launch(argv, **kwargs):
                # Replace only the fixture's argv, keeping production ownership
                # and cleanup. An outer safety job prevents leaks if it fails.
                process = spawn([sys.executable, str(script)], **kwargs)
                safety_job.attach(process)
                children.append(process)
                return process
            jobs = MediaJobs(Mock(), root)
            try:
                with patch('jarvis.island_media.subprocess.Popen', side_effect=launch):
                    jobs._run('pause')
                self.assertEqual(len(children), 1)
                self.assertTrue(marker.exists(), 'Actual owned interpreter never started')
                pid = int(marker.read_text())
                deadline = time.monotonic() + 2
                while psutil.pid_exists(pid) and time.monotonic() < deadline:
                    time.sleep(.05)
                self.assertFalse(psutil.pid_exists(pid), 'Redirector child survived timeout')
                self.assertIn('no retry', jobs.report.call_args[0][1]['error'])
                self.assertIsNone(jobs.process)
                self.assertIsNone(jobs.job)
                self.assertFalse(jobs.busy)
            finally:
                jobs.close()
                safety_job.close()
                for child in children:
                    child.wait(timeout=3)


if __name__ == '__main__':
    unittest.main()
