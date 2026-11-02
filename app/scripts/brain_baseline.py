"""Summarise live receipts into the brain baseline (or a brain run to compare against it).

    python scripts/brain_baseline.py <since ISO time> <out.json> [label]

Reads benchmarks/results/live/*.jsonl (local, gitignored) for runs started at or after `since` and reports, per
case and overall: verified success, p50/p95 end-to-end and first-action time, model calls, wasted retries,
peak RAM/VRAM and engine build time. The numbers are measurements of this PC on that date, not targets.
"""
from __future__ import annotations

import json
from pathlib import Path
import statistics
import sys
from typing import Any, Dict, List, Optional

APP = Path(__file__).resolve().parents[1]
LIVE = APP / 'benchmarks' / 'results' / 'live'


def percentile(values: List[float], q: float) -> Optional[float]:
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    index = min(len(values) - 1, max(0, round(q * (len(values) - 1))))
    return round(values[index], 1)


def summarise(since: str, label: str = '') -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for path in sorted(LIVE.glob('*.jsonl')):
        for line in path.read_text(encoding='utf-8').splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if str(row.get('date', ''))[:19] >= since:
                rows.append(row)
    cases: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        ledger = row.get('ledger') or {}
        entry = cases.setdefault(row['case'], {'runs': 0, 'passed': 0, 'seconds': [], 'first_action_s': [],
                                               'model_calls': [], 'wasted_retries': [], 'problems': []})
        entry['runs'] += 1
        entry['passed'] += bool(row.get('passed'))
        entry['seconds'].append(row.get('seconds'))
        entry['first_action_s'].append(row.get('first_action_s'))
        entry['model_calls'].append(ledger.get('model_calls', len(row.get('model_calls') or [])))
        entry['wasted_retries'].append(row.get('wasted_retries', 0))
        if row.get('problems'):
            entry['problems'].append(row['problems'][:2])
    seconds = [r.get('seconds') for r in rows]
    firsts = [r.get('first_action_s') for r in rows]
    return {
        'label': label, 'since': since, 'runs': len(rows), 'cases': len(cases),
        'verified_success': f"{sum(bool(r.get('passed')) for r in rows)}/{len(rows)}",
        'success_rate': round(sum(bool(r.get('passed')) for r in rows) / max(1, len(rows)), 3),
        'end_to_end_s': {'p50': percentile(seconds, .5), 'p95': percentile(seconds, .95)},
        'first_action_s': {'p50': percentile(firsts, .5), 'p95': percentile(firsts, .95),
                           'runs_with_an_action': sum(f is not None for f in firsts)},
        'model_calls_mean': round(statistics.mean([c for e in cases.values() for c in e['model_calls']] or [0]), 2),
        'wasted_retries_total': sum(r.get('wasted_retries', 0) or 0 for r in rows),
        'peak_ram_mb_max': max([r.get('peak_ram_mb') or 0 for r in rows] or [0]),
        'peak_vram_mb_max': max([r.get('peak_vram_mb') or 0 for r in rows] or [0]),
        'engine_build_s': {'p50': percentile([r.get('build_s') for r in rows], .5),
                           'p95': percentile([r.get('build_s') for r in rows], .95)},
        'per_case': {cid: {'passed': f"{e['passed']}/{e['runs']}", 'p50_s': percentile(e['seconds'], .5),
                           'first_action_p50_s': percentile(e['first_action_s'], .5),
                           'model_calls_mean': round(statistics.mean(e['model_calls'] or [0]), 1),
                           'wasted_retries': sum(e['wasted_retries']), 'problems': e['problems'][:2]}
                     for cid, e in sorted(cases.items())},
    }


def main(argv: List[str]) -> int:
    since, out = argv[0], Path(argv[1])
    summary = summarise(since, argv[2] if len(argv) > 2 else '')
    out.write_text(json.dumps(summary, indent=1, default=str), encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != 'per_case'}, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
