"""Native fixture admission/ownership faults; no WinRT action is executed here."""
import io
import queue
import subprocess
from unittest.mock import Mock,patch

import pytest
from tests import native_winrt_fixture as native


def child(ready=native.READY):
    value=Mock()
    value.stdout=io.StringIO(ready)
    value.poll.return_value=0
    value.returncode=0
    value.communicate.return_value=('','')
    return value


def test_unknown_fixture_never_launches_a_process():
    with patch('tests.native_winrt_fixture.subprocess.Popen') as launch:
        with pytest.raises(ValueError,match='reviewed'):
            native.run_fixture('untrusted.module.execute')
        launch.assert_not_called()


def test_bad_readiness_never_admits_assertions_or_retries():
    process=child('unexpected\n');process.poll.return_value=None
    with patch('tests.native_winrt_fixture.subprocess.Popen',return_value=process) as launch, \
         patch('jarvis.harness_process.OwnedJob') as job:
        with pytest.raises(RuntimeError,match='startup'):
            native.run_fixture(next(iter(native.ALLOWED)))
        launch.assert_called_once()
        process.terminate.assert_called_once()
        process.communicate.assert_called_once_with(timeout=2)
        job.return_value.close.assert_called_once()


def test_startup_timeout_reaps_only_owned_process_without_run_or_retry():
    process=child();process.poll.return_value=None
    with patch('tests.native_winrt_fixture.subprocess.Popen',return_value=process) as launch, \
         patch('jarvis.harness_process.OwnedJob') as job, \
         patch('tests.native_winrt_fixture.queue.Queue') as messages:
        messages.return_value.get.side_effect=queue.Empty
        with pytest.raises(subprocess.TimeoutExpired):
            native.run_fixture(next(iter(native.ALLOWED)))
        launch.assert_called_once()
        process.terminate.assert_called_once()
        process.communicate.assert_called_once_with(timeout=2)
        job.return_value.close.assert_called_once()


def test_ready_worker_keeps_original_assertion_deadline_and_nonzero_exit():
    process=child();process.returncode=7;process.communicate.return_value=('','synthetic assertion failed')
    with patch('tests.native_winrt_fixture.subprocess.Popen',return_value=process) as launch, \
         patch('jarvis.harness_process.OwnedJob') as job:
        result=native.run_fixture(next(iter(native.ALLOWED)))
        assert result.returncode==7 and result.stderr=='synthetic assertion failed'
        process.communicate.assert_called_once_with('RUN\n',timeout=15)
        argv=launch.call_args.args[0]
        assert argv[1:3]==['-I','-B']
        assert 'PYTHONPATH' not in launch.call_args.kwargs['env']
        job.return_value.close.assert_called_once()
