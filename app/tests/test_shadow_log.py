"""Shadow log: written only when on, redacted, size-bounded, and it never raises into a task."""
import json

import pytest

from jarvis.telemetry import shadow

ON = {'telemetry': {'shadow_log': True}}


def lines(tmp_path, decider='resolver'):
    path = shadow.path(decider, tmp_path)
    return [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines()] if path.exists() else []


def test_off_writes_nothing(tmp_path):
    assert shadow.record({}, 'resolver', 'a', 'a', base=tmp_path) is False
    assert shadow.record({'telemetry': {'shadow_log': 'true'}}, 'resolver', 'a', 'a', base=tmp_path) is False
    assert lines(tmp_path) == []


def test_rows_and_agreement(tmp_path):
    assert shadow.record(ON, 'resolver', {'name': 'Kunal'}, {'name': 'Kunal'}, 't1', 3.456, base=tmp_path)
    shadow.record(ON, 'resolver', 'notepad', 'wordpad', base=tmp_path)
    shadow.record(ON, 'resolver', 'x', 'x', base=tmp_path)
    rows = lines(tmp_path)
    assert [r['agree'] for r in rows] == [True, False, True]
    assert rows[0]['task'] == 't1' and rows[0]['latency_ms'] == 3.46
    assert shadow.agreement('resolver', tmp_path) == {'decider': 'resolver', 'total': 3, 'agreed': 2, 'rate': 0.6667}
    assert shadow.agreement('system1', tmp_path)['rate'] is None


def test_secrets_are_redacted(tmp_path):
    shadow.record(ON, 'resolver', 'password=hunter2hunter2', 'api_key: sk-abcdefghijklmnopqrstuvwx', base=tmp_path)
    text = shadow.path('resolver', tmp_path).read_text(encoding='utf-8')
    assert 'hunter2hunter2' not in text and 'sk-abcdefghijklmnopqrstuvwx' not in text


def test_rotation_bounds_the_file(tmp_path, monkeypatch):
    monkeypatch.setattr(shadow, 'MAX_BYTES', 600)
    for n in range(20):
        shadow.record(ON, 'resolver', 'x' * 50, n, base=tmp_path)
    path = shadow.path('resolver', tmp_path)
    assert path.stat().st_size <= 600
    assert path.with_suffix('.jsonl.1').exists()


def test_errors_never_raise(tmp_path):
    shadow.path('resolver', tmp_path).mkdir(parents=True)  # A directory where the log should be.
    assert shadow.record(ON, 'resolver', 'a', 'b', base=tmp_path) is False
    assert shadow.record(ON, 'Bad Name!', 'a', 'b', base=tmp_path) is False
    with pytest.raises(ValueError):
        shadow.path('../escape')
