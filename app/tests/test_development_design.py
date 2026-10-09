import json
from pathlib import Path
import tempfile
import unittest
from jarvis.development_design import specification, save_spec

class DesignTests(unittest.TestCase):
    def test_brief_saved_before_code_without_fabricated_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            spec=specification(root,'Animated dashboard for mobile','vite')
            for key in ('audience','primary_task','layout','typography','palette','spacing','components','states','motion','acceptance'):
                self.assertTrue(spec[key])
            self.assertTrue(all(not r['approved'] for r in spec['reference_interfaces']))
            first=save_spec(root,spec,lambda:False)
            second=save_spec(root,spec,lambda:False)
            self.assertNotEqual(first,second)
            self.assertEqual(json.loads(first.read_text())['goal'],spec['goal'])
            with self.assertRaises(ValueError): save_spec(root,spec,lambda:True)
