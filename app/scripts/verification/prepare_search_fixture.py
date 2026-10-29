"""Controlled existing-project fixture for Test 9, not autonomous app-generation proof."""
from pathlib import Path
from uuid import uuid4
import hashlib
import json
import sys

BASE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(BASE))

SOURCE='''import argparse
import json

class Notes:
    def __init__(self):
        self._items = {}
        self._next = 1

    def add(self, text):
        if not isinstance(text, str) or not text.strip():
            raise ValueError("A note needs nonempty text")
        identity = self._next
        self._next += 1
        self._items[identity] = text.strip()
        return identity

    def all(self):
        return dict(self._items)

    def remove(self, identity):
        return self._items.pop(identity, None) is not None

def main():
    parser = argparse.ArgumentParser(description="Controlled existing notes application")
    parser.add_argument("command", choices=["list"])
    parser.parse_args()
    notes = Notes()
    for text in ("Red notebook", "Blue folder", "Green pencil"):
        notes.add(text)
    print(json.dumps(notes.all(), sort_keys=True))

if __name__ == "__main__":
    main()
'''

TESTS='''import json
from pathlib import Path
import subprocess
import sys
import unittest
from notes import Notes

class ExistingBehavior(unittest.TestCase):
    def test_add_and_list_are_independent_copies(self):
        notes = Notes()
        identity = notes.add("  Red notebook  ")
        self.assertEqual(notes.all(), {identity: "Red notebook"})
        copied = notes.all()
        copied.clear()
        self.assertEqual(notes.all(), {identity: "Red notebook"})

    def test_remove_and_ids(self):
        notes = Notes()
        first = notes.add("One")
        second = notes.add("Two")
        self.assertNotEqual(first, second)
        self.assertTrue(notes.remove(first))
        self.assertFalse(notes.remove(first))
        self.assertEqual(notes.all(), {second: "Two"})

    def test_validation(self):
        for value in (None, 5, "", "   "):
            with self.assertRaises(ValueError):
                Notes().add(value)

    def test_actual_cli_list(self):
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("notes.py")), "list"],
                                capture_output=True, text=True, timeout=3)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(list(json.loads(result.stdout).values()),
                         ["Red notebook", "Blue folder", "Green pencil"])

if __name__ == "__main__":
    unittest.main()
'''

def main():
    if len(sys.argv)!=2:raise SystemExit('Supply an existing owned fixture-parent directory')
    parent=Path(sys.argv[1]).resolve(strict=True)
    root=parent/('controlled-search-'+uuid4().hex)
    root.mkdir()
    files={'notes.py':SOURCE,'test_notes.py':TESTS,
           'README.md':'# Controlled existing notes fixture\n\nRun `python notes.py list`. The Notes API supports add, all and remove. This is a supervisor-authored controlled Test 9 baseline, not evidence of autonomous project creation. Preserve the existing tests and unrelated file while adding the requested search feature.\n',
           'UNCHANGED.txt':'Controlled unrelated sentinel. Keep these bytes unchanged.\n'}
    for name,content in files.items():(root/name).write_text(content,encoding='utf-8')
    evidence=BASE/'.jarvis-runtime'/('search-fixture-'+uuid4().hex);evidence.mkdir()
    from jarvis.codex_validation import execute_check
    result=execute_check([sys.executable,'-m','unittest','discover','-s',str(root),'-p','test_notes.py','-v'],root,evidence,lambda:False,seconds=15)
    record={'scope':'Controlled supervisor-authored baseline for existing-project modification only; no search implementation supplied.',
            'project':str(root),'evidence':str(evidence),'baseline':result,
            'sha256':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files}}
    (evidence/'fixture.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(record,indent=2))
    if result['exit_code']:raise SystemExit('Baseline failed; retained without running the search task')

if __name__=='__main__':main()
