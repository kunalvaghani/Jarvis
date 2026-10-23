"""JCAE reasoning: salience-based attention, a bounded workspace, calibrated predictions and a self-model.

Attention decides what deserves reasoning; it never authorizes an action. Prediction
probabilities are heuristic until enough resolved outcomes exist, then they are
calibrated against those outcomes. The self-model reports what was actually
probed; an unprobed model, connector or tool is 'unknown', never 'available'.
"""
import math
import re
import threading
import time
import uuid
from collections import deque

DEFAULT_WEIGHTS = {'relevance': .30, 'urgency': .25, 'novelty': .20, 'confidence': .15, 'goal': .10}


def words(text):
    return set(re.findall(r'[a-z0-9]{3,}', str(text or '').casefold()))


def overlap(a, b):
    a, b = words(a), words(b)
    return len(a & b) / len(a | b) if a and b else 0.


class AttentionManager:
    """S = w·(R, U, N, C, G) with hysteresis, cooldowns and an interruption budget."""

    def __init__(self, options=None, clock=time.time):
        options = options or {}
        weights = {**DEFAULT_WEIGHTS, **(options.get('weights') or {})}
        if set(weights) != set(DEFAULT_WEIGHTS) or any(type(v) not in (int, float) or v < 0 for v in weights.values()) \
                or not sum(weights.values()):
            raise ValueError('awareness.attention.weights must be non-negative numbers for R, U, N, C and G')
        total = sum(weights.values())
        self.weights = {k: v / total for k, v in weights.items()}  # Tunable heuristic, normalised.
        self.enter = float(options.get('threshold', .45))
        self.exit = float(options.get('exit_threshold', max(0., self.enter - .1)))
        self.cooldown = float(options.get('cooldown_seconds', 900))
        self.budget = int(options.get('interruptions_per_hour', 6))
        self.novelty_half_life = float(options.get('novelty_half_life_seconds', 3600))
        if not 0 < self.enter <= 1 or not 0 <= self.exit <= self.enter or self.cooldown < 0 or not 0 <= self.budget <= 120:
            raise ValueError('Invalid awareness attention thresholds/budget')
        self.clock = clock
        self.lock = threading.RLock()
        self.seen, self.attended, self.last_interrupt = {}, {}, {}
        self.interruptions = deque(maxlen=200)
        self.filtered = 0

    def novelty(self, fingerprint):
        now = self.clock()
        with self.lock:
            count, last = self.seen.get(fingerprint, (0., now))
            effective = count * .5 ** (max(0., now - last) / self.novelty_half_life)
            self.seen[fingerprint] = (effective + 1, now)
            if len(self.seen) > 5000:
                for key in sorted(self.seen, key=lambda k: self.seen[k][1])[:1000]:
                    self.seen.pop(key)
        return 1 / (1 + effective)

    def score(self, fingerprint, relevance, urgency, confidence, goal, novelty=None):
        parts = {'relevance': relevance, 'urgency': urgency, 'confidence': confidence, 'goal': goal,
                 'novelty': self.novelty(fingerprint) if novelty is None else novelty}
        parts = {k: max(0., min(1., float(v))) for k, v in parts.items()}
        salience = sum(self.weights[k] * parts[k] for k in parts)
        with self.lock:
            # Hysteresis: once attended, an item stays until it falls below the lower exit threshold.
            threshold = self.exit if fingerprint in self.attended else self.enter
            selected = salience >= threshold
            if selected:
                self.attended[fingerprint] = self.clock()
            else:
                self.attended.pop(fingerprint, None)
                self.filtered += 1
        return round(salience, 4), selected, parts

    def may_interrupt(self, fingerprint, *, quiet=False, focus=False, critical=False):
        """Separate from salience: whether interrupting the user is allowed now, and why not."""
        now = self.clock()
        with self.lock:
            last = self.last_interrupt.get(fingerprint)
            if last is not None and now - last < self.cooldown:
                return False, 'already raised recently'
            if critical:
                return (not quiet), ('quiet hours' if quiet else '')
            if quiet:
                return False, 'quiet hours'
            if focus:
                return False, 'focus mode'
            recent = sum(1 for at in self.interruptions if now - at < 3600)
            if recent >= self.budget:
                return False, 'hourly interruption budget used'
        return True, ''

    def note_interrupt(self, fingerprint):
        now = self.clock()
        with self.lock:
            self.last_interrupt[fingerprint] = now
            self.interruptions.append(now)

    def tune(self, threshold):
        with self.lock:
            self.enter = max(.2, min(.9, float(threshold)))
            self.exit = max(0., self.enter - .1)


MODULE_SLOTS = {
    'planner': ('goals', 'problems', 'outcomes'), 'scheduler': ('predictions', 'pending', 'goals'),
    'router': ('predictions',), 'memory': ('problems', 'goals'), 'tools': ('problems',),
    'prediction': ('observations', 'beliefs', 'goals'), 'self_model': ('outcomes', 'problems'),
    'policy': ('observations', 'beliefs', 'goals', 'problems', 'predictions', 'pending', 'outcomes'),
    'island': ('observations', 'goals', 'problems', 'predictions', 'pending', 'outcomes'),
}
LEVEL = {'public': 0, 'internal': 1, 'private': 2}


class CognitiveWorkspace:
    """A bounded, structured shared context, never a growing prompt. Each module sees only its slots."""
    SLOTS = {'observations': 7, 'beliefs': 7, 'goals': 5, 'problems': 7, 'predictions': 5, 'pending': 5, 'outcomes': 7}

    def __init__(self, clock=time.time):
        self.clock = clock
        self.lock = threading.RLock()
        self.slots = {name: {} for name in self.SLOTS}
        self.version = 0

    def put(self, slot, key, item, salience=.5, sensitivity='internal'):
        if slot not in self.SLOTS:
            raise ValueError('Unknown workspace slot')
        with self.lock:
            rows = self.slots[slot]
            rows[key] = {'item': item, 'salience': float(salience), 'sensitivity': sensitivity, 'at': self.clock()}
            while len(rows) > self.SLOTS[slot]:
                rows.pop(min(rows, key=lambda k: (rows[k]['salience'], rows[k]['at'])))
            self.version += 1

    def remove(self, slot, key):
        with self.lock:
            if self.slots[slot].pop(key, None) is not None:
                self.version += 1

    def view(self, module, max_sensitivity='internal'):
        """Minimum relevant context for one consumer; privacy classes are preserved across the handoff."""
        ceiling = LEVEL[max_sensitivity]
        with self.lock:
            return {slot: [row['item'] for row in sorted(self.slots[slot].values(), key=lambda r: -r['salience'])
                           if LEVEL[row['sensitivity']] <= ceiling]
                    for slot in MODULE_SLOTS.get(module, ())}

    def size(self):
        with self.lock:
            return sum(len(rows) for rows in self.slots.values())


def _phi(x):
    return .5 * (1 + math.erf(x / math.sqrt(2)))


class PredictionEngine:
    """Deterministic/statistical forecasts with evidence, horizon and calibrated probability."""

    def __init__(self, store, clock=time.time, calibration_prior=5):
        self.store, self.clock, self.k = store, clock, calibration_prior
        self.lock = threading.RLock()
        self._calibration, self._calibration_at = {}, 0.

    # --- forecasters (pure; tests call them directly) ---------------------------------------------------------------
    @staticmethod
    def trend(samples):
        """Least-squares slope and R² of (t, value) samples."""
        if len(samples) < 4:
            return None
        n = len(samples)
        mt = sum(t for t, _ in samples) / n
        mv = sum(v for _, v in samples) / n
        stt = sum((t - mt) ** 2 for t, _ in samples)
        if stt <= 0:
            return None
        slope = sum((t - mt) * (v - mv) for t, v in samples) / stt
        total = sum((v - mv) ** 2 for _, v in samples)
        residual = sum((v - (mv + slope * (t - mt))) ** 2 for t, v in samples)
        return slope, (1 - residual / total) if total > 0 else 0., samples[-1][1]

    def resource_exhaustion(self, resource, samples, floor, horizon=600.):
        fit = self.trend(samples)
        if not fit:
            return None
        slope, fit_quality, current = fit
        if current <= floor:
            return self.make('resource_exhaustion', resource, .95, horizon,
                             [f'{resource} is already at {current:.0f}, below the {floor:.0f} reserve'],
                             f'{resource} below reserve', 'Defer low-priority work that needs this resource')
        if slope >= 0:
            return None
        seconds = (current - floor) / -slope
        if seconds > horizon:
            return None
        raw = max(.05, min(.95, fit_quality * (1 - seconds / horizon / 2)))
        return self.make('resource_exhaustion', resource, raw, horizon,
                         [f'{len(samples)} samples fall {(-slope * 60):.0f} per minute (fit R² {fit_quality:.2f})',
                          f'{resource} now {current:.0f}; reserve {floor:.0f}'],
                         f'{resource} may fall below reserve in about {seconds / 60:.0f} minutes',
                         'Defer or reroute low-priority work that needs this resource')

    def shortfall(self, resource, available, tasks, need_key, label):
        """Upcoming queued work whose declared need exceeds what is available now."""
        rows = []
        for task in tasks:
            need = task.get(need_key)
            if need and available is not None and need > available:
                raw = min(.95, .5 + (need - available) / max(need, 1) / 2)
                rows.append(self.make('resource_shortfall', task['id'], raw, 900.,
                    [f'task #{task["number"]} declares about {need:.0f} {label}; {available:.0f} available'],
                    f'task #{task["number"]} may not get enough {resource}',
                    'Postpone it while keeping the rest of the queue active', task=task['id']))
        return rows

    def deadline_risk(self, tasks, now):
        """Cumulative duration ahead of each deadline task; duration uncertainty widens with the workload."""
        rows, ahead = [], 0.
        for task in sorted(tasks, key=lambda t: -t.get('score', 0)):
            ahead += max(1., task.get('duration_seconds', 300))
            deadline = task.get('deadline')
            if not deadline:
                continue
            slack = deadline - now - ahead
            raw = 1 - _phi(slack / max(60., .5 * ahead))
            if raw >= .3:
                rows.append(self.make('deadline_risk', task['id'], raw, max(60., deadline - now),
                    [f'{ahead / 60:.0f} minutes of estimated work ahead of or including task #{task["number"]}',
                     f'deadline in {(deadline - now) / 60:.0f} minutes; estimates have high uncertainty'],
                    f'task #{task["number"]} may miss its deadline', 'Raise its priority or tell the user early',
                    task=task['id']))
        return rows

    def dependency_blockers(self, tasks):
        states = {t['id']: t for t in tasks}
        odds = {'FAILED': .97, 'CANCELLED': .97, 'PARTIAL': .8, 'WAITING_APPROVAL': .6, 'WAITING_USER': .6, 'PAUSED': .55}
        rows = []
        for task in tasks:
            if task['state'] in {'COMPLETED', 'FAILED', 'CANCELLED', 'PARTIAL'}:
                continue
            for dep in task.get('dependencies', []):
                upstream = states.get(dep)
                if upstream and upstream['state'] in odds:
                    rows.append(self.make('dependency_blocker', task['id'], odds[upstream['state']], 3600.,
                        [f'task #{task["number"]} waits for task #{upstream["number"]}, which is {upstream["state"]}'],
                        f'task #{task["number"]} is likely blocked', 'Resolve the prerequisite first',
                        task=task['id'], upstream=dep))
        return rows

    def stale_verification(self, project, last_pass, last_change):
        if last_pass and last_change and last_change > last_pass:
            return self.make('stale_verification', project, .9, 86400.,
                [f'project {project} changed {(last_change - last_pass) / 60:.0f} minutes after its last passing test'],
                f'the earlier passing result for {project} no longer establishes correctness',
                'Run the relevant tests again')
        return None

    def repeated_failure(self, subject, failures, successes):
        if failures < 2:
            return None
        raw = (failures + 1) / (failures + successes + 2)  # Beta(1,1) posterior mean.
        if raw < .5:
            return None
        return self.make('repeated_failure', subject, raw, 86400.,
            [f'{subject} failed {failures} of {failures + successes} recent attempts'],
            f'{subject} is likely to fail again', 'Investigate the cause before retrying')

    # --- bookkeeping ------------------------------------------------------------------------------------------------
    def make(self, kind, subject, raw, horizon, evidence, consequence, suggestion, **extra):
        raw = max(.01, min(.99, float(raw)))
        return {'id': uuid.uuid4().hex, 'kind': kind, 'subject': str(subject)[:160], 'created': self.clock(),
                'horizon': float(horizon), 'raw': round(raw, 4), 'probability': round(self.calibrate(kind, raw), 4),
                'calibrated': self.calibration(kind)['n'] >= self.k, 'evidence': evidence[:6],
                'consequence': consequence, 'suggestion': suggestion, **extra}

    def record(self, prediction):
        """One open prediction per (kind, subject); repeated forecasts do not double-count calibration."""
        with self.lock:
            if any(p['kind'] == prediction['kind'] and p['subject'] == prediction['subject'] for p in self.store.open_predictions()):
                return None
            self.store.add_prediction(prediction)
            return prediction

    def resolve(self, kind, subject, happened, note=''):
        resolved = []
        for row in self.store.open_predictions():
            if row['kind'] == kind and row['subject'] == subject:
                done = self.store.resolve_prediction(row['id'], happened, note)
                if done:
                    resolved.append(done)
        if resolved:
            self._calibration_at = 0.
        return resolved

    def expire(self):
        """At its horizon an unobserved event counts as 'did not happen' (forecast error is still recorded)."""
        now, expired = self.clock(), []
        for row in self.store.open_predictions():
            if now > row['created'] + row['horizon']:
                done = self.store.resolve_prediction(row['id'], False, 'Horizon passed without the predicted event')
                if done:
                    expired.append(done)
        if expired:
            self._calibration_at = 0.
        return expired

    def calibration(self, kind):
        now = self.clock()
        if now - self._calibration_at > 30:
            table = {}
            for row in self.store.resolved_predictions():
                table.setdefault(row['kind'], []).append((row['raw'], 1. if row['outcome'] else 0.))
            self._calibration, self._calibration_at = table, now
        rows = self._calibration.get(kind, [])
        if not rows:
            return {'n': 0, 'brier': None, 'bins': {}}
        bins = {}
        for raw, outcome in rows:
            bins.setdefault(min(9, int(raw * 10)), []).append(outcome)
        return {'n': len(rows), 'brier': round(sum((r - o) ** 2 for r, o in rows) / len(rows), 4),
                'bins': {b: (sum(v) / len(v), len(v)) for b, v in bins.items()}}

    def calibrate(self, kind, raw):
        """Histogram binning shrunk toward the raw heuristic: (n·observed + k·raw)/(n + k)."""
        table = self.calibration(kind)['bins'].get(min(9, int(raw * 10)))
        if not table:
            return raw
        frequency, n = table
        return (n * frequency + self.k * raw) / (n + self.k)

    def report(self):
        kinds = {row['kind'] for row in self.store.resolved_predictions()}
        return {kind: {k: v for k, v in self.calibration(kind).items() if k != 'bins'} for kind in sorted(kinds)}


class SelfModelManager:
    """J(t) = [K capabilities, L limitations, H component health, D decision reliability], from probes only."""

    def __init__(self, actions, clock=time.time, probe_models=None):
        self.actions, self.clock = actions, clock
        self.probe_models = probe_models or self._installed_models
        self.lock = threading.RLock()
        self.model = {'refreshed': None, 'capabilities': {}, 'limitations': [], 'health': {}, 'reliability': {},
                      'models': {'configured': [], 'installed': None, 'probe': 'not run'}}
        self.watchdog = None
        self.connector_errors = {}

    def _installed_models(self):
        import requests
        from .ollama_models import installed
        return installed(requests)

    def note_connector(self, name, ok, detail=''):
        with self.lock:
            row = self.connector_errors.setdefault(name, {'failures': 0, 'last_ok': None, 'last_error': None})
            if ok:
                row.update(failures=0, last_ok=self.clock())
            else:
                row.update(failures=row['failures'] + 1, last_error=str(detail)[:160], last_error_at=self.clock())

    def refresh(self, probe=True):
        actions, config = self.actions, getattr(self.actions, 'config', {}) or {}
        configured = sorted({v for v in (config.get('brain', {}).get('planner'), config.get('brain', {}).get('model'),
                                         config.get('knowledge', {}).get('model')) if isinstance(v, str) and v})
        models = {'configured': configured, 'installed': None, 'probe': 'not run'}
        if probe:
            try:
                installed = sorted(self.probe_models())
                models.update(installed=installed, probe='ok',
                              missing=[m for m in configured if m not in installed and m + ':latest' not in installed])
            except Exception as exc:
                models.update(probe='unavailable: ' + type(exc).__name__)
        capabilities, limitations = {}, []
        try:
            from .tools import ToolRegistry
            specs = ToolRegistry(actions).specs
            for name, spec in specs.items():
                capabilities[name] = {'status': 'registered', 'approval': bool(getattr(spec, 'approval', False)),
                                      'backend': getattr(spec, 'backend', '')}
        except Exception as exc:
            limitations.append('Tool registry could not be read (' + type(exc).__name__ + '); tool availability unknown')
        for name, enabled in (('gmail', config.get('gmail', {}).get('enabled')), ('spotify', config.get('spotify', {}).get('enabled')),
                              ('whatsapp', config.get('whatsapp', {}).get('enabled')), ('blender', config.get('blender', {}).get('enabled')),
                              ('groq', config.get('groq', {}).get('enabled'))):
            if enabled is False:
                limitations.append(name + ' is disabled in configuration')
        if models['installed'] is None:
            limitations.append('Installed local models are unknown: ' + models['probe'])
        elif models.get('missing'):
            limitations.append('Configured but not installed: ' + ', '.join(models['missing']))
        try:
            import psutil
            ram = psutil.virtual_memory().total / 1073741824
            limitations.append(f'{ram:.0f} GB RAM; GPU memory is shared with every local model')
        except Exception:
            limitations.append('Hardware capacity unknown')
        from .cognition import APPROVAL_KINDS
        limitations.append('Needs explicit approval: ' + ', '.join(sorted(APPROVAL_KINDS)) + ', and any tool whose policy requires it')
        limitations.append('Interactive desktop work is blocked while Windows is locked')
        health = {}
        watchdog = self.watchdog
        if watchdog is not None:
            for name, service in list(watchdog.services.items()):
                try:
                    enabled = bool(service['enabled']())
                except Exception:
                    enabled = None
                health[name] = {'enabled': enabled, 'failures': service.get('failures', 0),
                                'state': 'not running' if enabled is False else 'recovering' if service.get('warned') else 'ok'}
        with self.lock:
            connectors = {k: dict(v) for k, v in self.connector_errors.items()}
        for name, row in connectors.items():
            health['connector:' + name] = {'state': 'failing' if row['failures'] else 'ok', 'failures': row['failures'],
                                           'last_error': row['last_error']}
        reliability = {}
        cognition = getattr(actions, 'cognition', None)
        if cognition is not None:
            try:
                reliability = {k: {'attempts': v['attempts'], 'success': round(v['successes'] / v['attempts'], 2)}
                               for k, v in cognition.procedure_stats().items() if v['attempts'] >= 3}
            except Exception:
                reliability = {}
        with self.lock:
            self.model = {'refreshed': self.clock(), 'capabilities': capabilities, 'limitations': limitations,
                          'health': health, 'reliability': reliability, 'models': models}
        return self.snapshot()

    def snapshot(self):
        with self.lock:
            return {**self.model, 'capabilities': dict(self.model['capabilities'])}

    def capability(self, name):
        """'registered' (exists, not verified for this goal), 'unknown' (not registered or not probed)."""
        with self.lock:
            return self.model['capabilities'].get(name, {}).get('status', 'unknown')

    def broken(self):
        with self.lock:
            rows = {k: v for k, v in self.model['health'].items() if v.get('state') in {'failing', 'recovering'}}
            # Connector failures observed since the last refresh count immediately; a later success clears them.
            for name, row in self.connector_errors.items():
                key = 'connector:' + name
                if row['failures']:
                    rows[key] = {'state': 'failing', 'failures': row['failures'], 'last_error': row['last_error']}
                else:
                    rows.pop(key, None)
            return rows
