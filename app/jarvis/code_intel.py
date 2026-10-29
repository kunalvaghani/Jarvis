"""PCIDE code intelligence: project facts, symbol retrieval, search planning, guarded candidates and research.

Deterministic, CPU-only and I/O-bound. No model is loaded here. All retrieved text (READMEs, source,
web pages) is untrusted data: it is scanned and ranked, never executed and never treated as instructions.
"""
import ast
import hashlib
import json
import math
import re
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

from .code_memory import PERMISSIVE, EVIDENCE_WEIGHT, tokens

SOURCE_SUFFIXES = {'.py': 'python', '.js': 'javascript', '.jsx': 'javascript', '.ts': 'typescript', '.tsx': 'typescript',
                   '.vue': 'vue', '.svelte': 'svelte', '.css': 'css', '.scss': 'css', '.html': 'html', '.cs': 'csharp', '.go': 'go',
                   '.rs': 'rust', '.java': 'java'}
SKIP = {'.git', 'node_modules', '.venv', 'venv', '__pycache__', 'dist', 'build', '.next', 'target', '.jarvis', '.jarvis-runtime'}
STOP = {'the', 'and', 'with', 'for', 'that', 'this', 'make', 'create', 'build', 'add', 'use', 'using', 'into', 'from', 'jarvis',
        'please', 'app', 'application', 'should', 'have', 'some', 'beautiful', 'professional', 'nice', 'good', 'my', 'a', 'an',
        'everything', 'work', 'it', 'more', 'really', 'very', 'all', 'of', 'to', 'in', 'on'}
UI_CONCEPTS = {
    'navigation': {'dock', 'navbar', 'navigation', 'nav', 'sidebar', 'menu', 'toolbar', 'tabs'},
    'chart': {'chart', 'charts', 'graph', 'graphs', 'plot', 'visualization', 'visualisation', 'sparkline'},
    'card': {'card', 'cards', 'tile', 'tiles', 'panel', 'panels'},
    'animation': {'animated', 'animation', 'animations', 'transition', 'transitions', 'motion', 'smooth', 'spring', 'hover'},
    'layout': {'dashboard', 'layout', 'grid', 'responsive', 'landing', 'page', 'hero'},
    'form': {'form', 'forms', 'input', 'settings', 'login'},
    'dialog': {'modal', 'dialog', 'popover', 'drawer', 'toast'},
    'table': {'table', 'tables', 'list', 'datagrid'},
    'theme': {'theme', 'dark', 'light', 'futuristic', 'hud', 'style', 'design'},
}
CODE_CONCEPTS = {
    'telemetry': {'cpu', 'ram', 'gpu', 'telemetry', 'system', 'monitor', 'monitoring', 'performance', 'battery', 'disk', 'temperature'},
    'search': {'search', 'index', 'indexing', 'find', 'query', 'lookup'},
    'realtime': {'realtime', 'real', 'live', 'websocket', 'stream', 'streaming', 'polling'},
    'persistence': {'database', 'sqlite', 'store', 'storage', 'save', 'persist', 'history'},
    'filesystem': {'file', 'files', 'folder', 'watch', 'watcher', 'filesystem'},
    'scheduling': {'schedule', 'scheduler', 'cron', 'timer', 'reminder'},
    'parsing': {'parse', 'parser', 'csv', 'json', 'markdown', 'xml'},
}
# Behaviour-level strategies: the planner chooses the smallest set that fits the stated scale and constraints.
STRATEGIES = {
    'search': [('sqlite fts5 full text search', lambda r: True),
               ('bm25 ranking implementation', lambda r: 'rank' in r or 'relevan' in r or 'fast' in r),
               ('incremental file indexing watchdog', lambda r: 'file' in r or 'folder' in r),
               ('hybrid vector bm25 retrieval', lambda r: 'semantic' in r or 'meaning' in r or 'similar' in r)],
    'telemetry': [('psutil cpu ram disk monitoring', lambda r: True), ('gpu nvidia-smi usage monitoring', lambda r: 'gpu' in r)],
    'realtime': [('live updating chart high frequency', lambda r: 'chart' in r or 'graph' in r)],
}
ANIMATION_LIBRARIES = {'framer-motion', 'motion', 'gsap', 'react-spring', '@react-spring/web', 'animejs', 'lottie-web', 'popmotion',
                       '@motionone/dom', 'velocity-animate', 'auto-animate', '@formkit/auto-animate'}
NETWORK_LIBRARIES = {'axios', 'node-fetch', 'got', 'superagent', 'firebase', 'aws-sdk', '@aws-sdk/client-s3', 'requests', 'httpx',
                     'aiohttp', 'boto3', 'socket.io-client', 'pusher-js', '@supabase/supabase-js'}
COPYLEFT = re.compile(r'^(?:A?GPL|LGPL|MPL|EPL|EUPL|CDDL|OSL|SSPL|CC-BY-SA|CC-BY-NC)', re.I)
DANGER = [
    ('dynamic code execution', re.compile(r'\beval\s*\(|new\s+Function\s*\(|\bexec\s*\(|__import__\s*\(|\bcompile\s*\(.*exec', re.I)),
    ('process execution', re.compile(r'child_process|\bsubprocess\b|\bos\.system\s*\(|\bspawn\s*\(|Start-Process|powershell\s+-', re.I)),
    ('network access', re.compile(r'\bfetch\s*\(|XMLHttpRequest|\baxios\b|\brequests\.(?:get|post)|\bhttpx\b|urllib\.request|new\s+WebSocket|socket\.connect', re.I)),
    ('file-system writes or deletion', re.compile(r'fs\.(?:write|unlink|rm)\w*\(|shutil\.rmtree|os\.remove\(|\.unlink\(|open\([^)]*[\'"][wa]\+?[\'"]', re.I)),
    ('telemetry or tracking', re.compile(r'google-analytics|googletagmanager|segment\.(?:com|io)|mixpanel|amplitude\.com|sentry\.io|hotjar|posthog', re.I)),
    ('obfuscated payload', re.compile(r'[A-Za-z0-9+/]{300,}={0,2}|(?:\\x[0-9a-f]{2}){24,}', re.I)),
]
INSTALL_SCRIPTS = {'preinstall', 'install', 'postinstall', 'prepare', 'prepublish'}


def words(text):
    return [w for w in re.findall(r'[a-z0-9][a-z0-9+#.-]*', str(text or '').casefold()) if w not in STOP and len(w) > 1]


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def project_facts(root):
    """Language, framework, dependencies, styling and design system actually present in a project (read-only)."""
    root = Path(root)
    facts = {'root': str(root), 'languages': {}, 'dependencies': {}, 'framework': None, 'framework_version': None,
             'styling': [], 'design_system': None, 'animation': [], 'python_gui': None, 'tokens_file': None}
    package = read_json(root / 'package.json')
    deps = {**(package.get('dependencies') or {}), **(package.get('devDependencies') or {})}
    for line in ((root / 'requirements.txt').read_text(encoding='utf-8', errors='replace').splitlines() if (root / 'requirements.txt').is_file() else []):
        found = re.match(r'\s*([A-Za-z0-9_.-]+)\s*(?:[=<>~!]=?\s*([0-9][\w.]*))?', line)
        if found and not line.strip().startswith('#'):
            deps.setdefault(found[1].casefold(), found[2] or '*')
    pyproject = (root / 'pyproject.toml').read_text(encoding='utf-8', errors='replace') if (root / 'pyproject.toml').is_file() else ''
    for found in re.finditer(r'"([A-Za-z0-9_.-]+)\s*(?:[=<>~!]=?\s*([0-9][\w.]*))?[^"]*"', pyproject.split('dependencies', 1)[-1][:3000] if 'dependencies' in pyproject else ''):
        deps.setdefault(found[1].casefold(), found[2] or '*')
    facts['dependencies'] = {k: str(v) for k, v in deps.items()}
    for name, label in (('next', 'next'), ('react', 'react'), ('vue', 'vue'), ('svelte', 'svelte'), ('@angular/core', 'angular'),
                        ('solid-js', 'solid'), ('electron', 'electron')):
        if name in deps:
            facts['framework'], facts['framework_version'] = facts['framework'] or label, facts['framework_version'] or deps[name]
    if 'tailwindcss' in deps or any((root / n).is_file() for n in ('tailwind.config.js', 'tailwind.config.ts', 'tailwind.config.cjs')):
        facts['styling'].append('tailwind')
    if 'styled-components' in deps or '@emotion/react' in deps:
        facts['styling'].append('css-in-js')
    if (root / 'components.json').is_file():
        facts['design_system'] = 'shadcn'
    for name, label in (('@mui/material', 'mui'), ('@chakra-ui/react', 'chakra'), ('antd', 'antd'), ('@mantine/core', 'mantine')):
        if name in deps:
            facts['design_system'] = facts['design_system'] or label
    facts['animation'] = sorted(set(deps) & ANIMATION_LIBRARIES)
    count = 0
    for path in iterate(root):
        count += 1
        language = SOURCE_SUFFIXES.get(path.suffix.casefold())
        if language:
            facts['languages'][language] = facts['languages'].get(language, 0) + 1
        if path.suffix == '.py' and facts['python_gui'] is None and path.stat().st_size < 400_000:
            text = path.read_text(encoding='utf-8', errors='replace')
            for module, label in (('tkinter', 'tkinter'), ('PySide6', 'pyside6'), ('PyQt5', 'pyqt5'), ('PyQt6', 'pyqt6'), ('customtkinter', 'customtkinter')):
                if re.search(r'^\s*(?:import|from)\s+' + module, text, re.M):
                    facts['python_gui'] = label
                    break
        if facts['tokens_file'] is None and path.suffix in {'.css', '.scss'} and path.stat().st_size < 400_000 and \
                re.search(r'--[a-z][\w-]*\s*:', path.read_text(encoding='utf-8', errors='replace')):
            facts['tokens_file'] = path.relative_to(root).as_posix()
        if count > 4000:
            break
    if not facts['framework'] and facts['languages']:
        facts['framework'] = facts['python_gui'] if facts['python_gui'] else None
    facts['language'] = max(facts['languages'], key=facts['languages'].get) if facts['languages'] else None
    return facts


def iterate(root, limit=4000):
    stack, seen = [Path(root)], 0
    while stack:
        folder = stack.pop()
        try:
            entries = sorted(folder.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.name in SKIP or entry.name.startswith('.') or entry.is_symlink():
                continue
            if entry.is_dir():
                stack.append(entry)
            elif entry.is_file():
                seen += 1
                yield entry
                if seen >= limit:
                    return


def symbols_of(path, text):
    """Function/class/component symbols with a one-line description (AST for Python, patterns otherwise)."""
    rows = []
    if path.suffix == '.py':
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError):
            return rows
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                doc = (ast.get_docstring(node) or '').split('\n')[0][:160]
                args = [a.arg for a in node.args.args] if not isinstance(node, ast.ClassDef) else []
                rows.append({'name': node.name, 'kind': 'class' if isinstance(node, ast.ClassDef) else 'function',
                             'signature': f"{node.name}({', '.join(args)})", 'doc': doc, 'line': node.lineno})
        return rows
    for found in re.finditer(r'^(?:export\s+(?:default\s+)?)?(?:async\s+)?(?:function\s+([A-Za-z_$][\w$]*)|class\s+([A-Za-z_$][\w$]*)|'
                             r'(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>|'
                             r'(?:const|let)\s+([A-Z][\w$]*)\s*=\s*(?:React\.)?(?:forwardRef|memo)\()', text, re.M):
        name = next(g for g in found.groups() if g)
        line = text.count('\n', 0, found.start()) + 1
        comment = re.search(r'/\*\*?\s*(.{1,160}?)\s*(?:\*/|\n)', text[max(0, found.start() - 300):found.start()])
        rows.append({'name': name, 'kind': 'component' if name[:1].isupper() else 'function', 'signature': name,
                     'doc': comment[1] if comment else '', 'line': line})
    return rows


class SymbolIndex:
    """Function-level index of one project, refreshed by mtime; nothing is embedded or copied elsewhere."""

    def __init__(self):
        self.lock = threading.RLock()
        self.cache = {}

    def symbols(self, root, limit=1500):
        root = Path(root)
        rows = []
        with self.lock:
            files = self.cache.setdefault(str(root), {})
            for path in iterate(root, limit):
                if path.suffix.casefold() not in SOURCE_SUFFIXES or path.suffix in {'.css', '.scss', '.html'}:
                    continue
                try:
                    stat = path.stat()
                    key = (stat.st_mtime_ns, stat.st_size)
                    if files.get(str(path), (None,))[0] != key:
                        if stat.st_size > 300_000:
                            continue
                        text = path.read_text(encoding='utf-8', errors='replace')
                        files[str(path)] = (key, symbols_of(path, text))
                except OSError:
                    continue
                relative = path.relative_to(root).as_posix()
                rows += [{**s, 'path': relative} for s in files[str(path)][1]]
        return rows

    def search(self, root, query, limit=8, symbols=None):
        wanted = set(tokens(query)) - STOP
        if not wanted:
            return []
        rows = []
        for symbol in self.symbols(root) if symbols is None else symbols:
            have = set(tokens(symbol['name'] + ' ' + symbol['path'] + ' ' + symbol['doc']))
            hits = wanted & have
            if hits:
                rows.append({**symbol, 'score': round(len(hits) / len(wanted), 3)})
        rows.sort(key=lambda r: (-r['score'], r['path']))
        return rows[:limit]


class CodeSearchPlanner:
    """Smallest sufficient set of search intents for a requirement, deduplicated and budgeted."""

    def plan(self, requirement, facts=None, budget=4):
        facts = facts or {}
        text = str(requirement or '')
        low = text.casefold()
        phrases = [p.strip() for p in re.split(r',|;|\band\b|\bwith\b|\bplus\b', low) if len(words(p)) >= 1]
        framework = facts.get('framework') or ('react' if re.search(r'\breact\b', low) else None)
        language = facts.get('language')
        intents, seen = [], set()
        for phrase in phrases or [low]:
            core = words(phrase)
            # Specific components first; animation/theme/layout are modifiers of them.
            ui = sorted((name for name, members in UI_CONCEPTS.items() if set(core) & members),
                        key=lambda n: ['navigation', 'chart', 'card', 'table', 'form', 'dialog', 'layout', 'theme', 'animation'].index(n))
            code = sorted(name for name, members in CODE_CONCEPTS.items() if set(core) & members)
            queries = []
            for concept in code:
                for query, applies in STRATEGIES.get(concept, []):
                    if applies(low):
                        queries.append(('code', concept, query))
            if ui:
                queries.append(('ui', ui[0], ' '.join(([framework] if framework else []) + core[:5])))
            if code and not any(c in STRATEGIES for c in code):
                queries.append(('code', code[0], ' '.join(core[:6])))
            if not ui and not code and core:
                queries.append(('code', 'general', ' '.join(([framework] if framework else []) + core[:6])))
            for kind, concept, query in queries:
                signature = frozenset(words(query))
                if signature in seen or not signature:
                    continue
                seen.add(signature)
                intents.append({'kind': kind, 'concept': concept, 'phrase': phrase.strip(), 'query': query,
                                'language': 'TypeScript' if framework in {'react', 'next', 'vue', 'svelte', 'angular'}
                                else (language or '').title() or None})
        # Smallest sufficient set: one intent per concept first, then extra strategies while budget remains.
        first, rest, concepts = [], [], set()
        for intent in intents:
            (rest if intent['concept'] in concepts else first).append(intent)
            concepts.add(intent['concept'])
        return (first + rest)[:budget]

    @staticmethod
    def github_query(intent, min_stars=20):
        qualifiers = [f'stars:>={min_stars}', 'archived:false']
        if intent.get('language'):
            qualifiers.append('language:' + intent['language'])
        return intent['query'] + ' ' + ' '.join(qualifiers)


class ExternalCodeIntegrationGuard:
    """Hard gates and findings for untrusted code before any reuse."""

    def __init__(self, policy=None):
        self.policy = policy or {}

    def license_gate(self, license_id, license_files):
        license_id = (license_id or '').strip()
        if not license_id or license_id.upper() in {'NOASSERTION', 'OTHER', 'UNKNOWN', 'NONE'}:
            return False, 'license missing or ambiguous: reference only, no copying'
        if COPYLEFT.match(license_id):
            return False, f'{license_id} has copyleft/non-commercial obligations: reference only unless you approve'
        if license_id not in PERMISSIVE:
            return False, f'{license_id} is not on the permissive list: reference only'
        if not license_files:
            return False, 'license file not found in the source: reference only'
        return True, f'{license_id} permits reuse with attribution; preserve the notice'

    def scan(self, files, manifest=None):
        findings, hard = [], []
        from .cloud_policy import SECRET
        for path, text in (files or {}).items():
            text = str(text)
            if SECRET.search(text):
                hard.append(f'hardcoded credential-like value in {path}')
            for label, pattern in DANGER:
                match = pattern.search(text)
                if match:
                    findings.append({'path': path, 'risk': label, 'evidence': match.group(0)[:80]})
            if re.search(r'ignore (?:all |previous |prior )?instructions|you are now|system prompt', text, re.I):
                findings.append({'path': path, 'risk': 'embedded instructions (treated as data)', 'evidence': 'instruction-like text'})
        scripts = (manifest or {}).get('scripts') or {}
        for name in sorted(set(scripts) & INSTALL_SCRIPTS):
            hard.append(f'package install script "{name}": {str(scripts[name])[:80]} (never run automatically)')
        if any(f['risk'] == 'obfuscated payload' for f in findings):
            hard.append('obfuscated payload')
        return findings, hard

    def dependency_gate(self, dependencies, facts):
        """Project dependency policy from explicit requirements, e.g. no external animation library."""
        rejected = []
        existing = set((facts or {}).get('dependencies', {}))
        for name in dependencies or {}:
            low = name.casefold()
            if self.policy.get('no_animation_library') and low in ANIMATION_LIBRARIES:
                rejected.append(f'{name}: external animation libraries are prohibited for this project')
            if self.policy.get('offline') and low in NETWORK_LIBRARIES:
                rejected.append(f'{name}: network/cloud clients conflict with the offline requirement')
            if self.policy.get('no_new_dependencies') and low not in existing:
                rejected.append(f'{name}: new dependencies are not allowed for this project')
        return rejected

    def evaluate(self, candidate, facts=None):
        license_ok, license_note = self.license_gate(candidate.get('license'), candidate.get('license_files'))
        memory_source=str(candidate.get('source','')).startswith('verified memory')
        if memory_source and candidate.get('state') in {'PROJECT_VERIFIED','REUSABLE'} and str(candidate.get('origin','')).startswith('local:') and candidate.get('license')=='project':
            license_ok=True;license_note='Verified user-owned project code; preserve its local provenance.'
        if candidate.get('repository') and not memory_source:
            files=candidate.get('files') or {}
            notices=set(candidate.get('license_files') or [])
            source_present=any(name not in notices and name!='package.json' and isinstance(text,str) and text.strip()
                               for name,text in files.items())
            notice_present=any(isinstance(files.get(name),str) and files[name].strip() for name in notices)
            if not source_present or not notice_present:
                license_ok=False
                license_note+='; source or license notice not retrieved: reference only, no copying'
        findings, hard = self.scan(candidate.get('files'), candidate.get('manifest'))
        hard += self.dependency_gate(candidate.get('dependencies'), facts)
        offline = self.policy.get('offline')
        if offline and any(f['risk'] == 'network access' for f in findings):
            hard.append('network access conflicts with the offline requirement')
        framework = (facts or {}).get('framework')
        if framework and candidate.get('framework') and candidate['framework'] != framework:
            hard.append(f"built for {candidate['framework']}, project uses {framework}")
        return {'copy_allowed': license_ok and not hard, 'license': license_note, 'rejected': hard, 'findings': findings,
                'advisories': 'not checked (no offline advisory database); pin the revision and review before installing'}


WEIGHTS = {'functional_fit': .25, 'compatibility': .20, 'verification': .15, 'maintainability': .15, 'performance': .10,
           'integration_ease': .10, 'context': .05}
UI_WEIGHTS = {'visual_consistency': .4, 'accessibility': .3, 'motion_quality': .3}


class CodeCandidateRanker:
    """Hard gates first (the guard), then a weighted score. Weights are illustrative heuristics."""

    def __init__(self, weights=None):
        self.weights = {**WEIGHTS, **(weights or {})}

    def score(self, candidate, requirement, facts=None, guard=None):
        facts = facts or {}
        evaluation = (guard or ExternalCodeIntegrationGuard()).evaluate(candidate, facts)
        if evaluation['rejected']:
            return {'candidate': candidate['id'], 'score': 0., 'rejected': evaluation['rejected'], 'evaluation': evaluation}
        want = set(words(requirement))
        have = set(words(' '.join([candidate.get('name', ''), candidate.get('description', ''), ' '.join(candidate.get('symbols', []))])))
        parts = {'functional_fit': len(want & have) / max(1, len(want))}
        framework = facts.get('framework')
        parts['compatibility'] = 1. if not candidate.get('framework') or not framework or candidate['framework'] == framework else 0.
        new_deps = [d for d in candidate.get('dependencies', {}) if d not in facts.get('dependencies', {})]
        parts['compatibility'] *= 1 / (1 + .25 * len(new_deps))
        parts['verification'] = EVIDENCE_WEIGHT.get(candidate.get('state', 'DISCOVERED'), .1)
        pushed = candidate.get('pushed_days')
        parts['maintainability'] = .5 if pushed is None else max(0., 1 - pushed / 730)
        if candidate.get('archived'):
            parts['maintainability'] = 0.
        size = sum(len(str(t)) for t in (candidate.get('files') or {}).values()) or candidate.get('size', 4000)
        parts['performance'] = 1 / (1 + len(candidate.get('dependencies', {})) * .3)
        parts['integration_ease'] = 1 / (1 + size / 20000) * (1 if candidate.get('source_available', True) else .3)
        parts['context'] = 1. if candidate.get('scope', '').startswith('project:') or candidate.get('origin', '').startswith('local:') else .5
        total = sum(self.weights[k] * max(0., min(1., v)) for k, v in parts.items())
        if candidate.get('kind') == 'ui':
            ui = ui_quality(candidate, facts)
            parts.update(ui)
            total = .75 * total + .25 * sum(UI_WEIGHTS[k] * ui[k] for k in UI_WEIGHTS)
        if not evaluation['copy_allowed']:
            total *= .6  # Reference-only candidates still inform design but cost more to use.
        return {'candidate': candidate['id'], 'score': round(total, 4), 'parts': {k: round(v, 3) for k, v in parts.items()},
                'rejected': [], 'evaluation': evaluation}

    def rank(self, candidates, requirement, facts=None, guard=None):
        rows = [self.score(c, requirement, facts, guard) for c in candidates]
        return sorted(rows, key=lambda r: (-r['score'], r['candidate']))


def ui_quality(candidate, facts):
    source = '\n'.join(str(t) for t in (candidate.get('files') or {}).values())
    system = facts.get('design_system')
    consistency = 1. if not system or candidate.get('design_system') in {None, system} else .3
    if facts.get('styling') and candidate.get('styling') and not set(candidate['styling']) & set(facts['styling']):
        consistency *= .6
    accessibility = min(1., .2 + .2 * bool(re.search(r'aria-|role=', source)) + .3 * bool(re.search(r'onKeyDown|tabIndex|:focus-visible|focus', source))
                        + .3 * bool(re.search(r'<button|<nav|<a\s', source)))
    motion = .5
    if re.search(r'prefers-reduced-motion|useReducedMotion|reducedMotion', source):
        motion += .3
    if re.search(r'transform|opacity|translate|scale', source):
        motion += .2
    if re.search(r'transition:\s*(?:width|height|top|left)|animate\(\{\s*(?:width|height|top|left)', source):
        motion -= .3
    return {'visual_consistency': consistency, 'accessibility': accessibility, 'motion_quality': max(0., min(1., motion))}


# --- durable research results and handoff ---------------------------------------------------------------------------
RESEARCH_STATES = ('QUEUED', 'RUNNING', 'COMPLETE', 'CANCELLED', 'OBSOLETE', 'FAILED')
CANDIDATE_STATES = ('FOUND', 'VALIDATED', 'REJECTED', 'DELIVERED', 'ADOPTED', 'DECLINED', 'DISCARDED')


class ResearchBroker:
    """Research tasks and streamed candidates in SQLite; consumers wait on events, never poll the web."""

    def __init__(self, path, clock=time.time):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        self.lock = threading.RLock()
        self.changed = threading.Condition(self.lock)
        self.db = sqlite3.connect(path, check_same_thread=False, timeout=2)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS research (id TEXT PRIMARY KEY, project TEXT NOT NULL, created REAL NOT NULL, state TEXT NOT NULL,
                data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS candidates (seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, research TEXT NOT NULL,
                project TEXT NOT NULL, state TEXT NOT NULL, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, at REAL NOT NULL, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS metrics (key TEXT PRIMARY KEY, value REAL NOT NULL);
        ''')
        self.db.commit()

    @contextmanager
    def transaction(self):
        with self.lock:
            try:
                yield self.db
                self.db.commit()
                self.changed.notify_all()
            except BaseException:
                self.db.rollback()
                raise

    def create(self, project, goal, intents, *, task=None, spec_version=None, kind='code', budget=None):
        identity = uuid.uuid4().hex
        data = {'id': identity, 'project': str(project), 'goal': str(goal)[:1200], 'intents': intents, 'task': task,
                'spec_version': spec_version, 'kind': kind, 'budget': budget or {}, 'notes': [], 'created': self.clock(),
                'spent': {'queries': 0, 'repositories': 0, 'files': 0, 'bytes': 0, 'seconds': 0., 'model_calls': 0}}
        with self.transaction() as db:
            db.execute('INSERT INTO research VALUES(?,?,?,?,?)', (identity, data['project'], data['created'], 'QUEUED', json.dumps(data)))
        return identity

    def get(self, identity):
        with self.lock:
            row = self.db.execute('SELECT state, data FROM research WHERE id=?', (identity,)).fetchone()
        return {**json.loads(row[1]), 'state': row[0]} if row else None

    def update(self, identity, state=None, **changes):
        with self.transaction() as db:
            row = self.get(identity)
            if row is None:
                raise ValueError('Unknown research task')
            if row['state'] in {'CANCELLED', 'OBSOLETE'} and state not in {None, row['state']}:
                return row  # Late updates after cancellation are ignored.
            data = {k: v for k, v in row.items() if k != 'state'}
            data.update(changes)
            db.execute('UPDATE research SET state=?, data=? WHERE id=?', (state or row['state'], json.dumps(data, default=str), identity))
        return self.get(identity)

    def add(self, research, candidate, state='FOUND'):
        """Stream one candidate; ignored once its research is cancelled or obsolete."""
        task = self.get(research)
        if task is None or task['state'] in {'CANCELLED', 'OBSOLETE'}:
            return None
        # Candidate identities are per research pass: the same component found again in a later task is a new offer.
        identity = research[:12] + ':' + (candidate.get('id') or uuid.uuid4().hex)
        candidate = {**candidate, 'id': identity, 'research': research, 'task': task['task'], 'spec_version': task['spec_version'],
                     'at': self.clock()}
        with self.transaction() as db:
            db.execute('INSERT OR IGNORE INTO candidates(id,research,project,state,data) VALUES(?,?,?,?,?)',
                       (identity, research, task['project'], state, json.dumps(candidate, default=str)))
        return identity

    def set_candidate(self, identity, state, **changes):
        if state not in CANDIDATE_STATES:
            raise ValueError('Unknown candidate state')
        with self.transaction() as db:
            row = db.execute('SELECT data FROM candidates WHERE id=?', (identity,)).fetchone()
            if not row:
                raise ValueError('Unknown candidate')
            data = {**json.loads(row[0]), **changes}
            db.execute('UPDATE candidates SET state=?, data=? WHERE id=?', (state, json.dumps(data, default=str), identity))

    def candidates(self, project=None, research=None, states=None, after=0):
        query, args = 'SELECT seq, state, data FROM candidates WHERE seq>?', [after]
        if project:
            query += ' AND project=?'
            args.append(str(project))
        if research:
            query += ' AND research=?'
            args.append(research)
        with self.lock:
            rows = self.db.execute(query + ' ORDER BY seq', args).fetchall()
        rows = [{**json.loads(r[2]), 'state': r[1], 'seq': r[0]} for r in rows]
        return [r for r in rows if not states or r['state'] in states]

    def wait(self, project, after, timeout):
        """Block until a new candidate for the project exists (event-driven, bounded)."""
        deadline = time.monotonic() + timeout
        with self.changed:
            while True:
                rows = self.candidates(project=project, states={'VALIDATED'}, after=after)
                if rows or time.monotonic() >= deadline:
                    return rows
                self.changed.wait(max(0., deadline - time.monotonic()))

    def research(self, project=None, states=None):
        with self.lock:
            rows = self.db.execute('SELECT state, data FROM research' + (' WHERE project=?' if project else '') + ' ORDER BY created',
                                   ((str(project),) if project else ())).fetchall()
        rows = [{**json.loads(r[1]), 'state': r[0]} for r in rows]
        return [r for r in rows if not states or r['state'] in states]

    def cancel(self, identity, reason='cancelled'):
        task = self.update(identity, 'CANCELLED', cancel_reason=reason)
        for row in self.candidates(research=identity, states={'FOUND', 'VALIDATED'}):
            self.set_candidate(row['id'], 'DISCARDED', discard_reason=reason)
        return task

    def invalidate(self, project, spec_version, reason):
        """A newer requirement version makes queued/running research for older versions obsolete."""
        changed = []
        for task in self.research(project, states={'QUEUED', 'RUNNING', 'COMPLETE'}):
            if task['spec_version'] is not None and spec_version is not None and task['spec_version'] < spec_version:
                self.update(task['id'], 'OBSOLETE', obsolete_reason=reason)
                for row in self.candidates(research=task['id'], states={'FOUND', 'VALIDATED', 'DELIVERED'}):
                    self.set_candidate(row['id'], 'DISCARDED', discard_reason=reason)
                changed.append(task['id'])
        return changed

    def cached(self, key, ttl):
        with self.lock:
            row = self.db.execute('SELECT at, value FROM cache WHERE key=?', (key,)).fetchone()
        if row and self.clock() - row[0] <= ttl:
            try:value=json.loads(row[1])
            except (ValueError,TypeError):
                self.metric('cache_read_errors',1)
            else:
                self.metric('cache_hits', 1)
                return value
        self.metric('cache_misses', 1)
        return None

    def store(self, key, value):
        text=json.dumps(value,default=str)
        if len(text)>3_000_000:return False  # Never cache truncated JSON.
        with self.transaction() as db:
            db.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?)', (key, self.clock(), text))
        return True

    def metric(self, key, amount):
        with self.transaction() as db:
            db.execute('INSERT INTO metrics VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=value+excluded.value', (key, float(amount)))

    def metrics(self):
        with self.lock:
            return {r[0]: r[1] for r in self.db.execute('SELECT key, value FROM metrics')}

    def close(self):
        with self.lock:
            self.db.close()


# --- research workers (logical roles inside one bounded pool) ----------------------------------------------------------
UI_CATALOG = [
    # Discovery starting points. Licenses are never assumed: they are read from the repository at research time.
    {'name': 'shadcn/ui', 'homepage': 'https://ui.shadcn.com', 'repository': 'shadcn-ui/ui', 'framework': 'react',
     'styling': ['tailwind'], 'design_system': 'shadcn', 'tags': {'navigation', 'card', 'form', 'dialog', 'table', 'layout', 'theme', 'chart'}},
    {'name': 'Magic UI', 'homepage': 'https://magicui.design', 'repository': 'magicuidesign/magicui', 'framework': 'react',
     'styling': ['tailwind'], 'design_system': 'shadcn', 'tags': {'navigation', 'animation', 'card', 'layout'}},
    {'name': 'React Bits', 'homepage': 'https://reactbits.dev', 'repository': 'DavidHDev/react-bits', 'framework': 'react',
     'styling': ['css', 'tailwind'], 'design_system': None, 'tags': {'animation', 'navigation', 'card', 'layout', 'theme'}},
    {'name': 'Motion', 'homepage': 'https://motion.dev', 'repository': 'motiondivision/motion', 'framework': 'react',
     'styling': [], 'design_system': None, 'tags': {'animation'}},
    {'name': 'Aceternity UI', 'homepage': 'https://ui.aceternity.com', 'repository': None, 'framework': 'react',
     'styling': ['tailwind'], 'design_system': None, 'tags': {'animation', 'card', 'layout', 'navigation'}},
    {'name': '21st.dev', 'homepage': 'https://21st.dev', 'repository': None, 'framework': 'react', 'styling': ['tailwind'],
     'design_system': None, 'tags': {'navigation', 'card', 'animation', 'layout', 'form'}},
]


class ResearchRunner:
    """Code research, UI research and the compatibility/security validator for one research task.

    `http(url, params, raw)` is injected (RepoLearner's authenticated session in Jarvis, fixtures in tests).
    """

    def __init__(self, broker, memory, symbols, http=None, budget=None, ttl_days=7):
        self.broker, self.memory, self.symbols, self.http = broker, memory, symbols, http
        self.budget = {'queries': 4, 'repositories': 6, 'files': 20, 'bytes': 3_000_000, 'seconds': 90., 'concurrency': 3, **(budget or {})}
        self.ttl = ttl_days * 86400
        self.ranker = CodeCandidateRanker()
        self._source_lock=threading.RLock()
        self._source_reservations={}

    def local(self, research_id, project, facts, guard):
        """Memory-first: the current project's symbols and verified memory, instantly."""
        task = self.broker.get(research_id)
        found = 0
        indexed = self.symbols.symbols(project)  # One project walk per lookup, not one per intent.
        for intent in task['intents']:
            for symbol in self.symbols.search(project, intent['phrase'] or intent['query'], 4, symbols=indexed):
                if symbol['score'] < .5:
                    continue
                candidate = {'id': hashlib.sha1(f"{project}:{symbol['path']}:{symbol['name']}".encode()).hexdigest()[:16],
                             'kind': intent['kind'], 'name': symbol['name'], 'description': symbol['doc'] or symbol['signature'],
                             'source': 'project', 'origin': f"local:{symbol['path']}#L{symbol['line']}", 'symbols': [symbol['name']],
                             'license': 'project', 'state': 'PROJECT_VERIFIED', 'source_available': True, 'scope': 'project:self',
                             'intent': intent['query'], 'integration_point': symbol['path'], 'framework': None}
                ranked = self.ranker.score({**candidate, 'license': 'MIT', 'license_files': ['(project)']}, intent['phrase'], facts, guard)
                self.broker.add(research_id, {**candidate, 'ranking': ranked, 'license_status': 'own project code'}, 'VALIDATED')
                found += 1
            for row in self.memory.search(intent['phrase'] or intent['query'], project=project, limit=4):
                item = row['item']
                if item['state'] in {'PROJECT_VERIFIED','REUSABLE'}:
                    try:item=self.memory.verified_source(item['id'])
                    except ValueError:continue
                candidate = {'id': 'memory:' + item['id'], 'kind': intent['kind'], 'name': item['name'], 'description': item['description'],
                             'source': 'verified memory', 'origin': item['origin'], 'license': item['license'],
                             'license_files': item['license_files'], 'state': item['state'], 'dependencies': item['dependencies'],
                             'framework': item['framework'] or None, 'symbols': item['symbols'], 'memory_item': item['id'],
                             'source_available': item['source_stored'], 'scope': item['scope'], 'intent': intent['query'],
                             'files': {'source': item['source'] or ''}, 'repository': item['repository'], 'commit': item['commit']}
                ranked = self.ranker.score(candidate, intent['phrase'], facts, guard)
                trusted = item['state'] in {'PROJECT_VERIFIED', 'REUSABLE'}
                self.broker.add(research_id, {**candidate, 'files': None, 'ranking': ranked,
                                              'license_status': ranked['evaluation']['license'] if not ranked['rejected'] else '; '.join(ranked['rejected']),
                                              'trusted': trusted},
                                'VALIDATED' if not ranked['rejected'] else 'REJECTED')
                found += 1
        return found

    def _get(self, url, params=None, raw=False):
        key = 'http:' + url + ':' + json.dumps(params or {}, sort_keys=True) + (':raw-utf8-v1' if raw else '')
        cached = self.broker.cached(key, self.ttl)
        if cached is not None:
            return cached
        value = self.http(url, params, raw)
        if raw and isinstance(value,(bytes,bytearray)):
            value=bytes(value).decode('utf-8-sig')
        self.broker.store(key, value)
        return value

    def _read_source(self,url,size,spent):
        """Reserve shared in-flight budgets without serializing HTTP reads."""
        size=size if type(size) is int and 0<size<=120000 else 120000
        key=id(spent)
        with self._source_lock:
            pending=self._source_reservations.setdefault(key,{'files':0,'bytes':0})
            if spent['files']+pending['files']>=self.budget['files'] or spent['bytes']+pending['bytes']+size>self.budget['bytes']:
                if not pending['files']:self._source_reservations.pop(key,None)
                return None
            pending['files']+=1;pending['bytes']+=size
        received=None;actual=0
        try:
            text=self._get(url,raw=True)
            if not isinstance(text,str):return None
            actual=len(text.encode('utf-8'))
            if actual>size:raise ValueError('Source response exceeds its inspected GitHub size; no source retained.')
            received=text
            return text
        finally:
            with self._source_lock:
                pending['files']-=1;pending['bytes']-=size
                if received is not None:spent['files']+=1;spent['bytes']+=actual
                if not pending['files']:self._source_reservations.pop(key,None)

    def external(self, research_id, project, facts, guard, cancelled=lambda: False):
        """GitHub/UI-library research within budget; streams validated candidates."""
        task = self.broker.get(research_id)
        if self.http is None:
            self.broker.update(research_id, notes=task['notes'] + ['online research unavailable: no HTTP session'])
            return 0
        started, spent, found = time.monotonic(), dict(task['spent']), 0
        def over():
            return cancelled() or time.monotonic() - started > self.budget['seconds'] or spent['bytes'] > self.budget['bytes'] \
                or (self.broker.get(research_id) or {}).get('state') in {'CANCELLED', 'OBSOLETE'}
        intents = task['intents'][:self.budget['queries']]
        def search(intent):
            if over():
                return intent, []
            try:
                value = self._get('https://api.github.com/search/repositories',
                                  {'q': CodeSearchPlanner.github_query(intent), 'sort': 'stars', 'per_page': 5})
                return intent, (value or {}).get('items', [])[:3]
            except Exception as exc:  # Network failure: record and continue with what local memory offers.
                return intent, [{'error': type(exc).__name__ + ': ' + str(exc)[:120]}]
        with ThreadPoolExecutor(max_workers=max(1, int(self.budget['concurrency']))) as pool:
            results = list(pool.map(search, intents))
        spent['queries'] += len(intents)
        catalog = []
        for intent in intents:
            if intent['kind'] == 'ui':
                catalog += [entry for entry in UI_CATALOG if intent['concept'] in entry['tags'] and entry not in catalog
                            and (not facts.get('framework') or entry['framework'] == facts.get('framework')
                                 or facts.get('framework') in {'next'} and entry['framework'] == 'react')]
        errors = [item['error'] for _, items in results for item in items if 'error' in item]
        repositories, seen = [], set()
        for intent, items in results:
            for item in items:
                if 'error' in item or item.get('full_name') in seen:
                    continue
                seen.add(item['full_name'])
                repositories.append((intent, item))
        for entry in catalog:
            if entry['repository'] and entry['repository'] not in seen:
                seen.add(entry['repository'])
                repositories.append(({'kind': 'ui', 'concept': next(iter(entry['tags'])), 'phrase': task['goal'], 'query': entry['name']},
                                     {'full_name': entry['repository'], 'catalog': entry}))
            elif not entry['repository']:
                # No public repository: design reference only; licensing must be confirmed on the site itself.
                self.broker.add(research_id, {'kind': 'ui', 'name': entry['name'], 'description': 'Design/component reference site',
                    'source': entry['homepage'], 'origin': entry['homepage'], 'license': 'unknown', 'state': 'DISCOVERED',
                    'source_available': False, 'license_status': 'reference only: per-component terms must be checked on the site',
                    'framework': entry['framework']}, 'VALIDATED')
                found += 1
        limited = [any('rate limit' in e.casefold() or '403' in e for e in errors)]
        lock = threading.Lock()
        def examine(pair):
            intent, item = pair
            if over() or limited[0]:
                return None
            try:
                return intent, self.inspect(intent, item, spent)
            except Exception as exc:
                detail = str(exc)
                rate = '403' in detail or 'rate limit' in detail.casefold()
                with lock:
                    errors.append(f"{item.get('full_name')}: {type(exc).__name__}" + (': rate limit' if rate else ''))
                    if rate:
                        limited[0] = True  # Stop spending requests; local memory and cached results remain available.
                return None
        with ThreadPoolExecutor(max_workers=max(1, int(self.budget['concurrency']))) as pool:
            inspected = [row for row in pool.map(examine, repositories[:self.budget['repositories']]) if row]
        limited = limited[0]
        for intent, candidate in inspected:
            ranked = self.ranker.score(candidate, intent['phrase'] or task['goal'], facts, guard)
            state = 'REJECTED' if ranked['rejected'] else 'VALIDATED'
            self.broker.add(research_id, {**candidate, 'files': candidate['files'],
                                          'ranking': ranked, 'license_status': ranked['evaluation']['license']
                                          if not ranked['rejected'] else '; '.join(ranked['rejected'])}, state)
            spent['repositories'] += 1
            found += 1
        if limited:
            errors.append('GitHub API rate limit reached; online research paused until it resets (configure a GitHub token to raise it)')
        spent['seconds'] = round(spent['seconds'] + time.monotonic() - started, 3)
        self.broker.update(research_id, spent=spent, notes=task['notes'] + ([f'network/search errors: {"; ".join(errors[:3])}'] if errors else []))
        return found

    def inspect(self, intent, item, spent):
        """Read the real repository: metadata, license file and the most relevant source files at a pinned commit."""
        name = item['full_name']
        meta = item if 'default_branch' in item else self._get(f'https://api.github.com/repos/{name}')
        branch = meta.get('default_branch', 'main')
        commit = (self._get(f'https://api.github.com/repos/{name}/commits/{branch}') or {}).get('sha')
        tree = self._get(f'https://api.github.com/repos/{name}/git/trees/{commit or branch}', {'recursive': '1'}) or {}
        paths = [e['path'] for e in tree.get('tree', []) if e.get('type') == 'blob' and e.get('size', 0) < 120_000]
        sizes={e['path']:e.get('size',0) for e in tree.get('tree',[]) if e.get('type')=='blob'}
        license_files = [p for p in paths if re.fullmatch(r'(?:LICEN[CS]E|COPYING)(?:\.\w+)?', Path(p).name, re.I)]
        want = set(words(intent['phrase'] or intent['query']))
        def relevance(path):
            return len(want & set(tokens(path))) + (1 if Path(path).suffix in SOURCE_SUFFIXES else -5)
        chosen = [p for p in sorted(paths, key=lambda p: -relevance(p)) if relevance(p) > 0][:max(1, self.budget['files'] // max(1, self.budget['repositories']))]
        files = {}
        # Policy and attribution must be observable before offering source for
        # copying. A budget exhausted before source/notice means reference only.
        wanted=(['package.json'] if 'package.json' in paths else [])+license_files[:1]+chosen
        for path in dict.fromkeys(wanted):
            text = self._read_source(f'https://raw.githubusercontent.com/{name}/{commit or branch}/{path}',sizes.get(path),spent)
            if isinstance(text, str):
                files[path] = text
        manifest = {}
        if 'package.json' in files:
            try:
                manifest = json.loads(files.pop('package.json'))
            except ValueError:
                manifest = {}
        license_id = ((meta.get('license') or {}).get('spdx_id') or '') if isinstance(meta.get('license'), dict) else ''
        pushed = meta.get('pushed_at')
        days = None
        if isinstance(pushed, str):
            try:
                from datetime import datetime, timezone
                days = (datetime.now(timezone.utc) - datetime.fromisoformat(pushed.replace('Z', '+00:00'))).days
            except ValueError:
                days = None
        catalog = item.get('catalog') or {}
        symbols = [s['name'] for p, t in files.items() for s in symbols_of(Path(p), t)][:40]
        return {'id': hashlib.sha1(f'{name}@{commit}'.encode()).hexdigest()[:16], 'kind': intent['kind'], 'name': name,
                'description': (meta.get('description') or '')[:300], 'source': f'https://github.com/{name}',
                'origin': f'https://github.com/{name}/tree/{commit or branch}', 'repository': name, 'commit': commit,
                'license': license_id, 'license_files': license_files, 'files': files, 'manifest': manifest,
                'dependencies': {**(manifest.get('peerDependencies') or {}), **(manifest.get('dependencies') or {})},
                'symbols': symbols, 'stars': meta.get('stargazers_count'), 'archived': bool(meta.get('archived')), 'pushed_days': days,
                'framework': catalog.get('framework') or ('react' if 'react' in (manifest.get('peerDependencies') or {}) or
                                                          'react' in (manifest.get('dependencies') or {}) else None),
                'styling': catalog.get('styling', []), 'design_system': catalog.get('design_system'),
                'state': 'INSPECTED', 'source_available': bool(files), 'intent': intent['query'],
                'evidence': [f'https://github.com/{name}/blob/{commit or branch}/{p}' for p in files][:8]}
