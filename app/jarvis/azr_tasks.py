"""Absolute Zero-style synthetic reasoning tasks over a disposable computer state (Pillar D).

Adapted from the method of Absolute Zero (LeapLabTHU/Absolute-Zero-Reasoner, MIT; arXiv 2505.03335):
tasks come in three modes and every answer is judged by execution, never by a model:

* DEDUCTION  given an initial state and a tool-call sequence, predict the exact final state
             (trains state-transition prediction for ``cognition.predict``);
* ABDUCTION  given an initial and a desired state, produce a dependency-respecting tool-call DAG
             that reaches it (trains planning/tool selection for ``brain.py``); any DAG whose every
             valid execution order reaches the desired state is correct;
* INDUCTION  given visible input/output examples, write a Python function that also passes hidden
             cases (trains small capability generation for ``repo_abilities``).

The environment is a pure, in-memory simulation: no real file, window or clipboard is touched.
No AZR code is copied; the AZR executor is described upstream as research-only and is not used.
"""
import ast
import copy
import hashlib
import itertools
import json
import random
import re

ENV_VERSION = 1
ORACLE_VERSION = 1
MAX_CALLS = 12
TOOLS = {
    # name: (argument names, reads(args), writes(args))
    'create_file': (('path', 'content'), lambda a: [], lambda a: ['file:' + a['path']]),
    'append_file': (('path', 'text'), lambda a: ['file:' + a['path']], lambda a: ['file:' + a['path']]),
    'replace_text': (('path', 'old', 'new'), lambda a: ['file:' + a['path']], lambda a: ['file:' + a['path']]),
    'copy_file': (('src', 'dst'), lambda a: ['file:' + a['src']], lambda a: ['file:' + a['dst']]),
    'move_file': (('src', 'dst'), lambda a: ['file:' + a['src']], lambda a: ['file:' + a['src'], 'file:' + a['dst']]),
    'delete_file': (('path',), lambda a: ['file:' + a['path']], lambda a: ['file:' + a['path']]),
    'open_app': (('app',), lambda a: [], lambda a: ['app:' + a['app']]),
    'close_app': (('app',), lambda a: ['app:' + a['app']], lambda a: ['app:' + a['app']]),
    'copy_text': (('path',), lambda a: ['file:' + a['path']], lambda a: ['clipboard']),
    'paste_append': (('path',), lambda a: ['clipboard', 'file:' + a['path']], lambda a: ['file:' + a['path']]),
}
NAMES = ('notes', 'todo', 'report', 'draft', 'plan', 'log', 'ideas', 'budget', 'readme', 'summary')
FOLDERS = ('docs', 'work', 'home', 'archive', 'tmp')
WORDS = ('alpha', 'beta', 'gamma', 'delta', 'red', 'blue', 'green', 'one', 'two', 'three', 'done', 'open')
APPS = ('notepad', 'calculator', 'browser', 'editor', 'player')


class ExecutionError(Exception):
    def __init__(self, step, reason):
        super().__init__(f'{step}: {reason}')
        self.step, self.reason = step, reason


def canonical(state):
    return {'files': dict(sorted(state['files'].items())), 'apps': sorted(set(state['apps'])),
            'clipboard': state['clipboard']}


def apply(state, call):
    """Apply one call to a copy of the state; precondition failures raise ExecutionError."""
    tool, args, step = call['tool'], call['args'], call.get('id', '?')
    if tool not in TOOLS or set(args) != set(TOOLS[tool][0]) or not all(isinstance(v, str) for v in args.values()):
        raise ExecutionError(step, 'invalid_call')
    state = copy.deepcopy(state)
    files = state['files']
    def need(path):
        if path not in files:
            raise ExecutionError(step, 'missing:' + path)
    def free(path):
        if path in files:
            raise ExecutionError(step, 'exists:' + path)
    if tool == 'create_file':
        free(args['path'])
        files[args['path']] = args['content']
    elif tool == 'append_file':
        need(args['path'])
        files[args['path']] += args['text']
    elif tool == 'replace_text':
        need(args['path'])
        if args['old'] not in files[args['path']] or not args['old']:
            raise ExecutionError(step, 'text_not_found')
        files[args['path']] = files[args['path']].replace(args['old'], args['new'], 1)
    elif tool == 'copy_file':
        need(args['src'])
        free(args['dst'])
        files[args['dst']] = files[args['src']]
    elif tool == 'move_file':
        need(args['src'])
        free(args['dst'])
        files[args['dst']] = files.pop(args['src'])
    elif tool == 'delete_file':
        need(args['path'])
        del files[args['path']]
    elif tool == 'open_app':
        if args['app'] in state['apps']:
            raise ExecutionError(step, 'already_open:' + args['app'])
        state['apps'].append(args['app'])
    elif tool == 'close_app':
        if args['app'] not in state['apps']:
            raise ExecutionError(step, 'not_open:' + args['app'])
        state['apps'].remove(args['app'])
    elif tool == 'copy_text':
        need(args['path'])
        state['clipboard'] = files[args['path']]
    elif tool == 'paste_append':
        need(args['path'])
        files[args['path']] += state['clipboard']
    return state


def execute(state, calls):
    """Deduction semantics: run calls in order; on the first failure stop and report where."""
    current = canonical(state)
    for call in calls:
        try:
            current = canonical(apply(current, call))
        except ExecutionError as exc:
            return {**current, 'halted': {'step': exc.step, 'reason': exc.reason}}
    return {**current, 'halted': None}


# ---- generators (seeded; the environment computes every answer) --------------------------------------------------------
def random_state(rng):
    files = {}
    for _ in range(rng.randint(1, 4)):
        path = rng.choice(FOLDERS) + '/' + rng.choice(NAMES) + '.txt'
        files[path] = ' '.join(rng.sample(WORDS, rng.randint(1, 3)))
    return canonical({'files': files, 'apps': rng.sample(APPS, rng.randint(0, 2)), 'clipboard': ''})


def random_call(rng, state, index, allow_failure):
    files = sorted(state['files'])
    fresh = rng.choice(FOLDERS) + '/' + rng.choice(NAMES) + '.txt'
    options = ['create_file', 'open_app']
    if files:
        options += ['append_file', 'replace_text', 'copy_file', 'move_file', 'delete_file', 'copy_text', 'paste_append']
    if state['apps']:
        options.append('close_app')
    tool = rng.choice(options)
    path = rng.choice(files) if files and not (allow_failure and rng.random() < .15) else fresh
    if tool == 'create_file':
        args = {'path': fresh if fresh not in state['files'] or allow_failure else fresh + '.new',
                'content': rng.choice(WORDS)}
    elif tool == 'append_file':
        args = {'path': path, 'text': ' ' + rng.choice(WORDS)}
    elif tool == 'replace_text':
        content = state['files'].get(path, '')
        old = rng.choice(content.split()) if content.split() and rng.random() > .1 else rng.choice(WORDS)
        args = {'path': path, 'old': old, 'new': rng.choice(WORDS)}
    elif tool in {'copy_file', 'move_file'}:
        args = {'src': path, 'dst': fresh}
    elif tool in {'delete_file', 'copy_text', 'paste_append'}:
        args = {'path': path}
    elif tool == 'open_app':
        args = {'app': rng.choice(APPS)}
    else:
        args = {'app': rng.choice(state['apps'])}
    return {'id': f's{index}', 'tool': tool, 'args': args}


def deduction_task(seed, length=None):
    rng = random.Random(seed)
    state = random_state(rng)
    calls, current = [], state
    for index in range(length or rng.randint(2, 6)):
        call = random_call(rng, current, index + 1, allow_failure=True)
        calls.append(call)
        result = execute(current, [call])
        if result['halted']:
            break
        current = {k: result[k] for k in ('files', 'apps', 'clipboard')}
    return {'mode': 'deduction', 'seed': seed, 'initial': state, 'calls': calls,
            'answer': execute(state, calls)}  # oracle-computed, never model-written


def abduction_task(seed):
    """Desired state reached by a hidden valid plan; any other valid DAG reaching it is accepted."""
    rng = random.Random(seed)
    for _ in range(50):
        state = random_state(rng)
        calls, current = [], state
        for index in range(rng.randint(2, 5)):
            call = random_call(rng, current, index + 1, allow_failure=False)
            result = execute(current, [call])
            if result['halted']:
                continue
            call['id'] = f's{len(calls) + 1}'
            call['deps'] = []
            calls.append(call)
            current = {k: result[k] for k in ('files', 'apps', 'clipboard')}
        if calls and current != state:
            plan = with_dependencies(calls)
            return {'mode': 'abduction', 'seed': seed, 'initial': state, 'desired': canonical(current),
                    'reference_plan': plan}
    raise ValueError('Could not generate an abduction task for seed ' + str(seed))


def with_dependencies(calls):
    """Minimal dependency edges for a sequential plan: each call depends on the last earlier conflicting call."""
    plan = []
    for index, call in enumerate(calls):
        deps = []
        mine_r, mine_w = resources(call)
        for earlier in reversed(calls[:index]):
            theirs_r, theirs_w = resources(earlier)
            if (mine_w & (theirs_r | theirs_w)) or (mine_r & theirs_w):
                deps.append(earlier['id'])
        plan.append({**call, 'deps': sorted(set(deps))})
    return plan


def resources(call):
    _, reads, writes = TOOLS[call['tool']]
    return set(reads(call['args'])), set(writes(call['args']))


PROGRAMS = (
    # (family, description, source template, input generator name)
    ('reverse_words', 'reverse the order of words', "def f(x):\n    return ' '.join(reversed(x.split()))\n", 'text'),
    ('count_vowels', 'count vowels', "def f(x):\n    return sum(1 for c in x.lower() if c in 'aeiou')\n", 'text'),
    ('title_case', 'capitalize each word', "def f(x):\n    return ' '.join(w[:1].upper() + w[1:] for w in x.split())\n", 'text'),
    ('sum_even', 'sum of even numbers', "def f(x):\n    return sum(v for v in x if v % 2 == 0)\n", 'ints'),
    ('running_max', 'running maximum', "def f(x):\n    out, best = [], None\n    for v in x:\n        best = v if best is None or v > best else best\n        out.append(best)\n    return out\n", 'ints'),
    ('dedupe', 'remove duplicates keeping order', "def f(x):\n    seen, out = set(), []\n    for v in x:\n        if v not in seen:\n            seen.add(v)\n            out.append(v)\n    return out\n", 'ints'),
    ('pairwise_diff', 'differences of neighbours', "def f(x):\n    return [b - a for a, b in zip(x, x[1:])]\n", 'ints'),
    ('scale_k', 'multiply each by K', "def f(x):\n    return [v * {K} for v in x]\n", 'ints'),
    ('shift_k', 'add K to each', "def f(x):\n    return [v + {K} for v in x]\n", 'ints'),
    ('clip_k', 'clip values at K', "def f(x):\n    return [min(v, {K}) for v in x]\n", 'ints'),
    ('longest_word', 'longest word (first on ties)', "def f(x):\n    words = x.split()\n    return max(words, key=len) if words else ''\n", 'text'),
    ('initials', 'initials in upper case', "def f(x):\n    return ''.join(w[0].upper() for w in x.split())\n", 'text'),
    ('rotate_k', 'rotate list left by K', "def f(x):\n    k = {K} % len(x) if x else 0\n    return x[k:] + x[:k]\n", 'ints'),
    ('count_k', 'count values greater than K', "def f(x):\n    return sum(1 for v in x if v > {K})\n", 'ints'),
)


def program_input(kind, rng):
    if kind == 'text':
        return ' '.join(rng.choice(WORDS + NAMES) for _ in range(rng.randint(1, 5)))
    return [rng.randint(-9, 20) for _ in range(rng.randint(0, 7))]


def induction_task(seed, families=None):
    rng = random.Random(seed)
    family, description, template, kind = rng.choice([p for p in PROGRAMS if families is None or p[0] in families])
    k = rng.randint(2, 6)
    source = template.replace('{K}', str(k))
    namespace = {}
    exec(compile(source, 'oracle_program', 'exec'), namespace)  # Jarvis-authored template, not model output
    function = namespace['f']
    inputs, seen = [], set()
    while len(inputs) < 10:
        value = program_input(kind, rng)
        key = json.dumps(value)
        if key not in seen:
            seen.add(key)
            inputs.append(value)
    cases = [{'input': v, 'output': function(copy.deepcopy(v))} for v in inputs]
    if [function(copy.deepcopy(c['input'])) for c in cases] != [c['output'] for c in cases]:
        raise ValueError('Oracle program is nondeterministic')  # AZR determinism check (run twice)
    return {'mode': 'induction', 'seed': seed, 'family': family, 'k': k,
            'message': 'Write f(x) to ' + description + ('' if '{K}' not in template else ' (K is a constant to infer)') + '.',
            'visible': cases[:4], 'hidden': cases[4:], 'reference_source': source}


# ---- the independent oracle ----------------------------------------------------------------------------------------------
def parse_json_answer(text):
    """Extract one JSON object from model output; a format failure is distinguished from a wrong answer."""
    if isinstance(text, (dict, list)):
        return text
    text = str(text)
    decoder = json.JSONDecoder(strict=False)  # models often emit raw newlines inside strings
    for match in re.finditer(r'[\[{]', text):  # first decodable JSON value, ignoring prose or code around it
        try:
            value, _ = decoder.raw_decode(text, match.start())
        except ValueError:
            continue
        if isinstance(value, (dict, list)):
            return value
    raise ValueError('no JSON object')


def check_deduction(task, answer):
    try:
        value = parse_json_answer(answer)
    except ValueError:
        return {'format_ok': False, 'correct': False, 'reason': 'unparseable'}
    if not isinstance(value, dict) or not {'files', 'apps', 'clipboard', 'halted'} <= set(value):
        return {'format_ok': False, 'correct': False, 'reason': 'schema'}
    expected = task['answer']
    try:
        predicted = {**canonical(value), 'halted': value['halted']}
    except (TypeError, KeyError, AttributeError):
        return {'format_ok': False, 'correct': False, 'reason': 'schema'}
    return {'format_ok': True, 'correct': predicted == expected, 'reason': 'match' if predicted == expected else 'mismatch'}


def topological_orders(plan, limit=24):
    by_id = {c['id']: c for c in plan}
    deps = {c['id']: set(c['deps']) for c in plan}
    orders = []
    def walk(done, order):
        if len(orders) >= limit:
            return
        if len(order) == len(plan):
            orders.append(list(order))
            return
        for identifier in sorted(by_id):
            if identifier not in done and deps[identifier] <= done:
                walk(done | {identifier}, order + [by_id[identifier]])
    walk(set(), [])
    return orders


def check_abduction(task, answer):
    """Outcome-judged: valid schema and DAG, every pair of conflicting calls ordered, all orders reach the goal."""
    try:
        plan = parse_json_answer(answer)
    except ValueError:
        return {'format_ok': False, 'correct': False, 'reason': 'unparseable'}
    if isinstance(plan, dict):
        plan = plan.get('plan', plan.get('calls'))
    if not isinstance(plan, list) or not 1 <= len(plan) <= MAX_CALLS:
        return {'format_ok': False, 'correct': False, 'reason': 'schema'}
    ids = set()
    for call in plan:
        if (not isinstance(call, dict) or set(call) != {'id', 'tool', 'args', 'deps'} or not isinstance(call['id'], str)
                or call['id'] in ids or call['tool'] not in TOOLS or not isinstance(call['args'], dict)
                or set(call['args']) != set(TOOLS[call['tool']][0]) or not all(isinstance(v, str) for v in call['args'].values())
                or not isinstance(call['deps'], list) or not all(isinstance(d, str) for d in call['deps'])):
            return {'format_ok': False, 'correct': False, 'reason': 'schema'}
        ids.add(call['id'])
    if any(d not in ids or d == c['id'] for c in plan for d in c['deps']):
        return {'format_ok': True, 'correct': False, 'reason': 'unknown_dependency'}
    orders = topological_orders(plan)
    if not orders:
        return {'format_ok': True, 'correct': False, 'reason': 'cycle'}
    ancestors = {}
    def above(identifier):
        if identifier not in ancestors:
            ancestors[identifier] = set()
            for dep in next(c for c in plan if c['id'] == identifier)['deps']:
                ancestors[identifier] |= {dep} | above(dep)
        return ancestors[identifier]
    for first, second in itertools.combinations(plan, 2):
        r1, w1 = resources(first)
        r2, w2 = resources(second)
        if (w1 & (r2 | w2)) or (w2 & r1):
            if first['id'] not in above(second['id']) and second['id'] not in above(first['id']):
                return {'format_ok': True, 'correct': False, 'reason': 'missing_dependency:' + first['id'] + '/' + second['id']}
    for order in orders:
        result = execute(task['initial'], order)
        if result['halted'] or {k: result[k] for k in ('files', 'apps', 'clipboard')} != task['desired']:
            return {'format_ok': True, 'correct': False, 'reason': 'goal_not_reached' if not result['halted'] else 'halted'}
    return {'format_ok': True, 'correct': True, 'reason': 'goal_reached_in_all_orders', 'orders_checked': len(orders)}


SAFE_BUILTINS = {'len', 'range', 'sum', 'min', 'max', 'sorted', 'reversed', 'enumerate', 'zip', 'map', 'filter', 'abs',
                 'list', 'tuple', 'set', 'dict', 'str', 'int', 'float', 'bool', 'any', 'all', 'round', 'divmod'}
FORBIDDEN = {'eval', 'exec', 'compile', 'open', '__import__', 'globals', 'locals', 'vars', 'getattr', 'setattr', 'delattr',
             'input', 'breakpoint', 'help', 'memoryview', 'type', 'object', 'super', 'classmethod', 'staticmethod', 'property'}


def extract_code(text):
    match = re.search(r'```(?:python)?\s*\n(.*?)```', str(text), re.S)
    return (match.group(1) if match else str(text)).strip() + '\n'


def screen_program(source):
    """Static safety screen. Passing it is necessary, not sufficient: execution still happens only in the container."""
    if not 10 <= len(source) <= 3000:
        raise ValueError('program size')
    tree = ast.parse(source)
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef) or tree.body[0].name != 'f':
        raise ValueError('exactly one top-level function f is required')
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.ClassDef, ast.AsyncFunctionDef,
                             ast.Await, ast.With, ast.Try, ast.Raise, ast.Lambda, ast.Yield, ast.YieldFrom, ast.Delete)):
            raise ValueError('disallowed construct: ' + type(node).__name__)
        if isinstance(node, ast.Name) and (node.id in FORBIDDEN or node.id.startswith('__')):
            raise ValueError('forbidden name: ' + node.id)
        if isinstance(node, ast.Attribute) and node.attr.startswith('_'):
            raise ValueError('private attribute')
        if isinstance(node, ast.While):
            raise ValueError('while loops are not allowed (termination)')
    return hashlib.sha256(source.encode()).hexdigest()


def task_id(task):
    body = {k: task[k] for k in task if k not in {'answer', 'reference_plan', 'reference_source', 'hidden', 'seed'}}
    return task['mode'][:3] + '_' + hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:16]


def signature(task):
    """Near-duplicate signature: tool/structure skeleton without concrete strings."""
    if task['mode'] == 'deduction':
        return 'ded:' + '-'.join(c['tool'] for c in task['calls']) + ':' + str(len(task['initial']['files']))
    if task['mode'] == 'abduction':
        return 'abd:' + '-'.join(sorted(c['tool'] for c in task['reference_plan'])) + ':' + str(len(task['desired']['files']))
    return 'ind:' + task['family'] + ':' + str(task.get('k'))


# ---- prompts and verified targets ---------------------------------------------------------------------------------------
SYSTEM = ('You are Jarvis reasoning about a simulated computer. The state has files (path -> text), open apps and a '
          'clipboard. Tools: create_file(path, content) fails if the path exists; append_file(path, text); '
          'replace_text(path, old, new) replaces the first occurrence and fails if old is absent; copy_file(src, dst) and '
          'move_file(src, dst) fail if src is missing or dst exists; delete_file(path); open_app(app) fails if open; '
          'close_app(app) fails if not open; copy_text(path) copies file text to the clipboard; paste_append(path) appends '
          'the clipboard. Execution stops at the first failing call. Reply with JSON or code only.')


def render_prompt(task):
    if task['mode'] == 'deduction':
        return ('DEDUCTION. Initial state: ' + json.dumps(task['initial'], sort_keys=True) + '\nCalls in order: ' +
                json.dumps(task['calls']) + '\nReturn the final state as JSON with keys files, apps (sorted), clipboard '
                'and halted (null, or {"step": id, "reason": code} for the first failing call).')
    if task['mode'] == 'abduction':
        return ('ABDUCTION. Initial state: ' + json.dumps(task['initial'], sort_keys=True) + '\nDesired state: ' +
                json.dumps(task['desired'], sort_keys=True) + '\nReturn a JSON list of calls {"id", "tool", "args", "deps"} '
                'whose every dependency-respecting order reaches the desired state; calls touching the same file, app '
                'or clipboard must be ordered through deps.')
    return ('INDUCTION. ' + task['message'] + '\nExamples (input -> output): ' +
            json.dumps([[c['input'], c['output']] for c in task['visible']]) +
            '\nReturn only a Python function named f(x) without imports.')


def render_target(task):
    """Training target taken only from the oracle (environment result, verified plan, verified program)."""
    if task['mode'] == 'deduction':
        return json.dumps(task['answer'], sort_keys=True)
    if task['mode'] == 'abduction':
        return json.dumps([{k: c[k] for k in ('id', 'tool', 'args', 'deps')} for c in task['reference_plan']])
    return task['reference_source'].strip()
