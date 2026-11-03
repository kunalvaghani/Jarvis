"""Neuron lifecycle (jarvis/neural/lifecycle.py, Registry.disable/restore): grow, retire, restore."""
import tempfile
from pathlib import Path

import pytest

from jarvis.neural import lifecycle
from jarvis.neural.journal import Journal
from jarvis.neural.registry import Registry, RegistryError


def learned(registry, name='skill.learned.web_open_web_read'):
    parts = [registry.by_tool('web_read')]
    return registry.propose({
        'node_id': f'{name}@v1', 'kind': 'workflow', 'capability': name, 'provider': lifecycle.LEARNED,
        'inputs': [{'name': 'goal', 'type': 'Goal'}], 'outputs': [{'name': 'answer', 'type': 'Answer'}],
        'contract': 'explicit', 'side_effect_class': 'read_only', 'privilege': 'read',
        'description': 'test'}, built_from=[p.node_id for p in parts], proposer='learning')


def setup():
    folder = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)  # Windows: the journal stays open
    journal = Journal(Path(folder.name) / 'brain.sqlite3')
    return folder, journal, Registry(journal).refresh()


def test_a_failing_learned_neuron_is_retired_and_stays_retired_after_restart():
    folder, journal, registry = setup()
    with folder:
        neuron = learned(registry)
        assert neuron.status == 'active'  # read-only composite of active neurons
        for ok in (True, False, False, False, False):
            journal.record_outcome('ctx', neuron.node_id, ok)
        assert lifecycle.retire_failing(journal, registry) == [neuron.node_id]
        assert registry.get(neuron.node_id).status == 'disabled'
        again = Registry(journal).refresh()  # a restart
        assert again.get(neuron.node_id).status == 'disabled'


def test_a_learned_neuron_doing_well_is_kept():
    folder, journal, registry = setup()
    with folder:
        neuron = learned(registry)
        for ok in (True, True, True, False, True):
            journal.record_outcome('ctx', neuron.node_id, ok)
        assert lifecycle.retire_failing(journal, registry) == []


def test_built_in_neurons_are_never_retired_automatically_but_the_user_can_retire_and_restore():
    folder, journal, registry = setup()
    with folder:
        node = registry.by_tool('web_read').node_id
        for _ in range(6):
            journal.record_outcome('ctx', node, False)
        assert lifecycle.retire_failing(journal, registry) == []
        with pytest.raises(RegistryError):
            registry.disable(node, 'bad', 'lifecycle')
        registry.disable(node, 'user test', 'user')
        assert Registry(journal).refresh().get(node).status == 'disabled'  # survives the code-defined source
        registry.restore(node)
        assert registry.get(node).status == 'active'


def test_tick_runs_every_few_goals():
    folder, journal, registry = setup()
    with folder:
        service = type('S', (), {'journal': journal, 'registry': registry})()
        lifecycle._count = 0
        due = [lifecycle.tick(service) for _ in range(lifecycle.EVERY)]
        assert all(d == {'grown': [], 'retired': []} for d in due)  # nothing to grow or retire, no errors
        assert lifecycle._count == lifecycle.EVERY
