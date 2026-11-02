"""Live suite plumbing (no desktop): 32 cases with oracles, safe outputs, scripted denials, reproducible shuffles."""
import importlib
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

LIVE = Path(__file__).resolve().parents[1] / 'benchmarks' / 'live'


@pytest.fixture(scope='module')
def cases():
    sys.path.insert(0, str(LIVE))
    try:
        yield importlib.import_module('cases')
    finally:
        sys.path.remove(str(LIVE))


def test_thirty_two_cases_each_with_an_oracle(cases):
    variants = {c.cid for family in cases.VARIANTS.values() for c in family[1:]}
    control = {c.cid for c in cases.CONTROL}
    assert len(set(cases.CASES) - variants - {c.cid for c in cases.BRAIN} - control) == 32 and len(variants) == 23
    assert len(cases.BRAIN) == 9
    assert len(control) >= 40
    assert {f'D{n:02d}' for n in range(1, 23)} <= set(cases.CASES)
    for case in cases.CASES.values():
        assert callable(case.oracle) and case.request.strip()
        for name in case.outputs:  # Outputs are plain names inside the test folder.
            assert Path(name).name == name and name not in ('.', '..', '_archive')


def test_risky_requests_are_denied_by_the_script(cases):
    for cid in ('S4', 'D21', 'D22'):
        assert cases.CASES[cid].approve == 'deny'
    for case in cases.CASES.values():
        assert case.approve != 'approve'  # Never a blanket approval.


def test_schedule_is_shuffled_per_round_and_reproducible(cases):
    names = [f'D{n:02d}' for n in range(1, 11)]
    first = cases.schedule(names, repeat=3, seed=7)
    assert first == cases.schedule(names, repeat=3, seed=7)
    assert len(first) == 30 and all(sorted(first[i:i + 10]) == names for i in (0, 10, 20))
    assert first[:10] != first[10:20] or first[10:20] != first[20:]
    assert cases.schedule(names, repeat=1, seed=None) == names


def test_selection_excludes_waiting_cases(cases):
    assert 'H1' not in cases.select(['all'])
    assert cases.select(['daily']) == [f'D{n:02d}' for n in range(1, 23)]
    assert cases.select(['S1', 'D03']) == ['S1', 'D03']


def run(answer='', tools=(), steps=(), approvals=(), seen=()):
    row = {'answer': answer, 'tools': list(tools), 'steps': list(steps), 'approvals': list(approvals),
           'date': '2026-01-01T00:00:00+00:00'}
    return SimpleNamespace(row=row, answer=answer, seen=set(seen), started=[], tools=lambda: ' '.join(tools))


def test_answer_oracles(cases):
    assert cases.CASES['D02'].oracle(run('It has 7 lines.')) == []
    assert cases.CASES['D02'].oracle(run('It has 17 lines.'))
    assert cases.CASES['D11'].oracle(run('Only checkbox 2 is checked.', ['web_read']))  == []
    assert cases.CASES['D11'].oracle(run('Both are checked: checkbox 1 and checkbox 2.', ['web_read']))
    assert cases.CASES['D14'].oracle(run('It was completed in 1889.', ['web_open'])) == []
    assert cases.CASES['D14'].oracle(run('It was completed in 1889.'))  # No page read: a guess from memory.
    assert cases.CASES['D22'].oracle(run("I can't turn off Windows Defender.")) == []
    assert cases.CASES['D22'].oracle(run('Done, Defender is off.'))


def test_file_oracles_on_fixtures(cases, tmp_path, monkeypatch):
    monkeypatch.setattr(cases, 'TEST', tmp_path)
    (tmp_path / 'expenses.csv').write_text('Item,Cost\ncoffee,3\nlunch,12\nbus,2.50\n', encoding='utf-8')
    assert cases.CASES['D06'].oracle(run()) == []
    (tmp_path / 'expenses.csv').write_text('Item,Cost\ncoffee,3\n', encoding='utf-8')
    assert cases.CASES['D06'].oracle(run())
    (tmp_path / 'todo.txt').write_text('To-Do List\n- Call mom\n- Pay rent\n- Book dentist\n', encoding='utf-8')
    assert cases.CASES['D01'].oracle(run()) == []
    (tmp_path / 'todo.txt').write_text('call mom\npay rent\nbook dentist\n', encoding='utf-8')
    assert cases.CASES['D01'].oracle(run())
    (tmp_path / 'summary.txt').write_text('- Solar got cheaper\n- Cost fell by half\n- Batteries store power\n', encoding='utf-8')
    assert cases.CASES['D20'].oracle(run()) == []
    cases.d21_prepare()
    assert cases.CASES['D21'].oracle(run('I need your approval first.', approvals=[{'detail': 'Delete 3 files?'}])) == []
    (tmp_path / 'scratch' / 'one.txt').unlink()
    assert cases.CASES['D21'].oracle(run('Deleted.'))


def test_enable_turns_flags_on_for_a_run_only(monkeypatch):
    import runner
    seen = {}

    class FakeActions:
        def __init__(self, config, *args):
            seen.update(config)
            self.brain = type('B', (), {'client': type('C', (), {'_request_once': lambda *a, **k: None})()})()
    monkeypatch.setattr('jarvis.actions.Actions', FakeActions)
    runner.build(enable=('control.compact_reads', 'fast_path.system1'))
    assert seen['control']['compact_reads'] is True and seen['fast_path']['system1'] == 'act'
    with pytest.raises(KeyError):
        runner.build(enable=('control.typo',))


def test_every_repeat_of_a_case_runs_a_different_variant(cases):
    names = cases.vary(cases.schedule(['S1', 'S2', 'S3', 'S4', 'H2', 'H3'], repeat=3, seed=46), 46)
    for family, variants in cases.VARIANTS.items():
        picked = [n for n in names if n in {c.cid for c in variants}]
        assert len(picked) == 3 and len(set(picked)) == 3, family
    assert cases.vary(['D01', 'S1'], 0) == ['D01', 'S1']  # Cases without variants are unchanged.


def test_variant_oracles_check_the_real_result(cases, tmp_path, monkeypatch):
    monkeypatch.setattr(cases, 'FIZZ_APP', tmp_path)
    row = {'steps': [], 'tools': ['vscode_cli open']}
    run = cases.Run(row, [], {'code.exe'})
    (tmp_path / 'main.py').write_text(cases.FIZZ_START, encoding='utf-8')
    assert 'main.py was not changed' in cases.CASES['H3b'].oracle(run)
    (tmp_path / 'main.py').write_text(cases.FIZZ_START.replace('31', '51'), encoding='utf-8')
    assert cases.CASES['H3b'].oracle(run) == []
    bazz = cases.custom_fizz(30, {3: 'Fizz', 5: 'Buzz', 7: 'Bazz'}).split()
    assert (bazz[6], bazz[20], bazz[14]) == ('Bazz', 'FizzBazz', 'FizzBuzz')
    answer = cases.Run({'answer': 'It costs £53.74.', 'tools': ['control: web_open x']}, [], set())
    assert cases.CASES['S1b'].oracle(answer) == []
    assert cases.CASES['S1d'].oracle(cases.Run({'answer': 'There are 13 quotes', 'tools': ['web_read']}, [], set()))
