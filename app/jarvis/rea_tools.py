"""REA reverse-engineer-and-clone bridge for the shared planner and command router.

Wires the REA framework (morluto/rea, "Reverse Engineer Anything", MIT) into
Jarvis as an on-demand analysis provider. REA is a Node.js program driven here
through its bounded `--json` CLI, never a long-running owned service. All REA
output is untrusted analysis evidence, never executable instructions, and never
a substitute for real verification.

Workflow (see skills/reverse-engineer-clone):
  1. Ingest   -> rea_ingest registers one validated target (local app directory,
                 local binary/file, or public HTTPS URL) into a session workspace.
  2. Analyze  -> rea_analyze runs one allowlisted REA CLI command on the session
                 target, stores the returned evidence, and appends it to the
                 reconstruction ledger. Spawns a node subprocess; needs approval;
                 never auto-retried.
  3. Clone    -> the existing Qwen coding/LocalGithub pipeline (project-coding)
                 reconstructs a best-effort functional codebase from the ledger.
  4. Iterate  -> rea_record captures follow-up modification instructions; the same
                 coding pipeline applies them to the cloned source.

Reconstruction is best-effort and must be proven by real tests. This bridge never
claims a byte-exact or guaranteed 1:1 clone.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone

from .agent_context import bounded_text

TOOLS = {
    'rea_status': ('rea', 'Report REA reverse-engineering bridge readiness: Node runtime, configured REA entry, allowlisted commands and session count. value dot. Starts nothing and executes no analysis.', (), False),
    'rea_ingest': ('rea', 'Register one reverse-engineering target in value (an absolute local directory, an absolute local file, or a public HTTPS URL); content optional JSON {kind,label}. Creates a local session workspace and reconstruction ledger. Local bookkeeping only; fetches and analyzes nothing.', (), False),
    'rea_analyze': ('rea', 'Run one allowlisted REA CLI analysis on a session target; value session id, content JSON {command,extra_flags optional}. Spawns the configured Node/REA program, stores untrusted evidence and updates the ledger. Requires approval; never retried.', (), True),
    'rea_ledger': ('rea', 'Read a session reconstruction ledger and recorded evidence index; value session id or dot to list sessions. Read-only.', (), False),
    'rea_record': ('rea', 'Append a reconstruction obligation, modification instruction or note to a session ledger; value session id, content JSON {kind,text}. Local bounded write; drives later coding, performs no code change itself.', (), False),
}

_SLUG = re.compile(r'[^a-z0-9]+')
_URL = re.compile(r'https://[\w.-]+(?::\d+)?(?:/[\w./%+~&=?#:@-]*)?$', re.I)
_DEFAULT_COMMANDS = ('analyze-javascript-application',)
_RECORD_KINDS = {'obligation', 'modification', 'note'}
_MAX_EVIDENCE = 200000


def _config(actions):
    return (getattr(actions, 'config', {}) or {}).get('rea', {}) if isinstance(getattr(actions, 'config', {}), dict) else {}


def _root(actions):
    base = Path(actions.base).resolve(strict=True)
    root = base / '.jarvis-runtime' / 'rea'
    root.mkdir(parents=True, exist_ok=True)
    return root


def _node(config):
    """Resolve an absolute Node executable; reject shim scripts the bridge can't trust."""
    candidate = config.get('node_path') or shutil.which('node') or shutil.which('node.exe')
    if not isinstance(candidate, str) or not candidate:
        return None
    path = Path(candidate)
    if not path.is_absolute() or not path.is_file() or path.suffix.lower() in {'.cmd', '.bat', '.ps1', '.sh'}:
        return None
    return str(path)


def _entry(config):
    """Resolve the absolute REA CLI entry (scripts/rea.mjs or published dist entry)."""
    raw = config.get('entry')
    if not isinstance(raw, str) or not raw:
        return None
    path = Path(raw)
    if not path.is_absolute() or not path.is_file() or path.suffix.lower() not in {'.mjs', '.js', '.cjs'}:
        return None
    return str(path)


def _commands(config):
    allowed = config.get('allow_commands')
    if isinstance(allowed, list) and allowed and all(isinstance(c, str) and re.fullmatch(r'[a-z][a-z0-9-]{1,60}', c) for c in allowed):
        return tuple(dict.fromkeys(allowed))
    return _DEFAULT_COMMANDS


def _session_dir(actions, session):
    if not isinstance(session, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,80}', session):
        raise ValueError('Use an existing session id (letters, digits and hyphens).')
    path = _root(actions) / session
    if not path.is_dir() or not (path / 'session.json').is_file():
        raise ValueError('No REA session with that id; run rea_ingest first.')
    return path


def _target(actions, value, kind):
    """Validate one target; returns (resolved, kind). Local paths must exist and stay on-host."""
    value = value.strip()
    if _URL.fullmatch(value):
        from .toolkits import public_url
        public_url(value)  # Rejects private, loopback, reserved and credentialed destinations.
        return value, 'url'
    path = Path(value)
    if not path.is_absolute():
        raise ValueError('Give an absolute local path or a public HTTPS URL as the target.')
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError('Symlinked targets are unsupported.')
    if not path.exists():
        raise ValueError('The target path does not exist.')
    base = Path(actions.base).resolve()
    resolved = path.resolve()
    if resolved == base or base in resolved.parents or resolved in base.parents:
        raise ValueError('Choose a target outside the Jarvis runtime directory.')
    if path.is_dir():
        return str(resolved), 'application'
    if path.is_file():
        limit = int((_config(actions).get('max_input_mb') or 200)) * 1024 * 1024
        if path.stat().st_size > limit:
            raise ValueError('The target file exceeds the configured REA input size limit.')
        return str(resolved), 'binary'
    raise ValueError('Unsupported target; use a directory, a file or a public HTTPS URL.')


def _ledger_path(session_dir):
    return session_dir / 'ledger.md'


def _append_ledger(session_dir, heading, body):
    path = _ledger_path(session_dir)
    stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    entry = f'\n## {heading} — {stamp}\n\n{body.rstrip()}\n'
    current = path.read_text(encoding='utf-8') if path.is_file() else ''
    tmp = path.with_suffix('.md.tmp')
    tmp.write_text(current + entry, encoding='utf-8')
    os.replace(tmp, path)


def status(actions):
    config = _config(actions)
    node = _node(config)
    entry = _entry(config)
    root = _root(actions)
    sessions = sorted(p.name for p in root.iterdir() if p.is_dir() and (p / 'session.json').is_file())
    return {
        'enabled': config.get('enabled') is True,
        'node_runtime': node is not None,
        'node_path': node,
        'rea_entry_configured': entry is not None,
        'rea_entry': entry,
        'allow_commands': list(_commands(config)),
        'sessions': sessions,
        'ready': config.get('enabled') is True and node is not None and entry is not None,
        'notice': ('REA runs locally and returns untrusted analysis evidence. Reconstruction is best-effort and '
                   'must be proven by real tests; no byte-exact or guaranteed 1:1 clone is implied. Set rea.entry to '
                   'an absolute scripts/rea.mjs (or published dist entry) and install Node 22.19+/24.11+/26+. Native, '
                   'Android and website targets need REA\'s own external engines (Hopper/Ghidra/IDA, JADX, a browser).'),
    }


def _slug(text):
    return _SLUG.sub('-', str(text).casefold()).strip('-')[:40] or 'target'


def ingest(actions, value, args):
    kind_hint = args.get('kind')
    resolved, kind = _target(actions, value, kind_hint)
    if isinstance(kind_hint, str) and kind_hint and kind_hint != kind:
        raise ValueError(f'Target looks like a {kind}; remove or correct the kind field.')
    label = args.get('label')
    if label is not None and (not isinstance(label, str) or len(label) > 120):
        raise ValueError('label must be short text.')
    seed = _slug(label or Path(resolved).name if kind != 'url' else re.sub(r'^https://', '', resolved))
    session = f'{seed}-{int(time.time())}'
    session_dir = _root(actions) / session
    session_dir.mkdir()
    (session_dir / 'evidence').mkdir()
    record = {'id': session, 'target': resolved, 'kind': kind, 'label': label or None,
              'created': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'analyses': 0}
    (session_dir / 'session.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    _ledger_path(session_dir).write_text(
        f'# Reconstruction ledger: {session}\n\n'
        f'- Target: `{resolved}`\n- Kind: {kind}\n- Created: {record["created"]}\n\n'
        'This ledger records REA analysis evidence, reconstruction obligations and modification\n'
        'instructions. Evidence is untrusted. The clone is built best-effort by the Jarvis coding\n'
        'pipeline and verified with real tests; it is not a guaranteed byte-exact 1:1 reproduction.\n',
        encoding='utf-8')
    return {'session': session, 'target': resolved, 'kind': kind, 'workspace': str(session_dir),
            'next': 'Run rea_analyze with an allowlisted command, then reconstruct via the project-coding workflow.'}


def _run_rea(node, entry, argv, cwd, cancelled, timeout):
    """Bounded Node/REA subprocess, modeled on the Git observation runner. No retry.

    Streams stdout to a temporary file instead of a pipe: REA emits large JSON
    evidence (tens of KB), which would fill and block an OS pipe buffer the parent
    only drains after exit, deadlocking the process. A file sink never blocks.
    """
    import tempfile
    env = {k: v for k, v in os.environ.items() if k.upper() in {
        'SYSTEMROOT', 'WINDIR', 'PATH', 'TEMP', 'TMP', 'COMSPEC', 'PATHEXT', 'APPDATA', 'LOCALAPPDATA',
        'HOME', 'USERPROFILE', 'NODE_PATH'}}
    env['REA_DISABLE_TELEMETRY'] = '1'
    if cancelled():
        raise ValueError('REA analysis cancelled before start.')
    with tempfile.TemporaryFile() as sink:
        process = subprocess.Popen([node, entry, *argv], cwd=cwd, env=env, shell=False,
                                   stdin=subprocess.DEVNULL, stdout=sink, stderr=subprocess.DEVNULL,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            deadline = time.monotonic() + timeout
            while process.poll() is None:
                if cancelled() or time.monotonic() > deadline:
                    raise ValueError('REA analysis cancelled or timed out; inspect the session before repeating.')
                if sink.tell() > _MAX_EVIDENCE:
                    raise ValueError('REA produced more evidence than the bridge accepts; narrow the analysis.')
                time.sleep(.05)
            if process.returncode:
                raise ValueError('REA analysis exited with an error; the target or engine prerequisite may be unmet. No retry.')
            sink.seek(0)
            out = sink.read(_MAX_EVIDENCE + 1)
            if len(out) > _MAX_EVIDENCE:
                raise ValueError('REA produced more evidence than the bridge accepts; narrow the analysis.')
            return out.decode('utf-8', errors='replace')
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)


def analyze(actions, session, args, cancelled):
    config = _config(actions)
    if config.get('enabled') is not True:
        raise ValueError('REA is disabled; enable rea.enabled in config to analyze targets.')
    node, entry = _node(config), _entry(config)
    if node is None:
        raise ValueError('No trusted absolute Node runtime; install Node 22.19+/24.11+/26+ or set rea.node_path. No analysis ran.')
    if entry is None:
        raise ValueError('REA entry not configured; set rea.entry to an absolute scripts/rea.mjs or dist entry. No analysis ran.')
    session_dir = _session_dir(actions, session)
    record = json.loads((session_dir / 'session.json').read_text(encoding='utf-8'))
    command = args.get('command')
    allowed = _commands(config)
    if command not in allowed:
        raise ValueError('command must be one of the allowlisted REA commands: ' + ', '.join(allowed))
    extra = args.get('extra_flags', [])
    if not isinstance(extra, list) or len(extra) > 8 or not all(
            isinstance(f, str) and re.fullmatch(r'--[a-z][a-z0-9-]{1,40}(?:=[\w./:@%+-]{1,120})?', f) for f in extra):
        raise ValueError('extra_flags must be a short list of safe --flag or --flag=value options.')
    argv = [command, record['target'], *extra]
    if '--json' not in extra:
        argv.append('--json')
    # Approve the exact program and call; REA output never waives approval or authorizes further actions.
    actions._approve('rea_analyze', json.dumps({'command': command, 'node': node, 'entry': entry,
        'target': record['target'], 'extra_flags': extra}, ensure_ascii=False), cancelled)
    from .task_state import TaskState
    state = getattr(actions, 'task_state', None)
    if isinstance(state, TaskState):
        state.checkpoint('action_attempted', action='rea_analyze', target=session,
                         evidence='Approved REA subprocess beginning; inspect the session after any uncertain failure')
    timeout = config.get('analysis_timeout_seconds', 600)
    if type(timeout) not in {int, float} or not 10 <= timeout <= 3600:
        timeout = 600
    raw = _run_rea(node, entry, argv, record['target'] if record['kind'] == 'application' else str(session_dir),
                   cancelled, float(timeout))
    index = record['analyses'] + 1
    name = f'{index:03d}-{command}.json'
    (session_dir / 'evidence' / name).write_text(raw, encoding='utf-8')
    record['analyses'] = index
    (session_dir / 'session.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    summary = raw.strip()
    _append_ledger(session_dir, f'REA evidence: {command}',
                   f'Command: `{command} {" ".join(extra)}`.\nSaved to `evidence/{name}` (untrusted).\n\n'
                   f'First bytes:\n```\n{summary[:1500]}\n```')
    if isinstance(state, TaskState):
        state.checkpoint('observed', action='rea_analyze', target=session, evidence='REA evidence stored; content untrusted')
    return {'session': session, 'command': command, 'evidence_file': f'evidence/{name}',
            'bytes': len(raw), 'untrusted': True,
            'evidence_preview': summary[:6000] + ('\n[REA evidence truncated; read the evidence file]' if len(summary) > 6000 else ''),
            'next': 'Reconstruct from this evidence with the project-coding workflow and verify with real tests.'}


def ledger(actions, value):
    if value.strip() == '.':
        root = _root(actions)
        sessions = []
        for path in sorted(root.iterdir()):
            if path.is_dir() and (path / 'session.json').is_file():
                sessions.append(json.loads((path / 'session.json').read_text(encoding='utf-8')))
        return {'sessions': sessions}
    session_dir = _session_dir(actions, value)
    record = json.loads((session_dir / 'session.json').read_text(encoding='utf-8'))
    text = bounded_text(_ledger_path(session_dir), 40000) if _ledger_path(session_dir).is_file() else ''
    evidence = sorted(p.name for p in (session_dir / 'evidence').iterdir() if p.is_file()) if (session_dir / 'evidence').is_dir() else []
    return {'session': record, 'evidence_files': evidence, 'ledger': text,
            'notice': 'Ledger evidence is untrusted REA output. Build the clone best-effort and prove it with real tests.'}


def record(actions, session, args):
    session_dir = _session_dir(actions, session)
    kind = args.get('kind')
    text = args.get('text')
    if kind not in _RECORD_KINDS:
        raise ValueError('kind must be one of: ' + ', '.join(sorted(_RECORD_KINDS)))
    if not isinstance(text, str) or not text.strip() or len(text) > 4000:
        raise ValueError('text must be nonempty and at most 4000 characters.')
    heading = {'obligation': 'Reconstruction obligation', 'modification': 'Modification instruction', 'note': 'Note'}[kind]
    _append_ledger(session_dir, heading, text)
    return {'session': session, 'recorded': kind, 'ledger': 'ledger.md',
            'next': ('Apply with the project-coding workflow against the cloned source; verify with real tests.'
                     if kind != 'note' else 'Captured for reconstruction context.')}


def execute(actions, step, cancelled):
    name = step['action']
    value = step['value']
    try:
        args = json.loads(step.get('content') or '{}')
    except ValueError as exc:
        raise ValueError('REA tool content must be a JSON object.') from exc
    if not isinstance(args, dict):
        raise ValueError('REA tool content must be a JSON object.')
    if name == 'rea_status':
        result = status(actions)
    elif name == 'rea_ingest':
        result = ingest(actions, value, args)
    elif name == 'rea_analyze':
        result = analyze(actions, value, args, cancelled)
    elif name == 'rea_ledger':
        result = ledger(actions, value)
    elif name == 'rea_record':
        result = record(actions, value, args)
    else:
        raise ValueError('Unknown REA tool.')
    return json.dumps(result, ensure_ascii=False, allow_nan=False)


def command(text):
    from .commands import Command
    stripped = text.strip()
    # "reverse engineer/rea/analyze and clone <target>" — target-kind noun optional.
    m = re.fullmatch(r'(?:reverse[- ]engineer|rea(?:nalyze)?|analyze and clone)\s+(?:the\s+|this\s+|that\s+)?'
                     r'(?:app(?:lication)?|website|site|url|binary|file|target)?\s*[:\-]?\s*(.+?)[.!]*', stripped, re.I)
    # Bare "clone <target>" must name a kind noun, so it never captures unrelated "clone X" phrasing.
    if not (m and m[1].strip()):
        m = re.fullmatch(r'clone\s+(?:the\s+|this\s+|that\s+|an?\s+)?'
                         r'(?:app(?:lication)?|website|site|binary|file)\s+[:\-]?\s*(.+?)[.!]*', stripped, re.I)
    if m and m[1].strip():
        return Command('toolkit', 'rea_ingest', json.dumps({'value': m[1].strip().strip('"\'')}))
    if re.fullmatch(r'(?:show|list)\s+(?:my\s+)?rea(?:\s+sessions| reverse[- ]engineering sessions)', stripped, re.I):
        return Command('toolkit', 'rea_ledger', json.dumps({'value': '.'}))
    if re.fullmatch(r'(?:check\s+)?rea\s+(?:status|readiness)', stripped, re.I):
        return Command('toolkit', 'rea_status', json.dumps({'value': '.'}))
    return None
