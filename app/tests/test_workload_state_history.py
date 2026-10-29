"""Controlled history-contract fixtures; not historical/application acceptance."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from jarvis.workload_state import load_validation_history


def fixture(base):
    root=base/'autonomous-repair';campaign=root/('a'*32)
    native=campaign/'.jarvis-runtime/native-code'/('b'*32)
    snapshot=native/'check-workspace-1';snapshot.mkdir(parents=True)
    (snapshot/'main.py').write_text('value = []\n',encoding='utf-8')
    (snapshot/'test_main.py').write_text('import unittest\nclass Checks(unittest.TestCase):\n def test_value(self):\n  self.assertTrue(True)\n',encoding='utf-8')
    hashes={name:hashlib.sha256((snapshot/name).read_bytes()).hexdigest() for name in ['main.py','test_main.py']}
    checks=[{'kind':'python_tests','path':'test_main.py'}]
    (campaign/'campaign.json').write_text(json.dumps({'finished_at':'2026-10-27T00:00:00+00:00'}))
    (native/'result.json').write_text(json.dumps({'status':'failed'}))
    (native/'request.json').write_text(json.dumps({'validation_contract':{'checks':checks}}))
    validation=native/('validation-'+'c'*32+'.json')
    validation.write_text(json.dumps({'passed':False,'hashes':hashes,'errors':[{'path':'test_main.py',
        'error':'ERROR: test_value (Checks)\nTraceback (most recent call last):\n  File "'+str(snapshot/'test_main.py')+'", line 4\nAttributeError: controlled history fixture\n'}]}))
    return root,validation,snapshot,{'test_main.py':hashes['test_main.py']},checks


class ValidationHistory(unittest.TestCase):
    def test_pinned_failure_loads_read_only_and_duplicates_are_not_reused(self):
        with tempfile.TemporaryDirectory() as folder:
            root,path,snapshot,fixed,checks=fixture(Path(folder))
            before={p:p.read_bytes() for p in snapshot.iterdir()}
            records,manifest=load_validation_history(root,[str(path),str(path)],fixed,checks)
            self.assertEqual(len(records),1)
            self.assertTrue(manifest[0]['accepted']);self.assertFalse(manifest[1]['accepted'])
            self.assertEqual(manifest[0]['validation_sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual({p:p.read_bytes() for p in snapshot.iterdir()},before)

    def test_changed_frozen_checks_owner_and_snapshot_are_excluded(self):
        for change in ['frozen','checks','owner','snapshot','malformed_errors']:
            with self.subTest(change=change),tempfile.TemporaryDirectory() as folder:
                root,path,snapshot,fixed,checks=fixture(Path(folder))
                if change=='frozen':fixed={'test_main.py':'f'*64}
                if change=='checks':checks=[{'kind':'python_tests','path':'other.py'}]
                if change=='owner':(path.parents[3]/'campaign.json').write_text('{}')
                if change=='snapshot':(snapshot/'main.py').write_text('value = 2\n')
                if change=='malformed_errors':
                    value=json.loads(path.read_text());value['errors']='not a record array';path.write_text(json.dumps(value))
                records,manifest=load_validation_history(root,[str(path)],fixed,checks)
                self.assertEqual(records,[]);self.assertFalse(manifest[0]['accepted'])

    def test_namespace_and_size_limits_refuse_untrusted_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root,path,snapshot,fixed,checks=fixture(base)
            outside=base/path.name;outside.write_text('{}')
            records,manifest=load_validation_history(root,[str(outside)],fixed,checks)
            self.assertEqual(records,[]);self.assertIn('namespace',manifest[0]['reason'])
            path.write_text('x'*200001)
            self.assertEqual(load_validation_history(root,[str(path)],fixed,checks)[0],[])
            with self.assertRaises(ValueError):load_validation_history(root,[str(path)]*5,fixed,checks)
            with self.assertRaises(ValueError):load_validation_history(root,[str(path)],{},checks)


if __name__=='__main__':unittest.main()
