import json
from pathlib import Path
import tempfile
import unittest
from jarvis.development_knowledge import context, detect_stack, read
from jarvis.agent_context import coding_context, repository_map

class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_auto_retrieval_and_budget(self):
        rows = context(self.root, 'Build animated React dashboard')
        self.assertIn('animation', [r['name'] for r in rows])
        self.assertLessEqual(sum(len(json.dumps(r, ensure_ascii=False)) for r in rows), 5500)
        self.assertTrue(all(r['sources'] and r['reviewed'] for r in rows))
        self.assertEqual(context(self.root, 'React dashboard', 'script.py'), [])
        self.assertNotIn('animation', [r['name'] for r in context(self.root, 'React dashboard')])

    def test_existing_stack_wins(self):
        (self.root/'package.json').write_text('{"dependencies":{"expo":"55.0.0"}}')
        self.assertEqual(detect_stack(self.root, 'React website'), 'expo')
        self.assertIn('expo-platform', [r['name'] for r in context(self.root, 'app')])
        (self.root/'package.json').unlink()
        (self.root/'pyproject.toml').touch()
        self.assertEqual(context(self.root, 'React website'), [])

    def test_runtime_context_and_javascript_map(self):
        (self.root/'App.tsx').write_text('export function Dashboard() { return null; }')
        self.assertIn('Dashboard', repository_map(self.root, ['App.tsx']))
        self.assertTrue(coding_context(self.root, 'React dashboard')['development_skills'])
        self.assertIn('reducedMotion', read('animation'))
        with self.assertRaises(ValueError):
            read('../secret')
        self.assertIn('web-foundations',[r['name'] for r in context(self.root,'Write JavaScript utility','util.js')])
        self.assertNotIn('react-typescript',[r['name'] for r in context(self.root,'Write JavaScript utility','util.js')])
