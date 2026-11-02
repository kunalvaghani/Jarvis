"""Compare two live-suite arms (legacy vs new control/brain stack) and write docs/control/COMPARISON.md.

    python scripts/control_compare.py <arm A start ISO> <arm B start ISO> [<arm B end ISO>]

Reads benchmarks/results/live/C*.jsonl rows by time window: arm A = [A start, B start), arm B = [B start, end).
Success-rate difference: Newcombe interval from Wilson intervals (95%). Latency difference: bootstrap of the
median (95%, 2,000 resamples, fixed seed). No claim is made without its interval.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import random
import statistics
import sys
from typing import Any, Dict, List, Optional, Tuple

APP = Path(__file__).resolve().parents[1]
LIVE = APP / 'benchmarks' / 'results' / 'live'
OUT = APP / 'docs' / 'control' / 'COMPARISON.md'
CATEGORIES = {'native': range(1, 9), 'electron': range(9, 14), 'shell': range(14, 20), 'web': range(20, 28),
              'google': range(28, 35), 'hard': range(35, 41), 'concurrency': range(41, 45)}
Z = 1.959964


def wilson(k: int, n: int) -> Tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    centre = (p + Z * Z / (2 * n)) / (1 + Z * Z / n)
    half = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / (1 + Z * Z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def newcombe(k1: int, n1: int, k2: int, n2: int) -> Tuple[float, float, float]:
    """Difference p2 - p1 with its 95% interval (Newcombe hybrid score)."""
    p1, p2 = (k1 / n1 if n1 else 0.0), (k2 / n2 if n2 else 0.0)
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    d = p2 - p1
    return d, d - math.sqrt((p2 - l2) ** 2 + (u1 - p1) ** 2), d + math.sqrt((u2 - p2) ** 2 + (p1 - l1) ** 2)


def bootstrap_median_diff(a: List[float], b: List[float], n: int = 2000) -> Optional[Tuple[float, float, float]]:
    if not a or not b:
        return None
    rng = random.Random(7)
    diffs = sorted(statistics.median(rng.choices(b, k=len(b))) - statistics.median(rng.choices(a, k=len(a)))
                   for _ in range(n))
    return statistics.median(b) - statistics.median(a), diffs[int(.025 * n)], diffs[int(.975 * n) - 1]


def rows(start: str, end: str) -> List[Dict[str, Any]]:
    found = []
    for path in sorted(LIVE.glob('C*.jsonl')):
        for line in path.read_text(encoding='utf-8').splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if start <= str(row.get('date', ''))[:19] < end:
                found.append(row)
    return found


def category(cid: str) -> str:
    number = int(cid[1:3]) if cid[1:3].isdigit() else 0
    return next((name for name, span in CATEGORIES.items() if number in span), 'other')


def summary(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    seconds = [float(r['seconds']) for r in data if isinstance(r.get('seconds'), (int, float))]
    ok = sum(bool(r.get('passed')) for r in data)
    firsts = [float(r['first_action_s']) for r in data if isinstance(r.get('first_action_s'), (int, float))]
    calls = [len(r.get('model_calls') or []) for r in data]
    return {'n': len(data), 'ok': ok, 'rate': ok / len(data) if data else 0.0, 'ci': wilson(ok, len(data)),
            'p50': statistics.median(seconds) if seconds else None,
            'p95': sorted(seconds)[int(.95 * (len(seconds) - 1))] if seconds else None,
            'mean': statistics.mean(seconds) if seconds else None,
            'first': statistics.median(firsts) if firsts else None,
            'calls': statistics.mean(calls) if calls else 0.0,
            'focus': sum(int(r.get('focus_changes') or 0) for r in data),
            'retries': sum(int(r.get('wasted_retries') or 0) for r in data),
            'ram': max([int(r.get('peak_ram_mb') or 0) for r in data] or [0]),
            'vram': max([int(r.get('peak_vram_mb') or 0) for r in data] or [0]),
            'seconds': seconds}


def fmt(v: Optional[float], d: int = 1) -> str:
    return '—' if v is None else f'{v:.{d}f}'


def main(argv: List[str]) -> int:
    a_start, b_start = argv[0], argv[1]
    end = argv[2] if len(argv) > 2 else '9999'
    arm_a, arm_b = rows(a_start, b_start), rows(b_start, end)
    lines = ['# Control A/B comparison', '',
             f'Arm A (legacy control, brain shadow) from {a_start}; arm B (agent-desktop + agent-browser, brain on) '
             f'from {b_start}. Same scenarios and shuffle seed, same machine, independent oracles. '
             'Intervals are 95%; a difference whose interval spans 0 is not a claim.', '']
    total_a, total_b = summary(arm_a), summary(arm_b)
    d, lo, hi = newcombe(total_a['ok'], total_a['n'], total_b['ok'], total_b['n'])
    lat = bootstrap_median_diff(total_a['seconds'], total_b['seconds'])
    lines += ['## Overall', '', '| Metric | Legacy (A) | New (B) |', '|---|---|---|',
              f'| Verified success | {total_a["ok"]}/{total_a["n"]} ({total_a["rate"]:.0%}, CI {total_a["ci"][0]:.0%}–{total_a["ci"][1]:.0%}) '
              f'| {total_b["ok"]}/{total_b["n"]} ({total_b["rate"]:.0%}, CI {total_b["ci"][0]:.0%}–{total_b["ci"][1]:.0%}) |',
              f'| End-to-end p50 / p95 / mean (s) | {fmt(total_a["p50"])} / {fmt(total_a["p95"])} / {fmt(total_a["mean"])} '
              f'| {fmt(total_b["p50"])} / {fmt(total_b["p95"])} / {fmt(total_b["mean"])} |',
              f'| First action p50 (s) | {fmt(total_a["first"])} | {fmt(total_b["first"])} |',
              f'| Model calls per task (mean) | {fmt(total_a["calls"], 2)} | {fmt(total_b["calls"], 2)} |',
              f'| Foreground changes (focus steals) | {total_a["focus"]} | {total_b["focus"]} |',
              f'| Wasted retries | {total_a["retries"]} | {total_b["retries"]} |',
              f'| Peak RAM / VRAM (MB) | {total_a["ram"]} / {total_a["vram"]} | {total_b["ram"]} / {total_b["vram"]} |', '',
              f'Success difference B − A: **{d:+.0%}** (95% CI {lo:+.0%} to {hi:+.0%}).',
              (f'Median latency difference B − A: **{lat[0]:+.1f} s** (95% CI {lat[1]:+.1f} to {lat[2]:+.1f} s).'
               if lat else 'Latency difference: not enough runs.'), '',
              '## By category', '', '| Category | A success | B success | Δ (95% CI) | A p50 s | B p50 s | Rule |',
              '|---|---|---|---|---|---|---|']
    for name in list(CATEGORIES) + ['other']:
        ca = summary([r for r in arm_a if category(r['case']) == name])
        cb = summary([r for r in arm_b if category(r['case']) == name])
        if not ca['n'] and not cb['n']:
            continue
        dd, l2, h2 = newcombe(ca['ok'], ca['n'], cb['ok'], cb['n'])
        clat = bootstrap_median_diff(ca['seconds'], cb['seconds'])
        worse_latency = bool(clat and clat[1] > 0)
        rule = 'switch' if cb['ok'] >= ca['ok'] and l2 > -0.5 and not worse_latency else 'stay legacy'
        lines.append(f'| {name} | {ca["ok"]}/{ca["n"]} | {cb["ok"]}/{cb["n"]} | {dd:+.0%} ({l2:+.0%}…{h2:+.0%}) '
                     f'| {fmt(ca["p50"])} | {fmt(cb["p50"])} | {rule} |')
    lines += ['', '## Per scenario', '', '| Case | A | A s | B | B s | B problem |', '|---|---|---|---|---|---|']
    for cid in sorted({r['case'] for r in arm_a + arm_b}):
        ra = [r for r in arm_a if r['case'] == cid]
        rb = [r for r in arm_b if r['case'] == cid]
        sa, sb = summary(ra), summary(rb)
        problem = next((str(p)[:90] for r in rb for p in (r.get('problems') or [])), '')
        lines.append(f'| {cid} | {sa["ok"]}/{sa["n"]} | {fmt(sa["p50"])} | {sb["ok"]}/{sb["n"]} | {fmt(sb["p50"])} | '
                     f'{problem.replace("|", "/")} |')
    lines += ['', 'Go/no-go rule (master prompt): the new backend becomes default for a category only if its verified '
              'success is at least legacy\'s, there are zero unauthorized side effects or double executions, and its '
              'latency is not significantly worse. "switch" above applies that rule to this round only; small counts '
              'need the repeat runs before any default changes.']
    OUT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines[:24]))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
