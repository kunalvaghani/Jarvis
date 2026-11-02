"""Brain Phase 4: plasticity from verified outcomes only; growth by consolidation; eligibility never learned."""
import tempfile
import unittest
from pathlib import Path

from jarvis.neural import learning
from jarvis.neural.dispatcher import Outcome
from jarvis.neural.execution import Bind, Plan, Step
from jarvis.neural.journal import Journal
from jarvis.neural.policy import Context, eligibility
from jarvis.neural.registry import Registry


def plan():
    return Plan(goal_id='g1', goal='search the web for rust async', workflow='research.answer', goal_verifier='check',
                answer_step='answer', steps=[
                    Step(step_id='search', neuron='tool.web_search@v1', bind={'query': Bind(const='artifact://q')}),
                    Step(step_id='check', neuron='verifier.report_grounded@v1', repairs='search',
                         bind={'report': Bind(step='search', port='results'), 'page': Bind(step='search', port='results')}),
                    Step(step_id='answer', neuron='motor.report@v1',
                         bind={'report': Bind(step='search', port='results'), 'verdict': Bind(step='check', port='verdict')})])


class Learning(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.journal = Journal(Path(self.tmp.name) / 'j.sqlite3')

    def tearDown(self):
        self.journal.close()
        self.tmp.cleanup()

    def test_only_verified_or_failed_goals_teach(self):
        for state in ('cancelled', 'denied', 'deadline', 'uncertain', 'blocked'):
            self.assertEqual(learning.observe(self.journal, plan(), Outcome('g1', state, 'x')), 0)
        self.assertEqual(self.journal.stats(), [])
        learning.observe(self.journal, plan(), Outcome('g1', 'verified', 'ok', steps={'search': 'done', 'check': 'done',
                                                                                     'answer': 'done'}))
        rows = {r['node_id']: r for r in self.journal.stats()}
        self.assertEqual(rows['tool.web_search@v1']['successes'], 1)
        self.assertEqual(rows['workflow.research.answer@v1']['successes'], 1)

    def test_a_rejected_output_counts_against_its_producer(self):
        learning.observe(self.journal, plan(), Outcome('g1', 'failed', 'check failed', verdict={'passed': False},
                                                       steps={'search': 'done', 'check': 'failed'}))
        rows = {r['node_id']: r for r in self.journal.stats()}
        self.assertEqual(rows['tool.web_search@v1']['failures'], 1)
        self.assertEqual(rows['verifier.report_grounded@v1']['failures'], 1)

    def test_mode_defaults_to_shadow_and_bad_values_read_off(self):
        self.assertEqual(learning.mode({}), 'shadow')
        self.assertEqual(learning.mode({'neural': {'learning': 'on'}}), 'on')
        self.assertEqual(learning.mode({'neural': {'learning': 'yes please'}}), 'off')

    def test_consolidation_grows_read_only_skills_and_holds_writers_for_approval(self):
        registry = Registry(self.journal).refresh()
        for n in range(3):
            for goal, tools in ((f'r{n}', ['web_search', 'scrape_web']), (f'w{n}', ['read_file', 'create_file'])):
                self.journal.shadow(goal, {'chosen': []})
                for tool in tools:
                    self.journal.shadow_actual(goal, tool)
                self.journal.shadow_outcome(goal, 'verified')
        self.journal.shadow('once', {'chosen': []})
        self.journal.shadow_actual('once', 'web_search')
        self.journal.shadow_actual('once', 'list_files')
        self.journal.shadow_outcome('once', 'verified')
        made = learning.consolidate(self.journal, registry)
        self.assertEqual(sorted(made), ['skill.learned.read_file_create_file@v1 (proposed)',
                                        'skill.learned.web_search_scrape_web@v1 (active)'])
        writer = registry.get('skill.learned.read_file_create_file@v1')
        self.assertFalse(eligibility(writer, Context(goal='x', config={})).eligible)
        self.assertEqual(learning.consolidate(self.journal, registry), [])  # no duplicates
        self.assertIsNotNone(Registry(self.journal).refresh().get('skill.learned.web_search_scrape_web@v1'))

    def test_unverified_runs_never_consolidate(self):
        registry = Registry(self.journal).refresh()
        for n in range(5):
            self.journal.shadow(f'g{n}', {'chosen': []})
            self.journal.shadow_actual(f'g{n}', 'web_search')
            self.journal.shadow_actual(f'g{n}', 'scrape_web')
            self.journal.shadow_outcome(f'g{n}', 'completed')
        self.assertEqual(learning.consolidate(self.journal, registry), [])

    def test_replay_reports_agreement(self):
        self.journal.shadow('a', {'chosen': [{'node': 'tool.web_search@v1'}], 'fallback': 'none'})
        self.journal.shadow_actual('a', 'web_search')
        self.journal.shadow_outcome('a', 'verified')
        report = learning.replay(self.journal)
        self.assertEqual(report['first_choice_used_when_verified'], '1/1')


if __name__ == '__main__':
    unittest.main()
