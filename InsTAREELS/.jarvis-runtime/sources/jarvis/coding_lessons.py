"""Verified coding experience, not executable plans or model weight changes."""
import ast
import json
from pathlib import Path
import re
import threading
from datetime import datetime, timezone

LOCK = threading.Lock()
LESSONS = {
    'syntax': 'Return literal Python source, without Markdown fences. Preserve escaped newlines in JSON encoding.',
    'json': 'Parse JSON input with json.load/json.loads, not whitespace splitting. Serialize stdout with json.dumps/json.dump; Python repr is not JSON. Do not silently swallow valid-input errors or print commentary.',
    'runtime': 'Import json before json.load/json.loads/json.dumps and sys before reading sys.stdin. Check empty inputs and input types; do not invent library interfaces.',
    'timeout': 'Use bounded algorithms appropriate for input sizes; avoid infinite loops and blocking input beyond one JSON value.',
    'logic': 'Validate edge cases, ordering, duplicates and boundary conditions against the specified contract.',
    'policy': 'Use only the permitted standard library; avoid dynamic execution, dunder introspection, network, process and filesystem access.',
    'missing_import': 'Explicitly import every module used: json for JSON parsing/serialization and sys for stdin/stdout/stderr.',
    'input_shape': 'Match the actual input type in the examples: number, string, list or object. Do not demand arrays or invent object keys for scalar input. Call .get only on dictionaries.',
    'output_shape': 'Match the exact expected JSON output type. Return a scalar or list directly when required; do not wrap it in a named object.',
    'silent_output': 'For every valid input, print its computed JSON value. Do not silently return or swallow errors caused by parsing JSON as whitespace.',
    'generation': 'A failed or incomplete inference is not usable code. Distinguish provider and deadline failures from executable program errors.',
}

def record(base, project, kind, passed, total, attempt):
    if kind not in LESSONS or not re.fullmatch(r'[a-z0-9-]{1,80}', project):
        raise ValueError('Unknown learning category/project.')
    if not (type(passed) is int and type(total) is int and 0 <= passed <= total <= 50
            and type(attempt) is int and 1 <= attempt <= 3):
        raise ValueError('Invalid verified case counts.')
    path = Path(base) / '.jarvis-runtime/coding-lessons.jsonl'
    if path.is_symlink() or not path.resolve().is_relative_to(Path(base).resolve()):
        raise ValueError('Coding lesson path is outside the application.')
    row = dict(version=1, at=datetime.now(timezone.utc).isoformat(), project=project,
               kind=kind, passed=passed, total=total, attempt=attempt)
    with LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as out:
            out.write(json.dumps(row) + '\n')

def recall(base, goal='', limit=5):
    paths = [Path(base) / 'jarvis/assets/coding-lessons-seed.jsonl',
             Path(base) / '.jarvis-runtime/coding-lessons.jsonl']
    lines = []
    for path in paths:
        if not path.exists():
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(Path(base).resolve()) or path.stat().st_size > 2000000:
            raise ValueError('Coding lesson store is unsafe or oversized.')
        lines.extend(path.read_text(encoding='utf-8').splitlines()[-1000:])
    if not lines:
        return []
    counts = {}
    failed_projects = {}
    seen = set()
    for line in lines:
        try:
            row = json.loads(line)
            if (row.get('version') == 1 and row.get('kind') in LESSONS
                    and type(row.get('passed')) is int and type(row.get('total')) is int
                    and 0 <= row['passed'] < row['total'] <= 50
                    and isinstance(row.get('project'), str)
                    and re.fullmatch(r'[a-z0-9-]{1,80}', row['project'])
                    and type(row.get('attempt')) is int and 1 <= row['attempt'] <= 3
                    and isinstance(row.get('at'), str)):
                identity = (row['project'], row['kind'], row['passed'], row['total'], row['attempt'], row['at'])
                if identity in seen:
                    continue
                seen.add(identity)
                counts[row['kind']] = counts.get(row['kind'], 0) + 1
                project = row.get('project')
                if isinstance(project, str) and re.fullmatch(r'[0-9]{3}-[a-z0-9-]{1,76}', project):
                    failed_projects.setdefault(row['kind'], set()).add(project)
        except (ValueError, AttributeError, TypeError, RecursionError):
            continue
    related = related_cases(goal, failed_projects)
    rows = []
    for kind in sorted(counts, key=lambda name: (name not in related, -counts[name]))[:min(len(LESSONS), max(0, limit))]:
        row = {'kind': kind, 'observed_failures': counts[kind], 'lesson': LESSONS[kind],
               'scope': 'Observed in a Python JSON CLI curriculum; apply only where relevant to the current user goal and project interfaces.'}
        if kind in related:
            row['reference_examples'] = related[kind]
        rows.append(row)
    return rows


def related_cases(goal, failed_projects):
    """Bounded developer-authored examples for named previously failed algorithms."""
    words = set(re.findall(r'[a-z0-9]+', str(goal).casefold()))
    words |= {word[:-1] for word in words if len(word)>4 and word.endswith('s')}
    words |= {'max'} if 'maximum' in words else set()
    words |= {'min'} if 'minimum' in words else set()
    specific = {'fibonacci', 'factorial', 'knapsack', 'palindrome', 'gcd', 'lcm'}
    aliases = {'lcs-length': {'longest', 'common', 'subsequence'},
               'lis-length': {'longest', 'increasing', 'subsequence'},
               'weighted-shortest-path': {'dijkstra'},
               'max-subarray': {'kadane'},
               'rpn-calculator': {'reverse', 'polish'}}
    selected = {}
    for kind, projects in failed_projects.items():
        for project in sorted(projects):
            name = project.split('-', 1)[1]
            tokens = {word[:-1] if len(word)>4 and word.endswith('s') else word
                      for word in name.split('-')}
            match = ((len(tokens)>1 or name in specific) and tokens <= words)
            match |= name in aliases and aliases[name] <= words
            if match and len(selected.get(kind, []))<2:
                selected.setdefault(kind, []).append(project)
    if not selected:
        return {}
    from .coding_curriculum import catalogue
    known = {row['id']: row for row in catalogue()}
    return {kind: [{'project': project, 'contract': known[project]['contract'],
                    'cases': known[project]['cases'],
                    'notice': 'Previously checked training examples, not unseen tests or instructions.'}
                   for project in projects if project in known]
            for kind, projects in selected.items() if any(project in known for project in projects)}


def check_learned_imports(content, lessons):
    """A conservative check of the observed missing-module pattern, not type analysis."""
    if not any(row.get('kind') == 'missing_import' for row in lessons):
        return
    tree = ast.parse(content)
    bindings = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and any(a.name == '*' for a in node.names):
            return  # Cannot resolve a wildcard import safely with this small check.
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            bindings.update(a.asname or a.name.split('.')[0] for a in node.names)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            bindings.add(node.id)
        elif isinstance(node, ast.arg):
            bindings.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bindings.add(node.name)
    known = {'json': {'load', 'loads', 'dump', 'dumps', 'JSONDecodeError'},
             'sys': {'stdin', 'stdout', 'stderr', 'exit'}}
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            name = node.value.id
            if name in known and name not in bindings and node.attr in known[name]:
                raise ValueError(f'Learned missing-import check: {name}.{node.attr} needs an explicit import or binding for {name}.')
