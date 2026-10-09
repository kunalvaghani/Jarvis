"""Exact desktop requests bypass inference; unknown intents return to the planner."""
import os
import re
import time
from .desktop_actions import explicit_desktop_plan, validate_desktop_step


def compile_steps(goal):
    # Quoted text is literal, including words such as "then" or action verbs.
    literal = re.fullmatch(r'fill (?:the )?(.+?)(?: text)? field with ("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')', goal.strip(), re.I | re.S)
    if literal:
        import ast
        step = {'action': 'fill_text', 'value': literal[1], 'content': ast.literal_eval(literal[2]),
                'expected': 'Requested literal text is present in the field'}
        validate_desktop_step(step)
        return [step]
    # Delimiters require another action verb. Plain 'rock and roll' stays text.
    pieces = re.split(r'\s+(?:and then|then)\s+|\s+and\s+(?=(?:fill|scroll|press|use shortcut|open|click|select|choose|install|delete|remove|run|execute)\b)',
                      goal.strip(), flags=re.I)
    if len(pieces) > 12:
        return None
    steps = []
    for piece in pieces:
        plan = explicit_desktop_plan(piece)
        if not plan:
            return None  # Compile the entire request before doing anything.
        for step in plan['steps']:
            if step['action'] == 'select':
                step['verb'] = 'click' if piece.casefold().startswith('click ') else 'select'
        steps.extend(plan['steps'])
    for step in steps:
        validate_desktop_step(step)
    return steps


def run(actions, goal, cancelled, clock=time.monotonic):
    if getattr(actions, 'resume_source', None):
        return None  # Checkpoint-aware resume remains owned by the established planner.
    result = run_files(actions, goal, cancelled)
    if result is not None:
        return result
    steps = compile_steps(goal)
    if steps is None:
        return None
    from .targeting import scoped_matches
    from .ui_controls import UNSAFE_INFERRED
    from .tools import ToolRegistry
    ui, registry, completed = actions._ui(), ToolRegistry(actions), []
    state = actions.task_state
    state.update_plan(steps, [], 'Explicit desktop grammar; no model calls')
    actions.report('brain', 'Running explicit desktop actions directly')
    started = clock()
    for step in steps:
        if cancelled():
            raise ValueError('Task cancelled before input.')
        handle = ui._handle()
        snapshot = ui.runner({'operation': 'list', 'handle': handle, 'owner_pid': os.getpid()}, cancelled)
        operation = 'activate' if step['action'] in {'select', 'handle_dialog'} else step['action']
        request = {'operation': operation, 'handle': handle, 'owner_pid': os.getpid(),
                   'signature': snapshot['signature'], 'value': step['value'], 'verb': step.get('verb', 'select')}
        if step['action'] in {'select', 'fill_text', 'open_menu', 'handle_dialog'}:
            controls = snapshot['controls']
            if step['action'] == 'fill_text':
                controls = [c for c in controls if c['role'] == 'Edit' and not c.get('password')]
            elif step['action'] == 'open_menu':
                controls = [c for c in controls if c['role'] in {'MenuItem', 'Button', 'SplitButton', 'ComboBox'}]
            elif step['action'] == 'handle_dialog':
                if not snapshot.get('is_dialog'):
                    return 'Task paused: no accessible dialog is active. No dialog button was pressed.'
                controls = [c for c in controls if c['role'] == 'Button']
            else:
                controls = [c for c in controls if c['role'] not in {'Edit', 'Pane', 'Document'}]
            matching = scoped_matches(controls, step['value'])
            if len(matching) != 1:
                return 'Task paused: name one unique visible control or use the island choices. No input issued for this step.'
            chosen = matching[0]
            if (UNSAFE_INFERRED.search(chosen['name']) or chosen.get('password')
                    or re.search(r'\b(delete|remove|erase|recycle)\b', snapshot.get('title', ''), re.I)):
                return 'Task paused: this control needs the existing explicit command or approval flow.'
            request['control'] = chosen
            if operation == 'fill_text':
                request['content'] = step['content']
        state.checkpoint('acting', action=step['action'], target=step['value'])
        receipt = {}
        def activate():
            receipt.update(ui.runner(request, cancelled))
            return receipt['message']
        result = registry.execute(step, cancelled, activate=activate).evidence
        state.checkpoint('action_attempted', action=step['action'], target=step['value'], evidence=result)
        if cancelled():
            raise ValueError('Task cancelled after input; inspect the current result before retrying.')
        # Native field/selection/expand/scroll postconditions are independently read.
        # Mere state change after Invoke/shortcut does not prove a multi-step goal.
        if receipt.get('verified') is not True:
            return 'Task paused: ' + result + '. Inspect the result; no action was replayed.'
        completed.append({**step, 'verified': True, 'provider': receipt.get('provider'), 'result': result})
        state.checkpoint('verified', action=step['action'], target=step['value'],
                         source='fresh_native_state', evidence=receipt.get('evidence', ''))
        state.update_plan(steps[len(completed):], completed, 'Native result observed; next explicit step')
    state.checkpoint('goal_verified', source='explicit_desktop_native_postconditions',
                     evidence='All explicit inputs and observable postconditions confirmed')
    return 'Finished ' + str(len(completed)) + ' explicit desktop action(s) in ' + f'{clock() - started:.2f}' + ' seconds; no model calls.'


def run_files(actions, goal, cancelled):
    """Reuse approved/scoped file/command tools with exact independent readback."""
    from .brain import explicit_file_plan, explicit_command_plan
    from .tools import ToolRegistry
    from .commands import filename
    from pathlib import Path
    plan = explicit_file_plan(goal) or explicit_command_plan(goal)
    if not plan or any(step['action'] == 'open' for step in plan['steps']):
        return None
    state, completed, registry = actions.task_state, [], ToolRegistry(actions)
    state.update_plan(plan['steps'], [], 'Explicit file/command grammar; no model calls')
    for step in plan['steps']:
        if cancelled():
            raise ValueError('Task cancelled before input.')
        action, expected, path = step['action'], None, None
        if action in {'create_file', 'modify_file', 'delete_file'}:
            folder = Path(actions._task_folder(step['folder'], cancelled)).resolve(strict=True)
            path = folder / filename(step['value'])
            if path.is_symlink() or path.resolve().parent != folder:
                raise ValueError('The named file must remain inside its selected folder.')
            if action == 'create_file':
                expected = step['content']
            elif action == 'modify_file':
                if path.stat().st_size > 2_000_000:
                    raise ValueError('The text file is too large.')
                with path.open('r', encoding='utf-8', newline='') as stream:
                    original = stream.read()
                find = step.get('find', '')
                if find and original.count(find) != 1:
                    raise ValueError('The exact replacement text must occur once; no write issued.')
                expected = original.replace(find, step['content'], 1) if find else step['content']
            # Bind the tool to the resolved folder instead of resolving a name twice.
            step = {**step, 'folder': str(folder)}
        state.checkpoint('acting', action=action, target=step['value'])
        result = registry.execute(step, cancelled).evidence
        state.checkpoint('action_attempted', action=action, target=step['value'], evidence=result)
        verified = False
        if (path is not None and expected is not None and path.is_file() and not path.is_symlink()
                and path.stat().st_size <= 2_000_000):
            with path.open('r', encoding='utf-8', newline='') as stream:
                verified = stream.read().replace('\r\n', '\n') == expected.replace('\r\n', '\n')
        elif action == 'delete_file':
            verified = actions.last_deleted == path and not path.exists()
        elif action == 'run_command':
            verified = bool(actions.last_command and actions.last_command[1] == 0)
        if cancelled() or not verified:
            return 'Task paused: the requested result was not verified. Inspect the file or command output; no replay.'
        completed.append({**step, 'verified': True, 'result': result})
        state.checkpoint('verified', action=action, target=step['value'], source='disk_readback_or_exit_status', evidence=result)
        state.update_plan(plan['steps'][len(completed):], completed, 'Exact local result verified')
    state.checkpoint('goal_verified', source='disk_readback_or_exit_status', evidence='Explicit local tool result independently verified')
    return 'Finished; exact file result or command exit status verified without model calls.'
