"""Synthetic cases and controlled Win32 doubles; never operate on user applications."""
import copy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from jarvis.actions import Actions
from jarvis.brain import BrainClient
from jarvis.commands import Command
from jarvis.desktop_tasks import close_app
from jarvis.experience_memory import conditions, observe_conditions
from jarvis.obsidian_memory import ObsidianMemory
from jarvis.skill_memory import SkillMemory
from jarvis.task_state import TaskState


class ExperienceMemoryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.memory = ObsidianMemory(self.root, {'enabled': True, 'vault': 'vault'})
        self.skills = SkillMemory(self.memory)
        self.memory.skills = self.skills
        self.bank = self.skills.experiences
        self.current = {'surface': 'Spotify', 'app_fingerprint': 'version-one',
                        'ui_fingerprint': 'layout-one'}

    def task(self, goal='Close Spotify', status='completed', verified=True, failures=None):
        return {'goal': goal, 'kind': 'task', 'status': status, 'result': 'Done',
            'conditions': copy.deepcopy(self.current), 'failures': failures or [],
            'checkpoints': ([{'stage': 'goal_verified', 'source': 'window_state',
                'evidence': 'Window became hidden; process exit is not established.'}] if verified else [])}

    def save(self, **kwargs):
        self.skills.safe_record(self.task(**kwargs))
        self.assertIsNone(self.bank.error)

    def cases(self, **kwargs):
        return self.skills.context('Close Spotify', 'task', conditions=kwargs.get('current', self.current))['experience_context']['cases']

    def test_visual_and_save_observations_are_recalled_without_promoting_goal_success(self):
        task = self.task(verified=False)
        task['checkpoints'] = [
            {'stage':'visual_outcome','source':'fresh_visual_verifier','action':'select','evidence':'Visible destination checked','point':[.5,.5]},
            {'stage':'file_save_verified','source':'disk_readback','action':'save_file','evidence':'Bytes read back; semantics not verified'}]
        self.skills.safe_record(task)
        case = next(iter(self.bank.cases.values()))
        self.assertFalse(case['verified'])
        self.assertEqual({o['source'] for o in case['observations']},{'fresh_visual_verifier','disk_readback'})
        self.assertNotIn('point', json.dumps(case))

    def test_visual_field_payload_is_omitted_from_experience(self):
        task = self.task(verified=False)
        task['checkpoints'] = [{'stage':'visual_outcome','source':'fresh_visual_verifier','action':'fill_text',
                                'evidence':'typed private-example-content'}]
        self.skills.safe_record(task)
        case = next(iter(self.bank.cases.values()))
        self.assertNotIn('private-example-content', json.dumps(case))
        self.assertIn('omitted',case['observations'][0]['evidence'])

    def test_persistence_and_scoped_independent_proof(self):
        self.save()
        loaded = SkillMemory(self.memory)
        rows = loaded.context('Close Spotify', 'task', conditions=self.current)['experience_context']['cases']
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]['verified'])
        self.assertTrue(rows[0]['conditions_match'])
        self.assertEqual(rows[0]['verification'][0]['source'], 'window_state')
        self.assertIn('process exit is not established', rows[0]['verification'][0]['evidence'])
        self.assertTrue(rows[0]['requires_fresh_inspection'])
        self.assertNotIn('steps', rows[0])
        self.assertTrue((self.memory.vault / 'Jarvis Experiences.md').is_file())

    def test_negative_cases_have_reserved_retrieval_slots(self):
        for _ in range(6):
            self.save()
        self.save(status='failed', verified=False, failures=[{'action': 'close_app',
            'reason': 'The selected window changed; nothing was closed.', 'attempted': False}])
        rows = self.cases()
        self.assertLessEqual(len(rows), 4)
        self.assertFalse(rows[0]['verified'])
        self.assertEqual(rows[0]['failures'][0]['class'], 'state_changed')
        self.assertEqual(rows[0]['failures'][0]['outcome'], 'not_executed')
        self.assertTrue(any(row['verified'] for row in rows))

    def test_attempted_failure_cannot_become_positive_even_with_proof(self):
        self.save(failures=[{'action': 'close_app', 'reason': 'Worker stopped', 'attempted': True}])
        row = self.cases()[0]
        self.assertFalse(row['verified'])
        self.assertTrue(row['uncertain'])
        self.assertEqual(row['failures'][0]['class'], 'uncertain_effect')
        self.assertFalse(self.skills.procedures)

    def test_verified_recovery_keeps_failure_and_method_without_promoting_recipe(self):
        task = self.task(failures=[{'action': 'select', 'reason': 'No visible result', 'attempted': False}])
        task['checkpoints'].insert(0, {'stage': 'recovery_planned',
            'evidence': 'Fresh observation followed by alternative actions: search, select'})
        self.skills.safe_record(task)
        row = self.cases()[0]
        self.assertTrue(row['verified'])
        self.assertTrue(row['recovered'])
        self.assertTrue(row['failures'])
        self.assertTrue(row['recovery'][0]['verified'])
        self.assertIn('search, select', row['recovery'][0]['method'])
        self.assertFalse(self.skills.procedures)

    def test_changed_and_missing_conditions_require_inspection(self):
        self.save()
        changed = self.cases(current={'surface': 'Spotify', 'app_fingerprint': 'version-two'})[0]
        self.assertFalse(changed['conditions_match'])
        self.assertEqual(changed['changed_conditions'], ['app_fingerprint'])
        self.assertEqual(changed['missing_conditions'], ['ui_fingerprint'])

    def test_unchanged_navigation_shortcut_and_new_failure_and_success(self):
        task = self.task(goal='Open Chrome and search weather')
        task['checkpoints'].insert(0, {'stage': 'procedure_surface', 'screen': 'Spotify'})
        task['plan'] = {'completed': [{'action': 'search', 'value': 'weather',
            'expected': 'Results visible', 'verified': True}]}
        self.skills.safe_record(task)
        self.assertIsNotNone(self.skills.proposal(task['goal'], 'Spotify', self.current))
        self.assertIsNone(self.skills.proposal(task['goal'], 'Spotify', {**self.current, 'ui_fingerprint': 'changed'}))
        failed = copy.deepcopy(task)
        failed.update(status='failed', result='Window changed')
        self.skills.safe_record(failed)
        self.assertIsNone(self.skills.proposal(task['goal'], 'Spotify', self.current))
        self.skills.safe_record(task)
        self.assertIsNotNone(self.skills.proposal(task['goal'], 'Spotify', self.current))

    def test_legacy_procedure_without_conditions_requires_new_planning(self):
        task = self.task(goal='Open Chrome and search weather')
        task['checkpoints'].insert(0, {'stage': 'procedure_surface', 'screen': 'Spotify'})
        task['plan'] = {'completed': [{'action': 'search', 'value': 'weather',
            'expected': 'Results visible', 'verified': True}]}
        self.skills.safe_record(task)
        next(iter(self.skills.procedures.values())).pop('conditions')
        self.assertIsNone(self.skills.proposal(task['goal'], 'Spotify', self.current))

    def test_procedure_condition_guard_survives_case_index_eviction(self):
        task = self.task(goal='Open Chrome and search weather')
        task['checkpoints'].insert(0, {'stage': 'procedure_surface', 'screen': 'Spotify'})
        task['plan'] = {'completed': [{'action': 'search', 'value': 'weather',
            'expected': 'Results visible', 'verified': True}]}
        self.skills.safe_record(task)
        self.bank.cases.clear()
        self.assertIsNone(self.skills.proposal(task['goal'], 'Spotify', {**self.current, 'app_fingerprint': 'updated'}))
        self.assertIsNone(self.skills.proposal(task['goal'], 'Spotify'))
        self.assertIsNotNone(self.skills.proposal(task['goal'], 'Spotify', self.current))

    def test_expiry_unrelated_goals_and_project_scopes(self):
        self.save()
        self.assertFalse(self.bank.context('Search weather')['cases'])
        row = next(iter(self.bank.cases.values()))
        row['at'] = (datetime.now(timezone.utc) - timedelta(days=91)).isoformat()
        self.assertFalse(self.cases())
        task = self.task(goal='Fix calculator rendering')
        task.update(kind='code_task', project='D:/project')
        self.skills.safe_record(task)
        self.assertTrue(self.bank.context(task['goal'], 'code_task', 'd:\\PROJECT')['cases'])
        self.assertFalse(self.bank.context(task['goal'], 'code_task', 'D:/other')['cases'])
        self.assertFalse(self.bank.context(task['goal'], 'task', 'D:/project')['cases'])

    def test_payload_credentials_and_old_control_ids_excluded(self):
        task = self.task(goal='Type API key private-key-value')
        task['checkpoints'].insert(0, {'stage': 'acting', 'action': 'type_text',
            'target': 'private message body', 'evidence': 'private-key-value', 'control_id': 'old-control'})
        task['failures'] = [{'action': 'type_text', 'attempted': True, 'reason': 'private message body'}]
        self.skills.safe_record(task)
        index = (self.memory.vault / 'Jarvis Experiences.json').read_text()
        for value in ('private-key-value', 'private message body', 'old-control'):
            self.assertNotIn(value, index)
        self.assertFalse(self.bank.context(task['goal']))

    def test_coding_failure_remains_retrievable_without_source_payload(self):
        task = self.task(goal='Fix calculator rendering', status='failed', verified=False,
            failures=[{'action': 'modify_file', 'attempted': False, 'reason': 'Syntax validation failed in private source'}])
        task.update(kind='code_task', project='D:/project')
        task['checkpoints'] = [{'stage': 'generated_file', 'target': 'private source'}]
        self.skills.safe_record(task)
        row = self.bank.context(task['goal'], 'code_task', 'D:/project')['cases'][0]
        self.assertEqual(row['failures'][0]['class'], 'validation')
        self.assertNotIn('private source', json.dumps(row))

    def test_task_finish_delivery_idempotent_and_interruption_uncertain(self):
        state = TaskState(self.root)
        state.on_finish = self.skills.safe_record
        state.start('Close Spotify', 'task')
        state.set_conditions(self.current)
        state.checkpoint('goal_verified', source='window_state', evidence='Window hidden')
        state.finish('completed', 'done')
        self.skills.safe_record(state.snapshot())
        self.assertEqual(len(self.bank.cases), 1)
        state.start('Close Spotify', 'task')
        state.checkpoint('acting', action='close_app')
        interrupted = TaskState(self.root).snapshot()
        self.bank.safe_record(interrupted)
        self.assertTrue(any(c['uncertain'] for c in self.bank.cases.values()))
        self.assertIn('not verified', TaskState.resume_blocker(interrupted))

    def test_retention_shutdown_disable_and_invalid_options(self):
        self.bank.max_cases = 20
        for i in range(25):
            task = self.task()
            task['started_at'] = str(i)
            self.bank.safe_record(task)
        self.assertEqual(len(self.bank.cases), 20)
        before = (self.memory.vault / 'Jarvis Experiences.json').read_bytes()
        self.skills.close()
        self.skills.safe_record(self.task())
        self.assertEqual((self.memory.vault / 'Jarvis Experiences.json').read_bytes(), before)
        memory = ObsidianMemory(self.root, {'enabled': True, 'vault': 'disabled',
            'experience_learning': {'enabled': False, 'max_cases': None}})
        skills = SkillMemory(memory)
        skills.safe_record(self.task())
        self.assertFalse((memory.vault / 'Jarvis Experiences.json').exists())
        self.assertFalse(skills.experiences.context('Close Spotify'))

    def test_malformed_index_preserved_and_guides_still_available(self):
        path = self.memory.vault / 'Jarvis Experiences.json'
        path.parent.mkdir(parents=True)
        path.write_text('{broken', encoding='utf-8')
        damaged = SkillMemory(self.memory)
        damaged.safe_record(self.task())
        self.assertTrue(damaged.experiences.error)
        self.assertEqual(path.read_text(), '{broken')
        self.assertTrue(damaged.context('Search YouTube videos')['skills'])
        self.assertTrue(damaged.context('Close Spotify')['experience_context']['error'])

    def test_invalid_case_schema_cannot_enter_planner(self):
        self.save()
        path = self.memory.vault / 'Jarvis Experiences.json'
        data = json.loads(path.read_text())
        next(iter(data['cases'].values())).pop('observations')
        path.write_text(json.dumps(data), encoding='utf-8')
        loaded = SkillMemory(self.memory)
        self.assertTrue(loaded.experiences.error)
        self.assertFalse(loaded.experiences.cases)

    def test_invalid_index_root_disables_only_case_bank(self):
        path = self.memory.vault / 'Jarvis Experiences.json'
        path.parent.mkdir(parents=True)
        path.write_text('[]', encoding='utf-8')
        loaded = SkillMemory(self.memory)
        self.assertTrue(loaded.experiences.error)
        self.assertTrue(loaded.context('Search YouTube videos')['skills'])
        self.assertEqual(path.read_text(), '[]')

    def test_linked_vault_rejected_without_writing_target(self):
        with patch('jarvis.skill_memory.linked', side_effect=lambda p: p == self.memory.vault):
            loaded = SkillMemory(self.memory)
        self.assertIn('linked vault', loaded.experiences.error)
        self.assertFalse((self.memory.vault / 'Jarvis Experiences.json').exists())

    def test_memory_disk_failure_never_replays_or_changes_action_result(self):
        actions = Actions.__new__(Actions)
        actions._learning_local = threading.local()
        actions.task_state, actions.skills = TaskState(self.root), self.skills
        actions._execute = Mock(return_value='Opened')
        with patch('jarvis.skill_memory.atomic', side_effect=OSError('disk full')):
            self.assertEqual(actions.execute(Command('open', 'spotify')), 'Opened')
        actions._execute.assert_called_once()
        self.assertIn('disk full', self.bank.error)
        self.assertIn('disk full', self.memory.error)

    def test_cancellation_or_error_after_dispatch_is_never_positive(self):
        actions = Actions.__new__(Actions)
        actions._learning_local = threading.local()
        actions.task_state, actions.skills = TaskState(self.root), self.skills
        actions._execute = Mock(return_value='Sent')
        self.assertEqual(actions.execute(Command('open', 'spotify'), lambda: True), 'Sent')
        actions._execute = Mock(side_effect=OSError('worker stopped'))
        with self.assertRaises(OSError):
            actions.execute(Command('open', 'spotify'))
        self.assertTrue(all(c['uncertain'] and not c['verified'] for c in self.bank.cases.values()))
        actions._execute.assert_called_once()

    def test_native_harness_and_hermes_routes_receive_failures(self):
        self.save(status='failed', verified=False, failures=[{'action': 'close_app', 'attempted': False,
            'reason': 'Window changed after update'}])
        for backend in ('native', 'harness', 'hermes'):
            client = BrainClient(self.root, {backend: {'enabled': True}} if backend != 'native' else {})
            self.addCleanup(client.close)
            client.memory = self.memory
            if backend == 'native':
                route = patch.object(client, '_request_once', return_value={'steps': []})
            else:
                worker = Mock()
                setattr(client, backend, worker)
                route = patch.object(worker, 'request', return_value={'steps': []})
            with route as inference:
                for operation in ('plan', 'replan'):
                    client.request(operation, lambda: False, goal='Close Spotify', screen={'title': 'Spotify'})
                    rows = inference.call_args.kwargs['skill_context']['experience_context']['cases']
                    self.assertTrue(rows[0]['failures'])
                    self.assertTrue(rows[0]['missing_conditions'])

    def test_coding_inference_receives_project_scoped_cases(self):
        task = self.task(goal='Fix calculator rendering', status='failed', verified=False)
        task.update(kind='code_task', project='D:/project', result='Syntax validation failed')
        self.skills.safe_record(task)
        client = BrainClient(self.root, {})
        self.addCleanup(client.close)
        client.memory = self.memory
        with patch.object(client, '_request_once', return_value={}) as inference:
            for op in ('code_plan', 'code_edit'):
                client.request(op, lambda: False, goal=task['goal'], skill_project='D:/project')
                self.assertTrue(inference.call_args.kwargs['skill_context']['experience_context']['cases'])

    def test_context_budget_and_no_automatic_dispatch(self):
        for _ in range(8):
            task = self.task()
            task['checkpoints'] *= 3
            task['failures'] = [{'action': 'select', 'attempted': False, 'reason': 'changed ' * 60}] * 3
            self.bank.safe_record(task)
        rows = self.cases()
        self.assertLessEqual(len(json.dumps(rows, ensure_ascii=False)), 6000)
        self.assertNotIn('proposal', json.dumps(rows))
        self.assertNotIn('control_id', json.dumps(rows))

    def test_fingerprints_change_with_manifests_and_labels_not_control_ids(self):
        project = self.root / 'project'
        project.mkdir()
        manifest = project / 'package.json'
        manifest.write_text('{"version":"1"}')
        snapshot = {'title': 'Spotify', 'controls': [{'name': 'Close', 'role': 'Button', 'id': 'old', 'x': 20}]}
        a = conditions(snapshot=snapshot, project=project, tools=[{'action': 'close_app'}])
        snapshot['controls'][0].update(id='new', x=500)
        b = conditions(snapshot=snapshot, project=project, tools=[{'action': 'close_app'}])
        self.assertEqual(a, b)
        snapshot['controls'][0]['name'] = 'Hide'
        manifest.write_text('{"version":"2"}')
        c = conditions(snapshot=snapshot, project=project, tools=[{'action': 'open'}])
        for key in ('ui_fingerprint', 'project_fingerprint', 'tool_fingerprint'):
            self.assertNotEqual(a[key], c[key])
        with patch('jarvis.experience_memory.conditions', side_effect=OSError('unavailable')):
            self.assertEqual(observe_conditions(), {})

    def desktop(self, outcome):
        user = Mock()
        sent = {'value': False}
        user.GetForegroundWindow.return_value = 42
        user.GetWindowThreadProcessId.side_effect = lambda hwnd, ptr: setattr(ptr._obj, 'value', os.getpid() + 100)
        user.GetWindowTextW.side_effect = lambda hwnd, buf, length: setattr(buf, 'value', 'Spotify')
        user.IsWindow.side_effect = lambda hwnd: not (sent['value'] and outcome == 'destroyed')
        user.IsWindowVisible.side_effect = lambda hwnd: not (sent['value'] and outcome == 'hidden')
        def send(*args):
            sent['value'] = True
            return True
        user.PostMessageW.side_effect = send
        return SimpleNamespace(user=user, target=42)

    def test_close_hidden_window_records_scoped_verified_observation(self):
        actions = Actions.__new__(Actions)
        actions._learning_local = threading.local()
        actions.task_state, actions.skills = TaskState(self.root), self.skills
        actions.desktop = self.desktop('hidden')
        actions.apps = {'spotify': ['C:/Spotify.exe']}
        actions.projects = SimpleNamespace(pending=None)
        actions.pending_open = None
        actions.report = Mock()
        actions.ui_controls = None
        with patch('jarvis.desktop_tasks._process_path', return_value=Path('C:/Spotify.exe')):
            result = actions.execute(Command('close_app', 'spotify'))
        self.assertIn('became hidden', result)
        actions.desktop.user.PostMessageW.assert_called_once()
        row = self.bank.context('Close Spotify')['cases'][0]
        self.assertTrue(row['verified'])
        self.assertEqual(row['conditions']['surface'], 'Spotify')
        self.assertIn('tray presence and process exit are not established', row['observations'][0]['evidence'])

    def test_close_destroyed_and_save_prompt_are_distinct(self):
        for outcome, expected, verified in (('destroyed', 'window_destroyed', True),
                                             ('visible', 'window_still_visible', False)):
            desktop, observation = self.desktop(outcome), {}
            with patch('jarvis.desktop_tasks._process_path', return_value=Path('C:/Spotify.exe')), \
                    patch('jarvis.desktop_tasks.time.sleep'):
                close_app(desktop, {'spotify': ['C:/Spotify.exe']}, 'spotify', observed=observation.update)
            self.assertEqual(observation['state'], expected)
            self.assertEqual(observation['verified'], verified)
            desktop.user.PostMessageW.assert_called_once()

    def test_cancel_before_close_does_not_submit_or_invent_observation(self):
        desktop, observation = self.desktop('hidden'), {}
        with patch('jarvis.desktop_tasks._process_path', return_value=Path('C:/Spotify.exe')):
            result = close_app(desktop, {'spotify': ['C:/Spotify.exe']}, 'spotify', lambda: True, observation.update)
        self.assertEqual(result, 'Closing cancelled')
        desktop.user.PostMessageW.assert_not_called()
        self.assertFalse(observation)


if __name__ == '__main__':
    unittest.main()
