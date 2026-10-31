"""Small single-file programs (control.api_routes): kept only when an independent reference prints the same."""
import json
from unittest.mock import Mock

import pytest

from jarvis import small_program
from jarvis.small_program import agreed, matches, run_small_program, source

H3 = ('Open VS Code, create a new project folder called fizzbuzz-app in my Jarvis test folder, add main.py that '
      'prints FizzBuzz for 1 to 30, and save it.')
FIZZ = ("for i in range(1, 31):\n    print('FizzBuzz' if i % 15 == 0 else 'Fizz' if i % 3 == 0 else "
        "'Buzz' if i % 5 == 0 else i)\n")
REFERENCE = ("print('\\n'.join('FizzBuzz' if n % 15 == 0 else 'Fizz' if n % 3 == 0 else 'Buzz' if n % 5 == 0 "
             "else str(n) for n in range(1, 31)))\n")


@pytest.mark.parametrize('goal,name', [
    (H3, 'main.py'), ('write hello.py that prints Hello, Jarvis', 'hello.py'),
    ('make a script count.py in my test folder that outputs the numbers 1 to 5', 'count.py'),
])
def test_print_only_single_file_requests_match(goal, name):
    assert matches(goal) == name


@pytest.mark.parametrize('goal', [
    'build a todo app with a GUI in app.py that shows tasks', 'write main.py and utils.py that print hi',
    'create main.py with unit tests that prints hi', 'add index.html and main.py that prints hi',
    'write main.py for a web app server', 'refactor main.py', 'create sum_list.py with a function total(numbers)',
])
def test_bigger_or_non_printing_requests_keep_the_coder(goal):
    assert matches(goal) is None


def test_fenced_replies_become_source():
    assert source({'text': '```python\nprint(1)\n```'}) == 'print(1)\n'
    assert source({'text': 'print(2)'}) == 'print(2)\n'


def model(*replies):
    queue = list(replies)
    calls = []

    def request(operation, cancelled, **data):
        calls.append(data)
        return {'text': queue.pop(0)}
    return request, calls


def test_agreeing_independent_programs_are_kept():
    request, calls = model(FIZZ, REFERENCE)
    code, problems = agreed(request, 'main.py', H3, lambda: False)
    assert code == FIZZ and problems == []
    assert len(calls) == 2 and all(c['tool'] == 'write_code' for c in calls)
    assert 'reference' in calls[1]['goal'] or 'prints exactly' in calls[1]['goal']


def test_disagreement_retries_once_then_writes_nothing():
    wrong = FIZZ.replace('range(1, 31)', 'range(1, 30)')
    request, calls = model(wrong, REFERENCE, wrong, REFERENCE)
    code, problems = agreed(request, 'main.py', H3, lambda: False)
    assert code is None and len(calls) == 4 and len(problems) == 2 and 'different output' in problems[0]
    request, _ = model(wrong, REFERENCE, FIZZ, REFERENCE)
    assert agreed(request, 'main.py', H3, lambda: False)[0] == FIZZ


@pytest.mark.parametrize('main,ref,why', [
    ('raise SystemExit(2)\n', REFERENCE, 'failed to run'), ('x = 1\n', 'x = 1\n', 'printed nothing'),
    (FIZZ, 'raise ValueError()\n', 'reference failed'), ('while True:\n    pass\n', REFERENCE, 'failed to run'),
])
def test_broken_programs_are_never_kept(main, ref, why, monkeypatch):
    monkeypatch.setattr(small_program, 'TIMEOUT', 2.0)
    request, _ = model(main, ref, main, ref)
    code, problems = agreed(request, 'main.py', H3, lambda: False)
    assert code is None and why in problems[0]


def test_run_creates_the_file_through_the_create_command(tmp_path):
    project = tmp_path / 'fizzbuzz-app'
    project.mkdir()
    actions = Mock()
    actions.brain.client.request, _ = model(FIZZ, REFERENCE)

    def execute(command, cancelled):
        assert command.kind == 'create_in_folder' and command.value == 'main.py'
        data = json.loads(command.extra)
        (project / command.value).write_text(data['content'], encoding='utf-8')
        return 'created'
    actions.execute.side_effect = execute
    result = run_small_program(actions, project, H3, 'main.py', lambda: False)
    assert 'independent reference' in result and (project / 'main.py').read_text(encoding='utf-8') == FIZZ
    from jarvis.learning.verifiers import load
    fizz = '\n'.join('FizzBuzz' if i % 15 == 0 else 'Fizz' if i % 3 == 0 else 'Buzz' if i % 5 == 0 else str(i)
                     for i in range(1, 31))
    assert load('python_project').check(folder=project, entry='main.py', expected_stdout=fizz).passed


def test_existing_file_is_never_overwritten(tmp_path):
    (tmp_path / 'main.py').write_text('keep', encoding='utf-8')
    actions = Mock()
    with pytest.raises(ValueError, match='already exists'):
        run_small_program(actions, tmp_path, H3, 'main.py', lambda: False)
    actions.brain.client.request.assert_not_called()


def test_disagreement_writes_nothing(tmp_path):
    actions = Mock()
    wrong = 'print(1)\n'
    actions.brain.client.request, _ = model(wrong, REFERENCE, wrong, REFERENCE)
    with pytest.raises(ValueError, match='could not be confirmed'):
        run_small_program(actions, tmp_path, H3, 'main.py', lambda: False)
    actions.execute.assert_not_called()
    assert not (tmp_path / 'main.py').exists()
