"""Deterministic local hierarchy; proposals never grant execution authority.

Only aggregate verified outcomes are stored here. Task payloads stay in the
existing private task/skill stores and are never implicitly training examples.
"""
import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path

SMALL = {'qwen3.5:2b', 'qwen3.5:4b'}
DEFAULTS = {'enabled': True, 'execution_model': 'qwen3.5:4b', 'reasoning_model': 'qwen3.5:9b'}
HARD = re.compile(r'\b(debug|refactor|implement|design|architecture|research|compare|autonomous|unreal|blender|code|script|unknown|unfamiliar|delete|send|publish|install|password|secret|type|write|compose|draft|report|fill|form)\b', re.I)
ROUTINE = re.compile(r'^(?:please )?(?:open|show|launch|find|locate|search|play|pause|resume|skip|mute|unmute|set volume|list|read|create|append)\b', re.I)


def settings(options):
    value = options.get('model_hierarchy', {})
    if not isinstance(value, dict) or set(value) - set(DEFAULTS):
        raise ValueError('Invalid model_hierarchy settings.')
    policy = {**DEFAULTS, **value}
    if type(policy['enabled']) is not bool or policy['execution_model'] not in SMALL or policy['reasoning_model'] != 'qwen3.5:9b':
        raise ValueError('Use a Qwen3.5 2B/4B executor and the Qwen3.5 9B reasoning model.')
    return policy


def category(goal):
    text = str(goal).casefold()
    if any(word in text for word in ('youtube', 'spotify', 'music', 'volume', 'playback')):
        return 'media'
    if any(word in text for word in ('file', 'folder', '.txt', 'downloads', 'documents')):
        return 'files'
    return 'desktop'


class Outcomes:
    """Laplace-smoothed history; failures override cold-start routine admission."""
    def __init__(self, path):
        self.path = Path(path)

    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=.25)
        db.execute('CREATE TABLE IF NOT EXISTS outcomes(category TEXT, model TEXT, success INTEGER, failure INTEGER, PRIMARY KEY(category,model))')
        db.execute('CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY)')
        return db

    def unreliable(self, group, model):
        if not self.path.exists():
            return False
        with closing(self.connect()) as db:
            row = db.execute('SELECT success,failure FROM outcomes WHERE category=? AND model=?', (group, model)).fetchone()
        return bool(row and row[1] >= 2 and (row[0]+1)/(sum(row)+2) < .8)

    def record(self, task):
        identity = task.get('task_id')
        traces = []
        checks = task.get('checkpoints', []) if not task.get('model_routes') else [
            {'stage': 'model_route', 'evidence': json.dumps(row)} for row in task['model_routes']]
        for checkpoint in checks:
            if checkpoint.get('stage') == 'model_route':
                try:
                    trace = json.loads(checkpoint.get('evidence', ''))
                except (ValueError, TypeError):
                    continue
                if trace.get('category') in {'media', 'files', 'desktop'} and trace.get('model') in SMALL | {'qwen3.5:9b'}:
                    if trace.get('previous_model') in SMALL:
                        traces.append({**trace, 'model': trace['previous_model']})
                    traces.append(trace)
        if not isinstance(identity, str) or not traces or task.get('status') not in {'completed', 'failed', 'paused'}:
            return
        # A planner's claimed completion is not independent verification. Require
        # a goal proof plus a separately checked execution/readback checkpoint.
        checks = task.get('checkpoints', [])
        proof = any(c.get('stage') == 'goal_verified' and c.get('evidence') for c in checks)
        readback = any(c.get('stage') in {'verified', 'observed_file', 'external_write_verified'} and c.get('evidence') for c in checks)
        success = task.get('status') == 'completed' and proof and readback and not task.get('failures')
        rejected = {t.get('previous_model') for t in traces if t.get('reason') == 'executor_rejected'} & SMALL
        if task.get('status') == 'completed' and not success and not rejected:
            return  # Unknown quality must not be counted as failure or success.
        with closing(self.connect()) as db, db:
            if not db.execute('INSERT OR IGNORE INTO tasks VALUES (?)', (identity,)).rowcount:
                return
            for group, model in {(t['category'], t['model']) for t in traces}:
                if task.get('status') == 'completed' and not success and model not in rejected:
                    continue
                # A teacher recovery does not turn the student's earlier failure
                # into a success. Only the final contributing route earns credit.
                correct = success and model == traces[-1]['model'] and model not in rejected
                db.execute('INSERT INTO outcomes VALUES (?,?,?,?) ON CONFLICT(category,model) DO UPDATE SET success=success+excluded.success,failure=failure+excluded.failure',
                           (group, model, int(correct), int(not correct)))


def route(operation, data, options, names, outcomes=None):
    policy = settings(options)
    group = category(data.get('goal', ''))
    result = {'category': group, 'reason': 'configured', 'model': None}
    if not policy['enabled'] or operation not in {'plan', 'replan', 'next_step'}:
        return result
    goal = str(data.get('goal', '')).strip()
    last = data.get('last_result')
    recovered = isinstance(last, dict) and last.get('verified') is True and last.get('confirmed') is True
    failure = any(data.get(k) for k in ('plan_validation_error', 'validation_error'))
    failure = failure or (bool(data.get('failures')) and not recovered)
    failure = failure or (isinstance(last, dict) and (last.get('verified') is False or last.get('confirmed') is False))
    hard = failure or data.get('images') or HARD.search(goal) or len(goal) > 180 or not ROUTINE.match(goal)
    model = policy['reasoning_model'] if hard else policy['execution_model']
    reason = 'recovery_or_complexity' if hard else 'routine'
    if model in SMALL and outcomes and outcomes.unreliable(group, model):
        model, reason = policy['reasoning_model'], 'verified_history'
    if model not in names:
        model, reason = policy['reasoning_model'], 'executor_unavailable'
    if model not in names:
        return {**result, 'reason': 'configured_fallback'}
    return {'category': group, 'model': model, 'reason': reason}
