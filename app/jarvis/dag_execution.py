"""Bounded task-scoped DAG scheduling over existing synchronous tool adapters.

Thread workers fit Jarvis's existing transports. A deadline requests cooperative
cancellation; workers are drained before returning, never abandoned or replayed.
"""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import copy
import hashlib
from dataclasses import dataclass
import json
import math
import re
import threading
import time
import uuid

from .repo_analysis import validate


class CapabilityError(ValueError):
    pass


@dataclass(frozen=True)
class Tool:
    name: str
    schema: dict
    call: object
    verify: object
    read_only: bool = True
    resource: str = ''  # Conflicting resources always serialize.
    authorize: object = lambda arguments: None


@dataclass(frozen=True)
class Step:
    id: str
    tool: str
    arguments: dict
    dependencies: tuple
    expected: str
    permission: str
    resources: dict
    retry: dict
    timeout_seconds: float


# Ready-step admission heuristic: a bounded evolution surface (jarvis/evolution_surfaces.py).
# All-zero weights keep the planner's own order; a positive critical-path weight admits
# steps with longer downstream chains first. Safety rules (effect serialization,
# resource budgets, verification) are applied after ordering and never depend on it.
SCHEDULING = {'critical_path_weight': 0.0, 'read_only_bias': 0.0}


def admission_order(steps, tools, weights=None):
    """Return steps in admission order; stable on the plan order for equal priority."""
    weights = SCHEDULING if weights is None else weights
    children = {s.id: [] for s in steps}
    for step in steps:
        for dependency in step.dependencies:
            children[dependency].append(step.id)
    depth = {}
    def chain(identifier):  # validate_plan has already rejected cycles; plans hold at most 40 steps.
        if identifier not in depth:
            depth[identifier] = 1 + max((chain(c) for c in children[identifier]), default=0)
        return depth[identifier]
    for step in steps:
        chain(step.id)
    def priority(pair):
        index, step = pair
        bias = weights['read_only_bias'] if tools[step.tool].read_only else 0.
        return (-(weights['critical_path_weight'] * depth[step.id] + bias), index)
    return [step for _, step in sorted(enumerate(steps), key=priority)]


def bounded_number(value, low, high):
    return type(value) in {int, float} and math.isfinite(value) and low <= value <= high


def bounded_payload(value, maximum):
    """Bound JSON structure before encoding, including hostile depth/cycles."""
    pending=[(value,0)];nodes=0;characters=0
    while pending:
        item,depth=pending.pop();nodes+=1
        if depth>20 or nodes>6000:
            raise ValueError('DAG payload exceeds structural limits.')
        if isinstance(item,str):characters+=len(item)
        elif isinstance(item,dict):
            if len(item)>1000 or any(not isinstance(k,str) for k in item):raise ValueError('Invalid DAG object.')
            characters+=sum(len(k) for k in item)
            pending.extend((v,depth+1) for v in item.values())
        elif isinstance(item,list):
            if len(item)>1000:raise ValueError('DAG array exceeds limit.')
            pending.extend((v,depth+1) for v in item)
        elif item is not None and type(item) not in (bool,int,float):raise ValueError('Invalid DAG JSON value.')
        elif type(item) is float and not math.isfinite(item):raise ValueError('Nonfinite DAG value.')
        if characters>maximum:raise ValueError('DAG payload exceeds text budget.')
    if len(json.dumps(value,allow_nan=False))>maximum:raise ValueError('DAG payload exceeds encoded budget.')


def step_binding(step, arguments):
    from dataclasses import asdict
    return hashlib.sha256(json.dumps({'step':asdict(step),'resolved':arguments},sort_keys=True,allow_nan=False).encode()).hexdigest()


def references(value, depth=0):
    if depth > 20:
        raise ValueError('Result references exceed nesting limit.')
    if isinstance(value, dict):
        if '$ref' in value:
            ref = value['$ref']
            if (set(value) != {'$ref'} or not isinstance(ref, dict) or
                    set(ref) != {'step', 'path', 'type'} or not isinstance(ref['step'], str) or
                    not isinstance(ref['type'], str) or ref['type'] not in {'string', 'integer', 'number', 'boolean', 'object', 'array'} or
                    not isinstance(ref['path'], list) or len(ref['path']) > 8 or
                    any(not (type(k) is int and 0 <= k < 1000 or
                        isinstance(k, str) and 0 < len(k) < 100 and not k.startswith('__')) for k in ref['path'])):
                raise ValueError('Malformed typed result reference.')
            yield ref
        else:
            for item in value.values():
                yield from references(item, depth+1)
    elif isinstance(value, list):
        for item in value:
            yield from references(item, depth+1)


def argument_shape(schema, value):
    """Validate literals now; references are validated again against resolved types."""
    if isinstance(value, dict) and '$ref' in value:
        ref = list(references(value))[0]
        kind = schema.get('type')
        if kind and ref['type'] not in ([kind] if isinstance(kind, str) else kind):
            raise ValueError('Reference type does not match tool argument schema.')
        return
    if isinstance(value, dict):
        shallow = dict(schema)
        shallow['properties'] = {k: {} for k in schema.get('properties', {})}
        validate(shallow, value)
        for key, item in value.items():
            argument_shape(schema.get('properties', {}).get(key, {}), item)
    elif isinstance(value, list):
        shallow = {**schema, 'items': {}}
        validate(shallow, value)
        for item in value:
            argument_shape(schema.get('items', {}), item)
    else:
        validate(schema, value)
        if isinstance(value, str) and len(value) < schema.get('minLength', 0):
            raise ValueError('Tool argument is empty.')
        if type(value) in {int, float} and not bounded_number(value, schema.get('minimum', -1e100), schema.get('maximum', 1e100)):
            raise ValueError('Tool argument outside numeric bounds.')


def validate_plan(plan, tools, budgets=None):
    bounded_payload(plan,100000)
    budgets = budgets or {'cpu': 4, 'ram_mb': 256, 'gpu_mb': 0}
    if (not isinstance(plan, dict) or set(plan) != {'version', 'steps'} or
            type(plan['version']) is not int or plan['version'] != 1 or
            not isinstance(plan['steps'], list) or not 1 <= len(plan['steps']) <= 40):
        raise ValueError('Invalid bounded DAG envelope.')
    steps, ids = [], set()
    fields = {'id', 'tool', 'arguments', 'dependencies', 'expected', 'permission', 'resources', 'retry', 'timeout_seconds'}
    for row in plan['steps']:
        if not isinstance(row, dict) or set(row) != fields:
            raise ValueError('DAG steps must contain exactly the declared schema fields.')
        identifier = row['id']
        if not isinstance(identifier, str) or not re.fullmatch('[a-zA-Z][a-zA-Z0-9_]{0,39}', identifier) or identifier in ids:
            raise ValueError('Step IDs must be bounded and unique.')
        ids.add(identifier)
        tool = tools.get(row['tool']) if isinstance(row['tool'], str) else None
        if tool is None:
            raise CapabilityError('Unavailable registered DAG tool: ' + str(row['tool']))
        deps = row['dependencies']
        if not isinstance(deps, list) or len(deps) > 40 or not all(isinstance(d, str) for d in deps) or len(set(deps)) != len(deps):
            raise ValueError('Invalid dependencies.')
        if not isinstance(row['arguments'], dict):
            raise ValueError('Tool arguments must be objects.')
        argument_shape(tool.schema, row['arguments'])
        refs = list(references(row['arguments']))
        if refs and not tool.read_only:
            raise ValueError('Effectful arguments require literal user-grounded values, not result references.')
        if not refs:
            tool.authorize(row['arguments'])
        if row['permission'] != ('read' if tool.read_only else 'user'):
            raise ValueError('Plan permissions conflict with trusted tool metadata.')
        if not isinstance(row['expected'], str) or not 1 <= len(row['expected'].strip()) <= 500:
            raise ValueError('A step needs bounded verification criteria.')
        resources = row['resources']
        if (not isinstance(resources, dict) or set(resources) != set(budgets) or
                any(type(v) is not int or not 0 <= v <= budgets[k] for k, v in resources.items()) or
                resources['cpu'] < 1 or resources['ram_mb'] < 32):
            raise ValueError('Impossible resource reservation.')
        retry = row['retry']
        if (not isinstance(retry, dict) or set(retry) != {'attempts', 'backoff_seconds'} or
                type(retry['attempts']) is not int or not 1 <= retry['attempts'] <= (3 if tool.read_only else 1) or
                not bounded_number(retry['backoff_seconds'], .01, 5) or
                not bounded_number(row['timeout_seconds'], .05, 120)):
            raise ValueError('Invalid timeout/retry policy; effects cannot be retried.')
        steps.append(Step(**{**copy.deepcopy(row), 'dependencies': tuple(deps)}))
    by_id = {s.id: s for s in steps}
    visiting, ancestors = set(), {}
    def visit(identifier):
        if identifier in ancestors:
            return ancestors[identifier]
        if identifier not in by_id or identifier in visiting:
            raise ValueError('Missing dependency or cycle in DAG.')
        visiting.add(identifier)
        result = set()
        for dep in by_id[identifier].dependencies:
            result.add(dep)
            result.update(visit(dep))
        visiting.remove(identifier)
        ancestors[identifier] = result
        return result
    for step in steps:
        prior = visit(step.id)
        for ref in references(step.arguments):
            if ref['step'] not in prior:
                raise ValueError('Result reference requires an explicit dependency.')
    return tuple(steps)


def resolve(value, state):
    if isinstance(value, dict) and '$ref' in value:
        ref = list(references(value))[0]
        result = state[ref['step']]['result']
        try:
            for key in ref['path']:
                if isinstance(result, dict) and isinstance(key, str):
                    result = result[key]
                elif isinstance(result, list) and type(key) is int:
                    result = result[key]
                else:
                    raise ValueError('Invalid result lookup type.')
        except (KeyError, IndexError):
            raise ValueError('Result lookup path does not exist.') from None
        validate({'type': ref['type']}, result)
        return copy.deepcopy(result)
    if isinstance(value, dict):
        return {key: resolve(item, state) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve(item, state) for item in value]
    return value


class Executor:
    def __init__(self, tools, max_concurrency=3, budgets=None, max_seconds=300,
                 checkpoint=lambda state: None, progress=lambda event: None):
        if type(max_concurrency) is not int or not 1 <= max_concurrency <= 4 or not bounded_number(max_seconds, .05, 900):
            raise ValueError('Invalid bounded executor configuration.')
        self.tools, self.concurrency = tools, max_concurrency
        self.budgets = budgets or {'cpu': 4, 'ram_mb': 256, 'gpu_mb': 0}
        self.max_seconds, self.checkpoint, self.progress = max_seconds, checkpoint, progress

    def run(self, steps, cancelled=lambda: False, restored=None):
        # Revalidate even a caller-created Step tuple before dispatch.
        from dataclasses import asdict
        graph = {'version': 1, 'steps': [{**asdict(s), 'dependencies': list(s.dependencies)} for s in steps]}
        steps = validate_plan(graph, self.tools, self.budgets)
        order = admission_order(steps, self.tools)
        rows = {s.id: {'status': 'pending', 'attempts': 0} for s in steps}
        if restored:
            for step in steps:
                old = restored.get(step.id, {})
                if (old.get('status') == 'succeeded' and self.tools[step.tool].read_only and
                        all(rows[dep]['status']=='succeeded' for dep in step.dependencies)):
                    args = resolve(step.arguments, rows)
                    argument_shape(self.tools[step.tool].schema,args)
                    self.tools[step.tool].authorize(args)
                    if old.get('binding') == step_binding(step,args) and self.tools[step.tool].verify(args, old.get('result')) is True:
                        rows[step.id] = copy.deepcopy(old)
                elif old.get('status') != 'pending' and not self.tools[step.tool].read_only:
                    raise ValueError('Effectful checkpoint requires fresh inspection; never replayed.')
        started = time.monotonic()
        trace_id=uuid.uuid4().hex
        running, reservations, tokens, ready_at = {}, {}, {}, {}
        pool = ThreadPoolExecutor(max_workers=self.concurrency, thread_name_prefix='Jarvis DAG')
        interrupted = False
        def save():
            self.checkpoint(copy.deepcopy(rows))
        def work(step, arguments, stop):
            tool = self.tools[step.tool]
            now = time.monotonic()
            tool.authorize(arguments)
            if cancelled() or stop.is_set():
                raise InterruptedError('Task cancelled before dispatch.')
            output = tool.call(arguments, lambda: cancelled() or stop.is_set())
            execution = time.monotonic()-now
            if stop.is_set() or execution > step.timeout_seconds:
                raise TimeoutError('Tool exceeded deadline; worker drained, effect not replayed.')
            bounded_payload(output,24000)
            verify_started = time.monotonic()
            if tool.verify(arguments, output) is not True:
                raise ValueError('Deterministic verification failed.')
            return output, execution, time.monotonic()-verify_started
        try:
            save()
            while any(r['status'] in {'pending', 'running', 'retry_wait'} for r in rows.values()):
                now = time.monotonic()
                if cancelled() or now-started > self.max_seconds:
                    interrupted = True
                    for stop in tokens.values():
                        stop.set()
                    for row in rows.values():
                        if row['status'] in {'pending', 'retry_wait'}:
                            row['status'] = 'cancelled'
                for future, (step, admitted) in list(running.items()):
                    if now-admitted > step.timeout_seconds:
                        tokens[step.id].set()
                    if not future.done():
                        continue
                    row = rows[step.id]
                    try:
                        output, execution, verification = future.result()
                        if interrupted or tokens[step.id].is_set():
                            raise InterruptedError('Task cancelled; result retained only as unverified.')
                        row.update(status='succeeded', result=output, execution_seconds=execution,
                                   verification_seconds=verification)
                    except Exception as exc:
                        retryable = (self.tools[step.tool].read_only and isinstance(exc, (OSError, TimeoutError))
                                     and not isinstance(exc, InterruptedError) and not interrupted)
                        retry = retryable and row['attempts'] < step.retry['attempts']
                        row.update(status='retry_wait' if retry else ('cancelled' if interrupted else 'failed'),
                                   error_type=type(exc).__name__, error='DAG tool failed: '+type(exc).__name__,
                                   uncertain_effect=not self.tools[step.tool].read_only)
                        ready_at[step.id] = now+step.retry['backoff_seconds']*2**(row['attempts']-1)
                    running.pop(future)
                    reservations.pop(step.id)
                    tokens.pop(step.id)
                    self.progress({'step': step.id, 'tool': step.tool, 'status': row['status'],'trace_id':trace_id})
                    save()
                for step in order:
                    row = rows[step.id]
                    if row['status'] not in {'pending', 'retry_wait'}:
                        continue
                    deps = [rows[dep]['status'] for dep in step.dependencies]
                    if any(d in {'failed', 'blocked', 'cancelled'} for d in deps):
                        row.update(status='blocked', error='Dependency did not verify.')
                        save()
                        continue
                    if any(d != 'succeeded' for d in deps) or now < ready_at.get(step.id, 0) or len(running) >= self.concurrency:
                        continue
                    tool = self.tools[step.tool]
                    if ((not tool.read_only and any(not self.tools[s.tool].read_only for s,_ in running.values())) or
                            tool.resource and any(self.tools[s.tool].resource == tool.resource and
                            not (tool.read_only and self.tools[s.tool].read_only) for s, _ in running.values()) or
                            any(sum(r[k] for r in reservations.values())+step.resources[k] > self.budgets[k] for k in self.budgets)):
                        continue
                    try:
                        arguments = resolve(step.arguments, rows)
                        argument_shape(tool.schema, arguments)
                        tool.authorize(arguments)  # Admission plus a fresh check inside the worker.
                    except Exception as exc:
                        row.update(status='failed', error_type=type(exc).__name__, error='DAG admission failed: '+type(exc).__name__)
                        save()
                        continue
                    row.update(status='running', attempts=row['attempts']+1,
                               queue_seconds=now-started, effect=not tool.read_only,
                               binding=step_binding(step,arguments),trace_id=trace_id)
                    # Durable running state precedes dispatch, even for irreversible tools.
                    save()
                    stop = tokens[step.id] = threading.Event()
                    reservations[step.id] = step.resources
                    running[pool.submit(work, step, arguments, stop)] = (step, time.monotonic())
                    self.progress({'step': step.id, 'tool': step.tool, 'status': 'running','trace_id':trace_id})
                if running:
                    wait(running, timeout=.02, return_when=FIRST_COMPLETED)
                elif any(r['status'] == 'retry_wait' for r in rows.values()):
                    time.sleep(.01)
                elif any(r['status'] == 'pending' for r in rows.values()):
                    raise ValueError('DAG deadlock; no admissible task.')
            return {'trace_id':trace_id,'status': 'cancelled' if interrupted else ('completed' if all(r['status'] == 'succeeded' for r in rows.values()) else 'failed'),
                    'steps': rows, 'total_seconds': time.monotonic()-started}
        finally:
            for stop in tokens.values():
                stop.set()
            pool.shutdown(wait=True, cancel_futures=True)
