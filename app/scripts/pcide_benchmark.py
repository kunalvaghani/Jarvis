"""Repeatable PCIDE benchmark (owned temporary state).

Default: recorded GitHub responses with a fixed simulated network delay, so parallel vs serial retrieval,
cache reuse and "coding start delay" are comparable run to run. `--live` additionally performs ONE small,
read-only research pass against the public GitHub API (unauthenticated; counts against its rate limit).

    python scripts/pcide_benchmark.py [output.json] [--live]
"""
import json
import os
import statistics
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import psutil  # noqa: E402

from jarvis.code_intel import project_facts  # noqa: E402
from jarvis.pcide import ParallelCodeIntelligence  # noqa: E402
from tests.test_pcide import FakeGitHub, GOOD, react_project  # noqa: E402


class SlowGitHub(FakeGitHub):
    def __init__(self, delay):
        super().__init__()
        self.delay = delay

    def __call__(self, url, params=None, raw=False):
        time.sleep(self.delay)
        return super().__call__(url, params, raw)


def engine(base, http, budget=None):
    actions = SimpleNamespace(base=base, config={}, memory=SimpleNamespace(vault=base / 'vault'), report=Mock(), ingress=None,
                              project_intel=None)
    return ParallelCodeIntelligence(actions, {'enabled': True, 'research_budget': budget or {}}, http=http)


def live_http():
    import requests
    session = requests.Session()
    session.headers['User-Agent'] = 'jarvis-pcide-benchmark'
    def get(url, params=None, raw=False):
        response = session.get(url, params=params, timeout=15)
        response.raise_for_status()
        return response.text if raw else response.json()
    return get


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    out = Path(args[0]) if args else ROOT / 'artifacts' / 'code-intelligence' / 'benchmark.json'
    process = psutil.Process(os.getpid())
    result = {'measured_at': time.strftime('%Y-%m-%d %H:%M:%S %z'), 'python': sys.version.split()[0], 'model_calls': 0,
              'note': 'Recorded GitHub fixtures with a 120 ms simulated request delay unless marked live.'}
    with tempfile.TemporaryDirectory() as folder:
        base = Path(folder)
        rss = process.memory_info().rss
        project = react_project(base)
        for index in range(300):  # A mid-sized project for the symbol index.
            (project / 'src' / f'module_{index}.py').write_text(f'def helper_{index}(value):\n    """Format value {index}."""\n    return value\n',
                                                                 encoding='utf-8')
        intel = engine(base, SlowGitHub(.12))
        for index in range(500):  # A populated verified library.
            intel.memory.add(name=f'Component{index}', description=f'reusable widget number {index} for dashboards', category='ui-component',
                             language='typescript', framework='react', origin=f'local:{index}', source=f'export const C{index} = {index};',
                             license='project', scope='global')
        timings = []
        for attempt in range(5):
            started = time.perf_counter()
            research = intel.prepare(project, 'Add a floating navigation dock and live cpu usage charts')
            timings.append((time.perf_counter() - started) * 1000)
        result['memory_first_prepare_ms'] = {'n': 5, 'first_cold': round(timings[0], 2), 'median': round(statistics.median(timings), 2),
                                             'max': round(max(timings), 2), 'library_items': 500, 'project_files': 302,
                                             'local_candidates': len(intel.broker.candidates(research=research))}
        # Coding start delay: before = synchronous research ahead of the coder; after = local lookup only.
        intents = intel.planner.plan('floating navigation dock with animated cards and interactive charts', project_facts(project))
        for concurrency in (1, 3):
            fresh = engine(base / f'c{concurrency}', SlowGitHub(.12), {'concurrency': concurrency})
            research = fresh.broker.create(project, 'dock', intents)
            started = time.perf_counter()
            fresh.run_research(research)
            elapsed = time.perf_counter() - started
            result[f'research_wall_seconds_concurrency_{concurrency}'] = round(elapsed, 3)
            if concurrency == 3:
                cached = fresh.broker.create(project, 'dock', intents)
                started = time.perf_counter()
                fresh.run_research(cached)
                result['research_wall_seconds_cached_repeat'] = round(time.perf_counter() - started, 3)
                result['cache_hit_rate'] = fresh.report()['cache_hit_rate']
                result['research_spent'] = fresh.broker.get(research)['spent']
            fresh.close()
        coding_started = threading.Event()
        def coder():
            coding_started.set()
        started = time.perf_counter()
        research = intel.prepare(project, 'build an animated dock')
        threading.Thread(target=intel.run_research, args=(research,)).start()  # Research lane runs in parallel.
        threading.Thread(target=coder).start()
        coding_started.wait(5)
        after = (time.perf_counter() - started) * 1000
        result['coding_start_delay_ms'] = {'before_synchronous_research_estimate': round(result['research_wall_seconds_concurrency_3'] * 1000, 1),
                                           'after_memory_first': round(after, 2),
                                           'note': 'Before: the coder waited for research to finish (same simulated network). After: only the local lookup.'}
        time.sleep(result['research_wall_seconds_concurrency_3'] + .5)
        page = base / 'site'
        page.mkdir()
        (page / 'index.html').write_text(GOOD, encoding='utf-8')
        started = time.perf_counter()
        gate = intel.gate.evaluate(page, str(page / 'index.html'), out=base / 'qa')
        result['design_gate'] = {'status': gate['status'], 'render': gate['render']['status'], 'seconds': round(time.perf_counter() - started, 2),
                                 'screenshots': len(list((base / 'qa').glob('*.png')))}
        result['rss_mb'] = {'before': round(rss / 1048576, 1), 'after': round(process.memory_info().rss / 1048576, 1),
                            'note': 'Sampled whole-process RSS including Playwright driver objects; not peak.'}
        intel.close()
        if '--live' in sys.argv:
            live = engine(base / 'live', live_http(), {'queries': 2, 'repositories': 2, 'files': 6})
            target = react_project(base, 'live-dash')
            started = time.perf_counter()
            research = live.prepare(target, 'animated dock navigation react')
            live.run_research(research)
            rows = live.broker.candidates(research=research)
            result['live_github_research'] = {
                'seconds': round(time.perf_counter() - started, 2), 'spent': live.broker.get(research)['spent'],
                'notes': live.broker.get(research)['notes'],
                'candidates': [{'name': r['name'], 'state': r['state'], 'origin': r['origin'], 'license_status': r.get('license_status'),
                                'score': (r.get('ranking') or {}).get('score')} for r in rows]}
            live.close()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
