import json
from pathlib import Path
import tempfile
import unittest
from jarvis.development_learning import record, recall, fingerprint, feedback, preferences

class LearningTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.root=self.base/'project';self.root.mkdir()
        (self.root/'package.json').write_text('{"dependencies":{"react":"19.3.0"}}')

    def receipt(self,passed):
        views=[]
        for name in ('desktop','mobile','reduced-motion'):
            path=self.root/'.jarvis/development'/name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text('Test evidence fixture; not a screenshot')
            views.append({'screenshot':str(path),'scenarios':[{'passed':True}],'console_errors':[], 'accessibility_violations':[],'horizontal_overflow':False})
        return {'project':str(self.root.resolve()),'stack':'vite','source_fingerprint':fingerprint(self.root),
          'build_passed':passed,'goal_verified':passed,'build':[{'phase':'typecheck','exit_code':0},{'phase':'build','exit_code':0}],
          'browser':{'source':'playwright_chromium','goal_verified':passed,'functional_assertions':3,'functional_interactions':1,'views':views}}

    def test_failure_is_reference_not_success_and_framework_scope(self):
        e=self.receipt(False);record(self.base,self.root,'dashboard',e)
        self.assertFalse(recall(self.base,'vite')[0]['verified'])
        self.assertEqual(recall(self.base,'expo'),[])
        e=self.receipt(True);record(self.base,self.root,'dashboard',e)
        self.assertTrue(any(r['verified'] for r in recall(self.base,'vite')))

    def test_model_success_and_stale_code_rejected(self):
        with self.assertRaises(ValueError):
            record(self.base,self.root,'dashboard',{'stack':'vite','project':str(self.root),'goal_verified':True})
        e=self.receipt(True)
        (self.root/'App.tsx').write_text('changed after checks')
        with self.assertRaises(ValueError):record(self.base,self.root,'dashboard',e)

    def test_explicit_feedback_preserved_without_execution_permission(self):
        feedback(self.base,self.root,'Use larger text','workspace')
        rows=preferences(self.base,self.root)
        self.assertEqual(rows[0]['human_feedback'],'Use larger text')
        self.assertFalse(rows[0]['execution_permission'])
        with self.assertRaises(ValueError): feedback(self.base,self.root,'Fine','unknown')
