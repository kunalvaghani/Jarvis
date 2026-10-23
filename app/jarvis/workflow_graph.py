"""Persistent workflow metadata for the existing queue; never an effect executor.

Edges point from prerequisite to consumer. Context relations never order work.
All mutations share TaskStore's transaction and revision log. Results are data,
not tool instructions or approval receipts.
"""
import hashlib
import json
import re
import uuid
from pathlib import Path

from .task_store import TERMINAL

RELATIONS = {'CONTINUATION_OF', 'DEPENDS_ON', 'PRODUCES_INPUT_FOR', 'SAME_PROJECT_AS',
             'SAME_GOAL_AS', 'CONDITIONAL_ON', 'BLOCKED_BY', 'INDEPENDENT_OF', 'SUPERSEDES'}
CONDITIONS = {'success', 'failure', 'tests_pass', 'tests_fail', 'always'}
EDITABLE = {'RECEIVED', 'CLASSIFYING', 'QUEUED', 'READY', 'WAITING_DEPENDENCY', 'WAITING_USER', 'PAUSED'}


def bounded(value, limit=64000):
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    if len(encoded) > limit:
        raise ValueError('Workflow metadata exceeds its bounded size')
    return encoded


class WorkflowGraph:
    def __init__(self, store):
        self.store = store
        with store.lock:
            store.db.executescript('''
                CREATE TABLE IF NOT EXISTS workflow_groups (
                    id TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS workflows (
                    id TEXT PRIMARY KEY, group_id TEXT NOT NULL, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS workflow_nodes (
                    task TEXT PRIMARY KEY, workflow TEXT NOT NULL, parent TEXT, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS workflow_edges (
                    upstream TEXT NOT NULL, downstream TEXT NOT NULL, data TEXT NOT NULL,
                    PRIMARY KEY(upstream,downstream));
                CREATE TABLE IF NOT EXISTS task_relationships (
                    source TEXT NOT NULL, target TEXT NOT NULL, kind TEXT NOT NULL, data TEXT NOT NULL,
                    PRIMARY KEY(source,target,kind));
                CREATE TABLE IF NOT EXISTS workflow_results (
                    task TEXT NOT NULL, version INTEGER NOT NULL, data TEXT NOT NULL,
                    PRIMARY KEY(task,version));
                CREATE TABLE IF NOT EXISTS workflow_revisions (
                    revision INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL,
                    operation TEXT NOT NULL, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS workflow_evaluations (
                    task TEXT PRIMARY KEY, data TEXT NOT NULL);
            ''')
            store.db.commit()

    def migrate(self):
        """Backfill pre-graph queue records without changing lifecycle or rerunning work."""
        if self.store.setting('workflow_schema') == 1:return
        with self.store.transaction():
            for row in self.store.rows():
                if row['checkpoint'].get('control'):continue
                self.attach(row['id'], project=TaskRelationshipResolver.project(row['command']['value']))
                for upstream in row['spec'].get('dependencies', []):
                    if self.store.get(upstream):
                        self.store.db.execute('INSERT OR IGNORE INTO workflow_edges VALUES(?,?,?)',
                            (upstream, row['id'], bounded({'condition':'success','optional':False,
                             'requires_result':False,'reason':'Migrated existing explicit dependency'})))
                if row['state'] in TERMINAL and not self.result(row['id']):self.publish(row['id'])
            self._acyclic([(e['upstream'],e['downstream']) for e in self.edges()])
            self.store.setting('workflow_schema', 1)
            self.revision('migration', {'schema':1})

    def revision(self, operation, data):
        self.store.db.execute('INSERT INTO workflow_revisions(at,operation,data) VALUES(?,?,?)',
                              (self.store.clock(), operation, bounded(data)))

    def node(self, task):
        with self.store.lock:
            row = self.store.db.execute('SELECT * FROM workflow_nodes WHERE task=?', (task,)).fetchone()
            return {**dict(row), 'data': json.loads(row['data'])} if row else None

    def group(self, identity):
        with self.store.lock:
            row = self.store.db.execute('SELECT data FROM workflow_groups WHERE id=?', (identity,)).fetchone()
            return json.loads(row[0]) if row else None

    def group_for(self, task):
        with self.store.lock:
            row = self.store.db.execute('SELECT w.group_id FROM workflows w JOIN workflow_nodes n '
                                       'ON n.workflow=w.id WHERE n.task=?', (task,)).fetchone()
            return self.group(row[0]) if row else None

    def attach(self, task, *, project=None, goal=None, workflow=None, parent=None):
        with self.store.transaction():
            existing = self.node(task)
            if existing:
                return existing
            row = self.store.get(task)
            if not row:
                raise ValueError('Unknown task')
            if parent and not self.node(parent):
                raise ValueError('Unknown parent task')
            if workflow is None:
                group = next((g for g in self.groups() if project and g['project'] == project), None)
                if group is None:
                    group = {'id': uuid.uuid4().hex, 'workspace': 'local', 'project': project,
                             'goal': (goal or row['command']['value'] or row['command']['kind'])[:2000],
                             'applications': [], 'priority': 0, 'paused': False,
                             'completion_criteria': 'All required branches completed with recorded evidence',
                             'created': self.store.clock()}
                    self.store.db.execute('INSERT INTO workflow_groups VALUES(?,?)', (group['id'], bounded(group)))
                workflow = uuid.uuid4().hex
                self.store.db.execute('INSERT INTO workflows VALUES(?,?,?)',
                    (workflow, group['id'], bounded({'goal': goal or group['goal']})))
            if not self.store.db.execute('SELECT 1 FROM workflows WHERE id=?', (workflow,)).fetchone():
                raise ValueError('Unknown owning workflow')
            self.store.db.execute('INSERT INTO workflow_nodes VALUES(?,?,?,?)',
                (task, workflow, parent, bounded({'created': self.store.clock(), 'role': 'subtask' if parent else 'task'})))
            self.revision('attach', {'task': task, 'workflow': workflow, 'parent': parent})
            return self.node(task)

    def create_workflow(self, *, project, goal):
        """A new workflow in the project's group (created if needed); used for planned project work."""
        with self.store.transaction():
            group = next((g for g in self.groups() if project and g['project'] == project), None)
            if group is None:
                group = {'id': uuid.uuid4().hex, 'workspace': 'local', 'project': project, 'goal': str(goal)[:2000],
                         'applications': [], 'priority': 0, 'paused': False,
                         'completion_criteria': 'All required branches completed with recorded evidence',
                         'created': self.store.clock()}
                self.store.db.execute('INSERT INTO workflow_groups VALUES(?,?)', (group['id'], bounded(group)))
            workflow = uuid.uuid4().hex
            self.store.db.execute('INSERT INTO workflows VALUES(?,?,?)', (workflow, group['id'], bounded({'goal': str(goal)[:2000]})))
            self.revision('workflow', {'workflow': workflow, 'group': group['id']})
            return workflow

    def groups(self):
        with self.store.lock:
            return [json.loads(r[0]) for r in self.store.db.execute('SELECT data FROM workflow_groups ORDER BY rowid')]

    def relation(self, source, target, kind, reason, confidence=1.):
        if kind not in RELATIONS or source == target or not self.store.get(source) or not self.store.get(target):
            raise ValueError('Invalid relationship')
        with self.store.transaction():
            data = {'reason': str(reason)[:2000], 'confidence': float(confidence), 'ordering': False}
            self.store.db.execute('INSERT OR REPLACE INTO task_relationships VALUES(?,?,?,?)',
                                  (source, target, kind, bounded(data)))
            self.revision('relationship', {'source': source, 'target': target, 'kind': kind, **data})

    def edges(self, downstream=None):
        with self.store.lock:
            query, args = 'SELECT * FROM workflow_edges', ()
            if downstream:
                query += ' WHERE downstream=?'; args = (downstream,)
            return [{**dict(r), 'data': json.loads(r['data'])} for r in self.store.db.execute(query, args)]

    def _acyclic(self, edges):
        # Kahn's algorithm is bounded by persisted nodes; no recursive stack limit.
        children, indegree = {}, {}
        for upstream, downstream in edges:
            children.setdefault(upstream, set()).add(downstream)
            indegree.setdefault(upstream, 0)
            indegree[downstream] = indegree.get(downstream, 0)+1
        todo = [node for node, degree in indegree.items() if degree == 0]
        seen = 0
        while todo:
            node = todo.pop(); seen += 1
            for child in children.get(node, ()):
                indegree[child] -= 1
                if not indegree[child]: todo.append(child)
        if seen != len(indegree):
            raise ValueError('Dependency cycle rejected')

    def set_dependencies(self, task, dependencies, reason='Explicit dependency update'):
        """Replace incoming requirements atomically. Optional edges never block readiness."""
        if not isinstance(dependencies, list) or len(dependencies) > 64:
            raise ValueError('At most 64 prerequisites per task')
        with self.store.transaction():
            row = self.store.get(task)
            if not row:
                raise ValueError('Unknown task')
            parsed = []
            for dependency in dependencies:
                data = {'upstream': dependency} if isinstance(dependency, str) else dict(dependency)
                upstream = data.pop('upstream', None)
                if upstream == task or not self.store.get(upstream):
                    raise ValueError('Unknown or cyclic dependency')
                if set(data)-{'condition', 'optional', 'requires_result', 'reason'}:
                    raise ValueError('Unknown dependency fields')
                data = {'condition': 'success', 'optional': False, 'requires_result': False, 'reason': reason, **data}
                if data['condition'] not in CONDITIONS or type(data['optional']) is not bool or type(data['requires_result']) is not bool:
                    raise ValueError('Invalid dependency condition')
                if upstream in [p[0] for p in parsed]:
                    raise ValueError('Duplicate prerequisite')
                parsed.append((upstream, data))
            before = {e['upstream']:{k:v for k,v in e['data'].items() if k != 'reason'} for e in self.edges(task)}
            after = {u:{k:v for k,v in d.items() if k != 'reason'} for u,d in parsed}
            if before == after:
                return
            if row['state'] not in EDITABLE or row['checkpoint'].get('dispatch_at'):
                raise ValueError('Cannot change requirements after dispatch')
            rest = [(e['upstream'], e['downstream']) for e in self.edges() if e['downstream'] != task]
            self._acyclic(rest+[(u, task) for u, _ in parsed])
            self.store.db.execute('DELETE FROM workflow_edges WHERE downstream=?', (task,))
            self.store.db.execute("DELETE FROM task_relationships WHERE source=? AND kind IN ('DEPENDS_ON','CONDITIONAL_ON')", (task,))
            for upstream, data in parsed:
                self.store.db.execute('INSERT INTO workflow_edges VALUES(?,?,?)', (upstream, task, bounded(data)))
                kind = 'DEPENDS_ON' if data['condition']=='success' else 'CONDITIONAL_ON'
                self.store.db.execute('INSERT OR REPLACE INTO task_relationships VALUES(?,?,?,?)',
                    (task,upstream,kind,bounded({'ordering':True,'reason':data['reason'],'confidence':1.})))
            spec = {**row['spec'], 'dependencies': [u for u, _ in parsed],
                    'graph_dependencies':[{'upstream':u,**d} for u,d in parsed]}
            self.store.transition(task, row['state'], reason, spec=spec)
            self.revision('dependencies', {'task': task, 'requirements': [{'upstream': u, **d} for u, d in parsed]})

    def move(self, task, workflow, reason='User moved task'):
        with self.store.transaction():
            row, node = self.store.get(task), self.node(task)
            if not node or not row or row['state'] not in EDITABLE or row['checkpoint'].get('dispatch_at'):
                raise ValueError('Only undispatched tasks can move; history is retained')
            if not self.store.db.execute('SELECT 1 FROM workflows WHERE id=?', (workflow,)).fetchone():
                raise ValueError('Unknown workflow')
            self.store.db.execute('UPDATE workflow_nodes SET workflow=? WHERE task=?', (workflow, task))
            self.revision('move', {'task': task, 'old': node['workflow'], 'new': workflow, 'reason': reason})

    def split(self, task):
        with self.store.transaction():
            row = self.store.get(task)
            if not row or row['state'] not in EDITABLE or row['checkpoint'].get('dispatch_at'):
                raise ValueError('Only undispatched tasks may be split')
            group_id, workflow = uuid.uuid4().hex, uuid.uuid4().hex
            group = {'id':group_id,'workspace':'local','project':None,'goal':row['command']['value'][:2000],
                'applications':[],'priority':0,'paused':False,'completion_criteria':'Recorded task completion',
                'created':self.store.clock()}
            self.store.db.execute('INSERT INTO workflow_groups VALUES(?,?)',(group_id,bounded(group)))
            self.store.db.execute('INSERT INTO workflows VALUES(?,?,?)',(workflow,group_id,bounded({'goal':group['goal']})))
            self.move(task,workflow,'User split incorrectly grouped task; dependencies retained')
            return workflow

    def update_group(self, identity, *, priority=None, paused=None):
        with self.store.transaction():
            group = self.group(identity)
            if not group:
                raise ValueError('Unknown group')
            if priority is not None:
                if type(priority) is not int or not -100 <= priority <= 100:
                    raise ValueError('Group priority must be between -100 and 100')
                group['priority'] = priority
            if paused is not None:
                if type(paused) is not bool: raise ValueError('Pause must be boolean')
                group['paused'] = paused
            self.store.db.execute('UPDATE workflow_groups SET data=? WHERE id=?', (bounded(group), identity))
            self.revision('group', group)

    def result(self, task):
        with self.store.lock:
            row = self.store.db.execute('SELECT data FROM workflow_results WHERE task=? ORDER BY version DESC LIMIT 1', (task,)).fetchone()
            return json.loads(row[0]) if row else None

    def publish(self, task):
        """Called in the lifecycle completion transaction; never upgrades prose to verification."""
        with self.store.transaction():
            row = self.store.get(task)
            if not row or row['state'] not in TERMINAL:
                return None
            old = self.result(task)
            checkpoint = row['checkpoint']
            evidence = checkpoint.get('task_result', {})
            effects = checkpoint.get('effects', [])
            tests = checkpoint.get('tests', {})
            tool = checkpoint.get('tool_checkpoint', {})
            verified = not checkpoint.get('uncertain') and bool(
                row['spec'].get('read_only') or effects or evidence.get('verified') is True
                or tool.get('adaptive', {}).get('goal_verified') is True)
            result = {'task_id': task, 'outcome': row['state'], 'verification': 'verified' if verified else 'unverified',
                'structured_output': evidence.get('structured_output', {'summary': row['outcome'][:8000],
                    'execution_checkpoints': tool.get('checkpoints', [])}),
                'artifacts': effects, 'findings': evidence.get('findings', []),
                'errors': [row['outcome'][:2000]] if row['state'] == 'FAILED' else [],
                'warnings': [] if verified else ['Handler completion alone is not independent verification'],
                'tests': tests, 'version': old['version']+1 if old else 1, 'timestamp': self.store.clock(),
                'provenance': {'source': 'TaskStore committed lifecycle', 'checkpoint': tool.get('task_id'),
                               'input_versions': checkpoint.get('input_versions', {})},
                'context': {'command': {k:v[:2000] for k,v in row['command'].items()}, 'workflow': (self.node(task) or {}).get('workflow')},
                'valid': True}
            if len(bounded(result, 1000000)) > 64000:
                result.update(verification='unverified',structured_output={'summary':row['outcome'][:8000]},artifacts=[])
                result['warnings'].append('Result bundle exceeded handoff limit; inspect full authoritative task checkpoints')
            self.store.db.execute('INSERT INTO workflow_results VALUES(?,?,?)', (task, result['version'], bounded(result)))
            self.revision('result', {'task': task, 'version': result['version'], 'verification': result['verification']})
            return result

    def invalidate(self, task, reason):
        """Invalidate transitive results, never reset terminal tasks or replay effects."""
        with self.store.transaction():
            todo, seen, changed = [task], set(), []
            edges = self.edges()
            while todo:
                current = todo.pop()
                if current in seen: continue
                seen.add(current)
                result = self.result(current)
                if result and result['valid']:
                    changed.append(current)
                    result.update(valid=False, invalidation=str(reason)[:1000])
                    self.store.db.execute('UPDATE workflow_results SET data=? WHERE task=? AND version=?',
                                          (bounded(result), current, result['version']))
                todo.extend(e['downstream'] for e in edges if e['upstream'] == current)
            if changed:self.revision('invalidate', {'tasks': sorted(seen), 'reason': str(reason)[:1000]})

    def fresh(self, result):
        if not result or not result['valid']: return False
        latest = self.result(result['task_id'])
        if not latest or not latest['valid'] or latest['version']!=result['version']:return False
        # Follow versioned input lineage as well: a downstream result can be stale
        # even when no caller has inspected the original producer since its change.
        todo, seen = [result], set()
        while todo:
            current = todo.pop()
            if current['task_id'] in seen:continue
            seen.add(current['task_id'])
            if not current['valid']:return False
            for task, version in current['provenance']['input_versions'].items():
                upstream = self.result(task)
                if not upstream or upstream['version'] != version or not upstream['valid']:return False
                todo.append(upstream)
            # Only read explicitly recorded files, bounded by size; never execute artifacts.
            for artifact in current['artifacts']:
                if artifact.get('kind') == 'file' and artifact.get('sha256'):
                    try:
                        path = Path(artifact['path'])
                        valid = path.stat().st_size <= 32*1024*1024 and hashlib.sha256(path.read_bytes()).hexdigest() == artifact['sha256']
                    except (OSError, KeyError, ValueError):valid = False
                    if not valid:
                        self.invalidate(current['task_id'], 'Recorded artifact changed or became unavailable')
                        return False
        return True

    def evaluate(self, task):
        """Evaluate actual committed outcomes; unknown conditions fail closed."""
        with self.store.transaction():
            blockers, inputs, versions, impossible = [], [], {}, []
            for edge in self.edges(task):
                upstream, data = self.store.get(edge['upstream']), edge['data']
                result = self.result(upstream['id'])
                terminal = upstream['state'] in TERMINAL
                condition = data['condition']
                satisfied = terminal and (condition == 'always' or condition == 'success' and upstream['state'] == 'COMPLETED'
                    or condition == 'failure' and upstream['state'] == 'FAILED')
                if condition in {'tests_pass', 'tests_fail'}:
                    tests = result.get('tests') if result else None
                    satisfied = bool(terminal and result and result['verification'] == 'verified' and isinstance(tests, dict)
                        and tests.get('verified') is True and tests.get('passed') is (condition == 'tests_pass'))
                if result and not self.fresh(result):
                    self.invalidate(upstream['id'], 'Recorded artifact changed or became unavailable')
                    satisfied = False
                if data['requires_result'] and (not result or not self.fresh(result) or result['verification'] != 'verified'):
                    satisfied = False
                if not satisfied and not data['optional']:
                    blockers.append({'task': upstream['id'], 'condition': condition,
                                     'state': upstream['state'], 'reason': 'Prerequisite result does not satisfy condition'})
                    known_test = bool(result and result['valid'] and result['verification']=='verified'
                        and isinstance(result.get('tests'),dict) and result['tests'].get('verified') is True
                        and type(result['tests'].get('passed')) is bool)
                    if terminal and (condition == 'failure' and upstream['state']=='COMPLETED'
                            or condition in {'tests_pass','tests_fail'} and known_test and self.fresh(result)):
                        impossible.append(upstream['id'])
                if satisfied and result and self.fresh(result):
                    inputs.append(result); versions[upstream['id']] = result['version']
            if len(bounded(inputs, 5000000)) > 48000:
                blockers.append({'task':task,'condition':'bounded_result_context','state':'WAITING_USER',
                                 'reason':'Combined result bundle exceeds planner limit; provide a bounded verified summary'})
                inputs = []
            evaluation = {'ready': not blockers, 'blockers': blockers, 'inputs': inputs, 'versions': versions,
                          'impossible': impossible, 'at': self.store.clock()}
            previous = self.store.db.execute('SELECT data FROM workflow_evaluations WHERE task=?', (task,)).fetchone()
            if not previous or {k:v for k,v in json.loads(previous[0]).items() if k != 'at'} != {k:v for k,v in evaluation.items() if k != 'at'}:
                self.store.db.execute('INSERT OR REPLACE INTO workflow_evaluations VALUES(?,?)', (task, bounded(evaluation, 256000)))
                self.revision('evaluate', {'task': task, 'ready': evaluation['ready'], 'blockers': blockers, 'versions': versions})
            return evaluation

    def scheduling_bonus(self, task, rows):
        """Group priority plus bounded downstream importance/critical path; aging stays unbounded."""
        group = self.group_for(task) or {}
        edges, todo, distances, bonus = self.edges(), [(task, 0)], {}, 0.
        while todo:
            current, duration = todo.pop()
            if duration <= distances.get(current, -1): continue
            distances[current] = duration
            row = rows.get(current)
            if row and row['state'] not in TERMINAL:
                duration += min(3600, row['spec'].get('duration_seconds', 300))
                bonus = max(bonus, min(500, row['spec'].get('priority', 0)*2+duration/60))
            todo.extend((e['downstream'], duration) for e in edges if e['upstream'] == current and not e['data']['optional'])
        if not any(e['upstream'] == task for e in edges):
            bonus = 0
        return group.get('priority', 0)*10+bonus

    def snapshot(self):
        with self.store.lock:
            nodes = [dict(r) for r in self.store.db.execute('SELECT * FROM workflow_nodes')]
            rows = {r['id']: r for r in self.store.rows()}
            groups = []
            for group in self.groups():
                workflows = [r[0] for r in self.store.db.execute('SELECT id FROM workflows WHERE group_id=?', (group['id'],))]
                tasks = [n['task'] for n in nodes if n['workflow'] in workflows and n['task'] in rows]
                completed = sum(rows[t]['state'] == 'COMPLETED' for t in tasks)
                groups.append({**group, 'workflows': workflows, 'tasks': tasks, 'completed': completed,
                    'total': len(tasks), 'progress': completed/len(tasks) if tasks else 0,
                    'counts': {s: sum(rows[t]['state'] == s for t in tasks) for s in {rows[t]['state'] for t in tasks}},
                    'artifacts': [a for t in tasks for a in (self.result(t) or {}).get('artifacts', [])],
                    'errors_and_recovery': [{'task': t, **e} for t in tasks for e in self.store.history(t)
                                           if e['state'] in {'FAILED', 'PAUSED', 'RETRY_BACKOFF'}]})
            relations = [{**dict(r), 'data': json.loads(r['data'])} for r in self.store.db.execute('SELECT * FROM task_relationships')]
            revision = self.store.db.execute('SELECT max(revision) FROM workflow_revisions').fetchone()[0] or 0
            evaluations = {r['task']: json.loads(r['data']) for r in self.store.db.execute('SELECT * FROM workflow_evaluations')}
            return {'groups': groups, 'nodes': nodes, 'edges': self.edges(), 'relationships': relations,
                    'evaluations': evaluations, 'revision': revision}


class TaskRelationshipResolver:
    """Exact entities and explicit language first. Similar wording is never an edge.

    Unknown/competing referents become a saved question. Optional semantic hints
    can label context, but cannot authorize an ordering or a side effect.
    """
    def __init__(self, graph, context=None):
        self.graph, self.store = graph, graph.store
        self.context = context

    @staticmethod
    def project(text):
        path = re.search(r'(?i)(?:[a-z]:[\\/][^\n";]+|/[^\s]+)', text)
        named = re.search(r'(?i)\b(?:project|goal|workflow)\s+["\']([^"\']+)["\']', text)
        plain = re.search(r'(?i)\b(?:in|for|on|the|earlier)\s+([\w-]+)\s+(?:project|work)\b', text)
        app = re.search(r'(?i)\b(blender|unreal)\b', text)
        value = named[1] if named else plain[1] if plain else path[0].strip() if path else app[1] if app else None
        return value.casefold().rstrip(' .!?') if value else None

    @staticmethod
    def stage(text):
        if re.search(r'(?i)\b(test|tests|verify|verification)\b', text): return 'test'
        if re.search(r'(?i)\b(fix|repair|patch)\b', text): return 'repair'
        if re.search(r'(?i)\b(find|scan|analyze|analyse|identify)\b', text): return 'analyze'
        return None

    def resolve(self, task, command, include_later=False):
        row = self.store.get(task)
        text = row['original'].get('value', '') or command.value
        project = self.project(text+(' '+command.extra if command.kind == 'code_task' else ''))
        future_named = bool(project or re.search(r'(?i)\b(?:task|tasks)\s*#?\d+', text))
        rows = [r for r in self.store.rows(limit=200) if (r['number'] < row['number'] or include_later and future_named) and r['id'] != task
                and self.graph.node(r['id']) and not r['checkpoint'].get('control')]
        same = [r for r in rows if project and (self.graph.group_for(r['id']) or {}).get('project') == project]
        explicit = re.search(r'(?i)\b(?:after|from|use(?: the)? (?:results?|report) (?:from )?)\s*(?:task|tasks)\s*#?(\d+)((?:\s*(?:,|and)\s*#?\d+)*)', text)
        conditional = bool(re.search(r'(?i)\b(?:if|until)\b.*\b(?:pass|passes|fail|fails)\b', text))
        continuation = conditional or bool(re.search(r'(?i)\b(?:after that|those (?:issues|results|findings)|fix them|test the fixes|previous task|earlier .+ work|do the same|take those|now fix|continue the earlier)\b', text))
        independent = bool(re.search(r'(?i)\b(?:independently|unrelated|separate (?:goal|workflow)|other project)\b', text))
        if re.search(r'(?i)\bother project\b',text) and not project:
            return {'question':'Which other project should this task use? Name its project or an existing task number.','candidates':[]}
        candidates = []
        artifacts = []
        if re.search(r'(?i)\b(?:use|from|based on)\b',text):
            for other in rows:
                result = self.graph.result(other['id'])
                if not result or result['verification']!='verified' or not self.graph.fresh(result):continue
                for artifact in result['artifacts']:
                    path = artifact.get('path','')
                    if path and (path.casefold() in text.casefold() or re.search(r'(?i)(?<![\w.])'+re.escape(Path(path).name)+r'(?![\w.])',text)):
                        artifacts.append(other);break
        if re.search(r'(?i)\bprevious task\b', text) and rows:
            candidates = [rows[-1]]
        elif explicit:
            numbers = [int(explicit[1])]+[int(n) for n in re.findall(r'\d+', explicit[2])]
            candidates = [next((r for r in rows if r['number'] == n), None) for n in numbers]
            if None in candidates: return {'question': 'Referenced task is unavailable; select an existing task number', 'candidates': []}
        elif artifacts:
            if len(artifacts)!=1:
                return {'question':'Several tasks produced that artifact name; select its task number','candidates':[r['id'] for r in artifacts]}
            candidates = artifacts
        elif continuation and not independent:
            pool = same if project else rows
            if not pool and re.search(r'(?i)\bdo the same\b',text):pool = rows
            desired = 'test' if conditional else {'repair': 'analyze', 'test': 'repair'}.get(self.stage(text))
            if desired:
                pool = [r for r in pool if self.stage(r['command']['value']) == desired]
            if not project and self.context:
                context = self.context()
                corroborated = set(context.get('referenced_projects',[])) & set(context.get('active_projects',[]))
                if len(corroborated)==1:
                    scoped = [r for r in pool if (self.graph.group_for(r['id']) or {}).get('project') in corroborated]
                    if scoped:pool = scoped
            # Collapse a single lineage, never use bare recency across competing workflows/projects.
            workflows = {(self.graph.node(r['id']) or {})['workflow'] for r in pool}
            if len(workflows) == 1 and pool:
                candidates = [pool[-1]]
            elif len(pool) == 1:
                candidates = pool
            else:
                return {'question': 'Which task provides the intended context? Choose its persistent task number.',
                        'candidates': [r['id'] for r in pool[-10:]]}
        workflow = None
        if candidates and not independent:
            source_project = (self.graph.group_for(candidates[0]['id']) or {}).get('project')
            if not project or project == source_project:
                workflow = self.graph.node(candidates[0]['id'])['workflow']
        node = self.graph.attach(task, project=project, workflow=workflow)
        for other in same:
            self.graph.relation(task, other['id'], 'SAME_PROJECT_AS', 'Exact project/entity match; no ordering implied')
        if independent:
            for other in rows[-1:]: self.graph.relation(task, other['id'], 'INDEPENDENT_OF', 'Explicit independent request')
        dependencies = []
        for other in candidates:
            condition = 'tests_pass' if re.search(r'(?i)\b(?:if|only (?:if|when)|until)\b.*\b(?:pass|passes)\b', text) else 'tests_fail' if re.search(r'(?i)\bif\b.*\b(?:fail|fails)\b', text) else 'success'
            self.graph.relation(task, other['id'], 'CONTINUATION_OF', 'Explicit reference and compatible task lineage')
            self.graph.relation(other['id'],task,'PRODUCES_INPUT_FOR','Explicit reference to actual producer/result data')
            requires = bool(re.search(r'(?i)\b(?:those|them|results|report|fixes|findings|same)\b', text))
            dependencies.append({'upstream': other['id'], 'condition': condition, 'requires_result': requires,
                                 'reason': 'Resolved explicit task/context reference'})
        return {'node': node, 'dependencies': dependencies, 'project': project}
