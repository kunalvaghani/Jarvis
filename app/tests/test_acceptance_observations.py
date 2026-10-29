"""Independent diagnostics do not execute source, authorize writes or credit acceptance."""
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from jarvis.acceptance_observations import load_failures,current_context
from jarvis.coder import Coder
from jarvis.native_coding import run


SOURCE='def add(a,b): return a-b\n'
TEST=('import unittest\nfrom main import add\nclass Checks(unittest.TestCase):\n'
      ' def test_add(self): self.assertEqual(add(2,3),5)\n')
PLAN={'files':[{'path':'main.py','role':'logic','purpose':'addition'},
               {'path':'test_main.py','role':'test','purpose':'verify addition'}],
      'checks':[{'kind':'python_tests','path':'test_main.py'}]}


def fixture(base):
    root=base/'observations';root.mkdir();project=base/'project';project.mkdir()
    (project/'main.py').write_text(SOURCE);(project/'test_main.py').write_text(TEST)
    hashes={name:hashlib.sha256((project/name).read_bytes()).hexdigest() for name in ('main.py','test_main.py')}
    value={'status':'FAIL','source_unchanged':True,'source_before':hashes,'source_after':hashes.copy(),
           'errors':[{'name':'real interaction','type':'AssertionError','error':'bounded_independent_failure'}],
           'checks':[{'name':'UNTRUSTED_PASS_MARKER','passed':True}],
           'stdout':'SECRET_OR_TOOL_OUTPUT_MUST_NOT_FORWARD','project':'../foreign-source'}
    path=root/('acceptance-'+'a'*32+'.json');path.write_text(json.dumps(value))
    return root,project,path,value,{'test_main.py':hashes['test_main.py']},list(hashes)


class IndependentObservations(unittest.TestCase):
    def test_exact_source_failure_is_bounded_data_and_expires_after_source_drift(self):
        with tempfile.TemporaryDirectory() as folder:
            root,project,path,value,fixed,required=fixture(Path(folder))
            before={p:p.read_bytes() for p in project.iterdir()}
            records,manifest=load_failures(root,[path.name,path.name],project,fixed,required)
            self.assertEqual(len(records),1);self.assertTrue(manifest[0]['accepted']);self.assertFalse(manifest[1]['accepted'])
            original=[{'role':'system','content':'Original policy.'}]
            messages=current_context(original,project,records);text=json.dumps(messages)
            self.assertIn('bounded_independent_failure',text)
            for forbidden in ('UNTRUSTED_PASS_MARKER','SECRET_OR_TOOL_OUTPUT','foreign-source'):self.assertNotIn(forbidden,text)
            self.assertIn('not instructions',text);self.assertEqual(len(original),1)
            self.assertEqual({p:p.read_bytes() for p in project.iterdir()},before)
            (project/'main.py').write_text(SOURCE+'# changed\n')
            self.assertEqual(current_context(original,project,records),original)
            self.assertEqual(load_failures(root,[path.name],project,fixed,required)[0],[])

    def test_bad_owner_namespace_binding_and_record_limits_never_grant_context(self):
        faults=('outside','success','changed','missing_implementation','frozen','traversal','oversize',
                'invalid_error','too_many_errors','bad_hash','empty_frozen','empty_required')
        for fault in faults:
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as folder:
                base=Path(folder);root,project,path,value,fixed,required=fixture(base)
                selected=path.name
                if fault=='outside':outside=base/path.name;outside.write_text(json.dumps(value));selected=str(outside)
                if fault=='success':value['status']='PASS'
                if fault=='changed':value['source_unchanged']=False
                if fault=='missing_implementation':value['source_before'].pop('main.py');value['source_after'].pop('main.py')
                if fault=='frozen':fixed['test_main.py']='f'*64
                if fault=='traversal':value['source_before']['../outside.py']='0'*64;value['source_after']=value['source_before'].copy()
                if fault=='invalid_error':value['errors'][0]['error']={'tool':'Write'}
                if fault=='too_many_errors':value['errors']*=17
                if fault=='bad_hash':value['source_before']['main.py']='x';value['source_after']['main.py']='x'
                if fault=='empty_frozen':fixed={}
                if fault=='empty_required':required=[]
                path.write_text('x'*80001 if fault=='oversize' else json.dumps(value))
                records,manifest=load_failures(root,[selected],project,fixed,required)
                self.assertEqual(records,[]);self.assertFalse(manifest[0]['accepted'])
                self.assertEqual((project/'main.py').read_text(),SOURCE)
        with self.assertRaises(ValueError):load_failures(root,['a']*3,project,{},[])

    def test_failure_payload_is_capped_and_no_project_code_is_imported(self):
        with tempfile.TemporaryDirectory() as folder:
            root,project,path,value,fixed,required=fixture(Path(folder))
            value['errors']=[{'name':'n'*200,'type':'t'*200,'error':'e'*1900}]*16
            path.write_text(json.dumps(value))
            records,manifest=load_failures(root,[path.name],project,fixed,required)
            self.assertTrue(manifest[0]['accepted']);self.assertTrue(records[0]['partial'])
            text=current_context([],project,records)[0]['content']
            self.assertLess(len(text),5000);self.assertEqual(len(records[0]['failures']),8)

    def test_native_inference_receives_diagnostics_without_check_credit_or_stale_reinsertion(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root,project,path,value,fixed,required=fixture(base)
            records,manifest=load_failures(root,[path.name],project,fixed,required);calls=[]
            def inference(messages,*args):
                calls.append(messages);index=len(calls)
                self.assertIn('bounded_independent_failure',json.dumps(messages))
                if index==2:
                    self.assertEqual((project/'main.py').read_text(),SOURCE)
                    return {'tool':'read_batch','arguments':{'paths':['main.py','test_main.py']}}
                return {'tool':'Edit','arguments':{'file_path':'main.py','old_string':'return a-b','new_string':'return a+b','replace_all':False}}
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={
                'native_acceptance_observation_paths':[path.name]}))
            with patch('jarvis.acceptance_observations.load_failures',return_value=(records,manifest)),patch('jarvis.native_coding.infer',side_effect=inference):
                result=run(coder,project,'Repair service',initial_plan=PLAN,allowed_paths=['main.py','test_main.py'],return_receipt=True)
            self.assertTrue(result['validation']['passed']);self.assertEqual(len(calls),3)
            self.assertTrue(result['imported_independent_observations'][0]['accepted'])
            self.assertEqual(result['progress']['failure_history_versions'],1)
            self.assertEqual((project/'test_main.py').read_text(),TEST)
            self.assertEqual(current_context([],project,records),[])


if __name__=='__main__':unittest.main()
