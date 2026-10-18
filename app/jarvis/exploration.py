"""SEAgent-inspired autonomous exploration curriculum, restricted to verified-isolated environments.

Design reference: SunzeY/SEAgent (commit c8887f15; README states code Apache-2.0,
data CC BY-NC 4.0, research use). No SEAgent code is used: this is an original
curriculum loop -- observe -> propose a small measurable goal -> plan permitted
actions -> execute in the sandbox -> observe the difference -> verify
independently -> record the trajectory -> learn (ReasoningBank lessons, Pillar A
CAPTURED/FIX candidates) -> choose the next goal.

Isolation policy: only environments that are genuinely separated from the user's
session may run. The cyan cursor and Windows virtual desktops are NOT sandboxes, so
desktop GUI exploration stays disabled unless a verified VM backend exists (none
is implemented). Supported environments:
  * IsolatedBrowserEnv: headless Chrome, fresh context (no profile/cookies/downloads),
    every request outside one approved origin aborted.
  * BlenderSandboxEnv: background Blender through ToolRegistry `blender_task` in a
    disposable folder (factory settings, scripts disabled).
Exploration never sends uncertain steps twice: a crash leaves the step marked
uncertain and the next run re-observes a fresh sandbox.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import tempfile
import threading
import uuid

ALLOWED_BROWSER_OPERATIONS = frozenset({'click', 'fill'})
ERROR_TEXT = re.compile(r'\b(?:error|failed|choose|required|invalid|missing|cannot|not allowed)\b', re.I)


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class IsolationUnavailable(ValueError):
    """The environment cannot prove separation from the user's session; nothing ran."""


def desktop_environment(config):
    raise IsolationUnavailable('Desktop GUI exploration is disabled: no verified disposable VM backend is configured. '
                               'The cyan cursor and virtual desktops are not isolation boundaries.')


class IsolatedBrowserEnv:
    name = 'browser'

    def __init__(self, origin, entry_path='/', chrome=None):
        if not re.fullmatch(r'http://127\.0\.0\.1:\d{2,5}', str(origin)):
            raise IsolationUnavailable('Browser exploration is limited to an approved loopback origin.')
        self.origin, self.entry = origin, entry_path
        self.chrome = chrome or next((p for p in (Path('C:/Program Files/Google/Chrome/Application/chrome.exe'),
                                                  Path('C:/Program Files (x86)/Google/Chrome/Application/chrome.exe'))
                                      if p.is_file()), None)
        if self.chrome is None:
            raise IsolationUnavailable('Chrome is not installed for isolated browser exploration.')
        self.driver = self.browser = self.context = self.page = self.session = None
        self.blocked = []

    def reset(self):
        """A brand-new context per episode: no shared cookies, storage, downloads or permissions."""
        from playwright.sync_api import sync_playwright
        from .browser_worker import Session
        self.close()
        self.driver = sync_playwright().start()
        self.browser = self.driver.chromium.launch(headless=True, executable_path=str(self.chrome))
        self.context = self.browser.new_context(accept_downloads=False, service_workers='block', permissions=[])

        def route(request_route):
            if request_route.request.url.startswith(self.origin + '/'):
                request_route.continue_()
            else:
                self.blocked.append(request_route.request.url[:200])
                request_route.abort()
        self.context.route('**/*', route)
        self.page = self.context.new_page()
        self.page.goto(self.origin + self.entry)
        self.session = Session()
        self.session.page, self.session.context, self.session.open = self.page, self.context, (lambda _: None)

    def observe(self):
        report = self.session.inspect()
        controls = []
        for row in report.get('controls', []):
            name = row.get('name') or row.get('label') or ''
            role = row.get('role', '')
            if name:
                controls.append({'name': str(name)[:80], 'role': str(role)[:30],
                                 'fillable': role in {'Edit', 'ComboBox'}})
        status = self.page.evaluate("() => { const s = document.querySelector('[role=status],#status'); return s ? s.textContent.trim() : ''; }")
        return {'url': self.page.url, 'controls': controls, 'status': str(status)[:200]}

    def act(self, step):
        if step['operation'] not in ALLOWED_BROWSER_OPERATIONS:
            raise ValueError('Operation not permitted in exploration.')
        request = {'operation': step['operation'], 'url': self.page.url, 'value': step['target']}
        if step['operation'] == 'fill':
            request['content'] = step['content']
        return self.session.perform(request)

    def verify(self, before, after, goal):
        """Independent check: a fresh DOM read, not the action's own report."""
        status = after['status']
        if goal['kind'] == 'status_success':
            return bool(status) and status != before['status'] and not ERROR_TEXT.search(status), status
        if goal['kind'] == 'reveal':
            new = {c['name'] for c in after['controls']} - {c['name'] for c in before['controls']}
            return bool(new), ', '.join(sorted(new))[:200]
        return False, 'unknown goal kind'

    def close(self):
        for closer in (lambda: self.context and self.context.close(), lambda: self.browser and self.browser.close(),
                       lambda: self.driver and self.driver.stop()):
            try:
                closer()
            except Exception:  # Teardown of a disposable sandbox; nothing to preserve.
                pass
        self.driver = self.browser = self.context = self.page = None


class BlenderSandboxEnv:
    name = 'blender'
    OPERATIONS = ('create', 'export_gltf', 'export_obj', 'export_stl')

    def __init__(self, registry_factory):
        self.registry_factory = registry_factory
        self.folder = None
        self.registry = None

    def reset(self):
        self.close()
        self.folder = Path(tempfile.mkdtemp(prefix='jarvis-explore-blender-'))
        self.registry = self.registry_factory(self.folder)
        self.counter = 0

    def observe(self):
        files = sorted(p.name for p in self.folder.iterdir()) if self.folder else []
        return {'files': files, 'controls': [{'name': op, 'role': 'operation', 'fillable': False} for op in self.OPERATIONS]}

    def act(self, step):
        self.counter += 1
        name = f'probe{self.counter}.blend'
        content = {'operation': 'create', 'objects': [{'type': 'cube', 'name': 'Probe'}]}
        if step['target'].startswith('export_'):
            fmt = step['target'].split('_', 1)[1]
            content['export'] = {'format': fmt, 'path': f'probe{self.counter}.' + step.get('extension', fmt)}
        result = self.registry.execute({'action': 'blender_task', 'value': name, 'folder': 'explore',
                                        'content': json.dumps(content)}, lambda: False)
        return {'call_id': result.call_id, 'evidence': json.loads(result.evidence)}

    def verify(self, before, after, goal):
        new = sorted(set(after['files']) - set(before['files']))
        if goal['kind'] == 'file_created':
            wanted = goal['suffix']
            hits = [n for n in new if n.endswith(wanted)]
            if hits and wanted == '.glb':
                return (self.folder / hits[0]).read_bytes()[:4] == b'glTF', hits[0]
            return bool(hits), ', '.join(new)[:200]
        return False, 'unknown goal kind'

    def close(self):
        if self.folder:
            shutil.rmtree(self.folder, ignore_errors=True)
        self.folder = None


class Curriculum:
    """Picks the next small measurable goal from observations and history (unexplored first)."""

    def __init__(self, state):
        self.state = state

    def next_goal(self, environment, observation, lessons):
        attempts = self.state.setdefault('attempts', {})
        mastered = set(self.state.setdefault('mastered', []))
        if environment.name == 'blender':
            for operation in BlenderSandboxEnv.OPERATIONS[1:]:
                if operation not in mastered:
                    suffix = {'export_gltf': '.glb', 'export_obj': '.obj', 'export_stl': '.stl'}[operation]
                    return {'id': operation, 'kind': 'file_created', 'suffix': suffix, 'target': operation,
                            'description': f'Produce a verified {suffix} export from a disposable scene'}
            return None
        fills = [c for c in observation['controls'] if c['fillable']]
        buttons = [c for c in observation['controls'] if c['role'] in {'Button', 'Hyperlink'}]
        for control in sorted(buttons, key=lambda c: attempts.get(c['name'], 0)):
            if control['name'] in mastered or attempts.get(control['name'], 0) >= 3:
                continue
            return {'id': control['name'], 'kind': 'status_success' if control['name'] not in self.state.get('revealers', [])
                    else 'reveal', 'target': control['name'], 'fills': [f['name'] for f in fills],
                    'description': f'Activate "{control["name"]}" and reach a verified non-error state'}
        return None


def plan_steps(environment, goal, lessons, hint_values):
    """Permitted actions for a goal. Anti-pattern lessons about a control make the plan satisfy inputs first."""
    if environment.name == 'blender':
        step = {'operation': 'run', 'target': goal['target']}
        learned = any('extension' in l['content'].casefold() for l in lessons)
        # Naive first attempt names the file after the format; a learned lesson corrects the extension.
        step['extension'] = goal['suffix'].lstrip('.') if learned or goal['target'] != 'export_gltf' else 'gltf'
        return [step]
    steps = []
    warned = any(l['kind'] == 'anti_pattern' and goal['target'].casefold() in l['content'].casefold() for l in lessons)
    told = any(l['kind'] == 'strategy' and 'fill' in l['content'] and goal['target'].casefold() in l['content'].casefold()
               for l in lessons)
    if warned or told:
        steps += [{'operation': 'fill', 'target': name, 'content': hint_values.get(name, '')}
                  for name in goal.get('fills', []) if hint_values.get(name)]
    steps.append({'operation': 'click', 'target': goal['target']})
    return steps


class Explorer:
    def __init__(self, base, bank=None, skills=None, approved=('fixture-web', 'blender'), max_steps_per_episode=6):
        self.base = Path(base)
        self.root = self.base / '.jarvis-runtime' / 'exploration'
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.root / 'state.json'
        self.bank, self.skills, self.approved = bank, skills, set(approved)
        self.max_steps = max_steps_per_episode
        self.lock = threading.Lock()
        self.state = self._load()

    def _load(self):
        try:
            state = json.loads(self.state_path.read_text(encoding='utf-8'))
            if not isinstance(state, dict):
                raise ValueError
        except (OSError, ValueError):
            state = {}
        for application in state.get('applications', {}).values():
            if application.get('inflight'):
                # Crash recovery: the step's effect is unknown; never replay, observe a fresh sandbox.
                application.setdefault('uncertain', []).append(application.pop('inflight'))
        return state

    def _save(self):
        temporary = self.state_path.with_name('.state.' + uuid.uuid4().hex[:8])
        temporary.write_text(json.dumps(self.state, indent=1, default=str), encoding='utf-8')
        temporary.replace(self.state_path)

    def episode(self, application, environment, cancelled=lambda: False, hint_values=None, conditions=None):
        """One curriculum goal: observe, plan, act, verify, record, learn. Returns the trajectory."""
        if application not in self.approved:
            raise ValueError('Application is not approved for exploration.')
        app_state = self.state.setdefault('applications', {}).setdefault(application, {})
        curriculum = Curriculum(app_state)
        environment.reset()
        try:
            observation = environment.observe()
            query = application + ' ' + ' '.join(c['name'] for c in observation['controls'][:20])
            lessons = self.bank.retrieve(query, {'application': application}, k=3)['lessons'] if self.bank else []
            goal = curriculum.next_goal(environment, observation, lessons)
            if goal is None:
                return {'status': 'curriculum_complete', 'application': application}
            steps, trajectory = plan_steps(environment, goal, lessons, hint_values or {}), []
            task_id = 'explore-' + uuid.uuid4().hex[:24]
            before, verified, evidence = observation, False, ''
            for step in steps[:self.max_steps]:
                if cancelled():
                    trajectory.append({**step, 'action': step['operation'], 'error': 'cancelled before dispatch'})
                    break
                app_state['inflight'] = {'task_id': task_id, 'step': step, 'at': now()}
                self._save()
                row = {'action': 'browser_' + step['operation'] if environment.name == 'browser' else 'blender_task',
                       'target': step['target']}
                try:
                    receipt = environment.act(step)
                    row['call_id'] = receipt.get('call_id') if isinstance(receipt, dict) else None
                except Exception as exc:  # The sandbox step failed; recorded as evidence, not retried.
                    row['error'] = str(exc)[:300]
                app_state.pop('inflight', None)
                trajectory.append(row)
                after = environment.observe()
                if environment.name == 'browser' and after['status'] and ERROR_TEXT.search(after['status']):
                    row.setdefault('error', 'page reported: ' + after['status'][:160])
                before = after
            verified, evidence = environment.verify(observation, before, goal)
            if trajectory and verified:
                trajectory[-1]['verified'] = True
                trajectory[-1]['final'] = True
            status = 'completed' if verified else 'failed'
            attempts = app_state.setdefault('attempts', {})
            attempts[goal['id']] = attempts.get(goal['id'], 0) + 1
            if verified:
                app_state.setdefault('mastered', []).append(goal['id'])
            record = {'task_id': task_id, 'source': 'exploration', 'goal': goal['description'], 'status': status,
                      'verification': [evidence] if verified else [], 'steps': trajectory, 'lessons_used': [l['id'] for l in lessons],
                      'conditions': {'application': application, 'environment': environment.name, **(conditions or {})},
                      'at': now()}
            log = self.root / application / 'trajectories.jsonl'
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open('a', encoding='utf-8') as output:
                output.write(json.dumps(record, default=str) + '\n')
            record['trajectory_ref'] = str(log.relative_to(self.base)) + '#' + task_id
            learned = self.bank.learn(record) if self.bank else None
            if self.bank and lessons:
                self.bank.feedback([l['id'] for l in lessons], verified)
            self._skill_hooks(application, goal, record)
            self._save()
            return {**record, 'learned': learned, 'goal_id': goal['id']}
        finally:
            environment.close()

    def _skill_hooks(self, application, goal, record):
        """Pillar A: verified novel routes become CAPTURED candidates; repeated failures become FIX suggestions."""
        candidates = self.state.setdefault('skill_candidates', [])
        if record['status'] == 'completed' and len(record['steps']) >= 1:
            candidates.append({'kind': 'captured', 'application': application, 'goal': goal['id'],
                               'task_id': record['task_id'], 'steps': [s['action'] for s in record['steps']],
                               'needs': 'SkillEvolution.capture with fixture validation'})
        attempts = self.state['applications'][application]['attempts'].get(goal['id'], 0)
        if record['status'] == 'failed' and attempts >= 2:
            candidates.append({'kind': 'fix_suggestion', 'application': application, 'goal': goal['id'],
                               'task_id': record['task_id'], 'reason': next((s.get('error') for s in record['steps'] if s.get('error')), '')[:200]})
        self.state['skill_candidates'] = candidates[-200:]
