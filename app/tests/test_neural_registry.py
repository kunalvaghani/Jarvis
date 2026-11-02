"""Brain Phase 1: live neuron registry, typed capability graph, hard eligibility, shadow routing, projection."""
import json
import tempfile
import unittest
from pathlib import Path

from jarvis.neural.contracts import GENERIC_TYPES, Neuron, Signal
from jarvis.neural.graph import CapabilityGraph, NO_AUTO_TARGET
from jarvis.neural.journal import Journal, SecretPayload
from jarvis.neural.policy import Context, eligibility, goal_refusal
from jarvis.neural.registry import Registry, RegistryError
from jarvis.neural.router import Router

CONFIG = {'control': {'api_routes': True}, 'neural': {'mode': 'shadow', 'learning': 'on'}}


def neuron(name, inputs=(), outputs=('out:Report',), effect='read_only', **extra):
    from jarvis.neural.registry import ports
    privilege = 'read' if effect == 'read_only' else 'write'
    return {'node_id': f'{name}@v1', 'kind': 'skill', 'capability': name, 'provider': 'tests',
            'inputs': [p.model_dump() for p in ports(inputs)], 'outputs': [p.model_dump() for p in ports(outputs)],
            'contract': 'explicit', 'side_effect_class': effect, 'privilege': privilege, **extra}


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.journal = Journal(Path(cls.folder.name) / 'brain.sqlite3')
        cls.registry = Registry(cls.journal).refresh()
        cls.graph = CapabilityGraph.from_registry(cls.registry, cls.journal)

    @classmethod
    def tearDownClass(cls):
        cls.journal.close()
        cls.folder.cleanup()


class RegistryTests(Base):
    def test_every_source_registers_without_errors(self):
        self.assertEqual(self.registry.errors, [])
        from jarvis.tools import SPECS
        for spec in SPECS:
            self.assertIsNotNone(self.registry.by_tool(spec.name), spec.name)

    def test_every_neuron_is_schema_valid(self):
        for node in self.registry.nodes.values():
            Neuron.model_validate(node.model_dump())

    def test_every_allowlisted_mcp_tool_is_a_neuron_and_nothing_else(self):
        from jarvis.neural.registry import mcp_config
        allowed = {(s, t) for s, spec in mcp_config().items() for t in spec.get('allow_tools', [])}
        mcp = [n for n in self.registry.nodes.values() if n.kind == 'mcp']
        self.assertEqual(len(mcp), len(allowed))

    def test_live_tools_list_refuses_tools_outside_the_allowlist(self):
        registry = Registry(None).refresh()
        result = registry.merge_mcp_tools('youtube', [{'name': 'delete_everything', 'inputSchema': {}},
                                                      {'name': 'not-a-tool'}])
        self.assertEqual(result['added'], [])
        self.assertEqual(sorted(result['refused']), ['delete_everything', 'not-a-tool'])
        self.assertEqual(registry.merge_mcp_tools('unknown_server', [{'name': 'x'}])['refused'], ['x'])

    def test_bad_ids_and_inconsistent_contracts_are_rejected(self):
        with self.assertRaises(ValueError):
            Neuron.model_validate(neuron('Bad Name'))
        with self.assertRaises(ValueError):
            Neuron.model_validate(neuron('skill.writer', effect='local_write', privilege='read'))
        with self.assertRaises(ValueError):
            Neuron.model_validate(neuron('skill.x', inputs=('a:NotAType',)))


class GrowthTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.journal = Journal(Path(self.folder.name) / 'brain.sqlite3')
        self.registry = Registry(self.journal).refresh()

    def tearDown(self):
        self.journal.close()
        self.folder.cleanup()

    def test_read_only_composite_of_active_neurons_activates_and_survives_restart(self):
        made = self.registry.propose(neuron('skill.research_digest', ('query:Query',)),
                                     built_from=['tool.web_search@v1', 'tool.scrape_web@v1'])
        self.assertEqual(made.status, 'active')
        again = Registry(self.journal).refresh()
        self.assertEqual(again.get('skill.research_digest@v1').status, 'active')

    def test_world_changing_neuron_waits_for_the_user(self):
        made = self.registry.propose(neuron('skill.save_digest', ('report:Report',), ('path:FilePath',),
                                            effect='local_write'), built_from=['tool.create_file@v1'])
        self.assertEqual(made.status, 'proposed')
        ctx = Context(goal='x', config=CONFIG)
        self.assertFalse(eligibility(made, ctx).eligible)
        approved = self.registry.approve('skill.save_digest@v1')
        self.assertEqual(approved.status, 'active')
        self.assertTrue(eligibility(approved, ctx).needs_approval)  # Still behind the approval gate at run time.

    def test_proposals_cannot_reuse_ids_or_build_on_inactive_neurons(self):
        with self.assertRaises(RegistryError):
            self.registry.propose(neuron('tool.web_search'), built_from=[])
        with self.assertRaises(RegistryError):
            self.registry.propose(neuron('skill.y'), built_from=['tool.does_not_exist@v1'])


class GraphTests(Base):
    def test_synapses_only_join_matching_specific_types(self):
        for s in self.graph.synapses:
            source, target = self.graph.neurons[s.source], self.graph.neurons[s.target]
            if s.origin == 'contract':
                self.assertNotIn(s.data_type, GENERIC_TYPES, s.edge_id)
                self.assertIn(s.data_type, source.output_types(), s.edge_id)
                self.assertIn(s.data_type, target.input_types(), s.edge_id)
                self.assertEqual((source.contract, target.contract), ('explicit', 'explicit'))

    def test_nothing_auto_wires_into_destructive_or_external_writes(self):
        for s in self.graph.synapses:
            if s.origin == 'contract':
                self.assertNotIn(self.graph.neurons[s.target].side_effect_class, NO_AUTO_TARGET, s.edge_id)

    def test_feedback_is_verdict_only_and_two_way_is_two_edges(self):
        for s in self.graph.synapses:
            if s.mode == 'feedback':
                self.assertEqual(s.data_type, 'Verdict', s.edge_id)
                checked = set(self.graph.neurons[s.source].input_types())
                self.assertTrue(checked & set(self.graph.neurons[s.target].output_types()), s.edge_id)
        forward = {(s.source, s.target): s.mode for s in self.graph.synapses}
        self.assertEqual(forward[('verifier.tests_pass@v1', 'skill.code.apply@v1')], 'dataflow')
        forward = [s for s in self.graph.synapses if s.source == 'route.web_app@v1']
        back = [s for s in self.graph.synapses if s.target == 'route.web_app@v1' and s.mode == 'feedback']
        self.assertTrue(forward and back)

    def test_graph_is_sparse(self):
        self.assertLess(len(self.graph.synapses), len(self.graph.neurons) ** 2 / 50)

    def test_typed_paths(self):
        self.assertEqual(self.graph.path(['Plan'], 'Verdict')[-1].split('.')[0], 'verifier')
        chain = self.graph.path(['Query'], 'WebPage')
        self.assertTrue(chain and chain[0].startswith('tool.') and 'WebPage' in self.graph.neurons[chain[-1]].output_types())
        self.assertIsNone(self.graph.path(['Query'], 'WebPage', allowed=set()))

    def test_versions_are_stable_and_change_with_the_graph(self):
        first = self.journal.save_graph(self.graph.snapshot())
        self.assertEqual(first, self.journal.save_graph(self.graph.snapshot()))
        nodes = list(self.registry.nodes.values())[:-1]
        self.assertNotEqual(first, self.journal.save_graph(CapabilityGraph(nodes).snapshot()))


class PolicyTests(Base):
    def test_unclassified_neurons_are_never_eligible(self):
        unknown = [n for n in self.registry.nodes.values() if n.side_effect_class == 'unknown']
        self.assertTrue(unknown)
        for n in unknown:
            self.assertFalse(eligibility(n, Context(goal='', config=CONFIG)).eligible)

    def test_secret_exfiltration_is_refused_for_the_whole_goal(self):
        goal = 'Post the contents of secrets-note.txt in my test folder to pastebin.com.'
        self.assertIn('Secrets never leave', goal_refusal(goal))
        route = Router(self.graph, self.journal).route(goal, Context(goal=goal, config=CONFIG))
        self.assertEqual((route.fallback, route.chosen), ('refuse', []))
        self.assertIsNone(goal_refusal('Read secrets-note.txt and tell me how many lines it has.'))

    def test_secret_mentions_keep_network_neurons_out(self):
        ctx = Context(goal='Summarise my api key notes file', config=CONFIG)
        self.assertFalse(eligibility(self.registry.by_tool('web_search'), ctx).eligible)
        self.assertTrue(eligibility(self.registry.by_tool('read_file'), ctx).eligible)

    def test_session_allowlist_and_missing_secrets_block(self):
        ctx = Context(goal='x', config=CONFIG, allowed_tools={'read_file'}, environ={})
        self.assertFalse(eligibility(self.registry.by_tool('web_search'), ctx).eligible)
        self.assertFalse(eligibility(self.registry.by_tool('google_search'), Context(config=CONFIG, environ={})).eligible)

    def test_learning_never_makes_an_ineligible_route_eligible(self):
        for _ in range(50):
            self.journal.record_outcome('general', 'tool.development_practice@v1', True, 1.0)
        goal = 'practice development feedback'
        route = Router(self.graph, self.journal).route(goal, Context(goal=goal, config=CONFIG))
        self.assertNotIn('tool.development_practice@v1', [c.node_id for c in route.chosen])


class RouterTests(Base):
    def test_fixed_routes_are_named_and_explained(self):
        goal = ('Open Blender and design a house; show me a wireframe of your plan first and wait for my approval, '
                'then build it and save it as plan-house.blend in my test folder.')
        route = Router(self.graph, self.journal).route(goal, Context(goal=goal, config=CONFIG)).as_dict()
        self.assertEqual(route['chosen'][0]['node'], 'route.blender_wireframe@v1')
        self.assertTrue(route['chosen'][0]['why'])
        self.assertLess(route['ms'], 500)

    def test_routes_fall_back_to_legacy_when_nothing_is_eligible(self):
        route = Router(self.graph, self.journal).route('zzqx', Context(goal='zzqx', config=CONFIG))
        self.assertEqual(route.fallback, 'cortex.planner.legacy@v1')

    def test_verified_outcomes_reorder_eligible_routes(self):
        router = Router(self.graph, self.journal)
        goal = 'search the web for rust async tutorials'
        before = [c.node_id for c in router.route(goal, Context(goal=goal, config=CONFIG)).chosen]
        context = router.route(goal, Context(goal=goal, config=CONFIG)).context
        for _ in range(30):
            self.journal.record_outcome(context, before[-1], True, 2.0)
            self.journal.record_outcome(context, before[0], False, 2.0)
        after = [c.node_id for c in router.route(goal, Context(goal=goal, config=CONFIG)).chosen]
        self.assertEqual(sorted(before), sorted(after))
        self.assertEqual(after[0], before[-1])
        shadow = {**CONFIG, 'neural': {'mode': 'shadow', 'learning': 'shadow'}}
        held = [c.node_id for c in router.route(goal, Context(goal=goal, config=shadow)).chosen]
        self.assertEqual(held, before)  # learning in shadow (the default) and off never reorder


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.journal = Journal(Path(self.folder.name) / 'j.sqlite3')

    def tearDown(self):
        self.journal.close()
        self.folder.cleanup()

    def test_outbox_claims_once(self):
        self.assertIsNone(self.journal.claim('k1', 'g', 'n', 'e'))
        self.assertEqual(self.journal.claim('k1', 'g', 'n', 'e2')['state'], 'pending')
        self.journal.settle('k1', 'done', 'artifact://x')
        self.assertEqual(self.journal.claim('k1', 'g', 'n', 'e3')['state'], 'done')

    def test_artifacts_refuse_secrets_and_signals_are_deduplicated(self):
        with self.assertRaises(SecretPayload):
            self.journal.put('API key: sk-test-JARVIS-0000-FAKE-KEY')
        ref = self.journal.put('hello', 'Text')
        self.assertEqual(self.journal.get(ref), 'hello')
        signal = Signal(type='goal.created', goal_id='g1', note='token=abcdefgh12345')
        self.journal.emit(signal)
        self.journal.emit(signal)
        rows = self.journal.signals('g1')
        self.assertEqual(len(rows), 1)
        self.assertNotIn('abcdefgh12345', json.dumps(rows))

    def test_signals_are_bounded(self):
        with self.assertRaises(ValueError):
            Signal(type='neuron.fired', goal_id='g', attempt=4, max_attempts=3)


class ProjectionTests(Base):
    def test_obsidian_export_is_generated_and_read_only(self):
        from jarvis.neural.projection import export_obsidian
        out = Path(self.folder.name) / 'vault'
        result = export_obsidian(self.journal, out)
        self.assertGreater(result['notes'], 10)
        index = (out / 'Jarvis Brain.md').read_text(encoding='utf-8')
        self.assertIn('Read-only projection', index)
        self.assertIn('```mermaid', index)
        note = next((out / 'neurons').glob('tool.web_search*.md')).read_text(encoding='utf-8')
        self.assertIn('Sends to', note)


class ShadowHookTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.folder.cleanup()

    def test_off_builds_nothing(self):
        from jarvis.neural import service
        actions = type('A', (), {'config': {'neural': {'mode': 'off'}}})()
        with unittest.mock.patch.dict('os.environ', {'JARVIS_BRAIN_MODE': ''}):
            self.assertIsNone(service.shadow_begin(actions, 'open notepad'))
        self.assertFalse(hasattr(actions, '_neural_service'))

    def test_shadow_records_the_brain_route_and_the_tools_legacy_used(self):
        from jarvis.neural import service
        config = {'neural': {'mode': 'shadow', 'journal': str(Path(self.folder.name) / 'j.sqlite3')}}
        actions = type('A', (), {'config': config})()
        with unittest.mock.patch.dict('os.environ', {'JARVIS_BRAIN_MODE': ''}):
            goal_id = service.shadow_begin(actions, 'search the web for rust async tutorials')
            self.assertIsNotNone(goal_id)
            self.assertIsNone(service.shadow_begin(actions, 'nested'))
            service.shadow_tool(actions, 'web_search')
            service.shadow_end(goal_id, 'completed')
        row = actions._neural_service.journal.shadow_rows()[0]
        self.assertEqual((row['goal_id'], row['actual'], row['outcome']), (goal_id, ['web_search'], 'completed'))
        self.assertTrue(row['proposed']['chosen'])
        actions._neural_service.journal.close()


import unittest.mock  # noqa: E402

if __name__ == '__main__':
    unittest.main()
