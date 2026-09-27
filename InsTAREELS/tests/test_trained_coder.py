import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from jarvis.trained_coder import generate


class TrainedCoderTests(unittest.TestCase):
    def test_pathological_source_is_a_failed_case(self):
        from train_coding import inspect_source
        with patch('train_coding.ast.parse',side_effect=MemoryError):
            kind,error=inspect_source('print(1)')
            self.assertEqual(kind,'syntax')
            self.assertIn('nested',error)
        from jarvis.coder import check_content
        with patch('jarvis.coder.ast.parse',side_effect=MemoryError):
            with self.assertRaisesRegex(ValueError,'syntax validation'):
                check_content(Path('main.py'),'print(1)')
        source=(Path.cwd()/'artifacts/qwen-weight-training-20260927-corrective/round-2-evaluation/003-product/main.py')
        if source.is_file():
            self.assertEqual(inspect_source(source.read_text(encoding='utf-8'))[0],'syntax')

    def test_trained_coding_does_not_read_experience_store(self):
        from jarvis.coder import generate_checked
        class Client:
            base=Path.cwd()
            options={'trained_coder_checkpoint':'artifacts/run/round-1'}
            def request(self,operation,cancelled,**request):
                if 'coding_lessons' in request:
                    raise AssertionError('Experience recall leaked into trained-model request')
                return {'content':'print(1)'}
        with patch('jarvis.coding_lessons.recall',side_effect=AssertionError('Experience store was read')):
            self.assertEqual(generate_checked(Client(),lambda:False,Path('main.py'),goal='print one'),'print(1)')

    def test_outside_checkpoint_never_starts_process(self):
        with tempfile.TemporaryDirectory() as name, patch('jarvis.trained_coder.subprocess.run') as run:
            with self.assertRaises(ValueError):
                generate(Path(name), '../elsewhere', {'goal':'x'})
            run.assert_not_called()

    def test_json_inference_and_bounded_failure(self):
        with tempfile.TemporaryDirectory() as name:
            base = Path(name)
            checkpoint = base/'artifacts/run/round-1'
            checkpoint.mkdir(parents=True)
            (checkpoint/'adapter_model.safetensors').write_bytes(b'fixture')
            interpreter = base/'.venv-training/Scripts/python.exe'
            interpreter.parent.mkdir(parents=True)
            interpreter.write_bytes(b'fixture')
            result = subprocess.CompletedProcess([],0,json.dumps({'content':'print(1)'}),'')
            with patch('jarvis.trained_coder.subprocess.run',return_value=result) as run:
                self.assertEqual(generate(base,'artifacts/run/round-1',{'goal':'print one'})['content'],'print(1)')
                self.assertEqual(json.loads(run.call_args.kwargs['input'])['goal'],'print one')
            with patch('jarvis.trained_coder.subprocess.run',side_effect=subprocess.TimeoutExpired([],130)):
                with self.assertRaises(subprocess.TimeoutExpired):
                    generate(base,'artifacts/run/round-1',{'goal':'x'})

    def test_only_explicit_python_route_skips_ollama(self):
        from jarvis.brain_worker import Models
        request = {'operation':'code_edit','path':'main.py', 'options':{'trained_coder_checkpoint':'artifacts/run/round-1'}}
        with patch('jarvis.trained_coder.generate',return_value={'content':'print(1)'}) as trained, \
                patch('jarvis.brain_worker.ensure_server',side_effect=RuntimeError('Ollama not used')):
            self.assertEqual(Models().predict(request)['content'],'print(1)')
            trained.assert_called_once()
            request['path']='index.js'
            with self.assertRaisesRegex(RuntimeError,'Ollama not used'):
                Models().predict(request)


if __name__ == '__main__':
    unittest.main()
