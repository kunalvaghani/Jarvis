"""UI-TARS parsing plus bounded local vision; Jarvis owns input and independent outcomes."""
import ast
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from .names import common
from .task_recovery import TaskFailure
from .task_state import TaskState
from .visual_worker import unchanged

BLOCKED = re.compile(r'\b(delete|remove|erase|discard|uninstall|send|submit|publish|purchase|pay|checkout|upload|password|credential|administrator|terminal|powershell|permission)\b', re.I)


def readiness(base):
    """Check the reviewed component and owned workers without opening a window or model."""
    base = Path(base)
    try:
        manifest = json.loads((base/'runtime_manifest.json').read_text(encoding='utf-8'))['visual_interaction']
        source = base/'jarvis/_vendor/ui_tars_action_parser.py'
        digest = hashlib.sha256(source.read_text(encoding='utf-8').encode('utf-8')).hexdigest()
        if digest != manifest['component_sha256_lf']:
            raise ValueError('Reviewed UI-TARS parser checksum differs from the manifest')
        for relative in ('integrations/UI-TARS-LICENSE', 'integrations/UI-TARS-NOTICE.md',
                         'jarvis/visual_worker.py', 'jarvis/screen_worker.py'):
            if not (base/relative).is_file():
                raise ValueError('Missing visual integration file: '+relative)
        return None
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return 'Visual fallback readiness: '+str(exc)


def click_point(text):
    """Accept one literal UI-TARS click only; the upstream code generator is not included."""
    if not isinstance(text, str) or len(text) > 250:
        raise ValueError('Visual action is not a bounded UI-TARS click.')
    node = ast.parse(text.strip(), mode='eval').body
    if (not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != 'click'
            or node.args or len(node.keywords) != 1 or node.keywords[0].arg != 'start_box'
            or not isinstance(node.keywords[0].value, ast.Constant)
            or not isinstance(node.keywords[0].value.value, str)):
        raise ValueError('Visual fallback accepts only click(start_box="(x,y)").')
    from ._vendor.ui_tars_action_parser import parse_action
    parsed = parse_action(text.strip())
    coordinates = ast.literal_eval(parsed['args']['start_box'])
    if (not isinstance(coordinates, (tuple, list)) or len(coordinates) not in (2, 4)
            or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 < v < 1000 for v in coordinates)):
        raise ValueError('UI-TARS coordinates must be finite normalized values inside 0–1000.')
    if len(coordinates) == 4:
        if coordinates[0] > coordinates[2] or coordinates[1] > coordinates[3]:
            raise ValueError('Visual target box is inverted.')
        coordinates = ((coordinates[0]+coordinates[2])/2, (coordinates[1]+coordinates[3])/2)
    return [v/1000 for v in coordinates]


@dataclass
class Prepared:
    handle: int
    snapshot: dict
    frame: dict
    point: list
    step: dict
    role: str


@dataclass
class VisualOutcome:
    handle: int
    snapshot: dict
    screen: dict
    assessment: dict
    evidence: str


def save_plan(goal):
    match = re.fullmatch(r'save (?:the |this |current )?(?:document|file) as (.+?) in (?:the )?(?:folder )?(.+?)[.!?]*',
                         goal.strip(), re.I)
    if not match:
        return None
    from .commands import filename
    return {'steps': [{'action': 'save_file', 'value': filename(match[1]), 'folder': match[2],
                      'content': '', 'expected': 'The requested file is independently verified on disk'}]}


class VisualFallback:
    def __init__(self, brain):
        self.brain, self.actions = brain, brain.actions
        options = brain.options.get('visual_fallback', {})
        options = options if isinstance(options, dict) else {}
        self.enabled = options.get('enabled', False) is True
        try:
            self.minimum_confidence = max(.95, min(1.0, float(options.get('minimum_confidence', .95))))
        except (ValueError, TypeError, OverflowError):
            self.minimum_confidence = .95
        self.last_saved = None

    def checkpoint(self, stage, **details):
        self.brain.checkpoint(stage, **details)

    def capture(self, handle, snapshot, cancelled):
        frame = self.brain.visual_screen(handle, snapshot, cancelled, strict=True)
        if (frame.get('handle') != handle or not frame.get('pid') or not frame.get('rect')
                or not isinstance(frame.get('captured_at'), (int, float))):
            raise ValueError('Strict visual capture lacks target identity and geometry.')
        return frame

    def observe(self, cancelled, pid=None):
        handle, snapshot = self.brain.observe(cancelled)
        frame = self.capture(handle, snapshot, cancelled)
        if pid is not None and frame['pid'] != pid:
            raise ValueError('The dialog belongs to a different application; no input was sent.')
        return handle, snapshot, frame

    def prepare(self, goal, step, handle, snapshot, cancelled):
        if not self.enabled or cancelled():
            raise TaskFailure('Visual fallback is disabled or cancelled.', attempted=False)
        if step['action'] not in {'select', 'open_menu', 'handle_dialog', 'fill_text'} or BLOCKED.search(step['value']):
            raise TaskFailure('This target requires its dedicated explicit tool or direct user control.', attempted=False)
        try:
            frame = self.capture(handle, snapshot, cancelled)
            proposal = self.brain.client.request('visual_ground', cancelled, goal=goal, step=step, screen=frame)
            if (type(proposal.get('confidence')) not in (int, float)
                    or not math.isfinite(proposal['confidence']) or proposal['confidence'] < self.minimum_confidence
                    or proposal['confidence'] > 1 or common(proposal.get('target', '')) != common(step['value'])
                    or BLOCKED.search(proposal.get('target', ''))):
                raise ValueError('The named visual target was not confidently identified.')
            role = proposal.get('role')
            if role not in {'Button', 'Edit', 'MenuItem', 'TabItem', 'Hyperlink', 'ListItem', 'ComboBox'}:
                raise ValueError('The visual control role is unsupported.')
            if step['action'] == 'handle_dialog' and proposal.get('is_dialog') is not True:
                raise ValueError('No Save/confirmation dialog was visually established.')
            if step['action'] == 'fill_text' and (role != 'Edit' or proposal.get('password') is not False
                    or not isinstance(step.get('content'), str) or not 0 < len(step['content']) <= 2000
                    or any(ord(c) < 32 for c in step['content'])):
                raise ValueError('Visual typing requires a non-password single-line textbox with literal content.')
            xy = click_point(proposal['action'])
            # Inference can be slow. Never inject coordinates into its old screenshot.
            fresh = self.capture(handle, snapshot, cancelled)
            if (any(fresh[k] != frame[k] for k in ('handle', 'pid', 'rect', 'title'))
                    or not unchanged(frame['image'], fresh['image'], xy)):
                raise ValueError('The interface changed while grounding; inspect and plan from its new state.')
            return Prepared(handle, snapshot, fresh, xy, step, role)
        except (ValueError, OSError, KeyError, SyntaxError, TypeError) as exc:
            raise TaskFailure(str(exc), attempted=False) from exc

    def input(self, operation, frame, cancelled, **data):
        """Owned one-shot worker; its disappearance always means uncertain input."""
        if cancelled():
            raise TaskFailure('Visual input cancelled before dispatch.', attempted=False)
        process, submitted = None, False
        try:
            process = subprocess.Popen([sys.executable, '-m', 'jarvis.visual_worker'],
                cwd=self.brain.client.base, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, encoding='utf-8',
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            payload = json.dumps({'operation': operation, 'owner_pid': os.getpid(), 'frame': frame, **data})
            deadline, first = time.monotonic()+20, True
            while True:
                if cancelled() or time.monotonic() >= deadline:
                    raise TaskFailure('Visual input stopped; inspect the result before continuing.', attempted=submitted)
                try:
                    submitted = True
                    output, error = process.communicate(input=payload if first else None, timeout=.2)
                    break
                except subprocess.TimeoutExpired:
                    first = False
            if process.returncode:
                raise TaskFailure('Visual input worker stopped; input outcome is uncertain.', attempted=True)
            response = json.loads(output)
            if response.get('error'):
                raise TaskFailure(response['error'], attempted=response.get('attempted') is not False)
            if response.get('attempted') is not True:
                raise TaskFailure('Visual input worker returned no dispatch evidence.', attempted=True)
            return response
        except TaskFailure:
            raise
        except (OSError, ValueError, TypeError) as exc:
            raise TaskFailure('Visual input worker: ' + str(exc), attempted=submitted) from exc
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.communicate()

    def execute(self, goal, prepared, cancelled):
        step = prepared.step
        self.checkpoint('acting', action=step['action'], target=step['value'], source='ui_tars_visual')
        self.input('click', prepared.frame, cancelled, point=prepared.point)
        try:
            handle, snapshot, after = self.observe(cancelled, pid=prepared.frame['pid'])
            if step['action'] == 'fill_text':
                focused = self.brain.client.request('visual_field', cancelled, goal=goal,
                    step={**step, 'expected': 'The named textbox is visibly focused'}, screen=after, focused_only=True)
                if focused.get('verified') is not True:
                    raise ValueError('The textbox focus could not be independently checked; no text was typed.')
                # Verification inference also takes time: acquire a fresh frame for typing.
                fresh = self.capture(handle, snapshot, cancelled)
                if (any(after[k] != fresh[k] for k in ('handle', 'pid', 'rect', 'title'))
                        or not unchanged(after['image'], fresh['image'], prepared.point)):
                    raise ValueError('The textbox changed during focus verification; no text was typed.')
                self.input('fill', fresh, cancelled, point=prepared.point, content=step['content'])
                handle, snapshot, after = self.observe(cancelled, pid=prepared.frame['pid'])
                check = self.brain.client.request('visual_field', cancelled, goal=goal, step=step, screen=after)
                if check.get('verified') is not True or check.get('observed_text') != step['content']:
                    raise ValueError('The entered textbox value could not be independently read back.')
                assessment = {'step_verified': True, 'goal_done': False,
                    'summary': 'Named textbox visually read back; semantic/functional correctness is not established.',
                    'reason': 'The screenshot transcription matched the requested literal text.'}
            else:
                assessment = self.brain.client.request('visual', cancelled, goal=goal, step=step,
                    previous=self.brain.visual_context(prepared.frame), completed=[], screen=after)
                if assessment.get('step_verified') is not True:
                    raise ValueError('The visual action outcome was not observed: ' + str(assessment.get('reason', '')))
            after['summary'] = str(assessment.get('summary', ''))[:1000]
            evidence = 'UI-TARS parsed click; fresh local visual outcome checked: ' + step['value']
            self.checkpoint('visual_outcome', action=step['action'], target=step['value'],
                            source='fresh_visual_verifier', evidence=evidence)
            return VisualOutcome(handle, snapshot, after, assessment, evidence)
        except TaskFailure as exc:
            # An earlier click already happened, even if later typing was refused before dispatch.
            raise TaskFailure(str(exc), attempted=True) from exc
        except (ValueError, OSError, KeyError, TypeError) as exc:
            raise TaskFailure(str(exc), attempted=True) from exc

    def named(self, goal, step, cancelled, pid=None):
        """Save workflow primitive: an exact native match wins; no retry after a native failure."""
        if cancelled():
            raise TaskFailure('Dialog input cancelled before dispatch.', attempted=False)
        from .agent_events import check_policy
        from .targeting import scoped_matches
        check_policy(self.actions, step['action'])
        handle, snapshot, frame = self.observe(cancelled, pid)
        controls = snapshot.get('controls', [])
        if step['action'] == 'fill_text':
            controls = [c for c in controls if c.get('role') == 'Edit' and not c.get('password')]
        else:
            controls = [c for c in controls if c.get('role') in {'Button', 'MenuItem', 'ComboBox'}]
        matching = scoped_matches(controls, step['value'])
        if step['action'] == 'handle_dialog' and snapshot.get('is_dialog') is not True:
            matching = []
        if len(matching) > 1:
            raise TaskFailure('The named dialog control is ambiguous; specify its exact label.', attempted=False)
        if not matching:
            return self.execute(goal, self.prepare(goal, step, handle, snapshot, cancelled), cancelled)
        target = matching[0]
        if cancelled():
            raise TaskFailure('Dialog input cancelled before dispatch.', attempted=False)
        try:
            self.checkpoint('acting', action=step['action'], target=step['value'], source='native_save_dialog')
            if step['action'] == 'fill_text':
                result = self.actions._ui().runner({'operation': 'fill_text', 'handle': handle,
                    'owner_pid': os.getpid(), 'control': target, 'content': step['content']}, cancelled)['message']
                if not result.endswith('exact field value verified'):
                    raise ValueError('The native filename field did not confirm its exact value.')
            else:
                self.actions._ui()._activate(handle, snapshot, target, 'select', cancelled)
            landed, snap, after = self.observe(cancelled, frame['pid'])
            after['summary'] = ('Filename field value independently checked through UI Automation.'
                                if step['action'] == 'fill_text' else 'Named native dialog choice was sent; verify its destination.')
            return VisualOutcome(landed, snap, after, {'step_verified': step['action'] == 'fill_text', 'goal_done': False}, after['summary'])
        except (ValueError, OSError, KeyError, TypeError) as exc:
            raise TaskFailure('Native dialog input was attempted; no visual replay. ' + str(exc), attempted=True) from exc

    def dialog_kind(self, frame, snapshot, cancelled):
        # Native filename field + explicit Save dialog title is stronger than a generic modal flag.
        edits = [c for c in snapshot.get('controls', []) if c.get('role') == 'Edit' and not c.get('password')]
        if re.search(r'\bsave as\b', frame.get('title', ''), re.I) and edits:
            return {'kind': 'save_as', 'filename_label': next((c['name'] for c in edits
                if re.search(r'file.?name', c['name'], re.I)), ''), 'confirm_label': 'Save'}
        if not snapshot.get('visual_only') and snapshot.get('is_dialog') is False:
            return {'kind': 'none', 'filename_label': '', 'confirm_label': ''}
        result = self.brain.client.request('visual_dialog', cancelled, screen=frame)
        if type(result.get('confidence')) not in (float, int) or not self.minimum_confidence <= result['confidence'] <= 1:
            raise ValueError('The Save dialog was not confidently recognized.')
        label = result.get('filename_label', '')
        if result.get('kind') == 'save_as' and (not isinstance(label, str) or len(label)>100
                or re.search(r'[/\\]|\.[a-z0-9]{1,10}\b', label, re.I)):
            raise ValueError('The Save dialog returned a filename/path instead of its field label; no input was sent.')
        return result

    @staticmethod
    def file_state(path):
        from .skill_memory import linked
        if any(linked(p) for p in (path, *path.parents)):
            raise ValueError('Save targets cannot be linked files.')
        if not path.exists():
            return None
        if not path.is_file() or path.stat().st_size > 20*1024*1024:
            raise ValueError('Save verification requires a regular file up to 20 MB.')
        state = path.stat()
        data = path.read_bytes()
        after = path.stat()
        if (state.st_size, state.st_mtime_ns, state.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
            raise ValueError('The saved file changed during disk readback; inspect it before continuing.')
        return {'size': state.st_size, 'mtime_ns': state.st_mtime_ns, 'sha256': hashlib.sha256(data).hexdigest()}

    def save_file(self, goal, step, cancelled):
        if not self.enabled or cancelled():
            raise TaskFailure('The Save-dialog integration is disabled or cancelled.', attempted=False)
        from .commands import filename
        from .skill_memory import linked
        name = filename(step['value'])
        selected = Path(self.actions._task_folder(step['folder'], cancelled))
        if any(linked(p) for p in (selected, *selected.parents)):
            raise TaskFailure('The Save destination contains a linked path.', attempted=False)
        folder = selected.resolve(strict=True)
        path = folder / name
        if any(linked(p) for p in [path, folder, *folder.parents]):
            raise TaskFailure('The Save destination contains a linked path.', attempted=False)
        before = self.file_state(path)
        approved = before is not None
        if approved:
            self.actions._approve('overwrite', str(path) + '\nReplace it with the current application document.', cancelled)
            if self.file_state(path) != before:
                raise TaskFailure('The Save target changed while awaiting approval.', attempted=False)
        self.last_saved = None
        dispatched = False
        try:
            handle, snapshot, frame = self.observe(cancelled)
            pid = frame['pid']
            kind = self.dialog_kind(frame, snapshot, cancelled)
            if kind['kind'] not in {'save_as', 'none'}:
                raise ValueError('Resolve the current confirmation dialog explicitly before starting Save As.')
            if kind['kind'] != 'save_as':
                from .agent_events import check_policy
                check_policy(self.actions, 'shortcut')
                # Native UIA shortcut binding remains first; raw input only when the provider is unavailable.
                fresh_handle, fresh, fresh_frame = self.observe(cancelled, pid)
                self.checkpoint('acting', action='shortcut', target='ctrl+shift+s', source='save_dialog')
                dispatched = True
                if fresh.get('visual_only'):
                    self.input('shortcut', fresh_frame, cancelled, value='ctrl+shift+s')
                else:
                    self.actions._ui().runner({'operation': 'shortcut', 'handle': fresh_handle,
                        'owner_pid': os.getpid(), 'signature': fresh['signature'], 'value': 'ctrl+shift+s'}, cancelled)
                handle, snapshot, frame = self.observe(cancelled, pid)
                kind = self.dialog_kind(frame, snapshot, cancelled)
                if kind['kind'] != 'save_as':
                    raise ValueError('Save As did not become visible; the shortcut was not repeated.')
                self.checkpoint('verified', action='shortcut', target='ctrl+shift+s',
                                source='fresh_dialog_observation', evidence='Save As dialog observed')
            label = kind.get('filename_label') or 'File name'
            # Enter an absolute requested path in the filename field; do not navigate to an inferred folder.
            dispatched = True
            self.named(goal, {'action': 'fill_text', 'value': label, 'content': str(path),
                'expected': 'The filename textbox contains the exact requested absolute path'}, cancelled, pid)
            self.checkpoint('verified', action='fill_text', target='File name', source='field_readback',
                            evidence='Requested Save destination read back before confirmation')
            current = self.file_state(path)
            if current != before:
                raise ValueError('The Save target changed before confirmation; no Save click was sent.')
            dispatched = True
            self.named(goal, {'action': 'handle_dialog', 'value': kind.get('confirm_label') or 'Save',
                'expected': 'Save As closes or shows its overwrite confirmation'}, cancelled, pid)
            handle, snapshot, frame = self.observe(cancelled, pid)
            kind = self.dialog_kind(frame, snapshot, cancelled)
            if kind['kind'] == 'overwrite':
                if (not approved or self.file_state(path) != before
                        or str(kind.get('overwrite_name', '')).casefold() != path.name.casefold()):
                    raise ValueError('An unapproved or changed overwrite target needs your review; no Replace click was sent.')
                self.named(goal, {'action': 'handle_dialog', 'value': kind.get('confirm_label') or 'Yes',
                    'expected': 'Approved overwrite dialog closes'}, cancelled, pid)
                handle, snapshot, frame = self.observe(cancelled, pid)
                kind = self.dialog_kind(frame, snapshot, cancelled)
            if kind['kind'] != 'none':
                raise ValueError('The Save/overwrite dialog is still unresolved; inspect it before continuing.')
            deadline, verified = time.monotonic()+5, None
            while time.monotonic() < deadline:
                if cancelled():
                    raise ValueError('Save observation cancelled after input; inspect the file before repeating it.')
                a = self.file_state(path)
                if a is not None and a != before:
                    time.sleep(.15)
                    b = self.file_state(path)
                    if a == b:
                        verified = b
                        break
                time.sleep(.1)
            if verified is None:
                raise ValueError('The named file did not show a stable new/changed disk result; Save was not repeated.')
            if step.get('content') and path.read_text(encoding='utf-8') != step['content']:
                raise ValueError('The saved file did not match the explicitly requested text.')
            self.last_saved = {'path': path, **verified}
            evidence = f'Saved file independently read back: {name}; {verified["size"]} bytes; SHA-256 {verified["sha256"]}. Document semantics are not verified.'
            self.checkpoint('file_save_verified', action='save_file', target=name,
                            source='disk_readback', evidence=evidence)
            return evidence
        except TaskFailure as exc:
            raise TaskFailure(str(exc), attempted=dispatched or exc.attempted) from exc
        except (ValueError, OSError, KeyError, TypeError) as exc:
            raise TaskFailure(str(exc), attempted=dispatched) from exc
