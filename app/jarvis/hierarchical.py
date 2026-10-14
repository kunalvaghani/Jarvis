"""Compatibility adapter: existing Brain/ToolRegistry/TaskState, no second agent."""
from dataclasses import asdict
import hashlib
import json
import re
import sqlite3
from contextlib import closing
import time
from pathlib import Path

from .dag_execution import Executor, Tool, validate_plan
from .tools import ToolRegistry

READ_TOOLS = frozenset({'read_file', 'list_files', 'search_files', 'query_resource',
    'web_search', 'scrape_web', 'github_search', 'github_read_file', 'github_pull_request',
    'github_pr_files', 'toolkit_status', 'runtime_capabilities', 'integration_status',
    'knowledge_search', 'tool_search', 'repository_map', 'repository_instructions',
    'skill_list', 'skill_read', 'git_status', 'git_diff', 'git_log', 'mcp_status',
    'application_search', 'windows_command_search', 'realtime_query'})
FILE_WRITES = frozenset({'create_file', 'modify_file', 'append_file'})
NETWORK = frozenset({'web_search', 'scrape_web', 'github_search', 'github_read_file',
                    'github_pull_request', 'github_pr_files'})
LOCAL_SCOPE = frozenset({'read_file', 'list_files', 'search_files', 'query_resource',
    'knowledge_search', 'repository_map', 'repository_instructions', 'git_status', 'git_diff', 'git_log'}) | FILE_WRITES
ARGUMENTS = {'type': 'object', 'additionalProperties': False, 'required': ['value', 'expected'],
    'properties': {key: {'type': 'string', 'maxLength': limit} for key, limit in
        {'value': 1000, 'expected': 500, 'folder': 2000, 'content': 10000,
         'find': 1000, 'browser': 30, 'platform': 30}.items()}}


def settings(options):
    row = options.get('hierarchical_execution', {})
    if not isinstance(row, dict):
        raise ValueError('hierarchical_execution must be an object.')
    result = {'enabled': False, 'parallel_reads': True, 'macro_cache': True,
              'max_concurrency': 3, 'max_seconds': 300, 'max_repairs': 1,
              'max_replans': 1, **row}
    if any(type(result[k]) is not bool for k in ('enabled', 'parallel_reads', 'macro_cache')):
        raise ValueError('DAG feature flags must be booleans.')
    if (type(result['max_concurrency']) is not int or not 1 <= result['max_concurrency'] <= 4 or
            any(type(result[k]) is not int or not 0 <= result[k] <= 2 for k in ('max_repairs', 'max_replans')) or
            type(result['max_seconds']) not in {int, float} or not 1 <= result['max_seconds'] <= 900):
        raise ValueError('Invalid DAG execution limits.')
    return result


def eligible(goal, options):
    """Keep simple commands, live UI, coding, mail and specialized workflows intact."""
    if not settings(options)['enabled']:
        return False
    if re.search(r'\b(click|type|press|open|launch|close|send|delete|trash|unreal|blueprint|spotify|youtube|gmail|calendar|code|script|build|install|run command)\b', goal, re.I):
        return False
    return bool(re.search(r'\b(read|inspect|research|search|list|compare|analy[sz]e)\b', goal, re.I)
        and (re.search(r'\b(and|then|also|files|repositories|sources)\b', goal, re.I) or '\n' in goal))


def schema(tool_names):
    ref = {'type': 'object', 'additionalProperties': False, 'required': ['$ref'], 'properties': {
        '$ref': {'type': 'object', 'additionalProperties': False, 'required': ['step', 'path', 'type'],
            'properties': {'step': {'type': 'string'}, 'path': {'type': 'array', 'maxItems': 8,
                'items': {'anyOf': [{'type': 'string'}, {'type': 'integer'}]}},
                'type': {'type': 'string', 'enum': ['string']}}}}}
    arguments = {**ARGUMENTS, 'required': list(ARGUMENTS['properties']),
        'properties': {k: {'anyOf': [v, ref]} for k, v in ARGUMENTS['properties'].items()}}
    properties = {'id': {'type': 'string'}, 'tool': {'type': 'string', 'enum': sorted(tool_names)},
        'arguments': arguments, 'dependencies': {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 40},
        'expected': {'type': 'string'}, 'permission': {'type': 'string', 'enum': ['read', 'user']},
        'resources': {'type': 'object', 'additionalProperties': False, 'required': ['cpu', 'ram_mb', 'gpu_mb'],
            'properties': {k: {'type': 'integer'} for k in ('cpu', 'ram_mb', 'gpu_mb')}},
        'retry': {'type': 'object', 'additionalProperties': False, 'required': ['attempts', 'backoff_seconds'],
            'properties': {'attempts': {'type': 'integer'}, 'backoff_seconds': {'type': 'number'}}},
        'timeout_seconds': {'type': 'number'}}
    variants = []
    for name in sorted(tool_names):
        fields = {**properties, 'tool': {'type': 'string', 'enum': [name]}}
        if name in LOCAL_SCOPE:
            fields['arguments'] = {**arguments, 'properties': {**arguments['properties'],
                'folder': {'type': 'string', 'minLength': 1, 'maxLength': 2000}}}
        variants.append({'type': 'object', 'additionalProperties': False,
            'required': list(properties), 'properties': fields})
    return {'type': 'object', 'additionalProperties': False, 'required': ['version', 'steps'],
        'properties': {'version': {'type': 'integer', 'enum': [1]}, 'steps': {'type': 'array',
            'minItems': 1, 'maxItems': 40, 'items': {'anyOf': variants}}}}


def literal_reads(goal):
    """Compile only a fully specified read list; no intent model or guessed target."""
    match = re.fullmatch(r'read (.+?) in (this folder|current folder|selected folder)(?:,? then report (?:both|all)(?: file)? contents)?[.]?', goal.strip(), re.I)
    if not match:
        return None
    names = re.split(r'\s+and\s+(?:read\s+)?', match[1], flags=re.I)
    if not 2 <= len(names) <= 20 or any(not re.fullmatch(r'[\w .-]+\.[\w]+', name) for name in names):
        return None
    return {'version': 1, 'steps': [{'id': 'read'+str(i), 'tool': 'read_file',
        'arguments': {'value': name, 'expected': 'Read exact file', 'folder': match[2]},
        'dependencies': [], 'expected': 'File bytes match fresh readback', 'permission': 'read',
        'resources': {'cpu': 1, 'ram_mb': 32, 'gpu_mb': 0},
        'retry': {'attempts': 1, 'backoff_seconds': .1}, 'timeout_seconds': 60} for i, name in enumerate(names)]}


def legacy_step(name, arguments):
    return {'action': name, 'browser': 'chrome', 'folder': '', 'content': '',
            'find': '', 'platform': '', **arguments}


def adapters(brain, goal):
    registry = ToolRegistry(brain.actions)
    offered = {row['action'] for row in registry.catalog(goal)}
    result = {}
    for name in sorted(offered & (READ_TOOLS | FILE_WRITES)):
        def authorize(arguments, name=name):
            from .agent_events import check_policy
            from .brain import validate_plan as legacy_validate
            step = legacy_step(name, arguments)
            allowed = getattr(brain.actions, 'allowed_tools', None)
            if isinstance(allowed, (set, frozenset)) and name not in allowed:
                raise ValueError('DAG tool is outside current task scope.')
            check_policy(brain.actions, name)
            legacy_validate({'steps': [step]})
            brain.validate_remaining([step], goal)
            if name in {'read_file', 'create_file', 'modify_file', 'append_file'}:
                from .toolkits import scoped_path
                root = Path(brain.actions._task_folder(arguments.get('folder', ''), lambda: False)).resolve(strict=True)
                scoped_path(root, arguments['value'])
        def call(arguments, cancelled, name=name):
            row = registry.execute(legacy_step(name, arguments), cancelled)
            return {'tool': row.tool, 'backend': row.backend, 'evidence': row.evidence}
        def verify(arguments, output, name=name):
            if (not isinstance(output, dict) or output.get('tool') != name or
                    not isinstance(output.get('evidence'), str) or not output['evidence'].strip()):
                return False
            evidence = output['evidence']
            if re.match(r'(?i)^(error|failed|task paused|unavailable|not available|I couldn.t)', evidence):
                return False
            if name in {'read_file', 'create_file', 'modify_file', 'append_file'}:
                from .toolkits import scoped_path, read_text
                root = Path(brain.actions._task_folder(arguments.get('folder', ''), lambda: False)).resolve(strict=True)
                current = read_text(scoped_path(root, arguments['value']))
                if name == 'read_file':
                    return current == evidence
                if name == 'create_file' or name == 'modify_file' and not arguments.get('find'):
                    return current == arguments.get('content')
                # Existing exact-replacement/append tools independently read back bytes.
                # Require their receipt plus a fresh final-content observation.
                return bool(arguments.get('content') in current and
                    ('verified' in evidence.casefold() or 'read back' in evidence.casefold() or 'appended' in evidence.casefold() or 'updated' in evidence.casefold()))
            if name in NETWORK:
                # This verifies transport/shape, not truth, relevance or completeness.
                try:
                    payload = json.loads(evidence)
                except ValueError:
                    return False
                return isinstance(payload, (dict, list)) and bool(payload) and not (isinstance(payload, dict) and payload.get('error'))
            return True  # Receipt validity; completion claims state this narrow scope.
        result[name] = Tool(name, ARGUMENTS, call, verify, name in READ_TOOLS,
                            'files' if name in FILE_WRITES | {'read_file', 'list_files', 'search_files', 'query_resource'} else '', authorize)
    return result


def fingerprint(tools, options, environment=None):
    data = {'version': 1, 'options': settings(options), 'tools': {k: {
        'schema': v.schema, 'read_only': v.read_only, 'resource': v.resource} for k, v in tools.items()}}
    data['environment'] = environment or {}
    data['implementations'] = {name: hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest()
        for name in ('hierarchical.py', 'dag_execution.py', 'tools.py', 'toolkits.py', 'brain.py', 'agent_events.py')}
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


class MacroMemory:
    """Procedural tables extend the existing conversation database; no output cache."""
    def __init__(self, base):
        from .agent_context import scoped
        self.path = scoped(base, '.jarvis-runtime/conversations.sqlite3')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=1)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS dag_macros(intent TEXT PRIMARY KEY, fingerprint TEXT, plan TEXT, verified_at REAL, successes INTEGER, hits INTEGER)')
    @staticmethod
    def key(goal):
        # Exact normalized goal only. Never similarity-based authorization.
        return hashlib.sha256(goal.strip().encode()).hexdigest()
    def lookup(self, goal, signature):
        with closing(sqlite3.connect(self.path, timeout=1)) as db, db:
            row = db.execute('SELECT plan FROM dag_macros WHERE intent=? AND fingerprint=? AND verified_at>?',
                (self.key(goal), signature, time.time()-86400)).fetchone()
            if row:
                db.execute('UPDATE dag_macros SET hits=hits+1 WHERE intent=?', (self.key(goal),))
                return json.loads(row[0])
    def remember(self, goal, signature, graph, tools):
        if any(not tools[row['tool']].read_only for row in graph['steps']):
            return  # Effectful macros require a future explicit parameter/approval contract.
        with closing(sqlite3.connect(self.path, timeout=1)) as db, db:
            db.execute('INSERT INTO dag_macros VALUES (?,?,?,?,1,0) ON CONFLICT(intent) DO UPDATE SET fingerprint=excluded.fingerprint,plan=excluded.plan,verified_at=excluded.verified_at,successes=successes+1',
                (self.key(goal), signature, json.dumps(graph), time.time()))
            db.execute('DELETE FROM dag_macros WHERE intent NOT IN (SELECT intent FROM dag_macros ORDER BY verified_at DESC LIMIT 64)')


def run(brain, goal, cancelled):
    started = time.monotonic()
    options = settings(brain.options)
    tools = adapters(brain, goal)
    if not tools:
        return None  # No dispatch has happened; preserve existing specialized planner.
    tool_selection_seconds = time.monotonic()-started
    signature = fingerprint(tools, brain.options, {'files_root': str(brain.actions.config.get('files_root', '')),
        'project_roots': brain.actions.config.get('project_roots', [])})
    memory_started = time.monotonic()
    memory = MacroMemory(brain.actions.base) if options['macro_cache'] and not brain.actions.config.get('_ui_verification') else None
    prior = getattr(brain.actions, 'resume_source', None)
    previous = (prior or {}).get('dag', {}) if isinstance(prior, dict) else {}
    restored = None
    if previous.get('fingerprint') == signature and not any(r.get('effect') for r in previous.get('steps', {}).values()):
        graph = previous.get('graph')
        restored = {identifier: row for identifier, row in previous.get('steps', {}).items()
            if row.get('status') == 'succeeded' and row.get('result', {}).get('tool') == 'read_file'}
    else:
        graph = memory.lookup(goal, signature) if memory else None
    cached = graph is not None
    if graph is None and 'read_file' in tools:
        graph = literal_reads(goal)
    memory_seconds = time.monotonic()-memory_started
    planning_started = time.monotonic()
    if graph is None:
        acquisition = getattr(brain.actions, 'acquisition', None)
        learning_context = acquisition.prepare(goal, cancelled) if acquisition is not None else {}
        for attempt in range(options['max_repairs']+1):
            if cancelled():
                return 'Task cancelled before planning.'
            graph = brain.client.request('dag_plan', cancelled, goal=goal,
                learning_context=learning_context,
                tools=[{'action': k, 'read_only': t.read_only, 'arguments': t.schema} for k, t in tools.items()],
                validation_error=error if attempt else '', steps_left=brain.options.get('max_task_actions', 20))
            try:
                steps = validate_plan(graph, tools)
                if sum(s.retry['attempts'] for s in steps) > brain.options.get('max_task_actions', 20):
                    raise ValueError('DAG exceeds existing task action budget.')
                break
            except ValueError as exc:
                error = str(exc)
                if attempt == options['max_repairs']:
                    raise ValueError('DAG rejected before execution: ' + error) from exc
    planning_seconds = time.monotonic()-planning_started
    validation_started = time.monotonic()
    steps = validate_plan(graph, tools)
    if sum(s.retry['attempts'] for s in steps) > brain.options.get('max_task_actions', 20):
        raise ValueError('Cached DAG exceeds task action budget.')
    validation_seconds = time.monotonic()-validation_started
    state = brain.actions.task_state
    def checkpoint(rows):
        state.update_dag(graph, rows, signature, {'planning_seconds': planning_seconds,
            'cache_hit': cached, 'planner_model': brain.options.get('planner'),
            'tool_selection_seconds': tool_selection_seconds, 'memory_retrieval_seconds': memory_seconds,
            'dag_validation_seconds': validation_seconds,
            'elapsed_seconds': time.monotonic()-started})
    def progress(event):
        brain.actions.report('plan', 'DAG ' + event['step'] + ': ' + event['tool'] + ' · ' + event['status'])
    import psutil
    concurrency = options['max_concurrency'] if options['parallel_reads'] else 1
    battery = psutil.sensors_battery()
    if psutil.virtual_memory().available < 1024**3 or psutil.cpu_percent() > 85 or battery and not battery.power_plugged and battery.percent < 20:
        concurrency = 1
    result = Executor(tools, concurrency, max_seconds=options['max_seconds'],
                      checkpoint=checkpoint, progress=progress).run(steps, cancelled, restored)
    spent = sum(r['attempts'] for r in result['steps'].values())
    # An uncertain effect closes recovery. Only read-only affected work may be
    # replanned, and successful independent observations remain task-scoped.
    for revision in range(options['max_replans']):
        if (result['status'] != 'failed' or cancelled() or
                any(not tools[s.tool].read_only for s in steps) or
                time.monotonic()-started >= options['max_seconds']):
            break
        completed_ids = {key for key, row in result['steps'].items() if row['status'] == 'succeeded'}
        preserved = [row for row in graph['steps'] if row['id'] in completed_ids]
        observations = {key: result['steps'][key] for key in completed_ids}
        candidate = brain.client.request('dag_plan', cancelled, goal=goal,
            tools=[{'action': k, 'read_only': t.read_only, 'arguments': t.schema} for k, t in tools.items() if t.read_only],
            completed=observations, failures={k: r for k, r in result['steps'].items() if k not in completed_ids},
            validation_error='Replan only failed/blocked work; successful IDs are fixed and may be dependencies. Never repeat their tool/arguments.',
            steps_left=brain.options.get('max_task_actions', 20)-spent)
        if not isinstance(candidate, dict) or set(candidate) != {'version', 'steps'} or not isinstance(candidate['steps'], list):
            break
        if any(row.get('id') in completed_ids for row in candidate['steps'] if isinstance(row, dict)):
            break
        if any(not isinstance(row, dict) or row.get('tool') not in tools or
               not tools[row['tool']].read_only for row in candidate['steps']):
            break
        forbidden = {(r['tool'], json.dumps(r['arguments'], sort_keys=True)) for r in preserved}
        if any((row.get('tool'), json.dumps(row.get('arguments'), sort_keys=True)) in forbidden for row in candidate['steps'] if isinstance(row, dict)):
            break
        revised = {'version': 1, 'steps': preserved+candidate['steps']}
        try:
            revised_steps = validate_plan(revised, tools)
            remaining_budget = brain.options.get('max_task_actions', 20)-spent
            if sum(s.retry['attempts'] for s in revised_steps if s.id not in completed_ids) > remaining_budget:
                break
        except ValueError:
            break
        graph, steps = revised, revised_steps
        result = Executor(tools, concurrency, max_seconds=max(.05, options['max_seconds']-(time.monotonic()-started)),
            checkpoint=checkpoint, progress=progress).run(steps, cancelled, observations)
        spent += sum(row['attempts'] for identifier, row in result['steps'].items() if identifier not in completed_ids)
    result['dispatched_attempts'] = spent
    brain.last_dag_result = result
    if result['status'] == 'completed':
        if memory:
            memory.remember(goal, signature, graph, tools)
        evidence = [r['result']['evidence'][:2500] for r in result['steps'].values()]
        if re.search(r'\b(summarize|summarise|summary|analy[sz]e|compare|explain|research)\b', goal, re.I):
            # Preserve semantic-answer behavior: gathering data is not the same
            # as answering an analysis request. Reuse the registered local think
            # tool as ReWOO's solver, with no new provider or action privileges.
            if spent >= brain.options.get('max_task_actions', 20):
                return 'Task paused: reads verified, but no action budget remains for the requested analysis.'
            state.checkpoint('dag_response_generation', action='think', evidence='Bounded read-only synthesis from task observations.')
            registry = ToolRegistry(brain.actions)
            started_response = time.monotonic()
            excerpts = [text[:max(40, 8000//max(1, len(evidence)))] for text in evidence]
            context = json.dumps({'observations': excerpts, 'excerpted': True}, ensure_ascii=False)
            while len(context) > 10000:
                excerpts = [text[:len(text)//2] for text in excerpts]
                context = json.dumps({'observations': excerpts, 'excerpted': True}, ensure_ascii=False)
            response = registry.execute({'action': 'think', 'value': goal,
                'expected': 'Answer from supplied observations, with uncertainty and sources',
                'content': context,
                'folder': '', 'browser': 'chrome', 'find': '', 'platform': ''}, cancelled)
            if not response.evidence.strip() or re.match(r'(?i)^(error|failed|task paused)', response.evidence):
                return 'Task paused: reads verified, but response synthesis failed.'
            state.checkpoint('dag_response_timing', source='monotonic_clock',
                evidence=str(round(time.monotonic()-started_response, 4)))
            return response.evidence
        return 'Completed the dependency plan. Tool receipts and local file readback verified; retrieved content is reference data.\n' + '\n\n'.join(evidence)[:10000]
    failed = [(key, row.get('error', row['status'])) for key, row in result['steps'].items() if row['status'] != 'succeeded']
    return 'Task paused: successful steps retained; no uncertain effect was replayed. ' + '; '.join(k+': '+v for k, v in failed)[:1500]
