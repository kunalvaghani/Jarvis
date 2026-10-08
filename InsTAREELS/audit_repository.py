"""Inventory authored source and references without importing or deleting files.

Generated assets, private state, environments and upstream checkouts are retained
as groups. Import reachability is evidence, never proof that a file is unused.
"""
import argparse
import ast
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import unquote

BASE = Path(__file__).resolve().parent
PRUNED = {'.git', '__pycache__', 'node_modules', '.pytest_cache', '.next', 'dist', 'build'}
PRIVATE = {'.jarvis-runtime', 'models', 'JarvisFiles', 'custom-skills', '.firecrawl', 'secrets'}
CHECKOUTS = {'hermes-agent', 'execution-upstream', 'ultron-upstream', 'gods-eye-view-src'}
PRIVATE_FILES = {'file_catalog.json', 'file_catalog.sqlite3', 'installed_apps.scan.json',
                 'scan_report.json', 'task_state.json', 'ui_memory.json', 'config.before-pc-scan.json'}


def linked(path):
    return bool(getattr(path.lstat(), 'st_file_attributes', 0) & 1024) or path.is_symlink()


def authored_files(base):
    files, retained = [], []
    for directory, folders, names in os.walk(base, followlinks=False):
        folder = Path(directory)
        for name in list(folders):
            path = folder/name
            if (name in PRUNED or name.startswith('.venv') or linked(path)
                    or (folder == base and name in PRIVATE)
                    or (folder == base/'integrations' and name in CHECKOUTS)
                    or (folder == base and name == 'artifacts')):
                folders.remove(name)
                retained.append({'path': path.relative_to(base).as_posix(),
                                 'reason': 'generated/private/environment/upstream/reference group; retained'})
        for name in names:
            path = folder/name
            if linked(path) or name.startswith('.env') or name in PRIVATE_FILES or name.endswith(('.log', '.pyc', '.sqlite3')):
                continue
            files.append(path)
    return sorted(files), retained


def module_name(relative):
    parts = list(relative.with_suffix('').parts)
    if parts[-1] == '__init__':
        parts.pop()
    return '.'.join(parts)


def imports(tree, module, package=False):
    output = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            output.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = module.split('.') if package else module.split('.')[:-1]
                parts = parts[:len(parts)-node.level+1]
                target = '.'.join([*parts, *([node.module] if node.module else [])])
            else:
                target = node.module or ''
            if target:
                output.add(target)
                output.update(target+'.'+alias.name for alias in node.names if alias.name != '*')
    return output


def documentation_links(base):
    broken, count = [], 0
    # Historical/upstream READMEs remain owned by their authors; validate our
    # root overview, application README and authored guides.
    paths = [base.parent/'README.md', base/'README.md', *sorted((base/'docs').glob('*.md'))]
    for path in paths:
        text = path.read_text(encoding='utf-8-sig')
        for raw in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', text):
            target = raw.strip().split(' "', 1)[0].strip('<>')
            if not target or re.match(r'[a-z][a-z0-9+.-]*:', target, re.I) or target.startswith('#'):
                continue
            count += 1
            name = unquote(target.split('#', 1)[0])
            if not (path.parent/name).exists():
                broken.append({'document': path.relative_to(base.parent).as_posix(), 'target': target})
    return {'local_links_checked': count, 'missing_targets': broken,
            'scope': 'file existence; anchors, external URLs and upstream/generated documentation are not checked'}


def audit(base=BASE):
    base = Path(base).resolve()
    files, retained = authored_files(base)
    trees, errors, rows, text_files = {}, [], [], {}
    for path in files:
        relative = path.relative_to(base)
        raw = path.read_bytes()
        row = {'path': relative.as_posix(), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        if relative.parts[0] == 'jarvis':
            row['role'] = 'runtime'
        elif relative.parts[0] == 'tests' or path.name.startswith('verify_'):
            row['role'] = 'verification'
        elif relative.parts[0] == 'skills':
            row['role'] = 'bundled_skill'
        elif relative.parts[0] == 'integrations':
            row['role'] = 'reference_or_adapter_manifest'
        elif relative.parts[0] == 'docs' or path.suffix == '.md':
            row['role'] = 'documentation'
        else:
            row['role'] = 'setup_entrypoint_example_or_configuration'
        if path.suffix in {'.py', '.md', '.json', '.cmd', '.ps1', '.yml', '.yaml', '.txt'} and len(raw) < 2_000_000:
            try:
                text_files[row['path']] = raw.decode('utf-8-sig')
            except UnicodeError:
                pass
        if path.suffix == '.py' and relative.parts[0] != 'integrations':
            try:
                tree = ast.parse(raw.decode('utf-8-sig'), filename=row['path'])
                name = module_name(relative)
                trees[name] = tree
                row['module'] = name
                row['symbols'] = [{'name': node.name, 'line': node.lineno,
                                   'kind': type(node).__name__} for node in tree.body
                                  if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
                row['imports'] = sorted(imports(tree, name, path.name == '__init__.py'))
            except (SyntaxError, UnicodeError) as exc:
                errors.append({'path': row['path'], 'error_type': type(exc).__name__,
                               'line': getattr(exc, 'lineno', None)})
        rows.append(row)
    by_module = {row['module']: row for row in rows if 'module' in row}
    users = defaultdict(set)
    for row in by_module.values():
        for name in row['imports']:
            parts = name.split('.')
            while parts:
                candidate = '.'.join(parts)
                if candidate in by_module:
                    users[candidate].add(row['path'])
                    break
                parts.pop()
    # Literal strings catch worker -m launches and filename-driven discovery.
    for row in rows:
        name = row.get('module')
        if name:
            pattern = re.compile(r'(?<![\w.])'+re.escape(name)+r'(?![\w.])')
            for path, text in text_files.items():
                if path != row['path'] and (row['path'] in text or pattern.search(text)):
                    users[name].add(path)
            row['referenced_by'] = sorted(users[name])
            row['retention'] = ('connected_by_import_or_reference' if users[name] else
                                'entrypoint_test_or_dynamic_candidate; manual review required, not unused')
    registry = skills = None
    if base == BASE:
        from types import SimpleNamespace
        from jarvis.tools import SPECS
        from jarvis.skill_memory import SkillMemory
        registry = [{'name': spec.name, 'backend': spec.backend, 'approval': spec.approval} for spec in SPECS]
        memory = SimpleNamespace(base=base, vault=base/'.jarvis-runtime/obsidian-vault', enabled=False)
        source = SkillMemory(memory)
        skills = {'names': [row['name'] for row in source.catalog], 'errors': source.skill_errors}
        source.close()
    return {'date_ist': datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat(),
            'scope': 'AST/hash/reference inventory of authored source, tests, guides and integration metadata; no source execution or deletion',
            'limits': 'References do not prove live functionality. Absent static references do not prove unused files. Private data and generated/upstream groups are retained without content inspection.',
            'counts': dict(Counter(row['role'] for row in rows)), 'files': rows,
            'retained_groups': retained, 'parse_errors': errors, 'tools': registry,
            'skills': skills, 'documentation': documentation_links(base)}


def static_analysis(report, base=BASE):
    """Optional Pyflakes pass; retain warnings separately from correctness errors."""
    target = Path(base)/'.jarvis-runtime/audit-tools'
    sys.path.insert(0, str(target))
    try:
        from pyflakes.checker import Checker
    except ImportError:
        return {'status': 'unavailable', 'setup': 'Install requirements-audit.txt into .jarvis-runtime/audit-tools'}
    finally:
        sys.path.remove(str(target))
    warnings = {'UnusedImport', 'UnusedVariable', 'RedefinedWhileUnused'}
    findings, checked = [], 0
    for row in report['files']:
        if 'module' not in row:
            continue
        tree = ast.parse((Path(base)/row['path']).read_text(encoding='utf-8-sig'))
        checked += 1
        for message in Checker(tree, filename=row['path']).messages:
            kind = type(message).__name__
            findings.append({'path': row['path'], 'line': message.lineno, 'kind': kind,
                             'severity': 'warning' if kind in warnings else 'error',
                             'message': message.message % message.message_args})
    return {'status': 'checked', 'files_checked': checked, 'errors': sum(r['severity']=='error' for r in findings),
            'warnings': sum(r['severity']=='warning' for r in findings), 'findings': findings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=BASE/'artifacts/repository-audit.json')
    parser.add_argument('--static', action='store_true', help='Run the optional isolated Pyflakes checker.')
    args = parser.parse_args()
    report = audit()
    if args.static:
        report['static_analysis'] = static_analysis(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('counts', 'parse_errors', 'skills', 'documentation')}, ensure_ascii=False))
    if args.static:
        print(json.dumps({key: value for key, value in report['static_analysis'].items() if key != 'findings'}))
    raise SystemExit(bool(report['parse_errors'] or report['documentation']['missing_targets']
                          or report['skills']['errors'] or (args.static and (
                              report['static_analysis']['status'] != 'checked' or report['static_analysis']['errors']))))


if __name__ == '__main__':
    main()
