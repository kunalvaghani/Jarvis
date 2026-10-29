"""Per-action latency of route executors on this machine (Phase 2 gate, Part IV targets).

Browser: real installed Chrome against the local D1 site, throwaway profile. Each sample is
action + its verification, measured warm after one untimed warm-up. Results are appended to
benchmarks/results/route-latency.json with the date and revision.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP / 'benchmarks' / 'sites' / 'd1'))


def summary(samples):
    samples = sorted(samples)
    pick = lambda q: round(samples[min(len(samples) - 1, int(len(samples) * q))], 1)  # noqa: E731
    return {'n': len(samples), 'p50_ms': pick(.5), 'p90_ms': pick(.9), 'p95_ms': pick(.95),
            'max_ms': round(samples[-1], 1), 'mean_ms': round(statistics.fmean(samples), 1)}


def browser(iterations, headless):
    import re
    from server import Site
    from jarvis.control.policy import Policy
    from jarvis.control.routes.browser import BrowserExecutor
    from jarvis.control.types import Action, Expectation, Route

    site = Site()
    base, _ = site.start()
    root = Path(tempfile.mkdtemp(prefix='jarvis-latency-'))
    policy = Policy(allowed_roots=(root,), loopback_allow=frozenset({('127.0.0.1', p) for p in site.ports}))
    ex = BrowserExecutor(root / 'profile', policy, root / 'downloads', headless=headless)
    started = time.perf_counter()
    ex.start()
    cold_start = (time.perf_counter() - started) * 1000
    out = {'cold_start_ms': round(cold_start, 1)}
    try:
        def act(name, target=None, expectation=None, **params):
            return ex.act(Action(name, name, Route.BROWSER, params=params, target=target, expectation=expectation))

        nav, read, click, fill = [], [], [], []
        for i in range(iterations + 1):
            t = time.perf_counter()
            assert act('navigate', url=base + '/forms.html').ok
            nav.append((time.perf_counter() - t) * 1000)
            t = time.perf_counter()
            tree = ex.read_page(filter='interactive').text
            read.append((time.perf_counter() - t) * 1000)
            counter = re.search(r'button "Count 0"[^\[]*\[(ref_\d+)\]', tree).group(1)
            name = re.search(r'textbox "Name"[^\[]*\[(ref_\d+)\]', tree).group(1)
            t = time.perf_counter()
            result = act('left_click', counter, Expectation('probe_equals', {
                'what': 'text', 'args': {'selector': '#counter'}, 'expected': 'Count 1'}))
            assert result.ok and result.verified, result.text
            click.append((time.perf_counter() - t) * 1000)
            t = time.perf_counter()
            assert act('form_input', name, value=f'Ada {i}').verified
            fill.append((time.perf_counter() - t) * 1000)
        # Drop the warm-up iteration.
        out.update({'navigate_local': summary(nav[1:]), 'read_page_interactive': summary(read[1:]),
                    'ref_click_plus_verify': summary(click[1:]), 'form_input_plus_readback': summary(fill[1:])})
    finally:
        ex.close()
        site.stop()
    return out


def main():
    iterations = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    headless = '--headful' not in sys.argv
    revision = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=APP, capture_output=True, text=True).stdout.strip()
    record = {'date': datetime.now(timezone.utc).isoformat(), 'revision': revision, 'python': platform.python_version(),
              'route': 'browser', 'chrome': 'installed (channel=chrome)', 'headless': headless,
              'results': browser(iterations, headless)}
    path = APP / 'benchmarks' / 'results' / 'route-latency.json'
    history = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    history.append(record)
    path.write_text(json.dumps(history, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
