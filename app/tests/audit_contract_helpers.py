"""Shared executable boundary assertions; all paths are owned pytest fixtures."""
import csv
import json
from pathlib import Path
import queue
import threading
from types import SimpleNamespace
from unittest.mock import Mock, patch
import pytest


class ReadyVoiceOutput:
    """An owned ready frame followed by an open pipe until explicit disposal."""
    def __init__(self):
        self.rows=queue.Queue()
        self.rows.put('{"ready":true}\n')

    def readline(self,limit=-1):
        return self.rows.get()

    def close(self):
        self.rows.put('')


def trace_contract(root):
    from jarvis.tools import ToolRegistry
    actions=SimpleNamespace(base=root, config={})
    registry=ToolRegistry(actions)
    with patch.object(registry,'_execute',return_value=SimpleNamespace(backend='files')):
        registry.execute({'action':'open','value':'FAKE_PRIVATE_TOKEN'},lambda:False)
    with patch.object(registry,'_execute',side_effect=OSError('FAKE_PRIVATE_TOKEN')):
        with pytest.raises(OSError):registry.execute({'action':'open','value':'FAKE_PRIVATE_TOKEN'},lambda:False)
    wire=(root/'.jarvis-runtime/agent-events.jsonl').read_text(encoding='utf-8')
    rows=[json.loads(line) for line in wire.splitlines()]
    assert 'FAKE_PRIVATE_TOKEN' not in wire
    assert [row['event'] for row in rows]==['tool.started','tool.completed','tool.started','tool.failed']
    assert rows[0]['call_id']==rows[1]['call_id'] and rows[2]['call_id']==rows[3]['call_id']
    assert rows[0]['call_id']!=rows[2]['call_id'] and len(rows[0]['call_id'])==32


def benchmark_contract(module):
    root=Path(__file__).resolve().parents[1]/'artifacts/jarvis-audit/modules'/module
    rows=list(csv.DictReader((root/'benchmarks.csv').open(encoding='utf-8')))
    for mode in ('before','after'):
        selected=[row for row in rows if row['mode']==mode]
        counts={kind:sum(row['kind']==kind for row in selected) for kind in {row['kind'] for row in selected}}
        assert sorted(counts.values())==[5,20]
        assert all(float(row['milliseconds'])>=0 and int(row['rss_bytes'])>0 for row in selected)


def recovery_contract(root):
    from jarvis.recovery import restart_thread
    from jarvis.task_state import TaskState
    state=TaskState(root);state.start('Uncertain fixture','task')
    state.checkpoint('uncertain_external_write',action='gmail_api_send',target='fixture')
    old=Mock();old.is_alive.return_value=False
    owner=SimpleNamespace(closed=threading.Event(),thread=old,cancel=Mock(),queue=queue.Queue(),
        task_active=True,task_state=state,_run=Mock())
    owner.queue.put('uncertain external write')
    replacement=Mock()
    with patch('jarvis.recovery.threading.Thread',return_value=replacement):
        assert restart_thread(owner,'Owned fixture worker')
    assert owner.queue.empty() and not owner.task_active
    assert state.resume_blocker(state.snapshot()) and state.snapshot()['status']=='paused'
    replacement.start.assert_called_once();owner._run.assert_not_called()
    owner.closed.set()
    assert not restart_thread(owner,'Owned fixture worker')


def read_fault(error):
    from jarvis.task_recovery import retry_read
    read=Mock(side_effect=error);waits=[]
    with pytest.raises(type(error)):retry_read(read,read_only=True,wait=waits.append)
    assert read.call_count==5 and len(waits)==4 and sum(waits)==pytest.approx(1.5)
    write=Mock()
    with pytest.raises(ValueError):retry_read(write,read_only=False)
    write.assert_not_called()
