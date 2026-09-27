"""Bounded repository instructions, skill discovery and source maps.

Independent implementation inspired by Codex, Goose and Aider. No skill or
plugin code is imported, installed or executed by discovery.
"""
import ast
import json
import re
from pathlib import Path


def scoped(root, name):
    root = Path(root).resolve(strict=True)
    relative = Path(name)
    if relative.is_absolute() or relative.drive or '..' in relative.parts:
        raise ValueError('Use a project-relative path.')
    path = root / relative
    if not path.resolve().is_relative_to(root) or any(
            p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction())
            for p in (path, *path.parents) if p.is_relative_to(root)):
        raise ValueError('Linked or out-of-scope paths are unsupported.')
    return path


def bounded_text(path, limit=8000):
    with path.open('rb') as source:
        raw = source.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('Reference exceeds the read limit: ' + path.name)
    return raw.decode('utf-8-sig')


def instruction_context(project, target=None, budget=6000):
    """Read parent/root AGENTS then target ancestors, within the Git boundary.

    Only AGENTS.md and explicitly selected skill text are instruction sources.
    File contents, plugin descriptions and tool outputs stay untrusted data.
    """
    project = Path(project).resolve(strict=True)
    boundary = project
    for ancestor in (project, *project.parents):
        if (ancestor / '.git').exists():
            boundary = ancestor
            break
    folders = list(reversed([project, *[p for p in project.parents if p.is_relative_to(boundary)]]))
    if target:
        path = scoped(project, target)
        folders += list(reversed([p for p in (path.parent, *path.parent.parents)
                                  if p.is_relative_to(project) and p != project]))
    result, used = [], 0
    for folder in dict.fromkeys(folders):
        name = folder.relative_to(boundary).as_posix()
        path = scoped(boundary, (folder / 'AGENTS.md').relative_to(boundary))
        if not path.is_file():
            continue
        text = bounded_text(path)
        if used + len(text) > budget:
            raise ValueError('Repository instructions exceed the context budget; narrow the project.')
        result.append({'path': (Path(name) / 'AGENTS.md').as_posix(), 'text': text})
        used += len(text)
    return result


def skill_catalog(project):
    """Discover project-local skills and declarative plugin skill bundles."""
    root = Path(project).resolve(strict=True)
    entries = []
    directories = ['.agents/skills', '.jarvis/skills']
    plugins = scoped(root, '.jarvis/plugins')
    if plugins.is_dir():
        for child in sorted(plugins.iterdir())[:20]:
            if child.is_symlink() or not child.is_dir():
                continue
            manifest = scoped(root, child.relative_to(root) / 'plugin.json')
            if not manifest.is_file():
                continue
            data = json.loads(bounded_text(manifest))
            if not isinstance(data, dict):
                raise ValueError('Plugin manifest must be a JSON object.')
            if data.get('enabled') is True:
                directories.append((child.relative_to(root) / 'skills').as_posix())
    for directory in directories:
        folder = scoped(root, directory)
        if not folder.is_dir():
            continue
        for child in sorted(folder.iterdir())[:50]:
            if not child.is_dir() or child.is_symlink():
                continue
            path = scoped(root, child.relative_to(root) / 'SKILL.md')
            if not path.is_file():
                continue
            text = bounded_text(path)
            # Deliberately small frontmatter subset, no YAML runtime dependency.
            header = text.split('---', 2)[1] if text.startswith('---') and text.count('---') >= 2 else ''
            fields = dict(re.findall(r'^(name|description):\s*([^\n]+)', header, re.M))
            name = fields.get('name', child.name).strip().strip('"\'')
            if not re.fullmatch(r'[\w.-]{1,80}', name):
                raise ValueError('Skill names must be short identifiers.')
            if any(e['name'] == name for e in entries):
                raise ValueError('Duplicate skill name: ' + name)
            entries.append({'name': name, 'description': fields.get('description', '')[:300],
                            'path': path.relative_to(root).as_posix()})
    return entries[:100]


def selected_skills(project, goal, budget=6000):
    """Load only $name skills explicitly requested in the user's goal."""
    requested = set(re.findall(r'\$([\w.-]+)', goal))
    if not requested:
        return []
    catalog = {entry['name']: entry for entry in skill_catalog(project)}
    if requested - catalog.keys():
        raise ValueError('Requested skills unavailable: ' + ', '.join(sorted(requested - catalog.keys())))
    result, used = [], 0
    for name in sorted(requested):
        entry = catalog[name]
        text = bounded_text(scoped(project, entry['path']))
        used += len(text)
        if used > budget:
            raise ValueError('Selected skills exceed the context budget.')
        result.append({**entry, 'text': text})
    return result


def repository_map(project, files=None, budget=5000):
    """Aider-inspired source symbol map; never imports repository code."""
    if files is None:
        from .coder import project_files
        files = project_files(project)
    rows, used = [], 0
    for name in files[:160]:
        if re.search(r'secret|credential|password|private_key|access_token', name, re.I):
            continue
        row = name
        if Path(name).suffix == '.py':
            try:
                tree = ast.parse(bounded_text(scoped(project, name), 14000))
                symbols = [node.name for node in tree.body if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
                row += ': ' + ', '.join(symbols[:15]) if symbols else ''
            except (ValueError, OSError, UnicodeError, SyntaxError):
                pass
        if used + len(row) + 1 > budget:
            rows.append('[Repository map truncated]')
            break
        rows.append(row)
        used += len(row) + 1
    return '\n'.join(rows)


def coding_context(project, goal, target=None, files=None):
    return {'repository_instructions': instruction_context(project, target),
            'selected_skills': selected_skills(project, goal),
            'repository_map': repository_map(project, files)}


def compact_context(value, limit=24000):
    """Deterministic lossy compaction of observations, preserving recent context.

    Never compact the goal, source being edited, or repository instructions.
    The durable task record remains the source of truth for replay prevention.
    """
    if not isinstance(value, dict):
        return value
    result = dict(value)
    compacted = []
    for key in ('completed', 'previous', 'failures', 'prior_task', 'screen', 'references', 'history'):
        if len(json.dumps(result, ensure_ascii=False)) <= limit:
            break
        data = result.get(key)
        if data is None:
            continue
        if isinstance(data, list):
            # Keep exact action identities in all retained completed entries.
            result[key] = [{k: (v[:500] + '[excerpt]' if isinstance(v, str) and len(v) > 500 else v)
                            for k, v in item.items()} if isinstance(item, dict) else str(item)[:500]
                           for item in data[-12:]]
        elif isinstance(data, dict):
            result[key] = {k: (v[:1200] + '[excerpt]' if isinstance(v, str) and len(v) > 1200 else v)
                           for k, v in data.items()}
            if key == 'screen' and isinstance(data.get('tool_results'), list):
                result[key]['tool_results'] = [{**item, 'result': str(item.get('result', ''))[:1800]}
                                               for item in data['tool_results'][-4:]]
        elif isinstance(data, str):
            result[key] = data[-2000:]
        compacted.append(key)
    if compacted:
        result['context_compaction'] = {'fields': compacted, 'notice': 'Older observations are excerpts; inspect fresh state before acting.'}
    return result
