"""Adapters: how each neuron actually runs, by calling Jarvis's existing modules (wrapped, never rebuilt).

``adapter(neuron, inputs, env) -> {output port: value}``. Tool neurons go through ``ToolRegistry.execute``, which
keeps its own schema, scope and approval checks. Model work goes through the existing worker client
(``brain.client.request``). Brain-native neurons are small, deterministic and tested here.

Tool output is data, never instructions: it is passed to the model only as quoted context.
"""
from __future__ import annotations

import ast
import difflib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Callable, Dict, List, Optional

from .dispatcher import Env, NotStarted

APP = Path(__file__).resolve().parents[2]
WORK = APP / '.jarvis-runtime' / 'brain' / 'work'
MAX_FILE = 200_000
URL = re.compile(r'https?://[^\s"\'<>)\]]+')
WORD = re.compile(r"[A-Za-z][A-Za-z'-]{4,}")
Adapter = Callable[[Any, Dict[str, Any], Env], Dict[str, Any]]


# Tools -----------------------------------------------------------------------------------------------------
TOOL_ARGS: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    'discovery_call': lambda i: {'value':str(i['command']), 'content':json.dumps(i['parameters'],allow_nan=False) if 'parameters' in i else ''},
    'web_search': lambda i: {'value': str(i['query'])},
    'google_search': lambda i: {'value': str(i['query'])},
    'scrape_web': lambda i: {'value': str(i.get('url') or _first_url(i.get('results')))},
    'web_open': lambda i: {'value': str(i.get('url') or _first_url(i.get('results')))},
    'read_file': lambda i: {'value': Path(str(i['path'])).name, 'folder': str(Path(str(i['path'])).parent)},
    'list_files': lambda i: {'value': str(i['folder'])},
    'app_open': lambda i: {'value': str(i['app'])},
    'create_file': lambda i: {'value': str(i['name']), 'folder': str(i['folder']), 'content': str(i['text'])},
}
# Tools whose output port is known from their inputs once the tool reports success.
TOOL_OUTPUTS: Dict[str, Callable[[Dict[str, Any], str], Dict[str, Any]]] = {
    'create_file': lambda i, evidence: {'path': str(Path(str(i['folder'])) / str(i['name']))},
}


def _first_url(results: Any) -> str:
    found = URL.findall(results if isinstance(results, str) else json.dumps(results, default=str))
    if not found:
        raise NotStarted('the search returned no link to read')
    return str(found[0]).rstrip('.,;')


def tool_adapter(neuron: Any, inputs: Dict[str, Any], env: Env) -> Dict[str, Any]:
    if neuron.tool not in TOOL_ARGS:
        raise NotStarted(f'{neuron.tool} has no argument mapping yet')
    if env.actions is None:
        raise NotStarted('no Jarvis actions object to run tools with')
    from ..tools import ToolRegistry
    step = {'action': neuron.tool, **TOOL_ARGS[neuron.tool](inputs)}
    result = ToolRegistry(env.actions).execute(step, env.cancelled)
    text = str(getattr(result, 'evidence', result))
    if neuron.tool in TOOL_OUTPUTS:
        return TOOL_OUTPUTS[neuron.tool](inputs, text)
    return {neuron.outputs[0].name: text}


# Research slice --------------------------------------------------------------------------------------------
PREFER = re.compile(r'wikipedia\.org|\.gov\b|\.edu\b|docs\.|developer\.|readthedocs|python\.org|mozilla\.org', re.I)
AVOID = re.compile(r'duckduckgo\.com|google\.com/search|bing\.com|/ads?/|doubleclick|youtube\.com', re.I)


def pick_source(neuron: Any, inputs: Dict[str, Any], env: Env) -> Dict[str, Any]:
    text = inputs['results'] if isinstance(inputs['results'], str) else json.dumps(inputs['results'], default=str)
    links = [u.rstrip('.,;') for u in URL.findall(text) if not AVOID.search(u)]
    if not links:
        raise NotStarted('the search returned no usable link')
    preferred = [u for u in links if PREFER.search(u)]
    return {'url': (preferred or links)[0]}


def _model(env: Env) -> Optional[Callable[..., Any]]:
    client = getattr(getattr(env.actions, 'brain', None), 'client', None)
    return getattr(client, 'request', None)


def _relevant(page: str, query: str, limit: int = 12000) -> str:
    words = {w.lower() for w in WORD.findall(query)}
    sentences = re.split(r'(?<=[.!?])\s+', ' '.join(page.split()))
    scored = sorted(range(len(sentences)), key=lambda i: -sum(w in sentences[i].lower() for w in words))
    keep = sorted(scored[:60])
    return ' '.join(sentences[i] for i in keep)[:limit]


def analyse(neuron: Any, inputs: Dict[str, Any], env: Env) -> Dict[str, Any]:
    query, page = str(inputs['query']), str(inputs['page'])
    if not page.strip():
        raise NotStarted('the page was empty')
    context = _relevant(page, query)
    request = _model(env)
    if request is None:  # No model: an extractive answer (the most relevant sentences, verbatim).
        return {'report': ' '.join(re.split(r'(?<=[.!?])\s+', context)[:4])[:1500]}
    reply = request('tool_text', env.cancelled, tool='think', context=context,
                    goal=f'Answer this from the quoted page text only, in at most five sentences: {query}. '
                         'Copy numbers exactly as the page states them. If the page does not answer it, say so.')
    text = str(reply.get('text', '') if isinstance(reply, dict) else reply).strip()
    return {'report': text[:3000]}


def report_grounded(neuron: Any, inputs: Dict[str, Any], env: Env) -> Dict[str, Any]:
    from ..fast_routes import grounded
    report, page = str(inputs['report']), str(inputs['page'])
    problems: List[str] = []
    if len(report.split()) < 3:
        problems.append('the report is empty')
    if not grounded(report, page):
        problems.append('a number in the report does not appear in the source')
    words = [w.lower() for w in WORD.findall(report)]
    flat = page.lower()
    found = sum(w in flat for w in words)
    share = found / max(1, len(words))
    if words and share < 0.6:
        problems.append(f'only {share:.0%} of the report\'s words appear in the source')
    if re.search(r"\b(?:does not|doesn't|did not) (?:say|answer|mention)\b", report, re.I):
        problems.append('the source does not answer the question')
    return {'verdict': {'passed': not problems, 'problems': problems,
                        'evidence': [f'{found}/{len(words)} report words found in the source', 'numbers grounded'
                                     if 'number' not in ' '.join(problems) else 'numbers not grounded']}}


def report(neuron: Any, inputs: Dict[str, Any], env: Env) -> Dict[str, Any]:
    verdict = inputs['verdict'] or {}
    text = str(inputs['report']).strip()
    if verdict.get('passed'):
        return {'answer': f'{text}\n\n(Checked: {"; ".join(map(str, verdict.get("evidence", [])[:2]))}.)'}
    return {'answer': f'{text}\n\n(Not verified: {"; ".join(map(str, verdict.get("problems", [])[:2]))}.)'}


# Code slice ------------------------------------------------------------------------------------------------
def allowed_roots(config: Any) -> List[Path]:
    from ..control.settings import load
    return [Path(r).resolve() for r in load(config=config if isinstance(config, dict) else None).allowed_roots]


def inside(path: Path, roots: List[Path]) -> bool:
    path = path.resolve()
    return any(path == root or root in path.parents for root in roots)


def _read_folder(folder: Path) -> Dict[str, str]:
    files, total = {}, 0
    for path in sorted(folder.glob('*.py')):
        text = path.read_text(encoding='utf-8', errors='replace')
        total += len(text)
        if total > MAX_FILE:
            raise NotStarted('the folder holds more Python than one small fix should read')
        files[path.name] = text
    return files


def inspect(neuron: Any, inputs: Dict[str, Any], env: Env) -> Dict[str, Any]:
    folder = Path(str(inputs['folder']))
    if not inside(folder, allowed_roots(env.config)) or not folder.is_dir():
        raise NotStarted(f'{folder} is not a folder inside the approved roots')
    files = _read_folder(folder)
    tests = sorted(n for n in files if n.startswith('test_') or n.endswith('_test.py'))
    if not files:
        raise NotStarted('no Python files in the folder')
    return {'repo': {'folder': str(folder), 'files': files, 'tests': tests}}


def safe_patch(code: str, siblings: List[str]) -> bool:
    """small_program's safety rules, plus imports of the folder's own modules."""
    from ..small_program import SAFE_MODULES, UNSAFE_NAMES
    local = {Path(n).stem for n in siblings}
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(a.name.split('.')[0] not in SAFE_MODULES | local for a in node.names):
            return False
        if isinstance(node, ast.ImportFrom) and (node.level or (node.module or '').split('.')[0] not in
                                                 SAFE_MODULES | local):
            return False
        if isinstance(node, ast.Name) and node.id in UNSAFE_NAMES:
            return False
        if isinstance(node, ast.Attribute) and node.attr.startswith('__'):
            return False
    return True


def patch(neuron: Any, inputs: Dict[str, Any], env: Env) -> Dict[str, Any]:
    repo, goal, verdict = inputs['repo'], str(inputs['goal']), inputs.get('verdict') or {}
    request = _model(env)
    if request is None:
        raise NotStarted('no local model to write the fix')
    from ..small_program import source
    tests = '\n\n'.join(f'# {n}\n{repo["files"][n]}' for n in repo['tests'])
    changes: Dict[str, str] = {}
    for name in [n for n in repo['files'] if n not in repo['tests']][:3]:
        if env.cancelled():
            raise NotStarted('cancelled')
        hint = ('\nThe previous fix failed: ' + '; '.join(map(str, verdict.get('problems', [])[:3]))) if verdict else ''
        reply = request('tool_text', env.cancelled, tool='improve_code',
                        context=f'# {name}\n{repo["files"][name]}\n\n{tests}',
                        goal=f'{goal}\nReturn the complete corrected {name} only. The tests are correct and must '
                             f'not change; fix {name} so they pass. Keep every function name.{hint}')
        new = source(reply)
        if new.strip() and new.strip() != repo['files'][name].strip():
            changes[name] = new
    if not changes:
        raise NotStarted('the model proposed no change')
    return {'patch': changes}


def _scratch(repo: Dict[str, Any], changes: Dict[str, str]) -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix='fix-', dir=WORK))
    for name, text in {**repo['files'], **changes}.items():
        (folder / name).write_text(text, encoding='utf-8')
    return folder


def test(neuron: Any, inputs: Dict[str, Any], env: Env) -> Dict[str, Any]:
    repo, changes = inputs['repo'], inputs.get('patch') or {}
    if not changes:  # The final check reads the real folder again, independently of what the fix step said.
        repo = {**repo, 'files': _read_folder(Path(repo['folder']))}
    if any(name in repo['tests'] for name in changes):
        return {'report': {'returncode': 1, 'ran': 0, 'output': 'the patch edits a test file'}}
    unsafe = [n for n, text in changes.items() if not safe_patch(text, list(repo['files']))]
    if unsafe:
        return {'report': {'returncode': 1, 'ran': 0, 'output': f'unsafe code refused in {unsafe}'}}
    folder = _scratch(repo, changes)
    try:
        done = subprocess.run([sys.executable, '-I', '-m', 'unittest', 'discover', '-s', '.', '-t', '.', '-p', 'test*.py'],
                              cwd=folder, capture_output=True, text=True, timeout=60,
                              env={k: v for k, v in os.environ.items() if not re.search(
                                  r'TOKEN|SECRET|PASSWORD|API_?KEY|ACCESS_KEY', k, re.I)})
        ran = re.search(r'Ran (\d+) tests?', done.stderr)
        return {'report': {'returncode': done.returncode, 'ran': int(ran.group(1)) if ran else 0,
                           'output': done.stderr[-1500:], 'patched': sorted(changes)}}
    except subprocess.TimeoutExpired:
        return {'report': {'returncode': 1, 'ran': 0, 'output': 'the tests took longer than 60 s'}}
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def tests_pass(neuron: Any, inputs: Dict[str, Any], env: Env) -> Dict[str, Any]:
    result = inputs['report']
    problems = []
    if result.get('ran', 0) < 1:
        problems.append('no test ran: ' + str(result.get('output', ''))[-200:])
    elif result.get('returncode') != 0:
        problems.append('tests failed: ' + str(result.get('output', ''))[-300:])
    return {'verdict': {'passed': not problems, 'problems': problems,
                        'evidence': [f'{result.get("ran", 0)} tests ran, exit code {result.get("returncode")}']}}


def apply(neuron: Any, inputs: Dict[str, Any], env: Env) -> Dict[str, Any]:
    repo, changes, verdict = inputs['repo'], inputs['patch'], inputs['verdict'] or {}
    if not verdict.get('passed'):
        raise NotStarted('the fix did not pass its tests; nothing was written')
    folder = Path(repo['folder'])
    if not inside(folder, allowed_roots(env.config)):
        raise NotStarted('the folder is outside the approved roots')
    backups = {}
    for name, text in changes.items():
        target = folder / name
        if name in repo['tests'] or not target.is_file() or target.parent.resolve() != folder.resolve():
            raise NotStarted(f'{name} is not an existing source file of the folder')
        backups[name] = target.read_text(encoding='utf-8')
    for name, text in changes.items():  # Atomic per file: a reader never sees half a file.
        tmp = folder / f'.{name}.jarvis-tmp'
        tmp.write_text(text, encoding='utf-8')
        os.replace(tmp, folder / name)
    env.notes.setdefault('rollback', {}).update({str(folder / n): t for n, t in backups.items()})
    return {'repo': {**repo, 'files': {**repo['files'], **changes}}}


def summarise(neuron: Any, inputs: Dict[str, Any], env: Env) -> Dict[str, Any]:
    changes = inputs['patch']
    lines = [f'I fixed {", ".join(sorted(changes))}; the tests pass on a scratch copy and again in the folder.']
    return {'report': '\n'.join(lines)}


def diff(before: str, after: str, name: str) -> str:
    return ''.join(list(difflib.unified_diff(before.splitlines(True), after.splitlines(True), name, name))[:40])


# Sealed verifiers (jarvis/learning/verifiers): loaded through their tamper check, never re-implemented here.
def text_file_saved(neuron: Any, inputs: Dict[str, Any], env: Env) -> Dict[str, Any]:
    from ..learning.verifiers import load
    expected = inputs.get('expected')
    lines = [line for line in str(expected).splitlines() if line.strip()] if expected is not None else None
    verdict = load('text_file_saved').check(path=str(inputs['path']), started_after=env.notes.get('started'),
                                            lines=lines)
    return {'verdict': {'passed': bool(verdict.passed), 'problems': list(verdict.problems),
                        'evidence': [json.dumps(verdict.evidence, default=str)[:300]]}}


# Desktop workflows (2026-11-03) ---------------------------------------------------------------------------------
NAME_OK = re.compile(r'^[\w.() -]{1,120}$')


def _approved_path(env: Env, folder: str, name: str) -> Path:
    base = Path(folder)
    if not NAME_OK.match(name) or name in ('.', '..'):
        raise NotStarted(f'{name!r} is not a plain file or folder name')
    target = (base / name).resolve()
    if not inside(target, allowed_roots(env.config)) or target.parent != base.resolve():
        raise NotStarted(f'{target} is outside the approved folder')
    return target


def notepad_save(neuron: Any, inputs: Dict[str, Any], env: Env) -> Dict[str, Any]:
    """Notepad through ControlService (agent-desktop when that backend is on): new tab, type, File > Save as."""
    target = _approved_path(env, str(inputs['folder']), str(inputs['name']))
    if target.exists():
        raise NotStarted(f'{target.name} already exists; Jarvis does not overwrite without asking')
    control = getattr(env.actions, 'control', None)
    if control is None:
        raise NotStarted('no Jarvis control service')
    service = control()
    opened = json.loads(service.app_open('notepad', '', env.cancelled).splitlines()[0])
    if not opened.get('ok'):
        raise NotStarted(f'Notepad did not open: {opened.get("result")}')
    typed = json.loads(service.app_act('type', {'text': str(inputs['text'])}, env.cancelled).splitlines()[0])
    if not typed.get('ok'):
        raise RuntimeError(f'typing failed: {typed.get("result")}')  # may have acted: reported, never repeated
    saved = json.loads(service.app_act('save_as', {'text': str(target)}, env.cancelled).splitlines()[0])
    if not saved.get('ok'):
        raise RuntimeError(f'saving failed: {saved.get("result")}')
    return {'path': str(target)}


def rename(neuron: Any, inputs: Dict[str, Any], env: Env) -> Dict[str, Any]:
    source = _approved_path(env, str(inputs['folder']), str(inputs['name']))
    target = _approved_path(env, str(inputs['folder']), str(inputs['new']))
    if not source.is_file():
        raise NotStarted(f'{source.name} does not exist')
    if target.exists():
        raise NotStarted(f'{target.name} already exists; nothing was renamed')
    env.notes['renamed_text'] = source.read_text(encoding='utf-8', errors='replace')
    os.rename(source, target)
    env.notes['renamed_from'] = str(source)
    return {'path': str(target)}


def mkdir(neuron: Any, inputs: Dict[str, Any], env: Env) -> Dict[str, Any]:
    target = _approved_path(env, str(inputs['folder']), str(inputs['name']))
    if target.exists():
        raise NotStarted(f'{target.name} already exists')
    target.mkdir()
    return {'path': str(target)}


def file_renamed(neuron: Any, inputs: Dict[str, Any], env: Env) -> Dict[str, Any]:
    target = Path(str(inputs['path']))
    problems = []
    if not target.is_file():
        problems.append(f'{target.name} does not exist')
    elif env.notes.get('renamed_text') is not None and \
            target.read_text(encoding='utf-8', errors='replace') != env.notes['renamed_text']:
        problems.append(f'{target.name} does not hold the original text')
    if env.notes.get('renamed_from') and Path(env.notes['renamed_from']).exists():
        problems.append('the old name still exists')
    return {'verdict': {'passed': not problems, 'problems': problems, 'evidence': [f'{target.name} on disk']}}


def folder_exists(neuron: Any, inputs: Dict[str, Any], env: Env) -> Dict[str, Any]:
    target = Path(str(inputs['path']))
    ok = target.is_dir()
    return {'verdict': {'passed': ok, 'problems': [] if ok else [f'{target} is not a folder'],
                        'evidence': [f'{target.name} is a folder on disk'] if ok else []}}


def open_arrange(neuron: Any, inputs: Dict[str, Any], env: Env) -> Dict[str, Any]:
    """Open the file in the app through ControlService, then run each window step (resize/minimize/restore/...)."""
    path = Path(str(inputs['path']))
    if not inside(path, allowed_roots(env.config)) or not path.is_file():
        raise NotStarted(f'{path} is not a file inside the approved folder')
    control = getattr(env.actions, 'control', None)
    if control is None:
        raise NotStarted('no Jarvis control service')
    service = control()
    opened = json.loads(service.app_open(str(inputs['app']), str(path), env.cancelled).splitlines()[0])
    if not opened.get('ok'):
        raise NotStarted(f'{path.name} did not open: {opened.get("result")}')
    handle = int(opened.get('window') or 0)
    for step in inputs['plan']:
        args = {'window': str(handle), **({'width': step[1], 'height': step[2]} if step[0] == 'resize' else {})}
        done = json.loads(service.app_act(step[0], args, env.cancelled).splitlines()[0])
        if not done.get('ok'):
            raise RuntimeError(f'{step[0]} failed: {done.get("result")}')
    return {'window': {'handle': handle, 'title': path.name}}


def window_state(neuron: Any, inputs: Dict[str, Any], env: Env) -> Dict[str, Any]:
    """Independent read of the window list: the file's window exists and ends in the requested state."""
    from ..control.pc.runner import Runner
    handle = int((inputs['window'] or {}).get('handle') or 0)
    reply = Runner()(['list-windows'], timeout_s=15)
    rows = [w for w in (reply.data or []) if isinstance(w, dict)] if reply.ok else []
    row = next((w for w in rows if str(w.get('id')) == f'w-{handle}'), None)
    problems = []
    if row is None:
        problems.append('the window is not open')
    else:
        last = [s for s in inputs['plan'] if s[0] in ('minimize', 'restore', 'maximize')][-1:]
        if last and last[0][0] == 'minimize' and not row.get('minimized'):
            problems.append('the window is not minimized')
        if last and last[0][0] in ('restore', 'maximize') and row.get('minimized'):
            problems.append('the window is still minimized')
        sizes = [s for s in inputs['plan'] if s[0] == 'resize'][-1:]
        bounds = row.get('bounds') or {}
        if sizes and (abs(float(bounds.get('width', 0)) - sizes[0][1]) > 24 or
                      abs(float(bounds.get('height', 0)) - sizes[0][2]) > 24):
            problems.append(f'the window is {bounds.get("width")}x{bounds.get("height")}')
    return {'verdict': {'passed': not problems, 'problems': problems, 'evidence': ['window list read back']}}


ADAPTERS: Dict[str, Adapter] = {
    'skill.pc.open_arrange@v1': open_arrange,
    'verifier.window_state@v1': window_state,
    'skill.pc.notepad_save@v1': notepad_save,
    'skill.file.rename@v1': rename,
    'skill.file.mkdir@v1': mkdir,
    'verifier.file_renamed@v1': file_renamed,
    'verifier.folder_exists@v1': folder_exists,
    'verifier.text_file_saved@v1': text_file_saved,
    'skill.research.pick_source@v1': pick_source,
    'skill.research.analyse@v1': analyse,
    'verifier.report_grounded@v1': report_grounded,
    'motor.report@v1': report,
    'skill.code.inspect@v1': inspect,
    'skill.code.patch@v1': patch,
    'skill.code.test@v1': test,
    'verifier.tests_pass@v1': tests_pass,
    'skill.code.apply@v1': apply,
    'skill.code.summarise@v1': summarise,
}


def adapters_for(graph: Any) -> Dict[str, Adapter]:
    found = dict(ADAPTERS)
    for node_id, neuron in graph.neurons.items():
        if neuron.kind == 'tool' and neuron.tool in TOOL_ARGS and node_id.startswith('tool.'):
            found.setdefault(node_id, tool_adapter)
    return found
