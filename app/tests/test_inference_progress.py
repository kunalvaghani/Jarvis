"""Progress is observational and cannot extend deadlines or replay inference."""
import json,queue
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import pytest
from jarvis.brain import BrainClient


@pytest.mark.parametrize('callback_fails',[False,True])
def test_waiting_progress_does_not_change_one_dispatch_or_result(callback_fails):
    client=BrainClient(Path('.'),{})
    process=SimpleNamespace(poll=lambda:None,stdin=Mock())
    client.process=process;client.close=Mock()
    responses=Mock();responses.get.side_effect=[queue.Empty(),json.dumps({'result':{'verified':True}})]
    client.responses=responses
    client.progress_callback=Mock(side_effect=RuntimeError('UI unavailable') if callback_fails else None)
    with patch('jarvis.brain.time.monotonic',side_effect=[0,1,16,17]):
        assert client._request_once('verify',lambda:False)=={'verified':True}
    assert client.progress_callback.call_count==1
    assert '16s elapsed' in client.progress_callback.call_args.args[0]
    assert process.stdin.write.call_count==1
    client.close.assert_not_called()


def test_progress_cannot_extend_original_timeout():
    client=BrainClient(Path('.'),{'timeout_seconds':30})
    process=SimpleNamespace(poll=lambda:None,stdin=Mock());client.process=process;client.close=Mock()
    client.responses=Mock();client.responses.get.side_effect=queue.Empty()
    client.progress_callback=Mock()
    with patch('jarvis.brain.time.monotonic',side_effect=[0,1,16,10000]):
        with pytest.raises(ValueError,match='timed out'):client._request_once('verify',lambda:False)
    assert client.progress_callback.call_count==1
    assert process.stdin.write.call_count==1
    client.close.assert_called_once()
