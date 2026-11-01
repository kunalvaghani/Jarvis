"""Small single-file programs (flag control.api_routes, default off).

"Create a project folder fizzbuzz-app ... add main.py that prints FizzBuzz for 1 to 30" does not need the
multi-file coder. That coder also asks the model to type the expected output into a frozen test by hand, and a
wrong hand-typed list made live H3 fail every run: no correct program can pass a wrong test (2026-10-31).

This route asks the coding model twice, independently: once for the file, once for a separate reference program
that prints what the request expects. Both run isolated (`python -I`, a fresh temporary folder, a time limit).
The file is kept only when both run cleanly and print exactly the same non-empty output: two independent programs
agreeing is the check, and neither judges itself. One retry; otherwise nothing is written and the reason is
reported. The file is then created through the normal create command (same approval and folder checks).
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any, Callable, List, Optional, Tuple

PY_FILE = re.compile(r'\b([A-Za-z_][\w-]{0,60}\.py)\b')
OTHER_FILE = re.compile(r'\b[\w-]+\.(?:js|ts|tsx|jsx|html|css|json|java|cs|cpp|c|go|rs|rb|php|kt|swift|toml|cfg|ini|md|txt)\b',
                        re.I)
PRINTS = re.compile(r'\b(?:prints?|outputs?|displays?|shows?)\b', re.I)
BIG = re.compile(r'\b(?:app with|website|web app|gui|window|server|api|database|(?:unit )?tests?\b(?! folder)|'
                 r'files\b|modules\b|classes\b)', re.I)
# A print-only program needs none of the rest; anything else is refused before it runs (live 2026-10-31: given the
# whole request, the model's "reference" ran shell commands to create folders and open VS Code).
SAFE_MODULES = frozenset({'math', 'itertools', 'functools', 'string', 'collections', 'statistics', 'fractions',
                          'decimal', 'random', 'datetime', 'calendar', 'textwrap', 'operator', 're', 'typing'})
UNSAFE_NAMES = frozenset({'open', 'exec', 'eval', 'compile', '__import__', 'input', 'breakpoint', 'globals', 'locals',
                          'vars', 'getattr', 'setattr', 'delattr', '__builtins__', 'memoryview'})
FENCE = re.compile(r'^```[\w+-]*\s*\n(.*?)\n```\s*$', re.S)
TIMEOUT = 20.0
Run = Callable[..., Any]


def matches(goal: str) -> Optional[str]:
    """The one Python file a print-only, single-file request names; None for anything bigger."""
    files = set(PY_FILE.findall(goal))
    if len(files) != 1 or OTHER_FILE.search(goal) or not PRINTS.search(goal) or BIG.search(goal):
        return None
    return str(files.pop())


def spec(goal: str, name: str) -> str:
    """Only what the program must do ("prints FizzBuzz for 1 to 30"), never the folder or app steps around it."""
    found = re.search(re.escape(name) + r'\s+(?:that|which|to)\s+(.+?)(?=,|;|\.(?:\s|$)|\s+and\s+(?:save|open|run|then)\b|$)',
                      goal, re.I)
    return found.group(1).strip() if found else goal


def safe(code: str) -> bool:
    """Print-only source: safe-module imports only, no file, eval or attribute-escape builtins, no dunder access."""
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(a.name.split('.')[0] not in SAFE_MODULES for a in node.names):
            return False
        if isinstance(node, ast.ImportFrom) and (node.level or (node.module or '').split('.')[0] not in SAFE_MODULES):
            return False
        if isinstance(node, ast.Name) and node.id in UNSAFE_NAMES:
            return False
        if isinstance(node, ast.Attribute) and node.attr.startswith('__'):
            return False
    return True


def source(reply: Any) -> str:
    text = str(reply.get('text', '') if isinstance(reply, dict) else reply).strip()
    fenced = FENCE.match(text)
    return (fenced.group(1) if fenced else text).strip() + '\n'


def output(code: str, run: Run = subprocess.run, python: str = sys.executable) -> Tuple[bool, str]:
    """(ran cleanly, stdout) for code run isolated in a fresh temporary folder."""
    if not safe(code):
        return False, ''
    with tempfile.TemporaryDirectory() as sandbox:
        path = Path(sandbox) / 'program.py'
        path.write_text(code, encoding='utf-8')
        try:
            done = run([python, '-I', str(path)], capture_output=True, text=True, timeout=TIMEOUT, cwd=sandbox)
        except subprocess.TimeoutExpired:
            return False, ''
    return getattr(done, 'returncode', 1) == 0, str(getattr(done, 'stdout', ''))


def rule(request: Callable[..., Any], task: str, cancelled: Callable[[], bool]) -> str:
    """The rule each printed line follows, stated in words once and given to both programs.

    Live 2026-10-31: asked for code directly, the 9B swapped Fizz and Buzz in about half its programs, and once in
    both programs at the same time, so they agreed on wrong output. Asked to state the rule first, it was right
    every time.
    """
    reply = request('tool_text', cancelled, tool='think', context='',
                    goal=f'A program {task}. State precisely, in at most two sentences, the rule that decides each '
                         'printed line, as the request means it. Nothing else.')
    return ' '.join(source(reply).split())[:400]


def agreed(request: Callable[..., Any], name: str, goal: str, cancelled: Callable[[], bool],
           run: Run = subprocess.run) -> Tuple[Optional[str], List[str]]:
    """(source of `name` whose output matches an independent reference, or None; problems seen)."""
    problems: List[str] = []
    task = spec(goal, name)
    stated = rule(request, task, cancelled)
    for attempt in range(2):
        if cancelled():
            raise ValueError('Cancelled before the program was written.')
        main = source(request('tool_text', cancelled, tool='write_code', context='',
                              goal=f'Write the complete Python file {name}: a program that {task}. Rule: {stated} Running '
                                   f'`python {name}` must print the output itself (call any function you define). '
                                   'Standard library only, no files. Return only the source; no tests, no explanation.'))
        reference = source(request('tool_text', cancelled, tool='write_code', context='',
                                   goal=f'Write a short standalone Python program that {task}. Rule: {stated} It must print exactly '
                                        'that output and nothing else when run. Standard library only, no files. '
                                        'Return only the source.'))
        ran, printed = output(main, run)
        ref_ran, expected = output(reference, run)
        if ran and ref_ran and printed.strip() and printed.strip() == expected.strip():
            return main, problems
        problems.append(f'attempt {attempt + 1}: ' + (
            f'{name} was refused or failed to run' if not ran else 'the reference failed to run' if not ref_ran else
            f'{name} printed nothing' if not printed.strip() else
            f'{name} and the independent reference printed different output'))
    return None, problems


def run_small_program(actions: Any, project: Path, goal: str, name: str, cancelled: Callable[[], bool],
                      run: Run = subprocess.run) -> str:
    target = project / name
    if target.exists():
        raise ValueError(f'{target} already exists; Jarvis does not overwrite it without asking. Nothing was written.')
    code, problems = agreed(actions.brain.client.request, name, goal, cancelled, run)
    if code is None:
        raise ValueError(f'{name} was not written: its output could not be confirmed against an independent '
                         'reference program (' + '; '.join(problems) + ').')
    from .commands import Command
    actions.execute(Command('create_in_folder', name, json.dumps({'folder': str(project), 'content': code})), cancelled)
    if not target.is_file():
        raise ValueError(f'{target} was not created.')
    _, printed = output(target.read_text(encoding='utf-8'), run)
    lines = printed.strip().splitlines()
    # The coding path opens the project in VS Code afterwards when the user named it.
    return (f'Created {target}. It runs and its output matches an independent reference program '
            f'({len(lines)} lines, first: {lines[0][:60] if lines else ""!r}).')


VSCODE = re.compile(r'\b(?:vs ?code|visual studio code)\b', re.I)


def route(actions: Any, project: Path, goal: str, cancelled: Callable[[], bool]) -> Optional[str]:
    """Coder.run's hook: the checked single-file result, or None so the multi-file coder runs unchanged."""
    from . import flags
    if not flags.enabled(getattr(actions, 'config', None), 'control', 'api_routes'):
        return None
    from .small_edit import matches_edit, run_small_edit
    from .web_app import matches as web_matches, run_web_app
    web = web_matches(goal)
    name = matches_edit(goal)
    if web is not None and not (project / 'index.html').exists():
        name = 'index.html'  # An animated web page, checked and repaired in a real browser.
        result = run_web_app(actions, project, goal, web[0], cancelled)
    elif name is not None and (project / name).is_file():
        result = run_small_edit(actions, project, goal, name, cancelled)  # One existing file: edit and check it.
    else:
        name = matches(goal)
        if name is None or (project / name).exists():
            return None  # Anything bigger, or an existing file the edit route does not cover: the coder.
        result = run_small_program(actions, project, goal, name, cancelled)
    if VSCODE.search(goal):
        # Requests that reach the coder through the planner have no later VS Code step. A new window, never
        # --reuse-window, which replaced the project the user had open; the code-task path then skips its own open.
        try:
            from .app_adapters import vscode
            vscode(['--new-window', str(project), str(project / name)], cancelled)
            result += '\nOpened ' + str(project / name) + ' in VS Code.'
        except Exception as exc:
            result += '\nVS Code did not open the project: ' + str(exc)[:160]
    return result
