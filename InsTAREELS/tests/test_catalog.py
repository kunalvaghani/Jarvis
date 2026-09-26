import json
from pathlib import Path
import tempfile
import unittest
from jarvis.catalog import Catalog
from jarvis.commands import Command, parse
from build_catalog_index import build


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.first = self.base / "work"
        self.second = self.base / "personal"
        self.first.mkdir()
        self.second.mkdir()
        for folder in (self.first, self.second):
            (folder / "notes.txt").write_text("example")
        self.data = {"files": [str(folder / "notes.txt") for folder in (self.first, self.second)], "folders": [str(self.first), str(self.second)]}
        (self.base / "file_catalog.json").write_text(json.dumps(self.data))
        self.config = {"file_catalog": "file_catalog.json", "files": {"my notes": str(self.first / "notes.txt")}}

    def test_explicit_alias(self):
        self.assertEqual(Catalog(self.config, self.base).resolve("my notes", "file"), str(self.first / "notes.txt"))

    def test_duplicate_names_require_specificity(self):
        with self.assertRaisesRegex(ValueError, "2 matches"):
            Catalog(self.config, self.base).resolve("notes dot txt", "file")

    def test_database_lookup_and_parent_disambiguation(self):
        build(self.base)
        catalog = Catalog(self.config, self.base)
        self.assertEqual(catalog.resolve("work notes dot txt", "file"), str(self.first / "notes.txt"))
        self.assertEqual(catalog.resolve("personal", "folder"), str(self.second))
        with self.assertRaisesRegex(ValueError, "2 matches"):
            catalog.resolve("notes", "file")

    def test_stale_index_is_rejected(self):
        build(self.base)
        (self.base / "file_catalog.json").write_text(json.dumps(self.data) + " ")
        with self.assertRaisesRegex(ValueError, "outdated"):
            Catalog(self.config, self.base).resolve("notes", "file")

    def test_open_file_and_folder_parsing(self):
        self.assertEqual(parse("open file notes dot txt"), Command("open_file", "notes dot txt"))
        self.assertEqual(parse("open folder downloads"), Command("open_folder", "downloads"))


if __name__ == "__main__":
    unittest.main()
