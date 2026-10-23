"""Repeatable PIRAE latency benchmark: the conversation path only (no model, no coding agent).

Measures per-utterance handling time for the acceptance conversation, live requirement changes while
many project tasks are queued, and read-only reference indexing of a generated 2,000-file project.

    python scripts/project_intel_benchmark.py [output.json]
"""
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jarvis.project_intel import snapshot  # noqa: E402
from tests.project_fixtures import admit, close, make, say  # noqa: E402


def timed(env, text):
    started = time.perf_counter()
    reply = say(env, text)
    return (time.perf_counter() - started) * 1000, reply


def percentile(values, q):
    values = sorted(values)
    return round(values[min(len(values) - 1, int(q * len(values)))], 3)


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / 'artifacts' / 'project-intelligence' / 'benchmark.json'
    result = {'measured_at': time.strftime('%Y-%m-%d %H:%M:%S %z'), 'python': sys.version.split()[0],
              'note': 'Owned temporary project roots and queue; deterministic handlers only; coding agent not involved.'}
    with tempfile.TemporaryDirectory() as folder:
        env = make(Path(folder))
        conversation = ['Jarvis, create a new desktop application.', 'Monitor system performance and help optimize my PC.',
                        "Save it in my Projects folder. Use the old monitoring app as reference, but don't modify it.",
                        'Also add battery optimization.', 'Make the interface look futuristic.', 'Actually, use no cloud services.',
                        'Explain your current progress.', "What's left?", 'Finish the safe remaining work overnight.']
        result['acceptance_conversation_ms'] = [{'utterance': t, 'ms': round(timed(env, t)[0], 3)} for t in conversation]
        admit(env)
        changes = []
        for index in range(40):
            changes.append(timed(env, f'Also add exporter number {index} for csv reports')[0])
        admit(env)
        queries = [timed(env, text)[0] for text in ['Explain your current progress.', "What's left?", 'What are the blockers?'] * 5]
        result['requirement_change_ms'] = {'n': len(changes), 'median': round(statistics.median(changes), 3),
                                          'p95': percentile(changes, .95), 'max': round(max(changes), 3),
                                          'tasks_in_plan_at_end': len(env.projects.store.active()['plan']['tasks'])}
        result['status_query_ms'] = {'n': len(queries), 'median': round(statistics.median(queries), 3), 'p95': percentile(queries, .95)}
        close(env)
        big = Path(folder) / 'bigref'
        for index in range(2000):
            path = big / f'pkg{index // 100}' / f'module_{index}.py'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('x = %d\n' % index * 20, encoding='utf-8')
        started = time.perf_counter()
        files, languages, truncated = snapshot(big)
        result['reference_snapshot'] = {'files': len(files), 'truncated': truncated, 'seconds': round(time.perf_counter() - started, 3)}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
