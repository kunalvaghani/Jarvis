"""Sealed fitness benchmarks. Each returns (per-example scores, metadata).

Every benchmark drives the candidate's real module (DAG executor, ToolRegistry search,
ReasoningBank retrieval, Cognition perception, read-retry, prompt router). Data come from the
sealed evaluator directory; candidates never see the held-out split.
"""
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace


def dag_makespan(data, options):
    """Wall-clock makespan (ms, lower is better) of synthetic DAGs with sleeping tools."""
    from jarvis.dag_execution import Executor, Tool, validate_plan
    def sleeper(arguments, cancelled):
        deadline = time.perf_counter() + arguments['ms'] / 1000
        while time.perf_counter() < deadline:
            if cancelled():
                raise InterruptedError('cancelled')
            time.sleep(min(.002, max(0, deadline - time.perf_counter())))
        return 'done'
    schema = {'type': 'object', 'properties': {'ms': {'type': 'integer', 'minimum': 1, 'maximum': 2000}}, 'required': ['ms']}
    tools = {'work': Tool('work', schema, sleeper, lambda a, out: out == 'done'),
             'effect': Tool('effect', schema, sleeper, lambda a, out: out == 'done', read_only=False)}
    scores = []
    for case in data['cases']:
        steps = [{'id': s['id'], 'tool': 'work' if s.get('read_only', True) else 'effect', 'arguments': {'ms': s['ms']},
                  'dependencies': s['deps'], 'expected': 'Sleep completed.',
                  'permission': 'read' if s.get('read_only', True) else 'user',
                  'resources': {'cpu': 1, 'ram_mb': 32, 'gpu_mb': 0},
                  'retry': {'attempts': 1, 'backoff_seconds': .01}, 'timeout_seconds': 10} for s in case['steps']]
        plan = validate_plan({'version': 1, 'steps': steps}, tools)
        started = time.perf_counter()
        result = Executor(tools, max_concurrency=case['concurrency']).run(plan)
        elapsed = (time.perf_counter() - started) * 1000
        if result['status'] != 'completed':
            raise RuntimeError('DAG benchmark case did not complete: ' + result['status'])
        scores.append(round(elapsed, 3))
    return scores, {'unit': 'ms', 'objective': 'min'}


def tool_selection(data, options):
    """Reciprocal rank of the first acceptable tool in the real ToolRegistry search (higher is better)."""
    from jarvis.tools import ToolRegistry
    with tempfile.TemporaryDirectory() as folder:
        actions = SimpleNamespace(base=Path(folder), config={}, allowed_tools=None, skills=None,
                                  execute=lambda command, cancelled: None, report=lambda *args: None)
        registry = ToolRegistry(actions)
        scores, hits = [], 0
        for case in data['cases']:
            names = [row.get('action') for row in registry.search(case['query'], limit=12)]
            rank = next((i for i, name in enumerate(names) if name in case['expected']), None)
            scores.append(0. if rank is None else round(1 / (rank + 1), 6))
            hits += rank is not None and rank < 5
    return scores, {'metric': 'reciprocal_rank', 'hit_at_5': round(hits / len(scores), 4)}


def lesson_retrieval(data, options):
    """Precision@1 of ReasoningBank retrieval on the deterministic lexical path."""
    from jarvis.reasoning_bank import ReasoningBank
    with tempfile.TemporaryDirectory() as folder:
        bank = ReasoningBank(Path(folder), embedder=lambda *args: None)
        ids = {}
        for lesson in data['lessons']:
            identifier = bank._add({'kind': lesson.get('kind', 'strategy'), 'title': lesson['title'],
                                    'description': lesson['description'], 'content': lesson['content'],
                                    'conditions': lesson.get('conditions', {})}, {'task_id': lesson['label']}, 'benchmark')
            ids[identifier] = lesson['label']
            with bank.connect() as db:
                db.execute('UPDATE items SET confidence=?, updated_at=? WHERE id=?',
                           (lesson.get('confidence', .6), lesson.get('updated_at', '2026-10-01T00:00:00+00:00'), identifier))
        scores = []
        for case in data['cases']:
            found = bank.retrieve(case['query'], case.get('conditions'), k=1)['lessons']
            label = ids.get(found[0]['id']) if found else None
            scores.append(1. if label == case['label'] else 0.)
    return scores, {'metric': 'precision_at_1', 'path': 'lexical'}


def salience_retention(data, options):
    """Share of important percepts still held after a burst of low-value sensor events."""
    import jarvis.cognition as cognition
    real = cognition.time
    scores = []
    for case in data['cases']:
        clock = {'now': 1_000_000.}
        cognition.time = SimpleNamespace(time=lambda: clock['now'], perf_counter=real.perf_counter,
                                         monotonic=real.monotonic, sleep=real.sleep)
        try:
            with tempfile.TemporaryDirectory() as folder:
                mind = cognition.Cognition(SimpleNamespace(base=Path(folder)), {})  # threads are not started
                for event in case['events']:
                    clock['now'] += event['dt']
                    mind.perceive(event['source'], event['modality'], event['content'], event['salience'])
                held = {p.content for p in mind.percepts}
                wanted = case['important']
                scores.append(round(sum(item in held for item in wanted) / len(wanted), 6))
        finally:
            cognition.time = real
    return scores, {'metric': 'important_retained'}


def retry_recovery(data, options):
    """Simulated-time read recovery: success within budget, faster is better (0..1)."""
    from jarvis.task_recovery import retry_read
    scores = []
    for case in data['cases']:
        clock = {'ms': 0.}
        def operation():
            clock['ms'] += case['attempt_ms']
            if clock['ms'] < case['recover_after_ms']:
                raise OSError('transient')
            return 'ok'
        def wait(seconds):
            clock['ms'] += seconds * 1000
        try:
            retry_read(operation, read_only=True, attempts=case['attempts'], wait=wait)
            ok = clock['ms'] <= case['budget_ms']
        except OSError:
            ok = False
        scores.append(round(1 - clock['ms'] / case['budget_ms'], 6) if ok else 0.)
    return scores, {'metric': 'success_speed', 'simulated_time': True}


def prompt_routing(data, options):
    from jarvis.prompt_router import route
    return [1. if route(case['goal']) == case['slot'] else 0. for case in data['cases']], {'metric': 'slot_accuracy'}


def prompt_slots(data, options):
    """Local-model accuracy on routed multiple-choice tasks with the candidate's slot prompt."""
    import json
    import urllib.request
    from jarvis.prompt_router import SLOT_PROMPTS, route
    model = data['model']
    scores = []
    for case in data['cases']:
        slot = route(case['question'])
        system = (SLOT_PROMPTS.get(slot, '') if slot else '') or 'Answer with a single letter.'
        prompt = case['question'] + '\n' + '\n'.join(f'{k}) {v}' for k, v in case['choices'].items()) + '\nAnswer:'
        body = json.dumps({'model': model, 'system': system, 'prompt': prompt, 'stream': False, 'think': False,
                           'options': {'temperature': 0, 'seed': 7, 'num_predict': 8}}).encode()
        request = urllib.request.Request('http://127.0.0.1:11434/api/generate', body, {'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=120) as response:
            text = json.loads(response.read())['response'].strip()
        letter = next((ch for ch in text.upper() if ch in case['choices']), '')
        scores.append(1. if letter == case['answer'] else 0.)
    return scores, {'metric': 'choice_accuracy', 'model': model}


BENCHMARKS = {'dag_makespan': dag_makespan, 'tool_selection': tool_selection, 'lesson_retrieval': lesson_retrieval,
              'salience_retention': salience_retention, 'retry_recovery': retry_recovery,
              'prompt_routing': prompt_routing, 'prompt_slots': prompt_slots}
