"""Real local file read through ToolRegistry; synthetic public fixture, no models/UI."""
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import time
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jarvis.task_state import TaskState
from jarvis.tools import ToolRegistry


def main():
    root = Path(sys.argv[1]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if (root / '.jarvis-runtime/agent-events.jsonl').exists():
        raise ValueError('Choose a fresh output directory to preserve earlier traces.')
    fixture = root / 'public-fixture.txt'
    text = 'Jarvis public synthetic routing and readback fixture.\n'
    fixture.write_bytes(text.encode('utf-8'))
    state = TaskState(root)
    state.start('Read the owned public fixture', 'task')
    actions = SimpleNamespace(base=root, config={}, allowed_tools={'read_file'},
                              task_state=state, report=lambda *args: None,
                              _task_folder=lambda folder, cancelled: str(root))
    registry = ToolRegistry(actions)
    timings = []
    for _ in range(20):
        started = time.perf_counter_ns()
        result = registry.execute({'action': 'read_file', 'value': fixture.name, 'folder': '.'}, lambda: False)
        timings.append((time.perf_counter_ns() - started) / 1e6)
        assert result.evidence == text
    assert fixture.read_text(encoding='utf-8') == text
    state.checkpoint('goal_verified', source='disk_readback', evidence='Owned synthetic fixture exactly matched on all twenty reads')
    state.finish('completed', 'Twenty reads independently matched the owned fixture')
    journal = root / '.jarvis-runtime/agent-events.jsonl'
    events = [json.loads(line) for line in journal.read_text(encoding='utf-8').splitlines()]
    completed = [e for e in events if e['event'] == 'tool.completed']
    assert len(completed) == 20
    (root / 'trace.jsonl').write_text(journal.read_text(encoding='utf-8'), encoding='utf-8')
    report = {'date': '2026-10-21', 'scope': 'real ToolRegistry and real disk; synthetic public fixture; no UI/model/connector',
              'reads': 20, 'exact_matches': 20, 'model_calls': 0, 'tool_completion_events': len(completed),
              'p50_ms': statistics.median(timings), 'p95_ms': sorted(timings)[math.ceil(.95 * len(timings)) - 1],
              'fixture_sha256': hashlib.sha256(fixture.read_bytes()).hexdigest()}
    (root / 'summary.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
