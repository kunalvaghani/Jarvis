"""Timing ledger: observes only. Off = straight call-through and no file; on = correct rows; never breaks a task."""
import importlib.util
import json
from pathlib import Path
import sys
import threading
import time

import pytest

from jarvis.telemetry import ledger

APP = Path(__file__).resolve().parents[1]
ON = {'telemetry': {'timing_ledger': True}, 'brain': {'model_hierarchy': {'reasoning_model': 'qwen3.5:9b'}}}
OFF = {'telemetry': {'timing_ledger': False}}


class Client:
    def __init__(self, result=None, error=None):
        self.result, self.error = result, error

    @ledger.timed_model
    def _request_once(self, operation, cancelled, **data):
        if self.error:
            raise self.error
        return self.result


class Registry:
    @ledger.timed_tool
    def execute(self, step, cancelled, activate=None):
        if step.get('action') == 'boom':
            raise ValueError('tool failed')
        ledger.pause(.01)
        return 'done ' + step['action']


class Actions:
    def __init__(self, config, base, body):
        self.config, self.base, self.body = config, base, body

    @ledger.timed_task
    def execute(self, command, cancelled=lambda: False):
        return self.body()


class Command:
    kind = 'task'


def read(base):
    path = Path(base) / '.jarvis-runtime' / 'logs' / 'timing-ledger.jsonl'
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()] if path.exists() else []


def two_step_task():
    plan = {'model_used': 'qwen3.5:9b', 'inference': {'prompt_tokens': 700, 'prompt_s': 1.5, 'output_tokens': 40,
                                                      'output_s': .8}}
    Client(plan)._request_once('plan', lambda: False)
    Registry().execute({'action': 'app_open'}, lambda: False)
    Client({'model_used': 'qwen3.5:2b'})._request_once('decide', lambda: False)
    Registry().execute({'action': 'app_act'}, lambda: False)
    return 'answer'


def test_off_writes_nothing_and_returns_the_same_result(tmp_path):
    result = Actions(OFF, tmp_path, two_step_task).execute(Command())
    assert result == 'answer'
    assert read(tmp_path) == []
    marker = object()
    assert Client(marker)._request_once('plan', lambda: False) is marker  # Outside a task: no ledger.
    with pytest.raises(KeyError):
        Client(error=KeyError('x'))._request_once('plan', lambda: False)


def test_on_records_model_tool_wait_and_a_task_summary(tmp_path):
    assert Actions(ON, tmp_path, two_step_task).execute(Command()) == 'answer'
    rows = read(tmp_path)
    kinds = [r['type'] for r in rows]
    assert kinds == ['model', 'wait', 'tool', 'model', 'wait', 'tool', 'task']
    assert len({r['task'] for r in rows}) == 1
    summary = rows[-1]
    assert summary['outcome'] == 'completed' and summary['kind'] == 'task'
    assert summary['model_calls'] == 2 and summary['calls_9b'] == 1 and summary['steps'] == 2
    assert summary['prompt_tokens'] == 700 and summary['output_tokens'] == 40
    assert summary['wait_s'] >= .02 and summary['tool_s'] >= summary['wait_s']
    assert rows[0]['model'] == 'qwen3.5:9b' and rows[0]['prompt_s'] == 1.5
    assert rows[2]['action'] == 'app_open' and rows[2]['ok'] is True


def test_failures_are_recorded_and_still_raised(tmp_path):
    def failing():
        Client(error=ValueError('model down'))._request_once('plan', lambda: False)
    with pytest.raises(ValueError, match='model down'):
        Actions(ON, tmp_path, failing).execute(Command())
    rows = read(tmp_path)
    assert rows[0]['error'] == 'ValueError'
    assert rows[-1]['outcome'] == 'failed: ValueError'

    def tool_fails():
        Registry().execute({'action': 'boom'}, lambda: False)
    with pytest.raises(ValueError):
        Actions(ON, tmp_path, tool_fails).execute(Command())
    assert read(tmp_path)[-2] == {**read(tmp_path)[-2], 'type': 'tool', 'action': 'boom', 'ok': False}


def test_a_broken_ledger_file_never_reaches_the_task(tmp_path):
    blocked = tmp_path / '.jarvis-runtime' / 'logs' / 'timing-ledger.jsonl'
    blocked.mkdir(parents=True)  # A directory where the file should be: every write fails.
    assert Actions(ON, tmp_path, two_step_task).execute(Command()) == 'answer'


def test_nested_commands_belong_to_the_outer_task(tmp_path):
    outer = Actions(ON, tmp_path, lambda: Actions(ON, tmp_path, two_step_task).execute(Command()))
    outer.execute(Command())
    assert sum(1 for r in read(tmp_path) if r['type'] == 'task') == 1


def test_concurrent_tasks_stay_separate(tmp_path):
    def task(n):
        def body():
            for _ in range(n):
                Registry().execute({'action': f'step{n}'}, lambda: False)
        Actions(ON, tmp_path, body).execute(Command())
    threads = [threading.Thread(target=task, args=(n,)) for n in (2, 3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    rows = read(tmp_path)
    summaries = sorted(r['steps'] for r in rows if r['type'] == 'task')
    assert summaries == [2, 3]
    for summary in (r for r in rows if r['type'] == 'task'):
        tools = [r for r in rows if r['type'] == 'tool' and r['task'] == summary['task']]
        assert len({r['action'] for r in tools}) == 1 and len(tools) == summary['steps']


def test_hook_overhead_outside_a_task_is_negligible():
    client = Client('x')
    started = time.perf_counter()
    for _ in range(2000):
        client._request_once('plan', lambda: False)
    assert (time.perf_counter() - started) / 2000 < .001


def test_pause_sleeps_the_same_time_with_the_ledger_off():
    started = time.perf_counter()
    ledger.pause(.05)
    assert time.perf_counter() - started >= .045  # Windows sleeps can end a timer tick early.


def load_report():
    spec = importlib.util.spec_from_file_location('ledger_report', APP / 'benchmarks' / 'ledger_report.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules['ledger_report'] = module
    spec.loader.exec_module(module)
    return module


def test_report_percentiles_and_means(tmp_path):
    report = load_report()
    assert report.percentile([], 50) is None
    assert report.percentile([5.0, 1.0, 3.0, 2.0, 4.0], 50) == 3.0
    assert report.percentile([float(v) for v in range(1, 21)], 95) == 19.0
    rows = [{'type': 'task', 'total_s': t, 'model_s': t / 2, 'calls_9b': 1, 'steps': 3, 'outcome': 'completed',
             'at': '2026-10-31T00:00'} for t in (10.0, 20.0, 30.0)] + [{'type': 'tool', 'at': '2026-10-31T00:00'}]
    summary = report.summarise(rows)
    assert summary['tasks'] == 3 and summary['p50_s'] == 20.0 and summary['p95_s'] == 30.0
    assert summary['mean_model_s'] == 10.0 and summary['mean_calls_9b'] == 1.0 and summary['mean_steps'] == 3.0
    assert summary['mean_wait_s'] is None and summary['outcomes'] == {'completed': 3}
    path = tmp_path / 'l.jsonl'
    path.write_text('\n'.join(json.dumps(r) for r in rows) + '\nnot json\n', encoding='utf-8')
    assert report.summarise(report.rows(path, '2026-10-31'))['tasks'] == 3
    assert report.summarise(report.rows(path, '2026-11-01'))['tasks'] == 0


def test_real_hooks_are_installed():
    from jarvis.actions import Actions as RealActions
    from jarvis.brain import BrainClient
    from jarvis.tools import ToolRegistry
    for method in (RealActions.execute, BrainClient._request_once, ToolRegistry.execute):
        assert getattr(method, '__wrapped__', None) is not None, method
