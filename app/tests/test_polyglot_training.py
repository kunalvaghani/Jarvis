"""Check the authored examples used for non-Python weight updates."""
from pathlib import Path
import shutil
import tempfile
import unittest

from jarvis.polyglot_training_data import TASKS
from scripts.training.train_polyglot_qwen import verify_reference


class PolyglotTrainingDataTests(unittest.TestCase):
    def test_project_splits_and_languages(self):
        self.assertEqual(len(TASKS), len({row['id'] for row in TASKS}))
        self.assertEqual({row['language'] for row in TASKS}, {'javascript', 'sql'})
        self.assertEqual(sum(row['split'] == 'heldout' for row in TASKS), 4)
        self.assertEqual(sum(row['split'] == 'train' for row in TASKS), 16)

    def test_authored_references_pass_cases(self):
        if not shutil.which('node'):
            self.skipTest('Node.js is required to verify JavaScript training references')
        with tempfile.TemporaryDirectory() as directory:
            for row in TASKS:
                with self.subTest(task=row['id']):
                    verify_reference(row, Path(directory) / row['id'])


if __name__ == '__main__':
    unittest.main()
