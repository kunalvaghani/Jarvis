"""JARVIS Cognitive Awareness Engine (JCAE): an additive, event-driven awareness layer.

Observations -> world state and beliefs -> attention -> problems and predictions ->
policy (which may be silence) -> at most a read-only investigation submitted to the
*existing* durable scheduler, or a suggestion the user accepts through the ordinary
command path. It never clicks, types, writes, sends or approves anything itself, and
it is not a second scheduler, memory authority or approval manager.

One worker thread, bounded inbox, Tier 1 rules and statistics only. Model reasoning
(Tier 3) happens only through a scheduler task when explicitly enabled. If this layer
fails or is disabled, ordinary Jarvis commands, tools and the queue are unaffected.
"""
import ctypes
import json
import os
import re
import threading
import time
import uuid
from collections import deque
from pathlib import Path

from .awareness_model import AwarenessStore, BeliefEngine, Observation, WorldState, severity
from .awareness_policy import CuriosityEngine, ExperienceEvaluator, MetacognitiveEvaluator, ProactivePolicyEngine, compose
from .awareness_reasoning import AttentionManager, CognitiveWorkspace, PredictionEngine, SelfModelManager, overlap
from .commands import Command

DEFAULT_SENSORS = {'system': True, 'tasks': True, 'jarvis': True, 'user_presence': False, 'foreground_app': False,
                   'files': False, 'external': False}
SENSOR_ALIASES = {'app': 'foreground_app', 'apps': 'foreground_app', 'application': 'foreground_app', 'window': 'foreground_app',
                  'foreground': 'foreground_app', 'presence': 'user_presence', 'idle': 'user_presence', 'file': 'files',
                  'project': 'files', 'task': 'tasks', 'computer': 'system', 'hardware': 'system', 'resource': 'system'}
TTL = {'system': 30., 'user_activity': 120., 'application': 120., 'task': 3600., 'project': 86400., 'external': 1800., 'jarvis': 600.}
QUIET_STATES = {'RECEIVED', 'CLASSIFYING', 'QUEUED', 'READY', 'RUNNING', 'VERIFYING'}
STATUS = ('observing', 'interpreting', 'investigating', 'predicting', 'planning', 'executing', 'verifying', 'learning',
          'waiting for approval', 'idle')
ROUTINE = ('Investigate in the background', 'Just keep me informed', 'Ignore this')


def idle_seconds():
    """Seconds since the last keyboard/mouse input (no content is read); None when unavailable."""
    if os.name != 'nt':
        return None
    class LastInput(ctypes.Structure):
        _fields_ = [('size', ctypes.c_uint), ('time', ctypes.c_uint)]
    info = LastInput(ctypes.sizeof(LastInput), 0)
    try:
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return None
        return max(0., (ctypes.windll.kernel32.GetTickCount() - info.time) / 1000.)
    except (AttributeError, OSError):
        return None


def task_subject(kind):
    return 'planned task' if kind == 'task' else kind.replace('_', ' ') + ' task'


def _number(options, key, default, low, high, kind=(int, float)):
    value = options.get(key, default)
    if value is None and default is None:
        return None
    if type(value) not in kind or not low <= value <= high:
        raise ValueError('Invalid awareness.' + key)
    return value


def _redact(text):
    from .cloud_policy import SECRET
    return SECRET.sub('[redacted]', str(text))


class AwarenessEngine:
    def __init__(self, actions, options=None, clock=time.time, store_path=None, sampler=None, probe_models=None):
        self.actions, self.clock = actions, clock
        options = {} if options is None else options
        if not isinstance(options, dict) or type(options.get('enabled', False)) is not bool:
            raise ValueError('awareness options must be an object with a boolean enabled flag')
        self.options = options
        self.enabled = options.get('enabled', False)
        self.tick = _number(options, 'tick_seconds', 1., .05, 10)
        self.capacity = _number(options, 'event_queue', 512, 16, 5000, (int,))
        self.retention_days = _number(options, 'retention_days', 7, 0, 90)
        self.cpu_budget = _number(options, 'cpu_budget_percent', 2., .1, 50)
        self.max_tasks = _number(options, 'max_tasks_per_hour', 3, 0, 20, (int,))
        self.intervals = {'tasks': _number(options, 'task_poll_seconds', 2., .05, 60),
                          'system': _number(options, 'system_sample_seconds', 10., .05, 600),
                          'gpu': _number(options, 'gpu_sample_seconds', 60., 1, 3600),
                          'files': _number(options, 'file_scan_seconds', 30., .05, 3600),
                          'predict': _number(options, 'predict_seconds', 15., .05, 600),
                          'self_model': _number(options, 'self_model_seconds', 300., 1, 86400),
                          'maintenance': _number(options, 'maintenance_seconds', 60., .05, 3600)}
        self.gpu_need = _number(options, 'gpu_task_vram_mb', None, 64, 65536)
        self.cooldown = _number(options, 'suggestion_cooldown_seconds', 1800, 0, 604800)
        sensors = options.get('sensors', {})
        if not isinstance(sensors, dict) or any(k not in DEFAULT_SENSORS or type(v) is not bool for k, v in sensors.items()):
            raise ValueError('awareness.sensors must map known sensor names to booleans')
        watch = options.get('watch_paths', [])
        if not isinstance(watch, list) or any(not isinstance(p, str) for p in watch) or len(watch) > 20:
            raise ValueError('awareness.watch_paths must be a list of up to 20 folder paths')
        if type(options.get('deliberative_reasoning', False)) is not bool or type(options.get('reprioritize', True)) is not bool:
            raise ValueError('awareness.deliberative_reasoning and reprioritize must be booleans')
        self.attention = AttentionManager(options.get('attention', {}), clock)
        self.curiosity = CuriosityEngine(options.get('curiosity', {}), clock)
        self.policy_options = options
        self.closed = threading.Event()
        self.cond = threading.Condition()
        self.inbox, self.telemetry = deque(), {}
        self.counters = {'observed': 0, 'processed': 0, 'dropped': 0, 'coalesced': 0, 'rejected': 0, 'disabled_sensor': 0,
                         'problems': 0, 'filtered': 0, 'silent': 0, 'notified': 0, 'spoken': 0, 'asked': 0,
                         'investigations': 0, 'proposals': 0, 'model_calls': 0, 'errors': 0}
        self.latency = deque(maxlen=500)
        self.thread, self.restarts, self.last_error = None, 0, None
        self.heartbeat = time.monotonic()
        self.status_word = 'idle'
        self.recent = deque(maxlen=40)
        self.problems = {}
        self.decisions = {}
        self.watching = {}
        self.ram, self.kind_outcomes = deque(maxlen=60), {}
        self.due = {name: 0. for name in self.intervals}
        self.slowdown, self.cpu_window, self.cpu_percent = 1., deque(maxlen=120), 0.
        self.last_assessment = None
        self.sampler = sampler
        self.file_state = {}
        self.last_window = None
        self.store = None
        if not self.enabled:
            return
        self.store = AwarenessStore(Path(store_path or Path(actions.base) / '.jarvis-runtime' / 'awareness.sqlite3'), clock)
        self.sensors = {**DEFAULT_SENSORS, **sensors, **(self.store.setting('sensors', default={}) or {})}
        self.watch_paths = [Path(p) for p in watch]
        self.world, self.beliefs = WorldState(clock), BeliefEngine(clock)
        self.beliefs.load(self.store.setting('beliefs', default={}))
        self.workspace = CognitiveWorkspace(clock)
        self.predictions = PredictionEngine(self.store, clock)
        self.experience = ExperienceEvaluator(self.store, clock)
        self.policy = ProactivePolicyEngine(options, self.experience)
        self.metacognition = MetacognitiveEvaluator()
        self.self_model = SelfModelManager(actions, clock, probe_models)
        self.proactive = self.store.setting('proactive', default=True)
        self.stopped = self.store.setting('stopped', default=False)
        self.focus = self.store.setting('focus', default=False)
        self.curiosity.paused = self.store.setting('exploration_paused', default=False)
        frequency = self.store.setting('interruptions_per_hour')
        if frequency is not None:
            self.attention.budget = frequency
        self.attention.tune(self.experience.policy()['params']['attention_threshold'])
        self.last_seq = self.store.setting('task_seq')

    # --- intake (any thread; never blocks, never raises into the caller) ------------------------------------------
    def sensor_enabled(self, name):
        return self.enabled and not self.closed.is_set() and self.sensors.get(name, False)

    def observe(self, kind, source, category, values, *, sensor, low_value=False, **fields):
        if not self.enabled or self.closed.is_set():
            return False
        if not self.sensor_enabled(sensor):
            self.counters['disabled_sensor'] += 1
            return False
        try:
            observation = Observation(type=kind, source=source, category=category, values=values, at=self.clock(), **fields).validate()
        except (TypeError, ValueError):
            self.counters['rejected'] += 1
            return False
        with self.cond:
            self.counters['observed'] += 1
            if low_value:
                key = (kind, observation.project, observation.application, observation.task)
                if key in self.telemetry:
                    self.counters['coalesced'] += 1
                self.telemetry[key] = observation  # Latest sample wins; low-value telemetry is batched.
                if len(self.telemetry) > self.capacity:
                    self.telemetry.pop(next(iter(self.telemetry)))
                    self.counters['dropped'] += 1
            else:
                if len(self.inbox) >= self.capacity:
                    # Backpressure: shed the least severe pending event, never the caller.
                    weakest = min(self.inbox, key=lambda o: (self._severity(o), o.at))
                    self.counters['dropped'] += 1
                    if (self._severity(observation), observation.at) <= (self._severity(weakest), weakest.at):
                        return False
                    self.inbox.remove(weakest)
                self.inbox.append(observation)
            self.cond.notify()
        return True

    @staticmethod
    def _severity(observation):
        hint = observation.values.get('severity')
        return float(hint) if type(hint) in (int, float) and 0 <= hint <= 1 else severity(observation.type)

    def observe_report(self, kind, message):
        """Existing Jarvis report events (watchdog repairs, warnings, decisions) become observations."""
        if not self.enabled or self.closed.is_set():
            return
        try:
            if kind == 'task_decision' and isinstance(message, dict) and message.get('id') in self.decisions:
                self.observe('jarvis.decision.resolved', 'decision manager', 'jarvis',
                             {'decision': message['id'], 'status': str(message.get('status')), 'signature': message['id']},
                             sensor='jarvis')
                return
            if kind == 'task_report' and isinstance(message, str):
                self.observe('task.report.saved', 'task queue', 'task', {'path': message, 'severity': .1}, sensor='tasks')
                return
            if not isinstance(message, str) or not message or kind not in {'repair', 'warning', 'answer_error', 'fatal'} \
                    and 'alert' not in kind:
                return
            text = _redact(message)[:300]
            connector = self._connector(text)
            if kind == 'repair':
                service = re.split(r' (?:stopped|was|is not|declined|could not)\b', text, 1)[0][:80]
                fixed = 'was stopped and fixed' in text
                # Recovery stays silent (app/AGENTS.md): already in the transcript and repairs.jsonl.
                self.observe('service.recovered' if fixed else 'service.failed', 'watchdog', 'jarvis',
                             {'service': service, 'detail': text, 'signature': service, 'surfaced': True, 'recovery': True},
                             sensor='jarvis', retention='days')
                if connector:
                    self.self_model.note_connector(connector, fixed, text)
            elif 'alert' in kind:
                self.observe('external.alert', kind, 'external', {'detail': text, 'severity': .5, 'signature': text[:60]},
                             sensor='external', sensitivity='private')
            else:
                self.observe('jarvis.' + ('answer.error' if kind == 'answer_error' else kind), 'jarvis', 'jarvis',
                             {'detail': text, 'severity': .7 if kind == 'fatal' else .5, 'signature': text[:60],
                              'connector': connector or '', 'surfaced': True}, sensor='jarvis', retention='days')
                if connector:
                    self.self_model.note_connector(connector, False, text)
        except Exception as exc:  # A failing hook never changes the report path.
            self._fault(exc)

    def _connector(self, text):
        config = getattr(self.actions, 'config', {}) or {}
        names = [k for k, v in config.items() if isinstance(v, dict) and 'enabled' in v] if isinstance(config, dict) else []
        lowered = text.casefold()
        return next((n for n in names if re.search(r'(?<![a-z])' + re.escape(n.casefold()) + r'(?![a-z])', lowered)), '')

    def observe_window(self, title, executable=''):
        """Foreground changes only (opt-in). The title stays in memory; only the executable is ever persisted."""
        if not self.sensor_enabled('foreground_app') or not isinstance(title, str):
            if self.enabled:
                self.counters['disabled_sensor'] += 1
            return
        key = (title[:300], str(executable)[:80])
        if key == self.last_window:
            return
        self.last_window = key
        project = next((p for p in self._known_projects() if p and re.search(r'(?<!\w)' + re.escape(p) + r'(?!\w)', title, re.I)), '')
        self.observe('app.focus.changed', 'foreground window', 'application',
                     {'title': title[:300], 'executable': str(executable)[:80], 'signature': str(executable)[:80],
                      'severity': .05}, sensor='foreground_app', low_value=True, sensitivity='private',
                     application=str(executable)[:80], project=project)

    def observe_build(self, project, ok, detail='', kind='build'):
        """Connector/tool hook for builds and tests: project.<kind>.passed|failed."""
        kind = re.sub(r'[^a-z0-9_]', '_', str(kind).casefold())[:20] or 'build'
        return self.observe(f'project.{kind}.{"passed" if ok else "failed"}', 'project tools', 'project',
                            {'detail': _redact(detail)[:300], 'signature': kind}, sensor='files', project=str(project)[:80],
                            retention='days')

    def observe_external(self, name, values, sensitivity='private'):
        return self.observe('external.' + re.sub(r'[^a-z0-9_]', '_', str(name).casefold())[:30], name, 'external',
                            dict(values), sensor='external', sensitivity=sensitivity)

    # --- worker -----------------------------------------------------------------------------------------------------
    def start(self):
        if self.enabled and self.thread is None:
            self.thread = threading.Thread(target=self._run, name='Jarvis cognitive awareness', daemon=True)
            self.thread.start()
        return self

    def healthy(self):
        return not self.enabled or bool(self.thread and self.thread.is_alive() and time.monotonic() - self.heartbeat < 60)

    def repair(self):
        if not self.enabled or self.closed.is_set():
            return True
        if self.thread and self.thread.is_alive():
            return time.monotonic() - self.heartbeat < 60
        if self.restarts >= 3:
            return False  # Bounded; ordinary Jarvis keeps working without this layer.
        self.restarts += 1
        self.thread = threading.Thread(target=self._run, name='Jarvis cognitive awareness', daemon=True)
        self.thread.start()
        return True

    def close(self):
        self.closed.set()
        with self.cond:
            self.cond.notify_all()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=3)
        if self.store is not None:
            try:
                self._persist()
                self.store.close()
            except Exception:
                pass

    def _fault(self, exc):
        self.counters['errors'] += 1
        self.last_error = type(exc).__name__ + ': ' + str(exc)[:160]

    def _run(self):
        while not self.closed.is_set():
            self.heartbeat = time.monotonic()
            with self.cond:
                if not self.inbox and not self.telemetry:
                    self.cond.wait(self.tick)
            if self.closed.is_set():
                break
            started = time.thread_time()
            try:
                self.step()
            except Exception as exc:
                self._fault(exc)
            self._budget(time.thread_time() - started)

    def _budget(self, used):
        """Adaptive sampling: stretch every interval when this thread exceeds its CPU budget."""
        now = time.monotonic()
        self.cpu_window.append((now, used))
        window = [u for at, u in self.cpu_window if now - at <= 60]
        span = min(60., max(1., now - self.cpu_window[0][0]))
        percent = 100 * sum(window) / span
        if percent > self.cpu_budget:
            self.slowdown = min(8., self.slowdown * 1.5)
        elif percent < self.cpu_budget / 3:
            self.slowdown = max(1., self.slowdown / 1.25)
        self.cpu_percent = round(percent, 3)

    def _due(self, name):
        now = time.monotonic()
        if now < self.due[name]:
            return False
        heavy = self.world.value('system.cpu_percent', 0) > 85 if name in {'predict', 'files', 'gpu'} else False
        self.due[name] = now + self.intervals[name] * self.slowdown * (3 if heavy else 1)
        return True

    def step(self):
        with self.cond:
            batch = [self.inbox.popleft() for _ in range(min(64, len(self.inbox)))]
            batch += list(self.telemetry.values())
            self.telemetry.clear()
        if batch:
            self.status_word = 'interpreting'
        for observation in batch:
            try:
                self._process(observation)
            except Exception as exc:
                self._fault(exc)
        for name, run in (('tasks', self._tail_tasks), ('system', self._sample_system), ('gpu', self._sample_gpu),
                          ('files', self._scan_files), ('predict', self._predict), ('self_model', self._refresh_self),
                          ('maintenance', self._maintenance)):
            if self._due(name):
                try:
                    run()
                except Exception as exc:
                    self._fault(exc)
        if not batch and self.status_word not in {'waiting for approval'}:
            self.status_word = 'observing' if any(self.sensors.values()) else 'idle'

    # --- sensors ----------------------------------------------------------------------------------------------------
    def _ingress(self):
        ingress = getattr(self.actions, 'ingress', None)
        from .task_ingress import TaskIngress
        return ingress if isinstance(ingress, TaskIngress) or getattr(ingress, 'awareness_compatible', False) else None

    def _tail_tasks(self):
        """Read the durable task event log incrementally; the queue itself is not modified or slowed."""
        if not self.sensor_enabled('tasks'):
            return
        ingress = self._ingress()
        if ingress is None:
            return
        store = ingress.store
        with store.lock:
            if self.last_seq is None:
                # First start: begin at the present. History is not replayed as new events.
                self.last_seq = store.db.execute('SELECT coalesce(max(seq),0) FROM events').fetchone()[0]
                self.store.setting('task_seq', self.last_seq)
                return
            rows = store.db.execute('SELECT e.seq, e.task, e.state, e.detail, t.number, t.command, t.spec, t.idem, '
                                    't.checkpoint, t.state AS current FROM events e JOIN tasks t ON t.id=e.task '
                                    'WHERE e.seq>? ORDER BY e.seq LIMIT 200', (self.last_seq,)).fetchall()
        for row in rows:
            self.last_seq = row['seq']
            command, spec = json.loads(row['command']), json.loads(row['spec'])
            origin = 'cognitive' if str(row['idem']).startswith('cognitive:') else ''
            state = row['state']
            values = {'number': row['number'], 'kind': command['kind'], 'state': state, 'detail': _redact(row['detail'])[:200],
                      'instruction': command.get('value', '')[:160], 'signature': command['kind'] + ':' + state,
                      'dependencies': spec.get('dependencies', [])}
            if state == 'COMPLETED' and json.loads(row['checkpoint']).get('task_result', {}).get('verified'):
                values['verified'] = True
            self.observe('task.' + state.lower(), 'task queue', 'task', values, sensor='tasks', task=row['task'],
                         low_value=state in QUIET_STATES, sensitivity='private', origin=origin)
        if rows:
            self.store.setting('task_seq', self.last_seq)

    def _sample(self):
        if self.sampler is not None:
            return self.sampler()
        import psutil
        battery = psutil.sensors_battery()
        try:
            disk = psutil.disk_usage(str(Path(self.actions.base).anchor or '/')).percent
        except OSError:
            disk = None
        return {'cpu_percent': psutil.cpu_percent(), 'ram_available_mb': psutil.virtual_memory().available / 1048576,
                'battery_percent': battery.percent if battery else None,
                'on_battery': (not battery.power_plugged) if battery else None, 'disk_percent': disk,
                'idle_seconds': idle_seconds() if self.sensors.get('user_presence') else None}

    def _sample_system(self):
        if not self.sensor_enabled('system'):
            return
        sample = self._sample()
        now = self.clock()
        reserve = (getattr(self.actions, 'config', {}) or {}).get('task_queue', {}).get('reserve_ram_mb', 1024)
        for key, value in sample.items():
            if value is None or key == 'idle_seconds':
                continue  # Unknown stays unknown.
            self.world.set('P', 'system.' + key, value, 'psutil', ttl=TTL['system'] * 3)
        if sample.get('ram_available_mb') is not None:
            self.ram.append((now, sample['ram_available_mb']))
            if sample['ram_available_mb'] < reserve:
                self.predictions.resolve('resource_exhaustion', 'RAM available MB', True, 'Observed below reserve')
                self.observe('system.ram.low', 'psutil', 'system', {'available_mb': round(sample['ram_available_mb']),
                             'reserve_mb': reserve, 'signature': 'ram'}, sensor='system', retention='days')
        if sample.get('on_battery') and sample.get('battery_percent') is not None and sample['battery_percent'] < 20:
            self.observe('system.battery.low', 'psutil', 'system', {'percent': sample['battery_percent'], 'signature': 'battery'},
                         sensor='system')
        if sample.get('disk_percent') is not None and sample['disk_percent'] > 95:
            self.observe('system.disk.pressure', 'psutil', 'system', {'percent': sample['disk_percent'], 'signature': 'disk'},
                         sensor='system', retention='days')
        idle = sample.get('idle_seconds')
        if self.sensors.get('user_presence') and idle is not None:
            self.world.set('U', 'user.idle_seconds', idle, 'GetLastInputInfo', ttl=TTL['user_activity'])
            self.world.set('U', 'user.active', idle < 120, 'GetLastInputInfo', provenance='inferred', confidence=.8, ttl=TTL['user_activity'])

    def _sample_gpu(self):
        if not self.sensor_enabled('system'):
            return
        if self.sampler is not None:
            gpu = self.sampler().get('gpu')
        else:
            from .gpu_scheduler import memory
            gpu = memory()
        if gpu:
            self.world.set('P', 'system.vram_free_mb', gpu['total_mb'] - gpu['used_mb'], 'nvidia-smi', ttl=self.intervals['gpu'] * 3)
            self.world.set('P', 'system.vram_total_mb', gpu['total_mb'], 'nvidia-smi', ttl=86400)

    def _scan_files(self):
        """Opt-in watched folders: bounded mtime scan, no file contents read."""
        if not self.sensor_enabled('files') or not self.watch_paths:
            return
        for root in self.watch_paths:
            newest, count = 0., 0
            try:
                for path in root.rglob('*'):
                    if any(part in {'.git', '__pycache__', 'node_modules', '.jarvis-runtime', '.venv'} for part in path.parts):
                        continue
                    count += 1
                    if count > 5000:
                        break
                    if path.is_file():
                        newest = max(newest, path.stat().st_mtime)
            except OSError:
                self.world.set('A', 'project.' + root.name + '.watch', 'unavailable', 'file scan', ttl=600)
                continue
            previous = self.file_state.get(root)
            self.file_state[root] = newest
            if previous is not None and newest > previous:
                self.observe('project.file.changed', 'file scan', 'project', {'severity': .2, 'signature': root.name, 'mtime': newest},
                             sensor='files', project=root.name, retention='days')

    # --- interpretation -----------------------------------------------------------------------------------------------
    def _process(self, observation):
        self.counters['processed'] += 1
        self.latency.append(max(0., self.clock() - observation.at))
        facet, sev = observation.facet, self._severity(observation)
        subject = self._subject(observation)
        self.world.set(facet, observation.type + ':' + subject, observation.values, observation.source,
                       confidence=observation.confidence, provenance=observation.provenance,
                       ttl=TTL[observation.category], sensitivity=observation.sensitivity)
        self.store.put_observation(observation, self.retention_days)
        self.workspace.put('observations', observation.fingerprint(),
                           {'type': observation.type, 'subject': subject, 'at': observation.at,
                            **({} if observation.sensitivity == 'private' else {'values': observation.public_values()})},
                           sev, observation.sensitivity)
        if observation.type == 'jarvis.decision.resolved':
            return self._decision_resolved(observation.values['decision'])
        if observation.type == 'task.report.saved':
            try:
                self.write_report_companion(observation.values['path'])
            except (OSError, ValueError) as exc:
                self._fault(exc)
            return
        if observation.type.startswith('task.'):
            self._task_event(observation, subject)
        if observation.type.startswith('project.'):
            self._project_event(observation)
        if observation.type.startswith('app.focus') and observation.project:
            self.beliefs.update('user_state:working_on:' + observation.project, 2., 'foreground window',
                                kind='user_state', prior=.2, half_life=1800)
            self.world.set('A', 'project.active', observation.project, 'foreground window', provenance='inferred',
                           confidence=.6, ttl=1800)
        if sev >= .6:
            self.beliefs.update('problem:' + subject, 3., observation.source, observation.type)
        elif sev <= .15 and observation.type.split('.')[-1] in {'completed', 'passed', 'recovered', 'succeeded'}:
            if self.beliefs.probability('problem:' + subject) is not None:
                self.beliefs.update('problem:' + subject, 1 / 3., observation.source, observation.type)
        if subject in self.watching and self.watching[subject] > self.clock():
            sev = min(1., sev + .15)  # Monitored subjects get a little more attention.
        if sev >= .4 and observation.type not in {'task.report.saved'}:
            self._consider(self._problem(observation, sev, subject))

    @staticmethod
    def _subject(observation):
        values = observation.values
        if observation.category == 'task':
            return task_subject(values.get('kind', 'task'))
        parts = observation.type.split('.')
        return str(values.get('service') or values.get('component') or observation.project or observation.application
                   or values.get('connector') or (parts[1] if len(parts) > 1 else observation.source))[:80]

    def _task_event(self, observation, subject):
        values, state = observation.values, observation.values['state']
        if state in {'COMPLETED', 'FAILED', 'CANCELLED', 'PARTIAL'}:
            history = self.kind_outcomes.setdefault(subject, deque(maxlen=12))
            if observation.origin != 'cognitive':
                history.append((self.clock(), state == 'COMPLETED'))
            self.predictions.resolve('repeated_failure', subject, state == 'FAILED', 'Next attempt ' + state)
            for row in self.store.open_predictions():
                if row['kind'] == 'dependency_blocker' and row.get('upstream') == observation.task:
                    self.predictions.resolve('dependency_blocker', row['subject'], state != 'COMPLETED', 'Prerequisite ' + state)
                if row['kind'] == 'deadline_risk' and row['subject'] == observation.task:
                    ingress = self._ingress()
                    task = ingress.store.get(observation.task) if ingress else None
                    late = bool(task and task['spec'].get('deadline') and self.clock() > task['spec']['deadline'])
                    self.predictions.resolve('deadline_risk', observation.task, late or state != 'COMPLETED', 'Finished ' + state)
            if observation.origin != 'cognitive':
                self._assess(observation)  # "That result" means the user's work, not an investigation.
        if state == 'WAITING_APPROVAL':
            self.status_word = 'waiting for approval'
        if observation.origin == 'cognitive' and state in {'COMPLETED', 'FAILED', 'CANCELLED', 'PARTIAL'}:
            for suggestion in self.store.suggestions(since=self.clock() - 86400):
                if suggestion.get('task') == observation.task and suggestion['status'] in {'submitted', 'accepted'}:
                    self.store.update_suggestion(suggestion['id'], status='investigated' if state == 'COMPLETED' else 'investigation_' + state.lower(),
                                                 verified=bool(values.get('verified')))

    def _assess(self, observation):
        ingress = self._ingress()
        task = ingress.store.get(observation.task) if ingress else None
        if not task:
            return
        cognition = getattr(self.actions, 'cognition', None)
        estimate = None
        if cognition is not None:
            try:
                estimate = cognition.procedure_stats(task['command']['kind']).get('mean_seconds') or None
            except Exception:
                estimate = None
        assessment = self.metacognition.assess(task, estimate)
        self.workspace.put('outcomes', observation.task, {'task': task['number'], 'state': task['state'], **assessment},
                           .5 if assessment['task_success'] is not False else .8, 'internal')
        self.last_assessment = {'task': task['number'], 'kind': task['command']['kind'], **assessment, 'at': self.clock()}
        failures = sum(1 for _, ok in self.kind_outcomes.get(task_subject(task['command']['kind']), ()) if not ok)
        if failures in {3, 6, 12} and self.metacognition.reflection_needed(failures) and task['state'] == 'FAILED' and cognition is not None:
            self.status_word = 'learning'
            lesson = (f"{task['command']['kind']} tasks failed {failures} times recently; latest: "
                      + _redact(task['outcome'])[:120])
            if lesson not in (self.store.setting('lessons', default=[]) or []):
                self.store.setting('lessons', ((self.store.setting('lessons', default=[]) or []) + [lesson])[-20:])
                try:
                    cognition.consolidate('Awareness: ' + lesson)  # Existing Obsidian lesson path.
                except Exception as exc:
                    self._fault(exc)

    def _project_event(self, observation):
        project, kind = observation.project, observation.type
        key = 'project:' + project
        if kind.endswith('.passed') and '.test' in kind:
            self.world.set('A', key + ':last_test_pass', observation.at, 'project tools', ttl=86400 * 30)
            self.predictions.resolve('stale_verification', project, False, 'Tests passed again')
        if kind.endswith('.failed') and '.test' in kind:
            self.predictions.resolve('stale_verification', project, True, 'Tests failed after the change')
        if kind == 'project.file.changed':
            self.world.set('A', key + ':last_change', observation.at, 'file scan', ttl=86400 * 30)

    def _known_projects(self):
        ingress = self._ingress()
        names = set()
        if ingress is not None:
            try:
                names |= {g['project'] for g in ingress.scheduler.graph.groups() if g.get('project')}
            except Exception:
                pass
        names |= {p.name for p in getattr(self, 'watch_paths', [])}
        return sorted(names, key=len, reverse=True)

    def _goals(self):
        """Active goals: running/queued user tasks, active workflow groups, the cognition goal and focus project."""
        goals = []
        ingress = self._ingress()
        if ingress is not None:
            for row in ingress.store.rows(active=True)[-20:]:
                if not str(row.get('idem', '')).startswith('cognitive:'):
                    goals.append({'task': row['id'], 'text': row['command'].get('value') or row['command']['kind'],
                                  'priority': row['spec'].get('priority', 0)})
        cognition = getattr(self.actions, 'cognition', None)
        if cognition is not None:
            try:
                goal = cognition.working_memory().get('goal')
                if goal:
                    goals.append({'task': '', 'text': goal, 'priority': 0})
            except Exception:
                pass
        project = self.world.value('project.active')
        if project:
            goals.append({'task': '', 'text': project, 'priority': 0})
        for goal in goals[:5]:
            self.workspace.put('goals', goal['task'] or goal['text'][:40], {'text': goal['text'][:120]}, .5 + goal['priority'] / 200, 'private')
        return goals

    def _problem(self, observation, sev, subject):
        values, goals = observation.values, self._goals()
        relevance = max([overlap(subject + ' ' + str(values.get('instruction', '')) + ' ' + observation.project, g['text'])
                         for g in goals] or [0.])
        related_task = observation.task if observation.category == 'task' else values.get('task', '')
        if related_task and any(g['task'] == related_task for g in goals):
            relevance = 1.
        elif observation.category == 'task' and observation.origin != 'cognitive':
            relevance = max(relevance, .7)  # The user asked for this task.
        if observation.project and observation.project == self.world.value('project.active'):
            relevance = max(relevance, .8)
        if observation.category in {'system', 'jarvis'}:
            relevance = max(relevance, .5)  # Jarvis's own health always matters to every goal.
        p = self.beliefs.probability('problem:' + subject)
        evidence = self.beliefs.evidence('problem:' + subject)
        observed = [self._describe(observation)]
        inferred, uncertain = [], []
        if p is not None and len(evidence) >= 2 and p >= .5:
            inferred.append((f'{subject} has an ongoing problem ({len(evidence)} related signals)', p))
        if self.beliefs.contradictory('problem:' + subject):
            uncertain.append('whether it is still happening: recent evidence conflicts')
        if observation.confidence < .7:
            uncertain.append('about this observation; its source reports low reliability')
        fingerprint = observation.fingerprint()
        dependents = 0
        ingress = self._ingress()
        if related_task and ingress is not None:
            # Goal significance: how much other admitted work waits on this task.
            dependents = sum(related_task in r['spec'].get('dependencies', []) for r in ingress.store.rows(active=True))
        problem = {'id': uuid.uuid4().hex, 'fingerprint': fingerprint, 'situation': observation.type, 'subject': subject,
                   'severity': sev, 'relevance': round(relevance, 3), 'confidence': observation.confidence,
                   'goal': min(1., .3 + .2 * dependents) if related_task else .3,
                   'observed': observed, 'inferred': inferred, 'uncertain': uncertain, 'origin': observation.origin,
                   'task': related_task, 'project': observation.project, 'at': observation.at, 'novel': True,
                   'investigable': sev >= .6 and bool(subject), 'recommendation': 'look into the cause in the background',
                   'recovery': bool(values.get('recovery'))}
        # Already shown to the user (warnings) or handled by the watchdog (repairs): only a recurring
        # problem is worth more than updating beliefs.
        recurring = p is not None and p >= .9
        problem['handled'] = self._handled(problem) or bool(values.get('surfaced') and not recurring)
        return problem

    @staticmethod
    def _describe(observation):
        values = observation.values
        if observation.category == 'task':
            return f"task #{values.get('number')} ({values.get('kind')}) is now {values.get('state', '').lower().replace('_', ' ')}" + (
                f": {values['detail']}" if values.get('detail') else '')
        if values.get('detail'):
            return values['detail']
        shown = {k: v for k, v in observation.public_values().items() if k not in {'signature', 'severity'}}
        return observation.type.replace('.', ' ') + (' (' + ', '.join(f'{k} {v}' for k, v in list(shown.items())[:3]) + ')' if shown else '')

    def _handled(self, problem):
        """Existing equivalent work: an open suggestion, a queued investigation or a matching user task."""
        recent = self.store.suggestions(since=self.clock() - self.cooldown, limit=200)
        if any(s['fingerprint'] == problem['fingerprint'] and s['status'] in {'submitted', 'proposed', 'asked', 'accepted', 'notified'}
               for s in recent):
            return True
        if problem.get('investigable') and any(s['subject'] == problem['subject'] and s['action'] == 'investigate'
                                               and s['status'] in {'submitted', 'accepted', 'investigated'} for s in recent):
            return True  # The same subject was just investigated through another signal.
        ingress = self._ingress()
        if ingress is not None:
            for row in ingress.store.rows(active=True):
                if str(row.get('idem', '')).startswith('cognitive:' + problem['fingerprint']):
                    return True
                if row['id'] != problem['task'] and row['state'] in {'RUNNING', 'QUEUED'} and \
                        overlap(problem['subject'] + ' ' + problem['project'], row['command'].get('value', '')) >= .5:
                    return True
        return False

    def _context(self):
        ingress = self._ingress()
        hour = time.localtime(self.clock()).tm_hour
        queue = (getattr(self.actions, 'config', {}) or {}).get('task_queue', {})
        start, end = self.options.get('quiet_start_hour', queue.get('quiet_start_hour', 22)), \
            self.options.get('quiet_end_hour', queue.get('quiet_end_hour', 8))
        quiet = (hour >= start or hour < end) if start > end else start <= hour < end
        spent = sum(1 for s in self.store.suggestions(since=self.clock() - 3600) if s.get('task'))
        cpu = self.world.value('system.cpu_percent', 0) or 0
        return {'proactive': self.proactive, 'stopped': self.stopped, 'quiet': quiet and self.options.get('quiet_hours', True),
                'focus': self.focus, 'user_active': bool(self.world.value('user.active', False)),
                'task_budget': (self.max_tasks - spent) if ingress is not None else 0,
                'decisions': ingress is not None and self.options.get('decisions', True),
                'resource_pressure': max(0., min(1., (cpu - 50) / 50)),
                'interruption_scale': self.experience.policy()['params']['interruption_scale']}

    def _consider(self, problem):
        self.counters['problems'] += 1
        salience, selected, parts = self.attention.score(problem['fingerprint'], problem['relevance'], problem['severity'],
                                                         problem['confidence'], problem['goal'])
        problem['novel'] = parts['novelty'] > .5
        problem.update(salience=salience, salience_parts=parts)
        if not selected:
            self.counters['filtered'] += 1
            return None
        self.status_word = 'planning'
        context = self._context()
        best, rows = self.policy.choose(problem, context)
        problem.update(choice=best['action'], utilities=rows[:6], context={k: context[k] for k in ('quiet', 'focus', 'user_active', 'stopped', 'proactive')})
        self.problems[problem['id']] = problem
        while len(self.problems) > 200:
            self.problems.pop(next(iter(self.problems)))
        self.workspace.put('problems', problem['fingerprint'], {'subject': problem['subject'], 'summary': problem['observed'][0][:160],
                           'choice': best['action']}, salience, 'internal')
        action = best['action']
        if action == 'investigate':
            # Curiosity gate: only worth it when the expected information gain and goal benefit exceed the cost.
            belief = self.beliefs.probability('problem:' + problem['subject'])
            pick = self.curiosity.choose([{'id': problem['id'], 'belief': belief,
                                           'goal_benefit': problem['severity'] * problem['relevance'],
                                           'resource_cost': .3 * context['resource_pressure'], 'risk_cost': .01,
                                           'goal_directed': problem['relevance'] >= .5}], idle=not context['user_active'])
            problem['exploration'] = pick and pick['exploration_value']
            if pick is None:
                action = next((r['action'] for r in rows if r['action'] not in {'investigate', 'ask', 'execute_authorized'} and r['q'] > 0), 'ignore')
                problem['choice'] = action
        self.recent.append({'at': self.clock(), 'problem': problem['id'], 'subject': problem['subject'],
                            'choice': action, 'q': best['q'], 'salience': salience})
        self._act(problem, action)
        return problem

    # --- responses ------------------------------------------------------------------------------------------------
    def _suggest(self, problem, action, status, message, **extra):
        row = {'id': uuid.uuid4().hex, 'fingerprint': problem['fingerprint'], 'situation': problem['situation'],
               'action': action, 'created': self.clock(), 'status': status, 'message': _redact(message)[:600],
               'explanation': {k: problem.get(k) for k in ('observed', 'inferred', 'uncertain', 'salience', 'salience_parts',
                                                           'utilities', 'context', 'relevance', 'severity', 'handled')},
               'subject': problem['subject'], 'problem': {k: problem.get(k) for k in ('subject', 'task', 'project', 'situation', 'fingerprint')},
               **extra}
        row['number'] = self.store.add_suggestion(row)
        return row

    def _notify(self, problem, message, speak, number=None):
        speak = speak and not problem.get('recovery')  # Never a spoken repair announcement.
        allowed, reason = self.attention.may_interrupt(problem['fingerprint'], quiet=self._context()['quiet'], focus=self.focus,
                                                       critical=problem['severity'] >= .9) if speak else (False, '')
        speak = speak and allowed
        if speak:
            self.attention.note_interrupt(problem['fingerprint'])
        self.counters['spoken' if speak else 'notified'] += 1
        try:
            self.actions.report('awareness', {'text': message, 'speak': speak, 'number': number, 'subject': problem['subject'],
                                              'withheld': reason, 'recovery': bool(problem.get('recovery'))})
        except Exception as exc:
            self._fault(exc)
        return speak

    def _act(self, problem, action):
        if action in {'ignore', 'remember'}:
            self.counters['silent'] += 1
            return
        if action == 'monitor':
            self.watching[problem['subject']] = self.clock() + 3600
            self.counters['silent'] += 1
            return
        if action == 'investigate':
            return self._investigate(problem)
        if action == 'ask':
            return self._ask(problem)
        if action == 'request_approval':
            row = self._suggest(problem, action, 'proposed', compose(problem, action), remedy=problem['remedy'])
            self.counters['proposals'] += 1
            self._notify(problem, row['message'] + f" Say 'accept suggestion {row['number']}' to queue it; normal approvals still apply.",
                         True, row['number'])
            return
        if action == 'execute_authorized':
            return self._investigate(problem, Command(*problem['remedy']['command']))
        message = compose(problem, action)
        if problem.get('remedy'):
            # A remedy offered without interrupting: the user can still accept it later.
            row = self._suggest(problem, action, 'proposed', message, remedy=problem['remedy'])
            self.counters['proposals'] += 1
            message += f" Say 'accept suggestion {row['number']}' to queue it; normal approvals still apply."
        else:
            row = self._suggest(problem, action, 'notified', message)
        self._notify(problem, message, action == 'speak', row['number'])

    def _investigate(self, problem, command=None):
        from .engineering_judgment import engine_for
        engineering = engine_for(self.actions)
        if engineering:
            judgment = engineering.assess_proposal(problem['subject'], evidence=problem.get('observed', []), active_goal=problem.get('task'))
            # Reference assessment only; existing awareness autonomy/consent remains authoritative.
            problem = {**problem, 'engineering': judgment}
        ingress = self._ingress()
        if ingress is None:
            return None
        self.status_word = 'investigating'
        row = self._suggest(problem, 'investigate', 'submitted', '', task=None,
                            **({'engineering': problem['engineering']} if problem.get('engineering') else {}))
        command = command or Command('jarvis_status', 'awareness:investigate:' + row['id'])
        workflow = None
        if problem.get('task'):
            node = ingress.scheduler.graph.node(problem['task'])
            workflow = node['workflow'] if node else None  # Attach to the same goal group.
        key = 'cognitive:' + problem['fingerprint'] + ':' + str(int(self.clock() // max(1, self.cooldown)))
        identity = ingress.submit(command, idempotency_key=key, workflow=workflow)
        self.store.update_suggestion(row['id'], task=identity, status='submitted' if identity else 'rejected',
                                     message=f"Queued a read-only investigation of {problem['subject']}")
        if identity:
            self.counters['investigations'] += 1
            if self.options.get('deliberative_reasoning', False) and problem.get('novel') and                     not self.experience.mean(problem['situation'], 'investigate')[1]:
                # Tier 3 only for unfamiliar problems, as an ordinary scheduler question. Only structural,
                # non-private fields are included; existing routing/privacy policy decides the model.
                question = (f"An automated Jarvis monitor saw a {problem['situation'].replace('.', ' ')} event about "
                            f"'{problem['subject'][:60]}' (severity {problem['severity']:.1f}). List the most likely general causes "
                            'and safe read-only checks. Do not take actions.')
                if ingress.submit(Command('ask', question), idempotency_key=key + ':deliberate'):
                    self.counters['model_calls'] += 1
        return identity

    def _ask(self, problem):
        ingress = self._ingress()
        rows = {r['action']: r['q'] for r in problem.get('utilities', [])}
        usefulness, samples = self.experience.mean(problem['situation'], 'investigate')
        recommended = 0 if rows.get('investigate', -1) >= rows.get('notify_silent', -1) else 1
        # Confidence comes from rated outcomes for this situation, never from a model's self-report.
        confidence = usefulness if samples >= 5 else .6
        identity = ingress.decisions.create(problem.get('task') or None, 'Routine choice: ' + problem['subject'][:60],
                                            list(ROUTINE), recommended, confidence, reversible=True, sensitive=False)
        message = compose(problem, 'ask')
        row = self._suggest(problem, 'ask', 'asked', message, decision=identity)
        self.decisions[identity] = row['id']
        self.counters['asked'] += 1
        try:
            self.actions.report('task_decision', {'id': identity, 'status': 'PENDING'})  # The Queue view presents it; its timer starts then.
        except Exception as exc:
            self._fault(exc)
        self._notify(problem, message, False, row['number'])

    def _decision_resolved(self, identity):
        ingress = self._ingress()
        suggestion = self.store.suggestion(self.decisions.get(identity))
        if ingress is None or suggestion is None or suggestion['status'] != 'asked':
            return
        decision = next((d for d in ingress.decisions.rows() if d['id'] == identity), None)
        if not decision or decision['status'] == 'PENDING':
            return
        self.decisions.pop(identity, None)
        if decision['status'] != 'SELECTED':
            self.store.update_suggestion(suggestion['id'], status='deferred', decision_status=decision['status'])
            return
        choice, automatic = decision['choice'], decision.get('automatic', False)
        self.store.update_suggestion(suggestion['id'], status='decided', choice=ROUTINE[choice], automatic=automatic)
        if not automatic:
            self.experience.record(suggestion['situation'], 'ask', choice != 2, 1.)
        if suggestion.get('routine'):
            return self._apply_routine(suggestion, choice, automatic)
        problem = self.problems.get(next((k for k, v in self.problems.items() if v['fingerprint'] == suggestion['fingerprint']), ''))
        if choice == 0 and problem and (not automatic or self._context()['task_budget'] > 0):
            problem['handled'] = False
            self.store.update_suggestion(suggestion['id'], status='accepted')
            self._investigate(problem)

    # --- predictions --------------------------------------------------------------------------------------------------
    def _predict(self):
        self.status_word = 'predicting'
        ingress = self._ingress()
        config = getattr(self.actions, 'config', {}) or {}
        reserve = config.get('task_queue', {}).get('reserve_ram_mb', 1024)
        found = []
        if len(self.ram) >= 4:
            found.append(self.predictions.resource_exhaustion('RAM available MB', list(self.ram)[-12:], reserve))
        if ingress is not None:
            from .task_policy import score
            now, rows = self.clock(), ingress.store.rows(active=True)
            tasks = [{'id': r['id'], 'number': r['number'], 'state': r['state'], 'deadline': r['spec'].get('deadline'),
                      'duration_seconds': r['spec'].get('duration_seconds', 300), 'score': score(r, now),
                      'dependencies': r['spec'].get('dependencies', []),
                      'vram_mb': self.gpu_need if (r['spec'].get('resources') or {}).get('gpu') and r['state'] in {'QUEUED', 'READY', 'WAITING_DEPENDENCY'}
                      and not r['spec'].get('explicit_priority') else None} for r in rows]
            dependencies = {d for t in tasks for d in t['dependencies']}
            upstream = [ingress.store.get(d) for d in dependencies]
            context = tasks + [{'id': u['id'], 'number': u['number'], 'state': u['state'], 'dependencies': []}
                               for u in upstream if u and u['id'] not in {t['id'] for t in tasks}]
            found += self.predictions.deadline_risk([t for t in tasks if t['state'] not in {'PAUSED'}], now)
            found += self.predictions.dependency_blockers(context)
            free = self.world.value('system.vram_free_mb')
            if self.gpu_need and free is not None:
                found += self.predictions.shortfall('GPU memory', free, tasks, 'vram_mb', 'MB VRAM')
        for subject, history in self.kind_outcomes.items():
            recent = [ok for at, ok in history if self.clock() - at < 86400]
            found.append(self.predictions.repeated_failure(subject, recent.count(False), recent.count(True)))
        for project in self._known_projects():
            found.append(self.predictions.stale_verification(project, self.world.value('project:' + project + ':last_test_pass', fresh=False),
                                                             self.world.value('project:' + project + ':last_change', fresh=False)))
        for prediction in filter(None, found):
            if self.predictions.record(prediction):
                self.workspace.put('predictions', prediction['id'], {k: prediction[k] for k in ('kind', 'subject', 'probability', 'consequence')},
                                   prediction['probability'], 'internal')
                if prediction['probability'] >= .5:
                    self._consider(self._problem_from_prediction(prediction))

    def _problem_from_prediction(self, prediction):
        p = prediction['probability']
        problem = {'id': uuid.uuid4().hex, 'fingerprint': 'prediction:' + prediction['kind'] + ':' + prediction['subject'][:40],
                   'situation': 'prediction.' + prediction['kind'], 'subject': prediction['subject'], 'severity': .45 + .4 * p,
                   'relevance': .8 if prediction.get('task') else .5, 'confidence': p, 'goal': .6 if prediction.get('task') else .4,
                   'observed': prediction['evidence'][:2],
                   'inferred': [(prediction['consequence'] + ('' if prediction['calibrated'] else ' (uncalibrated estimate)'), p)],
                   'uncertain': [] if prediction['calibrated'] else ['how reliable this kind of forecast is yet; it has few checked outcomes'],
                   'origin': '', 'task': prediction.get('task', ''), 'project': '', 'at': prediction['created'], 'novel': True,
                   'investigable': prediction['kind'] in {'repeated_failure', 'dependency_blocker'},
                   'recommendation': prediction['suggestion'][0].lower() + prediction['suggestion'][1:], 'prediction': prediction['id']}
        if prediction['kind'] == 'stale_verification':
            problem['remedy'] = {'command': ('task', 'Run the tests for ' + prediction['subject']), 'read_only': False}
        problem['handled'] = self._handled(problem)
        if prediction['kind'] == 'resource_shortfall' and self.options.get('reprioritize', True) and not problem['handled']:
            self._routine_deferral(problem, prediction)
            problem['handled'] = True
        return problem

    def _routine_deferral(self, problem, prediction):
        """A reversible routine choice through the existing DecisionManager; silence decides only when confident."""
        ingress = self._ingress()
        task = ingress.store.get(prediction['task']) if ingress else None
        if not task or task['state'] not in {'QUEUED', 'READY', 'WAITING_DEPENDENCY'} or task['spec'].get('explicit_priority'):
            return
        deadline = task['spec'].get('deadline')
        if deadline and deadline - self.clock() < 1800:
            return  # Never trade an explicit deadline for a resource heuristic.
        # Measured free VRAM against the configured per-task estimate. A wide gap is a direct comparison,
        # so the reversible deferral may be chosen on timeout; a narrow one stays below the 0.85 auto bar.
        free = self.world.value('system.vram_free_mb')
        wide = free is not None and self.gpu_need and free < .75 * self.gpu_need
        confidence = max(prediction['probability'], .9) if wide else min(prediction['probability'], .8)
        identity = ingress.decisions.create(task['id'], f"Routine choice: postpone task #{task['number']} until GPU memory frees",
                                            [f"Postpone task #{task['number']} for 10 minutes", 'Run it as scheduled', 'Ignore this'],
                                            0, confidence, reversible=True, sensitive=False)
        row = self._suggest(problem, 'ask', 'asked', compose(problem, 'ask'), decision=identity, routine={'task': task['id'], 'seconds': 600})
        self.decisions[identity] = row['id']
        self.counters['asked'] += 1
        self.actions.report('task_decision', {'id': identity, 'status': 'PENDING'})

    def _apply_routine(self, suggestion, choice, automatic):
        ingress = self._ingress()
        routine = suggestion['routine']
        task = ingress.store.get(routine['task'])
        if choice != 0 or not task or task['state'] not in {'QUEUED', 'READY', 'WAITING_DEPENDENCY'}:
            self.store.update_suggestion(suggestion['id'], status='decided', applied=False)
            return
        with ingress.scheduler.lock:
            task = ingress.store.get(routine['task'])
            if task['state'] in {'QUEUED', 'READY', 'WAITING_DEPENDENCY'}:
                spec = {**task['spec'], 'not_before': max(task['spec'].get('not_before', 0), self.clock() + routine['seconds'])}
                ingress.store.transition(task['id'], task['state'], 'Cognitive routine deferral (reversible; '
                                         + ('automatic after timeout' if automatic else 'user selected') + ')', spec=spec)
        self.store.update_suggestion(suggestion['id'], status='applied', applied=True, automatic=automatic)
        self.actions.report('awareness', {'text': f"I postponed task #{task['number']} by {routine['seconds'] // 60} minutes while GPU memory is short; "
                                          'the rest of the queue keeps running.' + (' This was an automatic routine choice.' if automatic else ''),
                                          'speak': False, 'number': suggestion['number'], 'subject': 'GPU memory', 'withheld': ''})

    # --- maintenance ----------------------------------------------------------------------------------------------------
    def _refresh_self(self):
        previous = set(self.self_model.broken())
        missing_before = set(self.self_model.snapshot()['models'].get('missing') or [])
        model = self.self_model.refresh(probe=self.options.get('probe_models', True))
        for name in set(self.self_model.broken()) - previous:
            self.observe('jarvis.component.degraded', 'self model', 'jarvis', {'component': name, 'signature': name, 'service': name},
                         sensor='jarvis')
        for name in set(model['models'].get('missing') or []) - missing_before:
            self.observe('jarvis.model.unavailable', 'self model', 'jarvis', {'model': name, 'signature': name, 'service': name,
                         'detail': f'configured model {name} is not installed'}, sensor='jarvis')

    def _maintenance(self):
        for row in self.predictions.expire():
            self.workspace.remove('predictions', row['id'])
        self.store.purge()
        status, version = self.experience.adapt()
        if status in {'updated', 'rolled_back'}:
            self.attention.tune(version['params']['attention_threshold'])
        self._persist()

    def _persist(self):
        self.store.setting('beliefs', self.beliefs.export())
        if self.last_seq is not None:
            self.store.setting('task_seq', self.last_seq)

    # --- read-only investigation (runs as a scheduler task on the background lane) -------------------------------
    def investigate(self, suggestion_id):
        """Gather evidence from durable state and memory. Verified findings are direct readbacks only."""
        suggestion = self.store.suggestion(suggestion_id) if self.store else None
        if suggestion is None:
            return 'That awareness investigation no longer exists.'
        problem = suggestion['problem']
        findings, hypotheses, sources = [], [], []
        ingress = self._ingress()
        if ingress is not None and problem.get('task'):
            row = ingress.store.get(problem['task'])
            if row:
                findings.append({'claim': f"task #{row['number']} is {row['state']}: {_redact(row['outcome'])[:200]}", 'source': 'task store'})
                retries = [e for e in ingress.store.history(row['id']) if e['state'] in {'RETRY_BACKOFF', 'PAUSED', 'FAILED'}]
                if retries:
                    findings.append({'claim': f'{len(retries)} earlier failure/recovery events for this task', 'source': 'task events'})
                same = [r for r in ingress.store.rows(limit=200) if r['command']['kind'] == row['command']['kind'] and r['state'] == 'FAILED']
                if len(same) > 1:
                    findings.append({'claim': f"{len(same)} recent {row['command']['kind']} tasks failed", 'source': 'task store'})
                hypotheses += self._temporal(row)
        cognition = getattr(self.actions, 'cognition', None)
        subject = problem.get('subject', '')
        task = ingress.store.get(problem['task']) if ingress is not None and problem.get('task') else None
        if cognition is not None:
            kind = task['command']['kind'] if task else subject
            stat = cognition.procedure_stats(kind)
            if stat.get('attempts'):
                findings.append({'claim': f"{kind}: {stat['successes']} of {stat['attempts']} recorded attempts succeeded" +
                                 (f"; last failure: {stat['last_failure'][:120]}" if stat.get('last_failure') else ''),
                                 'source': 'procedure statistics'})
            for lesson in cognition.relevant_lessons(subject, 2):
                hypotheses.append({'claim': 'Earlier lesson: ' + lesson[17:][:160], 'source': 'Obsidian lessons', 'verified': False})
        learning = getattr(self.actions, 'learning', None)
        for name, call in (('ReasoningBank', getattr(learning, 'lessons', None)), ('OpenViking', getattr(learning, 'vault_hits', None))):
            if call is None:
                continue
            try:
                rows = call(subject)[:2]
            except Exception as exc:
                sources.append(name + ' unavailable: ' + type(exc).__name__)
                continue
            for item in rows:
                text = item.get('title') or item.get('summary') or ''
                if text:
                    hypotheses.append({'claim': f'{name}: {str(text)[:160]}', 'source': name, 'verified': False})
        health = self.self_model.broken()
        related = {k: v for k, v in health.items() if overlap(k, subject) > 0}
        if related:
            findings.append({'claim': 'Related component health: ' + ', '.join(f"{k} {v['state']}" for k, v in related.items()), 'source': 'watchdog'})
        verified = bool(findings)
        if ingress is not None and getattr(ingress.scheduler.local, 'identity', None):
            ingress.scheduler.publish_output({'subject': subject, 'hypotheses': hypotheses[:6], 'unavailable_sources': sources},
                                             findings=findings[:8], verified=verified)
        self.store.update_suggestion(suggestion_id, status='investigated', findings=findings[:8], hypotheses=hypotheses[:6], verified=verified)
        lines = [f['claim'] for f in findings[:3]] + ['(unverified) ' + h['claim'] for h in hypotheses[:2]]
        message = (f'Investigated {subject}: ' + '; '.join(lines) + '.') if lines else f'Investigated {subject}: no further evidence was available.'
        problem_view = {'fingerprint': suggestion['fingerprint'], 'subject': subject, 'severity': .5,
                        'recovery': suggestion['situation'].startswith('service.')}
        self._notify(problem_view, message, False, suggestion['number'])
        return ''  # Reported silently through the awareness channel, not spoken as an answer.

    def _temporal(self, row):
        """'This started after X': changes recorded between the last success and the first failure of this kind."""
        if not self.store:
            return []
        kind = row['command']['kind']
        ingress = self._ingress()
        rows = [r for r in ingress.store.rows(limit=200) if r['command']['kind'] == kind and r['state'] in {'COMPLETED', 'FAILED'}]
        last_ok = max((r['updated'] for r in rows if r['state'] == 'COMPLETED'), default=None)
        first_bad = min((r['updated'] for r in rows if r['state'] == 'FAILED' and (last_ok is None or r['updated'] > last_ok)), default=None)
        if last_ok is None or first_bad is None:
            return []
        changes = [o for o in self.store.observations(since=last_ok, kind_prefix='project.') if o['at'] <= first_bad]
        changes += [o for o in self.store.observations(since=last_ok, kind_prefix='service.') if o['at'] <= first_bad]
        if not changes:
            return [{'claim': f'{kind} last succeeded {(first_bad - last_ok) / 60:.0f} minutes before the first failure; no recorded change in between',
                     'source': 'awareness observations', 'verified': True}]
        return [{'claim': f"The failures started after {changes[0]['type'].replace('.', ' ')} ({changes[0].get('project') or changes[0]['source']})",
                 'source': 'awareness observations', 'verified': False}]

    # --- user controls and self-diagnosis -------------------------------------------------------------------------
    def control(self, value):
        if not self.enabled:
            return 'Cognitive awareness is off (config awareness.enabled). Ordinary commands are unaffected.'
        action, _, argument = str(value).partition(':')
        if action in {'on', 'off'}:
            self.proactive = self.store.setting('proactive', action == 'on')
            return 'Proactive awareness is ' + action + '. ' + ('I will still observe, but only speak when asked.' if action == 'off' else '')
        if action == 'stop':
            self.stopped = self.store.setting('stopped', True)
            cancelled = 0
            ingress = self._ingress()
            if ingress is not None:
                for row in ingress.store.rows(active=True):
                    if str(row.get('idem', '')).startswith('cognitive:'):
                        ingress.scheduler.control('cancel', row['id'])
                        cancelled += 1
            return f'Emergency stop: no proactive actions will start, and {cancelled} pending proactive task(s) were cancelled. Say "resume awareness" to continue.'
        if action == 'resume':
            self.stopped = self.store.setting('stopped', False)
            self.proactive = self.store.setting('proactive', True)
            return 'Proactive awareness resumed.'
        if action == 'sensor':
            name, _, state = argument.partition(':')
            name = SENSOR_ALIASES.get(name, name)
            if name not in DEFAULT_SENSORS or state not in {'on', 'off'}:
                return 'Known sensors: ' + ', '.join(DEFAULT_SENSORS) + '.'
            self.sensors[name] = state == 'on'
            self.store.setting('sensors', {k: v for k, v in self.sensors.items()})
            return f"The {name.replace('_', ' ')} sensor is {state}."
        if action == 'focus':
            self.focus = self.store.setting('focus', argument == 'on')
            return 'Focus mode ' + ('on: I will hold suggestions unless something is critical.' if self.focus else 'off.')
        if action == 'exploration':
            self.curiosity.paused = self.store.setting('exploration_paused', argument == 'pause')
            return 'Autonomous exploration ' + ('paused.' if self.curiosity.paused else 'resumed.')
        if action == 'frequency':
            budget = {'low': 2, 'normal': 6, 'high': 12}.get(argument)
            if budget is None:
                return 'Use low, normal or high.'
            self.attention.budget = self.store.setting('interruptions_per_hour', budget)
            return f'At most {budget} interruptions an hour.'
        if action == 'clear':
            category = argument or 'all'
            removed = self.store.purge(category if category in {'all', 'system', 'project', 'task', 'jarvis', 'external', 'application', 'user_activity'} else 'all')
            if category in {'all', 'user_activity', 'application'}:
                with self.world.lock:
                    for key in [k for k, f in self.world.facts.items() if f['facet'] in {'U', 'A'}]:
                        self.world.facts.pop(key, None)
            return f'Cleared {removed} stored observations.'
        if action in {'feedback', 'correct'}:
            kind, _, number = argument.partition(':') if action == 'feedback' else ('wrong', '', argument)
            suggestion = self.store.suggestion(number=int(number)) if number.isdigit() else \
                next(iter(self.store.suggestions(limit=1)), None)
            if suggestion is None:
                return 'There is no suggestion to rate.'
            self.experience.feedback(suggestion, kind)
            self.store.update_suggestion(suggestion['id'], status=suggestion['status'], feedback=kind)
            if kind in {'wrong', 'reject_similar'}:
                self.beliefs.update('problem:' + suggestion['subject'], 1 / 20., 'user', 'User corrected the inference')
            return {'helpful': 'Thanks, noted as helpful.', 'wrong': f"Noted: suggestion {suggestion['number']} was wrong. I lowered my belief in it.",
                    'dismissed': 'Dismissed.', 'reject_similar': f"I won't raise {suggestion['situation'].replace('.', ' ')} situations again unless you ask."}[kind]
        if action == 'accept':
            suggestion = self.store.suggestion(number=int(argument)) if argument.isdigit() else None
            if not suggestion or suggestion['status'] != 'proposed' or not suggestion.get('remedy'):
                return 'That suggestion is not waiting for acceptance.'
            ingress = self._ingress()
            command = Command(*suggestion['remedy']['command'])
            # Accepted by the user: an ordinary user command, so the existing approvals and policies apply.
            identity = ingress.submit(command, idempotency_key='cognitive-accepted:' + suggestion['id']) if ingress else None
            if ingress is None:
                self.actions.submit(command)
            self.store.update_suggestion(suggestion['id'], status='accepted', task=identity)
            self.experience.feedback(suggestion, 'helpful')
            return f"Queued: {command.value or command.kind}."
        return 'Unknown awareness control.'

    def status(self, topic='status'):
        if not self.enabled:
            return 'Cognitive awareness is off (config awareness.enabled). Ordinary commands are unaffected.'
        model = self.self_model.snapshot()
        if topic == 'capabilities':
            if model['refreshed'] is None:
                self._refresh_self()
                model = self.self_model.snapshot()
            caps = model['capabilities']
            installed = model['models']['installed']
            approval = sum(1 for c in caps.values() if c['approval'])
            return (f"{len(caps)} registered tools ({approval} need approval each time); registered means available to plan with, "
                    'not verified for every goal. ' + (f"Installed local models: {', '.join(installed[:6])}." if installed else
                    f"Installed models unknown ({model['models']['probe']}).") +
                    f" Working components: {sum(1 for h in model['health'].values() if h.get('state') == 'ok')}, "
                    f"degraded: {len(self.self_model.broken())}.")
        if topic == 'limitations':
            if model['refreshed'] is None:
                self._refresh_self()
                model = self.self_model.snapshot()
            return 'My current limitations: ' + '; '.join(model['limitations'][:8]) + '.'
        if topic == 'health':
            broken = self.self_model.broken()
            if not broken:
                return 'No component or connector is currently reported failing' + ('' if model['health'] else ' (component health has not been probed yet)') + '.'
            return 'Currently failing or recovering: ' + '; '.join(f"{k} ({v.get('failures', 0)} failures" +
                   (f", last: {v['last_error'][:80]}" if v.get('last_error') else '') + ')' for k, v in broken.items()) + '.'
        if topic == 'why_failed':
            ingress = self._ingress()
            rows = [r for r in (ingress.store.rows(limit=100) if ingress else []) if r['state'] == 'FAILED']
            if not rows:
                return 'No queued task has failed recently.'
            row = rows[-1]
            subject = task_subject(row['command']['kind'])
            p = self.beliefs.probability('problem:' + subject)
            investigated = next((s for s in self.store.suggestions(since=0, limit=50) if s.get('findings') and s['subject'] == subject), None)
            return (f"Task #{row['number']} failed: {_redact(row['outcome'])[:200]}." +
                    (f" My belief that {subject}s have an ongoing problem is {p:.0%}." if p is not None else '') +
                    (' Investigation found: ' + '; '.join(f['claim'] for f in investigated['findings'][:2]) + '.' if investigated else
                     ' I have not investigated it further.'))
        if topic == 'confidence':
            last = getattr(self, 'last_assessment', None)
            if not last:
                return 'I have not assessed a finished task yet.'
            verdict = ('verified by independent evidence' if last['task_success'] else 'failed' if last['task_success'] is False
                       else 'returned by its handler but not independently verified')
            return (f"Task #{last['task']} ({last['kind']}) {verdict}. Whether it achieved your goal is "
                    + ('confirmed by you.' if last['goal_success'] else 'unknown unless you tell me.') +
                    (' ' + '; '.join(last['questions']) + '.' if last['questions'] else ''))
        if topic == 'why':
            rows = [s for s in self.store.suggestions(limit=10) if s.get('explanation')]
            if not rows:
                return 'I have not made a suggestion yet.'
            s = rows[0]
            e = s['explanation']
            chosen = next((u for u in e.get('utilities') or [] if u['action'] == s['action']), None)
            return (f"Suggestion {s['number']} ({s['action'].replace('_', ' ')}) came from: {'; '.join(e.get('observed') or [])[:200]}. "
                    f"Salience {e.get('salience')} from relevance {e.get('relevance')} and severity {e.get('severity')}." +
                    (f" Its utility was {chosen['q']} (benefit {chosen['benefit']}, interruption cost {chosen['interruption']})," if chosen else '') +
                    ' higher than staying silent. Say "that suggestion was wrong" or "don\'t suggest that again" to correct me.')
        if topic == 'predictions':
            rows = sorted(self.store.open_predictions(), key=lambda r: -r['probability'])[:4]
            calibration = self.predictions.report()
            text = ('Open predictions: ' + '; '.join(f"{r['consequence']} ({r['probability']:.0%}{'' if r['calibrated'] else ', uncalibrated'})" for r in rows)
                    if rows else 'No open predictions.')
            if calibration:
                text += ' Checked forecasts: ' + ', '.join(f"{k} {v['n']} (Brier {v['brier']})" for k, v in calibration.items()) + '.'
            return text
        if topic == 'report':
            return json.dumps(self.report_since(self.clock() - 86400), ensure_ascii=False, indent=1)
        recent = list(self.recent)[-3:]
        return (f"Awareness is {self.status_word}; proactive {'on' if self.proactive and not self.stopped else 'off'}"
                + (', focus mode' if self.focus else '') + f". {self.counters['processed']} observations processed, "
                f"{self.counters['filtered']} judged not worth attention, {self.counters['silent']} handled silently, "
                f"{self.counters['notified'] + self.counters['spoken']} notifications, {self.counters['investigations']} investigations queued. "
                + ('Latest: ' + '; '.join(f"{r['subject']} → {r['choice'].replace('_', ' ')}" for r in recent) + '.' if recent else ''))

    def report_since(self, since):
        """The proactive part of a morning report, from persisted suggestions only."""
        rows = self.store.suggestions(since=since, limit=200) if self.store else []
        return {'generated_at': self.clock(), 'since': since,
                'proactive_actions': [{k: s.get(k) for k in ('number', 'action', 'status', 'subject', 'message', 'task', 'verified',
                                                            'automatic', 'feedback')} for s in rows],
                'prediction_calibration': self.predictions.report() if self.store else {},
                'note': 'Only recorded suggestions and their stored outcomes; investigations report verified readbacks separately from unverified memory hits.'}

    def write_report_companion(self, path):
        path = Path(path)
        target = path.with_name(path.stem + '.awareness.json')
        with target.open('x', encoding='utf-8') as stream:
            json.dump(self.report_since(self.store.setting('report_since', default=0) or 0), stream, ensure_ascii=False, indent=2)
        self.store.setting('report_since', self.clock())
        return target

    def snapshot(self):
        """For the Island: operational state, not internal monologue."""
        if not self.enabled:
            return {'enabled': False}
        latest = self.store.suggestions(limit=1)
        predictions = sorted(self.store.open_predictions(), key=lambda r: -r['probability'])[:1]
        latency = sorted(self.latency)
        return {'enabled': True, 'status': self.status_word, 'proactive': self.proactive and not self.stopped, 'stopped': self.stopped,
                'focus': self.focus, 'exploration_paused': self.curiosity.paused, 'sensors': dict(self.sensors),
                'observation': next((o['item'] for o in sorted(self.workspace.slots['observations'].values(), key=lambda r: -r['salience'])
                                     if o['sensitivity'] != 'private'), None),
                'goal': next(iter(self.workspace.view('island', 'private').get('goals', [])), None),  # Local display only.
                'suggestion': latest[0] if latest else None, 'prediction': predictions[0] if predictions else None,
                'warnings': list(self.self_model.broken())[:3], 'counters': dict(self.counters),
                'latency_p50_ms': round(1000 * latency[len(latency) // 2], 2) if latency else None,
                'cpu_percent': getattr(self, 'cpu_percent', None), 'slowdown': self.slowdown, 'error': self.last_error}
