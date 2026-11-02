"""Brain Phase 2: per-goal execution graphs, the durable dispatcher and the two vertical slices."""
import json
import tempfile
import threading
import unittest
import unittest.mock
from pathlib import Path

from jarvis.neural import adapters as A
from jarvis.neural.compiler import compile_goal
from jarvis.neural.dispatcher import Dispatcher, Env, resume_open_goals
from jarvis.neural.execution import Bind, Plan, Step
from jarvis.neural.graph import CapabilityGraph
from jarvis.neural.journal import Journal
from jarvis.neural.registry import Registry

PAGE = ('The Eiffel Tower is a wrought-iron lattice tower in Paris, France. It was completed in 1889 and stands '
        '330 metres tall. Gustave Eiffel\'s company designed and built the tower for the 1889 World\'s Fair.')
BUGGY = 'def add(a, b):\n    return a - b\n'
FIXED = 'def add(a, b):\n    return a + b\n'
TESTS = ('import unittest\nfrom calc import add\n\n\nclass T(unittest.TestCase):\n    def test_add(self):\n'
         '        self.assertEqual(add(2, 3), 5)\n')


class Model:
    """A stand-in for the local model worker: canned replies, counted."""

    def __init__(self, replies):
        self.replies, self.calls = list(replies), 0

    def request(self, op, cancelled, **data):
        self.calls += 1
        return {'text': self.replies[min(self.calls - 1, len(self.replies) - 1)]}


class Actions:
    def __init__(self, model=None):
        self.brain = type('B', (), {'client': model})()


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = Registry(None).refresh()
        cls.graph = CapabilityGraph(cls.registry.nodes.values())

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'tests-root'
        self.root.mkdir()
        self.config = {'control': {'allowed_roots': [str(self.root)]}}
        self.journal = Journal(Path(self.tmp.name) / 'j.sqlite3')
        self.calls = {}
        self.adapters = dict(A.ADAPTERS)
        self.adapters['tool.web_search@v1'] = self.counted('search', lambda n, i, e: {
            'results': 'Results: https://duckduckgo.com/x https://en.wikipedia.org/wiki/Eiffel_Tower https://example.com'})
        self.adapters['tool.scrape_web@v1'] = self.counted('scrape', lambda n, i, e: {'page': PAGE})
        self.dispatcher = Dispatcher(self.graph, self.journal, self.adapters)

    def tearDown(self):
        self.journal.close()
        self.tmp.cleanup()

    def counted(self, name, fn):
        def run(neuron, inputs, env):
            self.calls[name] = self.calls.get(name, 0) + 1
            return fn(neuron, inputs, env)
        return run

    def env(self, model=None, approve=lambda scope, summary: True, cancelled=lambda: False):
        return Env(actions=Actions(model), approve=approve, config=self.config, cancelled=cancelled)

    def bug_folder(self):
        folder = self.root / 'calc-bug'
        folder.mkdir()
        (folder / 'calc.py').write_text(BUGGY, encoding='utf-8')
        (folder / 'test_calc.py').write_text(TESTS, encoding='utf-8')
        return folder


class ResearchSlice(Base):
    def plan(self, goal='Research when the Eiffel Tower was completed'):
        plan = compile_goal(goal, self.journal, self.config)
        self.assertEqual(plan.workflow, 'research.answer')
        return plan

    def test_verified_answer_with_causal_signals_and_no_model(self):
        outcome = self.dispatcher.run(self.plan(), self.env())
        self.assertTrue(outcome.verified, outcome.stop_reason)
        self.assertIn('1889', outcome.answer)
        self.assertIn('Checked', outcome.answer)
        kinds = [s['type'] for s in self.journal.signals(outcome.goal_id)]
        self.assertEqual(kinds[0], 'goal.created')
        self.assertEqual(kinds[-1], 'goal.verified')
        fired = [s['task_id'] for s in self.journal.signals(outcome.goal_id) if s['type'] == 'neuron.fired']
        self.assertEqual(fired, ['search', 'pick', 'read', 'analyse', 'check', 'answer'])
        self.assertEqual(self.journal.pending(), [])

    def test_the_wikipedia_link_is_read_not_the_search_engine(self):
        self.dispatcher.run(self.plan(), self.env())
        url = next(json.loads(self.journal.get(json.loads(self.journal.get(s['payload_ref']))['url']))
                   for s in self.journal.signals() if s['type'] == 'neuron.succeeded' and s['task_id'] == 'pick')
        self.assertIn('wikipedia.org', url)

    def test_ungrounded_answers_are_repaired_then_fail_with_a_reason(self):
        model = Model(['It opened in 1925 and is 512 metres tall.'])
        outcome = self.dispatcher.run(self.plan(), self.env(model))
        self.assertEqual(outcome.state, 'failed')
        self.assertIn('2 attempt', outcome.stop_reason)
        self.assertEqual(outcome.answer, '')
        self.assertEqual(model.calls, 2)  # bounded: analyse.max_attempts

    def test_a_repair_that_succeeds_is_verified(self):
        model = Model(['It opened in 1925.', 'The tower was completed in 1889 for the World\'s Fair in Paris.'])
        outcome = self.dispatcher.run(self.plan(), self.env(model))
        self.assertTrue(outcome.verified, outcome.stop_reason)
        self.assertIn('verification.failed', [s['type'] for s in self.journal.signals(outcome.goal_id)])

    def test_write_requests_are_not_research(self):
        self.assertIsNone(compile_goal('Research cats and save it to a file', self.journal, self.config))

    def test_cancel_stops_before_the_next_wave(self):
        fired = []
        stop = threading.Event()

        def scrape(neuron, inputs, env):
            fired.append('read')
            stop.set()
            return {'page': PAGE}
        self.adapters['tool.scrape_web@v1'] = scrape
        outcome = self.dispatcher.run(self.plan(), self.env(cancelled=stop.is_set))
        self.assertEqual(outcome.state, 'cancelled')
        self.assertNotIn('analyse', [s['task_id'] for s in self.journal.signals(outcome.goal_id)
                                     if s['type'] == 'neuron.fired'])

    def test_secret_looking_output_is_never_passed_on(self):
        self.adapters['tool.scrape_web@v1'] = lambda n, i, e: {'page': 'config: api_key: sk-test-JARVIS-0000-FAKE-KEY'}
        outcome = self.dispatcher.run(self.plan(), self.env())
        self.assertEqual(outcome.state, 'refused')
        self.assertNotIn('FAKE-KEY', json.dumps(self.journal.signals()))


class CodeSlice(Base):
    def test_bug_fix_is_tested_on_a_copy_approved_once_applied_and_rechecked(self):
        folder = self.bug_folder()
        asked = []
        plan = compile_goal('Fix the bug in calc.py in the calc-bug folder so its tests pass.', self.journal, self.config)
        self.assertEqual(plan.workflow, 'code.bug_fix')
        outcome = self.dispatcher.run(plan, self.env(Model([FIXED]), approve=lambda s, d: asked.append(s) or True))
        self.assertTrue(outcome.verified, outcome.stop_reason)
        self.assertEqual(len(asked), 1)
        self.assertEqual((folder / 'calc.py').read_text(encoding='utf-8'), FIXED)
        self.assertEqual((folder / 'test_calc.py').read_text(encoding='utf-8'), TESTS)

    def test_denied_approval_writes_nothing(self):
        folder = self.bug_folder()
        plan = compile_goal('Fix the bug in calc.py in the calc-bug folder so its tests pass.', self.journal, self.config)
        outcome = self.dispatcher.run(plan, self.env(Model([FIXED]), approve=lambda s, d: False))
        self.assertEqual(outcome.state, 'denied')
        self.assertEqual((folder / 'calc.py').read_text(encoding='utf-8'), BUGGY)

    def test_a_wrong_fix_is_retried_with_the_failure_then_stops(self):
        folder = self.bug_folder()
        model = Model(['def add(a, b):\n    return a * b\n'])
        plan = compile_goal('Fix the bug in calc.py in the calc-bug folder so its tests pass.', self.journal, self.config)
        outcome = self.dispatcher.run(plan, self.env(model))
        self.assertEqual(outcome.state, 'failed')
        self.assertEqual(model.calls, 3)
        self.assertEqual((folder / 'calc.py').read_text(encoding='utf-8'), BUGGY)

    def test_patches_that_touch_tests_or_unsafe_code_are_refused(self):
        repo = {'folder': 'x', 'files': {'calc.py': BUGGY, 'test_calc.py': TESTS}, 'tests': ['test_calc.py']}
        report = A.test(None, {'repo': repo, 'patch': {'test_calc.py': 'pass\n'}}, self.env())['report']
        self.assertEqual(report['ran'], 0)
        report = A.test(None, {'repo': repo, 'patch': {'calc.py': 'import os\nos.remove("x")\n'}}, self.env())['report']
        self.assertIn('unsafe', report['output'])

    def test_folders_outside_the_approved_roots_are_refused(self):
        self.assertIsNone(compile_goal('Fix the bug in the Windows folder', self.journal, self.config))
        with self.assertRaises(A.NotStarted):
            A.inspect(None, {'folder': 'C:\\Windows'}, self.env())


class FileSlice(Base):
    def test_created_file_is_checked_by_the_sealed_verifier(self):
        def create(neuron, inputs, env):
            path = Path(inputs['folder']) / inputs['name']
            path.write_text(inputs['text'] + '\n', encoding='utf-8')
            return {'path': str(path)}
        self.adapters['tool.create_file@v1'] = create
        (self.root / 'notes').mkdir()
        asked = []
        plan = compile_goal('Create a file called note.txt in the notes folder containing exactly: one two three',
                            self.journal, self.config)
        self.assertEqual(plan.workflow, 'file.create_text')
        outcome = self.dispatcher.run(plan, self.env(approve=lambda s, d: asked.append(s) or True))
        self.assertTrue(outcome.verified, outcome.stop_reason)
        self.assertEqual(asked, [])  # tool neurons keep ToolRegistry's own approval rules (legacy parity)

    def test_wrong_content_is_not_reported_as_done(self):
        def create(neuron, inputs, env):
            path = Path(inputs['folder']) / inputs['name']
            path.write_text('exactly: one two three\n', encoding='utf-8')
            return {'path': str(path)}
        self.adapters['tool.create_file@v1'] = create
        (self.root / 'notes').mkdir()
        plan = compile_goal('Create a file called note.txt in the notes folder containing exactly: one two three',
                            self.journal, self.config)
        outcome = self.dispatcher.run(plan, self.env())
        self.assertEqual(outcome.state, 'failed')
        self.assertEqual(outcome.answer, '')


class ModeOn(unittest.TestCase):
    def test_unknown_goals_fall_back_to_legacy_and_off_never_acts(self):
        from jarvis.neural import service
        with tempfile.TemporaryDirectory() as folder:
            config = {'neural': {'mode': 'act', 'journal': str(Path(folder) / 'j.sqlite3')}}
            actions = type('A', (), {'config': config})()
            with unittest.mock.patch.dict('os.environ', {'JARVIS_BRAIN_MODE': ''}):
                self.assertIsNone(service.act(actions, 'open notepad and type hello', lambda: False))
                with unittest.mock.patch.dict('os.environ', {'JARVIS_BRAIN_MODE': 'off'}):
                    self.assertIsNone(service.act(actions, 'Research when the Eiffel Tower was completed',
                                                  lambda: False))
            actions._neural_service.journal.close()


class Durability(Base):
    def test_restart_reuses_done_steps_and_never_replays_an_uncertain_write(self):
        folder = self.bug_folder()
        plan = compile_goal('Fix the bug in calc.py in the calc-bug folder so its tests pass.', self.journal, self.config)
        crash = {'on': True}
        real_apply = self.adapters['skill.code.apply@v1']

        def apply(neuron, inputs, env):
            if crash['on']:
                raise KeyboardInterrupt('power cut')
            return real_apply(neuron, inputs, env)
        self.adapters['skill.code.apply@v1'] = apply
        model = Model([FIXED])
        with self.assertRaises(KeyboardInterrupt):
            self.dispatcher.run(plan, self.env(model))
        self.assertEqual(self.journal.goal(plan.goal_id)['state'], 'open')
        crash['on'] = False
        outcomes = resume_open_goals(self.dispatcher, lambda row: self.env(model))
        self.assertEqual(outcomes[0].state, 'uncertain')
        self.assertEqual(model.calls, 1)  # the patch was not written again
        self.assertEqual((folder / 'calc.py').read_text(encoding='utf-8'), BUGGY)

    def test_read_only_steps_replay_after_a_crash(self):
        plan = compile_goal('Research when the Eiffel Tower was completed', self.journal, self.config)
        crash = {'on': True}

        def analyse(neuron, inputs, env):
            if crash['on']:
                raise KeyboardInterrupt('power cut')
            return A.analyse(neuron, inputs, env)
        self.adapters['skill.research.analyse@v1'] = analyse
        with self.assertRaises(KeyboardInterrupt):
            self.dispatcher.run(plan, self.env())
        crash['on'] = False
        outcome = resume_open_goals(self.dispatcher, lambda row: self.env())[0]
        self.assertTrue(outcome.verified, outcome.stop_reason)
        self.assertEqual((self.calls['search'], self.calls['scrape']), (1, 1))  # done steps were not re-run


class PlanChecks(Base):
    def test_type_mismatch_and_cycles_are_rejected(self):
        bad = Plan(goal_id='g', goal='x', workflow='t', goal_verifier='b', answer_step='b', steps=[
            Step(step_id='a', neuron='skill.code.inspect@v1', bind={'folder': Bind(const='artifact://x')}),
            Step(step_id='b', neuron='verifier.tests_pass@v1', bind={'report': Bind(step='a', port='repo')})])
        outcome = self.dispatcher.run(bad, self.env())
        self.assertEqual(outcome.state, 'blocked')
        self.assertIn('needs TestReport', outcome.stop_reason)
        with self.assertRaises(ValueError):
            Plan(goal_id='g', goal='x', workflow='t', goal_verifier='a', answer_step='a', steps=[
                Step(step_id='a', neuron='n', bind={'x': Bind(step='b', port='y')}),
                Step(step_id='b', neuron='n', bind={'x': Bind(step='a', port='y')})])

    def test_deadline_is_a_stop_reason(self):
        plan = compile_goal('Research when the Eiffel Tower was completed', self.journal, self.config)
        plan = plan.model_copy(update={'deadline_s': 0.05})
        slow = self.adapters['tool.web_search@v1']
        self.adapters['tool.web_search@v1'] = lambda n, i, e: (__import__('time').sleep(0.1), slow(n, i, e))[1]
        self.assertEqual(self.dispatcher.run(plan, self.env()).state, 'deadline')


if __name__ == '__main__':
    unittest.main()


class DesktopWorkflows(Base):
    def test_rename_is_verified_on_disk_and_never_overwrites(self):
        (self.root / 'a.txt').write_text('body\n', encoding='utf-8')
        goal = 'In File Explorer, rename a.txt in the tests-root folder to b.txt.'
        self.config['control']['allowed_roots'] = [str(self.root.parent)]
        plan = compile_goal(goal, self.journal, self.config)
        self.assertEqual(plan.workflow, 'file.rename')
        outcome = self.dispatcher.run(plan, self.env())
        self.assertTrue(outcome.verified, outcome.stop_reason)
        self.assertEqual((self.root / 'b.txt').read_text(encoding='utf-8'), 'body\n')
        self.assertFalse((self.root / 'a.txt').exists())
        (self.root / 'c.txt').write_text('x', encoding='utf-8')
        plan = compile_goal('rename c.txt in the tests-root folder to b.txt', self.journal, self.config)
        self.assertEqual(self.dispatcher.run(plan, self.env()).state, 'failed')
        self.assertEqual((self.root / 'b.txt').read_text(encoding='utf-8'), 'body\n')

    def test_make_folder_and_refuse_names_that_escape(self):
        self.config['control']['allowed_roots'] = [str(self.root.parent)]
        plan = compile_goal('create a new folder named fresh in the tests-root folder', self.journal, self.config)
        self.assertTrue(self.dispatcher.run(plan, self.env()).verified)
        self.assertTrue((self.root / 'fresh').is_dir())
        with self.assertRaises(A.NotStarted):
            A.mkdir(None, {'folder': str(self.root), 'name': '..'}, self.env())
