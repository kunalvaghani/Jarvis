"""Index actual supplied specifications separately from execution evidence."""
import ast
import hashlib
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace

OUT = Path(__file__).resolve().parent
APP = Path('D:\\Kunals GitHub Repo\\LocalGithub\\Jarvis-e2e-e5af0e7\\app')
PACK = Path('D:/Phython Project/Jarvis test')
sys.path.insert(0, str(APP))
from scripts.verification.audit_catalog import TESTS
from jarvis.tools import ToolRegistry
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
catalog = PACK / 'test_cases/jarvis_test_cases.jsonl'
original = [json.loads(line) for line in catalog.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
assert len(original) == len({r['id'] for r in original}) == 1184
rows = []
for row in original:
    number = int(row['id'].split('-')[1])
    rows.append({**row, 'variant': 'original', 'status': 'NOT RUN', 'scope': 'planned specification, not execution',
        'candidate_tests_present': [f'tests/test_{name}.py' for name in TESTS[number] if (APP / f'tests/test_{name}.py').is_file()]})
documents = {p.name: {'sha256': sha(p), 'headings': re.findall(r'^#{1,3} (.+)', p.read_text(encoding='utf-8-sig'), re.M)}
    for p in (PACK / 'prompts').glob('*.md')}
request = Path('C:/Users/kunal/Downloads/99_CODEX_FINAL_INDEPENDENT_REVIEW.md')
documents[request.name] = {'sha256': sha(request), 'headings': re.findall(r'^#{1,3} (.+)', request.read_text(encoding='utf-8-sig'), re.M)}
for number in range(31, 38):
    path = next(Path('C:/Users/kunal/Downloads').glob(f'{number}_*REVISED.md'))
    text = path.read_text(encoding='utf-8-sig')
    documents[path.name] = {'sha256': sha(path), 'headings': re.findall(r'^#{1,3} (.+)', text, re.M)}
    for identifier, behavior in re.findall(r'- \*\*(JRV-\d{2}-\d{3}):\*\* (.+)', text):
        rows.append({'id': identifier, 'variant': 'revised', 'input_and_expected': behavior,
            'status': 'NOT RUN', 'scope': 'revised acceptance specification, not execution'})
unique = {}
for row in rows:
    behavior = row.get('input_and_expected', row.get('input', '') + ' -> ' + row.get('expected', ''))
    unique.setdefault((row['id'], behavior), row)
(OUT / 'corpus-specifications.jsonl').write_text('\n'.join(json.dumps(r) for r in unique.values()) + '\n', encoding='utf-8')
(OUT / 'corpus-provenance.json').write_text(json.dumps({'original_catalog_sha256': sha(catalog),
    'checked_out_catalog_matches': sha(catalog) == sha(APP / 'artifacts/jarvis-audit/catalog-input.jsonl'),
    'original_rows': len(original), 'deduplicated_id_behavior_rows': len(unique), 'documents': documents,
    'master_found': 'prompts/00_MASTER.md', '00_MASTER_CONTRACT': 'unavailable under that name',
    'unrelated_download_master': 'EDITH document inspected and excluded from Jarvis review scope'}, indent=2), encoding='utf-8')
modules = {}
edges = []
for path in (APP / 'jarvis').glob('*.py'):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    module = 'jarvis.' + path.stem
    modules[module] = {'path': path.relative_to(APP).as_posix(), 'sha256': sha(path),
        'functions': [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))],
        'classes': [n.name for n in tree.body if isinstance(n, ast.ClassDef)]}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            edges.append({'caller': module, 'import': ('.' * node.level) + (node.module or ''), 'line': node.lineno})
registry = ToolRegistry(SimpleNamespace(base=OUT / 'unused-registry-root', config={}, allowed_tools=None, skills=None, report=lambda *a: None))
(OUT / 'source-graph.json').write_text(json.dumps({'modules': modules, 'import_edges': edges,
    'registered_tools': sorted(registry.specs), 'registration_is_not_live_functionality': True}, indent=2), encoding='utf-8')
print(json.dumps({'original_cases': len(original), 'id_behavior_variants': len(unique), 'modules': len(modules), 'registered_tools': len(registry.specs)}))
