"""Prompt 32 fault injection. All processes/files/secrets are owned test fixtures.

Copied from Codex's independent packet (0e3ad47). Only the evidence-copy destinations were changed from
the test file's own folder to tmp_path, so running the suite never writes into tests/; every assertion is unchanged.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import Mock, patch

import pytest


@pytest.mark.parametrize('message', [
    'repair failed api_key=SYNTHETIC_REPAIR_CANARY_0123456789',
    'repair failed Bearer SYNTHETIC_REPAIR_CANARY_0123456789',
])
def test_JRV_32_011_repair_record_omits_synthetic_secret(tmp_path, message):
    from jarvis.recovery import record
    record(tmp_path, message)
    output = tmp_path / '.jarvis-runtime/repairs.jsonl'
    rows = [json.loads(line) for line in output.read_text(encoding='utf-8').splitlines()]
    copy = tmp_path / ('synthetic-api-key-repairs.jsonl' if 'api_key=' in message else 'synthetic-bearer-repairs.jsonl')
    copy.write_bytes(output.read_bytes())  # exact authored fixture output, never a real credential
    assert rows and all('at' in row and 'message' in row for row in rows)
    assert 'SYNTHETIC_REPAIR_CANARY_0123456789' not in output.read_text(encoding='utf-8')


def test_JRV_32_011_launcher_exception_cannot_leak_secret_into_repair_log(tmp_path):
    import jarvis.launcher as launcher
    runtime = tmp_path / '.jarvis-runtime'
    runtime.mkdir()
    def fail_preflight():
        (runtime / 'stop').touch()  # bounded exit after exactly one injected startup failure
        raise ValueError('startup failed api_key=SYNTHETIC_LAUNCHER_CANARY_0123456789')
    with patch.object(launcher, 'BASE', tmp_path), patch.object(launcher, 'RUNTIME', runtime), \
         patch.object(launcher, 'singleton', return_value=Mock()), \
         patch.object(launcher, 'preflight', side_effect=fail_preflight):
        launcher.run()
    output = (runtime / 'repairs.jsonl').read_text(encoding='utf-8')
    (tmp_path / 'synthetic-launcher-repairs.jsonl').write_bytes((runtime / 'repairs.jsonl').read_bytes())
    assert 'SYNTHETIC_LAUNCHER_CANARY_0123456789' not in output


@pytest.mark.skipif(os.name != 'nt', reason='BLOCKED: native Windows ownership test')
def test_JRV_32_005_heartbeat_pid_cannot_retarget_termination_to_sibling_fixture(tmp_path):
    """Only the two test-spawned process trees may be terminated. No name-based kill."""
    import psutil
    from jarvis.harness_process import OwnedJob, hidden_spawn
    from jarvis.launcher import OwnedApplication, session_heartbeat
    jobs = [OwnedJob(), OwnedJob()]
    children = []
    owner = None
    trace = {'scope': 'two hidden disposable Job-owned trees; sibling represents a non-Jarvis app',
             'events': []}
    try:
        for n, job in enumerate(jobs):
            marker = tmp_path / f'fixture-{n}.ready'
            script = 'from pathlib import Path; import sys,time; Path(sys.argv[1]).write_text("ready"); time.sleep(30)'
            child = hidden_spawn(job, subprocess.Popen)([sys.executable, '-c', script, str(marker)],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            children.append(child)
            until = time.monotonic() + 5
            while not marker.exists() and time.monotonic() < until:
                time.sleep(.01)
            assert marker.exists() and child.poll() is None, 'owned fixture failed to start'
            trace['events'].append({'role': 'application' if n == 0 else 'sibling', 'pid': child.pid,
                'created': psutil.Process(child.pid).create_time(), 'name': psutil.Process(child.pid).name()})
        application, sibling = children
        assert application.pid not in [p.pid for p in psutil.Process(sibling.pid).parents()]
        # A matching session value alone must not confer process ownership.
        state = {'session': 'synthetic-session', 'pid': sibling.pid}
        assert session_heartbeat(state, 'synthetic-session') is True
        owner = OwnedApplication(application)
        refused = False
        try:
            owner.attach(state['pid'])
        except (ValueError, OSError):
            refused = True
        trace['heartbeat_pid_accepted'] = not refused and bool(owner.handle)
        owner.terminate()  # production implementation; both possible targets are test-owned
        until = time.monotonic() + 2
        while sibling.poll() is None and time.monotonic() < until:
            time.sleep(.01)
        trace['sibling_alive_after_application_stop'] = sibling.poll() is None
        trace['application_alive_after_stop'] = application.poll() is None
        assert sibling.poll() is None, 'application stop terminated the unrelated sibling fixture'
    finally:
        if owner:
            owner.close()
        for job in jobs:
            job.close()  # Windows Job cleanup is limited to the exact trees created above
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()  # still only the exact Popen handle created above
                child.wait(timeout=5)
        trace['cleanup_complete'] = all(child.poll() is not None for child in children)
        (tmp_path / 'owned-process-trace.json').write_text(json.dumps(trace, indent=2), encoding='utf-8')


@pytest.mark.skipif(os.name != 'nt', reason='BLOCKED: native Windows ownership test')
def test_owned_child_stop_positive_control_preserves_sibling_fixture(tmp_path):
    from jarvis.harness_process import OwnedJob, hidden_spawn
    from jarvis.launcher import OwnedApplication
    jobs = [OwnedJob(), OwnedJob()]
    children = []
    owner = None
    try:
        for n, job in enumerate(jobs):
            marker = tmp_path / f'positive-{n}.ready'
            child = hidden_spawn(job, subprocess.Popen)([sys.executable, '-c',
                'from pathlib import Path; import sys,time; Path(sys.argv[1]).write_text("ready"); time.sleep(30)', str(marker)],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            children.append(child)
            until = time.monotonic() + 5
            while not marker.exists() and time.monotonic() < until:
                time.sleep(.01)
            assert marker.exists() and child.poll() is None
        owner = OwnedApplication(children[0])
        owner.attach(children[0].pid)
        owner.terminate()
        children[0].wait(timeout=5)
        assert children[1].poll() is None, 'ordinary stop must preserve the sibling fixture'
    finally:
        if owner:
            owner.close()
        for job in jobs:
            job.close()
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
