"""Extend the existing action queue with durable scheduling, not a second executor.

Legacy Actions owns its planner/desktop lane. Only explicitly read-only handlers
may use the independent fast lane; GPU/model admission remains gpu_scheduler's job.
"""
import json
import queue
import threading
import time
from pathlib import Path
from .commands import Command
from .task_store import TERMINAL
from .task_policy import classify, score, resources
from .workflow_graph import WorkflowGraph


class ScheduledQueue:
    def __init__(self, store, options=None, clock=time.time, observe=resources, recover=True):
        self.store, self.clock, self.observe = store, clock, observe
        self.graph = WorkflowGraph(store)
        self.options = options or {}
        self.lock = threading.RLock()
        self.local = threading.local()
        self.items, self.active, self.held = {}, {}, set()
        self.closed = False
        self.last_resource = {}
        self.heartbeat = clock()
        if recover:
            self.graph.migrate()
            self.store.recover()

    def restore(self, generation):
        self.graph.migrate()
        for row in self.store.rows(active=True):
            if row['state'] in {'QUEUED', 'READY', 'WAITING_DEPENDENCY', 'RETRY_BACKOFF'}:
                self.items[row['id']] = (generation, Command(**row['command']), threading.Event())

    @property
    def unfinished_tasks(self):
        with self.lock:
            return len(self.items)+len(self.active)

    def empty(self):
        return not self.unfinished_tasks

    def qsize(self):
        return sum(row['state'] in {'RECEIVED','CLASSIFYING','QUEUED','READY','WAITING_DEPENDENCY','RETRY_BACKOFF'} for row in self.store.rows())

    def join(self):
        while self.qsize() or self.active:
            time.sleep(.025)

    def put_nowait(self, item, identity=None, overrides=None):
        from dataclasses import asdict
        generation, command, token = item
        with self.lock:
            if self.closed:
                raise queue.Full
            with self.store.transaction():
                if identity is None:
                    identity, _ = self.store.admit(asdict(command))
                    self.store.transition(identity, 'CLASSIFYING')
                row = self.store.get(identity)
                if row['state'] == 'CANCELLED':
                    return
                spec = {**classify(asdict(command)), **(overrides or {})}
                estimates = self.store.setting('durations') or {}
                if command.kind in estimates:
                    spec['duration_seconds'] = max(.01, estimates[command.kind])
                deps = spec.get('dependencies', [])
                if identity in deps or any(not self.store.get(dep) for dep in deps):
                    raise ValueError('Unknown or cyclic dependency')
                self._check_cycle(identity, deps)
                self.store.transition(identity, 'QUEUED', 'Scheduled through existing Actions',
                                      command=asdict(command), spec=spec)
                self.graph.attach(identity)
                self.graph.set_dependencies(identity, spec.get('graph_dependencies', deps))
            self.items[identity] = item
            token.task_id = identity
            return identity

    def _check_cycle(self, identity, dependencies):
        todo, seen = list(dependencies), set()
        while todo:
            dep = todo.pop()
            if dep == identity:
                raise ValueError('Dependency cycle')
            if dep not in seen:
                seen.add(dep)
                todo.extend(self.store.get(dep)['spec'].get('dependencies', []))

    def _take(self, lane):
        with self.lock:
            self.heartbeat = self.clock()
            if self.closed or self.store.setting('paused'):
                return None
            self.last_resource = self.observe()
            now, candidates = self.clock(), []
            all_rows = {r['id']:r for r in self.store.rows()}
            for identity, item in list(self.items.items()):
                row = self.store.get(identity)
                if row['state'] in TERMINAL:
                    self.items.pop(identity, None)
                    continue
                if item[2].is_set():
                    self.store.transition(identity, 'CANCELLED', 'Cancelled before dispatch')
                    self.items.pop(identity, None)
                    continue
                spec = row['spec']
                if lane in {'fast', 'question', 'background'} and spec.get('lane') != lane:
                    continue
                if lane == 'legacy' and spec.get('lane') in {'fast', 'question', 'background'}:
                    continue
                if row['state'] in {'PAUSED', 'WAITING_APPROVAL', 'WAITING_USER'}:
                    continue
                group = self.graph.group_for(identity)
                if group and group['paused']:
                    continue
                readiness = self.graph.evaluate(identity)
                if not readiness['ready']:
                    if readiness['impossible']:
                        self.store.transition(identity, 'CANCELLED', 'Conditional branch skipped: committed upstream result selected a different branch',
                            checkpoint={**row['checkpoint'],'conditional_skip':readiness['impossible']})
                        self.graph.publish(identity)
                        self.items.pop(identity,None)
                        continue
                    if row['state'] != 'WAITING_DEPENDENCY':
                        self.store.transition(identity, 'WAITING_DEPENDENCY', 'Graph prerequisite/result gate is unsatisfied')
                    continue
                if spec.get('not_before', 0) > now:
                    continue
                if row['state'] in {'WAITING_DEPENDENCY', 'RETRY_BACKOFF'}:
                    self.store.transition(identity, 'QUEUED', 'Dependency/time gate satisfied')
                if spec.get('review_required'):
                    self.store.transition(identity, 'WAITING_APPROVAL', 'Generated effectful subtask requires explicit scope review; tool approvals still apply')
                    continue
                if self.store.setting('overnight') and spec.get('approval') is True:
                    self.store.transition(identity, 'WAITING_APPROVAL', 'Sensitive command deferred before unattended dispatch')
                    continue
                if self.held.intersection(spec['locks']):
                    continue
                if self.last_resource.get('ram_available_mb', 0) < self.options.get('reserve_ram_mb', 1024)+spec['resources']['ram_mb']:
                    continue
                if self.last_resource.get('battery_low') or self.last_resource.get('cpu_percent', 100) > self.options.get('max_cpu_percent', 95):
                    continue
                if 'desktop' in spec['locks'] and not self.last_resource.get('desktop'):
                    continue
                preference = 50 if self.store.setting('overnight_preference') == 'Prefer coding' and row['command']['kind'] == 'code_task' else 0
                candidates.append((score(row, now)+preference+self.graph.scheduling_bonus(identity, all_rows), -row['number'], row, item))
            if not candidates:
                return None
            _, _, row, item = max(candidates, key=lambda candidate: candidate[:2])
            identity = row['id']
            readiness = self.graph.evaluate(identity)
            if not readiness['ready']:
                return None
            self.store.transition(identity, 'RUNNING', 'Exclusive resources acquired', expected={'QUEUED','READY'},
                                  spec={**row['spec'], 'scheduling_score': score(row, now)},
                                  checkpoint={**row['checkpoint'], 'dispatch_at': now, 'input_versions': readiness['versions']})
            self.held.update(row['spec']['locks'])
            self.active[identity] = {'item': item, 'start': now, 'locks': row['spec']['locks'], 'heartbeat': now,
                                     'worker': threading.current_thread()}
            self.items.pop(identity)
            self.local.identity = identity
            self.local.outcome = ('PARTIAL', 'Handler returned without a verified outcome', {})
            self.local.approval_refused = False
            self.local.inputs = readiness['inputs']
            return item

    def current_inputs(self):
        """Fresh results bound at dispatch, never a global last-result slot."""
        return getattr(self.local, 'inputs', [])

    def publish_output(self, structured_output, *, findings=None, verified=False):
        """Trusted handler adapter; a model proposal alone must not set verified=True."""
        identity = getattr(self.local, 'identity', None)
        if not identity:
            raise ValueError('No active workflow task')
        from .workflow_graph import bounded
        evidence = {'structured_output': structured_output, 'findings': findings or [], 'verified': verified is True}
        bounded(evidence, 16000)
        row = self.store.get(identity)
        self.store.transition(identity, row['state'], 'Structured handler output recorded',
                              checkpoint={**row['checkpoint'], 'task_result': evidence})

    def get(self, timeout=.2, lane='legacy'):
        deadline = time.monotonic()+timeout
        while not self.closed:
            result = self._take(lane)
            if result is not None:
                return result
            if time.monotonic() >= deadline:
                break
            time.sleep(.025)
        raise queue.Empty

    def outcome(self, state, detail, checkpoint=None):
        self.local.outcome = (state, str(detail or ''), checkpoint or {})

    def record_effect(self, evidence):
        identity = getattr(self.local, 'identity', None)
        if identity:
            row = self.store.get(identity)
            self.store.transition(identity, row['state'], 'Fresh effect readback recorded',
                checkpoint={**row['checkpoint'], 'effects':[*row['checkpoint'].get('effects', []), evidence][-100:]})

    def touch(self):
        identity = getattr(self.local, 'identity', None)
        with self.lock:
            if identity in self.active:
                self.active[identity]['heartbeat'] = self.clock()

    def supervise(self):
        warnings = []
        with self.lock:
            for identity, active in list(self.active.items()):
                row = self.store.get(identity)
                if not active['worker'].is_alive():
                    if row['state'] not in TERMINAL and row['state'] != 'PAUSED':
                        self.store.transition(identity, 'PAUSED', 'Worker ended without a completion receipt; reconcile effects',
                                              checkpoint={**row['checkpoint'], 'uncertain': True})
                    self.active.pop(identity)
                    self.held = {lock for item in self.active.values() for lock in item['locks']}
                    warnings.append('Task #'+str(row['number'])+' worker ended; paused without replay')
                elif self.clock()-active['heartbeat'] > self.options.get('heartbeat_timeout_seconds', 120) and not active.get('warned'):
                    active['warned'] = True
                    warnings.append('Task #'+str(row['number'])+' has no recent cooperative heartbeat; inspect before recovery')
                    self.store.transition(identity, row['state'], 'Heartbeat stale; no action replay or forced thread termination',
                                          checkpoint={**row['checkpoint'], 'heartbeat_stale': True})
                if self.clock()-active['start'] > self.options.get('task_timeout_seconds', 3600):
                    active['item'][2].set()  # Cooperative boundary only; never terminate an in-flight write.
        return warnings

    def failure(self, error):
        row = self.store.get(self.local.identity)
        if row['spec'].get('read_only') and row['spec']['lane'] in {'fast','background'} and isinstance(error, (TimeoutError, ConnectionError, OSError)) and row['retries'] < 3:
            self.local.outcome = ('RETRY_BACKOFF', type(error).__name__, {})
        else:
            self.outcome('FAILED', type(error).__name__+': '+str(error)[:1000])

    def task_done(self):
        with self.lock:
            identity = self.local.identity
            active = self.active[identity]
            row = self.store.get(identity)
            state, detail, checkpoint = self.local.outcome
            checkpoint = {**row['checkpoint'], **checkpoint}
            if getattr(self.local, 'approval_refused', False):
                state, detail = 'PARTIAL', 'Explicit approval was not granted; inspect tool outcome'
            if row['state'] not in TERMINAL and not (self.closed and row['state'] == 'PAUSED'):
                if active['item'][2].is_set():
                    state = 'PAUSED' if active.get('pause') else 'CANCELLED'
                    detail = 'Stopped at a cooperative boundary; completed effects preserved'
                    checkpoint['uncertain'] = True
                if row['state'] == 'RUNNING':
                    self.store.transition(identity, 'VERIFYING', 'Handler returned; inspecting its evidence')
                checkpoint['elapsed_seconds'] = max(0, self.clock()-active['start'])
                checkpoint['dispatch_at'] = active['start']
                with self.store.transaction():
                    self.store.transition(identity, state, detail, outcome=detail, checkpoint=checkpoint)
                    if state in TERMINAL:
                        self.graph.publish(identity)
                if state == 'RETRY_BACKOFF':
                    spec = {**row['spec'], 'not_before': self.clock()+2**(row['retries']+1)}
                    self.store.transition(identity, 'RETRY_BACKOFF', 'Bounded read-only observation retry',
                                          retries=row['retries']+1, spec=spec)
                    self.items[identity] = active['item']
                if state == 'COMPLETED':
                    kind = row['command']['kind']
                    estimates = self.store.setting('durations') or {}
                    old = estimates.get(kind, checkpoint['elapsed_seconds'])
                    estimates[kind] = .8*old+.2*checkpoint['elapsed_seconds']
                    self.store.setting('durations', estimates)
            self.active.pop(identity)
            self.held.difference_update(active['locks'])
            self.local.identity = None
            self.local.inputs = []

    def control(self, action, identity=None, value=None):
        with self.lock:
            if action in {'pause_queue', 'resume_queue'}:
                self.store.setting('paused', action == 'pause_queue')
                return
            targets = self.store.rows(active=True) if identity is None else [self.store.get(identity)]
            for row in targets:
                if not row or row['state'] in TERMINAL:
                    continue
                key = row['id']
                running = self.active.get(key)
                if action in {'cancel', 'cancel_pending'}:
                    if running and action == 'cancel_pending':
                        continue
                    if running:
                        running['item'][2].set()
                    else:
                        with self.store.transaction():
                            self.store.transition(key, 'CANCELLED', 'User cancelled')
                            self.graph.publish(key)
                elif action == 'urgent':
                    spec = {**row['spec'], 'priority': 100 if value is None else int(value), 'explicit_priority': True}
                    self.store.transition(key, row['state'], 'User reprioritized', spec=spec)
                elif action in {'earlier','later'}:
                    priority = row['spec'].get('priority', 0)+(1 if action == 'earlier' else -1)
                    self.store.transition(key, row['state'], 'User reordered priority', spec={**row['spec'], 'priority': priority})
                elif action == 'deadline':
                    if not isinstance(value, (int, float)) or value <= self.clock():
                        raise ValueError('Deadline must be a future epoch timestamp')
                    self.store.transition(key, row['state'], 'User changed deadline', spec={**row['spec'], 'deadline': value})
                elif action == 'dependencies':
                    if running or not isinstance(value, list):
                        raise ValueError('Dependencies must name existing tasks before dispatch')
                    self.graph.set_dependencies(key, value)
                elif action == 'review' and row['state'] == 'WAITING_APPROVAL' and row['spec'].get('review_required'):
                    self.store.transition(key, 'QUEUED', 'User reviewed generated task scope; no tool approval granted',
                        spec={**row['spec'], 'review_required': False})
                elif action == 'pause':
                    if running:
                        # Request cooperative cancellation, never kill an active write.
                        running['pause'] = True
                        running['item'][2].set()
                    elif row['state'] in {'QUEUED', 'READY', 'WAITING_DEPENDENCY'}:
                        self.store.transition(key, 'PAUSED', 'User paused before dispatch')
                elif action == 'resume' and row['state'] in {'PAUSED', 'WAITING_USER', 'WAITING_APPROVAL'}:
                    if row['checkpoint'].get('uncertain') or row['checkpoint'].get('dispatch_at'):
                        raise ValueError('This task started already. Inspect its tool checkpoints and use the existing resume-task flow; automatic replay is prohibited.')
                    self.store.transition(key, 'QUEUED', 'User resumed before dispatch')
                    self.items.setdefault(key, (value or 0, Command(**row['command']), threading.Event()))

    def snapshot(self):
        rows = {r['id']:r for r in self.store.rows(limit=200)+self.store.rows(active=True)}
        rows = sorted(rows.values(),key=lambda r:r['number'])
        counts = self.store.counts()
        return {'tasks': rows, 'counts': counts, 'total': sum(counts.values()), 'resources': self.last_resource,
                'graph': self.graph.snapshot(),
                'overnight': self.store.setting('overnight') or False, 'paused': self.store.setting('paused') or False,
                'running': len(self.active), 'queued': len(self.items)}

    def report(self, directory):
        snapshot = self.snapshot()
        start = self.store.setting('batch_start') or 0
        snapshot['tasks'] = self.store.rows(since=start)
        snapshot['counts'] = {state:sum(r['state']==state for r in snapshot['tasks']) for state in {r['state'] for r in snapshot['tasks']}}
        snapshot['total'] = len(snapshot['tasks'])
        batch = {r['id']:r for r in snapshot['tasks']}
        graph = snapshot['graph']
        groups = []
        for group in graph['groups']:
            tasks = [task for task in group['tasks'] if task in batch]
            if not tasks:continue
            completed = sum(batch[t]['state']=='COMPLETED' for t in tasks)
            groups.append({**group,'tasks':tasks,'lifetime_progress':group['progress'],
                'completed':completed,'total':len(tasks),'progress':completed/len(tasks),
                'counts':{s:sum(batch[t]['state']==s for t in tasks) for s in {batch[t]['state'] for t in tasks}},
                'artifacts':[artifact for task in tasks for artifact in (self.graph.result(task) or {}).get('artifacts',[])],
                'errors_and_recovery':[e for e in group['errors_and_recovery'] if e['task'] in batch]})
        snapshot['graph'] = {**graph,'groups':groups,'nodes':[n for n in graph['nodes'] if n['task'] in batch],
            'edges':[e for e in graph['edges'] if e['downstream'] in batch],
            'relationships':[r for r in graph['relationships'] if r['source'] in batch or r['target'] in batch],
            'evaluations':{t:v for t,v in graph['evaluations'].items() if t in batch},
            'scope':'Current report batch; lifetime progress is separately labeled'}
        reused = {e['upstream'] for e in snapshot['graph']['edges'] if e['upstream'] not in batch}
        snapshot['graph']['reused_prerequisites'] = [self.graph.result(t) for t in sorted(reused) if self.graph.result(t)]
        decisions = self.store.setting('decision_history') or []
        report = {'generated_at': self.clock(), **snapshot, 'decisions': decisions,
                  'note': 'Outcomes are handler/checkpoint evidence. No inferred files, tests or quality claims.'}
        report['outcomes'] = {state:[r['number'] for r in snapshot['tasks'] if r['state']==state]
                              for state in ('COMPLETED','PARTIAL','FAILED','RUNNING','WAITING_APPROVAL','WAITING_USER','PAUSED')}
        report['files'] = [{'task':r['number'], **effect} for r in snapshot['tasks']
            for effect in r['checkpoint'].get('effects', []) if effect.get('kind')=='file']
        report['recorded_test_evidence'] = [{'task':r['number'], 'evidence':r['checkpoint']['tests']}
            for r in snapshot['tasks'] if r['checkpoint'].get('tests')]
        report['errors_and_recovery'] = [{'task':r['number'], **event} for r in snapshot['tasks']
            for event in self.store.history(r['id']) if event['state'] in {'FAILED','RETRY_BACKOFF','PAUSED','WAITING_APPROVAL'}]
        report['next_actions'] = [{'task':r['number'], 'action':
            'Inspect fresh effects before requesting only remaining work' if r['checkpoint'].get('uncertain') else
            'Provide explicit tool approval in the existing approval interface' if r['state']=='WAITING_APPROVAL' else
            'Answer the saved clarification using its task number' if r['checkpoint'].get('clarification') else
            'Inspect the task outcome and dependencies before continuing'}
            for r in snapshot['tasks'] if r['state'] in {'PARTIAL','FAILED','PAUSED','WAITING_APPROVAL','WAITING_USER','WAITING_DEPENDENCY'}]
        report = redact_report(report)
        path = Path(directory)/('morning-'+str(int(self.clock()*1000))+'.json')
        path.parent.mkdir(parents=True, exist_ok=True)
        # Reports are unique immutable files; do not overwrite a previous report.
        with path.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
        self.store.setting('last_report', str(path))
        return report, path

    def close(self):
        with self.lock:
            self.closed = True
            for identity, active in self.active.items():
                active['item'][2].set()
                row = self.store.get(identity)
                if row['state'] not in TERMINAL:
                    self.store.transition(identity, 'PAUSED', 'Shutdown; inspect checkpoint before continuation',
                                          checkpoint={**row['checkpoint'], 'uncertain': True})


def redact_report(value):
    """Reuse the existing credential pattern for export; the authoritative queue stays local."""
    from .cloud_policy import SECRET
    if isinstance(value, str):
        return SECRET.sub('[redacted]', value)
    if isinstance(value, dict):
        return {key:redact_report(item) for key,item in value.items()}
    if isinstance(value, list):
        return [redact_report(item) for item in value]
    return value
