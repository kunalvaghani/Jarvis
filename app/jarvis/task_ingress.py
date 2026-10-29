"""Bounded durable inbox: UI/audio callers never classify or prepare model context."""
from dataclasses import asdict
import json
import sqlite3
from pathlib import Path
import queue
import re
import threading
import time
from .commands import Command
from .task_store import TaskStore, TERMINAL
from .task_scheduler import ScheduledQueue
from .task_decisions import DecisionManager
from .task_policy import CONTROL, modifiers
from .workflow_graph import TaskRelationshipResolver, requires_prior_test_result


class TaskIngress:
    def __init__(self, actions, path, options=None):
        self.actions, self.options = actions, options or {}
        if type(self.options.get('enabled', True)) is not bool:
            raise ValueError('task_queue.enabled must be boolean')
        capacity, buffer_size = self.options.get('capacity', 512), self.options.get('buffer_size', 64)
        if type(capacity) is not int or not 1 <= capacity <= 10000 or type(buffer_size) is not int or not 1 <= buffer_size <= 1024:
            raise ValueError('Task queue capacity/buffer_size must be bounded positive integers')
        for key, default, low, high in [('reserve_ram_mb',1024,64,32768),('max_cpu_percent',95,1,100),('quiet_start_hour',22,0,23),('quiet_end_hour',8,0,23)]:
            value = self.options.get(key, default)
            if type(value) not in (int,float) or not low <= value <= high:
                raise ValueError('Invalid task queue '+key)
        if type(self.options.get('prevent_sleep', False)) is not bool:
            raise ValueError('task_queue.prevent_sleep must be boolean')
        self.path, self.owner = path, None
        self.store = TaskStore(path, capacity=capacity)
        self.scheduler = ScheduledQueue(self.store, self.options, recover=False)
        self.relationships = TaskRelationshipResolver(self.scheduler.graph, self._relationship_context)
        self.decisions = DecisionManager(self.store, self.options.get('decision_timeout_seconds', 20))
        self.buffer = queue.Queue(maxsize=buffer_size)
        self.local = threading.local()
        self.closed = threading.Event()
        self.thread = threading.Thread(target=self._run, name='Jarvis task ingress', daemon=True)
        self.fast_thread = threading.Thread(target=self._fast, name='Jarvis read-only lane', daemon=True)
        self.background_thread = threading.Thread(target=self._fast, args=('background',), name='Jarvis background observations', daemon=True)
        self.question_thread = threading.Thread(target=self._questions, name='Jarvis durable questions', daemon=True)
        self.research_thread = threading.Thread(target=self._fast, args=('research',), name='Jarvis code research', daemon=True)
        self.last_heartbeat = time.monotonic()
        self.started = False

    def _relationship_context(self):
        """Use already observed entities only; no window scan, model or filesystem crawl."""
        projects = {g['project'] for g in self.scheduler.graph.groups() if g['project']}
        knowledge = getattr(self.actions,'knowledge',None)
        history = getattr(knowledge,'history',[])
        if not isinstance(history,list):history=[]
        referenced = set()
        for turn in history[-16:]:
            if turn.get('role')=='user':
                text = turn.get('content','').casefold()
                referenced.update(project for project in projects if re.search(r'(?<!\w)'+re.escape(project)+r'(?!\w)',text))
        live = getattr(self.actions,'live_app',None)
        active = set()
        # LiveAppContext already owns this lock/cache. Do not persist unrelated titles.
        lock = getattr(live,'lock',None)
        if lock is not None:
            with lock:
                current = getattr(live,'windows',{}).get(getattr(live,'current',None),{})
                observed = current.get('observed_at')
                fresh = (current.get('status')=='open' and current.get('visible') is True
                    and type(observed) in (int,float) and 0 <= live.clock()-observed <= 30)
                if fresh:
                    title = current.get('title','').casefold()
                    active.update(project for project in projects if re.search(r'(?<!\w)'+re.escape(project)+r'(?!\w)',title))
        return {'referenced_projects':sorted(referenced),'active_projects':sorted(active)}

    def start(self):
        if self.started:
            return
        import os
        if os.name == 'nt':
            from .launcher import singleton
            self.owner = singleton(self.path.with_suffix('.owner.lock'))
            if self.owner is None:
                raise ValueError('Another Jarvis owns the durable task queue; no recovery or dispatch performed')
        self.started = True
        self.store.recover()
        self.scheduler.restore(self.actions.generation)
        with self.actions.queue_lock:
            self.actions.pending_tasks.extend((item[2], item[1]) for item in self.scheduler.items.values())
        self.thread.start()
        self.fast_thread.start()
        self.background_thread.start()
        self.question_thread.start()
        self.research_thread.start()

    def submit(self, command, expected_generation=None, idempotency_key=None, workflow=None, dependencies=None):
        if self.closed.is_set() or self.actions.closed.is_set():
            return None
        # Already-classified followups retain the original task on the ingress thread.
        if getattr(self.local, 'identity', None):
            return self.actions._submit(command, expected_generation)
        if expected_generation is not None and expected_generation != self.actions.generation:
            return None
        try:
            with self.store.transaction():
                identity, fresh = self.store.admit(asdict(command), idempotency_key)
                if workflow and fresh:
                    self.scheduler.graph.attach(identity, workflow=workflow)
                    # The caller named the owning workflow; no conversational relationship guessing.
                    self.store.transition(identity, 'RECEIVED', 'Explicit workflow admission', checkpoint={'relationship_resolved': True})
                if dependencies and fresh:
                    if any(not self.store.get(d) for d in dependencies):
                        raise ValueError('Unknown dependency')
                    self.store.setting('admission_overrides:'+identity, {'dependencies': list(dependencies)})
        except (BufferError, OSError, ValueError, sqlite3.Error) as exc:
            self.actions.report('warning', str(exc))
            return None
        if fresh:
            try:
                self.buffer.put_nowait(identity)
            except queue.Full:
                pass  # SQLite inbox is authoritative; polling drains overflow after capacity opens.
            row = self.store.get(identity)
            self.actions.report('task_received', {'id': identity, 'number': row['number'], 'status': 'RECEIVED'})
        return identity

    def enqueue(self, item):
        identity = getattr(self.local, 'identity', None)
        if identity and not self.store.get(identity)['checkpoint'].get('relationship_resolved'):
            resolution = self.relationships.resolve(identity, item[1])
            if resolution.get('question'):
                from .task_policy import classify
                row = self.store.get(identity)
                self.store.transition(identity, 'WAITING_USER', resolution['question'],
                    command=asdict(item[1]), spec={**classify(asdict(item[1])), **getattr(self.local,'overrides',{})},
                    checkpoint={**row['checkpoint'], 'relationship_question': resolution})
                with self.actions.queue_lock:
                    self.actions.pending_tasks = [(token, command) for token, command in self.actions.pending_tasks if token is not item[2]]
                self.actions.report('question', resolution['question']+' Use "link task '+str(row['number'])+' after task N".')
                return identity
            if resolution['dependencies']:
                self.local.overrides = {**getattr(self.local, 'overrides', {}),
                    'dependencies': [d['upstream'] for d in resolution['dependencies']],
                    'graph_dependencies': resolution['dependencies']}
            row = self.store.get(identity)
            self.store.transition(identity,row['state'],'Task relationship resolution recorded',
                checkpoint={**row['checkpoint'],'relationship_resolved':True})
        return self.scheduler.put_nowait(item, identity, getattr(self.local, 'overrides', None))

    def proactive_origin(self):
        """True on the ingress thread while it routes work the awareness layer submitted itself."""
        identity = getattr(self.local, 'identity', None)
        row = self.store.get(identity) if identity else None
        return bool(row and str(row['idem']).startswith(('cognitive:', 'project:', 'pcide:')))

    def checkpoint(self, state):
        identity = getattr(self.scheduler.local, 'identity', None)
        if identity:
            row = self.store.get(identity)
            if row['state'] not in TERMINAL:
                self.store.transition(identity, row['state'], 'Existing TaskState checkpoint persisted',
                    checkpoint={**row['checkpoint'], 'tool_checkpoint': state})

    def _parse(self, command):
        if command.kind not in {'task', 'ask'}:
            return command
        text, overrides = modifiers(command.value)
        self.local.new_task = text != command.value
        if overrides.pop('after_previous', False):
            number = self.store.get(self.local.identity)['number']
            previous = [r for r in self.store.rows() if r['number'] < number and r['command']['kind'] not in CONTROL
                        and not r['checkpoint'].get('control')]
            overrides['dependencies'] = [previous[-1]['id']] if previous else []
        named = re.match(r'^(?:do this|do|run this) after (?:the )?(.+?) task (?:finishes|completes)[:,]?\s+(.+)$', text, re.I|re.S)
        if named:
            matches = [r for r in self.store.rows() if r['id'] != self.local.identity and named[1].lower() in (r['command']['kind']+' '+r['command'].get('value','')).lower()]
            if len(matches) != 1:
                raise ValueError('Dependency description is ambiguous; use a unique task description')
            overrides['dependencies'], text = [matches[0]['id']], named[2]
            self.local.new_task = True
        self.local.overrides = overrides
        if re.search(r'(?i)^(?:after that|after tasks? \d+|now fix|fix them|test the fixes|use the report|do the same|take those|continue the earlier)|\bthose (?:issues|results|findings)\b', text) or requires_prior_test_result(text):
            self.local.new_task = True
            return Command('task', text)
        if text != command.value:
            from .engine import Engine
            parsed = []
            engine = Engine(parsed.append, lambda *_: None)
            engine.activate()
            engine.feed(text, final=True, raw=text)
            if len(parsed) != 1:
                raise ValueError('Give one task per admission when using scheduling modifiers')
            return parsed[0]
        return command

    def _run(self):
        while not self.closed.is_set():
            from .campaign_pause import queue_paused
            if queue_paused(self.store):
                self.closed.wait(.1)
                continue
            self.last_heartbeat = time.monotonic()
            try:
                identity = self.buffer.get(timeout=.1)
                self.buffer.task_done()
            except queue.Empty:
                row = next((r for r in self.store.rows(active=True) if r['state'] == 'RECEIVED'), None)
                identity = row['id'] if row else None
            try:
                self._maintenance()
                if not identity or self.store.get(identity)['state'] != 'RECEIVED':
                    continue
                self.local.identity, self.local.overrides, self.local.new_task = identity, {}, False
                self.store.transition(identity, 'CLASSIFYING')
                command = self._parse(Command(**self.store.get(identity)['command']))
                stored = self.store.setting('admission_overrides:'+identity)
                if stored:
                    self.local.overrides = {**getattr(self.local, 'overrides', {}), **stored}
                handled_control = self.control(command)
                if not handled_control:
                    self.actions._submit(command)
                row = self.store.get(identity)
                if row['state'] == 'CLASSIFYING':
                    self.store.transition(identity, 'PARTIAL', 'Handled by existing conversation/control/clarification path; no durable task outcome claimed',
                        checkpoint={**row['checkpoint'], 'control': handled_control})
            except Exception as exc:
                if identity and self.store.get(identity)['state'] not in TERMINAL:
                    self.store.transition(identity, 'FAILED', type(exc).__name__, outcome=str(exc)[:1000])
                self.actions.report('warning', 'Task admission failed: '+str(exc)[:200])
            finally:
                self.local.identity = None
        if getattr(self, '_power_enabled', False):
            import ctypes
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)

    def _fast(self, lane='fast'):
        from .intent_handlers import execute
        while not self.closed.is_set():
            try:
                generation, command, token = self.scheduler.get(lane=lane)
            except queue.Empty:
                continue
            responses = getattr(self.actions, 'response_reports', None)
            if responses is not None:
                responses.bind(generation, lambda generation=generation, token=token:
                    not self.closed.is_set() and generation == self.actions.generation and not token.is_set())
            try:
                if not token.is_set() and generation == self.actions.generation:
                    reply = execute(self.actions, command)
                    if reply and not token.is_set() and generation == self.actions.generation:
                        self.actions.report('answer', reply)  # Silent handlers (awareness investigations) return ''.
                    self.scheduler.outcome('COMPLETED', reply, {'source': 'existing read-only intent handler'})
                else:
                    self.scheduler.outcome('CANCELLED', 'Cancelled before handler')
            except Exception as exc:
                self.scheduler.failure(exc)
            finally:
                self.scheduler.task_done()
                if responses is not None:
                    responses.unbind()

    def _questions(self):
        while not self.closed.is_set():
            try:
                generation, command, token = self.scheduler.get(lane='question')
            except queue.Empty:
                continue
            ready, outcome = threading.Event(), {}
            def finished(completed, answer, outcome=outcome, ready=ready):
                outcome.update(completed=completed, answer=answer)
                ready.set()
            try:
                if generation != self.actions.generation or token.is_set():
                    self.scheduler.outcome('CANCELLED', 'Cancelled before inference')
                    continue
                cancelled = lambda token=token, generation=generation: self.closed.is_set() or token.is_set() or generation != self.actions.generation
                inputs = self.scheduler.current_inputs()
                context = {'workflow_context':inputs} if inputs else {}
                accepted = self.actions.knowledge.submit(command.value, command.extra == 'web', on_complete=finished, cancel_check=cancelled, **context)
                if not accepted:
                    self.scheduler.outcome('FAILED', 'Existing conversation queue rejected admission')
                    continue
                while not ready.wait(.1):
                    if self.closed.is_set() or token.is_set() or generation != self.actions.generation:
                        break
                self.scheduler.outcome('COMPLETED' if outcome.get('completed') else 'PARTIAL', outcome.get('answer', 'Conversation interrupted'),
                                       {'source': 'existing Knowledge completion callback'})
            except Exception as exc:
                self.scheduler.outcome('FAILED', str(exc))
            finally:
                self.scheduler.task_done()

    def _maintenance(self):
        self._power()
        projects = getattr(self.actions, 'project_intel', None)
        if projects is not None and getattr(projects, 'enabled', False):
            try:
                projects.reconcile()  # Fold finished project tasks back into their plans (throttled).
            except Exception as exc:
                self.actions.report('warning', 'Project reconciliation failed: '+type(exc).__name__)
        self._resolve_waiting_relationships()
        for warning in self.scheduler.supervise():
            self.actions.report('repair', warning)
        for decision in self.decisions.tick():
            self.apply_decision(decision)
        for decision in self.decisions.rows():
            if decision['status']=='SELECTED' and self.store.setting('graph_decision:'+decision['id']) and not self.store.setting('graph_decision_applied:'+decision['id']):
                self.apply_graph_decision(decision)
        if self.store.setting('overnight'):
            rows = self.store.rows(since=self.store.setting('batch_start') or 0)
            if rows and not any(r['state'] in {'RECEIVED','CLASSIFYING','QUEUED','READY','RUNNING','VERIFYING','RETRY_BACKOFF'} for r in rows):
                _, path = self.scheduler.report(self.actions.base/'.jarvis-runtime'/'task-reports')
                self.store.setting('overnight', False)
                self.actions.report('task_report', str(path))

    def _resolve_waiting_relationships(self):
        for row in self.store.rows(active=True):
            if row['state'] != 'WAITING_USER' or not row['checkpoint'].get('relationship_question') or row['checkpoint'].get('relationship_resolved'):
                continue
            with self.scheduler.lock:
                resolution = self.relationships.resolve(row['id'],Command(**row['command']),include_later=True)
                if resolution.get('question'):continue
                specs = {**row['spec'],'dependencies':[d['upstream'] for d in resolution['dependencies']],
                         'graph_dependencies':resolution['dependencies']}
                token = threading.Event()
                try:
                    self.scheduler.put_nowait((self.actions.generation,Command(**row['command']),token),row['id'],specs)
                except ValueError as exc:
                    # A proposed forward link can close a cycle. Persist the question, do not dispatch it.
                    if row['checkpoint'].get('graph_resolution_error') != str(exc):
                        self.store.transition(row['id'],'WAITING_USER','Relationship remains unresolved: '+str(exc),
                            checkpoint={**row['checkpoint'],'graph_resolution_error':str(exc)})
                    continue
                current = self.store.get(row['id'])
                self.store.transition(row['id'],current['state'],'New explicit project/task context resolved pending relationship',
                    checkpoint={**current['checkpoint'],'relationship_resolved':True})
                with self.actions.queue_lock:self.actions.pending_tasks.append((token,Command(**row['command'])))

    def quiet(self):
        if not self.store.setting('overnight'):
            return False
        start, end = self.options.get('quiet_start_hour', 22), self.options.get('quiet_end_hour', 8)
        hour = time.localtime().tm_hour
        return (hour >= start or hour < end) if start > end else start <= hour < end

    def _power(self):
        import os
        if os.name != 'nt':
            return
        enabled = bool(self.options.get('prevent_sleep', False) and self.store.setting('overnight') and not self.scheduler.last_resource.get('battery_low', True))
        if enabled != getattr(self, '_power_enabled', False):
            import ctypes
            request = ctypes.windll.kernel32.SetThreadExecutionState
            request.argtypes, request.restype = [ctypes.c_uint], ctypes.c_uint
            if request(0x80000001 if enabled else 0x80000000):
                self._power_enabled = enabled
            elif not getattr(self, '_power_warning', False):
                self._power_warning = True
                self.actions.report('repair', 'Windows declined the optional execution-state request; sleep prevention is unavailable')

    def apply_decision(self, decision):
        if decision['status'] == 'SELECTED' and decision['question'] == 'Overnight scheduling preference':
            self.store.setting('overnight_preference', decision['options'][decision['choice']])
        self.apply_graph_decision(decision)
        self.actions.report('task_decision', decision)

    def apply_graph_decision(self, decision):
        proposal = self.store.setting('graph_decision:'+decision['id'])
        if not proposal or decision['status'] != 'SELECTED':
            return
        # Only an ordering preference over already admitted nodes; no new permission.
        with self.scheduler.lock, self.store.transaction():
            if self.store.setting('graph_decision_applied:'+decision['id']):return
            selected = proposal['strategies'][decision['choice']]
            self.store.db.execute('SAVEPOINT apply_strategy')
            try:
                for task, dependencies in selected.items():
                    self._check_strategy_constraints(task, dependencies)
                    self.scheduler.graph.set_dependencies(task, dependencies, 'Routine workflow strategy: '+decision['justification'])
            except ValueError as exc:
                self.store.db.execute('ROLLBACK TO apply_strategy')
                self.scheduler.graph.revision('decision_deferred',{'decision':decision['id'],'reason':str(exc)})
                self.store.setting('graph_decision_deferred:'+decision['id'],str(exc))
            finally:self.store.db.execute('RELEASE apply_strategy')
            self.store.setting('graph_decision_applied:'+decision['id'], True)

    def propose_strategies(self, question, strategies, *, confidence=0., reversible=False, sensitive=True):
        """Adapters may offer validated graph strategies; only visible choices start timers."""
        if not 2 <= len(strategies) <= 5:
            raise ValueError('Offer two to five routine strategies')
        # Validate every alternate in a rollback-only transaction before showing it.
        with self.scheduler.lock, self.store.transaction():
            for strategy in strategies.values():
                for task, dependencies in strategy.items():
                    self._check_strategy_constraints(task, dependencies)
                # Automatic strategy selection is restricted to read-only tasks.
                if any(not self.store.get(task)['spec'].get('read_only') for task in strategy):
                    sensitive = True
                self.store.db.execute('SAVEPOINT strategy_validation')
                try:
                    for task, dependencies in strategy.items():
                        self.scheduler.graph.set_dependencies(task, dependencies)
                finally:
                    self.store.db.execute('ROLLBACK TO strategy_validation')
                    self.store.db.execute('RELEASE strategy_validation')
            identity = self.decisions.create(None, question, list(strategies), confidence=confidence,
                reversible=reversible, sensitive=sensitive)
            self.store.setting('graph_decision:'+identity, {'strategies': list(strategies.values())})
        self.actions.report('task_decision', {'id':identity, 'status':'PENDING'})
        return identity

    def _check_strategy_constraints(self, task, dependencies):
        proposed = {d if isinstance(d,str) else d.get('upstream'):d for d in dependencies}
        for edge in self.scheduler.graph.edges(task):
            candidate = proposed.get(edge['upstream'])
            if candidate is None or isinstance(candidate,str) and any(edge['data'][key]!=default
                for key,default in [('condition','success'),('optional',False),('requires_result',False)]):
                raise ValueError('Routine strategies cannot remove existing prerequisite constraints')
            if isinstance(candidate,dict) and any(candidate.get(k,default)!=edge['data'][k]
                for k,default in [('condition','success'),('optional',False),('requires_result',False)]):
                raise ValueError('Routine strategies cannot weaken existing prerequisite constraints')

    def expand(self, parent, commands, key, *, join=None):
        """Bounded subtasks enter the same durable inbox, classification and policy gates.

        Generated side-effect work is held for explicit review, never auto-authorized.
        Exact expansion keys deduplicate across restarts. No new worker is created.
        """
        with self.scheduler.lock:
            previous = dict(self.scheduler.items)
            try:
                return self._expand(parent, commands, key, join=join)
            except BaseException:
                self.scheduler.items = previous
                raise

    def _expand(self, parent, commands, key, *, join=None):
        from .task_policy import classify
        from .workflow_graph import bounded
        if not isinstance(commands, list) or not 1 <= len(commands) <= 20 or not isinstance(key, str) or not 1 <= len(key) <= 100:
            raise ValueError('Expansion needs a stable key and one to twenty commands')
        bounded([asdict(c) for c in commands])
        with self.scheduler.lock, self.store.transaction():
            row, node = self.store.get(parent), self.scheduler.graph.node(parent)
            if not row or not node or row['state'] not in {'RUNNING', 'COMPLETED'}:
                raise ValueError('Expansion requires a running or completed parent')
            existing = self.store.setting('expansion:'+parent+':'+key)
            if existing:return existing
            # Includes descendants, so nested expansions cannot evade the quota.
            snapshot = self.scheduler.graph.snapshot()
            children = [n for n in snapshot['nodes'] if n['workflow'] == node['workflow'] and n['parent']]
            if len(children)+len(commands) > 50:
                raise ValueError('Workflow automatic expansion quota exceeded')
            lineage, depth = node, 0
            while lineage.get('parent'):
                depth += 1; lineage = self.scheduler.graph.node(lineage['parent'])
            if depth >= 3:raise ValueError('Automatic expansion depth limit reached')
            admitted = []
            for index, command in enumerate(commands):
                if command.kind in CONTROL or command.kind not in {'task','ask','code_task','jarvis_status','system_info','screen_info'}:
                    raise ValueError('Subtasks must use an ordinary task or read-only handler')
                if command.kind != 'code_task' and command.extra:
                    raise ValueError('Generated tasks cannot carry approval, resume or routing claims')
                identity, _ = self.store.admit(asdict(command), parent+':expand:'+key+':'+str(index))
                self.scheduler.graph.attach(identity, workflow=node['workflow'], parent=parent)
                readonly = classify(asdict(command))['read_only'] or command.kind == 'ask'
                spec = {'generated': True, 'review_required': not readonly,
                        'dependencies': [parent], 'graph_dependencies': [{'upstream':parent, 'requires_result':True}]}
                if command.kind == 'ask':spec.update(lane='question',locks=['conversation'],read_only=True)
                self.store.transition(identity, 'CLASSIFYING')
                self.scheduler.put_nowait((self.actions.generation, command, threading.Event()), identity, spec)
                admitted.append(identity)
            if join:
                old = self.scheduler.graph.edges(join)
                self.scheduler.graph.set_dependencies(join, [{'upstream':e['upstream'], **e['data']} for e in old]+admitted,
                                                       'Combined verification waits for generated subtasks')
            self.store.setting('expansion:'+parent+':'+key, admitted)
            self.scheduler.graph.revision('expand', {'parent':parent,'tasks':admitted,'join':join})
            return admitted

    def control(self, command):
        text = re.sub(r'^jarvis[, ]*', '', command.value.strip().lower()).rstrip('.!?')
        add = re.fullmatch(r'add to workflow ([a-f0-9]{32})\s*:\s*(.+)', command.value.strip(), re.I|re.S)
        if add:
            from .commands import parse
            previous = self.local.identity
            try:
                self.local.identity = None
                try: child = parse(add[2])
                except ValueError: child = Command('task',add[2],'unparsed')
                if not self.submit(child, workflow=add[1], idempotency_key=previous+':workflow-child'):
                    raise ValueError('Workflow task was not admitted')
            finally:self.local.identity = previous
            return True
        link = re.fullmatch(r'link task (\d+) after tasks? ([\d ,and]+)', text)
        if link:
            with self.scheduler.lock:
                rows = {r['number']:r for r in self.store.rows()}
                row = rows.get(int(link[1]))
                numbers = [int(n) for n in re.findall(r'\d+', link[2])]
                if not row or not numbers or any(n not in rows for n in numbers):
                    raise ValueError('Select existing task numbers')
                dependencies = [{'upstream':rows[n]['id'], 'requires_result':True} for n in numbers]
                self.scheduler.graph.attach(row['id'], workflow=(self.scheduler.graph.node(rows[numbers[0]]['id']) or {})['workflow'])
                self.scheduler.graph.set_dependencies(row['id'], dependencies, 'User clarified the intended task references')
                if row['state'] == 'WAITING_USER' and row['checkpoint'].get('relationship_question'):
                    self.store.transition(row['id'], 'QUEUED', 'Relationship clarification resolved',
                        checkpoint={**row['checkpoint'], 'relationship_resolved':True})
                    self.scheduler.items[row['id']] = (self.actions.generation, Command(**row['command']), threading.Event())
            return True
        group_control = re.fullmatch(r'(pause|resume|urgent|cancel pending) group ([a-f0-9]{32})', text)
        if group_control:
            self.group_control(group_control[1], group_control[2])
            return True
        move = re.fullmatch(r'move task (\d+) to workflow ([a-f0-9]{32})', text)
        if move:
            row = next((r for r in self.store.rows() if r['number'] == int(move[1])), None)
            self.scheduler.graph.move(row['id'] if row else '', move[2])
            return True
        answer = re.fullmatch(r'answer task (\d+)\s*:\s*(.+)', command.value.strip(), re.I|re.S)
        if answer:
            with self.scheduler.lock:
                row = next((r for r in self.store.rows(active=True) if r['number'] == int(answer[1])), None)
                clarified = clarification_command(row, answer[2], self.actions.catalog.resolve)
                previous = (self.local.identity, self.local.overrides, self.local.new_task)
                try:
                    self.local.identity, self.local.overrides, self.local.new_task = row['id'], row['spec'], True
                    self.actions._submit(clarified)
                    if self.store.get(row['id'])['state'] != 'QUEUED':
                        raise ValueError('Continuation was not queued; original checkpoint retained')
                finally:
                    self.local.identity, self.local.overrides, self.local.new_task = previous
            self.actions.report('answer', f"Task {row['number']}: clarification queued from its saved checkpoint")
            return True
        batch = re.match(r'^queue these (?:(\d+|one|two|three|four|five|six|seven|eight|nine|ten) )?requests?\s*:\s*(.+)$', command.value.strip(), re.I|re.S)
        if batch:
            from .commands import parse
            requests = [part.strip(' -\t') for part in re.split(r'[;\n]+',batch[2]) if part.strip()]
            words = 'one two three four five six seven eight nine ten'.split()
            expected = int(batch[1]) if batch[1] and batch[1].isdigit() else words.index(batch[1].lower())+1 if batch[1] else len(requests)
            if not 1 <= len(requests) <= 50 or expected != len(requests):
                raise ValueError('Separate each request with a semicolon or newline and match the stated count')
            parent = self.local.identity
            admitted = []
            try:
                self.local.identity = None
                for index, request in enumerate(requests):
                    try:
                        parsed = parse(request)
                    except ValueError:
                        parsed = Command('task',request,'unparsed')
                    identity = self.submit(parsed,idempotency_key=parent+':child:'+str(index))
                    if identity is None:
                        break
                    admitted.append(identity)
            finally:
                self.local.identity = parent
            self.actions.report('answer', f'{len(admitted)} of {len(requests)} requests durably admitted')
            return True
        if command.kind == 'cancel_task' and command.extra != 'except':
            text = 'cancel task '+re.sub(r'^(?:task |number )', '', text)
        if text in {'balanced priorities', 'prefer coding'}:
            pending = next((d for d in self.decisions.rows() if d['status'] == 'PENDING' and text in [v.lower() for v in d['options']]), None)
            if pending:
                changed, decision = self.decisions.choose(pending['id'], [v.lower() for v in pending['options']].index(text))
                if changed or decision['status'] != 'PENDING':
                    self.apply_decision(decision)
                return True
        named_control = re.fullmatch(r'(pause|resume|cancel) (?:the )?(.+?) task', text)
        if named_control:
            matches = [r for r in self.store.rows() if r['state'] not in TERMINAL and r['id'] != self.local.identity and named_control[2] in (r['command']['kind']+' '+r['command'].get('value','')).lower()]
            if len(matches) != 1:
                raise ValueError('Task description is ambiguous; select a persistent task number')
            self.scheduler.control(named_control[1], matches[0]['id'])
            return True
        if text == 'continue the previous task':
            matches = [r for r in self.store.rows() if r['state'] in {'PAUSED','WAITING_USER'}]
            if not matches:
                raise ValueError('No paused task to continue')
            self.scheduler.control('resume', matches[-1]['id'])
            return True
        if command.kind == 'queue_status' or text in {"what are you currently doing", 'how many tasks are left', "what's in the queue", 'show task queue'}:
            snapshot = self.scheduler.snapshot()
            self.actions.report('answer', f"{snapshot['running']} running, {snapshot['queued']} waiting. "+str(snapshot['counts']))
            self.actions.report('island_navigation', ('Queue', ''))
            return True
        if text in {'run the queue overnight','run all queued tasks overnight',"i'm going to sleep. finish everything you safely can",'work overnight'}:
            self.store.setting('overnight', True)
            self.store.setting('paused', False)
            active = [r for r in self.store.rows() if r['state'] not in TERMINAL]
            self.store.setting('batch_start', min((r['number'] for r in active), default=0))
            remaining = sum(r['spec'].get('duration_seconds', 300) for r in active)
            self.actions.report('answer', f'Overnight mode enabled. Rough serial estimate {remaining/60:.0f} minutes, high uncertainty. Approval and locked-desktop gates still apply.')
            identity = self.decisions.create(None, 'Overnight scheduling preference', ['Balanced priorities','Prefer coding'], confidence=.95, reversible=True, sensitive=False)
            self.actions.report('task_decision', {'id': identity, 'status': 'PENDING'})
            return True
        if text in {'stop overnight mode','disable overnight mode','day mode'}:
            self.store.setting('overnight', False)
            self.actions.report('answer', 'Overnight mode disabled. Deferred tasks can be resumed; existing tool approvals still apply.')
            return True
        controls = {'pause the queue':'pause_queue','pause queue':'pause_queue','resume the queue':'resume_queue','continue queue':'resume_queue',
                    "cancel everything that hasn't started":'cancel_pending', 'stop the queue':'pause_queue'}
        if text in controls:
            self.scheduler.control(controls[text])
            return True
        if text in {'show me everything you completed last night','open the morning report','prepare a report when everything finishes','why did you choose that option'}:
            if text == 'prepare a report when everything finishes':
                self.store.setting('overnight', True)
                return True
            if text == 'why did you choose that option':
                self.actions.report('answer', json.dumps(self.decisions.rows(), ensure_ascii=False, indent=2))
                return True
            previous = self.store.setting('last_report')
            if previous and Path(previous).is_file():
                path = Path(previous)
                report = json.loads(path.read_text(encoding='utf-8'))
            else:
                report, path = self.scheduler.report(self.actions.base/'.jarvis-runtime'/'task-reports')
            self.actions.report('answer', json_report(report, path))
            self.actions.report('island_navigation', ('Queue', ''))
            return True
        match = re.fullmatch(r'(make|pause|resume|cancel) task (\d+|one|two|three|four|five|six|seven|eight|nine|ten)( urgent)?', text)
        if match:
            numbers = 'one two three four five six seven eight nine ten'.split()
            number = int(match[2]) if match[2].isdigit() else numbers.index(match[2])+1
            row = next((r for r in self.store.rows() if r['number'] == number), None)
            if not row:
                raise ValueError('Unknown persistent task number')
            action = 'urgent' if match[1] == 'make' else match[1]
            self.scheduler.control(action, row['id'])
            self.actions.report('answer', f'Task {number}: {action}')
            return True
        return False

    def group_control(self, action, identity):
        with self.scheduler.lock:
            group = self.scheduler.graph.group(identity)
            if not group:raise ValueError('Unknown group')
            if action in {'pause','resume'}:
                self.scheduler.graph.update_group(identity, paused=action == 'pause')
            elif action == 'urgent':
                self.scheduler.graph.update_group(identity, priority=100)
            elif action == 'cancel pending':
                group = next(g for g in self.scheduler.graph.snapshot()['groups'] if g['id'] == identity)
                for task in group['tasks']:self.scheduler.control('cancel_pending',task)
            else:raise ValueError('Unknown group control')

    def healthy(self):
        return not self.closed.is_set() and all(t.is_alive() for t in [self.thread,self.fast_thread,self.background_thread,self.question_thread,self.research_thread])

    def repair(self):
        # Never overlap an alive worker or replay an admission interrupted in CLASSIFYING.
        if self.closed.is_set():
            return
        if not self.thread.is_alive():
            for row in self.store.rows():
                if row['state'] == 'CLASSIFYING':
                    self.store.transition(row['id'], 'WAITING_USER', 'Admission worker interrupted; reconcile before resubmission')
            self.thread = threading.Thread(target=self._run, name='Jarvis task ingress', daemon=True)
            self.thread.start()
        if not self.fast_thread.is_alive():
            # Running effects require reconciliation; do not replay.
            self.fast_thread = threading.Thread(target=self._fast, name='Jarvis read-only lane', daemon=True)
            self.fast_thread.start()
        if not self.question_thread.is_alive():
            self.question_thread = threading.Thread(target=self._questions, name='Jarvis durable questions', daemon=True)
            self.question_thread.start()
        if not self.background_thread.is_alive():
            self.background_thread = threading.Thread(target=self._fast, args=('background',), name='Jarvis background observations', daemon=True)
            self.background_thread.start()
        if not self.research_thread.is_alive():
            self.research_thread = threading.Thread(target=self._fast, args=('research',), name='Jarvis code research', daemon=True)
            self.research_thread.start()

    def close(self):
        self.closed.set()
        self.scheduler.close()
        # SQLite stays open until process exit: an in-flight owned handler may still checkpoint.

    def close_storage(self):
        threads = [self.thread, self.fast_thread, self.background_thread, self.question_thread, self.research_thread, self.actions.thread]
        for thread in threads:
            if thread.is_alive() and thread is not threading.current_thread():
                thread.join(timeout=1)
        if not any(t.is_alive() for t in threads):
            self.store.db.close()
            if self.owner is not None:
                self.owner.close()
                self.owner = None


def json_report(report, path):
    tasks = '\n'.join(f"#{r['number']} {r['state']}: {r['command'].get('value') or r['command']['kind']}\n{r['outcome']}" for r in report['tasks'])
    return 'Saved report: '+str(path)+'\n'+str(report['counts'])+'\n'+tasks+'\nDecisions: '+json.dumps(report['decisions'], ensure_ascii=False)+'\n'+report['note']


def clarification_command(row, answer, resolve_folder):
    """Bind continuation to one persisted prompt; never replay an uncertain effect."""
    from .task_state import TaskState
    from .clarification import choice_index
    if not row or row['state'] != 'WAITING_USER':
        raise ValueError('That task is not waiting for a clarification')
    pending = row['checkpoint'].get('clarification')
    if not pending or not isinstance(answer, str) or not 0 < len(answer.strip()) <= 2000:
        raise ValueError('No saved clarification or answer is invalid; inspect the task')
    source = pending['source']
    blocker = TaskState.resume_blocker(source)
    if blocker or row['checkpoint'].get('uncertain'):
        raise ValueError(blocker or 'Uncertain effects require fresh inspection before continuation')
    answer = answer.strip()
    if pending.get('slot') == 'folder':
        choices = pending.get('choices', [])
        index = choice_index(answer, choices) if choices else None
        if index is not None:
            if not 0 <= index < len(choices):raise ValueError('Folder option is out of range')
            answer = choices[index]
        answer = resolve_folder(answer, 'folder')
        goal = 'In folder '+str(answer)+', '+pending['goal']
    elif pending.get('slot') == 'python_purpose':
        goal = 'Create a Python file with '+answer+' code. Original request: '+pending['goal']
    else:
        goal = pending['goal']+'\nClarification question: '+pending['question']+'\nYour answer: '+answer
    return Command('clarified_task', goal, json.dumps(source))
