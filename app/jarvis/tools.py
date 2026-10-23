"""Shared capabilities and dispatch for the planner and desktop task runner."""
from dataclasses import dataclass, replace
import json
import os
import re
import time

from .commands import Command
from .desktop_actions import CONTROL_ACTIONS, validate_desktop_step
from .toolkits import TOOLS as KIT_TOOLS


@dataclass(frozen=True)
class ToolSpec:
    name: str
    backend: str
    description: str
    approval: str = "none"


SPECS = (
    ToolSpec('workflow_expand', 'toolkit', 'Propose bounded subtasks in the CURRENT durable workflow. value=stable expansion key; content=JSON {requests:[{kind:"task"|"ask"|"jarvis_status"|"system_info"|"screen_info",value:"...",extra:""}],join:optional existing task UUID}. Maximum 20 children/call, 50/workflow, depth 3. Children wait for a verified parent result; effectful children additionally require explicit scope review and existing tool approvals. Does not execute children or grant permissions.'),
    ToolSpec('application_inspect', 'desktop', 'Read a configured app executable/version and sanitized foreground controls. value MUST be an exact configured application name or current for the current configured app. Cube, Modifier and other object/control names are invalid; use select for controls. Read-only: never selects objects, launches, types, clicks, installs or executes scripts.'),
    ToolSpec('realtime_query', 'realtime', 'Read one of the green public APIs. value=provider ID or catalog; content=JSON arguments {query,id,symbol,latitude,longitude,timezone,base,target,country,route,to_latitude,to_longitude}. No arbitrary URLs or writes. Returns timestamps, coverage and failures. Use catalog first to choose an exact provider; self-hosted sources require configured endpoints.'),
    ToolSpec("open", "desktop", "Open a configured app or named file/folder. Folder values can include a spoken drive constraint; preserve it. Existing full paths avoid app-name ambiguity. Folder-opening preferences do not authorize writes."),
    ToolSpec("browse", "browser", "Open a website URL in an installed browser."),
    ToolSpec("browser_search", "browser", "Search the web using the exact query."),
    ToolSpec("browser_inspect", "dom", "Read the Jarvis-owned browser's current URL, title and visible named controls. Use before browser_click/fill."),
    ToolSpec("browser_navigate", "dom", "Open an explicit public website/domain in the Jarvis-owned Chrome profile; returns its current URL/title/controls."),
    ToolSpec("browser_click", "dom", "Click one exact visible named button/link in the Jarvis browser. value=label, folder=last observed exact URL. Does not approve account writes."),
    ToolSpec("browser_fill", "dom", "Fill one unique named non-password textbox with exact requested content in the Jarvis browser. folder=last observed URL; does not submit."),
    ToolSpec("media_search", "browser", "Search YouTube or the native Spotify app; does not start playback."),
    ToolSpec("media_control", "desktop", "Control foreground YouTube or native Spotify using fresh accessible controls. Set platform youtube or spotify. YouTube: play, pause, mute, unmute, fullscreen, exit_fullscreen, captions, captions_on/off, seek_10/-10, position_0..100, volume_0..100/up/down, next/previous, speed_up/down, next/previous_chapter, next/previous_frame (paused), restart, theater, miniplayer, status. Spotify: play/pause/next/previous/status, seek_seconds, shuffle_on/off, repeat_one/all/off, volume_0..100/up/down, mute/unmute; UI: queue, library, playlists, artists, albums, podcasts, home, now_playing, liked_songs, lyrics, like, add_queue. Named menus/select/fill_text cover other exposed controls."),
    ToolSpec("select", "desktop", "Activate a currently visible enabled control after checking its identity."),
    ToolSpec("fill_text", "desktop", "Replace a named visible Edit field with exact content; does not submit. value = the field's visible name exactly as listed in screen fields (for example Search), content = the exact text to enter."),
    ToolSpec("type_text", "desktop", "Type the user's exact words with the keyboard into the focused window, for editors whose text area is not a listed field (for example Notepad or Word). value = the window title, content = the exact text from the request. Does not save."),
    ToolSpec("scroll", "desktop", "Scroll the current accessible window one page up, down, left or right."),
    ToolSpec("shortcut", "desktop", "Press an allowed shortcut in the current checked window."),
    ToolSpec("open_menu", "desktop", "Expand or invoke a named visible menu or dropdown, then observe its items."),
    ToolSpec("handle_dialog", "desktop", "Choose a named visible dialog button; never guess or approve deletion."),
    ToolSpec("save_file", "desktop", "Save the current application document through its Save As dialog to the explicitly requested filename=value and folder. Native controls first, UI-TARS parsed visual fallback when absent. Overwrite needs runtime approval; success requires independent disk readback. Use for user requests to save documents, never infer a destination."),
    ToolSpec("close_app", "desktop", "Close the app explicitly named by the user."),
    ToolSpec("create_file", "files", "Create a named UTF-8 file directly with exact content in the identified folder."),
    ToolSpec("modify_file", "files", "Modify an existing UTF-8 file directly using exact replacement text."),
    ToolSpec("delete_file", "files", "Move one explicitly named file to Recycle Bin after user approval.", "user"),
    ToolSpec("run_command", "terminal", "Run the explicitly requested command and return output and exit code after approval.", "user"),
)
SPECS += tuple(ToolSpec(name, "toolkit", data[1], "user" if data[3] else "none")
               for name, data in KIT_TOOLS.items())
TOOL_NAMES = tuple(spec.name for spec in SPECS)

# Fields each built-in tool reads: (required, optional). Toolkit tools are checked by toolkits.validate_step.
_FIELDS = {
    'workflow_expand': ({'value','content'}, set()),
    'application_inspect': ({'value'}, set()), 'realtime_query': ({'value'}, {'content'}),
    'open': ({'value'}, set()), 'browse': ({'value'}, {'browser'}), 'browser_search': ({'value'}, {'browser'}),
    'browser_inspect': (set(), {'value', 'folder', 'content'}), 'browser_navigate': (set(), {'value', 'folder', 'content'}),
    'browser_click': (set(), {'value', 'folder', 'content'}), 'browser_fill': (set(), {'value', 'folder', 'content'}),
    'media_search': ({'value', 'platform'}, set()), 'media_control': ({'value', 'platform'}, set()),
    'select': ({'value'}, set()), 'fill_text': ({'value', 'content'}, set()), 'type_text': ({'value', 'content'}, set()),
    'scroll': ({'value'}, set()), 'shortcut': ({'value'}, set()), 'open_menu': ({'value'}, set()),
    'handle_dialog': ({'value'}, set()), 'save_file': ({'value'}, {'folder'}), 'close_app': ({'value'}, set()),
    'create_file': ({'value', 'folder', 'content'}, set()), 'modify_file': ({'value', 'folder', 'content'}, {'find'}),
    'delete_file': ({'value', 'folder'}, set()), 'run_command': ({'value'}, set()),
}
_LIMITS = {'value': 4000, 'content': 2_000_000, 'find': 1_000_000}
# A proposal can never carry its own authorization; only the host approval flow grants it.
APPROVAL_CLAIMS = frozenset({'approved', 'approval', 'preapproved', 'user_approved', 'authorized', 'authorization',
                             'skip_approval', 'bypass_approval', 'requires_approval', 'permission', 'permissions'})
_SECRET_PATTERNS = (
    (re.compile(r'''(?i)(["']?\b(?:access_token|refresh_token|id_token|client_secret|api[_-]?key|apikey|token|secret|password|passwd|pwd|authorization)["']?\s*:\s*)(?:"[^"\r\n]*"|'[^'\r\n]*'|(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]+|[^\s,}\]]+)'''), r'\1[redacted]'),
    (re.compile(r'(?i)\b(access_token|refresh_token|id_token|client_secret|api[_-]?key|apikey|token|secret|'
                r'password|passwd|pwd|sig|signature)=([^&\s#"\']+)'), r'\1=[redacted]'),
    (re.compile(r'(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}'), r'\1 [redacted]'),
    (re.compile(r'\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|'
                r'xox[abprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{30,}|gsk_[A-Za-z0-9]{20,})'), '[redacted]'),
)


class ToolArgumentError(ValueError):
    """A proposal failed its tool contract; nothing was reported or dispatched."""


def redact(text):
    """Scrub credential-like values from emitted traces (UI reports, logs); never from tool evidence."""
    text = str(text)
    for key, secret in os.environ.items():
        if len(secret) >= 8 and re.search(r'TOKEN|PASSWORD|SECRET|API_?KEY|ACCESS_KEY', key, re.I) and secret in text:
            text = text.replace(secret, '[redacted]')
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def required_arguments(name):
    """Expose existing argument prerequisites to native schema generation."""
    required = set(_FIELDS.get(name, (set(), set()))[0])
    from .toolkits import requires_folder
    if requires_folder(name):
        required.add('folder')
    return required


def validate_arguments(step):
    """Deterministic contract check before any report, approval prompt or dispatch."""
    if not isinstance(step, dict):
        raise ToolArgumentError('A tool step must be an object.')
    name = step.get('action')
    if name in KIT_TOOLS:
        from .toolkits import validate_step
        try:
            validate_step(step)
        except KeyError as exc:
            raise ToolArgumentError('Missing tool argument: ' + str(exc.args[0])) from None
        except ValueError as exc:
            raise ToolArgumentError(str(exc)) from None
        return
    required, optional = _FIELDS.get(name, (set(), set()))
    missing = sorted(field for field in required if field not in step)
    if missing:
        raise ToolArgumentError(f'{name} requires: ' + ', '.join(missing))
    for field in required | optional:
        if field in step and not isinstance(step[field], str):
            raise ToolArgumentError(f'{name} {field} must be text.')
        if len(step.get(field, '')) > _LIMITS.get(field, 4000):
            raise ToolArgumentError(f'{name} {field} exceeds its size limit.')
    if 'value' in required and not step['value'].strip():
        raise ToolArgumentError(f'{name} requires a nonempty value.')
    if name == 'realtime_query':
        try:
            params = json.loads(step.get('content') or '{}')
        except (ValueError, RecursionError):
            raise ToolArgumentError('realtime_query content must be a JSON object.') from None
        if not isinstance(params, dict):
            raise ToolArgumentError('realtime_query content must be a JSON object.')
    if name == 'workflow_expand':
        try:
            data = json.loads(step['content'])
            if not isinstance(data,dict) or set(data)-{'requests','join'} or not isinstance(data.get('requests'),list) or not 1 <= len(data['requests']) <= 20:
                raise ValueError()
            if len(step['value']) > 100 or len(step['content']) > 64000:raise ValueError()
            for command in data['requests']:
                if not isinstance(command,dict) or set(command)!={'kind','value','extra'} or any(not isinstance(v,str) for v in command.values()):raise ValueError()
                if command['kind'] not in {'task','ask','jarvis_status','system_info','screen_info'} or command['extra']:raise ValueError()
            if 'join' in data and (not isinstance(data['join'],str) or not re.fullmatch('[0-9a-f]{32}',data['join'])):raise ValueError()
        except (ValueError,TypeError,RecursionError):
            raise ToolArgumentError('workflow_expand requires bounded ordinary requests, a stable key and optional task UUID.') from None


def failure_category(exc, cancelled):
    from .toolkits import ToolUnavailable
    if isinstance(exc, ToolArgumentError):
        return 'invalid_arguments'
    if isinstance(exc, ToolUnavailable):
        return 'unavailable'
    try:
        if cancelled():
            return 'cancelled'
    except Exception:
        pass
    return 'failed'


@dataclass(frozen=True)
class ToolResult:
    tool: str
    backend: str
    evidence: str
    # Dispatch evidence is not verification of the user's goal.
    attempted: bool = True
    call_id: str = ''  # Correlates with .jarvis-runtime/agent-events.jsonl.


def _outcome(actions, name, step, call_id, started, result=None, category=None):
    """Execution-method telemetry (execution_contracts); never affects the tool result."""
    try:
        from .execution_strategy import observe
        observe(actions, name, step, call_id, (time.perf_counter() - started) * 1000, result, category)
    except Exception:  # Broad by design: telemetry must not turn a completed call into a failure.
        pass


class ToolRegistry:
    def __init__(self, actions):
        self.actions = actions
        self.specs = {spec.name: spec for spec in SPECS}

    def self_model(self, names):
        from .capability_model import model_for
        model = model_for(self.actions)
        return model.describe(self.specs, names, getattr(self.actions, 'allowed_tools', None)) if model else {}

    def catalog(self, goal=None):
        from .toolkits import available
        rows = [{"action": spec.name, "backend": spec.backend,
                 "description": spec.description, "approval": spec.approval}
                for spec in self.specs.values() if goal is None or spec.name not in KIT_TOOLS or available(spec.name)]
        if getattr(self.actions,'ingress',None) is None:
            rows = [row for row in rows if row['action']!='workflow_expand']
        allowed = getattr(self.actions, 'allowed_tools', None)
        if isinstance(allowed, (set, frozenset)):
            rows = [row for row in rows if row['action'] in allowed]
        config = getattr(self.actions, 'config', {})
        if goal is not None and (not isinstance(config, dict) or not config.get('brain', {}).get('visual_fallback', {}).get('enabled', False)):
            rows = [row for row in rows if row['action'] != 'save_file']
        options = config.get('agent_runtime', {}) if isinstance(config, dict) else {}
        if goal is not None and options.get('deferred_tools', False):
            loaded = getattr(self.actions, '_discovered_tools', set())
            loaded = loaded if isinstance(loaded, set) else set()
            selected = {row['action'] for row in self.search(goal)} | loaded | {'tool_search', 'toolkit_status'}
            rows=[row for row in rows if row['action'] not in KIT_TOOLS or row['action'] in selected]
            from .capabilities import relevant_tool
            # Tools the ranking chose for this request (including skill-guided ones) always stay.
            rows=[row for row in rows if row['action'] in selected or relevant_tool(row['action'], goal)]
        from .repo_tools import definitions
        from .utility_profiles import decorate
        return decorate(rows)+definitions(self.actions,goal or '.',6)

    def search(self, query, limit=12):
        """Rank configured deferred tools; never expose credentials or start providers."""
        from .capabilities import rank_tools
        allowed = getattr(self.actions, 'allowed_tools', None)
        skills = getattr(self.actions, 'skills', None)
        from .skill_memory import SkillMemory
        if isinstance(skills, SkillMemory):
            skills.refresh()
        else:
            skills = None
        names = rank_tools(self.specs, query, allowed, skills, limit)
        from .repo_tools import definitions
        from .utility_profiles import decorate
        return (decorate([{'action': spec.name, 'backend': spec.backend, 'description': spec.description,
                 'approval': spec.approval} for spec in (self.specs[name] for name in names)]
                )+definitions(self.actions,query,min(limit,6)))

    def execute(self, step, cancelled, activate=None):
        from .agent_events import task_trace
        with task_trace(self.actions):
            return self._execute_traced(step, cancelled, activate)

    def _execute_traced(self, step, cancelled, activate=None):
        from .agent_events import check_policy, event
        # Type first: a non-object proposal must not reach identity or policy checks.
        if not isinstance(step, dict):
            raise ToolArgumentError('A tool step must be an object.')
        if 'task_id' in step:
            from .task_state import TaskState
            state=getattr(self.actions,'task_state',None)
            if not isinstance(state,TaskState):
                raise ValueError('Task identity is unavailable; execution refused.')
            state.require_identity(step['task_id'])
            step={key:value for key,value in step.items() if key!='task_id'}
        step = {key: value for key, value in step.items() if key not in APPROVAL_CLAIMS}
        name = step.get('action')
        allowed = getattr(self.actions, 'allowed_tools', None)
        if isinstance(allowed, (set, frozenset)) and name not in allowed:
            raise ValueError('Tool is outside the current task scope: ' + str(name))
        check_policy(self.actions, name)
        call_id = event(self.actions, 'tool.started', name)
        started = time.perf_counter()
        try:
            if name in self.specs:
                validate_arguments(step)
            result = self._execute(step, cancelled, activate)
        except Exception as exc:
            # Audit failures cannot turn an uncertain write into a retriable action.
            category = failure_category(exc, cancelled)
            try:
                event(self.actions, 'tool.failed', name, call_id, error_type=type(exc).__name__,
                      category=category)
            except (OSError, ValueError):
                pass
            _outcome(self.actions, name, step, call_id, started, category=category)
            raise
        try:
            event(self.actions, 'tool.completed', name, call_id, backend=result.backend)
        except (OSError, ValueError):
            pass
        _outcome(self.actions, name, step, call_id, started, result=result)
        return replace(result, call_id=call_id) if isinstance(result, ToolResult) else result

    def _execute(self, step, cancelled, activate=None):
        name = step.get("action")
        if name not in self.specs:
            raise ValueError("Unsupported tool: " + str(name))
        if cancelled():
            raise ValueError("Task cancelled before tool execution.")
        if name == 'workflow_expand':
            ingress = getattr(self.actions,'ingress',None)
            parent = getattr(ingress.scheduler.local,'identity',None) if ingress else None
            if not parent:raise ValueError('Workflow expansion requires an active durable task')
            data = json.loads(step['content'])
            children = ingress.expand(parent,[Command(**c) for c in data['requests']],step['value'],join=data.get('join'))
            return ToolResult(name,'toolkit',json.dumps({'parent':parent,'children':children,'execution':'pending parent verification and policy gates'}))
        if name == 'application_inspect':
            from .application_discovery import inspect
            return ToolResult(name, 'desktop_observation', json.dumps(inspect(self.actions, step['value'], cancelled), ensure_ascii=False))
        if name == 'realtime_query':
            params = json.loads(step.get('content') or '{}')
            realtime = getattr(self.actions, 'realtime', None)
            if realtime is None:
                from .toolkits import ToolUnavailable
                raise ToolUnavailable('Realtime data is not available in this session.')
            result = realtime.query(step.get('value',''), params, cancelled)
            return ToolResult(name, 'realtime', json.dumps(result, ensure_ascii=False))
        if name in {"browser_inspect", "browser_navigate", "browser_click", "browser_fill"}:
            if name == "browser_fill" and (not isinstance(step.get("content"), str) or len(step["content"]) > 10000):
                raise ValueError("Browser filling requires bounded exact content.")
            operation = {"browser_inspect": "inspect", "browser_navigate": "navigate", "browser_click": "click", "browser_fill": "fill"}[name]
            if name == 'browser_navigate':
                from .youtube_chrome import open_requested
                pinned = open_requested(self.actions, step.get('value', ''), cancelled)
                if pinned is not None:
                    return ToolResult(name, 'browser', json.dumps(pinned, ensure_ascii=False))
            result = self.actions._browser().request(operation, cancelled, value=step.get("value", ""),
                        url=step.get("folder", ""), content=step.get("content", ""))
            return ToolResult(name, "dom", json.dumps(result, ensure_ascii=False)[:12000])
        spec = self.specs[name]
        validate_desktop_step(step)
        self.actions.report("tool", redact(spec.backend + ": " + name + " " + str(step.get("value", ""))))
        if name == 'save_file':
            from .task_state import TaskState
            state = getattr(self.actions, 'task_state', None)
            task = state.snapshot() if isinstance(state, TaskState) else None
            if not task or task.get('status') != 'running':
                raise ValueError('Save requires a current explicitly authorized Jarvis task.')
            self.actions.brain.validate_remaining([step], task['goal'])
            evidence = self.actions.brain.visual_fallback.save_file(task['goal'], step, cancelled)
        elif name in KIT_TOOLS:
            from .toolkits import execute
            evidence = execute(self.actions, step, cancelled)
        elif name in CONTROL_ACTIONS or name in {"shortcut", "scroll", "type_text"}:
            if activate is None:
                raise ValueError("Selection requires a freshly checked visible control.")
            evidence = activate()
        else:
            value = step["value"]
            if name in {"create_file", "modify_file"}:
                data = {"folder": step["folder"], "content": step["content"]}
                if name == "modify_file":
                    data["find"] = step.get("find", "")
                command = Command("create_in_folder" if name == "create_file" else "modify_in_folder",
                                  value, json.dumps(data))
            elif name == "delete_file":
                command = Command("delete_in_folder", value, step["folder"])
            elif name in {"media_search", "media_control"}:
                command = Command(name, value, step["platform"])
            else:
                command = Command(name, value, step.get("browser", "chrome")
                                  if name in {"browse", "browser_search"} else "")
            evidence = self.actions.execute(command, cancelled)
        if cancelled():
            raise ValueError("Task cancelled after tool execution. Check the last action before repeating it.")
        return ToolResult(name, "spotify" if name == "media_search" and step.get("platform") == "spotify" else spec.backend,
                          str(evidence or "Action attempted; result needs verification."))
