"""Python project works (e.g. a VS Code project): its entry file, copied to a fresh temporary folder, runs in
isolated mode (`python -I`) within a time limit and prints exactly the expected output; optional function
checks import the module there and compare return values."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .base import Verdict, Verifier, judged

Run = Callable[..., Any]
CALLS = r'''
import importlib, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I leaves the sandbox off sys.path.
module = importlib.import_module(sys.argv[1])
results = []
for expression in json.loads(sys.argv[2]):
    try:
        results.append(repr(eval(expression, {"module": module})))
    except Exception as error:
        results.append("error: " + type(error).__name__)
print("CALLS" + json.dumps(results))
'''


class PythonProject(Verifier):
    NAME = 'python_project'
    READS = frozenset({'file', 'process'})

    def check(self, *, folder: str | Path, entry: str = 'main.py', expected_stdout: Optional[str] = None,
              calls: Sequence[Tuple[str, str]] = (), timeout: float = 20, python: str = sys.executable,
              run: Run = subprocess.run, **_: Any) -> Verdict:
        """`calls` are (expression using `module`, expected repr) pairs, e.g. ("module.total([1, 2])", "3")."""
        source = Path(folder) / entry
        evidence: Dict[str, Any] = {'path': str(source)}
        if not source.is_file():
            return judged([f'{source} was not saved'], evidence)
        problems: List[str] = []
        with tempfile.TemporaryDirectory() as sandbox:
            copy = Path(sandbox) / source.name
            shutil.copy2(source, copy)
            if expected_stdout is not None:
                try:
                    out = run([python, '-I', str(copy)], capture_output=True, text=True, timeout=timeout, cwd=sandbox)
                except subprocess.TimeoutExpired:
                    return judged([f'{entry} did not finish within {timeout:g} s'], evidence)
                evidence['stdout'] = str(out.stdout)[:400]
                if str(out.stdout).strip() != expected_stdout.strip():
                    problems.append(f'output is not the expected text: {str(out.stdout)[:200]!r} {str(out.stderr)[-200:]!r}')
            if calls:
                helper = Path(sandbox) / '_jarvis_calls.py'
                helper.write_text(CALLS, encoding='utf-8')
                expressions = [expression for expression, _ in calls]
                try:
                    out = run([python, '-I', str(helper), copy.stem, json.dumps(expressions)], capture_output=True,
                              text=True, timeout=timeout, cwd=sandbox)
                except subprocess.TimeoutExpired:
                    return judged([f'function checks did not finish within {timeout:g} s'], evidence)
                line = next((l for l in str(out.stdout).splitlines() if l.startswith('CALLS')), '')
                try:
                    got = json.loads(line[5:]) if line else None
                except ValueError:
                    got = None
                if not isinstance(got, list) or len(got) != len(calls):
                    problems.append(f'the module could not be imported: {str(out.stderr)[-300:]!r}')
                else:
                    evidence['calls'] = got
                    problems += [f'{expression} returned {value}, expected {expected}'
                                 for (expression, expected), value in zip(calls, got) if value != expected]
        return judged(problems, evidence)


def check(**params: Any) -> Verdict:
    return PythonProject().check(**params)
