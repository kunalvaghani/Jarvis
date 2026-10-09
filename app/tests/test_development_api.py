import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from jarvis.development_api import execute
from jarvis.development_native import readiness
from jarvis.task_state import TaskState

class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.actions=Mock(base=self.root)
        self.actions.development_tools=None
        self.actions._task_folder.return_value=str(self.root)
        self.actions.task_state=TaskState(self.root)

    def test_readiness_and_feedback_cannot_be_invented_by_planner(self):
        step={'action':'development_feedback','folder':str(self.root),'value':'Larger text','content':'{"approve_reference":"workspace"}'}
        self.actions.task_state.start('Build a website','task')
        with self.assertRaises(ValueError):execute(self.actions,step,lambda:False)
        self.actions.task_state.start('Design feedback: Larger text. Approve workspace.','task')
        result=json.loads(execute(self.actions,step,lambda:False))
        self.assertEqual(result['approved_reference'],'workspace')
        self.assertFalse(result['execution_permission'])
        self.assertFalse(readiness(self.root,'electron','windows')['ready'])
        with patch.dict('os.environ',{'ANDROID_HOME':'','ANDROID_SDK_ROOT':''}):
            self.assertFalse(readiness(self.root,'expo','android')['ready'])

    def test_static_readiness_does_not_start_preview(self):
        result=json.loads(execute(self.actions,{'action':'development_status','folder':str(self.root),'value':'.'},lambda:False))
        self.assertEqual(len(result['practice']),5)
        self.assertIsNone(result['preview'])
        self.actions._approve.assert_not_called()
        self.actions.development_tools.close()
