"""Edit one existing small Python file (flag control.api_routes, default off).

Varied live gate 2026-10-31: "edit main.py ... so it prints FizzBuzz for 1 to 50" and "add a function is_prime(n)
to main.py, keep the output" went to the multi-file coder, which added a test file and left main.py unchanged, or
had its plan rejected over a path format. A one-file change needs one file rewritten and checked.

The model rewrites the whole file for the requested change. The new file is kept only when:

- it passes the same safety check as a new small program (`small_program.safe`) and differs from the old file;
- an independently written reference program, given the same stated rule, prints exactly the same output;
- every one-argument function the request names (``is_prime(n)``) agrees with an independently written version
  of that function on the integers -5..60 (two independent implementations agreeing is the check).

One retry; otherwise nothing is written. The file is replaced through the normal modify command (atomic write).
Same limit as new programs: the reference comes from the same local model, so a mistake both share is possible.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any, Callable, Dict, List, Optional, Tuple

from .small_program import BIG, OTHER_FILE, PY_FILE, TIMEOUT, Run, output, safe, source

EDIT = re.compile(r'\b(?:edit|change|modify|update|add|fix|make|extend|adjust)\b', re.I)
FUNCTION = re.compile(r'\b(?:function|def)\s+([A-Za-z_]\w*)\s*\(\s*([A-Za-z_]\w*)\s*\)')
NOISE = (re.compile(r'^\s*open (?:vs ?code|visual studio code)\s*(?:,|and)\s*', re.I),
         re.compile(r'\s+in the [\w.-]+ folder in (?:my |the )?[\w -]+? folder\b', re.I),
         re.compile(r',?\s*and save it\.?\s*$', re.I))
INPUTS = list(range(-5, 61))
# "keep the FizzBuzz output exactly as it is": the current program's own output is the expected output.
KEEP = re.compile(r'\b(?:keep|leave|preserve)\b[^.]*\b(?:output|prints?|printing)\b[^.]*\b(?:same|as it is|'
                  r'unchanged|exactly)\b|\b(?:output|prints?)\b[^.]*\b(?:unchanged|stays? the same)\b', re.I)


def matches_edit(goal: str) -> Optional[str]:
    """The one Python file a small edit names; None for anything bigger."""
    files = set(PY_FILE.findall(goal))
    if len(files) != 1 or OTHER_FILE.search(goal) or not EDIT.search(goal) or BIG.search(goal):
        return None
    return str(files.pop())


def change_text(goal: str) -> str:
    """The change itself, without the app and folder steps around it."""
    text = goal
    for pattern in NOISE:
        text = pattern.sub(' ', text)
    return ' '.join(text.split())


HARNESS = '''import contextlib, io, json, sys
def load(path):
    space = {"__name__": "checked"}
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(open(path, encoding="utf-8").read(), path, "exec"), space)
    return space
a, b = load(sys.argv[1]), load(sys.argv[2])
name = sys.argv[3]
rows = []
for value in json.loads(sys.argv[4]):
    row = []
    for space in (a, b):
        try:
            row.append(repr(space[name](value)))
        except Exception as error:
            row.append("error " + type(error).__name__)
    rows.append(row)
print(json.dumps(rows))
'''


def same_function(new: str, reference: str, name: str, run: Run = subprocess.run,
                  python: str = sys.executable) -> Tuple[bool, str]:
    """(agree, why not): both sources define `name` and return the same value for every test input."""
    if not (safe(new) and safe(reference)):
        return False, 'a function source was refused by the safety check'
    with tempfile.TemporaryDirectory() as sandbox:
        folder = Path(sandbox)
        (folder / 'harness.py').write_text(HARNESS, encoding='utf-8')
        (folder / 'new.py').write_text(new, encoding='utf-8')
        (folder / 'reference.py').write_text(reference, encoding='utf-8')
        try:
            done = run([python, '-I', str(folder / 'harness.py'), str(folder / 'new.py'), str(folder / 'reference.py'),
                        name, json.dumps(INPUTS)], capture_output=True, text=True, timeout=TIMEOUT, cwd=sandbox)
        except subprocess.TimeoutExpired:
            return False, f'{name} did not finish in time'
    if getattr(done, 'returncode', 1) != 0:
        return False, f'{name} is missing or failed to load'
    rows = json.loads(str(done.stdout))
    for value, (mine, theirs) in zip(INPUTS, rows):
        if mine != theirs:
            return False, f'{name}({value}) gave {mine}, the independent version {theirs}'
    return True, ''


def edited(request: Callable[..., Any], name: str, current: str, goal: str, cancelled: Callable[[], bool],
           run: Run = subprocess.run) -> Tuple[Optional[str], List[str]]:
    """(new source of `name` that passed every check, or None; problems seen)."""
    change = change_text(goal)
    shown = f'The current {name}:\n```python\n{current}\n```\n'
    stated = ' '.join(source(request('tool_text', cancelled, tool='think', context='', goal=(
        shown + f'Requested change: {change}\nState precisely, in at most two sentences, the rule that decides each '
        'line the CHANGED program prints. Nothing else.'))).split())[:400]
    functions = FUNCTION.findall(goal)
    kept = output(current, run) if KEEP.search(change) else None  # Varied gate H3c: the reference never saw 1..30.
    problems: List[str] = []
    for attempt in range(2):
        if cancelled():
            raise ValueError(f'Cancelled before {name} was changed.')
        new = source(request('tool_text', cancelled, tool='write_code', context='', goal=(
            shown + f'Apply this change: {change}\nOutput rule after the change: {stated}\nKeep everything else as it '
            f'is. Running `python {name}` must still print its output. Standard library only, no files. Return only '
            'the complete new file; no tests, no explanation.')))
        reference = '' if kept is not None else source(request('tool_text', cancelled, tool='write_code', context='', goal=(
            f'Write a short standalone Python program that prints exactly what a program prints when it follows '
            f'this rule: {stated} (the request was: {change}). Print that output and nothing else. Standard '
            'library only, no files. Return only the source.')))
        why = ''
        if new.strip() == current.strip():
            why = f'{name} came back unchanged'
        else:
            ran, printed = output(new, run)
            ref_ran, expected = kept if kept is not None else output(reference, run)
            if not ran:
                why = f'the new {name} was refused or failed to run'
            elif not ref_ran:
                why = 'the reference failed to run'
            elif printed.strip() != expected.strip():
                why = f'the new {name} and the independent reference printed different output'
        for function, parameter in functions if not why else ():
            other = source(request('tool_text', cancelled, tool='write_code', context='', goal=(
                f'Write only the Python function {function}({parameter}) for this request: {change} Return only that '
                'function; standard library only, no prints, no other code.')))
            agree, why = same_function(new, other, function, run)
            if not agree:
                break
        if not why:
            return new, problems
        problems.append(f'attempt {attempt + 1}: {why}')
    return None, problems


def run_small_edit(actions: Any, project: Path, goal: str, name: str, cancelled: Callable[[], bool],
                   run: Run = subprocess.run) -> str:
    target = project / name
    if target.is_symlink() or not target.is_file() or target.stat().st_size > 200_000:
        raise ValueError(f'{target} is not a small regular file; Jarvis edits only that kind here.')
    current = target.read_text(encoding='utf-8')
    new, problems = edited(actions.brain.client.request, name, current, goal, cancelled, run)
    if new is None:
        raise ValueError(f'{name} was not changed: the edit could not be confirmed against independent checks ('
                         + '; '.join(problems) + ').')
    if target.read_text(encoding='utf-8') != current:
        raise ValueError(f'{target} changed while Jarvis was working; nothing was written.')
    from .commands import Command
    data: Dict[str, str] = {'folder': str(project), 'content': new, 'find': ''}
    actions.execute(Command('modify_in_folder', name, json.dumps(data)), cancelled)
    if target.read_text(encoding='utf-8') != new:
        raise ValueError(f'{target} does not contain the checked edit.')
    checked = [f for f, _ in FUNCTION.findall(goal)]
    return (f'Changed {target}. Its output matches an independent reference program'
            + (f', and {", ".join(checked)} agrees with an independent version on {len(INPUTS)} inputs' if checked else '')
            + '.')
