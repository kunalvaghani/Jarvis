import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from jarvis.coder import check_content, generate_checked, relative_parts, workspace_coding_request
from jarvis.coding_languages import context, evidence_label
from jarvis.commands import parse, normalize_spoken_code_request
from jarvis.development_knowledge import detect_stack


class Languages(unittest.TestCase):
    def test_direct_coder_gpu_setting_is_checked_before_inference(self):
        from jarvis.brain_worker import Models
        from unittest.mock import Mock
        model=Models.__new__(Models);model.client=Mock()
        for invalid in (True,'20',129,-2):
            model.coding_options={'coding_num_gpu':invalid}
            with patch('jarvis.brain_worker.chat') as chat,self.assertRaisesRegex(ValueError,'coding_num_gpu'):
                model.generate('qwen3.5:9b','Edit',{'path':'main.py'},'code_edit')
                chat.assert_not_called()
        model.coding_options={'coding_num_gpu':20}
        with patch('jarvis.brain_worker.chat',return_value='{"content":"x=1","explanation":""}') as chat:
            model.generate('qwen3.5:9b','Edit',{'path':'main.py'},'code_edit')
            self.assertEqual(chat.call_args.args[1]['num_gpu'],20)

    def test_named_languages_route_and_native_stack(self):
        with tempfile.TemporaryDirectory() as folder:
            for language in ('C++', 'C#', 'C', 'Java', 'Go', 'Rust', 'Kotlin'):
                goal = 'create a ' + language + ' desktop app with animated UI'
                self.assertTrue(workspace_coding_request(goal))
                self.assertEqual(parse(goal).kind, 'task')
                self.assertEqual(detect_stack(Path(folder), goal), 'existing')
            self.assertEqual(detect_stack(Path(folder), 'create a standalone HTML website'), 'node')
            self.assertEqual(detect_stack(Path(folder), 'create a React website'), 'vite')

    def test_source_paths_and_voice_spacing(self):
        for filename in ('Main.cs', 'game.cpp', 'game.cxx', 'Main.java', 'App.tsx', 'project.csproj', 'view.xaml'):
            self.assertEqual(str(relative_parts(filename)), filename)
            self.assertEqual(normalize_spoken_code_request('edit' + filename.replace('.', ' . ')), 'edit ' + filename)
            self.assertEqual(parse('edit ' + filename + ' to add UI').kind, 'task')
        for filename in ('../Main.cs', '/Main.cs', 'Main.exe'):
            with self.assertRaises(ValueError): relative_parts(filename)

    def test_correct_context_and_evidence(self):
        guidance = context('add animated UI', 'Main.cs')
        self.assertEqual(guidance['languages'][0]['language'], 'csharp')
        self.assertIn('Application.Run', guidance['languages'][0]['guidance'])
        self.assertIn('compiler', evidence_label('Main.cs'))
        self.assertFalse(workspace_coding_request('create note.txt in documents with hello'))
        from jarvis.projects import has_project_marker
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            self.assertFalse(has_project_marker(root))
            (root/'App.csproj').write_text('<Project />')
            self.assertTrue(has_project_marker(root))
            self.assertEqual(detect_stack(root, 'add animated desktop app UI'), 'existing')

    def test_inline_js_and_xml_fail_before_write(self):
        with self.assertRaisesRegex(ValueError,'unclosed script'):check_content(Path('index.html'),'<script>function unfinished() {')
        with self.assertRaisesRegex(ValueError,'unclosed script'):check_content(Path('index.html'),'<script src="offline.js">')
        with self.assertRaisesRegex(ValueError,'Unicode'):check_content(Path('App.tsx'),'const x="\udc8d";')
        with self.assertRaises(ValueError): check_content(Path('Main.csproj'), '<Project><bad></Project>')
        with self.assertRaises(ValueError): check_content(Path('Main.xaml'), '<!DOCTYPE x><x/>')
        import shutil
        if shutil.which('node'):
            with self.assertRaises(ValueError): check_content(Path('index.html'), '<script>const x = ;</script>')
            with self.assertRaises(ValueError) as failure:
                check_content(Path('index.html'), '<script>const pause=0;'+(' '*3500)+'const pause=1;</script>')
            self.assertIn('SyntaxError:',str(failure.exception)[:700])
            self.assertIn('already been declared',str(failure.exception)[:700])
            check_content(Path('index.html'), '<script type="application/json">{"a":1}</script><script>const x=1;</script>')

    def test_correction_receives_exact_current_and_language(self):
        class Client:
            calls = []
            def request(self, operation, cancelled, **data):
                self.calls.append(data)
                return {'content': '<bad>' if len(self.calls)==1 else '<Project />'}
        client = Client()
        source = '<Project><PropertyGroup /></Project>'
        self.assertEqual(generate_checked(client, lambda: False, Path('App.csproj'), goal='fix C# project', current=source), '<Project />')
        self.assertEqual(len(client.calls), 2)
        self.assertTrue(all(c['current']==source for c in client.calls))
        self.assertIn('language_context', client.calls[0])
        self.assertIn('invalid', client.calls[1]['validation_error'])
        with self.assertRaises(ValueError): generate_checked(client, lambda: True, Path('Main.cs'), goal='create C# app')


if __name__ == '__main__': unittest.main()
