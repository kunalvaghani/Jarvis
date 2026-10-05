"""Index pinned upstream source without importing or executing upstream code."""
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

BASE = Path(__file__).resolve().parent
REPOS = [('ufo', 'microsoft/ufo'), ('windows-mcp', 'cursortouch/windows-mcp'),
         ('cua', 'trycua/cua'), ('open-computer-use', 'opensymph/open-computer-use'),
         ('agent-s', 'simular-ai/Agent-S')]
EXTENSIONS = {'.py', '.rs', '.go', '.ts', '.tsx', '.js', '.mjs', '.swift', '.kt',
              '.cpp', '.cc', '.c', '.h', '.cs', '.ps1', '.sh'}


def category(path):
    name = path.lower()
    if any(x in name.split('/') for x in ('tests', 'test', 'fuzz')) or '_test.' in name:
        return 'test/fixture; not a runtime action'
    if any(x in name for x in ('macos', 'linux', 'hyprland', 'android', 'ios', 'lume')):
        return 'other platform/runtime; not a local Windows adapter'
    if any(x in name for x in ('automator/', '/uia/', '/input/', 'native_actions', '/aci/', '/desktop/', '/tools/')):
        return 'execution candidate; selected adapters require individual review'
    if any(x in name for x in ('agents/', 'model', 'llm', 'planner', 'grounding')):
        return 'model/orchestration; not a deterministic task snippet'
    return 'support/app/SDK/build code; not automatically callable'


def audit():
    result = {'date': datetime.now(timezone.utc).isoformat(),
              'scope': 'All Git-tracked files with the listed source extensions indexed and hashed. Python symbols use AST; other languages use declaration matching. This inventory is not a claim of line-by-line manual review or runtime compatibility.',
              'source_extensions': sorted(EXTENSIONS),
              'repositories': []}
    for priority, (name, repo) in enumerate(REPOS, 1):
        root = BASE / 'integrations' / 'execution-upstream' / name
        revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
        paths = subprocess.check_output(['git', 'ls-files'], cwd=root, text=True).splitlines()
        rows = []
        for relative in paths:
            path = root / relative
            if path.suffix not in EXTENSIONS or not path.is_file():
                continue
            data = path.read_bytes()
            text = data.decode('utf-8-sig', errors='replace')
            symbols, error = [], None
            if path.suffix == '.py':
                try:
                    tree = ast.parse(text)
                    symbols = [{'name': node.name, 'line': node.lineno,
                                'kind': type(node).__name__} for node in ast.walk(tree)
                               if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))]
                except SyntaxError as exc:
                    error = f'{exc.msg} at {exc.lineno}; scanner Python version may differ from upstream'
            else:
                pattern = r'^\s*(?:(?:pub(?:\([^)]*\))?|export|async|public|private|static|unsafe)\s+)*(?:fn|func|function|class|struct|interface)\s+(?:\([^)]*\)\s*)?(\w+)'
                symbols = [{'name': m.group(1), 'line': text.count('\n', 0, m.start()) + 1,
                            'kind': 'declaration'} for m in re.finditer(pattern, text, re.M)]
            rows.append({'path': relative, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                         'category': category(relative), 'symbols': symbols,
                         **({'parse_note': error} if error else {})})
        result['repositories'].append({'priority': priority, 'name': name,
            'url': f'https://github.com/{repo}', 'revision': revision,
            'tracked_files': len(paths), 'source_files': len(rows),
            'symbol_count': sum(len(row['symbols']) for row in rows),
            'categories': dict(Counter(row['category'] for row in rows)), 'files': rows})
    destination = BASE / 'integrations' / 'execution-primitives'
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'source-inventory.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps([{k: v for k, v in repo.items() if k != 'files'}
                      for repo in result['repositories']], indent=2))
    return result


if __name__ == '__main__':
    audit()
