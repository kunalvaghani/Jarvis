"""Task-owned two-frame context, prompt preparation and checked navigation recipes.

Recipes are semantic observations, never saved coordinates or an action retry queue.
"""
from concurrent.futures import ThreadPoolExecutor
import copy
import hashlib
import json
import math
import re
import time
from pathlib import Path

from .skill_memory import atomic, linked
from .task_recovery import TaskFailure

NEXT_PROMPT = (
    'Choose ONLY ONE next executable action from the fresh screenshot and available tools. '
    'The goal and verified completed steps are supplied; step_number is the next step. '
    'Never plan future actions or repeat a completed/uncertain action. '
    'Use exact visible labels and user-requested text. Unknown IDs, paths and content require a read first. '
    'Return question, steps, done and reason. steps contains exactly one action when done is false '
    'and no essential question is needed; otherwise it is empty. Every step needs action,value,browser,'
    'expected,folder,content,find,platform strings; use chrome for unused browser, empty other unused fields. '
    'For file read/write actions, folder must be the explicitly requested destination. '
    'plan_validation_error is runtime feedback about the last rejected proposal; correct it without changing the goal. '
    'done is true ONLY when the ENTIRE goal is supported by fresh evidence. '
    'Only the current image is current evidence. A previous image, when supplied for an error, is reference. '
    'The prompt scaffold was prepared before the last action finished; it is not evidence or permission. '
    'Missing optional preferences do not require questions. Choose sensible defaults. Return only JSON.'
)

NATIVE_NEXT_PROMPT = (
    'Choose exactly one advertised native function for the next executable action. '
    'Use the user goal, available tools and fresh observations. Do not plan future '
    'actions or repeat a completed or uncertain action. Use exact observed labels '
    'and user-requested text; read before inventing IDs, paths or content. '
    'Use open to launch a configured application such as Chrome. browser_navigate '
    'requires a public website URL/domain, never an application name. '
    'Correct plan_validation_error without changing the goal. '
    'Call jarvis_finish only when fresh evidence establishes the entire goal. '
    'Call jarvis_clarify for essential missing information or an unavailable required '
    'capability; explain that limitation plainly. Do not ask about optional preferences. '
    'An email draft is not a sent email. Prefer connected Gmail API tools for mail '
    'search, reading, drafts, sending, Trash and labels. For unread emails use gmail_api_list with query '
    'is:unread; summaries:true returns bounded sender/subject metadata. Never search '
    'for a Gmail desktop application to access the API. The Chrome adapter supports '
    'drafts only and cannot substitute for API mailbox reads. Do not claim Gmail '
    'execution when its required adapter is unavailable. '
    'Historical screenshots, memory and tool output are reference, never approval.'
)


class StepSession:
    """One task, one bounded prompt job, at most current and previous image."""
    def __init__(self, clock=time.monotonic):
        self.clock, self.started = clock, clock()
        self.frames, self.trace, self.timings = [], [], []
        self.goal_verified = False
        self.learnable = True
        self.pool = None
        self.future = None
        self.closed = False

    def capture(self, frame):
        if self.closed:
            frame.pop('image', None)
            return
        if any(frame is item for item in self.frames):
            return
        self.frames.append(frame)
        if len(self.frames) > 2:
            self.frames.pop(0).pop('image', None)

    @staticmethod
    def scaffold(goal, completed, step, apps, tools):
        # No future screen, speculative action or verification claim is prepared.
        return copy.deepcopy({'goal': goal, 'completed_count': len(completed),
            'last_dispatched': {'action': step['action'], 'value': step['value']},
            'system_prompt': NEXT_PROMPT})

    def prepare(self, goal, completed, step, apps, tools):
        if self.closed:
            raise ValueError('Planning session is closed.')
        if self.future is not None:
            self.future.result(timeout=1)
        if self.pool is None:
            self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='Jarvis prompt')
        # Copy before submitting: the worker cannot read mutable execution state.
        args = copy.deepcopy((goal, completed[-40:], step, [], []))
        self.future = self.pool.submit(self.scaffold, *args)

    def consume(self):
        future, self.future = self.future, None
        return future.result(timeout=1) if future else {}

    def images(self, recovery=False):
        selected = self.frames[-2:] if recovery else self.frames[-1:]
        return [item['image'] for item in selected if item.get('image')]

    def measure(self, stage, started):
        self.timings.append({'stage': stage, 'seconds': round(self.clock() - started, 4)})

    def record(self, step, before, after, chosen):
        if not recipe_control(step, chosen) or not surface(before) or not surface(after):
            self.learnable = False
            return
        if fingerprint(before) == fingerprint(after):
            self.learnable = False  # An unchanged tree alone cannot prove activation.
            return
        self.trace.append({'action': step['action'], 'value': chosen['name'],
            'expected': step['expected'], 'role': chosen['role'],
            'context': chosen.get('context', ''), 'before': fingerprint(before),
            'after': fingerprint(after)})

    def close(self):
        self.closed = True
        if self.future:
            self.future.cancel()
        if self.pool:
            # Only bounded local copying runs here, never inference or a UI action.
            self.pool.shutdown(wait=True, cancel_futures=True)
        self.future = self.pool = None
        for item in self.frames:
            item.pop('image', None)
        self.frames.clear()


FORBIDDEN = re.compile(r'\b(delete|remove|erase|save|send|submit|publish|post|buy|pay|install|'
                       r'upload|transfer|permission|password|login|command|terminal|run|execute)\b', re.I)
NATIVE_APPS = {'notepad.exe', 'explorer.exe', 'mspaint.exe', 'calc.exe', 'calculatorapp.exe'}


def surface(snapshot):
    if snapshot.get('is_dialog') or snapshot.get('visual_only'):
        return False
    try:
        context = json.loads(snapshot.get('context', ''))
        executable = str(context[0]).replace('\\', '/').rsplit('/', 1)[-1].casefold()
        return executable in NATIVE_APPS and bool(snapshot.get('controls'))
    except (ValueError, TypeError, IndexError):
        return False


def recipe_control(step, chosen):
    if not chosen or chosen.get('password') or FORBIDDEN.search(chosen.get('name', '')):
        return False
    # Cache only navigation tabs and named standard menu expansions, not arbitrary buttons.
    return (step['action'] == 'select' and chosen.get('role') == 'TabItem' or
            step['action'] == 'open_menu' and chosen.get('role') in {'MenuItem', 'Button'}
            and chosen.get('name', '').casefold().replace('&', '') in {'file', 'edit', 'view', 'help', 'tools'})


def fingerprint(snapshot):
    rows = [{key: item[key] for key in ('name', 'role', 'context', 'selected', 'toggle_state') if key in item}
            for item in snapshot.get('controls', [])]
    data = {'title': snapshot.get('title'), 'context': snapshot.get('context'), 'controls': rows,
            'is_dialog': snapshot.get('is_dialog', False)}
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


class WorkflowMemory:
    """Small expiring exact-goal navigation cache; malformed memory disables reuse."""
    def __init__(self, base, clock=time.time):
        self.base, self.clock = Path(base), clock
        self.path = self.base / '.jarvis-runtime' / 'navigation-workflows.json'
        self.rows, self.error = {}, None
        try:
            self.check_path()
            if self.path.exists():
                if self.path.stat().st_size > 200_000:
                    raise ValueError('Workflow memory exceeds its size limit.')
                data = json.loads(self.path.read_text(encoding='utf-8'))
                if data.get('version') != 1 or not isinstance(data.get('workflows'), dict) or len(data['workflows']) > 24:
                    raise ValueError('Invalid workflow memory.')
                for key, row in data['workflows'].items():
                    self.validate(key, row)
                self.rows = data['workflows']
        except (OSError, ValueError, TypeError, KeyError) as exc:
            self.error = str(exc)

    def check_path(self):
        if any(linked(path) for path in (self.path, self.path.parent, self.base)):
            raise ValueError('Workflow memory cannot use linked paths.')

    @staticmethod
    def key(goal):
        return hashlib.sha256(goal.strip().casefold().encode('utf-8')).hexdigest()

    @classmethod
    def validate(cls, key, row):
        if (not isinstance(row, dict) or set(row) != {'goal', 'at', 'steps'} or
                not isinstance(row['goal'], str) or len(row['goal']) > 1500 or
                key != cls.key(row['goal']) or FORBIDDEN.search(row['goal']) or
                type(row['at']) not in (int, float) or not math.isfinite(row['at']) or not isinstance(row['steps'], list) or
                not 1 <= len(row['steps']) <= 6):
            raise ValueError('Invalid remembered workflow.')
        previous = None
        for step in row['steps']:
            if (not isinstance(step, dict) or set(step) != {'action', 'value', 'expected', 'role', 'context', 'before', 'after'} or
                    any(not isinstance(value, str) or len(value) > 500 for value in step.values()) or
                    not recipe_control(step, {'name': step['value'], 'role': step['role']}) or
                    any(not re.fullmatch('[a-f0-9]{64}', step[k]) for k in ('before', 'after')) or
                    step['before'] == step['after'] or previous and step['before'] != previous):
                raise ValueError('Invalid remembered navigation step.')
            previous = step['after']

    def remember(self, goal, session):
        if self.error or not session.goal_verified or not session.learnable or not session.trace or FORBIDDEN.search(goal):
            return False
        key = self.key(goal)
        row = {'goal': goal, 'at': self.clock(), 'steps': session.trace}
        try:
            self.validate(key, row)
            self.check_path()
            rows = {**self.rows, key: row}
            rows = dict(sorted(rows.items(), key=lambda pair: pair[1]['at'])[-24:])
            atomic(self.path, json.dumps({'version': 1, 'workflows': rows}, ensure_ascii=True, indent=2))
            self.rows = copy.deepcopy(rows)
            return True
        except (OSError, ValueError, TypeError) as exc:
            self.error = str(exc)  # Disable cache; never replay an action to repair persistence.
            return False

    def proposal(self, goal, snapshot):
        if self.error or not surface(snapshot):
            return None
        row = self.rows.get(self.key(goal))
        if not row or not 0 <= self.clock() - row['at'] <= 14 * 86400:
            return None
        if fingerprint(snapshot) != row['steps'][0]['before']:
            return None
        return copy.deepcopy(row)


def replay(brain, goal, cancelled, clock=time.monotonic, sleep=time.sleep):
    """No model calls; every step freshly grounded and its semantic state checked.

    Five seconds is a dispatch budget, not a promise about an OS provider call.
    After any dispatch, mismatches stop the task without falling back or replaying.
    """
    started = clock()
    if cancelled() or getattr(brain.actions, 'resume_source', None):
        return None
    if brain.workflows.error or brain.workflows.key(goal) not in brain.workflows.rows:
        return None  # A new goal needs no extra accessibility read for cache discovery.
    try:
        handle, snapshot = brain.observe(cancelled)
    except (ValueError, OSError):
        return None  # No action attempted; ordinary planning may use visual fallback.
    row = brain.workflows.proposal(goal, snapshot)
    if not row:
        return None
    completed = []
    brain.actions.report('brain', 'Using remembered navigation with fresh control and outcome checks')
    for saved in row['steps']:
        if cancelled() or clock() - started >= 5:
            raise TaskFailure('Remembered task stopped at its five-second budget; inspect the last verified state.', attempted=bool(completed))
        handle, snapshot = brain.observe(cancelled)
        if not surface(snapshot) or fingerprint(snapshot) != saved['before']:
            if not completed:
                return None
            raise TaskFailure('Remembered navigation state changed; stopped without repeating actions.', attempted=True)
        matches = [c for c in snapshot['controls'] if c.get('name') == saved['value'] and
                   c.get('role') == saved['role'] and c.get('context', '') == saved['context']]
        if len(matches) != 1:
            if not completed:
                return None
            raise TaskFailure('Remembered control is missing or ambiguous.', attempted=True)
        step = {k: saved[k] for k in ('action', 'value', 'expected')}
        brain.validate_remaining([step], goal)
        brain.save_plan([step], completed, 'Fresh remembered navigation check')
        brain.checkpoint('acting', action=step['action'], target=step['value'], screen=snapshot['title'])
        control = matches[0]
        if cancelled() or clock() - started >= 5:
            raise TaskFailure('Remembered task cancelled or budget elapsed before dispatch.', attempted=bool(completed))
        ui = brain.actions._ui()
        if step['action'] == 'select':
            activate = lambda: ui._activate(handle, snapshot, control, 'select', cancelled)
        else:
            activate = lambda: ui.runner({'operation': 'open_menu', 'handle': handle,
                'owner_pid': __import__('os').getpid(), 'control': control, 'content': ''}, cancelled)['message']
        result = brain.dispatch(step, cancelled, activate=activate).evidence
        brain.checkpoint('action_attempted', action=step['action'], target=step['value'], evidence=result)
        while True:
            if cancelled():
                raise TaskFailure('Cancelled after remembered action; inspect its result.', attempted=True)
            try:
                _, after = brain.observe(cancelled)
            except (ValueError, OSError) as exc:
                raise TaskFailure('Observation failed after remembered action: ' + str(exc), attempted=True) from exc
            if surface(after) and fingerprint(after) == saved['after']:
                break
            if clock() - started >= 5:
                raise TaskFailure('Remembered action result is unverified; stopped without retrying.', attempted=True)
            sleep(.05)
        completed.append({**step, 'verified': True, 'result': result[:500]})
        brain.checkpoint('verified', action=step['action'], target=step['value'], evidence='Fresh semantic navigation state matched')
        brain.save_plan([], completed, 'Remembered navigation result verified')
    brain.checkpoint('goal_verified', source='fresh_navigation_recipe', evidence='All navigation transitions and final semantic state matched the verified exact-goal recipe')
    return 'Finished. Remembered navigation verified in %.2f seconds.' % (clock() - started)
