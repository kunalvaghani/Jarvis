"""Shared capabilities and dispatch for the planner and desktop task runner."""
from dataclasses import dataclass
import json
import re

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
    ToolSpec("fill_text", "desktop", "Replace a named visible Edit field with exact content; does not submit."),
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


@dataclass(frozen=True)
class ToolResult:
    tool: str
    backend: str
    evidence: str
    # Dispatch evidence is not verification of the user's goal.
    attempted: bool = True


class ToolRegistry:
    def __init__(self, actions):
        self.actions = actions
        self.specs = {spec.name: spec for spec in SPECS}

    def catalog(self, goal=None):
        from .toolkits import available
        rows = [{"action": spec.name, "backend": spec.backend,
                 "description": spec.description, "approval": spec.approval}
                for spec in self.specs.values() if goal is None or spec.name not in KIT_TOOLS or available(spec.name)]
        allowed = getattr(self.actions, 'allowed_tools', None)
        if isinstance(allowed, (set, frozenset)):
            rows = [row for row in rows if row['action'] in allowed]
        config = getattr(self.actions, 'config', {})
        if goal is not None and (not isinstance(config, dict) or not config.get('brain', {}).get('visual_fallback', {}).get('enabled', False)):
            rows = [row for row in rows if row['action'] != 'save_file']
        options = config.get('agent_runtime', {}) if isinstance(config, dict) else {}
        if goal is None or not options.get('deferred_tools', False):
            return rows
        loaded = getattr(self.actions, '_discovered_tools', set())
        loaded = loaded if isinstance(loaded, set) else set()
        selected = {row['action'] for row in self.search(goal)} | loaded | {'tool_search', 'toolkit_status'}
        return [row for row in rows if row['action'] not in KIT_TOOLS or row['action'] in selected]

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
        return [{'action': spec.name, 'backend': spec.backend, 'description': spec.description,
                 'approval': spec.approval} for spec in (self.specs[name] for name in names)]

    def execute(self, step, cancelled, activate=None):
        from .agent_events import check_policy, event
        name = step.get('action')
        allowed = getattr(self.actions, 'allowed_tools', None)
        if isinstance(allowed, (set, frozenset)) and name not in allowed:
            raise ValueError('Tool is outside the current task scope: ' + str(name))
        check_policy(self.actions, name)
        call_id = event(self.actions, 'tool.started', name)
        try:
            result = self._execute(step, cancelled, activate)
        except Exception as exc:
            # Audit failures cannot turn an uncertain write into a retriable action.
            try:
                event(self.actions, 'tool.failed', name, call_id, error_type=type(exc).__name__)
            except (OSError, ValueError):
                pass
            raise
        try:
            event(self.actions, 'tool.completed', name, call_id, backend=result.backend)
        except (OSError, ValueError):
            pass
        return result

    def _execute(self, step, cancelled, activate=None):
        name = step.get("action")
        if name not in self.specs:
            raise ValueError("Unsupported tool: " + str(name))
        if cancelled():
            raise ValueError("Task cancelled before tool execution.")
        if name in {"browser_inspect", "browser_navigate", "browser_click", "browser_fill"}:
            if name == "browser_fill" and (not isinstance(step.get("content"), str) or len(step["content"]) > 10000):
                raise ValueError("Browser filling requires bounded exact content.")
            operation = {"browser_inspect": "inspect", "browser_navigate": "navigate", "browser_click": "click", "browser_fill": "fill"}[name]
            result = self.actions._browser().request(operation, cancelled, value=step.get("value", ""),
                        url=step.get("folder", ""), content=step.get("content", ""))
            return ToolResult(name, "dom", json.dumps(result, ensure_ascii=False)[:12000])
        spec = self.specs[name]
        validate_desktop_step(step)
        self.actions.report("tool", spec.backend + ": " + name + " " + str(step.get("value", "")))
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
        elif name in CONTROL_ACTIONS or name in {"shortcut", "scroll"}:
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
