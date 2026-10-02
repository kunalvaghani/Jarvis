import json
from pathlib import Path
import tempfile
import unittest
from jarvis.development_projects import scaffold, scaffold_files, batches, requested

class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.events=[]

    def test_four_scaffolds_and_scope(self):
        for stack in ('vite','next','electron','expo'):
            folder=self.root/stack
            folder.mkdir()
            rows=scaffold(folder,stack,lambda:False,lambda *x:self.events.append(x),lambda *x,**kw:None)
            self.assertGreater(len(rows),3)
            self.assertTrue(json.loads((folder/'package.json').read_text())['private'])
            self.assertEqual(scaffold(folder,stack,lambda:False,lambda *x:None,lambda *x,**kw:None),[])
        self.assertIn('sandbox:true', scaffold_files('electron')['electron/main.js'])
        self.assertNotIn('<div',scaffold_files('expo')['src/App.tsx'])

    def test_collision_and_cancellation(self):
        (self.root/'index.html').write_text('user file')
        with self.assertRaises(ValueError):
            scaffold(self.root,'vite',lambda:False,lambda *x:None,lambda *x,**kw:None)
        self.assertFalse((self.root/'package.json').exists())
        (self.root/'index.html').unlink()
        with self.assertRaises(ValueError):
            scaffold(self.root,'vite',lambda:True,lambda *x:None,lambda *x,**kw:None)
        self.assertFalse((self.root/'src').exists())

    def test_batches_and_existing_language(self):
        plan={'files':[{'path':f'src/File{i}.tsx','reason':'component'} for i in range(20)],'directories':['src']}
        self.assertEqual([len(b) for b in batches(plan)], [3,3,3,3,3,3,2])
        plan['files'][1]['path']='../oops.tsx'
        with self.assertRaises(ValueError): batches(plan)
        (self.root/'pyproject.toml').touch()
        self.assertFalse(requested(self.root,'Build React website'))
