"""Bounded plan/observe/decide/act loop using three local models."""
from difflib import SequenceMatcher
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time

from .commands import Command
from .names import common
from .task_state import TaskState
from .task_recovery import TaskFailure, action_key
from .tools import TOOL_NAMES, ToolRegistry
from .desktop_actions import CONTROL_ACTIONS, validate_desktop_step, explicit_desktop_plan
from .task_graph import validate_dependencies

ALLOWED = set(TOOL_NAMES)
SENSITIVE = re.compile(r"\b(delete|remove|erase|uninstall|send|submit|publish|post|purchase|buy|pay|checkout|upload|transfer|permission|administrator|terminal|powershell|command prompt)\b", re.I)


def validate_plan(plan, completed=()):
    if not isinstance(plan, dict) or not isinstance(plan.get("steps"), list):
        raise ValueError("Planner returned an invalid plan.")
    if plan.get("question"):
        raise ValueError(str(plan["question"])[:500])
    steps = plan["steps"]
    if not 1 <= len(steps) <= 6:
        raise ValueError("The plan must have one to six steps. Please narrow the task.")
    for step in steps:
        if (not isinstance(step, dict) or step.get("action") not in ALLOWED
                or not isinstance(step.get("value"), str) or not 0 < len(step["value"]) <= 500
                or not isinstance(step.get("expected"), str) or not step["expected"]):
            raise ValueError("The planner proposed an unsupported step.")
        validate_desktop_step(step)
        from .toolkits import validate_step
        validate_step(step)
        if step["action"] in CONTROL_ACTIONS | {"open"} and SENSITIVE.search(step["value"]):
            raise ValueError("That step requires an explicit direct command; the automatic plan was stopped.")
        if step["action"] in {"browse", "browser_search", "media_search"} and step.get("browser", "chrome") not in {"chrome", "edge", "firefox", "google chrome"}:
            raise ValueError("Planner named an unsupported browser.")
        if step["action"] in {"create_file", "modify_file", "delete_file"}:
            if not isinstance(step.get("folder"), str) or not step["folder"].strip():
                raise ValueError("A file task needs an explicit folder.")
            if step["action"] != "delete_file" and (not isinstance(step.get("content"), str) or len(step["content"]) > 10000):
                raise ValueError("A file edit needs exact content (up to 10,000 characters).")
            if step["action"] == "modify_file" and not isinstance(step.get("find", ""), str):
                raise ValueError("A file edit needs exact text to replace or an explicit full overwrite.")
            if step["action"] == "modify_file" and not step.get("find") and not step.get("content"):
                raise ValueError("The file edit omitted both the text to find and the new content.")
        if step["action"] == "media_search" and step.get("platform") not in {"youtube", "spotify"}:
            raise ValueError("A music task needs YouTube or Spotify.")
    return validate_dependencies(steps, completed)


def normalize_plan(steps, goal):
    """Remove known redundant opens and complete an explicit music request safely."""
    normalized = []
    for index, step in enumerate(steps):
        if step["action"] in {"create_file", "modify_file"} and isinstance(step.get("content"), str):
            content = step["content"]
            trimmed = content.rstrip("\r\n")
            if trimmed and trimmed != content and trimmed.casefold() in goal.casefold():
                step = {**step, "content": trimmed}
        next_step = steps[index + 1] if index + 1 < len(steps) else None
        value = common(step["value"])
        if step["action"] == "open" and next_step and next_step["action"] in {"browse", "browser_search", "media_search"} \
                and value in {"chrome", "edge", "firefox"}:
            continue  # The next action launches its browser itself.
        if step["action"] == "open" and value in {"here", "this folder", "current folder", "the open folder"} \
                and any(s["action"] == "create_file" and common(s.get("folder", "")) == value for s in steps):
            continue  # The selected Explorer folder is already open.
        normalized.append(step)
    if re.search(r"\b(?:play|put on|start playing)\b", goal, re.I) and not any(s["action"] == "select" for s in normalized):
        media = next((s for s in normalized if s["action"] == "media_search"), None)
        if media and len(normalized) < 6:
            normalized.append({"action": "select", "value": media["value"] + " result", "browser": media["browser"],
                               "expected": "Music result opened", "folder": "", "content": "", "platform": ""})
    return normalized


def spotify_media_plan(goal):
    """Use the user's exact search words; a small model need not invent media steps."""
    match = re.fullmatch(r"(?:play|put on|start playing) (.+?) (?:on|from|in|using) spotify", goal.strip(), re.I)
    opening = False
    if not match:
        match = re.fullmatch(r"(?:open|show) playlist (.+?) (?:on|in) spotify", goal.strip(), re.I)
        opening = True
        if not match:
            return None
    query = match[1].strip()
    if not query:
        return None
    return {"steps": [
        {"action": "media_search", "value": ("playlist " + query) if opening else query, "browser": "chrome", "expected": "Spotify search results for " + query,
         "folder": "", "content": "", "platform": "spotify"},
        {"action": "select", "value": ("playlist " + query) if opening else query, "browser": "chrome", "expected": "Playlist opened in Spotify" if opening else "Selected music is playing in Spotify",
         "folder": "", "content": "", "platform": ""},
    ]}


def youtube_search_plan(goal):
    """Search the exact requested topic, then select a visible video by position."""
    match = re.fullmatch(
        r"(?:open|launch) (?:the )?youtube(?: in (chrome|edge|firefox))? and "
        r"search(?: for)? (.+?) and (?:play|open|select) (?:the )?"
        r"(first|second|third|[1-9](?:st|nd|rd|th)?) video[.!?]*", goal.strip(), re.I)
    if not match:
        return None
    browser, query, ordinal = match.groups()
    number = {"first": 1, "second": 2, "third": 3}.get(ordinal.lower())
    if number is None:
        number = int(ordinal[0])
    return {"steps": [
        {"action": "media_search", "value": query.strip(), "platform": "youtube",
         "browser": browser or "chrome", "expected": "YouTube search results for " + query.strip()},
        {"action": "select", "value": ordinal + " video", "position": number,
         "category": "video", "expected": "Requested video opened and playback controls visible"}]}


def explicit_app_launch_plan(goal, apps):
    """Launch an explicitly named configured app before planning its workflow."""
    match = re.fullmatch(r"(?:open|launch|start) (?:the )?(.+?)(?: app)? and "
                         r"(?:search|find|click|select|choose|play|pause|create|make|modify|edit|type|write|fill|scroll|press|do|add|save)\b.+", goal.strip(), re.I)
    if not match:
        return None
    from .names import rank_spelling
    names = rank_spelling(match[1], apps)
    if len(names) != 1:
        return None
    return {"steps": [{"action": "open", "value": names[0], "browser": "chrome",
                       "expected": names[0] + " window visible", "folder": "", "content": "", "platform": ""}]}


def explicit_file_plan(goal):
    """Preserve exact words for simple file requests instead of asking a model to copy them."""
    from .commands import filename
    goal = goal.strip()
    delete = re.fullmatch(r"(?:delete|remove)(?: the)? file (.+?) (?:in|from) (?:the )?(.+?)\.?", goal, re.I)
    if delete:
        return {"steps": [{"action": "delete_file", "value": filename(delete[1]),
            "folder": delete[2].strip(), "expected": "Named file moved to Recycle Bin after approval"}]}
    edit = re.fullmatch(r"(?:modify|edit)(?: the)? file (.+?) in (?:the )?(.+?)\s*:\s*replace (.+?) with (.+)", goal, re.I)
    if edit:
        return {"steps": [{"action": "modify_file", "value": filename(edit[1]), "folder": edit[2].strip(),
            "find": edit[3], "content": edit[4], "expected": "Exact replacement written to the file"}]}
    overwrite = re.fullmatch(r"(?:overwrite|replace entire)(?: the)? file (.+?) in (?:the )?(.+?) with (?:content )?(.+)", goal, re.I)
    if overwrite:
        return {"steps": [{"action": "modify_file", "value": filename(overwrite[1]), "folder": overwrite[2].strip(),
            "find": "", "content": overwrite[3], "expected": "Complete file content replaced"}]}
    return None


def explicit_command_plan(goal):
    match = re.fullmatch(r"(?:run|execute) command (.+)", goal.strip(), re.I)
    if match:
        return {"steps": [{"action": "run_command", "value": match[1],
            "expected": "Approved command finished with exit code zero"}]}
    return None


class BrainClient:
    def __init__(self, base, options):
        self.base, self.options = Path(base), options
        self.process = None
        self.responses = None
        self.log = None

    def close(self):
        process, self.process = self.process, None
        if process:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            process.stdin.close()
            process.stdout.close()
        if self.log:
            self.log.close()
            self.log = None

    def request(self, operation, cancelled, **data):
        for attempt in range(2):
            try:
                return self._request_once(operation, cancelled, **data)
            except (OSError, ValueError) as exc:
                retryable = isinstance(exc, OSError) or "Brain worker stopped" in str(exc)
                if attempt or not retryable or cancelled():
                    raise
                self.close()
                from .recovery import record
                record(self.base, "Brain inference worker stopped; restarted and retried inference only, without replaying actions.")

    def _request_once(self, operation, cancelled, **data):
        if cancelled():
            raise ValueError("Task cancelled.")
        if self.process is None or self.process.poll() is not None:
            self.close()
            executable = self.base / ".venv-brain/Scripts/python.exe"
            if not executable.is_file() or not (self.base / "models/laya/model.safetensors").is_file():
                raise ValueError("Brain models are not ready. Run Setup Jarvis Brain.cmd, then restart Jarvis.")
            self.log = (self.base / "brain-worker.log").open("a", encoding="utf-8")
            self.process = subprocess.Popen([str(executable), "-u", "-m", "jarvis.brain_worker"],
                cwd=self.base, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.log,
                encoding="utf-8", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            responses = self.responses = queue.Queue()
            process = self.process
            def read():
                try:
                    for line in process.stdout:
                        responses.put(line)
                except (OSError, ValueError):
                    pass
                finally:
                    responses.put(None)
            threading.Thread(target=read, daemon=True).start()
        self.process.stdin.write(json.dumps({"operation": operation, "options": self.options, **data}) + "\n")
        self.process.stdin.flush()
        deadline = time.monotonic() + 150
        try:
            while True:
                if cancelled():
                    raise ValueError("Task cancelled.")
                if time.monotonic() > deadline:
                    raise ValueError("The local brain timed out. Try a shorter task.")
                try:
                    line = self.responses.get(timeout=.1)
                except queue.Empty:
                    continue
                if line is None:
                    raise ValueError("Brain worker stopped. See brain-worker.log.")
                result = json.loads(line)
                if result.get("error"):
                    raise ValueError(result["error"])
                return result["result"]
        except Exception:
            self.close()
            raise


class Brain:
    def __init__(self, actions, base, options):
        self.actions, self.options = actions, options
        self.client = BrainClient(base, options)

    def checkpoint(self, stage, **details):
        state = getattr(self.actions, "task_state", None)
        if isinstance(state, TaskState):
            state.checkpoint(stage, **details)

    def save_plan(self, remaining, completed, reason):
        state = getattr(self.actions, "task_state", None)
        if isinstance(state, TaskState):
            state.update_plan(remaining, completed, reason)

    def blocked(self, reason):
        if self.options.get("task_recovery", False):
            raise TaskFailure(reason)
        raise ValueError(reason)

    def dispatch(self, step, cancelled, activate=None):
        try:
            return ToolRegistry(self.actions).execute(step, cancelled, activate=activate)
        except Exception as exc:
            if cancelled() or not self.options.get("task_recovery", False):
                raise
            # A tool exception cannot establish whether the external effect happened.
            raise TaskFailure(str(exc), attempted=True) from exc

    def recover_task(self, goal, step, failure, failures, completed, remaining, apps, number, cancelled):
        row = {**step, "reason": str(failure)[:500], "attempted": failure.attempted,
               "verified": False, "outcome": "uncertain" if failure.attempted else "not_executed"}
        failures.append(row)
        state = getattr(self.actions, "task_state", None)
        if isinstance(state, TaskState):
            state.record_failure(row)
        self.checkpoint("action_failed", action=step["action"], target=step["value"], evidence=str(failure))
        self.actions.report("repair", "Task failure recorded: " + str(failure)[:300])
        if cancelled():
            raise ValueError("Task cancelled before recovery.")
        if failure.attempted:
            raise ValueError("Task paused: the last action may have taken effect; inspect it before continuing. " + str(failure))
        if len(failures) > 2 or number >= 6:
            raise ValueError("Task paused: recovery limit reached; unsuccessful actions were not repeated.")
        try:
            handle, snapshot = self.observe(cancelled)
            context = self.screen(snapshot)
            captured = None
            if self.options.get("screen_aware", False):
                captured = self.visual_screen(handle, snapshot, cancelled)
                observation = self.client.request("visual", cancelled, goal=goal, step=None,
                    completed=completed, previous=None, screen=captured)
                captured["summary"] = str(observation.get("summary", ""))[:1000]
                context = self.visual_context(captured)
            steps = self.revise_plan(goal, context, apps, completed, remaining, number, cancelled, failures, recovering=True)
            self.validate_remaining(steps, goal)
            if steps and steps[0]["action"] in {"create_file", "modify_file", "delete_file", "run_command", "close_app"}:
                raise ValueError("Recovery requires a navigation approach before any file, terminal or close action.")
            self.actions.report("repair", "A different approach was planned from the current screen.")
            return steps, snapshot, captured
        except (ValueError, OSError) as exc:
            raise ValueError("Task paused: no safe alternative recovery plan. " + str(exc)) from exc

    def revise_plan(self, goal, screen, apps, completed, remaining, number, cancelled, failures=None, recovering=False):
        if cancelled():
            raise ValueError("Task cancelled before replanning.")
        try:
            revised = self.client.request("replan", cancelled, goal=goal, screen=screen,
                apps=apps, completed=completed, remaining=remaining,
                last_result=(failures[-1] if failures and (recovering or not completed) else completed[-1]), failures=failures or [],
                steps_left=6-number, tools=ToolRegistry(self.actions).catalog(goal))
            if cancelled():
                raise ValueError("Task cancelled during replanning.")
            if not isinstance(revised, dict) or not isinstance(revised.get("done"), bool):
                raise ValueError("Adaptive planner returned an invalid completion status.")
            if revised.get("question"):
                raise ValueError(str(revised["question"])[:500])
            if revised["done"]:
                if revised.get("steps") != []:
                    raise ValueError("Adaptive planner marked done but still proposed actions.")
                steps = []
            else:
                steps = normalize_plan(validate_plan(revised, completed), goal)
                if not steps:
                    raise ValueError("Adaptive planner omitted the remaining tasks.")
            # Compare full tool arguments; entering different text is a different task.
            fingerprints = {action_key(item) for item in completed}
            if any(item["action"] != "scroll" and action_key(item) in fingerprints for item in steps):
                raise ValueError("Adaptive plan repeated an action already completed.")
            if len(steps) > 6-number:
                raise ValueError("Adaptive plan exceeds the remaining action budget.")
            forbidden = {action_key(item) for item in failures or []}
            if any(action_key(item) in forbidden for item in steps):
                raise ValueError("Recovery plan repeated an unsuccessful action.")
            self.save_plan(steps, completed, revised.get("reason", "Updated from the verified result"))
            self.actions.report("plan", "Revised remaining tasks: " + (
                " → ".join(item["action"] + " " + item["value"] for item in steps) or "Goal ready for final verification"))
            return steps
        except (ValueError, OSError) as exc:
            self.checkpoint("replan_paused", evidence=str(exc))
            raise ValueError("Task paused after the last verified action: " + str(exc)) from exc

    def validate_remaining(self, steps, goal):
        low_goal = goal.casefold()
        for pending in steps:
            from .toolkits import TOOLS as toolkit_tools
            if pending["action"] in toolkit_tools and toolkit_tools[pending["action"]][3]:
                intent = {"github_add_file": r"\b(?:create|add|update|commit|push)\b",
                          "github_delete_file": r"\b(?:delete|remove)\b", "calendar_create": r"\b(?:create|add|schedule)\b",
                          "calendar_delete": r"\b(?:delete|remove|cancel)\b", "jira_create": r"\b(?:create|add)\b",
                          "jira_edit": r"\b(?:edit|update|modify)\b"}.get(pending["action"], r"\b(?:send|post|publish|tweet)\b")
                if not re.search(intent, low_goal):
                    raise ValueError("External toolkit write was not explicitly requested.")
            if pending["action"] == "append_file":
                if not re.search(r"\bappend\b", low_goal) or pending.get("content", "").casefold() not in low_goal:
                    raise ValueError("Append needs the user's explicit exact text.")
            if pending["action"] in {"create_file", "modify_file", "delete_file"}:
                if pending["action"] == "delete_file" and not re.search(r"\b(?:delete|remove)\b", low_goal):
                    raise ValueError("File deletion was not requested.")
                if common(pending["value"]) not in common(goal):
                    raise ValueError("The new plan chose a filename you did not name.")
                folder = common(pending["folder"])
                if folder not in common(goal) and not (folder in {"here", "this folder", "current folder", "the open folder", "selected folder"}
                    and any(word in common(goal) for word in ("here", "this folder", "current folder", "open folder", "selected folder"))):
                    raise ValueError("The new plan chose a folder you did not identify.")
                if pending["action"] != "delete_file" and pending["content"] and pending["content"].casefold() not in low_goal:
                    raise ValueError("The new plan changed the words to write.")
                if pending["action"] == "modify_file":
                    if not pending.get("find") and not re.search(r"\b(?:overwrite|replace entire|replace whole)\b", low_goal):
                        raise ValueError("The new plan omitted the old text and would overwrite the whole file.")
                    if pending.get("find") and pending["find"].casefold() not in low_goal:
                        raise ValueError("The new plan invented text to replace.")
            if pending["action"] == "run_command" and not re.search(r"\b(?:run|execute)\b.*\b(?:command|cmd|script|test)\b", low_goal):
                raise ValueError("Running a command was not explicitly requested.")
            if pending["action"] == "run_command" and pending["value"].casefold() not in low_goal:
                raise ValueError("The new plan invented a command that you did not dictate.")
            if pending["action"] == "media_search" and pending["platform"] not in low_goal:
                raise ValueError("The new plan changed the music service.")

    def observe(self, cancelled):
        ui = self.actions._ui()
        handle = ui._handle()
        snapshot = ui.runner({"operation": "list", "handle": handle, "owner_pid": os.getpid()}, cancelled)
        return handle, snapshot

    def observe_after_action(self, before, action, cancelled):
        """Get a fresh destination state, allowing a short UI transition to finish.

        A missing or unchanged accessibility tree can still be checked by vision.
        No action is repeated during this wait.
        """
        file_action = action in {"create_file", "modify_file", "delete_file", "run_command"}
        attempts = 1 if file_action else 8
        last_error = None
        for attempt in range(attempts):
            if cancelled():
                raise ValueError("Task cancelled after action; inspect the result before retrying.")
            if not file_action:
                time.sleep(.2)
            try:
                handle, snapshot = self.observe(cancelled)
            except ValueError as exc:
                last_error = exc
                continue
            last_error = None
            if file_action or not before or (handle, snapshot.get("title"), snapshot.get("signature")) != (
                    before[0], before[1].get("title"), before[1].get("signature")):
                return handle, snapshot
            # A canvas may change without a UIA signature change; return the
            # freshest state after the bounded wait so vision can judge it.
        if last_error and not file_action:
            raise ValueError("Could not observe the screen after acting: " + str(last_error)) from last_error
        if file_action:
            return 0, {}
        return handle, snapshot

    @staticmethod
    def screen(snapshot):
        return {"title": snapshot.get("title", "")[:200], "is_dialog": snapshot.get("is_dialog", False),
                "fields": [c["name"] for c in snapshot.get("controls", []) if c["role"] == "Edit" and not c.get("password")][:20],
                "controls": [c["name"][:80] for c in snapshot.get("controls", [])[:40]]}

    def visual_screen(self, handle, snapshot, cancelled):
        """Capture the actual destination window, with Jarvis hidden during capture."""
        self.actions.report("screen_capture", "")
        process = None
        try:
            time.sleep(.3)
            if cancelled():
                raise ValueError("Task cancelled.")
            process = subprocess.Popen([sys.executable, "-m", "jarvis.screen_worker"],
                cwd=self.client.base, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, encoding="utf-8",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            deadline = time.monotonic() + 20
            payload = json.dumps({"handle": handle})
            first = True
            while True:
                if cancelled():
                    raise ValueError("Task cancelled.")
                if time.monotonic() >= deadline:
                    raise TimeoutError("Screen capture timed out.")
                try:
                    output, error = process.communicate(input=payload if first else None, timeout=.2)
                    break
                except subprocess.TimeoutExpired:
                    first = False
            if cancelled():
                raise ValueError("Task cancelled.")
            if process.returncode:
                raise ValueError(error[-500:] or "Screen capture failed.")
            captured = json.loads(output)
            if captured.get("error") or not captured.get("image"):
                raise ValueError(captured.get("error", "Screen capture returned no image."))
            captured["controls"] = self.screen(snapshot)["controls"]
            captured["is_dialog"] = snapshot.get("is_dialog", False)
            captured["fields"] = self.screen(snapshot)["fields"]
            return captured
        finally:
            if process and process.poll() is None:
                process.kill()
                process.communicate()
            self.actions.report("screen_capture_done", "")

    @staticmethod
    def visual_context(observation):
        return {"title": observation.get("title", ""), "ocr": observation.get("ocr", "")[:2500],
                "visual": observation.get("summary", "")[:1000],
                "is_dialog": observation.get("is_dialog", False),
                "fields": observation.get("fields", []),
                "controls": observation.get("controls", [])}

    def run(self, goal, cancelled):
        if not self.options.get("enabled", False):
            raise ValueError("Autonomous brain is disabled. Enable brain.enabled after Setup Jarvis Brain.cmd succeeds.")
        if not goal.strip() or len(goal) > 1500:
            raise ValueError("Use a short, specific task.")
        from .coder import Coder, create_python_from_goal, python_file_request, workspace_coding_request
        from .commands import normalize_spoken_code_request
        spoken_goal = goal
        goal = normalize_spoken_code_request(goal)
        state = getattr(self.actions, "task_state", None)
        resumed = getattr(self.actions, "resume_source", None)
        prior = resumed if isinstance(resumed, dict) else (state.previous(spoken_goal, "task") if isinstance(state, TaskState) else None)
        inferred_python_name = python_file_request(goal)
        if inferred_python_name:
            return create_python_from_goal(self.actions, self.client, goal, inferred_python_name, cancelled)
        if workspace_coding_request(goal):
            selected_folder = prior["project"] if prior and prior.get("project") else self.actions._task_folder("this folder", cancelled)
            return Coder(self.actions, self.client).run(selected_folder, goal, cancelled, selected=True)
        fixed_media_plan = spotify_media_plan(goal) or youtube_search_plan(goal)
        initial_launch_plan = explicit_app_launch_plan(goal, self.actions.apps) if self.options.get("screen_aware", False) else None
        has_progress = bool(prior and ((prior.get("plan") or {}).get("completed") or
                           any(item.get("stage") == "verified" for item in prior.get("checkpoints", []))))
        if has_progress:
            fixed_media_plan = initial_launch_plan = None
        resume_completed = prior.get("plan", {}).get("completed", []) if has_progress and prior.get("plan") else []
        try:
            handle, snapshot = self.observe(cancelled)
        except ValueError:
            handle, snapshot = 0, {}
        screen_aware = self.options.get("screen_aware", False)
        adaptive = self.options.get("adaptive_planning", False)
        recovery_enabled = self.options.get("task_recovery", False)
        visual = None
        if screen_aware and (fixed_media_plan or initial_launch_plan):
            captured = {"title": snapshot.get("title", "Desktop"), "ocr": "", "summary": "",
                        "controls": snapshot.get("controls", [])}
        elif screen_aware:
            captured = self.visual_screen(handle, snapshot, cancelled)
            visual = self.client.request("visual", cancelled, goal=goal, step=None, completed=[],
                previous=None, screen=captured)
            if not isinstance(visual.get("summary"), str):
                raise ValueError("The screen model returned an invalid observation.")
            captured["summary"] = visual["summary"]
            self.actions.report("screen", "Saw " + captured["title"] + ": " + visual["summary"][:200])
        self.actions.report("brain", "Using direct media search plan" if fixed_media_plan else
                            "Opening requested app before planning remaining steps" if initial_launch_plan else
                            "Planning with " + self.options["planner"])
        words = set(common(goal).split())
        apps = sorted(self.actions.apps, key=lambda name: (bool(words & set(common(name).split())),
            name in {"chrome", "notepad", "file explorer", "edge", "calculator"}), reverse=True)[:80]
        exact_single_request = None if has_progress else (explicit_file_plan(goal) or explicit_command_plan(goal) or explicit_desktop_plan(goal))
        plan = exact_single_request or fixed_media_plan or initial_launch_plan or self.client.request("plan", cancelled, goal=goal,
            screen=self.visual_context(captured) if screen_aware else self.screen(snapshot), apps=apps,
            completed=resume_completed, prior_task=prior, tools=ToolRegistry(self.actions).catalog(goal),
            experience=state.recall(spoken_goal) if isinstance(state, TaskState) else [])
        if plan.get("model_used") and plan["model_used"] != self.options["planner"]:
            self.actions.report("brain", "Using installed fallback " + plan["model_used"] + "; preferred model is not installed yet")
        steps = normalize_plan(validate_plan(plan, resume_completed), goal)
        if resume_completed and any(action_key(step) in {action_key(item) for item in resume_completed} for step in steps):
            raise ValueError("Task retained: the resume plan repeated an already completed action.")
        coverage = steps + resume_completed
        self.checkpoint("planned", evidence="; ".join(s["action"] + " " + s["value"] for s in steps))
        low_goal = goal.casefold()
        if not initial_launch_plan and re.search(r"\b(?:create|make)\b.*\bfile\b", low_goal) and not any(s["action"] == "create_file" for s in coverage):
            raise ValueError("The plan omitted the requested file creation. Say the folder, filename and content again.")
        if not initial_launch_plan and re.search(r"\b(?:play|put on|start playing)\b", low_goal) and not any(s["action"] == "select" for s in coverage):
            raise ValueError("The plan found music but did not select anything to play. Name a song or playlist.")
        if not initial_launch_plan and re.search(r"\b(?:play|put on|start playing)\b.*\b(?:spotify|youtube)\b", low_goal) and not any(s["action"] == "media_search" for s in coverage):
            raise ValueError("The plan omitted searching the requested music service.")
        if not initial_launch_plan and re.search(r"\b(?:close|quit|exit)\b", low_goal) and not any(s["action"] == "close_app" for s in coverage):
            raise ValueError("The plan omitted closing the requested application.")
        if not initial_launch_plan and re.search(r"\b(?:delete|remove)\b.*\bfile\b", low_goal) and not any(s["action"] == "delete_file" for s in coverage):
            raise ValueError("The plan omitted the requested file deletion.")
        if not initial_launch_plan and re.search(r"\b(?:modify|edit|replace|overwrite)\b.*\bfile\b", low_goal) and not any(s["action"] == "modify_file" for s in coverage):
            raise ValueError("The plan omitted the requested file edit.")
        for step in steps:
            if step["action"] in {"create_file", "modify_file", "delete_file"}:
                if common(step["value"]) not in common(goal):
                    raise ValueError("The plan chose a filename you did not name.")
                content = step.get("content", "").strip()
                folder_name = common(step["folder"])
                if folder_name in {"here", "this folder", "current folder", "the open folder", "selected folder"}:
                    if not any(phrase in low_goal for phrase in ("here", "this folder", "current folder", "open folder", "selected folder")):
                        raise ValueError("The plan chose a folder you did not identify.")
                elif folder_name not in common(goal):
                    raise ValueError("The plan chose a folder you did not name.")
                if step["action"] != "delete_file" and content and content.casefold() not in low_goal:
                    raise ValueError("The plan changed the words to write. Please dictate the exact file contents.")
                if step["action"] == "create_file" and not content and re.search(r"\b(?:write|containing|with content)\b", low_goal):
                    raise ValueError("The plan omitted the words to write.")
                if step["action"] == "delete_file" and not re.search(r"\b(?:delete|remove)\b", low_goal):
                    raise ValueError("File deletion was not requested.")
                if step["action"] == "modify_file" and step.get("find") and step["find"].casefold() not in low_goal:
                    raise ValueError("The plan invented text to replace.")
                if step["action"] == "modify_file" and not step.get("find") and not re.search(r"\b(?:overwrite|replace entire|replace whole)\b", low_goal):
                    raise ValueError("The plan omitted the old text and would overwrite the whole file.")
            if step["action"] == "run_command" and not re.search(r"\b(?:run|execute)\b.*\b(?:command|cmd|script|test)\b", low_goal):
                raise ValueError("Running a command was not explicitly requested.")
            if step["action"] == "run_command" and step["value"].casefold() not in low_goal:
                raise ValueError("The plan invented a command that you did not dictate.")
            if step["action"] == "media_search" and step["platform"] not in low_goal:
                raise ValueError("The plan changed the music service.")
        self.actions.report("plan", " → ".join(s["action"] + " " + s["value"] for s in steps))
        completed = list(resume_completed)
        self.save_plan(steps, completed, "Initial goal breakdown")
        executed_steps = []
        number = 0
        failures = list(prior.get("failures", [])) if prior and recovery_enabled else []
        while steps and number < 6:
            attempted = result_verified = False
            try:
                number += 1
                step = steps[0]
                validate_dependencies([step], completed)
                if recovery_enabled and action_key(step) in {action_key(item) for item in failures}:
                    self.blocked("The plan repeated an unsuccessful action.")
                self.checkpoint("observing", action=step["action"], target=step["value"])
                if cancelled():
                    raise ValueError("Task cancelled.")
                try:
                    handle, snapshot = self.observe(cancelled)
                except ValueError:
                    if step["action"] in CONTROL_ACTIONS or step["action"] in {"shortcut", "scroll"}:
                        self.blocked("Could not observe the target before acting.")
                    handle, snapshot = None, {}
                step_screen = self.screen(snapshot)
                if screen_aware:
                    step_screen = {**self.visual_context(captured),
                        "title": step_screen["title"] or captured.get("title", ""),
                        "controls": step_screen["controls"] if snapshot else captured.get("controls", [])}
                candidates, suggestion, chosen = [], {}, None
                if step["action"] in CONTROL_ACTIONS:
                    from .ui_controls import matches, _category
                    controls = snapshot["controls"]
                    if step["action"] == "fill_text":
                        controls = [c for c in controls if c["role"] == "Edit" and not c.get("password")]
                        if step["content"].casefold() not in low_goal:
                            raise ValueError("Text entry must use the exact text requested by the user.")
                    elif step["action"] == "open_menu":
                        controls = [c for c in controls if c["role"] in {"MenuItem", "Button", "SplitButton", "ComboBox"}]
                    elif step["action"] == "handle_dialog":
                        if not snapshot.get("is_dialog"):
                            self.blocked("No accessible modal dialog is active. Use select for a normal screen button.")
                        if re.search(r"\b(delete|remove|erase|recycle)\b", snapshot.get("title", ""), re.I):
                            raise ValueError("File deletion must use the named file tool and its approval dialog.")
                        controls = [c for c in controls if c["role"] == "Button"]
                    else:
                        controls = [c for c in controls if c["role"] not in {"Edit", "Pane", "Document"}]
                    if fixed_media_plan and step.get("position"):
                        visible = _category(controls, step["category"], snapshot.get("title", ""))
                        position = step["position"] - 1
                        if position >= len(visible):
                            self.blocked("Task paused: the requested video is not visible in the search results.")
                        matching = [visible[position]]
                    else:
                        matching = matches(controls, step["value"])
                    ordered = matching or sorted(controls, key=lambda c: SequenceMatcher(None, common(step["value"]), common(c["name"])).ratio(), reverse=True)
                    candidates = [{"key": f"c{i}", "name": c["name"], "role": c["role"], "context": c.get("context", "")} for i, c in enumerate(ordered[:8])]
                    if not candidates:
                        self.blocked("No visible choices. Open the target app or menu first.")
                    if len(matching) == 1:
                        suggestion = {"choice": "c0"}
                    else:
                        self.actions.report("brain", "Laya is comparing visible choices")
                        suggestion = self.client.request("choose", cancelled, target=step["value"], goal=goal,
                            screen=step_screen, candidates=candidates)
                if initial_launch_plan and not executed_steps and step["action"] == "open":
                    decision = {"approved": True, "choice": "", "reason": "Explicit configured app launch"}
                elif fixed_media_plan and step["action"] == "media_search":
                    decision = {"approved": True, "choice": "", "reason": "Explicit media search"}
                else:
                    self.actions.report("brain", "Checking step " + str(number) + " with " + self.options["decision"])
                    decision = self.client.request("decide", cancelled, goal=goal, step=step,
                        screen=step_screen, candidates=candidates, suggestion=suggestion)
                if cancelled():
                    raise ValueError("Task cancelled before action.")
                if decision.get("approved") is not True:
                    raise ValueError("Task paused: " + str(decision.get("reason", "No clear next action.")))
                if step["action"] in CONTROL_ACTIONS:
                    if decision.get("choice") != suggestion.get("choice"):
                        raise ValueError("Laya and the decision model disagree on the control. Say its name or list buttons to choose.")
                    index = next((i for i, c in enumerate(candidates) if c["key"] == decision.get("choice")), None)
                    if index is None:
                        raise ValueError("No unambiguous control selected. Say the option name.")
                    chosen = ordered[index]
                    if SENSITIVE.search(chosen["name"]):
                        raise ValueError("This control needs an explicit direct command.")
                    new_handle, fresh = self.observe(cancelled)
                    if new_handle != handle or fresh.get("context") != snapshot.get("context") or chosen not in fresh["controls"]:
                        self.blocked("The target changed during decision-making. Task stopped before clicking.")
                    self.checkpoint("acting", action=step["action"], target=chosen["name"],
                                    screen=step_screen.get("title"))
                    if step["action"] in {"select", "handle_dialog"}:
                        activate = lambda: self.actions._ui()._activate(handle, fresh, chosen, "select", cancelled)
                    else:
                        activate = lambda: self.actions._ui().runner({"operation": step["action"], "handle": handle,
                            "owner_pid": os.getpid(), "control": chosen, "content": step.get("content", "")}, cancelled)["message"]
                    attempted = True
                    result = self.dispatch(step, cancelled, activate=activate).evidence
                elif step["action"] in {"shortcut", "scroll"}:
                    new_handle, fresh = self.observe(cancelled)
                    if new_handle != handle or fresh.get("context") != snapshot.get("context") or fresh.get("signature") != snapshot.get("signature"):
                        self.blocked("The target changed before the desktop action.")
                    self.checkpoint("acting", action=step["action"], target=step["value"], screen=step_screen.get("title"))
                    attempted = True
                    result = self.dispatch(step, cancelled, activate=lambda:
                        self.actions._ui().runner({"operation": step["action"], "handle": handle,
                            "owner_pid": os.getpid(), "signature": fresh["signature"], "value": step["value"]}, cancelled)["message"]).evidence
                else:
                    self.checkpoint("acting", action=step["action"], target=step["value"],
                                    screen=step_screen.get("title"))
                    if step["action"] == "open":
                        from .names import rank
                        # Model-generated opens may launch configured apps or ordinary data files,
                        # never an arbitrary executable/script discovered in the file catalog.
                        if not rank(step["value"], self.actions.apps):
                            from .catalog import AmbiguousName
                            for kind in ("file", "folder"):
                                try:
                                    path = self.actions.catalog.resolve(step["value"], kind)
                                    candidates_paths = [path]
                                except AmbiguousName as exc:
                                    candidates_paths = exc.matches
                                except ValueError:
                                    continue
                                if any(Path(path).suffix.lower() in {".exe", ".com", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".py", ".msi", ".lnk", ".url"} for path in candidates_paths):
                                    raise ValueError("Opening scripts or executables requires a direct command, not an inferred plan.")
                    attempted = True
                    result = self.dispatch(step, cancelled).evidence
                    if self.actions.pending_open:
                        return "Task paused for your numbered choice. Resume with a new task after selecting it."
                if cancelled():
                    raise ValueError("Task cancelled. Check the last action before repeating it.")
                self.actions.report("action", result)
                recorded_result = ("Command exit code " + str(self.actions.last_command[1])
                                   if step["action"] == "run_command" and self.actions.last_command else result)
                self.checkpoint("action_attempted", action=step["action"], target=step["value"], evidence=recorded_result)
                # Every action is followed by a fresh observation before another is planned.
                # Waiting for a transition never repeats the action.
                try:
                    landed_handle, after = self.observe_after_action((handle, snapshot), step["action"], cancelled)
                except ValueError as exc:
                    if recovery_enabled:
                        raise TaskFailure("Task paused: action was attempted, but the new screen could not be observed. " + str(exc), attempted=True)
                    return "Task paused: action was attempted, but the new screen could not be observed. " + str(exc)
                self.checkpoint("observed", action=step["action"], target=step["value"],
                                screen=after.get("title", "Desktop"))
                if step["action"] == "run_command" and self.actions.last_command and self.actions.last_command[1] != 0:
                    if recovery_enabled:
                        raise TaskFailure("Task paused: the command exited with code " + str(self.actions.last_command[1]) + ". Check the command output.", attempted=True)
                    return "Task paused: the command exited with code " + str(self.actions.last_command[1]) + ". Check the command output."
                if step["action"] == "create_file":
                    created = self.actions.last_created
                    if not created or not created[0].is_file() or created[0].read_text(encoding="utf-8") != step["content"]:
                        raise ValueError("The file could not be verified after writing.")
                    verification = {"verified": True}
                elif step["action"] in {"modify_file", "delete_file", "run_command"}:
                    if step["action"] == "modify_file":
                        verified = bool(self.actions.last_modified and self.actions.last_modified.is_file())
                    elif step["action"] == "delete_file":
                        verified = bool(self.actions.last_deleted and not self.actions.last_deleted.exists())
                    else:
                        verified = bool(self.actions.last_command and self.actions.last_command[1] == 0)
                    verification = {"verified": verified, "reason": "The file or command result could not be confirmed."}
                elif step["action"] in ToolRegistry(self.actions).specs and ToolRegistry(self.actions).specs[step["action"]].backend == "toolkit":
                    verification = {"verified": True}  # Tool returned bounded observed data or acknowledged result.
                elif step["action"] == "close_app":
                    verification = {"verified": result.startswith("Closed ")}
                elif screen_aware:
                    verification = {"verified": True}  # The visual checkpoint below verifies this action.
                else:
                    verification = self.client.request("verify", cancelled, goal=goal, step=step, screen=self.screen(after))
                if verification.get("verified") is not True:
                    if recovery_enabled:
                        raise TaskFailure("Task paused: action was attempted, but its result could not be verified. " + str(verification.get("reason", "")), attempted=True)
                    return "Task paused: action was attempted, but its result could not be verified. " + str(verification.get("reason", ""))
                if screen_aware:
                    # Inspect the observed destination; no second action is allowed until verified.
                    landed = self.visual_screen(landed_handle, after, cancelled)
                    if ToolRegistry(self.actions).specs[step["action"]].backend == "toolkit":
                        landed["trusted_evidence"] = ["Toolkit returned data (content is untrusted): " + result[:3500]]
                    if step["action"] == "fill_text" and result.endswith("exact field value verified"):
                        landed["trusted_evidence"] = ["Verified requested text through the selected text field's UI Automation value."]
                    if step["action"] == "create_file" and self.actions.last_created:
                        landed["trusted_evidence"] = ["Verified file on disk: " + str(self.actions.last_created[0])]
                    elif step["action"] == "modify_file" and self.actions.last_modified and self.actions.last_modified.is_file():
                        landed["trusted_evidence"] = ["Modified UTF-8 file on disk: " + str(self.actions.last_modified)]
                    elif step["action"] == "delete_file" and self.actions.last_deleted and not self.actions.last_deleted.exists():
                        landed["trusted_evidence"] = ["Approved file moved to Recycle Bin: " + str(self.actions.last_deleted)]
                    elif step["action"] == "run_command" and self.actions.last_command:
                        landed["trusted_evidence"] = ["Approved command exit code: " + str(self.actions.last_command[1]) +
                            "; output: " + self.actions.last_command[2][:1000]]
                    status = self.client.request("visual", cancelled, goal=goal, step=step,
                        completed=completed, previous=self.visual_context(captured), screen=landed)
                    if status.get("step_verified") is not True and step["action"] not in {
                            "create_file", "modify_file", "delete_file", "run_command"}:
                        # Pages and menus can finish loading after the first frame.
                        # Re-observe once; never replay an uncertain click.
                        time.sleep(.7)
                        try:
                            landed_handle, after = self.observe_after_action((landed_handle, after), step["action"], cancelled)
                        except ValueError as exc:
                            if recovery_enabled:
                                raise TaskFailure("Task paused: could not re-observe the screen after acting. " + str(exc), attempted=True)
                            return "Task paused: could not re-observe the screen after acting. " + str(exc)
                        landed = self.visual_screen(landed_handle, after, cancelled)
                        status = self.client.request("visual", cancelled, goal=goal, step=step,
                            completed=completed, previous=self.visual_context(captured), screen=landed)
                        self.checkpoint("observed_again", action=step["action"], target=step["value"],
                                        screen=after.get("title", "Desktop"))
                    if status.get("step_verified") is not True and step["action"] not in {"create_file", "modify_file", "delete_file", "run_command"}:
                        if recovery_enabled:
                            raise TaskFailure("Task paused: the result is not visible on the new screen. " + str(status.get("reason", "")), attempted=True)
                        return "Task paused: the result is not visible on the new screen. " + str(status.get("reason", ""))
                    landed["summary"] = str(status.get("summary", ""))[:1000]
                    self.actions.report("screen", "Now on " + landed["title"] + ": " + landed["summary"][:200])
                    captured = landed
                completed.append({**step, "result": recorded_result[:500], "verified": True,
                    "screen": after.get("title", ""),
                    "observation": landed["summary"][:500] if screen_aware else self.screen(after)})
                result_verified = True
                self.actions.report("brain", "Verified step " + str(number))
                self.checkpoint("verified", action=step["action"], target=step["value"],
                                evidence=recorded_result, screen=after.get("title") if isinstance(after, dict) else None)
                executed_steps.append(step)
                self.save_plan(steps[1:], completed, "Last action verified; reviewing remaining tasks")
                if screen_aware or adaptive:
                    if (screen_aware and status.get("goal_done") is True and not (fixed_media_plan and len(steps) > 1)) or (exact_single_request and len(executed_steps) == 1):
                        self.save_plan([], completed, "Goal ready for final verification")
                        break
                    if number >= 6:
                        return "Task paused after six verified actions; the full goal is still not visible."
                    if fixed_media_plan and not adaptive:
                        steps = steps[1:]
                        if steps:
                            self.actions.report("plan", "Next from current screen: " + steps[0]["action"] + " " + steps[0]["value"])
                        continue
                    if adaptive:
                        steps = self.revise_plan(goal, self.visual_context(captured) if screen_aware else self.screen(after),
                            apps, completed, steps[1:], number, cancelled, failures=failures)
                        if not steps:
                            break
                    else:
                        revised = self.client.request("plan", cancelled, goal=goal,
                            screen=self.visual_context(captured), apps=apps, completed=completed,
                            tools=ToolRegistry(self.actions).catalog(goal))
                        steps = normalize_plan(validate_plan(revised, completed), goal)
                    self.checkpoint("replanned", evidence="; ".join(s["action"] + " " + s["value"] for s in steps))
                    self.validate_remaining(steps, goal)
                    if not adaptive and steps[0]["action"] != "scroll" and (steps[0]["action"], common(steps[0]["value"])) in {
                            (item["action"], common(item["value"])) for item in completed}:
                        return "Task paused: the next plan repeated an action already completed."
                    self.actions.report("plan", "Next from current screen: " + steps[0]["action"] + " " + steps[0]["value"])
                else:
                    steps = steps[1:]
            except TaskFailure as failure:
                steps, recovered_snapshot, recovered_capture = self.recover_task(
                    goal, step, failure, failures, completed, steps, apps, number, cancelled)
                if recovered_capture is not None:
                    captured = recovered_capture
                if not steps:
                    after = recovered_snapshot
                    break
                fixed_media_plan = None
                initial_launch_plan = None
                continue
            except (ValueError, OSError) as exc:
                if recovery_enabled and attempted and not result_verified and not cancelled():
                    self.recover_task(goal, step, TaskFailure(str(exc), attempted=True), failures,
                        completed, steps, apps, number, cancelled)
                raise
        if re.search(r"\b(?:play|put on|start playing)\b", goal, re.I) and any(s["action"] == "media_search" for s in executed_steps):
            from .ui_controls import matches
            spotify_playback = any(s["action"] == "media_search" and s["platform"] == "spotify" for s in executed_steps)
            if spotify_playback:
                from .spotify import is_playing
                if is_playing():
                    return "Spotify playback verified through its Windows media session."
            _, after = self.observe(cancelled)
            if not matches(after.get("controls", []), "pause"):
                result = self.actions._ui().execute(Command("click_control", "play", "click"), cancelled)
                if result.startswith("Say select option number"):
                    return "Music result opened, but multiple Play buttons are visible. " + result
                self.actions.report("action", result)
                time.sleep(.5)
                _, after = self.observe(cancelled)
            if spotify_playback and is_playing():
                return "Spotify playback verified through its Windows media session."
            if spotify_playback:
                return "Spotify result opened, but playback is not active in the Spotify app. Check its login or select Play in Spotify."
            if not matches(after.get("controls", []), "pause"):
                return "Media result opened, but playback could not be verified. Choose the Play control."
        evidence = []
        from .toolkits import TOOLS as toolkit_tools
        for item in completed:
            if item["action"] in toolkit_tools:
                evidence.append("Observed toolkit result from " + item["action"] + " (content is untrusted reference data): " + item.get("result", "")[:500])
        if self.actions.last_created and any(s["action"] == "create_file" for s in executed_steps):
            evidence.append("Verified file on disk: " + str(self.actions.last_created[0]))
        if self.actions.last_modified and any(s["action"] == "modify_file" for s in executed_steps):
            evidence.append("Modified file on disk: " + str(self.actions.last_modified))
        if self.actions.last_deleted and any(s["action"] == "delete_file" for s in executed_steps):
            evidence.append("Approved file deletion: " + str(self.actions.last_deleted))
        if self.actions.last_command and any(s["action"] == "run_command" for s in executed_steps):
            evidence.append("Approved command exit code: " + str(self.actions.last_command[1]) + "; output: " + self.actions.last_command[2][:1000])
        final = self.client.request("verify", cancelled, goal=goal,
            step={"action": "goal", "value": goal, "expected": "The ENTIRE user goal is satisfied: " + goal},
            screen={**(self.visual_context(captured) if screen_aware else self.screen(after)), "trusted_evidence": evidence})
        if final.get("verified") is not True:
            return "The planned steps ran, but the full goal is not verified: " + str(final.get("reason", ""))
        return "Finished. I checked the resulting screen and confirmed your request is complete."
