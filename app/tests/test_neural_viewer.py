"""Brain Phase 5: the live neuron view serves real journal events only, locally, without payloads."""
import json
import tempfile
import unittest
from pathlib import Path
from urllib.request import urlopen

from jarvis.neural.dispatcher import Dispatcher, Env
from jarvis.neural import adapters as A
from jarvis.neural.compiler import compile_goal
from jarvis.neural.graph import CapabilityGraph
from jarvis.neural.journal import Journal
from jarvis.neural.registry import Registry
from jarvis.neural.viewer import serve

PAGE = 'The Eiffel Tower was completed in 1889. PRIVATE-PAGE-MARKER It is 330 metres tall.'


class Viewer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        path = Path(cls.tmp.name) / 'j.sqlite3'
        journal = Journal(path)
        graph = CapabilityGraph.from_registry(Registry(journal).refresh(), journal)
        adapters = dict(A.ADAPTERS)
        adapters['tool.web_search@v1'] = lambda n, i, e: {'results': 'https://en.wikipedia.org/wiki/Eiffel_Tower'}
        adapters['tool.scrape_web@v1'] = lambda n, i, e: {'page': PAGE}
        plan = compile_goal('Research when the Eiffel Tower was completed', journal, {})
        cls.outcome = Dispatcher(graph, journal, adapters).run(plan, Env(config={}))
        journal.close()
        cls.server, cls.url = serve(path)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server.RequestHandlerClass.journal.close()
        cls.tmp.cleanup()

    def get(self, path):
        with urlopen(self.url + path, timeout=5) as reply:
            return reply.read().decode('utf-8')

    def test_local_only(self):
        self.assertTrue(self.url.startswith('http://127.0.0.1:'))
        self.assertIn('cytoscape', self.get(''))

    def test_every_lit_neuron_is_a_journaled_event(self):
        signals = json.loads(self.get(f'api/signals?goal={self.outcome.goal_id}'))
        fired = [s['target_node'] for s in signals if s['type'] == 'neuron.fired']
        self.assertEqual(len(fired), 6)
        graph = json.loads(self.get(f'api/graph?goal={self.outcome.goal_id}'))
        shown = {n['id'] for n in graph['nodes']}
        self.assertTrue(set(fired) <= shown)

    def test_payloads_never_leave_the_journal(self):
        everything = self.get(f'api/signals?goal={self.outcome.goal_id}') + self.get('api/goals') + \
            self.get('api/neuron?id=tool.scrape_web@v1') + self.get('api/graph')
        self.assertNotIn('PRIVATE-PAGE-MARKER', everything)

    def test_neuron_detail_explains_contract_and_history(self):
        detail = json.loads(self.get('api/neuron?id=verifier.report_grounded@v1'))
        self.assertEqual(detail['contract']['kind'], 'verifier')
        self.assertTrue(detail['last_signals'])
        self.assertEqual(json.loads(self.get('api/neuron?id=nope'))['error'], 'unknown neuron')


if __name__ == '__main__':
    unittest.main()
