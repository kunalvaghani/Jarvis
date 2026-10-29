"""Generic callback provenance and coordinated caller/callee repair regressions."""
import ast
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from jarvis.callback_contract import routes
from jarvis.coder import Coder
from jarvis.codex_validation import validate_project
from jarvis.execution_contract import focus, statement_cells, compile_statements
from jarvis.native_coding import run, scoped_schema
from jarvis.source_observation import exact_python_edit_spans
from jarvis.structured_output import validate_contract

SOURCE = ('class Router:\n'
 ' def __init__(self):\n'
 '  self.events = {}\n'
 '  choices = [("left", "west"), ("right", "east")]\n'
 '  for label, code in choices:\n'
 '   self.events[label] = lambda value=label: self.send(value)\n'
 '  self.keep = "retained"\n'
 ' def send(self, value):\n'
 '  current = value\n'
 '  if current in ("west", "east"):\n'
 '   return current\n'
 '  return "bad"\n')
FROZEN = ('import unittest\nfrom worker import Router\n'
 'class Checks(unittest.TestCase):\n'
 ' def setUp(self): self.router = Router()\n'
 ' def test_keep(self): self.assertEqual(self.router.keep, "retained")\n'
 ' def test_left(self): self.assertEqual(self.router.events["left"](), "WEST")\n'
 ' def test_right(self): self.assertEqual(self.router.events["right"](), "EAST")\n')
PLAN = {'files': [{'path': 'worker.py', 'role': 'logic', 'purpose': 'Owned routes'},
                  {'path': 'test_worker.py', 'role': 'test', 'purpose': 'Frozen behavior'}],
        'checks': [{'kind': 'python_tests', 'path': 'test_worker.py'}]}


class CallbackContract(unittest.TestCase):
    def test_static_routes_require_observed_setup_and_unique_literal_provenance(self):
        functions = [{'function': 'send', 'definition_line': 8}]
        setup = [{'function': '__init__', 'definition_line': 2}]
        linked = routes(SOURCE, functions, setup)
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0]['captured_name'], 'label')
        self.assertEqual(linked[0]['literal_captures'], [
            {'name': 'label', 'values': ['left', 'right']}, {'name': 'code', 'values': ['west', 'east']}])
        self.assertEqual(routes(SOURCE, functions, []), [])
        for changed in [SOURCE.replace('  for label', '  alias = choices\n  for label'),
                        SOURCE.replace('  for label', '  choices.append(("other", "north"))\n  for label'),
                        SOURCE.replace('   self.events', '   code = label\n   self.events'),
                        SOURCE.replace('lambda value=label', 'lambda value=str(label)'),
                        SOURCE.replace('self.send(value)', 'other.send(value)')]:
            tree = ast.parse(changed)
            target = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == 'send')
            with self.subTest(changed=changed):
                self.assertEqual(routes(changed, [{'function': 'send', 'definition_line': target.lineno}], setup), [])

    def test_nested_callback_edit_preserves_loop_and_unselected_statements(self):
        functions = [{'function': '__init__', 'definition_line': 2, 'callsite_lines': [6]}]
        cells = statement_cells(SOURCE, functions)
        self.assertEqual(len(cells), 1)
        self.assertEqual(cells[0]['statement_path'], [2, 'body', 0])
        contract = {'functions': functions, 'statement_cells': cells}
        args = {'changes': [{'function_id': cells[0]['function_id'], 'statement_id': cells[0]['statement_id'],
            'placement': 'replace', 'statements': [{'kind': 'assign', 'target': 'self.events[label]',
                'expression': 'lambda value=code: self.send(value)'}]}]}
        result, proof = compile_statements(SOURCE, args, contract)
        before = ast.parse(SOURCE).body[0]; after = ast.parse(result).body[0]
        self.assertEqual(ast.dump(before.body[1]), ast.dump(after.body[1]))
        self.assertEqual(ast.dump(before.body[0].body[-1]), ast.dump(after.body[0].body[-1]))
        self.assertEqual(ast.dump(before.body[0].body[2].target), ast.dump(after.body[0].body[2].target))
        self.assertEqual(ast.dump(before.body[0].body[2].iter), ast.dump(after.body[0].body[2].iter))
        self.assertEqual(proof[0]['replaced_statement_paths'], [[2, 'body', 0]])

    def test_real_worker_combines_evidenced_callback_and_executed_handler_in_one_candidate(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); project = base/'project'; project.mkdir(); ledger = base/'ledger'; ledger.mkdir()
            (project/'worker.py').write_text(SOURCE); (project/'test_worker.py').write_text(FROZEN)
            frozen_sha = hashlib.sha256((project/'test_worker.py').read_bytes()).hexdigest()
            calls = []
            def infer(messages, options, *args):
                calls.append(options); index = len(calls)
                if index == 1: return {'tool': 'read_batch', 'arguments': {'paths': ['worker.py', 'test_worker.py']}}
                if index == 2: return {'tool': 'run_checks', 'arguments': {}}
                if index == 3: return {'tool': 'Read', 'arguments': {'file_path': 'worker.py'}}
                if index == 5:return {'tool': 'Read', 'arguments': {'file_path': 'worker.py'}}
                self.assertIn(index, (4, 6))
                scope = options['native_exact_edit_spans']; contract = scope['function_contract']
                self.assertIn('callback_routes', contract)
                self.assertIn('execution alone does not locate the defect', json.dumps(messages))
                cells = contract['statement_cells']
                callback = next(row for row in cells if 'lambda' in row['source'])
                handler = next(row for row in cells if row['function_id'] == 'send:8' and row['statement_id'] == 1)
                changes = [dict(function_id=callback['function_id'], statement_id=callback['statement_id'], placement='replace',
                                statements=[{'kind': 'assign', 'target': 'self.events[label]', 'expression': 'lambda value=code: self.send(value)'}]),
                           dict(function_id=handler['function_id'], statement_id=handler['statement_id'], placement='replace',
                                statements=[{'kind': 'if', 'condition': 'current in ("west", "east")',
                                    'body': [{'kind': 'return', 'expression': 'current.upper()'}]}])]
                value = {'tool': 'edit_batch', 'arguments': {'file_path': 'worker.py', 'source_sha256': scope['sha256'], 'changes': changes[:1] if index == 4 else changes}}
                validate_contract(scoped_schema(args[-1], force_tool='edit_batch', force_edit_paths=['worker.py'], force_edit_spans=scope), value)
                return value
            coder = Coder(SimpleNamespace(base=ledger, report=lambda *args: None), SimpleNamespace(options={
                'native_require_repair_progress': True, 'native_execution_function_repair': True, 'native_max_turns': 16, 'native_max_repairs': 6}))
            with patch('jarvis.native_coding.infer', side_effect=infer):
                receipt = run(coder, project, 'Repair owned event dispatch; preserve frozen tests.', initial_plan=PLAN,
                              allowed_paths=['worker.py', 'test_worker.py'], return_receipt=True)
            self.assertEqual(len(calls), 6)
            self.assertTrue(receipt['validation']['passed'])
            self.assertEqual(hashlib.sha256((project/'test_worker.py').read_bytes()).hexdigest(), frozen_sha)
            self.assertFalse(receipt['candidate_decisions'][0]['verified_case_progress'])
            self.assertTrue(receipt['candidate_decisions'][1]['verified_case_progress'])
            self.assertTrue(all(row['controller_supplied_body'] is False for row in receipt['function_renderings'][0]['changes']))
