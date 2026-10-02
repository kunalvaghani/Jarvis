import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from build_catalog_index import build
from jarvis.actions import Actions
from jarvis.catalog import Catalog, AmbiguousName
from jarvis.commands import parse
from jarvis.folder_lookup import folder_request


class FolderLookupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.paths = [self.base / 'work' / 'Ollama', self.base / 'personal' / 'Ollama', self.base / 'deep' / 'AnotherFolder']
        for p in self.paths:
            p.mkdir(parents=True)
        (self.base / 'file_catalog.json').write_text(json.dumps({'files': [], 'folders': list(map(str, self.paths))}))
        build(self.base)
        self.catalog = Catalog({'apps': {}, 'files_root': 'Files'}, self.base)

    def test_spoken_drive_and_suffix_are_separate(self):
        for phrase in ('Ollama folder in D drive', 'Ollama in D drive', 'Olamind D drive', 'Olamide D drive'):
            name, drive = folder_request(phrase)
            self.assertEqual(drive, 'D')
            self.assertNotIn('drive', name)
            self.assertEqual(parse('open ' + phrase).kind, 'open_folder')
        self.assertEqual(folder_request('AnotherFolder directory'), ('anotherfolder', None))
        self.assertEqual(folder_request(str(self.paths[0])), (str(self.paths[0]), None))

    def test_new_root_folder_does_not_require_catalogue(self):
        fresh = self.base / 'FreshFolder'
        fresh.mkdir()
        with patch.object(self.catalog.folders, 'roots', return_value=[self.base]):
            self.assertEqual(self.catalog.resolve('freshfolder folder', 'folder'), str(fresh))

    def test_literal_folder_suffix_is_not_lost(self):
        fresh = self.base / 'New folder'
        fresh.mkdir()
        with patch.object(self.catalog.folders, 'roots', return_value=[self.base]):
            self.assertEqual(self.catalog.resolve('New folder', 'folder'), str(fresh))

    def test_fuzzy_database_candidates_survive_typo(self):
        self.assertEqual(self.catalog.resolve('AnotherFodler', 'folder'), str(self.paths[2]))
        with self.assertRaises(AmbiguousName):
            self.catalog.resolve('Olama', 'folder')

    def test_usage_prefers_same_name_but_never_write_destination(self):
        with self.assertRaises(AmbiguousName):
            self.catalog.resolve('Ollama', 'folder', prefer_usage=True)
        self.catalog.folders.record_open(str(self.paths[1]), 'Ollama')
        loaded = Catalog({}, self.base)
        self.assertEqual(loaded.resolve('Ollama', 'folder', prefer_usage=True), str(self.paths[1]))
        with self.assertRaises(AmbiguousName):
            loaded.resolve('Ollama', 'folder')
        with self.assertRaises(ValueError):
            loaded.resolve('not-even-similar', 'folder', prefer_usage=True)

    def test_removed_preference_not_used_and_ties_prompt(self):
        for p in self.paths[:2]:
            self.catalog.folders.record_open(str(p), 'Ollama')
        with self.assertRaises(AmbiguousName):
            self.catalog.resolve('Ollama', 'folder', prefer_usage=True)
        self.paths[1].rmdir()
        self.assertEqual(self.catalog.resolve('Ollama', 'folder', prefer_usage=True), str(self.paths[0]))

    def test_drive_restriction_never_falls_back_to_other_drive(self):
        other = 'Z' if self.base.drive.casefold() != 'z:' else 'Y'
        with self.assertRaises(ValueError):
            self.catalog.resolve('Ollama in ' + other + ' drive', 'folder', prefer_usage=True)

    def test_open_only_records_after_dispatch_no_replay_on_save_failure(self):
        config = {'apps': {}, 'files_root': 'Files', 'folders': {'my folder': str(self.paths[0])}, 'memory': {'enabled': True, 'vault': 'vault'}}
        actions = Actions(config, self.base, lambda *_: None)
        self.addCleanup(actions.close)
        with patch('jarvis.actions.os.startfile', side_effect=OSError('launch failed')):
            with self.assertRaises(OSError):
                actions.execute(parse('open folder my folder'))
        self.assertEqual(actions.catalog.folders.history, {})
        with patch('jarvis.actions.os.startfile') as launch:
            actions.execute(parse('open folder my folder'))
            launch.assert_called_once_with(str(self.paths[0]))
        self.assertIn('Accepted folder-open requests', (self.base / 'vault/Jarvis Folder Usage.md').read_text())
        with patch('jarvis.actions.os.startfile') as launch, patch('jarvis.skill_memory.atomic', side_effect=OSError('full')):
            self.assertIn('Opened', actions.execute(parse('open folder my folder')))
            launch.assert_called_once()
        self.assertIn('full', actions.catalog.folders.error)

    def test_corrupt_history_preserved_without_disabling_lookup(self):
        usage = self.base / '.jarvis-runtime/folder-usage.json'
        usage.parent.mkdir()
        usage.write_text('broken')
        loaded = Catalog({}, self.base)
        self.assertTrue(loaded.folders.error)
        loaded.folders.record_open(str(self.paths[2]), 'AnotherFolder')
        self.assertEqual(usage.read_text(), 'broken')
        self.assertEqual(loaded.resolve('AnotherFolder', 'folder'), str(self.paths[2]))


if __name__ == '__main__':
    unittest.main()
