"""Sealed verifiers: real-state checks, weak-verifier lint, tamper refusal, and parity with the live oracles."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from jarvis.learning import verifiers
from jarvis.learning.verifiers import base
from jarvis.learning.verifiers.blender_object import BlenderObject
from jarvis.learning.verifiers.python_project import PythonProject
from jarvis.learning.verifiers.text_file import TextFileSaved

BLENDER = Path(r'D:\blender.exe')
FIZZ = '\n'.join('FizzBuzz' if i % 15 == 0 else 'Fizz' if i % 3 == 0 else 'Buzz' if i % 5 == 0 else str(i)
                 for i in range(1, 31))
SHOPPING = dict(title_words=('shopping', 'list'), items=('milk', 'eggs', 'bread'))


# The live S3 file rule as it was before the verifiers (benchmarks/live/cases.py, 2026-10-30): the reference.
LEGACY_POINT = re.compile(r'^\s*(?:[-*\u2022]|\d+[.)])\s+(.+?)\s*$')


def legacy_s3(path):
    if not path.is_file():
        return [f'{path} was not saved']
    lines = [l for l in path.read_text(encoding='utf-8-sig', errors='replace').splitlines() if l.strip()]
    problems = []
    if not lines or not re.search(r'shopping', lines[0], re.I) or not re.search(r'\blist\b', lines[0], re.I) or LEGACY_POINT.match(lines[0]):
        problems.append('title')
    items = [LEGACY_POINT.match(l) for l in lines[1:]]
    if not all(items) or sorted(m.group(1).strip().lower().rstrip('.') for m in items if m) != ['bread', 'eggs', 'milk']:
        problems.append('items')
    return problems


LISTS = {
    'titled': 'Shopping List\n- milk\n- eggs\n- bread\n',
    'numbered': '\ufeffShopping List:\n\n1. Milk\n2. Eggs.\n3. Bread\n',
    'bullets': 'My shopping list\n\u2022 bread\n\u2022 milk\n\u2022 eggs',
    'bare_round_23': 'milk\neggs\nbread\n',
    'no_title': '- milk\n- eggs\n- bread\n',
    'extra_item': 'Shopping List\n- milk\n- eggs\n- bread\n- jam\n',
    'missing_item': 'Shopping List\n- milk\n- eggs\n',
    'prose_line': 'Shopping List\n- milk\n- eggs\nand bread\n',
    'wrong_title': 'Groceries\n- milk\n- eggs\n- bread\n',
}


@pytest.mark.parametrize('name', sorted(LISTS))
def test_text_file_matches_the_legacy_s3_rule(tmp_path, name):
    path = tmp_path / 'shopping.txt'
    path.write_text(LISTS[name], encoding='utf-8')
    verdict = TextFileSaved().check(path=path, **SHOPPING)
    assert verdict.passed == (not legacy_s3(path)), (name, verdict.problems)


def test_text_file_basics(tmp_path):
    path = tmp_path / 'meeting.txt'
    missing = TextFileSaved().check(path=path, lines=['a'])
    assert missing.status == base.FAILED and 'was not saved' in missing.problems[0]
    path.write_text('Meeting at 3pm\r\n\r\nBring laptop\r\n', encoding='utf-8')
    assert TextFileSaved().check(path=path, lines=['Meeting at 3pm', 'Bring laptop']).passed
    assert not TextFileSaved().check(path=path, lines=['Meeting at 4pm', 'Bring laptop']).passed
    stale = TextFileSaved().check(path=path, lines=['Meeting at 3pm', 'Bring laptop'], started_after=time.time() + 60)
    assert not stale.passed and 'not written during this task' in stale.problems[0]


def fake_blender(row):
    def run(command, **kwargs):
        assert command[1] == '-b' and command[-2] == '--'
        return SimpleNamespace(stdout='Blender 4.x\nORACLE' + json.dumps(row) + '\n', stderr='')
    return run


@pytest.mark.parametrize('row,ok', [
    ({'found': True, 'type': 'MESH', 'dims': [2.0, 2.0, 2.0], 'loc': [0, 0, 0]}, True),
    ({'found': True, 'type': 'MESH', 'dims': [1.991, 2.0, 2.009], 'loc': [0.009, 0, 0]}, True),
    ({'found': True, 'type': 'MESH', 'dims': [2.02, 2.0, 2.0], 'loc': [0, 0, 0]}, False),
    ({'found': True, 'type': 'MESH', 'dims': [2.0, 2.0, 2.0], 'loc': [0, 0, 1]}, False),
    ({'found': True, 'type': 'CURVE', 'dims': [2.0, 2.0, 2.0], 'loc': [0, 0, 0]}, False),
    ({'found': False}, False),
])
def test_blender_object_tolerances(tmp_path, row, ok):
    path = tmp_path / 'cylinder.blend'
    path.write_bytes(b'BLENDER')
    verdict = BlenderObject().check(path=path, name='JarvisCylinder', dims=(2, 2, 2), blender=sys.executable,
                                    run=fake_blender(row))
    assert verdict.passed is ok and verdict.status in (base.PASSED, base.FAILED)


def test_blender_cannot_look_is_never_a_pass(tmp_path):
    path = tmp_path / 'cylinder.blend'
    assert not BlenderObject().check(path=path, name='X', blender=sys.executable).passed  # not saved
    path.write_bytes(b'BLENDER')
    absent = BlenderObject().check(path=path, name='X', blender=tmp_path / 'no-blender.exe')
    assert absent.status == base.UNVERIFIABLE and not absent.passed
    garbled = BlenderObject().check(path=path, name='X', blender=sys.executable,
                                    run=lambda *a, **k: SimpleNamespace(stdout='crash', stderr=''))
    assert garbled.status == base.UNVERIFIABLE

    def timeout(*a, **k):
        raise subprocess.TimeoutExpired('blender', 1)
    assert BlenderObject().check(path=path, name='X', blender=sys.executable, run=timeout).status == base.UNVERIFIABLE


@pytest.mark.skipif(not BLENDER.is_file(), reason='Blender is not installed at D:\\blender.exe')
def test_blender_object_on_a_real_file(tmp_path):
    path = tmp_path / 'cylinder.blend'
    make = ('import bpy\nbpy.ops.wm.read_factory_settings(use_empty=True)\n'
            'bpy.ops.mesh.primitive_cylinder_add(radius=1, depth=2, location=(0, 0, 0))\n'
            'bpy.context.active_object.name = "JarvisCylinder"\n'
            f'bpy.ops.wm.save_as_mainfile(filepath={str(path)!r})\n')
    subprocess.run([str(BLENDER), '-b', '--python-expr', make], capture_output=True, timeout=180, check=True)
    assert BlenderObject().check(path=path, name='JarvisCylinder', dims=(2, 2, 2)).passed
    wrong = BlenderObject().check(path=path, name='JarvisCylinder', dims=(2, 2, 3))
    assert not wrong.passed and 'size wrong' in wrong.problems[0]


def project(tmp_path, source):
    folder = tmp_path / 'fizzbuzz-app'
    folder.mkdir()
    (folder / 'main.py').write_text(source, encoding='utf-8')
    return folder


GOOD = ("for i in range(1, 31):\n    print('FizzBuzz' if i % 15 == 0 else 'Fizz' if i % 3 == 0 else "
        "'Buzz' if i % 5 == 0 else i)\n")


@pytest.mark.parametrize('source,ok', [
    (GOOD, True),
    (GOOD.replace('31', '30'), False),
    ('raise SystemExit("boom")\n', False),
    ('print("FizzBuzz")\n', False),
    ('', False),
])
def test_python_project_output(tmp_path, source, ok):
    assert PythonProject().check(folder=project(tmp_path, source), expected_stdout=FIZZ).passed is ok


def test_python_project_timeout_and_isolation(tmp_path):
    hang = PythonProject().check(folder=project(tmp_path, 'while True:\n    pass\n'), expected_stdout='x', timeout=2)
    assert not hang.passed and 'did not finish' in hang.problems[0]
    # Runs from a temporary copy: a sibling module next to the original is not importable.
    other = tmp_path / 'other'
    other.mkdir()
    (other / 'helper.py').write_text('VALUE = 1\n', encoding='utf-8')
    (other / 'main.py').write_text('import helper\nprint(helper.VALUE)\n', encoding='utf-8')
    assert not PythonProject().check(folder=other, expected_stdout='1').passed


def test_python_project_function_calls(tmp_path):
    folder = tmp_path / 'p'
    folder.mkdir()
    (folder / 'sum_list.py').write_text('def total(numbers):\n    return sum(numbers)\n', encoding='utf-8')
    calls = [('module.total([1, 2, 3])', '6'), ('module.total([])', '0'), ('module.total([2.5, 0.5])', '3.0')]
    assert PythonProject().check(folder=folder, entry='sum_list.py', calls=calls).passed
    (folder / 'sum_list.py').write_text('def total(numbers):\n    return 0\n', encoding='utf-8')
    wrong = PythonProject().check(folder=folder, entry='sum_list.py', calls=calls)
    assert not wrong.passed and 'returned 0, expected 6' in wrong.problems[0]
    (folder / 'sum_list.py').write_text('def total(:\n', encoding='utf-8')
    assert 'could not be imported' in PythonProject().check(folder=folder, entry='sum_list.py', calls=calls).problems[0]


def test_weak_verifier_lint():
    class SaysSuccess(base.Verifier):
        NAME = 'says_success'
        READS = frozenset({'answer'})

        def check(self, **params):
            return base.judged([] if 'success' in params['answer'] else ['no success'], {})
    assert base.weak(SaysSuccess)
    assert base.weak(base.Verifier)
    for module, cls in verifiers.REGISTRY.values():
        assert not base.weak(verifiers.load(next(n for n, v in verifiers.REGISTRY.items() if v == (module, cls))))


def test_ai_judge_is_low_confidence_and_reverified():
    verdict = base.Verdict(base.PASSED, kind=base.AI_JUDGE)
    assert verdict.confidence == 'low' and verdict.reverify
    assert base.Verdict(base.PASSED).confidence == 'high'
    with pytest.raises(ValueError):
        base.Verdict(base.PASSED, ('a problem',))
    with pytest.raises(ValueError):
        base.Verdict('maybe')


def test_manifest_matches_and_tampering_is_refused(tmp_path, monkeypatch):
    assert verifiers.tampered() == []
    for name in verifiers.REGISTRY:
        assert verifiers.load(name).NAME == name
    copy = tmp_path / 'verifiers'
    shutil.copytree(verifiers.HERE, copy, ignore=shutil.ignore_patterns('__pycache__'))
    assert verifiers.tampered(copy) == []
    target = copy / 'text_file.py'
    lf = target.read_bytes().replace(b'\r\n', b'\n')
    target.write_bytes(lf.replace(b'\n', b'\r\n'))  # A CRLF checkout is not tampering.
    assert verifiers.tampered(copy) == []
    target.write_text(target.read_text(encoding='utf-8') + '\nPASS_EVERYTHING = True\n', encoding='utf-8')
    assert verifiers.tampered(copy) == ['text_file.py']
    monkeypatch.setattr(verifiers, 'tampered', lambda folder=None: ['text_file.py'])
    with pytest.raises(verifiers.TamperedVerifier):
        verifiers.load('text_file_saved')
    with pytest.raises(KeyError):
        verifiers.load('nope')
