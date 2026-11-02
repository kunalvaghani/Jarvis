"""Plasticity: verified outcomes strengthen or weaken *preference* among eligible routes. Nothing else.

- ``observe(plan, outcome)``: after a brain goal ends. Only ``verified`` and ``failed`` count; a stop, a denial or
  a deadline says nothing about route quality. On success every fired neuron earns a verified success in the
  goal's task context; on failure only the step that failed (or whose output the verifier rejected) earns one.
- ``neural.learning`` = ``off`` | ``shadow`` (default) | ``on``: the router uses learned statistics only when
  ``on``; in ``shadow`` they are recorded and ``replay`` shows what they would have changed. ``off`` is the
  one-step rollback (routing goes back to retrieval order and priors).
- ``consolidate``: a chain of neurons that ended verified at least ``MIN_REPEATS`` times becomes a proposed
  composite neuron. Read-only chains activate (they add no new power); anything that changes the world waits for
  the user's approval in the registry. Eligibility is never learned.
"""
from __future__ import annotations

from collections import Counter
import json
from typing import Any, Dict, List, Optional

from .router import task_context

MODES = ('off', 'shadow', 'on')
MIN_REPEATS = 3


def mode(config: Any) -> str:
    section = (config.get('neural') if isinstance(config, dict) else None) or {}
    value = str(section.get('learning', 'shadow')).lower()
    return value if value in MODES else 'off'


def observe(journal: Any, plan: Any, outcome: Any, seconds_by_step: Optional[Dict[str, float]] = None) -> int:
    """Record verified evidence from one finished goal. Returns how many rows were written."""
    if outcome.state not in ('verified', 'failed'):
        return 0
    context = task_context(plan.goal)
    seconds_by_step = seconds_by_step or {}
    written = 0
    for step in plan.steps:
        state = outcome.steps.get(step.step_id)
        if outcome.state == 'verified' and state == 'done':
            journal.record_outcome(context, step.neuron, True, seconds_by_step.get(step.step_id))
            written += 1
        elif outcome.state == 'failed' and state == 'failed':
            journal.record_outcome(context, step.neuron, False, seconds_by_step.get(step.step_id))
            written += 1
    if outcome.state == 'failed' and outcome.verdict and not outcome.verdict.get('passed'):
        producer = next((s.repairs for s in plan.steps if s.step_id == plan.goal_verifier and s.repairs), None)
        if producer:
            journal.record_outcome(context, plan.step(producer).neuron, False, None)
            written += 1
    journal.record_outcome(context, f'workflow.{plan.workflow}@v1', outcome.state == 'verified', outcome.seconds)
    return written + 1


def replay(journal: Any, limit: int = 500) -> Dict[str, Any]:
    """Offline check of the shadow log: how often the brain's first choice was a tool legacy really used, split by
    the independently checked outcome. Tells the user whether the brain's routing is ready to be trusted."""
    rows = [r for r in journal.shadow_rows(limit)]
    judged = [r for r in rows if r.get('outcome') in ('verified', 'failed')]
    hit: Counter[str] = Counter()
    total: Counter[str] = Counter()
    for row in judged:
        chosen = [c['node'] for c in row['proposed'].get('chosen', [])]
        first = chosen[0].split('.', 1)[-1].split('@')[0] if chosen else None
        total[row['outcome']] += 1
        hit[row['outcome']] += bool(first and first in row['actual'])
    return {'shadow_rows': len(rows), 'judged': len(judged),
            'first_choice_used_when_verified': f'{hit["verified"]}/{total["verified"]}',
            'first_choice_used_when_failed': f'{hit["failed"]}/{total["failed"]}',
            'fallback_to_legacy': sum(r['proposed'].get('fallback') == 'cortex.planner.legacy@v1' for r in rows)}


def consolidate(journal: Any, registry: Any, min_repeats: int = MIN_REPEATS) -> List[str]:
    """Propose composite neurons for tool chains that ended verified at least ``min_repeats`` times."""
    chains: Counter[tuple[str, ...]] = Counter()
    for row in journal.shadow_rows(2000):
        if row.get('outcome') == 'verified' and 1 < len(row['actual']) <= 8:
            chains[tuple(row['actual'])] += 1
    made = []
    for chain, count in chains.items():
        if count < min_repeats:
            continue
        parts = [registry.by_tool(tool) for tool in chain]
        if any(p is None or p.status != 'active' for p in parts):
            continue
        name = 'skill.learned.' + '_'.join(dict.fromkeys(chain))[:60].lower()
        node_id = f'{name}@v1'
        if registry.get(node_id) is not None:
            continue
        effects = {p.side_effect_class for p in parts}
        effect = 'read_only' if effects == {'read_only'} else (
            'destructive' if 'destructive' in effects else 'external_write' if 'external_write' in effects else
            'operation_dependent' if 'operation_dependent' in effects else 'local_write')
        try:
            neuron = registry.propose({
                'node_id': node_id, 'kind': 'workflow', 'capability': name, 'provider': 'jarvis.neural.learning',
                'inputs': [{'name': 'goal', 'type': 'Goal'}], 'outputs': [{'name': 'answer', 'type': 'Answer'}],
                'contract': 'explicit', 'side_effect_class': effect,
                'privilege': 'read' if effect == 'read_only' else 'approval_required',
                'description': f'Learned from {count} verified runs: ' + ' -> '.join(chain)},
                built_from=[p.node_id for p in parts], proposer='learning')
        except ValueError:
            continue
        made.append(f'{neuron.node_id} ({neuron.status})')
    return made


def summary(journal: Any) -> Dict[str, Any]:
    rows = journal.stats()
    return {'contexts': len({r['context'] for r in rows}), 'neurons_with_evidence': len({r['node_id'] for r in rows}),
            'verified_successes': sum(r['successes'] for r in rows), 'verified_failures': sum(r['failures'] for r in rows),
            'top': json.loads(json.dumps(sorted(rows, key=lambda r: -(r['successes'] + r['failures']))[:5]))}
