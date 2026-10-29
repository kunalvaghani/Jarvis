"""Phase 0 baseline of the OLD control stack: in-process decisions only.

Nothing here opens a window, a browser or a model. Live task baselines need the approved
test directory and a clean browser profile, so they are recorded as BLOCKED, not run.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP / 'benchmarks' / 'controlled'))


def timed(function, iterations=2000):
    samples = []
    for _ in range(iterations):
        started = time.perf_counter()
        function()
        samples.append((time.perf_counter() - started) * 1000)
    samples.sort()
    return {'iterations': iterations, 'p50_ms': round(samples[len(samples) // 2], 4),
            'p95_ms': round(samples[int(len(samples) * .95)], 4), 'max_ms': round(samples[-1], 4),
            'mean_ms': round(statistics.fmean(samples), 4)}


def main():
    from jarvis.browser_worker import validate_request
    from jarvis.desktop_actions import explicit_desktop_plan
    from jarvis.execution_adapters import desktop_order
    from jarvis.tools import validate_arguments
    import suite

    goals = ['fill the search field with python venv', 'scroll down', 'press ctrl+s', 'open the file menu',
             'click Save in the dialog', 'click OK', 'open notepad and type hello']
    decisions = {
        'desktop_actions.explicit_desktop_plan (regex intent -> step)':
            timed(lambda: [explicit_desktop_plan(goal) for goal in goals]),
        'tools.validate_arguments (browser_click)':
            timed(lambda: validate_arguments({'action': 'browser_click', 'value': 'Search', 'folder': 'https://example.test/'})),
        'browser_worker.validate_request (click)':
            timed(lambda: validate_request({'operation': 'click', 'value': 'Search', 'url': 'https://example.test/'})),
        'execution_adapters.desktop_order (reads config.json each call)':
            timed(desktop_order, 500),
    }
    plan_hits = {goal: explicit_desktop_plan(goal) is not None for goal in goals}
    tasks = suite.load()
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=APP, capture_output=True, text=True).stdout.strip()
    result = {
        'kind': 'baseline', 'system': 'old control stack', 'date': datetime.now(timezone.utc).isoformat(),
        'revision': revision, 'python': platform.python_version(), 'machine': platform.platform(),
        'in_process_decisions': decisions,
        'explicit_plan_coverage': plan_hits,
        'controlled_tasks': {
            'defined': len(tasks), 'executed': 0, 'passed': 0,
            'status': 'BLOCKED',
            'reason': 'Live desktop/browser baseline needs the approved test directory and a clean test browser '
                      'profile (the owned profile holds Login Data/Cookies). Asked the user in Phase 0.',
            'ids': [task['id'] for task in tasks]},
    }
    out = APP / 'benchmarks' / 'results' / 'baseline.json'
    out.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
