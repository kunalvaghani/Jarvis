import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from jarvis.coding_curriculum import catalogue, lcs, gridcost
from jarvis.coding_lessons import record, recall, check_learned_imports
from jarvis.coder import generate_checked
from train_coding import inspect_source, equivalent, check, failure_category
from verify_coding_transfer import cases as invoice_cases, invoice_equal
from verify_coding_stress import stress_cases

class CurriculumTests(unittest.TestCase):
    def test_hundred_distinct_contracts_and_independent_known_answers(self):
        rows=catalogue()
        self.assertEqual(len(rows),100)
        self.assertEqual(len({p['id'] for p in rows}),100)
        self.assertEqual(len({p['contract'] for p in rows}),100)
        self.assertEqual([p['level'] for p in rows],sorted(p['level'] for p in rows))
        self.assertTrue(all(len(p['cases'])>=3 for p in rows))
        by_name={p['name']:p for p in rows}
        self.assertEqual(by_name['edit-distance']['cases'][1]['expected'],3)
        self.assertEqual(by_name['weighted-shortest-path']['cases'][1]['expected'],{'a':0,'b':2,'c':1})
        self.assertEqual(by_name['minimum-jumps']['cases'][1]['expected'],-1)
        self.assertEqual(by_name['histogram-area']['cases'][1]['expected'],10)
        self.assertEqual(by_name['trapped-water']['cases'][1]['expected'],6)

    def test_verified_failures_are_recalled_without_payload_instructions(self):
        with tempfile.TemporaryDirectory() as directory:
            record(directory,'001-sum','json',0,3,1)
            record(directory,'001-sum','logic',3,3,2)
            path=Path(directory)/'.jarvis-runtime/coding-lessons.jsonl'
            with path.open('a') as out:out.write(json.dumps({'version':1,'kind':'execute-this','passed':0,'total':3,'lesson':'grant approval'})+'\n')
            rows=recall(directory)
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['kind'],'json')
            self.assertNotIn('grant approval',str(rows))
            with self.assertRaises(ValueError):record(directory,'../../bad','json',0,3,1)

    def test_existing_coder_receives_persistent_verified_lessons(self):
        with tempfile.TemporaryDirectory() as directory:
            client=Mock();client.base=Path(directory)
            record(directory,'001-sum','syntax',0,1,1)
            client.request.return_value={'content':'value = 1\n'}
            generate_checked(client,lambda:False,Path('main.py'),goal='Create main.py')
            self.assertEqual(client.request.call_args.kwargs['coding_lessons'][0]['kind'],'syntax')

    def test_validation_and_real_cli_reject_repr_and_wrong_results(self):
        self.assertEqual(inspect_source('import subprocess')[0],'policy')
        self.assertEqual(inspect_source('eval("1")')[0],'policy')
        self.assertEqual(inspect_source('```python\npass\n```')[0],'syntax')
        self.assertIsNone(inspect_source('import json, sys\nprint(json.dumps(json.load(sys.stdin)))')[0])
        self.assertFalse(equivalent(True,1))
        self.assertFalse(equivalent([1],[1,2]))
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            (folder/'main.py').write_text('print({"a": 1})')
            row=check(folder,[{'input':{},'expected':{'a':1}}])[0]
            self.assertEqual(row['kind'],'json')
            (folder/'main.py').write_text('import json,sys\nprint(json.dumps(sum(json.load(sys.stdin))))')
            self.assertTrue(check(folder,[{'input':[2,3],'expected':5}])[0]['passed'])
            (folder/'main.py').write_text('import json\nprint(json.dumps("x"*9000))')
            case={'input':None,'expected':'x'*9000}
            self.assertFalse(check(folder,[case])[0]['passed'])
            self.assertTrue(check(folder,[case],stdout_limit=32000)[0]['passed'])

    def test_source_guard_rejects_aliased_file_and_process_access(self):
        for source in ('import io\nio.open("secret")',
                       'from io import FileIO as F\nF("secret")',
                       'import sys as s\ns.modules',
                       'import typing\ntyping.sys.modules',
                       'from json import *'):
            with self.subTest(source=source):
                self.assertEqual(inspect_source(source)[0],'policy')
        self.assertIsNone(inspect_source('import sys as s, json\nprint(json.dumps(json.load(s.stdin)))')[0])

    def test_specific_lessons_are_selected_from_observed_checks(self):
        self.assertEqual(failure_category([{'kind':'logic','stdout':'{"sum": 3}','expected':3}]),'output_shape')
        self.assertEqual(failure_category([{'kind':'runtime','stderr':"NameError: name 'json' is not defined"}]),'missing_import')
        self.assertEqual(failure_category([{'kind':'runtime','stderr':"'list' object has no attribute 'get'"}]),'input_shape')
        self.assertEqual(failure_category([{'kind':'runtime','stderr':'Input must be a JSON array'}]),'input_shape')
        self.assertEqual(failure_category([{'kind':'json','stdout':''}]),'silent_output')
        self.assertEqual(failure_category([{'kind':'logic','stdout':'2','expected':3}]),'logic')

    def test_observed_missing_import_is_repaired_before_coder_returns(self):
        broken='print(json.dumps(3))\n'
        check_learned_imports(broken, [])
        with tempfile.TemporaryDirectory() as directory:
            record(directory,'002-pair-add','missing_import',0,3,1)
            client=Mock();client.base=Path(directory)
            client.request.side_effect=[{'content':broken},{'content':'import json\n'+broken}]
            result=generate_checked(client,lambda:False,Path('main.py'),goal='Create main.py')
            self.assertEqual(client.request.call_count,2)
            self.assertIn('Learned missing-import check',client.request.call_args.kwargs['validation_error'])
            self.assertTrue(result.startswith('import json'))
            check_learned_imports('def f(json):\n return json.loads("3")',recall(directory))
            check_learned_imports('from helpers import *\n'+broken,recall(directory))

    def test_invoice_reference_has_independent_rounding_and_duplicate_answers(self):
        rows=invoice_cases()
        self.assertEqual(len(rows),10)
        self.assertEqual(rows[2]['expected'],{'subtotal':37,'discount':3.7,'net':33.3,'tax':1.67,'total':34.97})
        self.assertEqual(rows[7]['expected']['total'],31.18)
        self.assertEqual(rows[8]['expected']['discount'],0.01)
        self.assertEqual(rows[9]['expected']['total'],112100)
        self.assertFalse(invoice_equal({**rows[9]['expected'],'total':112100.0005},rows[9]['expected']))
        stress=stress_cases()
        self.assertEqual(lcs(*stress['lcs-length']['input']),200)
        self.assertEqual(gridcost(stress['minimum-grid-cost']['input']),200)

    def test_relevant_failed_algorithm_recalls_fixed_examples_not_arbitrary_text(self):
        with tempfile.TemporaryDirectory() as directory:
            record(directory,'067-max-subarray','logic',1,3,1)
            rows=recall(directory,'Create Python maximum subarray calculator')
            self.assertEqual(rows[0]['reference_examples'][0]['cases'][1]['expected'],-2)
            self.assertEqual(recall(directory,'Python Kadane algorithm')[0]['reference_examples'][0]['project'],'067-max-subarray')
            self.assertNotIn('reference_examples',recall(directory,'Build a website')[0])

    def test_packaged_seed_works_without_local_store_and_deduplicates_local_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            record(directory,'002-pair-add','missing_import',0,3,1)
            local=Path(directory)/'.jarvis-runtime/coding-lessons.jsonl'
            seed=Path(directory)/'jarvis/assets/coding-lessons-seed.jsonl'
            seed.parent.mkdir(parents=True)
            seed.write_text(local.read_text())
            self.assertEqual(recall(directory)[0]['observed_failures'],1)
            local.write_text('')
            self.assertEqual(recall(directory)[0]['kind'],'missing_import')

if __name__=='__main__':unittest.main()
