"""Frozen protocol intent is structural; model prose is not a repair instruction."""
import ast
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from jarvis.repair_contract import build,schema,compile_steps,binding_spans,render_bindings
from jarvis.native_coding import current_test_interfaces
from jarvis.source_observation import exact_python_edit_spans
from jarvis.structured_output import validate_contract


def fixture(base,member='channels',same_key=False):
    source=('class Service:\n def __init__(self):\n  self.'+member+'={}\n'
            '  for name in ("west","east"):\n   item=object()\n   self.'+member+'[name]=[item]\n'
            +''.join('  self.state_'+str(i)+'='+str(i)+'\n' for i in range(40))+
            ' def late_handler(self,event):\n  value=event.value\n  return value\n')
    frozen=('from worker import Service\nclass Checks:\n def setUp(self):\n  self.service=Service()\n'
            '  self.items=self.service.'+member+'\n def test_direct(self): self.items["west"].send()\n'
            ' def test_indexed(self): self.items["'+('west' if same_key else 'east')+'"][0].send()\n')
    (base/'worker.py').write_text(source);(base/'test_worker.py').write_text(frozen)
    files=SimpleNamespace(root=base,tests={'test_worker.py'},fixed_sources={},fixed_tests={},allowed={'worker.py'},
        plan={'files':[{'path':'worker.py','role':'logic'},{'path':'test_worker.py','role':'test'}]})
    source_packet={'file_path':'worker.py','sha256':hashlib.sha256((base/'worker.py').read_bytes()).hexdigest(),'current_source':source}
    messages=current_test_interfaces([{'role':'system','content':'Policy'},{'role':'user','content':'Original goal'}],files)
    return source,files,source_packet,messages


class RepairIntent(unittest.TestCase):
    def test_binding_rendering_preserves_model_ast_literals_and_owned_scope(self):
        old='   self.channels[name]=[item]'
        raw=('class Endpoint:\n def send(self):\n  return """first\n        retained spaces\nlast"""\n'
             'self.channels[name]=Endpoint()')
        arguments={'file_path':'worker.py','source_sha256':'a'*64,
                   'changes':[{'old_string':old,'new_string':raw}]}
        rendered,proof=render_bindings(arguments,['channels']);new=rendered['changes'][0]['new_string']
        original_tree=ast.parse(raw)
        self.assertEqual(ast.dump(ast.parse('if True:\n'+new).body[0].body[-1]),ast.dump(original_tree.body[-1]))
        source='class Service:\n def __init__(self):\n  self.channels={}\n  for name in ("west",):\n'+new+'\n'
        namespace={};exec(compile(source,'controlled-binding.py','exec'),namespace)
        self.assertEqual(namespace['Service']().channels['west'].send(),'first\n        retained spaces\nlast')
        self.assertEqual(arguments['changes'][0]['new_string'],raw)
        self.assertTrue(proof[0]['ast_unchanged']);self.assertNotEqual(proof[0]['proposed_sha256'],proof[0]['rendered_sha256'])
        # Equivalent whitespace/quotes become the same candidate, not another action.
        equivalent={**arguments,'changes':[{'old_string':old,'new_string':'        self.channels[name] = item'}]}
        other={**arguments,'changes':[{'old_string':old,'new_string':'self.channels[name]=item'}]}
        self.assertEqual(render_bindings(equivalent,['channels'])[0],render_bindings(other,['channels'])[0])

    def test_binding_rendering_rejects_noops_invalid_source_and_budget_growth(self):
        from jarvis.structured_output import ModelOutputError
        old='   self.channels[name]=[item]'
        def proposal(new,span=old):return {'changes':[{'old_string':span,'new_string':new}]}
        for new in ['self.channels[name] = [item] # no behavioral change','self.channels[name]=(',
                    '   self.channels[name]=item\nother=1','   self.channels[name]=item\nelse:\n other=1']:
            with self.subTest(new=new),self.assertRaises(ModelOutputError):render_bindings(proposal(new),['channels'])
        with self.assertRaises(ModelOutputError):render_bindings(proposal('self.channels[name]="'+'x'*1200+'"'),['channels'])
        for value,members in [(proposal('self.channels[name]=item'),['other']),
                              (proposal('def run(self):\n return 2','def run(self):\n return 1'),['channels'])]:
            self.assertEqual(render_bindings(value,members),(value,[]))

    def test_bound_schema_recomputes_the_binding_subset_and_caps_changes(self):
        from jarvis.native_coding import scoped_schema
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source,files,packet,messages=fixture(root)
            contract=build(packet,messages,files);spans=binding_spans(source,exact_python_edit_spans(source),contract)
            ledger=root/'ledger';ledger.mkdir()
            (ledger/'request.json').write_text(json.dumps({'project':str(root),'allowed_paths':['worker.py'],
                'validation_contract':files.plan}))
            bounded={'file_path':'worker.py','sha256':packet['sha256'],'old_strings':spans,
                     'binding_members':contract['members'],'allow_batch':True}
            wire=scoped_schema(ledger,force_tool='edit_batch',force_edit_paths=['worker.py'],force_edit_spans=bounded)
            proposal={'tool':'edit_batch','arguments':{'file_path':'worker.py','source_sha256':packet['sha256'],
                'changes':[{'old_string':spans[0],'new_string':spans[0]+' # controlled fixture data'}]}}
            validate_contract(wire,proposal)
            proposal['arguments']['changes']*=2
            with self.assertRaises(ValueError):validate_contract(wire,proposal)
            with self.assertRaisesRegex(ValueError,'spans do not match'):
                scoped_schema(ledger,force_tool='edit_batch',force_edit_paths=['worker.py'],
                              force_edit_spans={**bounded,'binding_members':['unknown_member']})

    def test_structural_intent_excludes_contradictory_prose_and_preserves_each_key(self):
        for member in ('channels','ports'):
            with self.subTest(member=member),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);source,files,packet,messages=fixture(root,member)
                contract=build(packet,messages,files);self.assertIsNotNone(contract)
                self.assertIn('key_specific_values',contract['strategies'])
                self.assertEqual([(r['key'],r['subscripts_after_key']) for r in contract['obligations'][0]['accesses']],
                                 [('west',0),('east',1)])
                bad={'tool':'update_plan','arguments':{'observed_cause':'Wrong invented cause.',
                    'permitted_strategy':'Uniform ordinary values satisfy both forms.','verification':'All checks will pass.'}}
                with self.assertRaises(ValueError):validate_contract(schema(contract),bad)
                proposal={'tool':'update_plan','arguments':{'observed_cause':'CONTRADICTORY_AUDIT_ONLY',
                    'strategy':'key_specific_values','uncertainty':'PREDICTED_SUCCESS_AUDIT_ONLY'}}
                text=json.dumps(compile_steps(proposal,contract))
                self.assertNotIn('CONTRADICTORY_AUDIT_ONLY',text);self.assertNotIn('PREDICTED_SUCCESS',text)
                self.assertIn('west',text);self.assertIn('east',text)
                spans=binding_spans(source,exact_python_edit_spans(source),contract)
                self.assertEqual(spans,['   self.'+member+'[name]=[item]'])
                self.assertEqual((root/'worker.py').read_text(),source)

    def test_same_key_mixed_forms_requires_compatible_owned_value(self):
        with tempfile.TemporaryDirectory() as folder:
            source,files,packet,messages=fixture(Path(folder),same_key=True)
            contract=build(packet,messages,files)
            self.assertNotIn('key_specific_values',contract['strategies'])
            with self.assertRaises(ValueError):compile_steps({'tool':'update_plan','arguments':{
                'observed_cause':'Observed shape.','strategy':'key_specific_values','uncertainty':'Unknown.'}},contract)
            with self.assertRaisesRegex(ValueError,'unresolved'):compile_steps({'tool':'update_plan','arguments':{
                'observed_cause':'Observed shape.','strategy':'unresolved','uncertainty':'Unknown.'}},contract)

    def test_current_hash_and_frozen_binding_are_required(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source,files,packet,messages=fixture(root)
            files.fixed_tests={'test_worker.py':'f'*64};self.assertIsNone(build(packet,messages,files))
            files.fixed_tests={};(root/'worker.py').write_text(source+'# drift\n')
            self.assertIsNone(build(packet,messages,files))

    def test_complete_late_method_is_reachable_within_original_span_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            source,files,packet,messages=fixture(Path(folder))
            spans=exact_python_edit_spans(source)
            self.assertTrue(any('def late_handler' in span and 'return value' in span for span in spans))
            self.assertLessEqual(len(spans),32);self.assertLessEqual(sum(map(len,spans)),6000)
            self.assertTrue(all(source.count(span)==1 for span in spans))


if __name__=='__main__':unittest.main()
