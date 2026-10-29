"""Complete read-only model hypotheses never become actions or successful checks."""
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from jarvis.acceptance_observations import load_diagnoses,diagnosis_context
from jarvis.coder import Coder
from jarvis.native_coding import run
from tests.test_acceptance_observations import fixture,SOURCE,TEST,PLAN


def diagnostic_fixture(base):
    _,project,_,value,fixed,required=fixture(base)
    root=base/'runtime/diagnosis-probes';probe=root/('e'*32);raw_path=probe/'model-responses/diagnosis-1/response.txt'
    raw_path.parent.mkdir(parents=True)
    native=root.parent/'autonomous-repair'/('c'*32)/'.jarvis-runtime/native-code'/('b'*32)
    native.mkdir(parents=True)
    campaign=native.parents[2];(campaign/'campaign.json').write_text(json.dumps({'finished_at':'2026-10-28T00:00:00+00:00'}))
    (native/'result.json').write_text(json.dumps({'status':'failed'}))
    immutable=native/('validation-'+'d'*32+'.json')
    validation={'passed':False,'hashes':value['source_before'],'evidence':str(immutable)}
    immutable.write_text(json.dumps(validation));(native/'validation.json').write_text(json.dumps(validation))
    conclusion={'possible':True,'implementation_path':'main.py','approach':'Controlled owned interface hypothesis.',
                'direct_access_resolution':'Preserve direct method access.',
                'indexed_access_resolution':'Preserve indexed method access.','uncertainty':'Real checks remain required.'}
    raw=json.dumps(conclusion).encode();raw_path.write_bytes(raw)
    metadata={'sha256':hashlib.sha256(raw).hexdigest(),'completed':True,'done':True,'done_reason':'stop','served_model':'qwen3.5:9b'}
    raw_path.with_name('metadata.json').write_text(json.dumps(metadata))
    result={'status':'OBSERVED','response_format':'structured','prompt_mode':'receiver_contract_only',
            'input_unchanged':True,'configuration_unchanged':True,'application_acceptance':False,
            'model':'qwen3.5:9b','completion':{'done':True,'done_reason':'stop','served_model':'qwen3.5:9b'},
            'diagnosis':conclusion,'campaign':'c'*32,'input_manifest':{name:{'sha256':sha} for name,sha in value['source_before'].items()}}
    (probe/'result.json').write_text(json.dumps(result))
    return root,project,probe,result,fixed,required,native,raw_path,metadata


class DiagnosticObservations(unittest.TestCase):
    def test_complete_raw_model_conclusion_is_source_bound_untrusted_data(self):
        with tempfile.TemporaryDirectory() as folder:
            root,project,probe,result,fixed,required,*_=diagnostic_fixture(Path(folder))
            before={p:p.read_bytes() for p in project.iterdir()}
            records,manifest=load_diagnoses(root,[probe.name],project,fixed,required,{'main.py'},'qwen3.5:9b')
            self.assertTrue(manifest[0]['accepted']);self.assertEqual(len(records),1)
            messages=diagnosis_context([],project,records)
            self.assertIn('Controlled owned interface hypothesis',messages[0]['content'])
            self.assertIn('untrusted DATA',messages[0]['content']);self.assertIn('not an edit',messages[0]['content'])
            self.assertEqual({p:p.read_bytes() for p in project.iterdir()},before)
            (project/'main.py').write_text(SOURCE+'# drift\n')
            self.assertEqual(diagnosis_context([],project,records),[])
            self.assertEqual(load_diagnoses(root,[probe.name],project,fixed,required,{'main.py'},'qwen3.5:9b')[0],[])

    def test_incomplete_foreign_stale_or_changed_evidence_never_loads(self):
        faults=('identity','length','raw_length','model','raw_model','raw_changed','source','frozen','missing_binding',
                'immutable','native_owner','campaign_owner','input','write_scope','oversize')
        for fault in faults:
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as folder:
                root,project,probe,result,fixed,required,native,raw_path,metadata=diagnostic_fixture(Path(folder));identity=probe.name;writable={'main.py'}
                if fault=='identity':identity='../outside'
                if fault=='length':result['completion']['done_reason']='length'
                if fault=='raw_length':metadata['done_reason']='length'
                if fault=='model':result['model']='foreign-model'
                if fault=='raw_model':metadata['served_model']='foreign-model'
                if fault=='raw_changed':raw_path.write_text('{}')
                if fault=='source':(project/'main.py').write_text(SOURCE+'# drift\n')
                if fault=='frozen':fixed['test_main.py']='f'*64
                if fault=='missing_binding':required.append('extra.py')
                if fault=='immutable':(native/('validation-'+'d'*32+'.json')).write_text('{}')
                if fault=='native_owner':(native/'result.json').write_text('{"status":"running"}')
                if fault=='campaign_owner':(native.parents[2]/'campaign.json').write_text('{}')
                if fault=='input':result['input_manifest']['main.py']['sha256']='f'*64
                if fault=='write_scope':writable=set()
                raw_path.with_name('metadata.json').write_text(json.dumps(metadata))
                (probe/'result.json').write_text('x'*80001 if fault=='oversize' else json.dumps(result))
                records,manifest=load_diagnoses(root,[identity],project,fixed,required,writable,'qwen3.5:9b')
                self.assertEqual(records,[]);self.assertFalse(manifest[0]['accepted'])

    def test_selection_and_closed_conclusion_contract_are_bounded(self):
        with tempfile.TemporaryDirectory() as folder:
            root,project,probe,result,fixed,required,*_=diagnostic_fixture(Path(folder))
            with self.assertRaises(ValueError):load_diagnoses(root,[probe.name]*2,project,fixed,required,{'main.py'},'qwen3.5:9b')
            result['diagnosis']['content']='unassigned source'
            (probe/'result.json').write_text(json.dumps(result))
            self.assertEqual(load_diagnoses(root,[probe.name],project,fixed,required,{'main.py'},'qwen3.5:9b')[0],[])

    def test_native_hypothesis_does_not_grant_source_read_or_check_credit(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root,project,probe,result,fixed,required,*_=diagnostic_fixture(base)
            records,manifest=load_diagnoses(root,[probe.name],project,fixed,required,{'main.py'},'qwen3.5:9b');calls=[]
            def inference(messages,*args):
                calls.append(messages);index=len(calls)
                self.assertIn('Controlled owned interface hypothesis',json.dumps(messages))
                if index==2:
                    self.assertEqual((project/'main.py').read_text(),SOURCE)
                    return {'tool':'read_batch','arguments':{'paths':['main.py','test_main.py']}}
                return {'tool':'Edit','arguments':{'file_path':'main.py','old_string':'return a-b','new_string':'return a+b','replace_all':False}}
            coder=Coder(SimpleNamespace(base=base,report=lambda *a:None),SimpleNamespace(options={
                'coder':'qwen3.5:9b','native_diagnostic_observation_ids':[probe.name]}))
            with patch('jarvis.acceptance_observations.load_diagnoses',return_value=(records,manifest)),patch('jarvis.native_coding.infer',side_effect=inference):
                value=run(coder,project,'Repair service',initial_plan=PLAN,allowed_paths=['main.py','test_main.py'],return_receipt=True)
            self.assertTrue(value['validation']['passed']);self.assertEqual(len(calls),3)
            self.assertEqual(value['progress']['failure_history_versions'],1)
            self.assertTrue(value['imported_diagnostic_observations'][0]['accepted'])
            self.assertEqual((project/'test_main.py').read_text(),TEST)
            self.assertEqual(diagnosis_context([],project,records),[])


if __name__=='__main__':unittest.main()
