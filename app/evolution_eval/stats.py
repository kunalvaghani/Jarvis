"""Paired comparison statistics for candidate versus parent (seeded, reproducible)."""
import random
import statistics


def paired(parent, child, objective, seed=0, resamples=2000):
    """parent/child: per-example lists of per-repeat scores. Returns direction-adjusted deltas.

    A positive delta always means the child is better. The 95% interval is a seeded percentile
    bootstrap over examples (each example's mean over repeats), so one lucky example or one
    lucky repeat cannot qualify a candidate on its own.
    """
    if len(parent) != len(child) or not parent:
        raise ValueError('Paired comparison needs equally sized, non-empty example lists.')
    sign = 1 if objective == 'max' else -1
    parent_means = [statistics.fmean(values) for values in parent]
    child_means = [statistics.fmean(values) for values in child]
    deltas = [sign * (c - p) for p, c in zip(parent_means, child_means)]
    rng = random.Random(seed)
    boots = sorted(statistics.fmean(rng.choices(deltas, k=len(deltas))) for _ in range(resamples))
    base = statistics.fmean(parent_means)
    spread = [max(v) - min(v) for v in parent + child]
    return {'examples': len(deltas), 'repeats': len(parent[0]),
            'parent_mean': round(base, 6), 'child_mean': round(statistics.fmean(child_means), 6),
            'mean_delta': round(statistics.fmean(deltas), 6),
            'relative_delta': round(statistics.fmean(deltas) / abs(base), 6) if base else None,
            'ci95': [round(boots[int(.025 * resamples)], 6), round(boots[int(.975 * resamples) - 1], 6)],
            'improved_examples': sum(d > 0 for d in deltas), 'worse_examples': sum(d < 0 for d in deltas),
            'max_repeat_spread': round(max(spread), 6), 'deterministic': max(spread) == 0}
