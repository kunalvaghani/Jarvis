"""Adapters to the existing queue/checkpoint owner; never a second job runner."""
from __future__ import annotations

from .catalog import enabled
from .contracts import Experiment


def submit(queue, config, request, generation, token):
    from ..commands import Command
    if not enabled(config, 'sim'):
        raise PermissionError('Lab simulation jobs are disabled')
    if not isinstance(request, str) or not 1 <= len(request) <= 2000:
        raise ValueError('bounded scientific request required')
    # Existing intake/classification, generation, pause, ownership and dependency rules remain authoritative.
    return queue.put_nowait((generation, Command('task', request), token))


def checkpoint(memory, task_state, experiment: Experiment):
    ref = memory.put(experiment)
    task_state.checkpoint('discovery.experiment', evidence=ref, source='brain_journal')
    return ref
