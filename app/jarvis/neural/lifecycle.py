"""Neuron lifecycle while the brain runs: grow learned neurons from verified chains, retire learned ones that fail.

- Grow: ``learning.consolidate`` (unchanged rules): a tool chain verified at least 3 times becomes a proposed
  composite; read-only composites activate, anything that changes the world waits for the user's approval.
- Retire: a *learned* neuron (provider ``jarvis.neural.learning``) whose verified record is poor (at least
  ``MIN_RUNS`` judged runs, success rate below ``MAX_SUCCESS``) is disabled, with the reason journalled. Built-in,
  tool and MCP neurons are never retired automatically; the user can retire or restore any neuron
  (``python -m jarvis.neural retire|restore <node>``).
- ``tick`` runs both every ``EVERY`` finished brain goals. Only verified outcomes count (eligibility is never
  learned, a stop or a denial says nothing about quality).
"""
from __future__ import annotations

import threading
from typing import Any, Dict, List

EVERY = 10
MIN_RUNS = 5
MAX_SUCCESS = 0.4
LEARNED = 'jarvis.neural.learning'
_count = 0
_lock = threading.Lock()


def retire_failing(journal: Any, registry: Any) -> List[str]:
    totals: Dict[str, List[int]] = {}
    for row in journal.stats():
        ok_bad = totals.setdefault(str(row['node_id']), [0, 0])
        ok_bad[0] += int(row['successes'])
        ok_bad[1] += int(row['failures'])
    retired = []
    for neuron in registry.active():
        if neuron.provider != LEARNED:
            continue
        ok, bad = totals.get(neuron.node_id, [0, 0])
        runs = ok + bad
        if runs >= MIN_RUNS and ok / runs < MAX_SUCCESS:
            registry.disable(neuron.node_id, f'verified success {ok}/{runs} below {MAX_SUCCESS:.0%}', 'lifecycle')
            retired.append(neuron.node_id)
    return retired


def tick(service: Any, force: bool = False) -> Dict[str, List[str]]:
    """After a finished brain goal: every ``EVERY`` goals, grow and retire. Never raises into the task."""
    global _count
    with _lock:
        _count += 1
        due = force or _count % EVERY == 0
    if not due:
        return {'grown': [], 'retired': []}
    from .learning import consolidate
    try:
        grown = consolidate(service.journal, service.registry)
    except Exception:
        grown = []
    try:
        retired = retire_failing(service.journal, service.registry)
    except Exception:
        retired = []
    return {'grown': grown, 'retired': retired}
