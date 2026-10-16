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
import math
import threading
from contextlib import contextmanager
from uuid import uuid4
from datetime import datetime, timezone

from .agent_context import bounded_text
from .skill_memory import linked, atomic

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
_LOCK = threading.RLock()
_MAX_LEDGER = 2 * 1024 * 1024


def _config(actions):
    settings = getattr(actions, 'config', {})
    if not isinstance(settings, dict) or not isinstance(settings.get('rea', {}), dict):
        raise ValueError('REA config must be an object.')
    config = settings.get('rea', {})
    for key, default, low, high in (('analysis_timeout_seconds', 600, 10, 3600), ('max_input_mb', 200, 1, 200)):
        value = config.get(key, default)
        if type(value) not in {int, float} or not math.isfinite(value) or not low <= value <= high:
            raise ValueError('Invalid rea.' + key)
    if 'enabled' in config and type(config['enabled']) is not bool:
        raise ValueError('Invalid rea.enabled')
    _commands(config)
    return config


def _unlinked(path):
    path = Path(path).absolute()
    if any(linked(p) for p in (path, *path.parents)):
        raise ValueError('REA paths must not contain links or reparse points.')
    return path


def _read_session(path):
    path = _unlinked(path / 'session.json')
    if path.stat().st_size > 65536:
        raise ValueError('REA session checkpoint size exceeds limit.')
    try:
        record = json.loads(path.read_text(encoding='utf-8'))
        if (not isinstance(record, dict) or record.get('id') != path.parent.name or
                record.get('kind') not in {'url', 'application', 'binary'} or
                not isinstance(record.get('target'), str) or len(record['target']) > 4096 or
                type(record.get('analyses')) is not int or not 0 <= record['analyses'] <= 1000 or
                record.get('analysis_state', 'idle') not in {'idle', 'attempted', 'uncertain', 'completed'}):
            raise ValueError('Invalid REA session checkpoint.')
        return record
    except (RecursionError, TypeError, UnicodeError, json.JSONDecodeError):
        raise ValueError('Invalid REA session checkpoint.') from None


@contextmanager
def _exclusive(path):
    # Cross-process fail-closed fence. A crash leaves the fence for manual inspection.
    with _LOCK:
        lock = _unlinked(path / '.operation.lock')
        try:
            with lock.open('x', encoding='utf-8') as stream:
                stream.write(str(os.getpid()))
        except FileExistsError:
            raise ValueError('REA session busy or uncertain after interruption; inspect before repeating.') from None
        try:
            yield
        finally:
            lock.unlink()


def _root(actions):
    base = _unlinked(actions.base).resolve(strict=True)
    root = base / '.jarvis-runtime' / 'rea'
    _unlinked(root)
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
    if 'allow_commands' not in config:
        return _DEFAULT_COMMANDS
    if isinstance(allowed, list) and allowed and all(isinstance(c, str) and re.fullmatch(r'[a-z][a-z0-9-]{1,60}', c) for c in allowed):
        return tuple(dict.fromkeys(allowed))
    raise ValueError('Invalid rea.allow_commands config; use a nonempty command allowlist.')


def _session_dir(actions, session):
    if not isinstance(session, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,80}', session):
        raise ValueError('Use an existing session id (letters, digits and hyphens).')
    path = _unlinked(_root(actions) / session)
    if not path.is_dir() or not (path / 'session.json').is_file():
        raise ValueError('No REA session with that id; run rea_ingest first.')
    return path


def _target(actions, value, kind):
    """Validate one target; returns (resolved, kind). Local paths must exist and stay on-host."""
    if not isinstance(value, str):
        raise ValueError('REA target must be text.')
    value = value.strip()
    if not value or len(value) > 4096 or any(0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise ValueError('REA target must be bounded Unicode text.')
    if _URL.fullmatch(value):
        from .toolkits import public_url
        public_url(value)  # Rejects private, loopback, reserved and credentialed destinations.
        return value, 'url'
    path = Path(value)
    if not path.is_absolute():
        raise ValueError('Give an absolute local path or a public HTTPS URL as the target.')
    _unlinked(path)
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
    path = _unlinked(_ledger_path(session_dir))
    stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    entry = f'\n## {heading} — {stamp}\n\n{body.rstrip()}\n'
    if (path.stat().st_size if path.exists() else 0) + len(entry.encode('utf-8')) > _MAX_LEDGER:
        raise ValueError('REA ledger size limit reached; archive this session before continuing.')
    # Caller holds the session fence. Append avoids copying the entire ledger per note.
    with path.open('a', encoding='utf-8', newline='') as stream:
        stream.write(entry)
        stream.flush()
        os.fsync(stream.fileno())


def status(actions):
    config = _config(actions)
    node = _node(config)
    entry = _entry(config)
    root = _root(actions)
    sessions = sorted(p.name for p in _sessions(root))
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


def _sessions(root):
    result = []
    for count, path in enumerate(root.iterdir()):
        if count >= 1000:
            raise ValueError('REA session inventory limit reached; archive old sessions.')
        _unlinked(path)
        if path.is_dir() and (path / 'session.json').is_file():
            result.append(path)
    return sorted(result)


def ingest(actions, value, args):
    _config(actions)
    kind_hint = args.get('kind')
    if kind_hint is not None and (not isinstance(kind_hint, str) or kind_hint not in {'url', 'application', 'binary'}):
        raise ValueError('kind must be url, application or binary.')
    resolved, kind = _target(actions, value, kind_hint)
    if isinstance(kind_hint, str) and kind_hint and kind_hint != kind:
        raise ValueError(f'Target looks like a {kind}; remove or correct the kind field.')
    label = args.get('label')
    if label is not None and (not isinstance(label, str) or len(label) > 120 or any(0xD800 <= ord(c) <= 0xDFFF for c in label)):
        raise ValueError('label must be short text.')
    seed = _slug(label or (Path(resolved).name if kind != 'url' else re.sub(r'^https://', '', resolved)))
    session = f'{seed}-{uuid4().hex}'
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
        'HOME', 'USERPROFILE'}}
    env['REA_DISABLE_TELEMETRY'] = '1'
    if cancelled():
        raise ValueError('REA analysis cancelled before start.')
    from .harness_process import OwnedJob, hidden_spawn
    job = OwnedJob()
    with tempfile.TemporaryFile() as sink:
        process = None
        try:
            process = hidden_spawn(job, subprocess.Popen)([node, entry, *argv], cwd=cwd, env=env, shell=False,
                                   stdin=subprocess.DEVNULL, stdout=sink, stderr=subprocess.DEVNULL)
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
            job.close()
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)


def analyze(actions, session, args, cancelled):
    directory = _session_dir(actions, session)
    with _exclusive(directory):
        try:
            return _analyze(actions, session, args, cancelled)
        except BaseException:
            from .task_state import TaskState
            state = getattr(actions, 'task_state', None)
            if isinstance(state, TaskState) and _read_session(directory).get('analysis_state') in {'attempted', 'uncertain'}:
                state.checkpoint('uncertain_external_write', action='rea_analyze', target=session,
                                 evidence='REA subprocess outcome uncertain; inspect session; never replay')
            raise


def _analyze(actions, session, args, cancelled):
    config = _config(actions)
    if config.get('enabled') is not True:
        raise ValueError('REA is disabled; enable rea.enabled in config to analyze targets.')
    node, entry = _node(config), _entry(config)
    if node is None:
        raise ValueError('No trusted absolute Node runtime; install Node 22.19+/24.11+/26+ or set rea.node_path. No analysis ran.')
    if entry is None:
        raise ValueError('REA entry not configured; set rea.entry to an absolute scripts/rea.mjs or dist entry. No analysis ran.')
    session_dir = _session_dir(actions, session)
    record = _read_session(session_dir)
    _unlinked(session_dir / 'evidence')
    if record.get('analysis_state') in {'attempted', 'uncertain'}:
        raise ValueError('REA analysis is uncertain; inspect evidence and create a fresh session before repeating.')
    if record['analyses'] >= 1000:
        raise ValueError('REA session analysis limit reached.')
    if cancelled():
        raise ValueError('REA analysis cancelled before approval.')
    _target(actions, record['target'], record['kind'])
    identities = [(p, p.stat().st_size, p.stat().st_mtime_ns) for p in (_unlinked(node), _unlinked(entry))]
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
    if cancelled():
        raise ValueError('REA analysis cancelled after approval.')
    _target(actions, record['target'], record['kind'])
    if any((_unlinked(p).stat().st_size, p.stat().st_mtime_ns) != (size, stamp) for p, size, stamp in identities):
        raise ValueError('REA program changed during approval; request fresh approval.')
    from .task_state import TaskState
    state = getattr(actions, 'task_state', None)
    if isinstance(state, TaskState):
        state.checkpoint('action_attempted', action='rea_analyze', target=session,
                         evidence='Approved REA subprocess beginning; inspect the session after any uncertain failure')
    timeout = config.get('analysis_timeout_seconds', 600)
    record['analysis_state'] = 'attempted'
    record['attempt_id'] = uuid4().hex
    atomic(session_dir / 'session.json', json.dumps(record, ensure_ascii=False))
    try:
        raw = _run_rea(node, entry, argv, record['target'] if record['kind'] == 'application' else str(session_dir),
                       cancelled, float(timeout))
        if cancelled():
            raise ValueError('REA analysis cancelled during readback.')
        if not isinstance(raw, str) or len(raw.encode('utf-8')) > _MAX_EVIDENCE:
            raise ValueError('REA JSON evidence exceeds size limit.')
        try:
            payload = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except (ValueError, RecursionError):
            raise ValueError('REA must return bounded valid JSON evidence.') from None
        if not isinstance(payload, dict) or not payload:
            raise ValueError('REA JSON evidence must be a nonempty object.')
    except BaseException:
        record['analysis_state'] = 'uncertain'
        atomic(session_dir / 'session.json', json.dumps(record, ensure_ascii=False))
        raise
    index = record['analyses'] + 1
    name = f'{index:03d}-{command}.json'
    evidence = _unlinked(session_dir / 'evidence' / name)
    with evidence.open('x', encoding='utf-8') as stream:
        stream.write(raw)
    record['analyses'] = index
    summary = raw.strip()
    _append_ledger(session_dir, f'REA evidence: {command}',
                   f'Command: `{command} {" ".join(extra)}`.\nSaved to `evidence/{name}` (untrusted).\n\n'
                   f'First bytes:\n```\n{summary[:1500]}\n```')
    record['analysis_state'] = 'completed'
    atomic(session_dir / 'session.json', json.dumps(record, ensure_ascii=False))
    if isinstance(state, TaskState):
        state.checkpoint('observed', action='rea_analyze', target=session, evidence='REA evidence stored; content untrusted')
    return {'session': session, 'command': command, 'evidence_file': f'evidence/{name}',
            'bytes': len(raw.encode('utf-8')), 'untrusted': True, 'verified_behavior': False,
            'attempt_id': record['attempt_id'],
            'evidence_preview': summary[:6000] + ('\n[REA evidence truncated; read the evidence file]' if len(summary) > 6000 else ''),
            'next': 'Reconstruct from this evidence with the project-coding workflow and verify with real tests.'}


def ledger(actions, value):
    if value.strip() == '.':
        root = _root(actions)
        sessions = []
        for path in _sessions(root):
            sessions.append(_read_session(path))
        return {'sessions': sessions}
    session_dir = _session_dir(actions, value)
    record = _read_session(session_dir)
    _unlinked(_ledger_path(session_dir))
    text = bounded_text(_ledger_path(session_dir), 40000) if _ledger_path(session_dir).is_file() else ''
    evidence_root = _unlinked(session_dir / 'evidence')
    evidence = sorted(p.name for p in evidence_root.iterdir() if p.is_file() and not linked(p)) if evidence_root.is_dir() else []
    return {'session': record, 'evidence_files': evidence, 'ledger': text,
            'notice': 'Ledger evidence is untrusted REA output. Build the clone best-effort and prove it with real tests.'}


def record(actions, session, args):
    session_dir = _session_dir(actions, session)
    kind = args.get('kind')
    text = args.get('text')
    if not isinstance(kind, str) or kind not in _RECORD_KINDS:
        raise ValueError('kind must be one of: ' + ', '.join(sorted(_RECORD_KINDS)))
    if not isinstance(text, str) or not text.strip() or len(text) > 4000 or any(0xD800 <= ord(c) <= 0xDFFF for c in text):
        raise ValueError('text must be nonempty and at most 4000 characters.')
    heading = {'obligation': 'Reconstruction obligation', 'modification': 'Modification instruction', 'note': 'Note'}[kind]
    with _exclusive(session_dir):
        _read_session(session_dir)
        _append_ledger(session_dir, heading, text)
    return {'session': session, 'recorded': kind, 'ledger': 'ledger.md',
            'next': ('Apply with the project-coding workflow against the cloned source; verify with real tests.'
                     if kind != 'note' else 'Captured for reconstruction context.')}


def execute(actions, step, cancelled):
    name = step['action']
    value = step['value']
    content = step.get('content') or '{}'
    if not isinstance(content, str) or len(content) > 16384:
        raise ValueError('REA tool content size exceeds limit.')
    try:
        args = json.loads(content)
    except (ValueError, RecursionError) as exc:
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
