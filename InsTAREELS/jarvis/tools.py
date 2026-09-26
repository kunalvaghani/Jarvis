"""Shared capabilities and dispatch for the planner and desktop task runner."""
from dataclasses import dataclass
import json

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
    ToolSpec("open", "desktop", "Open a configured app or named file/folder."),
    ToolSpec("browse", "browser", "Open a website URL in an installed browser."),
    ToolSpec("browser_search", "browser", "Search the web using the exact query."),
    ToolSpec("media_search", "browser", "Search YouTube or the native Spotify app; does not start playback."),
    ToolSpec("select", "desktop", "Activate a currently visible enabled control after checking its identity."),
    ToolSpec("fill_text", "desktop", "Replace a named visible Edit field with exact content; does not submit."),
    ToolSpec("scroll", "desktop", "Scroll the current accessible window one page up, down, left or right."),
    ToolSpec("shortcut", "desktop", "Press an allowed shortcut in the current checked window."),
    ToolSpec("open_menu", "desktop", "Expand or invoke a named visible menu or dropdown, then observe its items."),
    ToolSpec("handle_dialog", "desktop", "Choose a named visible dialog button; never guess or approve deletion."),
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
        from .toolkits import relevant
        return [{"action": spec.name, "backend": spec.backend,
                 "description": spec.description, "approval": spec.approval}
                for spec in self.specs.values() if goal is None or spec.name not in KIT_TOOLS or relevant(spec.name, goal)]

    def execute(self, step, cancelled, activate=None):
        name = step.get("action")
        if name not in self.specs:
            raise ValueError("Unsupported tool: " + str(name))
        if cancelled():
            raise ValueError("Task cancelled before tool execution.")
        spec = self.specs[name]
        validate_desktop_step(step)
        self.actions.report("tool", spec.backend + ": " + name + " " + str(step.get("value", "")))
        if name in KIT_TOOLS:
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
            elif name == "media_search":
                command = Command(name, value, step["platform"])
            else:
                command = Command(name, value, step.get("browser", "chrome")
                                  if name in {"browse", "browser_search"} else "")
            evidence = self.actions.execute(command, cancelled)
        if cancelled():
            raise ValueError("Task cancelled after tool execution. Check the last action before repeating it.")
        return ToolResult(name, "spotify" if name == "media_search" and step.get("platform") == "spotify" else spec.backend,
                          str(evidence or "Action attempted; result needs verification."))
