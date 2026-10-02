import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from jarvis.hermes import REVISION
from jarvis.hermes_skills import HermesSkills
from jarvis.obsidian_memory import ObsidianMemory
from jarvis.skill_memory import SkillMemory
from jarvis.agent_tools import execute


class HermesSkillsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'integrations/hermes-agent'
        self.rows = []
        for name, platforms in [('python-debugging', ['windows']), ('mac-reminders', ['macos'])]:
            folder = self.root / 'skills/development' / name
            folder.mkdir(parents=True)
            files = []
            for relative, body in [('SKILL.md', f'---\nname: {name}\ndescription: Debug Python.\n---\nFull guide.\n'),
                                   ('references/details.md', 'Complete reference.'),
                                   ('scripts/helper.py', "raise AssertionError('never execute')")]:
                path = folder / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                raw = body.encode('utf-8'); path.write_bytes(raw)
                files.append({'path': relative, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
            self.rows.append({'name': name, 'description': 'Debug Python.', 'source': 'skills',
                              'category': 'development', 'directory': folder.relative_to(self.root).as_posix(),
                              'platforms': platforms, 'tags': ['debugging'], 'prerequisites': {'commands': ['optional-cli']},
                              'conditions': {}, 'files': files})
        self.manifest = self.base / 'integrations/hermes-skills.json'
        self.write_manifest()
        (self.base / 'integrations/HERMES-LICENSE').write_text('MIT attribution', encoding='utf-8')
        self.catalog = HermesSkills(self.base)

    def write_manifest(self, revision=REVISION):
        self.manifest.write_text(json.dumps({'version': 1, 'revision': revision, 'skills': self.rows}), encoding='utf-8')

    def test_platform_filter_and_requirements_are_not_assumed(self):
        rows = self.catalog.search('Python debugging')
        self.assertEqual([r['name'] for r in rows], ['python-debugging'])
        self.assertFalse(rows[0]['requirements_verified'])
        self.assertEqual(len(self.catalog.search('.', include_unsupported=True)), 2)
        with self.assertRaisesRegex(ValueError, 'Windows support'):
            self.catalog.read('mac-reminders')

    def test_full_references_are_read_and_no_partial_body_is_loaded(self):
        result = self.catalog.read('python-debugging', 'references/details.md')
        self.assertEqual(result['guidance'], 'Complete reference.')
        self.assertIn('approval', result['contract'])
        with self.assertRaisesRegex(ValueError, 'No partial guide'):
            self.catalog.read('python-debugging', limit=1)

    def test_changed_copy_or_unindexed_path_is_rejected(self):
        with self.assertRaises(ValueError):
            self.catalog.read('python-debugging', '../outside.txt')
        path = self.root / self.rows[0]['directory'] / 'SKILL.md'
        path.write_text('tampered guide', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.catalog.read('python-debugging')

    def test_revision_mismatch_disables_only_upstream_catalogue(self):
        self.write_manifest(revision='wrong')
        self.assertTrue(HermesSkills(self.base).error)

    def test_sync_copies_helpers_without_execution_and_links_catalogue(self):
        memory = ObsidianMemory(self.base, {'enabled': True, 'vault': 'vault', 'hermes_skills': True})
        skills = SkillMemory(memory)
        skills.sync()
        target = memory.vault / 'Jarvis Skills/Hermes' / self.rows[0]['directory']
        self.assertEqual((target / 'scripts/helper.py').read_text(), "raise AssertionError('never execute')")
        self.assertIn('platform unsupported', (memory.vault / 'Jarvis Hermes Skills.md').read_text())
        self.assertIn('[[Jarvis Hermes Skills]]', (memory.vault / 'Jarvis Skills.md').read_text())
        self.assertFalse(skills.procedures)

    def test_cancellation_does_not_continue_copying(self):
        destination = self.base / 'cancelled'
        self.assertEqual(self.catalog.sync(lambda name: destination / name, lambda: True), 0)
        self.assertFalse(destination.exists())

    def test_existing_skill_tools_use_reserved_source_without_folder_question(self):
        actions = SimpleNamespace(skills=SimpleNamespace(upstream=self.catalog), _task_folder=Mock(side_effect=AssertionError('must not resolve project')))
        result = execute(actions, {'action': 'skill_read', 'folder': '@hermes', 'value': 'python-debugging', 'content': 'references/details.md'}, lambda: False)
        self.assertEqual(json.loads(result)['guidance'], 'Complete reference.')
        actions._task_folder.assert_not_called()

    def test_failed_upstream_read_does_not_disable_native_guides(self):
        memory = ObsidianMemory(self.base, {'enabled': True, 'vault': 'vault', 'hermes_skills': True})
        skills = SkillMemory(memory)
        (self.root / self.rows[0]['directory'] / 'SKILL.md').write_text('changed', encoding='utf-8')
        context = skills.context('Python debugging YouTube')
        self.assertTrue(skills.upstream_error)
        self.assertTrue(context['skills'])
        self.assertIsNone(skills.error)

    def test_explicit_names_use_complete_guidance(self):
        result = self.catalog.context('use $hermes:python-debugging to inspect this issue')
        self.assertEqual(result['skills'][0]['name'], 'python-debugging')
        self.assertIn('Full guide.', result['skills'][0]['guidance'])

    def test_upstream_namespace_does_not_become_a_missing_project_skill(self):
        from jarvis.agent_context import selected_skills
        self.assertEqual(selected_skills(self.base, 'use $hermes:python-debugging'), [])

    def test_media_compiler_does_not_load_irrelevant_upstream_bodies(self):
        memory = ObsidianMemory(self.base, {'enabled': True, 'vault': 'vault', 'hermes_skills': True})
        skills = SkillMemory(memory)
        upstream = skills.context('search YouTube for robot tutorials')['upstream_skills']
        self.assertNotIn('skills', upstream)
        self.assertIn('native Jarvis guides', upstream['notice'])

    def test_disconnected_browser_reopens_only_for_explicit_new_task(self):
        from jarvis.browser_worker import Session
        session = Session()
        old = session.context = Mock()
        session.page = Mock()
        session.page.is_closed.return_value = False
        session.user_closed = True
        with self.assertRaisesRegex(ValueError, 'closed deliberately'):
            session.perform({'operation': 'inspect'})
        old.close.assert_not_called()
        session.open = Mock(side_effect=lambda *_: setattr(session, 'page', Mock()))
        session.search = Mock(return_value={'verified': True})
        self.assertTrue(session.perform({'operation': 'search', 'new_task': True, 'value': 'cats'})['verified'])
        old.close.assert_called_once()
        session.open.assert_called_once()
