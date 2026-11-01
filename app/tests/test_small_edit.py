"""One existing small Python file edited and checked (control.api_routes): independent reference output and,
for a named one-argument function, an independent implementation that must agree on every test input."""
import json
from unittest.mock import Mock

import pytest

from jarvis import small_program
from jarvis.small_edit import change_text, edited, matches_edit, run_small_edit, same_function

START = ("for i in range(1, 31):\n    print('FizzBuzz' if i % 15 == 0 else 'Fizz' if i % 3 == 0 else "
         "'Buzz' if i % 5 == 0 else i)\n")
TO_50 = START.replace('31', '51')
REF_50 = ("print('\\n'.join('FizzBuzz' if n % 15 == 0 else 'Fizz' if n % 3 == 0 else 'Buzz' if n % 5 == 0 "
          "else str(n) for n in range(1, 51)))\n")
PRIME = START + "\n\ndef is_prime(n):\n    return n > 1 and all(n % d for d in range(2, int(n ** .5) + 1))\n"
OTHER_PRIME = "def is_prime(n):\n    if n < 2:\n        return False\n    return all(n % k != 0 for k in range(2, n))\n"
WRONG_PRIME = "def is_prime(n):\n    return n % 2 == 1\n"
EDIT_50 = ('Open VS Code and edit main.py in the fizzbuzz-app folder in my Jarvis test folder so it prints FizzBuzz '
           'for 1 to 50, and save it.')
ADD_PRIME = ('Open VS Code and add a function is_prime(n) to main.py in the fizzbuzz-app folder in my Jarvis test '
             'folder that returns True when n is prime, keep the FizzBuzz output exactly as it is, and save it.')


def model(*replies):
    queue = list(replies)

    def request(operation, cancelled, **data):
        if data['tool'] == 'think':
            return {'text': 'Multiples of 3 print Fizz, of 5 Buzz, of both FizzBuzz, others the number.'}
        return {'text': queue.pop(0)}
    return request


def test_edits_of_one_named_file_match_and_the_change_is_cut_out():
    assert matches_edit(EDIT_50) == 'main.py'
    assert change_text(EDIT_50) == 'edit main.py so it prints FizzBuzz for 1 to 50'
    assert matches_edit('edit main.py and utils.py') is None
    assert matches_edit('add a web app with main.py') is None


def test_a_checked_edit_is_kept():
    assert small_program.output(REF_50)[1] == small_program.output(TO_50)[1]
    assert edited(model(TO_50, REF_50), 'main.py', START, EDIT_50, lambda: False) == (TO_50, [])


def test_an_unchanged_or_disagreeing_edit_is_never_kept():
    off_by_one = TO_50.replace('51', '50')
    new, problems = edited(model(START, REF_50, off_by_one, REF_50), 'main.py', START, EDIT_50, lambda: False)
    assert new is None and 'unchanged' in problems[0] and 'different output' in problems[1]


def test_a_named_function_must_agree_with_an_independent_version():
    # "keep the output": the current program's own output is expected, so no reference program is asked for.
    assert edited(model(PRIME, OTHER_PRIME), 'main.py', START, ADD_PRIME, lambda: False)[0] == PRIME
    changed_output = PRIME.replace('31', '30')
    assert 'different output' in edited(model(changed_output, changed_output), 'main.py', START, ADD_PRIME,
                                        lambda: False)[1][0]
    wrong = PRIME.replace('n > 1 and all(n % d for d in range(2, int(n ** .5) + 1))', 'n % 2 == 1')
    new, problems = edited(model(wrong, OTHER_PRIME, wrong, OTHER_PRIME), 'main.py', START, ADD_PRIME, lambda: False)
    assert new is None and 'is_prime(' in problems[0] and 'independent version' in problems[0]
    assert same_function(PRIME, WRONG_PRIME, 'is_prime')[0] is False
    assert same_function('import os\n' + PRIME, OTHER_PRIME, 'is_prime')[0] is False  # Refused before running.


def test_the_file_is_replaced_through_the_modify_command(tmp_path):
    (tmp_path / 'main.py').write_text(START, encoding='utf-8')
    actions = Mock()
    actions.brain.client.request = model(TO_50, REF_50)

    def execute(command, cancelled):
        assert command.kind == 'modify_in_folder' and command.value == 'main.py'
        data = json.loads(command.extra)
        assert data['find'] == '' and data['folder'] == str(tmp_path)
        (tmp_path / 'main.py').write_text(data['content'], encoding='utf-8')
        return 'Modified'
    actions.execute.side_effect = execute
    assert 'independent reference' in run_small_edit(actions, tmp_path, EDIT_50, 'main.py', lambda: False)
    assert (tmp_path / 'main.py').read_text(encoding='utf-8') == TO_50


def test_a_refused_edit_writes_nothing(tmp_path):
    (tmp_path / 'main.py').write_text(START, encoding='utf-8')
    actions = Mock()
    actions.brain.client.request = model(START, REF_50, START, REF_50)
    with pytest.raises(ValueError, match='was not changed'):
        run_small_edit(actions, tmp_path, EDIT_50, 'main.py', lambda: False)
    actions.execute.assert_not_called()


def test_the_route_edits_existing_files_and_creates_new_ones(tmp_path, monkeypatch):
    import jarvis.small_edit as small_edit
    monkeypatch.setattr(small_edit, 'run_small_edit', lambda *a, **k: 'edited')
    monkeypatch.setattr(small_program, 'run_small_program', lambda *a, **k: 'created')
    on = Mock(config={'control': {'api_routes': True}})
    assert small_program.route(on, tmp_path, 'make main.py that prints hello', lambda: False) == 'created'
    (tmp_path / 'main.py').write_text(START, encoding='utf-8')
    monkeypatch.setattr('jarvis.app_adapters.vscode', lambda argv, cancelled: '')
    assert small_program.route(on, tmp_path, EDIT_50, lambda: False).startswith('edited\nOpened ')
    assert small_program.route(Mock(config={}), tmp_path, EDIT_50, lambda: False) is None
