"""Missing keys must focus their literal producer, never a second consumer."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from jarvis.key_producer import producer,focus,validate_replacement
from jarvis.source_observation import exact_python_edit_spans
from jarvis.coder import Coder
from jarvis.native_coding import run,scoped_schema


SOURCE=('class Port:\n def send(self): return "ok"\nclass Service:\n def __init__(self):\n'
        '  routes = [("west", "send"), ("east", "send")]\n  self.channels={}\n'
        '  for name, action in routes:\n   item=Port()\n'
        '   self.channels[name]=item if name == "west" else [item]\n')
OLD='  routes = [("west", "send"), ("east", "send")]'
NEW='  routes = [("west", "send"), ("east", "send"), ("north", "send")]'


class KeyProducerTests(unittest.TestCase):
    def test_provenance_is_bounded_and_ambiguous_or_computed_producers_are_not_guessed(self):
        spans=exact_python_edit_spans(SOURCE)
        facts=producer(SOURCE,spans,['channels'],'north')
        self.assertEqual(facts['old_string'],OLD);self.assertEqual(facts['key_position'],0)
        contract={'members':['channels'],'obligations':[{'accesses':[{'key':'north'}]}]}
        self.assertEqual(focus(SOURCE,spans,contract,[{'primary_error':"KeyError: 'north'"}]),facts)
        self.assertIsNone(focus(SOURCE,spans,contract,[{'primary_error':"KeyError: 'unknown'"}]))
        for changed in [SOURCE.replace(OLD,'  routes = discover()'),
                        SOURCE.replace('  self.channels={}','  routes.append(("south", "send"))\n  self.channels={}'),
                        SOURCE+' def rewrite(self):\n  self.channels["other"] = Port()\n',
                        SOURCE.replace('   item=Port()','   name="unrelated"\n   item=Port()'),
                        SOURCE.replace('  self.channels={}','  alias=routes\n  self.channels={}'),
                        SOURCE.replace('  self.channels={}','  self.channels={"north": Port()}')]:
            with self.subTest(source=changed):self.assertIsNone(producer(changed,exact_python_edit_spans(changed),['channels'],'north'))
        self.assertIsNone(producer(SOURCE,[],['channels'],'north'))
        self.assertIsNone(producer(SOURCE,spans,['channels'],'west'))

    def test_model_data_addition_cannot_replace_prior_rows_or_add_code(self):
        facts=producer(SOURCE,exact_python_edit_spans(SOURCE),['channels'],'north')
        validate_replacement(OLD,NEW,facts)
        for changed in [OLD,NEW+'\n  invoke()',NEW.replace('"send"','make_action()',1),
                        NEW.replace('"west"','"other"'),NEW.replace('routes =','elsewhere ='),
                        '  routes = [("north", "send"), ("east", "send"), ("west", "send")]',
                        NEW.replace('("north", "send")','("north", "send"), ("north", "send")')]:
            with self.subTest(source=changed),self.assertRaises(ValueError):validate_replacement(OLD,changed,facts)

    def test_real_worker_uses_fresh_producer_scope_and_preserves_existing_bindings(self):
        frozen=('import unittest\nfrom worker import Service\nclass Checks(unittest.TestCase):\n'
                ' def setUp(self):\n  self.service=Service()\n  self.items=self.service.channels\n'
                ' def test_direct(self): self.assertEqual(self.items["west"].send(),"ok")\n'
                ' def test_indexed(self): self.assertEqual(self.items["east"][0].send(),"ok")\n'
                ' def test_missing(self): self.assertEqual(self.items["north"][0].send(),"ok")\n')
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);project=base/'project';project.mkdir();calls=[]
            (project/'worker.py').write_text(SOURCE);(project/'test_worker.py').write_text(frozen)
            plan={'files':[{'path':'worker.py','role':'logic','purpose':'Service'},
                           {'path':'test_worker.py','role':'test','purpose':'Fixed checks'}],
                  'checks':[{'kind':'python_tests','path':'test_worker.py'}]}
            def infer(messages,options,stop,deadline,report,run_path):
                calls.append(options)
                if len(calls)==1:return {'tool':'read_batch','arguments':{'paths':['worker.py','test_worker.py']}}
                if len(calls)==2:return {'tool':'run_checks','arguments':{}}
                if len(calls)==3:return {'tool':'Read','arguments':{'file_path':'worker.py'}}
                if len(calls)>4:self.fail('Unexpected repeated inference')
                scope=options['native_exact_edit_spans']
                self.assertEqual(scope['old_strings'],[OLD]);self.assertIsNone(options['native_diagnostic_window'])
                schema=scoped_schema(run_path,force_tool='Edit',force_edit_paths=['worker.py'],force_edit_spans=scope)
                self.assertEqual([v['properties']['tool']['enum'][0] for v in schema['anyOf']],['Edit'])
                self.assertIn('literal producer',json.dumps(messages))
                stale={**scope,'literal_producer':{**scope['literal_producer'],'binding_line':999}}
                with self.assertRaisesRegex(ValueError,'provenance changed'):
                    scoped_schema(run_path,force_tool='Edit',force_edit_paths=['worker.py'],force_edit_spans=stale)
                return {'tool':'Edit','arguments':{'file_path':'worker.py','old_string':OLD,'new_string':NEW,'replace_all':False}}
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={
                'native_require_repair_progress':True,'native_max_repairs':6,'native_max_turns':16}))
            with patch('jarvis.native_coding.infer',side_effect=infer):
                result=run(coder,project,'Repair service',initial_plan=plan,allowed_paths=['worker.py','test_worker.py'],return_receipt=True)
            self.assertTrue(result['validation']['passed']);self.assertEqual(len(calls),4)
            self.assertEqual((project/'worker.py').read_text(),SOURCE.replace(OLD,NEW))
            self.assertEqual((project/'test_worker.py').read_text(),frozen)
            self.assertEqual(len(result['literal_producer_focus']),1)
            self.assertTrue(result['candidate_decisions'][0]['verified_case_progress'])


if __name__=='__main__':unittest.main()
