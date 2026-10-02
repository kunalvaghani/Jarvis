import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

from add_skill import create
from jarvis.agent_context import selected_skills
from jarvis.agent_tools import execute
from jarvis.obsidian_memory import ObsidianMemory
from jarvis.skill_memory import SkillMemory


class CustomSkillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.memory = ObsidianMemory(self.base, {'enabled': True, 'vault': 'vault'})

    def test_create_discover_context_and_vault_copy(self):
        create(self.base, 'focus-session', 'Start a focus work session', '# Steps\nOpen the requested project and verify the folder.')
        skills = SkillMemory(self.memory)
        self.assertEqual(len(skills.catalog), 10)
        skills.sync()
        self.assertTrue((self.memory.vault / 'Jarvis Skills/Custom/focus-session/SKILL.md').is_file())
        self.assertIn('Jarvis Skills/Custom/focus-session', (self.memory.vault / 'Jarvis Skills.md').read_text())
        self.assertIn('focus-session', [s['name'] for s in skills.context('Start a focus work session')['skills']])
        self.assertEqual(skills.context('Use $custom:focus-session now')['skills'][0]['name'], 'focus-session')
        self.assertEqual(selected_skills(self.base, 'Use $custom:focus-session now'), [])
        actions = SimpleNamespace(skills=skills)
        result = json.loads(execute(actions, {'action': 'skill_read', 'folder': '@jarvis', 'value': 'focus-session'}, lambda: False))
        self.assertIn('verify the folder', result['guidance'])

    def test_helper_rejects_overwrite_and_unsafe_names(self):
        create(self.base, 'focus', 'Focus', 'Open the requested folder.')
        with self.assertRaises(FileExistsError):
            create(self.base, 'focus', 'Focus', 'Replacement')
        for name in ('../escape', 'UpperCase', 'x' * 65):
            with self.assertRaises(ValueError):
                create(self.base, name, 'Focus', 'Body')
        with self.assertRaises(ValueError):
            create(self.base, 'other', 'Line\nbreak', 'Body')

    def test_invalid_or_duplicate_guide_is_visible_and_other_guides_work(self):
        folder = self.base / 'custom-skills/youtube-media'
        folder.mkdir(parents=True)
        (folder / 'SKILL.md').write_text('---\nname: youtube-media\ndescription: Duplicate\n---\n')
        huge = self.base / 'custom-skills/huge'
        huge.mkdir()
        (huge / 'SKILL.md').write_text('x' * 9000)
        skills = SkillMemory(self.memory)
        self.assertEqual(len(skills.catalog), 9)
        self.assertEqual(len(skills.skill_errors), 2)
        skills.sync()
        self.assertIn('Guides needing correction', (self.memory.vault / 'Jarvis Skills.md').read_text())
        self.assertTrue(skills.context('YouTube videos')['skills'])


if __name__ == '__main__':
    unittest.main()
