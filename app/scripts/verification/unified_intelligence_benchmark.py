"""Offline routing microbenchmark; no providers, models or desktop actions.

Run before and after against the same interpreter. These timings measure Python
discovery/parser work only, not end-to-end task success or voice latency.
"""
import argparse
import json
import math
from pathlib import Path
import statistics
import sys
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jarvis.capabilities import rank_tools
from jarvis.commands import parse
from jarvis.tools import SPECS

QUERIES = ('Debug Python script', 'Research official documentation', 'Find files in a folder',
           'Play first video on YouTube', 'browser_click', 'blender scene', 'runtime capabilities')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    specs = {s.name: s for s in SPECS}
    rows, selections = [], {}
    # A fixed available set prevents host credentials from affecting results.
    with patch('jarvis.toolkits.available', return_value=True):
        for query in QUERIES:
            selections[query] = rank_tools(specs, query)
        for label, operation in (
                ('tool_search', lambda: [rank_tools(specs, q) for q in QUERIES]),
                ('command_parse', lambda: [parse(q) for q in ('pause', 'volume up', 'open chrome')])):
            for _ in range(10):
                operation()
            samples = []
            for _ in range(100):
                start = time.perf_counter_ns()
                operation()
                samples.append((time.perf_counter_ns() - start) / 1e6)
            rows.append({'operation': label, 'iterations': len(samples),
                         'p50_ms': statistics.median(samples),
                         'p95_ms': sorted(samples)[math.ceil(.95 * len(samples)) - 1]})
    result = {'date': '2026-10-21', 'scope': 'offline warm Python microbenchmark',
              'tool_count': len(specs), 'queries_per_search_sample': len(QUERIES),
              'timings': rows, 'selections': selections,
              'model_calls': 0, 'external_actions': 0}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'selections'}))


if __name__ == '__main__':
    main()
