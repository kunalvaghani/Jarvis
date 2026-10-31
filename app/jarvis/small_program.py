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
FENCE = re.compile(r'^```[\w+-]*\s*\n(.*?)\n```\s*$', re.S)
TIMEOUT = 20.0
Run = Callable[..., Any]


def matches(goal: str) -> Optional[str]:
    """The one Python file a print-only, single-file request names; None for anything bigger."""
    files = set(PY_FILE.findall(goal))
    if len(files) != 1 or OTHER_FILE.search(goal) or not PRINTS.search(goal) or BIG.search(goal):
        return None
    return str(files.pop())


def source(reply: Any) -> str:
    text = str(reply.get('text', '') if isinstance(reply, dict) else reply).strip()
    fenced = FENCE.match(text)
    return (fenced.group(1) if fenced else text).strip() + '\n'


def output(code: str, run: Run = subprocess.run, python: str = sys.executable) -> Tuple[bool, str]:
    """(ran cleanly, stdout) for code run isolated in a fresh temporary folder."""
    with tempfile.TemporaryDirectory() as sandbox:
        path = Path(sandbox) / 'program.py'
        path.write_text(code, encoding='utf-8')
        try:
            done = run([python, '-I', str(path)], capture_output=True, text=True, timeout=TIMEOUT, cwd=sandbox)
        except subprocess.TimeoutExpired:
            return False, ''
    return getattr(done, 'returncode', 1) == 0, str(getattr(done, 'stdout', ''))


def agreed(request: Callable[..., Any], name: str, goal: str, cancelled: Callable[[], bool],
           run: Run = subprocess.run) -> Tuple[Optional[str], List[str]]:
    """(source of `name` whose output matches an independent reference, or None; problems seen)."""
    problems: List[str] = []
    for attempt in range(2):
        if cancelled():
            raise ValueError('Cancelled before the program was written.')
        main = source(request('tool_text', cancelled, tool='write_code', context='',
                              goal=f'Write the complete Python file {name} for this request: {goal} '
                                   'Return only the source of that one file; no tests, no explanation.'))
        reference = source(request('tool_text', cancelled, tool='write_code', context='',
                                   goal='Write a short standalone Python program that prints exactly the output this '
                                        f'request expects, nothing else: {goal} Return only the source.'))
        ran, printed = output(main, run)
        ref_ran, expected = output(reference, run)
        if ran and ref_ran and printed.strip() and printed.strip() == expected.strip():
            return main, problems
        problems.append(f'attempt {attempt + 1}: ' + (
            f'{name} failed to run' if not ran else 'the reference failed to run' if not ref_ran else
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
