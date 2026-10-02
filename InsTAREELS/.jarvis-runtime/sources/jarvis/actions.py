import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time


class Desktop:
    """Unicode typing without touching the clipboard, bound to one window."""
    def __init__(self):
        if os.name != "nt":
            raise RuntimeError("Desktop actions require Windows.")
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self.user.GetForegroundWindow.restype = wintypes.HWND
        self.user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.user.IsWindow.argtypes = [wintypes.HWND]
        self.user.IsWindowVisible.argtypes = [wintypes.HWND]
        self.user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self.user.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.target = None

    def capture(self, expected=None):
        hwnd = self.user.GetForegroundWindow()
        pid = wintypes.DWORD()
        self.user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not hwnd or pid.value == os.getpid():
            raise ValueError("Click the destination app before dictating.")
        if expected:
            handle = self.kernel.OpenProcess(0x1000, False, pid.value)
            if not handle:
                raise ValueError("Could not verify destination app.")
            try:
                length = wintypes.DWORD(32768)
                path = ctypes.create_unicode_buffer(length.value)
                if not self.kernel.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(length)):
                    raise ValueError("Could not verify destination app.")
                if Path(path.value).name.lower() != expected.lower():
                    raise ValueError("Waiting for the requested app to take focus.")
            finally:
                self.kernel.CloseHandle(handle)
        self.target = hwnd

    def type(self, text, cancelled):
        if self.target is None:
            self.capture()

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

        class UNION(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]

        class INPUT(ctypes.Structure):
            _fields_ = [("type", wintypes.DWORD), ("u", UNION)]

        encoded = text.encode("utf-16-le")
        for offset in range(0, len(encoded), 2):
            if cancelled():
                return
            pointer = wintypes.POINT()
            if self.user.GetCursorPos(ctypes.byref(pointer)):
                right, bottom = self.user.GetSystemMetrics(0) - 1, self.user.GetSystemMetrics(1) - 1
                if pointer.x in (0, right) and pointer.y in (0, bottom):
                    raise ValueError("Typing halted: mouse is in a screen corner.")
            if self.user.GetForegroundWindow() != self.target:
                raise ValueError("Destination window changed. Dictation stopped; say stop dictation before restarting.")
            code = int.from_bytes(encoded[offset:offset + 2], "little")
            events = (INPUT * 2)(INPUT(1, UNION(ki=KEYBDINPUT(0, code, 4, 0, 0))), INPUT(1, UNION(ki=KEYBDINPUT(0, code, 6, 0, 0))))
            if self.user.SendInput(2, events, ctypes.sizeof(INPUT)) != 2:
                raise RuntimeError("Windows blocked typing. Select a normal, non-administrator app.")


class Actions:
    def __init__(self, config, base, report, desktop=None, recycler=None):
        self.base = Path(base).resolve()
        self.config = config
        self._discovered_tools = set()
        self.root = (Path(base) / config["files_root"]).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.apps = dict(config["apps"])
        from .catalog import Catalog
        self.catalog = Catalog(config, base)
        from .projects import Projects
        self.projects = Projects(base, config.get("project_roots", [r"D:\Phython Project", "D:\\"]))
        from .task_state import TaskState
        self.task_state = TaskState(base, read_only=bool(config.get('_ui_verification', False)))
        self.report = report
        self.desktop = desktop
        self.ui_controls = None
        self.browser_automation = None
        self.development_tools = None
        self.external_handle = lambda: 0
        self.pending_open = None
        self.pending_question = None
        from .ui_memory import UIMemory
        from .knowledge import Knowledge
        from .obsidian_memory import ObsidianMemory
        self.ui_memory = UIMemory(Path(base) / "ui_memory.json")
        self.memory = ObsidianMemory(base, config.get("memory"))
        self.catalog.memory = self.memory
        from .skill_memory import SkillMemory
        self.skills = SkillMemory(self.memory)
        self.memory.skills = self.skills
        self.task_state.on_finish = self.skills.safe_record
        interrupted = self.task_state.snapshot()
        if (interrupted and interrupted.get('status') == 'interrupted'
                and not config.get('_ui_verification', False)):
            self.skills.experiences.safe_record(interrupted)
        self._learning_local = threading.local()
        self.knowledge = Knowledge(config.get("knowledge", {}), report)
        self.knowledge.memory = self.memory
        self.knowledge.client.memory = self.memory
        from .quick_answers import QuickAnswers
        self.knowledge.quick = QuickAnswers(self.memory, config.get("weather", {}), settings=config)
        from .brain import Brain
        self.brain = Brain(self, base, config.get("brain", {}))
        self.task_active = False
        self.suggest_enabled = False
        self.suggest_until = 0
        self.dictation_active = False
        self.next_suggestion = 0
        self.recycler = recycler
        self.queue = queue.Queue(maxsize=128)
        self.generation = 0
        self.superseded_generations = set()
        self.closed = threading.Event()
        self.typing_failed = False
        self.open_target_pending = False
        self.last_created = None
        self.last_modified = None
        self.last_deleted = None
        self.last_command = None
        self.approval_handler = None
        self.gods_eye_view = None
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        try:
            self.skills.sync()
        except (OSError, ValueError) as exc:
            self.memory.error = "Skill sync: " + str(exc)
        from .memory_index import installed_windows_apps
        for app in installed_windows_apps():
            executable = app["locations"].get("executable")
            if executable and Path(executable).is_file():
                self.apps.setdefault(app["name"].casefold(), [executable])
        try:
            self.memory.start()
            self.memory.ensure_index(self.config)
        except OSError as exc:
            self.memory.error = str(exc)
            self.memory.enabled = False
            self.report("warning", "Obsidian memory could not start: " + str(exc))
        self.knowledge.start()
        self.thread.start()

    def cancel(self):
        self.generation += 1
        self.pending_open = None
        self.pending_question = None
        self.knowledge.cancel()
        self.projects.pending = None
        self.suggest_enabled = False
        self.dictation_active = False
        if self.ui_controls:
            self.ui_controls.clear_pending()
        self.report("question", "")

    def submit(self, command):
        from .island_choices import navigation, task_answer
        local = navigation(command.value) if command.kind in {'task', 'ask', 'play_media', 'open'} else None
        if local:
            self.report('island_navigation', local)
            return  # Games/view changes never supersede a background task.
        answer = task_answer(getattr(self, 'task_state', None), command.value) if command.kind in {'ask','task'} else None
        if answer is not None:
            self.report('answer', answer)
            return
        if command.kind == 'island_choice' and self.task_active:
            self.report('question', 'The task is still running. Select its option once it pauses for an answer.')
            return
        if command.kind=='spotify_control' and command.value=='status':
            self.report('island_navigation',('Music',''))
            return
        if command.kind=='spotify_control' and (self.task_active or command.extra=='island'):
            from .island_media import TRANSPORT
            if command.value in TRANSPORT:
                from .agent_events import check_policy
                try:
                    check_policy(self,'spotify_control')
                except ValueError as exc:
                    self.report('warning',str(exc))
                    return
                self.report('island_transport',command.value)
                return
        if command.kind in {'play_media','media_search'} and command.extra=='spotify':
            self.report('island_music_request',command.value)
        elif command.kind=='task':
            import re
            music = re.fullmatch(r'(?:play|put on|start playing) (.+?) (?:on|from|in|using) spotify',command.value,re.I)
            if music:
                self.report('island_music_request',music[1])
        self.memory.ensure_index(self.config)
        command = self._resolve_reply(command)
        if command.kind not in {"ask", "forget_chat", "clarification_blocked"}:
            self.memory.record("Jarvis request", f"{command.kind}: {command.value}")
        if self.task_active and command.kind == "resume_task":
            self.report("repair", "The current task is still running; it has not been forgotten.")
            return
        if command.kind == "ask":
            self.pending_open = None
            if self.ui_controls:
                self.ui_controls.clear_pending()
            self.report("question", "")
            self.knowledge.submit(command.value, command.extra == "web")
            return
        if command.kind == "forget_chat":
            self.knowledge.forget()
            self.report("answer", "Conversation history cleared.")
            return
        if command.kind == "sleep":
            self.cancel()
            self.report("state", "Listening for Jarvis Â· queued tasks cancelled")
            return
        if self.task_active:
            # Mutating task requests retain single-owner desktop execution; questions run independently.
            self.superseded_generations.add(self.generation)
            self.generation += 1
        try:
            self.queue.put_nowait((self.generation, command))
        except queue.Full:
            self.cancel()
            self.report("warning", "Action queue full; queued tasks cancelled.")

    def _resolve_reply(self, command, task_pending=None):
        """Route answers before the general-question worker can consume them."""
        from .commands import Command
        from .clarification import choice_index, short_reply
        if command.kind == 'island_choice':
            return command  # Validate again when the action worker executes it.
        groups = []
        if self.pending_open:
            groups.append((self.pending_open, 45, [c.value for c in self.pending_open["choices"]]))
        if self.projects.pending:
            groups.append((self.projects.pending, 180, [p.name for p in self.projects.pending["choices"]]))
        if self.ui_controls and self.ui_controls.pending:
            groups.append((self.ui_controls.pending, 45, [c["name"] for c in self.ui_controls.pending["choices"]]))
        for pending, lifetime, labels in ([] if task_pending else groups):
            if command.kind in {"task", "ask", "click_control", "choose_control", "select_context", "open", "open_folder", "open_project"}:
                index = choice_index(command.value, labels)
                if time.monotonic() - pending["time"] > lifetime:
                    if index is not None or command.kind in {"choose_control", "select_context"}:
                        self.report("question", "Those choices expired. Repeat the original request to get a fresh list.")
                        return Command("clarification_blocked", "Those choices expired. Repeat the original request.")
                    continue
                if command.kind == "select_context" and command.value.endswith(":option") and command.value.split(":")[0].isdigit():
                    index = int(command.value.split(":")[0]) - 1
                if index is not None:
                    if not 0 <= index < len(labels):
                        self.report("question", "That number is not in the list. Choose 1 through " + str(len(labels)) + ".")
                        return Command("clarification_blocked", "That number is not in the list; your choices are still available.")
                    return Command("choose_control", str(index + 1))
        pending = task_pending or self.pending_question
        if pending and time.monotonic() - pending["time"] > 180:
            self.pending_question = None
            if short_reply(command):
                self.report("question", "That task question expired. Repeat the original request.")
                return Command("clarification_blocked", "That task question expired. Repeat the original request.")
            pending = None
        if pending and short_reply(command):
            self.pending_question = None
            answer = command.value.strip()
            if command.kind == "confirm_suggestion" and answer == "no":
                return Command("sleep")
            source = pending["source"]
            blocker = self.task_state.resume_blocker(source)
            if blocker:
                self.report("question", "Task still paused: " + blocker)
                return Command("clarification_blocked", blocker)
            if pending["slot"] == "folder":
                # Resolve before generating a new plan; an answer never authorizes a guessed path.
                answer = answer.removeprefix("use ").removeprefix("in ")
                choices = pending.get("choices", [])
                index = choice_index(answer, choices) if choices else None
                if index is not None:
                    if not 0 <= index < len(choices):
                        self.pending_question = pending
                        self.report("question", pending["question"])
                        return Command("clarification_blocked", "That folder number is not in the list.")
                    answer = choices[index]
                try:
                    self.catalog.resolve(answer, "folder")
                except ValueError as exc:
                    self.pending_question = pending
                    self.report("question", "I could not resolve that folder. Say its full path. " + str(exc))
                    return Command("clarification_blocked", "Waiting for a valid destination folder.")
                goal = "In folder " + answer + ", " + pending["goal"]
            elif pending["slot"] == "python_purpose":
                goal = "Create a Python file with " + answer + " code. Original request: " + pending["goal"]
            else:
                goal = pending["goal"] + "\nClarification question: " + pending["question"] + "\nYour answer: " + answer
            return Command("clarified_task", goal, json.dumps(source))
        if command.kind not in {"choose_control", "confirm_suggestion"}:
            self.pending_question = None
        return command

    def close(self):
        self.skills.close()
        if self.development_tools:
            self.development_tools.close()
        self.cancel()
        if self.gods_eye_view:
            self.gods_eye_view.close()
        self.knowledge.close()
        self.memory.close()
        self.closed.set()
        if self.ui_controls:
            self.ui_controls.close()
        if self.browser_automation:
            self.browser_automation.close()
        if self.thread.is_alive():
            self.thread.join(timeout=3)
        self.brain.client.close()

    def _ui(self):
        if self.ui_controls is None:
            from .ui_controls import UIControls
            self.ui_controls = UIControls(self.desktop, memory=self.ui_memory,
                external_handle=lambda: self.external_handle())
        return self.ui_controls

    def ui_healthy(self):
        return self.ui_controls is None or self.ui_controls.healthy()

    def repair_ui(self):
        return not self.closed.is_set() and (self.ui_controls is None or self.ui_controls.repair())

    def _browser(self):
        if self.browser_automation is None:
            from .browser_automation import BrowserAutomation
            self.browser_automation = BrowserAutomation(self.apps, self.base)
        return self.browser_automation

    def browser_healthy(self):
        return self.browser_automation is None or self.browser_automation.healthy()

    def repair_browser(self):
        return not self.closed.is_set() and (self.browser_automation is None or self.browser_automation.repair())

    def _suggest(self):
        if self.projects.pending and time.monotonic() - self.projects.pending["time"] >= 180:
            self.projects.pending = None
        if (self.pending_open and time.monotonic() - self.pending_open["time"] < 45) or self.projects.pending:
            return
        if time.monotonic() > self.suggest_until:
            self.suggest_enabled = False
        if not self.suggest_enabled or self.dictation_active or time.monotonic() < self.next_suggestion:
            return
        self.next_suggestion = time.monotonic() + 10
        generation = self.generation
        cancelled = lambda: (self.closed.is_set() or generation != self.generation
                             or not self.suggest_enabled or not self.queue.empty())
        try:
            question = self._ui().suggest(cancelled)
            if question and not cancelled():
                self.report("question", question)
        except Exception:
            # A background suggestion must not interrupt explicit commands.
            self.next_suggestion = time.monotonic() + 30

    def _path(self, name):
        from .commands import filename
        if filename(name) != name:
            raise ValueError("Invalid filename")
        path = self.root / name
        if path.is_symlink() or path.resolve().parent != self.root:
            raise ValueError("File must be directly inside the configured JarvisFiles folder.")
        return path

    def _approve(self, kind, detail, cancelled):
        if self.approval_handler is None:
            raise ValueError("Open the Jarvis app to approve this action.")
        if cancelled() or not self.approval_handler(kind, detail, cancelled) or cancelled():
            raise ValueError("Action cancelled; approval was not given.")

    def _task_folder(self, folder_name, cancelled):
        from .clarification import TaskClarification
        from .catalog import AmbiguousName
        folder_name = folder_name.strip()
        if folder_name.casefold() in {"here", "this folder", "current folder", "the open folder", "selected folder"}:
            try:
                ui = self._ui()
                return ui.runner({"operation": "folder", "handle": ui._handle(), "owner_pid": os.getpid()}, cancelled)["folder"]
            except ValueError as exc:
                raise TaskClarification("Which destination folder should I use? Say Downloads or a full folder path. " + str(exc), "folder") from exc
        if folder_name:
            try:
                return self.catalog.resolve(folder_name, "folder")
            except ValueError as exc:
                if not isinstance(exc, AmbiguousName):
                    matches = self.memory.project_matches(folder_name)
                    if len(matches) == 1:
                        return matches[0]
                    if len(matches) > 1:
                        exc = AmbiguousName(folder_name, matches)
                question = "Which destination folder should I use? Say its full path. " + str(exc)
                error = TaskClarification(question, "folder")
                error.choices = exc.matches if isinstance(exc, AmbiguousName) else []
                if error.choices:
                    error.args = ("Which folder? " + "; ".join(f"{i}. {path}" for i, path in enumerate(error.choices, 1)),)
                raise error from exc
        raise TaskClarification("Name a destination folder or select one in File Explorer.", "folder")

    def _resolve_project(self, name):
        from .catalog import AmbiguousName
        matches = self.memory.project_matches(name)
        if len(matches) > 1:
            raise AmbiguousName(name, matches)
        return Path(matches[0]) if matches else self.projects.resolve(name)

    def execute(self, command, cancelled=lambda: False):
        """Audit outer direct commands without duplicating nested task execution."""
        local = getattr(self, "_learning_local", None)
        if local is None or getattr(local, "active", False):
            return self._execute(command, cancelled)
        local.active = True
        local.observation = None
        from .experience_memory import observe_conditions
        initial_conditions = observe_conditions(self)
        before = self.task_state.snapshot()
        result, status = None, "completed"
        try:
            result = self._execute(command, cancelled)
            if cancelled():
                status = "cancelled"
            return result
        except Exception as exc:
            result, status = str(exc), "cancelled" if cancelled() else "failed"
            raise
        finally:
            local.active = False
            after = self.task_state.snapshot()
            # TaskState.finish already recorded a new managed task, including errors.
            if (after or {}).get("started_at") == (before or {}).get("started_at"):
                checkpoints = [{"stage": "action_attempted", "action": command.kind,
                                "target": command.value}]
                outcome = local.observation
                if outcome:
                    checkpoints.append({'stage': 'outcome_observed', 'action': command.kind,
                                        'source': outcome['source'], 'evidence': outcome['evidence']})
                    # The named target may differ from the foreground observed before dispatch.
                    initial_conditions = {**outcome['conditions'],
                        **({'tool_fingerprint': initial_conditions['tool_fingerprint']}
                           if initial_conditions.get('tool_fingerprint') else {})}
                    if outcome.get('verified') and status == 'completed':
                        checkpoints.append({'stage': 'goal_verified', 'source': outcome['source'],
                                            'evidence': outcome['evidence']})
                self.skills.safe_record({"goal": command.kind.replace('_', ' ') + ' ' + command.value,
                    "kind": command.kind, "status": status, "result": result,
                    'conditions': initial_conditions, "checkpoints": checkpoints})

    def _execute(self, command, cancelled=lambda: False):
        from .commands import Command
        if cancelled():
            return
        if command.kind == 'island_choice':
            from .island_choices import resolve
            return self.execute(resolve(self, command.extra, int(command.value)), cancelled)
        if command.kind == 'island_control_choice':
            from .island_choices import snapshot
            current = snapshot(self)
            if not current or current['token']!=command.extra or current['kind']!='control':
                raise ValueError('Those choices changed or expired. Get a fresh list.')
            return self._ui().execute(Command('choose_control',str(int(command.value)+1),'island_bound'),cancelled)
        if command.kind == "open" and command.value.casefold() in {"jarvis browser", "automation browser"}:
            return str(self._browser().request("reset", cancelled))
        browser = getattr(self, "browser_automation", None)
        if browser is not None and command.kind in {"context_search", "media_search", "media_control", "select_context", "click_control"}:
            handle = self.external_handle() or (self.desktop.user.GetForegroundWindow() if self.desktop else None)
            if browser.owns_handle(handle) and "youtube.com" in browser.last_url:
                if command.kind in {"context_search", "media_search"} and (command.kind == "context_search" or command.extra == "youtube"):
                    return browser.request("search", cancelled, value=command.value)["message"]
                if command.kind == "select_context":
                    ordinal, category = command.value.split(":", 1)
                    if ordinal.isdigit() and category in {"video", "result"}:
                        return browser.request("select_video", cancelled, value="", position=int(ordinal))["message"]
                if command.kind == "media_control" and command.extra == "youtube":
                    return browser.request("control", cancelled, value=command.value)["message"]
                if command.kind == "click_control" and command.value.casefold() in {"play", "pause", "mute", "unmute"}:
                    return browser.request("control", cancelled, value=command.value.casefold())["message"]
        if command.kind == "clarification_blocked":
            return command.value
        if command.kind == "clarified_task":
            self.resume_source = json.loads(command.extra)
            try:
                return self.execute(Command("task", command.value), cancelled)
            finally:
                self.resume_source = None
        if command.kind == "toolkit":
            from .tools import ToolRegistry
            params = json.loads(command.extra)
            self.task_active = True
            self.task_state.start(command.value, "toolkit")
            try:
                result = ToolRegistry(self).execute({"action": command.value,
                    "value": params.get("value", "."), "folder": params.get("folder", ""),
                    "content": params.get("content", "")}, cancelled).evidence
                self.task_state.finish("completed", result)
                return result
            except Exception as exc:
                self.task_state.finish("cancelled" if cancelled() else "failed", exc)
                raise
            finally:
                self.task_active = False
        pending_project = self.projects.pending
        if pending_project and time.monotonic() - pending_project["time"] < 180:
            selected = None
            if command.kind == "choose_control":
                index = int(command.value) - 1
                if 0 <= index < len(pending_project["choices"]):
                    selected = pending_project["choices"][index]
                else:
                    raise ValueError("That project number is not in the list.")
            elif command.kind in {"task", "open", "open_project", "open_folder"}:
                from .names import rank
                names = [path.name for path in pending_project["choices"]]
                matched = rank(command.value.removeprefix("project "), names)
                choices = [path for path in pending_project["choices"] if path.name in matched]
                if len(choices) == 1:
                    selected = choices[0]
            if selected:
                self.projects.pending = None
                self.report("question", "")
                return self._open_project(selected, cancelled)
        elif pending_project:
            self.projects.pending = None
        if command.kind == "resume_task":
            source = self.task_state.unfinished(automatic=command.extra == "automatic")
            if not source:
                return "No interrupted task needs resuming."
            blocker = self.task_state.resume_blocker(source)
            if blocker:
                self.report("repair", "Retained task: " + source["goal"] + ". " + blocker)
                return "Task paused: " + blocker
            self.report("repair", "Resuming saved goal from fresh state: " + source["goal"])
            self.resume_source = source
            try:
                return self.execute(Command(source["kind"], source["goal"], source.get("project") or ""), cancelled)
            finally:
                self.resume_source = None
        if command.kind == "task":
            self.pending_open = None
            self.projects.pending = None
            self.last_created = None
            self.last_modified = None
            self.last_deleted = None
            self.last_command = None
            if self.ui_controls:
                self.ui_controls.clear_pending()
            self.report("question", "")
            self.task_active = True
            try:
                self.task_state.start(command.value, "task")
                result = None
                if self.config.get("agent_runtime", {}).get("fast_workflows", False):
                    from .fast_workflows import run
                    result = run(self, command.value, cancelled)
                if result is None:
                    result = self.brain.run(command.value, cancelled)
                paused = result and any(word in result.casefold() for word in
                    ("paused", "not verified", "could not be verified", "playback is not active", "stopped", "multiple play buttons"))
                self.task_state.finish("paused" if paused else "completed", result)
                return result
            except Exception as exc:
                from .clarification import TaskClarification
                if isinstance(exc, TaskClarification) and not cancelled():
                    self.task_state.finish("paused", exc)
                    self.pending_question = {"time": time.monotonic(), "goal": command.value,
                        "question": str(exc), "slot": exc.slot, "choices": getattr(exc, "choices", []), "source": self.task_state.snapshot()}
                    self.report("question", str(exc))
                    self.report("spoken_reply", str(exc))
                    return "Task paused, waiting for your answer: " + str(exc)
                self.task_state.finish("cancelled" if cancelled() else
                    "paused" if str(exc).startswith("Task paused") else "failed", exc)
                raise
            finally:
                self.task_active = False
        if command.kind == "code_task":
            from .coder import Coder
            project = self._resolve_project(command.extra)
            self.task_active = True
            try:
                self.task_state.start(command.value, "code_task", project)
                result = Coder(self, self.brain.client).run(project, command.value, cancelled)
                self.task_state.finish("paused" if result and "stopped" in result.casefold() else "completed", result)
                return result
            except Exception as exc:
                self.task_state.finish("cancelled" if cancelled() else "failed", exc)
                raise
            finally:
                self.task_active = False
        self.report("question", "")
        if command.kind == "show_command_prompt":
            self.report("show_command_prompt", "")
            return "Opened Jarvis command prompt"
        if command.kind == "project_recent":
            path, remembered = self.projects.last()
            source = "The last project I opened for you" if remembered else "The most recently active project folder I found"
            return f"{source} is {path.name} at {path}. Say open project {path.name} to open it."
        if command.kind == "project_list":
            choices = self.projects.list()
            if not choices:
                raise ValueError("No project folders found. Add their parent folders to project_roots in config.json.")
            self.projects.pending = {"time": time.monotonic(), "choices": choices}
            message = "Recent project folders (pending work is not inferred): " + "; ".join(f"{i}. {p.name}" for i, p in enumerate(choices, 1)) + ". Say a project name or option number."
            self.report("question", message)
            return message
        if command.kind == "open_project_root":
            root = next((Path(raw) for raw in self.projects.roots if Path(raw).parent != Path(raw) and Path(raw).is_dir()), None)
            if root is None:
                raise ValueError("No configured project folder is available.")
            os.startfile(str(root))
            self.catalog.folders.record_open(str(root), 'project root')
            return f"Opened {root}"
        if command.kind == "open_project":
            return self._open_project(self._resolve_project(command.value), cancelled)
        if command.kind == "gods_eye_view":
            from .browser import browser_args
            from .gods_eye_view import GodsEyeView
            if self.gods_eye_view is None:
                self.gods_eye_view = GodsEyeView()
            url = self.gods_eye_view.start(cancelled)
            if cancelled():
                return
            subprocess.Popen([*browser_args(self.apps, command.extra or "chrome"), url], shell=False)
            self.open_target_pending = self.typing_failed = True
            if self.desktop:
                self.desktop.target = None
            return f"Opened God's Eye View in {command.extra or 'chrome'}. Its public live data is available without an AI API key."
        if command.kind == "choose_control" and self.pending_open:
            pending, self.pending_open = self.pending_open, None
            if time.monotonic() - pending["time"] > 45:
                raise ValueError("Those file/app choices expired. Repeat the open command.")
            index = int(command.value) - 1
            if not 0 <= index < len(pending["choices"]):
                raise ValueError("That number is not in the list.")
            return self.execute(pending["choices"][index], cancelled)
        self.pending_open = None
        if command.kind in {"click_control", "select_context", "choose_control", "list_controls", "confirm_suggestion", "suggest_control", "forget_ui_memory"}:
            brain = getattr(self, 'brain', None)
            fallback = getattr(brain, 'visual_fallback', None)
            if command.kind == 'click_control' and fallback is not None and fallback.enabled is True:
                from .targeting import scoped_matches
                ui = self._ui()
                # Only a read-only preflight can select the fallback. Never catch an action failure here.
                try:
                    handle = ui._handle()
                    snapshot = ui.runner({'operation': 'list', 'handle': handle, 'owner_pid': os.getpid()}, cancelled)
                    missing = not scoped_matches(snapshot.get('controls', []), command.value)
                except ValueError:
                    missing = True
                if missing:
                    return self.execute(Command('task', 'Click ' + command.value), cancelled)
            result = self._ui().execute(command, cancelled)
            if command.kind == "suggest_control" or (command.kind == "confirm_suggestion" and command.value == "no"):
                self.report("question", result)
            return result
        if self.ui_controls:
            self.ui_controls.clear_pending()
        if command.kind == "close_app":
            from .desktop_tasks import close_app
            from .task_state import TaskState
            outcome = {}
            result = close_app(self.desktop, self.apps, command.value, cancelled, observed=outcome.update)
            if outcome:
                local = getattr(self, '_learning_local', None)
                if local is not None:
                    local.observation = outcome
                if isinstance(getattr(self, 'task_state', None), TaskState):
                    self.task_state.checkpoint('outcome_observed', action='close_app',
                        source=outcome['source'], evidence=outcome['evidence'])
            return result
        if command.kind == "create_in_folder":
            from .desktop_tasks import write_new_file
            data = json.loads(command.extra)
            folder = self._task_folder(data["folder"], cancelled)
            path = write_new_file(folder, command.value, data["content"], cancelled)
            self.last_created = (path, data["content"]) if path else None
            return f"Created {path} and wrote {len(data['content'])} characters" if path else "File task cancelled"
        if command.kind == "modify_in_folder":
            from .desktop_tasks import modify_text_file
            data = json.loads(command.extra)
            folder = self._task_folder(data["folder"], cancelled)
            path = modify_text_file(folder, command.value, data.get("find", ""), data["content"], cancelled)
            self.last_modified = path
            return f"Modified {path}" if path else "File edit cancelled"
        if command.kind == "delete_in_folder":
            from .commands import filename
            folder = Path(self._task_folder(command.extra, cancelled)).resolve(strict=True)
            path = folder / filename(command.value)
            if path.is_symlink() or path.resolve().parent != folder or not path.is_file():
                raise ValueError("Only an existing, individually named regular file can be deleted.")
            before = path.stat()
            self._approve("delete", str(path), cancelled)
            if path.is_symlink() or not path.is_file() or path.stat().st_size != before.st_size or path.stat().st_mtime_ns != before.st_mtime_ns:
                raise ValueError("The file changed while awaiting approval; nothing was deleted.")
            if self.recycler is None:
                from send2trash import send2trash
                self.recycler = send2trash
            self.recycler(str(path))
            self.last_deleted = path
            return f"Moved {path} to Recycle Bin"
        if command.kind == "run_command":
            command_text = command.value.strip()
            if not command_text or len(command_text) > 2000 or "\n" in command_text or "\r" in command_text:
                raise ValueError("Enter one command on a single line (maximum 2,000 characters).")
            self._approve("command", command_text, cancelled)
            with tempfile.TemporaryFile() as output_file:
                process = subprocess.Popen(["cmd.exe", "/d", "/s", "/c", command_text], cwd=self.root,
                    stdout=output_file, stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                try:
                    deadline = time.monotonic() + 60
                    while process.poll() is None:
                        if cancelled() or time.monotonic() >= deadline:
                            process.kill()
                            process.wait(timeout=5)
                            raise ValueError("Command cancelled or timed out after 60 seconds.")
                        time.sleep(.1)
                    output_file.seek(max(0, output_file.tell() - 12000))
                    output = output_file.read().decode("utf-8", errors="replace")
                finally:
                    if process.poll() is None:
                        process.kill()
            self.report("command_output", f"> {command_text}\n{output}\nExit code: {process.returncode}")
            self.last_command = (command_text, process.returncode, output[-2000:])
            return f"Command finished with exit code {process.returncode}"
        if command.kind == "spotify_control":
            from .spotify import control
            return control(command.value, cancelled)
        if command.kind == "media_control":
            from .media_ui import control
            if command.extra == 'spotify':
                from .spotify import control as spotify_control, volume
                if command.value in {'play', 'pause', 'next', 'previous', 'status', 'shuffle_on', 'shuffle_off', 'repeat_off', 'repeat_one', 'repeat_all'} or command.value.startswith('seek_'):
                    return spotify_control(command.value, cancelled)
                if command.value in {'mute', 'unmute'} or command.value.startswith('volume_'):
                    return volume(command.value.removeprefix('volume_'), cancelled)
            return control(self._ui(), command.extra, command.value, cancelled)
        if command.kind == 'context_search':
            from .media_ui import snapshot_for, platform_of
            platform = None
            try:
                _, current = snapshot_for(self._ui(), cancelled)
                platform = platform_of(current)
            except ValueError:
                if cancelled():
                    return
            return self.execute(Command('media_search', command.value, platform), cancelled) if platform else self.execute(Command('browser_search', command.value, 'chrome'), cancelled)
        if command.kind == "spotify_volume":
            from .spotify import volume
            return volume(command.value, cancelled)
        if command.kind == "spotify_search":
            from .spotify import search
            return search(command.value, cancelled)
        if command.kind == "spotify_open_playlist":
            return self.execute(Command("task", f"Open playlist {command.value} on Spotify"), cancelled)
        if command.kind == "play_media":
            return self.execute(Command("task", f"Play {command.value} on {command.extra}"), cancelled)
        if command.kind == "media_search":
            if command.extra == "spotify":
                from .spotify import search
                result = search(command.value, cancelled)
                self.open_target_pending = self.typing_failed = True
                if self.desktop:
                    self.desktop.target = None
                return result
            if self.config.get("agent_runtime", {}).get("dom_browser", False):
                return self._browser().request("search", cancelled, value=command.value, new_task=True)["message"]
            from .browser import browser_args, music_search_url
            from .media_ui import search_current
            current = search_current(self._ui(), 'youtube', command.value, cancelled)
            if current is not None:
                return current
            url = music_search_url(command.value, command.extra)
            args = browser_args(self.apps, "chrome")
            if cancelled():
                return
            subprocess.Popen([*args, url], shell=False)
            self.open_target_pending = self.typing_failed = True
            if self.desktop:
                self.desktop.target = None
            return f"Opened {command.extra} search for {command.value}; playback has not started yet."
        if command.kind in {"browse", "browser_search"}:
            from .browser import browser_args, url_for
            if (command.kind == "browse" and command.value.casefold() == "youtube"
                    and command.extra in {"", "chrome", "google chrome"}
                    and self.config.get("agent_runtime", {}).get("dom_browser", False)):
                return self._browser().request("navigate", cancelled, value="youtube", new_task=True)["message"]
            args = browser_args(self.apps, command.extra or "chrome")
            url = url_for(command.value, command.kind == "browser_search")
            if cancelled():
                return
            subprocess.Popen([*args, url], shell=False)
            self.open_target_pending = self.typing_failed = True
            if self.desktop:
                self.desktop.target = None
            return f"Opened {url} in {command.extra or 'chrome'}"
        if command.kind == "open_drive":
            if len(command.value) != 1 or not command.value.isalpha():
                raise ValueError("Invalid drive letter.")
            path = Path(command.value.upper() + ":\\")
            if not path.is_dir():
                raise ValueError(f"Drive {command.value} is not available.")
            os.startfile(str(path))
            self.open_target_pending = self.typing_failed = True
            return f"Opened {path}"
        if command.kind == "create":
            with self._path(command.value).open("x", encoding="utf-8") as file:
                file.write(command.extra)
            return f"Created {command.value}"
        if command.kind == "modify":
            from .desktop_tasks import modify_text_file
            data = json.loads(command.extra)
            path = modify_text_file(self.root, command.value, data["find"], data["content"], cancelled)
            self.last_modified = path
            return f"Modified {path}" if path else "File edit cancelled"
        if command.kind == "rename":
            source, target = self._path(command.value), self._path(command.extra)
            if not source.is_file():
                raise ValueError("Source file does not exist.")
            if target.exists():
                raise ValueError("Destination already exists; no file was overwritten.")
            source.rename(target)
            return f"Renamed {command.value} to {command.extra}"
        if command.kind == "delete":
            path = self._path(command.value)
            if not path.is_file():
                raise ValueError("Only an existing, individually named file can be deleted.")
            before = path.stat()
            self._approve("delete", str(path), cancelled)
            if path.is_symlink() or not path.is_file() or path.stat().st_size != before.st_size or path.stat().st_mtime_ns != before.st_mtime_ns:
                raise ValueError("The file changed while awaiting approval; nothing was deleted.")
            if self.recycler is None:
                from send2trash import send2trash
                self.recycler = send2trash
            self.recycler(str(path))
            self.last_deleted = path
            return f"Moved {command.value} to Recycle Bin"
        if command.kind in {"open_file", "open_folder"}:
            from .catalog import AmbiguousName
            from .commands import Command
            try:
                if command.kind == "open_folder" and not Path(command.value).is_absolute():
                    try:
                        path = self.catalog.resolve(command.value, 'folder', prefer_usage=True)
                    except AmbiguousName:
                        raise
                    except ValueError:
                        from .folder_lookup import folder_request
                        _, drive = folder_request(command.value)
                        if drive:
                            raise
                        path = str(self._resolve_project(command.value))
                else:
                    path = self.catalog.resolve(command.value, command.kind.removeprefix("open_"))
            except AmbiguousName as exc:
                return self._offer_open([Command(command.kind, path) for path in exc.matches[:20]])
            if cancelled():
                return
            os.startfile(path)
            if command.kind == 'open_folder':
                self.catalog.folders.record_open(path, command.value)
            self.open_target_pending = True
            self.typing_failed = True
            return f"Opened {path}. Select its text field and say stop dictation before writing."
        if command.kind == "open":
            from .names import rank_spelling, common
            from .commands import Command
            from .browser import SITES
            # Spotify exists in both the app and site catalogs. Prefer its
            # registered native app; browser requests still use browse.
            if common(command.value) == 'spotify' and 'spotify' not in self.apps:
                from .spotify import open_app
                return open_app(cancelled)
            if common(command.value) in SITES and common(command.value) != 'spotify':
                return self.execute(Command("browse", command.value, "chrome"), cancelled)
            aliases = rank_spelling(command.value, self.apps)
            memory_args = None
            if not aliases:
                # Exact saved app names only; a stale path never becomes a guessed command.
                saved = self.memory.program_matches(command.value)
                if len(saved) > 1:
                    raise ValueError('Multiple saved programs match ' + command.value + '; specify its executable path.')
                if saved:
                    memory_args = saved[0]['launcher']
            if not aliases:
                sites = rank_spelling(command.value, SITES)
                if len(sites) == 1:
                    self.report("state", "Understood '" + command.value + "' as " + sites[0])
                    return self.execute(Command("browse", sites[0], "chrome"), cancelled)
            unique = []
            for alias in aliases:
                if not any(self.apps[alias] == self.apps[other] for other in unique):
                    unique.append(alias)
            if len(unique) > 1:
                return self._offer_open([Command("open", alias) for alias in unique[:20]])
            if memory_args is not None:
                pass
            elif unique:
                if common(command.value) != common(unique[0]):
                    self.report("state", "Understood '" + command.value + "' as " + unique[0])
                command = Command("open", unique[0])
            else:
                # Generic 'open my report' also searches the existing file catalog.
                from .catalog import AmbiguousName
                choices = []
                for kind in ("file", "folder"):
                    try:
                        path = self.catalog.resolve(command.value, kind, prefer_usage=kind == 'folder')
                        choices.append(Command("open_" + kind, path))
                    except AmbiguousName as exc:
                        choices.extend(Command("open_" + kind, path) for path in exc.matches[:20])
                    except ValueError:
                        pass
                for path in self.memory.project_matches(command.value):
                    choice = Command("open_folder", path)
                    if choice not in choices:
                        choices.append(choice)
                if len(choices) == 1:
                    return self.execute(choices[0], cancelled)
                if choices:
                    return self._offer_open(choices[:20])
                raise ValueError(f"No matching app, file, or folder for '{command.value}'. Try another word from its name.")
            self.open_target_pending = True
            self.typing_failed = True
            args = memory_args if memory_args is not None else self.apps.get(command.value)
            expected = None
            if isinstance(args, dict):
                if args.get("shortcut"):
                    if not Path(args["shortcut"]).is_file():
                        raise ValueError("App shortcut no longer exists; rerun scan_pc.ps1.")
                    os.startfile(args["shortcut"])
                    expected = Path(args["executable"]).name if args.get("executable") else None
                elif args.get("shell_id"):
                    subprocess.Popen(["explorer.exe", "shell:AppsFolder\\" + args["shell_id"]], shell=False)
                    if command.value == 'spotify':
                        return 'Opened the native Spotify app.'
                else:
                    raise ValueError("Invalid application catalog entry.")
                if expected is None:
                    return f"Launched {command.value}. For typing, click its text field and say stop dictation, then write."
            else:
                if not isinstance(args, list) or not args or not all(isinstance(x, str) for x in args):
                    raise ValueError(f"Unknown app '{command.value}'. Add its executable to config.json or run scan_pc.ps1.")
                subprocess.Popen(args, shell=False)
                expected = Path(args[0]).name
            # Give the new app a chance to take focus. Never type into the old one.
            for _ in range(50):
                if cancelled():
                    return
                try:
                    self.desktop.capture(expected=expected)
                    # The app can own the foreground before its editor is ready.
                    time.sleep(0.3)
                    self.desktop.capture(expected=expected)
                    self.typing_failed = False
                    return f"Opened {command.value}"
                except ValueError:
                    pass
                time.sleep(0.1)
            self.typing_failed = True
            return f"Opened {command.value}; focus was not detected. Click the app, say stop dictation, then write."
        if command.kind == "begin_dictation":
            self.dictation_active = True
            if self.open_target_pending:
                self.open_target_pending = False
                if self.typing_failed:
                    raise ValueError("The requested app did not take focus. Click its text area, then say stop dictation and write again.")
            else:
                # A new 'write' command targets the currently selected app.
                self.desktop.target = None
                self.typing_failed = False
                try:
                    self.desktop.capture()
                except Exception:
                    self.typing_failed = True
                    raise
            return "Dictation ready in the selected app"
        if command.kind == "stop_dictation":
            self.dictation_active = False
            self.open_target_pending = False
            self.desktop.target = None
            self.typing_failed = False
            return "Dictation stopped"
        if command.kind == "type":
            if self.typing_failed:
                raise ValueError("Typing paused. Say stop dictation, select the app, then say write.")
            try:
                self.desktop.type(command.value, cancelled)
            except Exception:
                self.typing_failed = True
                raise
            return f"Typed {len(command.value.split())} words"
        raise ValueError(f"Unsupported action: {command.kind}")

    def _offer_open(self, choices):
        self.pending_open = {"time": time.monotonic(), "choices": choices}
        message = "Which one? Say select option number: " + "; ".join(f"{i}. {c.value}" for i, c in enumerate(choices, 1))
        self.report("question", message)
        return message

    def _open_project(self, path, cancelled):
        from .browser import browser_args, url_for
        import shutil
        path = Path(path).resolve(strict=True)
        if not path.is_dir():
            raise ValueError("That project folder is no longer available.")
        chrome = browser_args(self.apps, "chrome")
        codex = shutil.which("codex")
        if not codex:
            raise ValueError("Codex CLI was not found on PATH; reinstall Codex or set its launcher on PATH.")
        if cancelled():
            return "Project opening cancelled"
        os.startfile(str(path))
        self.catalog.folders.record_open(str(path), 'project ' + path.name)
        if cancelled():
            return f"Opened {path} in File Explorer; remaining launches cancelled."
        subprocess.Popen([codex, "app", str(path)], shell=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if cancelled():
            return f"Opened {path} in File Explorer and sent it to Codex; YouTube launch cancelled."
        subprocess.Popen([*chrome, url_for("youtube")], shell=False)
        self.projects.remember(path)
        return f"Opened {path.name} in File Explorer and Codex, and opened YouTube in Chrome."

    def _run(self):
        while not self.closed.is_set():
            try:
                generation, command = self.queue.get(timeout=0.2)
            except queue.Empty:
                self._suggest()
                continue
            try:
                cancelled = lambda: self.closed.is_set() or generation != self.generation
                if not cancelled():
                    from .progress import status
                    phases = {'open': 'Opening', 'open_folder': 'Opening folder', 'open_file': 'Opening file',
                              'code_task': 'Preparing code', 'task': 'Planning task', 'browse': 'Opening website',
                              'media_search': 'Searching', 'run_command': 'Running command'}
                    status(self.report, phases.get(command.kind, 'Working'),
                           '' if command.kind in {'type', 'dictate', 'run_command'} else command.value)
                    result = self.execute(command, cancelled)
                    if result and not cancelled():
                        self.report("action", result)
                        if command.kind in {"task", "code_task", "resume_task", "open", "browse", "browser_search",
                                            "create", "create_in_folder", "modify_in_folder", "delete_in_folder",
                                            "play_media", "spotify_control", "spotify_open_playlist", "close_app"}:
                            self.report("spoken_reply", result)
            except Exception as exc:
                if generation in self.superseded_generations and generation != self.generation:
                    self.report("state", "Previous task replaced by your newer request.")
                    self.superseded_generations.discard(generation)
                else:
                    self.report("warning", str(exc))
            finally:
                from .progress import status
                status(self.report, 'Ready' if generation == self.generation else 'Cancelled', active=False)
                self.superseded_generations.discard(generation)
                self.queue.task_done()
