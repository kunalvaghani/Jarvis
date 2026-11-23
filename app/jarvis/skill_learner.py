"""Skill learner: point Jarvis at a folder or archive; it inspects, integrates, tests and reports by itself.

"learn the skills in D:\\Downloads\\pdf-tools", "integrate this folder: <path>", "install skills from <path>.zip".

1. **Stage.** The source is copied (a folder) or safely extracted (.zip, .tar, .tar.gz, .tgz) into Jarvis's own
   staging folder; the user's original is never changed. Archive paths, links, sizes and entry counts are checked
   (no path escapes, no symlinks, at most ``MAX_FILES`` files and ``MAX_BYTES`` bytes). Secret-looking files
   (.env, keys, credentials) are never copied anywhere.
2. **Understand.** An inventory finds, at any depth: Agent Skills (``SKILL.md``), MCP tool servers (Python using
   the MCP SDK), and code (manifests and source files). Nothing found is executed at this point.
3. **Integrate** each kind through the module that already owns it:
   - skills -> converted to Jarvis's guide format (``SkillMemory``: name = folder, one-line description, at most
     8,000 bytes; a longer guide is condensed and the original kept under ``references/``), installed atomically
     in ``custom-skills/``, reloaded, and *tested*: the guide must load without error and a request built from its
     description must select it. Guidance is text: no approval.
   - MCP servers -> copied to ``integrations/learned/<name>/``; one approval card covers creating its own virtual
     environment with its declared packages and starting it once; its ``tools/list`` is read; it is registered in
     ``.jarvis/mcp.json`` (enabled, trusted, exact tool allowlist), where the brain's registry picks its tools up as
     neurons. Every later tool call keeps the existing per-call approval of ``mcp_bridge``.
   - code -> ``RepoLearner.learn_archive`` (read as text, saved to memory and Obsidian); the ability forge
     (``repo_abilities``) then proposes spoken commands, each waiting for approval as before.
4. **Report.** What Jarvis can now do, what was skipped and why, as an Island card, a memory note and the answer.

Every step is journalled in ``.jarvis-runtime/skill-learning/<id>/report.json`` before it acts; re-learning the
same content (same SHA-256) returns the earlier report instead of integrating twice. Every loop is bounded and
nothing is retried after an uncertain step. Source text is data, never instructions.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import zipfile

APP = Path(__file__).resolve().parents[1]
STAGING = APP / '.jarvis-runtime' / 'skill-learning'
CUSTOM = APP / 'custom-skills'
LEARNED_SERVERS = APP / 'integrations' / 'learned'
MAX_FILES = 20_000
MAX_BYTES = 300 * 1024 * 1024
MAX_FILE = 50 * 1024 * 1024
GUIDE_LIMIT = 8000
SKIP_DIRS = frozenset({'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'env', '.mypy_cache', '.pytest_cache',
                       '.idea', '.vscode', 'dist', 'build', '.tox'})
SECRET_NAMES = re.compile(r'(?i)(?:^\.env(?:\..*)?$|\.pem$|\.key$|\.p12$|\.pfx$|id_rsa|id_ed25519|credentials?\.json$|'
                          r'secrets?\.(?:json|ya?ml|toml)$|token\.json$|\.keystore$)')
ARCHIVES = ('.zip', '.tar', '.tar.gz', '.tgz')
MCP_PY = re.compile(r'^\s*(?:from\s+mcp(?:\.[\w.]+)?\s+import\b|import\s+mcp\b)|FastMCP\s*\(|@\w+\.tool\s*\(', re.M)
CONNECTOR_PY = re.compile(r'^\s*from\s+jarvis_connector\s+import\b.*\bBaseConnector\b', re.M)  # Jarvis's own framework
RAW_STDIO = re.compile(r'["\']tools/list["\']')
CODE_SUFFIXES = frozenset({'.py', '.js', '.ts', '.go', '.rs', '.java', '.cs', '.rb', '.php', '.cpp', '.c', '.ps1'})
MANIFESTS = frozenset({'pyproject.toml', 'setup.py', 'setup.cfg', 'requirements.txt', 'package.json', 'Cargo.toml',
                       'go.mod'})
LEARN = re.compile(r'^\s*(?:please\s+)?(?:learn|integrate|import|install|add|load|absorb|study)\b'
                   r'(?:\s+(?:the|all|these|this|my|new))*\s*(?:skills?|tools?|connectors?|plugins?|folder|'
                   r'archive|zip|package|repo(?:sitory)?|code|abilit(?:y|ies))?\b[^:"“]*?'
                   r'(?:\s+(?:from|in|at|inside)\s+|:\s*|\s+)["“]?(?P<path>(?:[A-Za-z]:[\\/]|\\\\|/)[^"”\n]+?)["”]?'
                   r'\s*[.!]?\s*$', re.I)


class SkillLearningError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def learned_servers() -> List[Dict[str, Any]]:
    """Tool servers the learner integrated: name and their tools' descriptions (from their companion guides)."""
    rows = []
    for marker in CUSTOM.glob('*/.learned_from'):
        try:
            data = json.loads(marker.read_text(encoding='utf-8'))
            if not data.get('companion'):
                continue
            guide = (marker.parent / 'SKILL.md').read_text(encoding='utf-8')
        except (OSError, ValueError):
            continue
        described = re.search(r'(?m)^description: (.+)$', guide)
        rows.append({'server': str(data.get('server', '')), 'description': described[1] if described else ''})
    return rows


STOP = frozenset('the and for with from this that what into use using my please can you could would tools tool '
                 'server degrees'.split())


def tool_request(text: str) -> bool:
    """The request names a learned tool server, or asks for what one of its tools does (2+ shared content words)."""
    words = {w for w in re.findall(r'[a-z]{4,}', (text or '').lower()) if w not in STOP}
    for row in learned_servers():
        name_words = {w for w in re.findall(r'[a-z]{4,}', row['server'].lower()) if w not in ('connector', 'server')}
        if name_words and name_words <= words:
            return True
        if len(words & {w for w in re.findall(r'[a-z]{4,}', row['description'].lower()) if w not in STOP}) >= 2:
            return True
    return False


def parse_command(text: str) -> Optional[Any]:
    """A request to learn a local folder or archive becomes a task the skill learner's route handles; so does a
    request for a learned tool server (the planner then uses its guide and mcp_call)."""
    from .commands import Command
    if UNLEARN.match(text or '') and learned_runs(UNLEARN.match(text or '').group('label').strip()):  # type: ignore[union-attr]
        return Command('task', text.strip(), 'skill_unlearn')
    found = LEARN.match(text or '')
    if not found:
        return Command('task', text.strip(), 'learned_tool') if tool_request(text) else None
    path = Path(found.group('path').strip().rstrip('.'))
    if not path.exists() or not (path.is_dir() or path.name.lower().endswith(ARCHIVES)):
        return None
    return Command('task', text.strip(), 'skill_learn')


def source_path(goal: str) -> Optional[Path]:
    found = LEARN.match(goal or '')
    if not found:
        return None
    path = Path(found.group('path').strip().rstrip('.'))
    return path if path.exists() else None


def slug(value: str, limit: int = 64) -> str:
    text = re.sub(r'[^a-z0-9]+', '-', str(value).lower()).strip('-')
    return (text or 'learned')[:limit].strip('-') or 'learned'


# ---- 1. Stage ------------------------------------------------------------------------------------------------------
def _safe_member(name: str) -> Optional[PurePosixPath]:
    """An archive member path that stays inside the destination (no absolute paths, drives or '..')."""
    path = PurePosixPath(name.replace('\\', '/'))
    if not name or path.is_absolute() or re.match(r'^[A-Za-z]:', name) or any(p in ('..', '') for p in path.parts):
        return None
    return path


def _skip(parts: Tuple[str, ...]) -> bool:
    return any(p in SKIP_DIRS for p in parts[:-1]) or bool(SECRET_NAMES.search(parts[-1]))


def stage(source: Path, target: Path) -> Dict[str, Any]:
    """Copy or extract ``source`` into ``target`` with bounds. Returns counts and what was left out."""
    if target.exists():
        shutil.rmtree(target)  # Jarvis's own staging folder only
    target.mkdir(parents=True)
    count, total, left_out = 0, 0, []

    def admit(rel: PurePosixPath, size: int) -> bool:
        nonlocal count, total
        if _skip(rel.parts):
            left_out.append(f'{rel} (secret or build folder)')
            return False
        if size > MAX_FILE:
            left_out.append(f'{rel} (larger than {MAX_FILE // 2**20} MB)')
            return False
        count += 1
        total += size
        if count > MAX_FILES or total > MAX_BYTES:
            raise SkillLearningError(f'The source is too large (over {MAX_FILES} files or {MAX_BYTES // 2**20} MB).')
        return True

    name = source.name.lower()
    if source.is_dir():
        for here, dirs, files in os.walk(source, followlinks=False):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not Path(here, d).is_symlink()]
            for file in files:
                path = Path(here, file)
                if path.is_symlink():
                    left_out.append(f'{path.relative_to(source)} (link)')
                    continue
                rel = PurePosixPath(path.relative_to(source).as_posix())
                if admit(rel, path.stat().st_size):
                    out = target.joinpath(*rel.parts)
                    out.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, out)
    elif name.endswith('.zip'):
        with zipfile.ZipFile(source) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                inner = _safe_member(info.filename)
                if inner is None or (info.external_attr >> 16) & 0o170000 == 0o120000:
                    left_out.append(f'{info.filename} (unsafe path or link)')
                    continue
                if admit(inner, info.file_size):
                    out = target.joinpath(*inner.parts)
                    out.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info) as data, open(out, 'wb') as handle:
                        shutil.copyfileobj(data, handle, 1 << 20)
    elif name.endswith(('.tar', '.tar.gz', '.tgz')):
        with tarfile.open(source) as tarball:
            for member in tarball.getmembers():
                if not member.isfile():
                    if member.issym() or member.islnk():
                        left_out.append(f'{member.name} (link)')
                    continue
                member_path = _safe_member(member.name)
                if member_path is None:
                    left_out.append(f'{member.name} (unsafe path)')
                    continue
                if admit(member_path, member.size):
                    stream = tarball.extractfile(member)
                    if stream is None:
                        continue
                    out = target.joinpath(*member_path.parts)
                    out.parent.mkdir(parents=True, exist_ok=True)
                    with stream, open(out, 'wb') as handle:
                        shutil.copyfileobj(stream, handle, 1 << 20)
    else:
        raise SkillLearningError('Give a folder or a .zip, .tar, .tar.gz or .tgz archive.')
    top = target
    children = [c for c in target.iterdir()]
    if len(children) == 1 and children[0].is_dir():  # an archive with one top folder
        top = children[0]
    return {'files': count, 'bytes': total, 'left_out': left_out[:50], 'root': str(top)}


def content_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob('*') if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode('utf-8'))
        with open(path, 'rb') as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b''):
                digest.update(chunk)
    return digest.hexdigest()


# ---- 2. Understand -------------------------------------------------------------------------------------------------
def inventory(root: Path) -> Dict[str, Any]:
    """What the source contains, read as text only."""
    skills: List[str] = []
    servers: List[Dict[str, Any]] = []
    code_files, manifests, docs = 0, [], 0
    skill_roots = [p.parent for p in root.rglob('SKILL.md') if p.parent != root]
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if path.name == 'SKILL.md':
            skills.append(rel)
            continue
        if path.name in MANIFESTS:
            manifests.append(rel)
        suffix = path.suffix.lower()
        if suffix in CODE_SUFFIXES and not any(parent in skill_roots for parent in path.parents):
            code_files += 1  # a skill's own scripts belong to the skill
        if suffix in ('.md', '.txt', '.rst'):
            docs += 1
        if suffix == '.py' and path.stat().st_size <= 400_000:
            text = path.read_text(encoding='utf-8', errors='replace')
            runs = re.search(r'(?m)^if __name__ == .__main__.:', text) is not None
            kind = ('connector' if CONNECTOR_PY.search(text) and runs else
                    'sdk' if MCP_PY.search(text) and re.search(r'\bmcp\b', text) and (runs or '.run(' in text) else
                    'stdio' if RAW_STDIO.search(text) and 'jsonrpc' in text and 'stdin' in text and runs else '')
            if kind:
                servers.append({'entry': rel, 'kind': kind,
                                'tools_hint': sorted(set(re.findall(r'def (\w+)\(', text)))[:40]})
    # A skill's own scripts are part of the skill, not separate code to learn.
    skill_dirs = {str(PurePosixPath(s).parent) for s in skills}
    def in_skills(rel: str) -> bool:
        return any(rel == d or rel.startswith(d + '/') for d in skill_dirs if d != '.')
    servers = [s for s in servers if not in_skills(str(s['entry']))]
    return {'skills': skills, 'servers': servers[:5], 'code_files': code_files, 'manifests': manifests[:20],
            'docs': docs, 'is_skill_pack': bool(skills) and '.' in skill_dirs and len(skills) == 1}


# ---- 3a. Skills ----------------------------------------------------------------------------------------------------
def frontmatter(text: str) -> Tuple[Dict[str, str], str]:
    """YAML-style front matter (name/description/...; folded and literal blocks, quotes) and the body after it."""
    text = text.replace('\r\n', '\n').replace('\r', '\n').lstrip('﻿')
    meta: Dict[str, str] = {}
    if not text.startswith('---\n'):
        return meta, text
    end = text.find('\n---', 4)
    if end < 0:
        return meta, text
    head, body = text[4:end], text[end + 4:].lstrip('\n')
    key: Optional[str] = None
    block: List[str] = []
    for line in head.split('\n'):
        top = re.match(r'^([A-Za-z_][\w-]*)\s*:\s*(.*)$', line)
        if top and not line.startswith((' ', '\t')):
            if key is not None and block:
                meta[key] = ' '.join(b.strip() for b in block if b.strip())
            key, value, block = top.group(1).lower(), top.group(2).strip(), []
            if value in ('>', '|', '>-', '|-', '>+', '|+', ''):
                continue
            meta[key] = value.strip('"\'')
            key = None
        elif key is not None:
            block.append(line)
    if key is not None and block:
        meta[key] = ' '.join(b.strip() for b in block if b.strip())
    return meta, body


def condense(body: str, budget: int) -> str:
    """Headings and the first paragraph of each section, in order, within ``budget`` bytes."""
    out: List[str] = []
    used = 0
    for section in re.split(r'(?m)^(?=#{1,6} )', body):
        lines = section.strip().split('\n')
        if not lines or not lines[0]:
            continue
        head = lines[0] if lines[0].startswith('#') else ''
        rest = '\n'.join(lines[1:] if head else lines).strip()
        first = rest.split('\n\n')[0].strip() if rest else ''
        piece = '\n'.join(x for x in (head, first) if x) + '\n\n'
        size = len(piece.encode('utf-8'))
        if used + size > budget:
            break
        out.append(piece)
        used += size
    return ''.join(out).strip()


def jarvis_guide(name: str, description: str, body: str) -> Tuple[str, bool]:
    """A SKILL.md that SkillMemory loads: matching name, one-line description, at most GUIDE_LIMIT bytes."""
    head = f'---\nname: {name}\ndescription: {description}\n---\n\n'
    guide = head + body.strip() + '\n'
    if len(guide.encode('utf-8')) <= GUIDE_LIMIT:
        return guide, False
    note = ('\n\n> Condensed by Jarvis to fit its 8,000-byte guide limit. The full original guide is '
            '`references/ORIGINAL_SKILL.md` in this skill\'s folder.\n')
    budget = GUIDE_LIMIT - len(head.encode('utf-8')) - len(note.encode('utf-8')) - 64
    return head + condense(body, budget) + note, True


def taken_names(actions: Any) -> Set[str]:
    skills = getattr(actions, 'skills', None)
    names = {str(row.get('name')) for row in getattr(skills, 'catalog', []) or []}
    names |= {p.name for p in CUSTOM.glob('*') if p.is_dir()}
    names |= {p.name for p in (APP / 'skills').glob('*') if p.is_dir()}
    return names


def install_skill(actions: Any, skill_file: Path, taken: Set[str], source_label: str) -> Dict[str, Any]:
    """Convert one skill folder and install it in custom-skills/ atomically. Returns the installed record."""
    from .obsidian_memory import SENSITIVE
    raw = skill_file.read_text(encoding='utf-8', errors='replace')
    meta, body = frontmatter(raw)
    if SENSITIVE.search(raw):
        raise SkillLearningError('it contains something that looks like a password or key; not installed')
    original = hashlib.sha256(raw.encode('utf-8')).hexdigest()
    for marker in CUSTOM.glob('*/.learned_from'):  # the same guide installed before: reuse it, never duplicate
        try:
            if json.loads(marker.read_text(encoding='utf-8')).get('sha256') == original:
                installed = marker.parent
                described = re.search(r'(?m)^description: (.+)$', (installed / 'SKILL.md').read_text(encoding='utf-8'))
                return {'name': installed.name, 'description': described[1] if described else '', 'files': 0,
                        'condensed': (installed / 'references' / 'ORIGINAL_SKILL.md').is_file(), 'renamed_from': '',
                        'already_installed': True}
        except (OSError, ValueError):
            continue
    name = slug(meta.get('name') or skill_file.parent.name)
    base, n = name, 2
    while name in taken:
        name = f'{base[:58]}-{n}'
        n += 1
    description = ' '.join(str(meta.get('description', '')).split())
    if not description:
        first = next((line.strip() for line in body.split('\n') if line.strip() and not line.startswith('#')), '')
        description = first or f'Guide learned from {source_label}.'
    description = description[:1000]
    guide, condensed = jarvis_guide(name, description, body)
    CUSTOM.mkdir(parents=True, exist_ok=True)
    tmp = CUSTOM / f'.incoming-{name}'
    final = CUSTOM / name
    if tmp.exists():
        shutil.rmtree(tmp)  # an unfinished earlier attempt of Jarvis's own
    folder = skill_file.parent
    copied = 0
    for path in sorted(folder.rglob('*')):  # the skill's own scripts, references and assets
        if not path.is_file() or path == skill_file or _skip(path.relative_to(folder).parts) or copied >= 300:
            continue
        out = tmp / path.relative_to(folder)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, out)
        copied += 1
    tmp.mkdir(parents=True, exist_ok=True)
    if condensed or meta.get('name') != name:
        (tmp / 'references').mkdir(exist_ok=True)
        (tmp / 'references' / 'ORIGINAL_SKILL.md').write_text(raw, encoding='utf-8')
    (tmp / 'SKILL.md').write_text(guide, encoding='utf-8')
    (tmp / '.learned_from').write_text(json.dumps({'source': source_label, 'original_name': meta.get('name', ''),
                                                   'sha256': original, 'at': utc_now()}), encoding='utf-8')
    tmp.replace(final)
    taken.add(name)
    return {'name': name, 'description': description, 'condensed': condensed, 'files': copied + 1,
            'renamed_from': meta.get('name') if meta.get('name') and meta.get('name') != name else ''}


def verify_skill(actions: Any, record: Dict[str, Any]) -> Tuple[bool, str]:
    """Loaded by SkillMemory without error, and selected for a request built from its own description."""
    skills = getattr(actions, 'skills', None)
    if skills is None:
        return False, 'no skill memory in this Jarvis'
    skills._guide_stamp = None  # force a reload now
    skills.refresh()
    loaded = next((row for row in skills.catalog if row.get('name') == record['name'] and row.get('origin') == 'Custom'),
                  None)
    if loaded is None:
        error = next((e for e in skills.skill_errors if e.startswith(record['name'] + ':')), 'not loaded')
        return False, error
    if not getattr(skills.memory, 'enabled', False):
        return True, 'loaded (selection not tested: memory is off)'
    picked = [s.get('name') for s in (skills.context(record['description']) or {}).get('skills', [])]
    if record['name'] in picked:
        return True, 'loaded and selected for its kind of request'
    named = [s.get('name') for s in (skills.context(record['description'] + ' $custom:' + record['name']) or {})
             .get('skills', [])]
    if record['name'] in named:
        return True, 'loaded; selected when named ($custom:' + record['name'] + ')'
    return False, 'loaded but never selected'


# ---- 3b. MCP tool servers ------------------------------------------------------------------------------------------
def server_packages(folder: Path, entry: Path) -> List[str]:
    """Packages the server declares (requirements.txt, pyproject dependencies), plus the MCP SDK it imports."""
    found: List[str] = []
    for req in (folder / 'requirements.txt', entry.parent / 'requirements.txt'):
        if req.is_file():
            for line in req.read_text(encoding='utf-8', errors='replace').splitlines():
                line = line.split('#')[0].strip()
                if line and not line.startswith(('-', 'git+', 'http://', 'https://')) and re.fullmatch(r'[A-Za-z0-9_.\-\[\],<>=!~ ]{1,120}', line):
                    found.append(line)
    pyproject = folder / 'pyproject.toml'
    if pyproject.is_file():
        try:
            import importlib
            data = importlib.import_module('tomllib').loads(pyproject.read_text(encoding='utf-8', errors='replace'))
            for dep in (data.get('project') or {}).get('dependencies', []) or []:
                if isinstance(dep, str) and re.fullmatch(r'[A-Za-z0-9_.\-\[\],<>=!~ ;"\']{1,160}', dep):
                    found.append(dep.split(';')[0].strip())
        except (ValueError, OSError):
            pass
    if not any(re.match(r'(?i)^mcp\b', p) for p in found):
        found.append('mcp')
    return list(dict.fromkeys(found))[:40]


def base_python() -> str:
    import sys
    return str(getattr(sys, '_base_executable', '') or sys.executable)


def build_environment(folder: Path, packages: List[str], cancelled: Callable[[], bool]) -> Path:
    """The server's own virtual environment (never Jarvis's), with its packages installed from binary wheels."""
    import subprocess
    venv = folder / '.venv'
    python = venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.is_file():
        subprocess.run([base_python(), '-m', 'venv', str(venv)], check=True, capture_output=True, timeout=300,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if cancelled():
        raise SkillLearningError('cancelled before installing packages')
    done = subprocess.run([str(python), '-m', 'pip', 'install', '--disable-pip-version-check', '--only-binary=:all:',
                           *packages], capture_output=True, text=True, timeout=900,
                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if done.returncode != 0:
        tail = ' '.join((done.stderr or done.stdout or '').split())[-300:]
        raise SkillLearningError('its packages did not install: ' + tail)
    return python


def mcp_config_path() -> Path:
    return APP / '.jarvis' / 'mcp.json'


def register_server(name: str, config: Dict[str, Any]) -> None:
    """Add the server to .jarvis/mcp.json (kept as a dated backup first), atomically."""
    path = mcp_config_path()
    data = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {'servers': {}}
    servers = data.setdefault('servers', {})
    if name not in servers and len(servers) >= 20:
        raise SkillLearningError('Jarvis already has 20 tool servers configured (its limit)')
    if path.is_file():
        backup = path.with_name(f'mcp.json.{time.strftime("%Y%m%d-%H%M%S")}.bak')
        shutil.copy2(path, backup)
    servers[name] = config
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def integrate_server(actions: Any, root: Path, server: Dict[str, Any], name: str,
                     cancelled: Callable[[], bool]) -> Dict[str, Any]:
    """Copy, approve once, give it its own environment, list its tools, register it."""
    from .mcp_bridge import StdioClient
    import sys
    entry_rel = PurePosixPath(server['entry'])
    kind = server.get('kind', 'sdk')
    source_folder = root / entry_rel.parent if str(entry_rel.parent) != '.' else root
    if kind == 'sdk' and not any(source_folder.glob('*.toml')) and not (source_folder / 'requirements.txt').exists() \
            and source_folder != root:
        source_folder = root  # the server's manifests sit at the top
    # Jarvis connectors live beside the YouTube/Spotify ones (they find their framework two folders up).
    dest = (APP / 'integrations' / 'jarvis-connectors' / 'connectors' / 'apps' / name if kind == 'connector'
            else LEARNED_SERVERS / name)
    packages = server_packages(source_folder, root / entry_rel) if kind == 'sdk' else []
    approve = getattr(actions, '_approve', None)
    if approve is None:
        raise SkillLearningError('no approval channel; open the Jarvis app')
    setup = (f'install {", ".join(packages[:8])}{" and more" if len(packages) > 8 else ""} into its own separate '
             'environment, then ' if packages else '')
    approve('skill learner', f'Set up the tool server "{name}" from your folder: {setup}start it once to list its '
            'tools. Jarvis\'s own environment is not changed.', cancelled)  # raises when declined
    if dest.exists():
        shutil.rmtree(dest)  # Jarvis's own earlier copy
    shutil.copytree(source_folder, dest, ignore=shutil.ignore_patterns(*SKIP_DIRS))
    inside = PurePosixPath((root / entry_rel).relative_to(source_folder).as_posix())
    entry = dest.joinpath(*inside.parts)
    python = build_environment(dest, packages, cancelled) if packages else Path(sys.executable)
    args = [str(entry)] + (['--runtime', 'builtin'] if kind == 'connector' else [])
    probe = {'enabled': True, 'trusted': True, 'command': str(python), 'args': args,
             'allow_tools': ['__list_only__'], 'timeout_seconds': 45}
    client = StdioClient(probe, APP, cancelled)
    try:
        client.initialize()
        tools = [t for t in client.tools() if isinstance(t, dict) and isinstance(t.get('name'), str)]
    finally:
        client.close()
    if not tools:
        raise SkillLearningError('it started but offers no tools')
    names = [t['name'] for t in tools][:100]
    register_server(name, {**probe, 'allow_tools': names, 'timeout_seconds': 30,
                           'learned_from': server['entry']})
    return {'name': name, 'kind': kind, 'folder': str(dest), 'packages': packages,
            'tools': [{'name': t['name'], 'description': ' '.join(str(t.get('description', '')).split())[:200],
                       'arguments': arguments_of(t)} for t in tools[:30]]}


def arguments_of(tool: Dict[str, Any]) -> Dict[str, str]:
    """{argument: 'type, required: description'} from a tool's input schema."""
    found = tool.get('inputSchema')
    schema: Dict[str, Any] = found if isinstance(found, dict) else {}
    required = set(schema.get('required') or [])
    out: Dict[str, str] = {}
    for key, spec in list((schema.get('properties') or {}).items())[:12]:
        if isinstance(spec, dict):
            kind = str(spec.get('type', 'value'))
            text = ' '.join(str(spec.get('description', '')).split())[:120]
            out[str(key)] = f'{kind}{", required" if key in required else ""}{": " + text if text else ""}'
    return out


def companion_skill(actions: Any, server: Dict[str, Any], taken: Set[str]) -> Dict[str, Any]:
    """A guide for the new server, so a spoken request selects it and the planner knows the exact mcp_call."""
    tools = server['tools']
    name = slug(server['name'] + '-tools')
    words = '; '.join(t['description'].rstrip('.') or t['name'].replace('_', ' ') for t in tools)[:700]
    description = f'Use the {server["name"]} tools: {words}.'
    lines = [f'# {server["name"]} tools', '',
             f'These tools run on the trusted MCP server `{server["name"]}` (learned from a folder the user gave). '
             'Call them with the `mcp_call` tool: value is the server name, content is JSON with the tool name and an '
             'arguments object. Every call asks the user first; never retry a call whose result is uncertain.', '']
    for tool in tools:
        example = {k: ('<' + k + '>') for k in tool['arguments']}
        lines += [f'## {tool["name"]}', '', tool['description'] or '(no description)', '']
        lines += [f'- `{k}`: {v}' for k, v in tool['arguments'].items()]
        lines += ['', 'Call: `mcp_call` value `' + server['name'] + '`, content `' +
                  json.dumps({'name': tool['name'], 'arguments': example}) + '`', '']
    guide, _ = jarvis_guide(name, description, '\n'.join(lines))
    guide = guide.replace('\n---\n', '\ntools: [mcp_call]\n---\n', 1)  # the binding SkillMemory declares
    CUSTOM.mkdir(parents=True, exist_ok=True)
    folder = CUSTOM / name
    tmp = CUSTOM / f'.incoming-{name}'
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    (tmp / 'SKILL.md').write_text(guide, encoding='utf-8')
    (tmp / '.learned_from').write_text(json.dumps({'server': server['name'], 'companion': True, 'at': utc_now()}),
                                       encoding='utf-8')
    if folder.exists():
        shutil.rmtree(folder)  # Jarvis's own earlier companion for this server
    tmp.replace(folder)
    taken.add(name)
    return {'name': name, 'description': description, 'condensed': False, 'files': 1, 'renamed_from': '',
            'companion_of': server['name']}


# ---- 3c. Code ------------------------------------------------------------------------------------------------------
def zip_source(root: Path, limit: int = 38_000_000) -> bytes:
    """The staged source as an in-memory zip with one top folder, as RepoLearner reads a GitHub download."""
    buffer = io.BytesIO()
    total = 0
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob('*')):
            if not path.is_file():
                continue
            size = path.stat().st_size
            if size > 400_000 or total + size > limit:
                continue
            archive.write(path, root.name + '/' + path.relative_to(root).as_posix())
            total += size
    return buffer.getvalue()


def learn_code(actions: Any, root: Path, label: str, digest: str, cancelled: Callable[[], bool],
               origin: Optional[Path] = None) -> Dict[str, Any]:
    learner = getattr(actions, 'repo_learner', None)
    if learner is None or not getattr(learner, 'enabled', True):
        raise SkillLearningError('repository learning is off in this Jarvis')
    full_name = 'local/' + slug(label, 90)
    readme = next((p for p in root.glob('*') if re.fullmatch(r'(?i)readme(\.\w+)?', p.name)), None)
    description = ''
    if readme is not None:
        description = next((line.strip('# ').strip() for line in readme.read_text(encoding='utf-8', errors='replace')
                            .splitlines() if line.strip().strip('#').strip()), '')[:300]
    forge = getattr(actions, 'ability_forge', None)
    if forge is not None:
        forge.wanted.add(full_name.casefold())  # build abilities from it now (each still waits for approval)
    row = learner.learn_archive(full_name, zip_source(root), {
        'full_name': full_name, 'html_url': (origin or root).resolve().as_uri(), 'description': description,
        'commit': digest[:40],
        'stargazers_count': 0, 'topics': [], 'license': {}}, reason='folder you gave me', cancelled=cancelled)
    return {'name': full_name, 'purpose': row.get('purpose', ''), 'use_when': row.get('use_when', '')}


# ---- 4. The whole run, journalled ----------------------------------------------------------------------------------
DEADLINE_S = 1800


class Journal:
    """report.json in the run's staging folder, written before every step that changes anything."""

    def __init__(self, folder: Path, data: Dict[str, Any]) -> None:
        self.path, self.data = folder / 'report.json', data

    def step(self, what: str, **fields: Any) -> None:
        self.data.setdefault('steps', []).append({'step': what, 'at': utc_now(), **fields})
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.data, indent=1, default=str), encoding='utf-8')
        tmp.replace(self.path)


def notify(actions: Any, phase: str, title: str, subtitle: str = '', detail: str = '') -> None:
    try:
        from .media_player import card
        actions.report('media_card', card('skills', phase, title, subtitle, '', 0, 0, detail))
    except Exception:
        pass


def previous_run(digest: str) -> Optional[Dict[str, Any]]:
    for report in STAGING.glob('*/report.json'):
        try:
            data = json.loads(report.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        complete = not data.get('problems') and (data.get('skills') or data.get('servers') or data.get('code')) \
            if isinstance(data, dict) else False
        if isinstance(data, dict) and data.get('sha256') == digest and data.get('state') == 'done' and complete:
            return dict(data)  # a declined or failed run is not "learned": the user may try again
    return None


def learn(actions: Any, source: Path, cancelled: Callable[[], bool] = lambda: False) -> Dict[str, Any]:
    """Learn everything usable in ``source``. Returns the report (also journalled and announced)."""
    started = time.monotonic()
    label = source.name[:-len(next(s for s in ARCHIVES if source.name.lower().endswith(s)))] \
        if source.name.lower().endswith(ARCHIVES) else source.name
    run_id = time.strftime('%Y%m%d-%H%M%S') + '-' + os.urandom(3).hex() + '-' + slug(label, 40)
    folder = STAGING / run_id
    journal = Journal(folder, {'source': str(source), 'label': label, 'started': utc_now(), 'state': 'staging',
                               'skills': [], 'servers': [], 'code': None, 'problems': []})
    journal.save()
    notify(actions, 'learning', f'Learning {label}', 'Checking the folder', 'staging')
    staged = stage(source, folder / 'source')
    root = Path(staged['root'])
    digest = content_hash(root)
    journal.data.update(sha256=digest, staged=staged)
    earlier = previous_run(digest)
    if earlier is not None:
        journal.data.update(state='done', same_as=earlier.get('started'))
        journal.step('skipped', reason='this exact content was learned before')
        shutil.rmtree(folder / 'source', ignore_errors=True)
        return {**earlier, 'repeat': True}
    found = inventory(root)
    journal.data['inventory'] = found
    journal.step('inventory', skills=len(found['skills']), servers=len(found['servers']), code=found['code_files'])

    def out_of_time() -> bool:
        return cancelled() or time.monotonic() - started > DEADLINE_S

    taken = taken_names(actions)
    for rel in found['skills'][:50]:
        if out_of_time():
            journal.data['problems'].append('stopped at the time limit before every skill was installed')
            break
        notify(actions, 'learning', f'Learning {label}', f'Skill: {PurePosixPath(rel).parent.name or label}', 'skills')
        try:
            journal.step('install_skill', file=rel)
            record = install_skill(actions, root / rel, taken, str(source))
            ok, how = verify_skill(actions, record)
            record.update(verified=ok, check=how)
            if not ok and not record.get('already_installed'):
                shutil.rmtree(CUSTOM / record['name'], ignore_errors=True)  # never leave a guide that does not load
                journal.data['problems'].append(f'{record["name"]}: {how}; removed again')
            else:
                journal.data['skills'].append(record)
        except (SkillLearningError, OSError, UnicodeError) as error:
            journal.data['problems'].append(f'{rel}: {error}')
        journal.save()

    for server in found['servers']:
        if out_of_time():
            journal.data['problems'].append('stopped at the time limit before the tool server was set up')
            break
        name = slug(label if len(found['servers']) == 1 else f'{label}-{PurePosixPath(server["entry"]).stem}', 50)
        notify(actions, 'learning', f'Learning {label}', f'Tool server: {name}', 'approval needed')
        try:
            journal.step('integrate_server', entry=server['entry'], name=name)
            integrated = integrate_server(actions, root, server, name, cancelled)
            journal.data['servers'].append(integrated)
            journal.step('companion_skill', server=name)
            guide = companion_skill(actions, integrated, taken)
            ok, how = verify_skill(actions, guide)
            guide.update(verified=ok, check=how)
            if ok:
                journal.data['skills'].append(guide)
            else:
                journal.data['problems'].append(f'{guide["name"]} (guide for {name}): {how}')
        except Exception as error:  # a declined approval, a failed install or a server that does not start
            journal.data['problems'].append(f'tool server {server["entry"]}: {str(error)[:240]}')
        journal.save()

    plain_code = found['code_files'] > 0 and not found['servers'] and not found.get('is_skill_pack')
    if plain_code and not out_of_time():
        notify(actions, 'learning', f'Learning {label}', 'Understanding the code', 'code')
        try:
            journal.step('learn_code', files=found['code_files'])
            journal.data['code'] = learn_code(actions, root, label, digest, cancelled, source)
        except Exception as error:
            journal.data['problems'].append(f'code: {str(error)[:240]}')
        journal.save()

    journal.data.update(state='done', finished=utc_now(), seconds=round(time.monotonic() - started, 1))
    journal.data['summary'] = summary(journal.data)
    journal.save()
    shutil.rmtree(folder / 'source', ignore_errors=True)  # skills, servers and learned code keep their own copies
    memory = getattr(actions, 'memory', None)
    if memory is not None and hasattr(memory, 'record'):
        try:
            memory.record('Learned skills', f'{label}: ' + journal.data['summary'].split('\n')[0])
        except Exception:
            pass
    learned = len(journal.data['skills']) + len(journal.data['servers']) + bool(journal.data['code'])
    notify(actions, 'learned' if learned else 'failed', f'{"Learned" if learned else "Could not learn"} {label}',
           journal.data['summary'].split('\n')[0][:120], 'done')
    return journal.data


def summary(report: Dict[str, Any]) -> str:
    """What Jarvis can do now, in plain words."""
    lines: List[str] = []
    skills, servers, code = report.get('skills', []), report.get('servers', []), report.get('code')
    parts = []
    own = [s for s in skills if not s.get('companion_of')]
    if own:
        parts.append(f'{len(own)} skill{"s" if len(own) != 1 else ""}')
    if servers:
        tools = sum(len(s['tools']) for s in servers)
        parts.append(f'{len(servers)} tool server{"s" if len(servers) != 1 else ""} with {tools} tools')
    if code:
        parts.append('its code (in memory; new commands being built)')
    lines.append(f'Learned from {report.get("label")}: ' + (', '.join(parts) if parts else 'nothing usable') + '.')
    for skill in skills:
        if skill.get('companion_of'):
            continue  # described with its server below
        extra = ' (condensed; full guide kept)' if skill.get('condensed') else ''
        lines.append(f'- Skill "{skill["name"]}": {skill["description"][:160].rstrip(".")}{extra}. '
                     f'Checked: {skill["check"]}.')
    for server in servers:
        lines.append(f'- Tool server "{server["name"]}" ({len(server["tools"])} tools, each call asks you first; '
                     'ask for it in your own words):')
        lines += [f'    - {t["name"]}: {t["description"] or "(no description)"}' for t in server['tools'][:12]]
    if code:
        lines.append(f'- Code "{code["name"]}": {code["purpose"][:200]}')
        if code.get('use_when'):
            lines.append(f'    Useful when: {code["use_when"][:200]}')
        lines.append('    Jarvis is turning it into spoken commands in the background; each one asks for your approval.')
    if report.get('problems'):
        lines.append('Not learned:')
        lines += [f'- {p}' for p in report['problems'][:10]]
    left = (report.get('staged') or {}).get('left_out') or []
    if left:
        lines.append(f'Left out for safety: {len(left)} file(s), e.g. {left[0]}.')
    return '\n'.join(lines)


UNLEARN = re.compile(r'^\s*(?:please\s+)?(?:forget|unlearn|remove|uninstall)\s+(?:the\s+|all\s+)?(?:skills?|tools?|'
                     r'connectors?|everything|what you learned)\s+(?:you\s+)?(?:learned\s+|learnt\s+|got\s+)?'
                     r'(?:from|of)\s+["“]?(?P<label>[^"”\n]{1,120}?)["”]?\s*[.!]?\s*$', re.I)


def learned_runs(label: str) -> List[Tuple[Path, Dict[str, Any]]]:
    """Finished runs whose source name (or path) matches ``label``, newest first."""
    want = slug(label)
    rows = []
    for report in STAGING.glob('*/report.json'):
        try:
            data = json.loads(report.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get('state') == 'done' and not data.get('forgotten') and \
                want in (slug(str(data.get('label', ''))), slug(Path(str(data.get('source', ''))).name)):
            rows.append((report, data))
    return sorted(rows, key=lambda row: str(row[1].get('started', '')), reverse=True)


def unlearn(actions: Any, label: str, cancelled: Callable[[], bool]) -> str:
    """Remove what one learning run integrated: its skills, tool servers and learned code (after approval)."""
    runs = learned_runs(label)
    if not runs:
        return f'I have not learned anything from "{label}".'
    skills = sorted({s['name'] for _, d in runs for s in d.get('skills', []) if isinstance(s, dict)})
    servers = sorted({s['name'] for _, d in runs for s in d.get('servers', []) if isinstance(s, dict)})
    code = sorted({d['code']['name'] for _, d in runs if isinstance(d.get('code'), dict) and d['code'].get('name')})
    what = ', '.join([f'skills {", ".join(skills)}' if skills else '', f'tool servers {", ".join(servers)}' if servers
                      else '', f'learned code {", ".join(code)}' if code else '']).strip(', ').replace(', ,', ',')
    approve = getattr(actions, '_approve', None)
    if approve is None:
        raise SkillLearningError('no approval channel; open the Jarvis app')
    approve('skill learner', f'Remove what Jarvis learned from "{label}": {what}. Your original folder is not '
            'touched.', cancelled)  # raises when declined
    removed: List[str] = []
    for name in skills:
        folder = CUSTOM / name
        if folder.is_dir() and (folder / '.learned_from').is_file():  # only guides the learner installed
            shutil.rmtree(folder)
            removed.append(f'skill {name}')
    path = mcp_config_path()
    if servers and path.is_file():
        data = json.loads(path.read_text(encoding='utf-8'))
        gone = [n for n in servers if n in data.get('servers', {}) and data['servers'][n].get('learned_from')]
        if gone:
            shutil.copy2(path, path.with_name(f'mcp.json.{time.strftime("%Y%m%d-%H%M%S")}.bak'))
            for name in gone:
                data['servers'].pop(name, None)
            tmp = path.with_suffix('.json.tmp')
            tmp.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
            tmp.replace(path)
        for _, d in runs:
            for server in d.get('servers', []):
                folder = Path(str(server.get('folder', '')))
                inside = any(str(folder).startswith(str(base)) for base in
                             (LEARNED_SERVERS, APP / 'integrations' / 'jarvis-connectors' / 'connectors' / 'apps'))
                if server.get('name') in gone and folder.is_dir() and inside:
                    shutil.rmtree(folder)
        removed += [f'tool server {n}' for n in gone]
    learner = getattr(actions, 'repo_learner', None)
    forge = getattr(actions, 'ability_forge', None)
    for name in code:
        if forge is not None and name in forge.registry.get('repos', {}):
            forge.registry['repos'][name] = {'state': 'forgotten', 'at': utc_now(), 'abilities': []}
            forge.wanted.discard(name.casefold())
            forge._save()  # no build resumes for it
        if learner is not None and name in learner.index:
            from .repo_learning import repo_id
            learner.index.pop(name, None)
            learner._save_index()
            shutil.rmtree(learner.cache / repo_id(name), ignore_errors=True)
            note = learner.vault / (repo_id(name) + '.md')
            if note.is_file():
                note.unlink()
        removed.append(f'learned code {name}')
    for report, data in runs:
        data.update(forgotten=utc_now(), removed=removed)
        report.write_text(json.dumps(data, indent=1, default=str), encoding='utf-8')
    taken = getattr(actions, 'skills', None)
    if taken is not None:
        taken._guide_stamp = None
        taken.refresh()
    notify(actions, 'learned', f'Forgot {label}', ', '.join(removed)[:120] or 'nothing to remove', 'removed')
    return ('Finished: removed ' + (', '.join(removed) if removed else 'nothing (it was already gone)') +
            f'. Your original "{label}" was not touched.')


def server_tools(server: str) -> List[Dict[str, Any]]:
    """The tools (name, description, arguments) the learner recorded for a server it integrated."""
    newest: List[Dict[str, Any]] = []
    for report in sorted(STAGING.glob('*/report.json')):
        try:
            data = json.loads(report.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        for row in data.get('servers', []) if isinstance(data, dict) else []:
            if isinstance(row, dict) and row.get('name') == server:
                newest = [t for t in row.get('tools', []) if isinstance(t, dict)]
    return newest


def coerce(value: Any, kind: str) -> Any:
    try:
        if kind.startswith('integer'):
            return int(float(value))
        if kind.startswith('number'):
            return float(value)
        if kind.startswith('boolean'):
            return value if isinstance(value, bool) else str(value).lower() in ('true', 'yes', '1')
    except (TypeError, ValueError):
        return value
    return value


def use_learned_tool(actions: Any, goal: str, cancelled: Callable[[], bool]) -> Optional[str]:
    """A request for a learned tool server: pick the tool and arguments, call it (approved), answer from its result."""
    from .fast_routes import grounded
    from .mcp_bridge import configurations, execute
    words = {w for w in re.findall(r'[a-z]{4,}', goal.lower()) if w not in STOP}
    best: Tuple[int, str] = (0, '')
    for row in learned_servers():
        text = row['server'] + ' ' + row['description']
        score = len(words & {w for w in re.findall(r'[a-z]{4,}', text.lower()) if w not in STOP})
        best = max(best, (score, row['server']))
    server = best[1]
    config = configurations(Path(getattr(actions, 'base', APP))).get(server) if server else None
    tools = [t for t in server_tools(server) if t.get('name') in (config or {}).get('allow_tools', [])]
    if not server or not config or not tools:
        return None  # not a learned server request after all: the planner decides
    actions.report('brain', f'Learned tool server: {server}')
    listing = '\n'.join(f'- {t["name"]}: {t.get("description", "")}; arguments: {json.dumps(t.get("arguments", {}))}'
                        for t in tools)
    reply = actions.brain.client.request('tool_text', cancelled, tool='think', context='', goal=(
        'Choose the one tool that does this request and fill in its arguments from the request. Return ONLY JSON '
        '{"tool": "<name>", "arguments": {...}}; numbers as numbers. If no tool fits, return {"tool": ""}.\n'
        f'Request: {goal}\nTools:\n{listing}'))
    text = str(reply.get('text', '') if isinstance(reply, dict) else reply)
    found = re.search(r'\{.*\}', text, re.S)
    try:
        choice = json.loads(found.group(0)) if found else {}
    except ValueError:
        choice = {}
    tool = next((t for t in tools if t['name'] == choice.get('tool')), None) if isinstance(choice, dict) else None
    if tool is None or not isinstance(choice.get('arguments'), dict):
        return None
    kinds = tool.get('arguments', {})
    arguments = {k: coerce(v, str(kinds.get(k, ''))) for k, v in choice['arguments'].items() if k in kinds}
    actions.report('tool', f'mcp_call {server}.{tool["name"]} {json.dumps(arguments)}')
    result = execute(actions, {'action': 'mcp_call', 'value': server,
                               'content': json.dumps({'name': tool['name'], 'arguments': arguments})}, cancelled)
    shown = str(result)
    try:
        data = json.loads(shown)
        payload = (data.get('structuredContent') or {}).get('result') if isinstance(data, dict) else None
        if payload is None and isinstance(data, dict):
            payload = ' '.join(str(c.get('text', '')) for c in data.get('content', []) if isinstance(c, dict))
        if isinstance(data, dict) and data.get('isError'):
            return f'The {server} tool {tool["name"]} reported an error: {str(payload)[:300]}'
        shown = json.dumps(payload) if not isinstance(payload, str) else payload
    except ValueError:
        pass
    phrased = actions.brain.client.request('tool_text', cancelled, tool='think', context='', goal=(
        'Answer the request in one short sentence using ONLY this tool result; copy numbers exactly.\n'
        f'Request: {goal}\nTool {tool["name"]} result: {shown[:2000]}'))
    sentence = ' '.join(str(phrased.get('text', '') if isinstance(phrased, dict) else phrased).split())[:400]
    if sentence and grounded(sentence, shown):
        return f'Finished: {sentence} (from your {server} tool {tool["name"]})'
    return f'Finished: {server} {tool["name"]} returned {shown[:400]}'


def route(actions: Any, goal: str, cancelled: Callable[[], bool]) -> Optional[str]:
    """fast_routes hook: a learn-this-folder request runs here and answers with what Jarvis can now do; a request
    for a learned tool server calls that tool."""
    forget = UNLEARN.match(goal or '')
    if forget:
        try:
            return unlearn(actions, forget.group('label').strip(), cancelled)
        except SkillLearningError as error:
            return f'I could not remove it: {error}'
    source = source_path(goal)
    if source is None:
        return use_learned_tool(actions, goal, cancelled) if tool_request(goal) else None
    actions.report('brain', f'Skill learner: {source}')
    try:
        report = learn(actions, source, cancelled)
    except SkillLearningError as error:
        notify(actions, 'failed', f'Could not learn {source.name}', str(error)[:120], 'stopped')
        return f'I could not learn {source}: {error}'
    if report.get('repeat'):
        return 'Finished: I already learned this exact content before; nothing new to integrate.\n\n' + \
            str(report.get('summary', ''))
    return 'Finished: ' + str(report.get('summary', ''))
