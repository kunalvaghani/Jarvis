"""Summarise the per-step timing ledger (.jarvis-runtime/logs/timing-ledger.jsonl).

    python benchmarks/ledger_report.py [--since 2026-10-30T00:00] [--ledger PATH] [--json]

Per task: total, model, tool, wait and other seconds; prompt tokens; 9B calls; steps. Across tasks: p50/p95
latency and means. The before/after instrument for every upgrade v2 phase.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import sys
from typing import Any, Dict, Iterable, List, Optional

APP = Path(__file__).resolve().parents[1]
LEDGER = APP / '.jarvis-runtime' / 'logs' / 'timing-ledger.jsonl'
FIELDS = ('total_s', 'model_s', 'tool_s', 'wait_s', 'other_s', 'prompt_tokens', 'output_tokens', 'model_calls',
          'calls_9b', 'steps')


def percentile(values: List[float], q: float) -> Optional[float]:
    """Nearest-rank percentile (q in 0..100); None for no data."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, -(-len(ordered) * q // 100))  # ceil(n*q/100), at least 1
    return ordered[int(rank) - 1]


def rows(path: Path, since: str = '') -> Iterable[Dict[str, Any]]:
    try:
        with path.open(encoding='utf-8') as lines:
            for line in lines:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and str(row.get('at', '')) >= since:
                    yield row
    except OSError:
        return


def summarise(data: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    tasks = [r for r in data if r.get('type') == 'task']
    out: Dict[str, Any] = {'tasks': len(tasks)}
    if not tasks:
        return out
    totals = [float(t.get('total_s', 0)) for t in tasks]
    out['p50_s'], out['p95_s'] = percentile(totals, 50), percentile(totals, 95)
    for name in FIELDS:
        values = [float(t[name]) for t in tasks if isinstance(t.get(name), (int, float))]
        out['mean_' + name] = round(statistics.fmean(values), 3) if values else None
    out['outcomes'] = {o: sum(1 for t in tasks if t.get('outcome') == o) for o in sorted({str(t.get('outcome')) for t in tasks})}
    return out


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--ledger', type=Path, default=LEDGER)
    parser.add_argument('--since', default='')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    summary = summarise(rows(args.ledger, args.since))
    if args.json:
        print(json.dumps(summary, indent=1))
    else:
        for key, value in summary.items():
            print(f'{key:>20}: {value}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
