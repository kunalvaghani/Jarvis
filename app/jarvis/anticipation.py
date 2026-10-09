"""Evidence-bound idle preparation, independent of the desktop action executor.

Research inspiration: THUNLP ProactiveAgent and AgentACE-AI ProAct. This is an
independent local implementation, not either upstream runtime or benchmark.
"""
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import uuid

from .obsidian_memory import SENSITIVE


DEFAULTS = dict(enabled=True, idle_seconds=45, dwell_seconds=20,
                cooldown_seconds=300, expiry_seconds=900, max_jobs_per_hour=3,
                max_seconds_per_job=45, max_seconds_per_hour=120,
                local_model=False, model_tokens=256, public_search=True)
RANGES = dict(idle_seconds=(5, 600), dwell_seconds=(5, 300),
              cooldown_seconds=(30, 3600), expiry_seconds=(60, 3600),
              max_jobs_per_hour=(1, 10), max_seconds_per_job=(5, 120),
              max_seconds_per_hour=(5, 600), model_tokens=(64, 512))
PRIVATE = re.compile(r'(?i)\b(inbox|gmail|outlook|bank|banking|patient|medical record|'
                     r'incognito|inprivate|private browsing|sign in|log in|checkout|payment)\b|'
                     r'[\w.+-]+@[\w.-]+|https?://|[A-Za-z]:[\\/]')
RESEARCH = re.compile(r'(?i)^(?:research|look up|learn about|compare|search (?:for|about))\s+(.+)')
BROWSER = re.compile(r'(?i)\s*[-–—|]\s*(?:Google Chrome|Microsoft Edge|Mozilla Firefox)\s*$')
SEARCH_TITLE = re.compile(r'(?i)\s*[-–—|]\s*(?:Google Search|Bing|DuckDuckGo)\s*$')
CODE = re.compile(r'(?i)^([^\\/:*?"<>|]+\.(?:py|js|jsx|ts|tsx|html|css))\s*[-–—]')
COMMANDS = {
    'what have you prepared': 'show', 'show prepared work': 'show',
    'show anticipation': 'show', 'anticipation status': 'status',
    'pause anticipation': 'pause', 'stop anticipation': 'pause',
    'resume anticipation': 'resume', 'start anticipation': 'resume',
    'accept preparation': 'accept', 'accept prepared work': 'accept',
    'dismiss preparation': 'dismiss', 'dismiss prepared work': 'dismiss',
    'always prepare public research': 'authorize',
    'stop automatic public research': 'revoke',
}


def command(text):
    return COMMANDS.get(str(text).strip().casefold().rstrip('.!?'))


def settings(options=None):
    options = {} if options is None else options
    if not isinstance(options, dict):
        raise ValueError('anticipation must be an object')
    result = {**DEFAULTS, **{k: v for k, v in options.items() if k in DEFAULTS}}
    for key in ('enabled', 'local_model', 'public_search'):
        if type(result[key]) is not bool:
            raise ValueError('anticipation.' + key + ' must be boolean')
    for key, (low, high) in RANGES.items():
        value = result[key]
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f'anticipation.{key} must be an integer between {low} and {high}')
    return result


def safe_topic(value):
    value = ' '.join(str(value).split()).strip(' .?!')
    if not 3 <= len(value) <= 180 or SENSITIVE.search(value) or PRIVATE.search(value):
        return ''
    return value


def request_signal(kind, value):
    if kind == 'browser_search':
        topic = safe_topic(value)
    elif kind in {'task', 'ask', 'media_search'}:
        match = RESEARCH.match(str(value).strip())
        topic = safe_topic(match[1]) if match else ''
    else:
        topic = ''
    # Never send compound actions or private identifiers to a preparation search.
    if not topic or re.search(r'(?i)\b(?:and then|send|email|delete|publish|password)\b', topic):
        return None
    return dict(kind='research', topic=topic, origin='request',
                evidence='Explicit research/search request: ' + topic)


def window_signal(title):
    title = str(title).strip()
    if SENSITIVE.search(title) or PRIVATE.search(title):
        return None
    if BROWSER.search(title):
        topic = SEARCH_TITLE.sub('', BROWSER.sub('', title)).strip()
        if not SEARCH_TITLE.search(BROWSER.sub('', title)) and not re.search(
                r'(?i)\b(documentation|tutorial|research|guide|arxiv|paper)\b', topic):
            return None
        topic = safe_topic(topic)
        if topic:
            return dict(kind='research', topic=topic, origin='window',
                        evidence='Observed browser title (page contents not read): ' + topic)
    if re.search(r'(?i)\bVisual Studio Code\s*$', title):
        match = CODE.match(title.lstrip('●• '))
        if match:
            topic = safe_topic(match[1])
            if topic:
                return dict(kind='code_review', topic=topic, origin='window',
                            evidence='Observed editor filename only: ' + topic)
    return None


class Anticipation:
    """One owned worker, no tool dispatcher, no task replay, no account access."""
    def __init__(self, base, options, report, busy=lambda: False, model='qwen3.5:4b',
                 clock=time.monotonic, wall=time.time, runner=None):
        self.base = Path(base).resolve()
        self.options = settings(options)
        self.report, self.busy, self.model = report, busy, model
        self.clock, self.wall = clock, wall
        self.runner = runner or self._worker
        self.directory = self.base / '.jarvis-runtime' / 'anticipation'
        self.lock = threading.RLock()
        self.closed = threading.Event()
        self.interrupt = threading.Event()
        self.thread = None
        self.process = None
        self.generation = 0
        self.paused = False
        self.microphone_stopped = False
        self.storage_failed = False
        self.last_input = self.clock()
        self.window = None
        self.window_since = self.clock()
        self.signal = None
        self.signal_at = self.wall()
        self.rows, self.feedback, self.grants = [], {}, []
        self.jobs = deque()
        self.next_job = self.next_retry = 0.
        self.failures = 0
        self.inflight = False
        self.last_tick = self.clock()
        self.artifact_slot = 0
        self._load()

    def _load(self):
        path = self.directory / 'state.json'
        try:
            if not path.exists():
                return
            if self.directory.resolve() != self.directory or path.is_symlink():
                raise ValueError('state is outside owned storage')
            if path.stat().st_size > 65536:
                raise ValueError('state exceeds size limit')
            data = json.loads(path.read_text(encoding='utf-8'))
            feedback = data.get('feedback', {})
            self.feedback = {key: {name: min(1000, value.get(name, 0)) for name in
                             ('accepted', 'dismissed', 'ignored')}
                for key, value in feedback.items() if key in
                {'research:request', 'research:window', 'code_review:window'}
                and isinstance(value, dict) and all(type(value.get(n, 0)) is int
                and value.get(n, 0) >= 0 for n in ('accepted', 'dismissed', 'ignored'))}
            self.grants = ['public_research'] if data.get('public_research_authorized') is True else []
            self.paused = data.get('paused') is True
            # Preparations are not auto-resumed across a restart; only feedback/grants survive.
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            self.storage_failed = True
            self.report('repair', 'Anticipation state needs review; preserved without replay: ' + str(exc))

    def _path(self, name):
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / name
        if self.directory.resolve() != self.directory or path.is_symlink():
            raise ValueError('Anticipation storage must remain in its owned directory')
        return path

    def _save(self):
        if self.storage_failed:
            return False
        try:
            path = self._path('state.json')
            temporary = self._path('state.tmp')
            temporary.write_text(json.dumps(dict(version=1, feedback=self.feedback,
                paused=self.paused,
                public_research_authorized='public_research' in self.grants,
                preparations=[{k: v for k, v in row.items() if k != 'content'}
                              for row in self.rows[-8:]]), ensure_ascii=False), encoding='utf-8')
            temporary.replace(path)
            return True
        except (OSError, ValueError) as exc:
            self.storage_failed = True
            self.report('repair', 'Anticipation storage stopped; uncertain writes will not be replayed: ' + str(exc))
            return False

    def start(self):
        with self.lock:
            if self.closed.is_set() or not self.options['enabled'] or self.storage_failed:
                return
            if self.thread and self.thread.is_alive():
                return
            self.thread = threading.Thread(target=self._run, name='jarvis-anticipation', daemon=True)
            self.thread.start()

    def _run(self):
        while not self.closed.wait(.5):
            try:
                self.tick()
            except Exception as exc:
                with self.lock:
                    self.failures += 1
                    self.next_retry = self.clock() + min(300, 5 * 2 ** min(self.failures, 6))
                self.report('repair', 'Anticipation read/preparation failed; bounded backoff: ' + str(exc)[:200])
            self.last_tick = self.clock()

    def healthy(self):
        return self.storage_failed or not self.options['enabled'] or bool(
            self.thread and self.thread.is_alive() and
            self.clock() - self.last_tick < self.options['max_seconds_per_job'] + 15)

    def repair(self):
        if self.closed.is_set() or self.storage_failed:
            return False
        self.cancel()
        if self.thread and self.thread.is_alive():
            return self.healthy()  # Never launch a second concurrent worker.
        self.start()
        return self.healthy()

    def cancel(self, microphone=False):
        with self.lock:
            self.generation += 1
            self.interrupt.set()
            self.last_input = self.clock()
            if microphone:
                self.microphone_stopped = True

    def microphone_started(self):
        with self.lock:
            self.microphone_stopped = False
            self.last_input = self.clock()

    def close(self):
        self.closed.set()
        self.cancel()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3)

    def observe_request(self, kind, value):
        self.cancel()
        signal = request_signal(kind, value)
        with self.lock:
            self.signal = signal
            self.signal_at = self.wall()
            self._invalidate(signal)

    def observe_window(self, title, handle=0):
        signal = window_signal(title)
        key = (handle, str(title))
        with self.lock:
            if key != self.window:
                self.window, self.window_since = key, self.clock()
                # Request context remains relevant only until a different observed topic.
                if self.signal and self.signal['origin'] == 'request' and signal and (
                        self.signal['topic'].casefold() in signal['topic'].casefold()):
                    return
                self.generation += 1
                self.interrupt.set()
                self.signal = signal
                self.signal_at = self.wall()
                self._invalidate(signal)

    def _invalidate(self, signal):
        changed = False
        for row in self.rows:
            if row['status'] in {'pending', 'suggested', 'prepared', 'preparing', 'accepted'} and (
                    not signal or row['topic'].casefold() != signal['topic'].casefold()):
                row['status'] = 'stale'
                changed = True
        if changed:
            self._save()
            self._notify()

    def _expire(self):
        changed = False
        for row in self.rows:
            if row['status'] in {'pending', 'suggested', 'prepared', 'preparing', 'accepted'} and self.wall() >= row['expires']:
                if row['status'] == 'suggested':
                    self._feedback(row, 'ignored')
                row['status'] = 'expired'
                changed = True
        if changed:
            self._save()
            self._notify()

    def _feedback(self, row, result):
        if result == 'accepted' and row.get('acceptance_recorded'):
            return
        values = self.feedback.setdefault(row['kind'] + ':' + row['origin'],
                                         dict(accepted=0, dismissed=0, ignored=0))
        values[result] = min(1000, values[result] + 1)
        if result == 'accepted':
            row['acceptance_recorded'] = True

    def _suppressed(self, signal):
        values = self.feedback.get(signal['kind'] + ':' + signal['origin'], {})
        return values.get('dismissed', 0) + values.get('ignored', 0) >= max(2, values.get('accepted', 0) + 2)

    def _notify(self):
        self.report('anticipation', self.snapshot())

    def snapshot(self):
        with self.lock:
            return dict(paused=self.paused or self.microphone_stopped,
                enabled=self.options['enabled'], storage_failed=self.storage_failed,
                public_research_authorized='public_research' in self.grants,
                preparations=[dict(row) for row in self.rows if row['status'] in
                              {'pending', 'suggested', 'preparing', 'prepared', 'accepted'} and self.wall() < row['expires']],
                feedback={k: dict(v) for k, v in self.feedback.items()})

    def handle(self, action, token=''):
        with self.lock:
            self._expire()
            if action == 'show':
                self._notify()
                return 'Prepared work is shown in the island. Predictions and model drafts require review.'
            if action == 'status':
                return ('Anticipation ' + ('paused' if self.paused or self.microphone_stopped else 'enabled'
                    if self.options['enabled'] else 'disabled') +
                    f'; {len(self.snapshot()["preparations"])} current preparations. ' +
                    ('Public browser-topic research is authorized.' if self.grants else
                     'Browser topics require acceptance before public searches.') +
                    (' Storage needs review.' if self.storage_failed else ''))
            if action in {'pause', 'resume', 'authorize', 'revoke'}:
                self.cancel()
                if action == 'pause': self.paused = True
                elif action == 'resume':
                    if not self.options['enabled']:
                        return 'Anticipation is disabled in configuration; enable it and restart Jarvis.'
                    self.paused = self.microphone_stopped = False
                elif action == 'authorize': self.grants = ['public_research']
                elif action == 'revoke': self.grants = []
                if not self._save():
                    self.grants = []
                    return 'Anticipation storage needs review; authorization was not saved.'
                self._notify()
                return {'pause': 'Anticipation paused.', 'resume': 'Anticipation resumed.',
                    'authorize': 'Authorized idle public research from eligible browser topics. No account or desktop actions are authorized.',
                    'revoke': 'Automatic browser-topic research authorization removed.'}[action]
            candidates = [r for r in self.rows if r['status'] in {'suggested', 'prepared'}
                          and self.wall() < r['expires'] and (not token or r['id'] == token)]
            if not candidates:
                return 'That preparation changed or expired. Ask for fresh prepared work.'
            row = candidates[-1]
            if action == 'dismiss':
                row['status'] = 'dismissed'
                self._feedback(row, 'dismissed')
                self._save(); self._notify()
                return 'Preparation dismissed. Similar suggestions will become less frequent.'
            if action == 'accept':
                if row['status'] == 'prepared':
                    try:
                        path = self._path(row['artifact'])
                        if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
                            raise ValueError('artifact changed')
                    except (OSError, ValueError):
                        row['status'] = 'stale'
                        self._save(); self._notify()
                        return 'Prepared artifact changed or is unavailable; prepare fresh evidence.'
                    row['status'] = 'accepted'
                    self._feedback(row, 'accepted')
                else:
                    row['authorized'] = True
                    row['mode'] = 'perform_authorized'
                    row['status'] = 'pending'
                    self._feedback(row, 'accepted')
                    self.cancel()
                self._save(); self._notify()
                return 'Preparation accepted. Read-only work will run when Jarvis is idle.' if row['status'] == 'pending' else row['content']
            return 'Unknown anticipation action.'

    def tick(self):
        with self.lock:
            self.last_tick = self.clock()
            self._expire()
            if (self.closed.is_set() or self.paused or self.microphone_stopped or self.storage_failed
                    or not self.options['enabled'] or self.busy() or self.inflight
                    or self.clock() - self.last_input < self.options['idle_seconds']
                    or self.clock() < max(self.next_job, self.next_retry)):
                return
            while self.jobs and self.clock() - self.jobs[0][0] >= 3600:
                self.jobs.popleft()
            if len(self.jobs) >= self.options['max_jobs_per_hour']:
                return
            remaining = self.options['max_seconds_per_hour'] - sum(j[1] for j in self.jobs)
            if remaining < 5:
                return
            pending = next((r for r in self.rows if r['status'] == 'pending' and self.wall() < r['expires']), None)
            if pending:
                row = pending
            else:
                signal = self.signal
                if not signal or self._suppressed(signal) or (signal['origin'] == 'window' and
                        self.clock() - self.window_since < self.options['dwell_seconds']):
                    return
                if signal['origin'] == 'request' and self.wall() - self.signal_at >= self.options['expiry_seconds']:
                    return  # An old request alone is not fresh evidence for another preparation.
                if any(r['topic'].casefold() == signal['topic'].casefold() and r['status'] not in
                       {'stale', 'expired', 'cancelled', 'failed'} for r in self.rows):
                    return
                authorized = signal['origin'] == 'request' or (signal['kind'] == 'research' and 'public_research' in self.grants)
                row = {**signal, 'id': uuid.uuid4().hex, 'created': self.wall(),
                       'expires': self.wall() + self.options['expiry_seconds'],
                       'authorized': authorized, 'mode': 'prepare' if signal['origin'] == 'request'
                       else 'perform_authorized' if authorized else 'suggest', 'status': 'pending',
                       'content': '', 'artifact': '', 'sha256': ''}
                self.rows = (self.rows + [row])[-8:]
                if not authorized:
                    row['status'] = 'suggested'
                    self.next_job = self.clock() + self.options['cooldown_seconds']
                    self._save(); self._notify()
                    return
            row['status'] = 'preparing'
            self.inflight = True
            self.interrupt.clear()
            generation, started = self.generation, self.clock()
            budget = min(self.options['max_seconds_per_job'], remaining)
            self.jobs.append((started, budget))  # Reserve the worst case before starting.
            self.next_job = started + self.options['cooldown_seconds']
            self._notify()
        cancelled = lambda: (self.closed.is_set() or self.interrupt.is_set() or generation != self.generation
                              or self.busy() or self.wall() >= row['expires'])
        writing = False
        try:
            result = self.runner({**row, 'options': {**self.options, 'model': self.model}}, cancelled, budget)
            with self.lock:
                if cancelled():
                    row['status'] = 'cancelled' if row['status'] != 'stale' else 'stale'
                    return
                content = result.get('content', '')
                if not isinstance(content, str) or not content.strip() or len(content) > 16000:
                    raise ValueError('Preparation returned invalid/bounded output')
                slot = self.artifact_slot % 8
                self.artifact_slot += 1
                for previous in self.rows:
                    if previous is not row and previous['artifact'] == f'draft-{slot}.md':
                        previous['status'] = 'stale'
                writing = True
                path = self._path(f'draft-{slot}.md')
                temporary = self._path(f'draft-{slot}.tmp')
                temporary.write_text(content, encoding='utf-8')
                temporary.replace(path)
                observed = path.read_text(encoding='utf-8')
                if observed != content:
                    raise OSError('Preparation disk readback failed')
                row.update(content=content, status='prepared', artifact=path.name,
                           sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                           scope=str(result.get('scope', 'Unverified preparation'))[:300])
                self.failures = 0
                self._save()
        except Exception as exc:
            with self.lock:
                row['status'] = 'cancelled' if cancelled() else 'failed'
                if not cancelled():
                    self.failures += 1
                    self.next_retry = self.clock() + min(300, 5 * 2 ** min(self.failures, 6))
                if writing and isinstance(exc, OSError):
                    self.storage_failed = True
                self.report('repair', 'Anticipation preparation stopped: ' + str(exc)[:200])
        finally:
            with self.lock:
                self.inflight = False
                self.jobs[-1] = (started, max(0, min(budget, self.clock() - started)))
                self._save(); self._notify()

    def _worker(self, request, cancelled, budget):
        process = subprocess.Popen([sys.executable, '-m', 'jarvis.anticipation_worker'],
            cwd=self.base, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            encoding='utf-8', env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONUTF8='1'),
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.process = process
        deadline = self.clock() + budget
        payload = json.dumps(request)
        first = True
        try:
            while True:
                if cancelled():
                    raise InterruptedError('Idle preparation cancelled')
                if self.clock() >= deadline:
                    raise TimeoutError('Idle preparation reached its compute deadline')
                try:
                    output, error = process.communicate(input=payload if first else None, timeout=.1)
                    break
                except subprocess.TimeoutExpired:
                    first = False
            if process.returncode:
                raise ValueError('Preparation worker failed: ' + error[-300:])
            if len(output) > 20000:
                raise ValueError('Preparation output exceeds limit')
            result = json.loads(output)
            if result.get('error'):
                raise ValueError(result['error'])
            return result
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=3)
            self.process = None
