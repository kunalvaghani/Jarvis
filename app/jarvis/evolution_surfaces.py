"""Bounded mutation surfaces for controlled self-evolution (Pillar C).

A surface is one module-level dict literal of tunable numbers or strings in a named
Jarvis source file. A candidate may change only the values of that literal, within
declared bounds; every other byte of the module's syntax tree must stay identical.
That rule is checked on source text with ``ast`` and never by importing candidate code.

Security policy, the evaluator, approval authority, deployment controls, tests and
configuration are not surfaces and cannot be targeted (``PROTECTED``).
"""
import ast
import hashlib
import math
import re

# name -> file, symbol, domain, benchmark, per-key bounds (type, low, high) or (str, max_length)
SURFACES = {
    'dag_scheduling': {
        'file': 'jarvis/dag_execution.py', 'symbol': 'SCHEDULING', 'domain': 'dag_planning',
        'benchmark': 'dag_makespan', 'objective': 'min',
        'bounds': {'critical_path_weight': (float, 0.0, 10.0), 'read_only_bias': (float, -5.0, 5.0)}},
    'tool_ranking': {
        'file': 'jarvis/capabilities.py', 'symbol': 'RANKING', 'domain': 'skill_registry',
        'benchmark': 'tool_selection', 'objective': 'max',
        'bounds': {'route_boost': (float, 2.0, 16.0), 'route_step': (float, 0.0, 2.0), 'route_step_cap': (int, 1, 10),
                   'skill_tool_boost': (float, 0.0, 12.0), 'exact_name_bonus': (float, 5.0, 40.0),
                   'preferred_skill_bonus': (int, 0, 16), 'min_skill_overlap': (int, 1, 4)}},
    'lesson_retrieval': {
        'file': 'jarvis/reasoning_bank.py', 'symbol': 'RETRIEVAL', 'domain': 'memory',
        'benchmark': 'lesson_retrieval', 'objective': 'max',
        'bounds': {'fit': (float, 0.0, 1.0), 'mismatch': (float, 0.0, 1.0), 'confidence': (float, 0.0, 1.0),
                   'age_cap': (float, 0.0, 0.5), 'age_days': (float, 30.0, 3650.0), 'min_score': (float, 0.0, 0.6)}},
    'percept_salience': {
        'file': 'jarvis/cognition.py', 'symbol': 'SALIENCE', 'domain': 'voice_routing',
        'benchmark': 'salience_retention', 'objective': 'max',
        'bounds': {'decay_seconds': (float, 10.0, 900.0), 'vision': (float, 0.3, 0.95), 'sensor_cap': (float, 0.1, 0.9)}},
    'read_retry_backoff': {
        'file': 'jarvis/task_recovery.py', 'symbol': 'BACKOFF', 'domain': 'recovery',
        'benchmark': 'retry_recovery', 'objective': 'max',
        'bounds': {'base_seconds': (float, 0.01, 1.0), 'max_seconds': (float, 0.1, 5.0)}},
    'prompt_router': {
        'file': 'jarvis/prompt_router.py', 'symbol': 'ROUTER', 'domain': 'prompt_routing',
        'benchmark': 'prompt_routing', 'objective': 'max',
        'bounds': {'keyword_weight': (float, 0.1, 5.0), 'phrase_weight': (float, 0.1, 5.0),
                   'tool_name_weight': (float, 0.0, 5.0), 'min_score': (float, 0.0, 5.0)}},
    'prompt_slots': {
        'file': 'jarvis/prompt_router.py', 'symbol': 'SLOT_PROMPTS', 'domain': 'prompt_routing',
        'benchmark': 'prompt_slots', 'objective': 'max',
        'bounds': {slot: (str, 600) for slot in ('planning', 'coding', 'ui_automation', 'knowledge', 'tool_selection',
                                                  'error_recovery')}},
}

# Never surfaces: policy, evaluation, approval, deployment, tests and configuration.
PROTECTED = re.compile(r'(?:^|/)(?:tests/|config/|evolution_eval/|requirements/)|'
                       r'(?:secret|credential|permission|approval|security|auth|token|cloud_policy|cloud_architect|'
                       r'evolution_(?:promotion|lab|archive|surfaces)|autoresearch|self_evolution|tools\.py|toolkits|'
                       r'actions\.py|launcher|(?:^|/)recovery\.py|gpu_scheduler|deliberation)', re.I)
# Prompt text cannot carry instructions that widen authority.
UNSAFE_TEXT = re.compile(r'\b(?:ignore|override|bypass|disable|skip)\b.{0,40}\b(?:approval|permission|safety|security|'
                         r'polic(?:y|ies)|verification|rules?)\b|\bapprove\b.{0,20}\bautomatically\b|'
                         r'\b(?:api[_ -]?key|password|token|secret)\b', re.I | re.S)


class SurfaceViolation(ValueError):
    pass


def surface(name):
    if name not in SURFACES:
        raise SurfaceViolation('Unknown mutation surface: ' + str(name))
    spec = SURFACES[name]
    if PROTECTED.search(spec['file']):
        raise SurfaceViolation('Protected source cannot be a mutation surface.')
    return spec


def _assignment(tree, symbol):
    found = [node for node in tree.body if isinstance(node, ast.Assign) and len(node.targets) == 1
             and isinstance(node.targets[0], ast.Name) and node.targets[0].id == symbol]
    if len(found) != 1 or not isinstance(found[0].value, ast.Dict):
        raise SurfaceViolation('Surface symbol must be exactly one module-level dict literal: ' + symbol)
    return found[0]


def extract(source, name):
    """Return the literal values of a surface from source text (never imports it)."""
    spec = surface(name)
    node = _assignment(ast.parse(source), spec['symbol'])
    try:
        values = ast.literal_eval(node.value)
    except ValueError:
        raise SurfaceViolation('Surface values must be literals.') from None
    validate(name, values)
    return values


def validate(name, values):
    spec = surface(name)
    if not isinstance(values, dict) or set(values) != set(spec['bounds']):
        raise SurfaceViolation('Surface keys must match the declared bounds exactly.')
    for key, bound in spec['bounds'].items():
        value = values[key]
        if bound[0] is str:
            if not isinstance(value, str) or len(value) > bound[1] or not value.isascii() or UNSAFE_TEXT.search(value):
                raise SurfaceViolation('Unsafe or oversized prompt text for ' + key)
            continue
        kind, low, high = bound
        if kind is int and type(value) is not int or kind is float and type(value) not in (int, float):
            raise SurfaceViolation('Wrong value type for ' + key)
        if not math.isfinite(value) or not low <= value <= high:
            raise SurfaceViolation(f'{key}={value!r} is outside [{low}, {high}]')
    return values


def render(source, name, values):
    """Rewrite only the surface literal; the result must still pass ``verify_bounded``."""
    spec = surface(name)
    validate(name, values)
    node = _assignment(ast.parse(source), spec['symbol']).value
    lines = source.splitlines(keepends=True)
    # col offsets are UTF-8 byte offsets; surface lines are ASCII so character and byte offsets match.
    if not lines[node.lineno - 1].isascii() or not lines[node.end_lineno - 1].isascii():
        raise SurfaceViolation('Surface literal lines must be ASCII.')
    start = sum(len(line) for line in lines[:node.lineno - 1]) + node.col_offset
    end = sum(len(line) for line in lines[:node.end_lineno - 1]) + node.end_col_offset
    literal = '{' + ', '.join(f'{key!r}: {values[key]!r}' for key in spec['bounds']) + '}'
    changed = source[:start] + literal + source[end:]
    verify_bounded(source, changed, name)
    return changed


def _normalized(tree, symbol):
    node = _assignment(tree, symbol)
    node.value = ast.Dict(keys=[], values=[])
    return ast.dump(tree, include_attributes=False)


def verify_bounded(parent_source, child_source, name):
    """Accept a child only if its syntax tree equals the parent's apart from in-bound surface values."""
    spec = surface(name)
    try:
        parent, child = ast.parse(parent_source), ast.parse(child_source)
    except SyntaxError as exc:
        raise SurfaceViolation('Candidate does not parse: ' + str(exc.msg)) from None
    if _normalized(parent, spec['symbol']) != _normalized(child, spec['symbol']):
        raise SurfaceViolation('Candidate changes code outside the declared surface literal.')
    return extract(child_source, name)


def digest(values):
    return hashlib.sha256(repr(sorted(values.items())).encode('utf-8')).hexdigest()[:16]


def distance(name, first, second):
    """Normalized distance between two value sets (0 identical, 1 maximal) for diversity metrics."""
    spec = surface(name)
    parts = []
    for key, bound in spec['bounds'].items():
        a, b = first[key], second[key]
        if bound[0] is str:
            union = set(a.split()) | set(b.split())
            parts.append(len(set(a.split()) ^ set(b.split())) / len(union) if union else 0.)
        else:
            parts.append(abs(a - b) / ((bound[2] - bound[1]) or 1))
    return sum(parts) / len(parts)
