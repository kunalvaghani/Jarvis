"""Ten planning-to-real-file-execution workflows, with independent disk oracles.

--live uses the configured Qwen planner for each full plan. Verification/decision
oracles are deterministic and scoped to authored fixture files; no desktop/model
decision accuracy or real-microphone claim is made.
"""
from jarvis.paths import APP_ROOT, artifact_path
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from jarvis.actions import Actions
from jarvis.brain import BrainClient, validate_plan, normalize_plan, FILE_SCOPE_ACTIONS
from jarvis.commands import Command
from jarvis.task_recovery import action_key, TaskFailure
from jarvis.task_state import TaskState

BASE = Path(__file__).resolve().parents[2]
LENGTHS = (2, 3, 4, 5, 6, 8, 10, 12, 15, 20)
TOPICS = ('notes', 'todo', 'inventory', 'journal', 'schedule', 'budget', 'release', 'travel', 'project', 'audit')


def scenario(number, length):
    topic = TOPICS[number]
    steps, expected = [], {}
    for index in range(length-1):
        filename = topic + str(index // 3 + 1) + '.txt'
        phase = ('pending', 'reviewed', 'complete')[index % 3]
        if index % 3 == 0:
            step = {'action': 'create_file', 'value': filename, 'content': phase, 'find': '',
                    'expected': filename + ' contains ' + phase}
        else:
            step = {'action': 'modify_file', 'value': filename, 'find': expected[filename], 'content': phase,
                    'expected': filename + ' contains ' + phase}
        steps.append({'browser': 'chrome', 'folder': 'this folder', 'platform': '', **step})
        expected[filename] = phase
    steps.append({'action': 'read_file', 'value': filename, 'expected': 'Read final ' + phase,
                  'browser': 'chrome', 'folder': 'this folder', 'content': '', 'find': '', 'platform': ''})
    lines = []
    for index, step in enumerate(steps, 1):
        if step['action'] == 'create_file':
            instruction = f"Create {step['value']} containing {step['content']}"
        elif step['action'] == 'modify_file':
            instruction = f"Modify {step['value']}: replace {step['find']} with {step['content']}"
        else:
            instruction = f"Read {step['value']}"
        lines.append(f'{index}. {instruction}')
    goal = 'Prepare the ' + topic + ' workflow in this folder in this exact order, then finish:\n' + '\n'.join(lines)
    return {'name': topic, 'length': length, 'goal': goal, 'steps': steps, 'expected': expected}


class FixtureClient:
    def __init__(self, actions, case, planner=None, incremental=False):
        self.actions, self.case, self.planner = actions, case, planner
        self.incremental = incremental
        self.calls, self.plans, self.index = [], [], 0

    def close(self):
        pass  # Shared live planner is closed once by the fixture coordinator.

    def request(self, operation, cancelled, **data):
        self.calls.append(operation)
        if operation in {'plan', 'next_step', 'replan'}:
            if operation == 'next_step':
                completed = data['completed']
                if len(completed) == len(self.case['steps']):
                    return {'done': True, 'question': '', 'steps': [], 'reason': 'Independent disk oracle satisfied'}
                self.index = len(completed)
                return {'done': False, 'question': '', 'steps': [self.case['steps'][self.index]]}
            if self.planner:
                result = self.planner.request(operation, cancelled, **data)
            else:
                result = {'question': '', 'steps': self.case['steps']}
            self.plans.append(result)
            if any(step.get('action') in FILE_SCOPE_ACTIONS
                   and not step.get('folder') for step in result.get('steps', []) if isinstance(step, dict)):
                return result  # Production's bounded read-only correction/validator handles this; no dispatch.
            # Reject omissions before execution instead of silently inserting
            # missing steps into model output and calling that a model success.
            proposed = normalize_plan(validate_plan(result, max_steps=20), self.case['goal'])
            if [action_key(step) for step in proposed] != [action_key(step) for step in self.case['steps']]:
                raise ValueError('Planner did not preserve all requested operations, targets, text and order.')
            return result
        if operation == 'decide':
            self.actions.brain.validate_remaining([data['step']], self.case['goal'])
            return {'approved': True, 'choice': '', 'reason': 'Explicit authored file operation; deterministic scope check'}
        if operation == 'verify':
            step = data['step']
            if step['action'] == 'goal':
                okay = all((self.actions.fixture_root / name).read_text(encoding='utf-8') == content
                           for name, content in self.case['expected'].items())
                completed = self.actions.task_state.snapshot()['plan']['completed']
                okay &= len(completed) == self.case['length']
            else:
                text = (self.actions.fixture_root / step['value']).read_text(encoding='utf-8')
                evidence = data['screen'].get('trusted_evidence', [])
                okay = bool(evidence) and text in evidence[0]
            return {'verified': bool(okay), 'reason': 'Independent authored filesystem/content/action-count oracle'}
        raise AssertionError('Unexpected model operation: ' + operation)


def fixture(base, case, planner=None, incremental=False, *, fault_after=None, cancel_after=None, extra_at_limit=False):
    root = base / case['name']
    root.mkdir(parents=True)
    options = {'enabled': True, 'planner': 'qwen3.5:9b', 'decision': 'deterministic-fixture-oracle',
               'screen_aware': False, 'adaptive_planning': incremental, 'incremental_planning': incremental,
               'max_task_actions': 20, 'task_recovery': True}
    actions = Actions({'files_root': 'managed', 'apps': {}, '_ui_verification': True,
                       'memory': {'enabled': False}, 'brain': options}, root, lambda *_: None)
    actions.task_state = TaskState(root)
    actions.fixture_root = root
    actions.allowed_tools = {'create_file', 'modify_file', 'read_file'}
    def folder(name, cancelled):
        if name != 'this folder':
            raise ValueError('Fixture permits only this folder')
        return root
    actions._task_folder = folder
    def observe(cancelled):
        files = [(p.name, p.read_text(encoding='utf-8')) for p in root.glob('*.txt')]
        return None, {'title': 'Authored file workspace', 'context': str(root), 'controls': [],
                      'signature': hashlib.sha256(json.dumps(files).encode()).hexdigest()}
    actions.brain.observe = observe
    client = FixtureClient(actions, case, planner, incremental)
    actions.brain.client = client
    dispatched = []
    dispatch = actions.brain.dispatch
    def tracked_dispatch(step, cancelled, **kwargs):
        dispatched.append(step)
        result = dispatch(step, cancelled, **kwargs)
        if len(dispatched) == fault_after:
            raise TaskFailure('Injected failure after the real file effect', attempted=True)
        return result
    actions.brain.dispatch = tracked_dispatch
    request = client.request
    def checked_request(operation, cancelled, **data):
        if extra_at_limit and operation == 'next_step' and len(data.get('completed', [])) == 20:
            return {'done': False, 'question': '', 'steps': [case['steps'][0]]}
        return request(operation, cancelled, **data)
    client.request = checked_request
    def cancelled():
        return cancel_after is not None and len((actions.task_state.snapshot() or {}).get('plan', {}).get('completed', [])) >= cancel_after
    started = time.monotonic()
    try:
        reply = actions.execute(Command('task', case['goal']), cancelled)
        state = actions.task_state.snapshot()
        completed = state.get('plan', {}).get('completed', [])
        correct = all((root / name).is_file() and (root / name).read_text(encoding='utf-8') == content for name, content in case['expected'].items())
        actual = [action_key(row) for row in completed]
        wanted = [action_key(row) for row in case['steps']]
        passed = correct and actual == wanted and state['status'] == 'completed'
        return {'name': case['name'], 'plan_lines': case['length'], 'passed': passed, 'seconds': round(time.monotonic()-started, 3),
                'goal': case['goal'], 'planner_calls': client.calls.count('plan') + client.calls.count('next_step') + client.calls.count('replan'),
                'completed_actions': len(completed), 'exact_order_and_arguments': actual == wanted, 'disk_content_verified': correct,
                'state_status': state['status'], 'reply': reply, 'generated_plans': client.plans,
                'final_files': case['expected'], 'dispatched_actions': len(dispatched)}
    except Exception as exc:
        state = actions.task_state.snapshot() or {}
        return {'name': case['name'], 'plan_lines': case['length'], 'passed': False, 'seconds': round(time.monotonic()-started, 3),
                'error_type': type(exc).__name__, 'error': str(exc)[:800], 'goal': case['goal'], 'generated_plans': client.plans,
                'completed_actions': len(state.get('plan', {}).get('completed', [])), 'dispatched_actions': len(dispatched),
                'remaining_actions': len(state.get('plan', {}).get('remaining', [])), 'state_status': state.get('status'),
                'failures': state.get('failures', []), 'resume_blocker': TaskState.resume_blocker(state)}
    finally:
        actions.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--resume', action='store_true', help='Retain recorded successes; rerun failures and missing cases')
    args = parser.parse_args()
    name = 'plan-execution-live-check.json' if args.live else 'plan-execution-fixture-check.json'
    record_path = artifact_path(BASE, name)
    previous = json.loads(record_path.read_text(encoding='utf-8')) if record_path.exists() else None
    if record_path.exists():
        history_path = record_path.with_name(record_path.stem + '-history.json')
        history = json.loads(history_path.read_text(encoding='utf-8')) if history_path.exists() else []
        history.append(json.loads(record_path.read_text(encoding='utf-8')))
        history_path.write_text(json.dumps(history, indent=2) + '\n', encoding='utf-8')
    root = BASE / '.jarvis-runtime/plan-execution-fixture' / str(time.time_ns())
    root.mkdir(parents=True)
    planner = None
    if args.live:
        options = json.loads((BASE / 'config/config.json').read_text(encoding='utf-8'))['brain']
        # Exercise the existing full-plan proposal path. Production incremental
        # continuation is tested separately with controlled proposal fixtures.
        planner = BrainClient(BASE, {**options, 'incremental_planning': False, 'native_tool_calling': False,
                                     'harness': {'enabled': False}, 'hermes': {'enabled': False}, 'max_task_actions': 20})
    result = {'date': datetime.now(timezone.utc).isoformat(), 'live_planner': args.live,
              'scope': 'Ten authored real file workflows through Brain/ToolRegistry/Actions; fresh disk observations and independent deterministic decision/verification oracles. No microphone, native desktop, or end-to-end model decision claim.',
              'cases': []}
    try:
        for index, length in enumerate(LENGTHS):
            retained = next((case for case in (previous or {}).get('cases', [])
                             if case.get('passed') and case.get('name') == TOPICS[index]
                             and case.get('plan_lines') == length and case.get('goal') == scenario(index, length)['goal']), None) if args.resume else None
            if retained:
                result['cases'].append({**retained, 'retained_from_check': previous['date']})
                print(json.dumps({'name': retained['name'], 'plan_lines': length, 'passed': True, 'retained': True}), flush=True)
                continue
            row = fixture(root, scenario(index, length), planner)
            result['cases'].append(row)
            print(json.dumps({key: row.get(key) for key in ('name', 'plan_lines', 'passed', 'seconds', 'completed_actions', 'error')}, ensure_ascii=True), flush=True)
            result['passed'] = len(result['cases']) == 10 and all(case['passed'] for case in result['cases'])
            record_path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        result['passed'] = len(result['cases']) == 10 and all(case['passed'] for case in result['cases'])
        record_path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    finally:
        if planner:
            planner.close()
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
