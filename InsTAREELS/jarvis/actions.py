from .paths import state_file
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


# Requests worth a spoken "queued" acknowledgement (not keystrokes or UI clicks).
QUEUED_ANNOUNCED = {'task', 'code_task', 'clarified_task', 'resume_task', 'open', 'browse', 'browser_search',
                    'compose_text', 'write_text',
                    'play_media', 'media_search', 'open_folder', 'open_file', 'open_project', 'toolkit',
                    'windows_command', 'run_command', 'create', 'create_in_folder', 'modify_in_folder', 'delete_in_folder'}


TYPING_INTERVAL = 0.01  # Seconds between typed characters.


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
            raise ValueError("Click the app you want me to write in first.")
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

        encoded = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-16-le")
        for offset in range(0, len(encoded), 2):
            if cancelled():
                return
            pointer = wintypes.POINT()
            if self.user.GetCursorPos(ctypes.byref(pointer)):
                right, bottom = self.user.GetSystemMetrics(0) - 1, self.user.GetSystemMetrics(1) - 1
                if pointer.x in (0, right) and pointer.y in (0, bottom):
                    raise ValueError("Typing halted: mouse is in a screen corner.")
            if self.user.GetForegroundWindow() != self.target:
                raise ValueError("The window changed while typing, so typing stopped. Nothing more was typed.")
            code = int.from_bytes(encoded[offset:offset + 2], "little")
            if code == 10:
                # Shift+Enter: a new line in editors, email bodies and chat boxes, where a
                # plain Enter would send the message or submit the form.
                events = (INPUT * 4)(INPUT(1, UNION(ki=KEYBDINPUT(0x10, 0, 0, 0, 0))), INPUT(1, UNION(ki=KEYBDINPUT(0x0D, 0, 0, 0, 0))),
                                     INPUT(1, UNION(ki=KEYBDINPUT(0x0D, 0, 2, 0, 0))), INPUT(1, UNION(ki=KEYBDINPUT(0x10, 0, 2, 0, 0))))
            else:
                events = (INPUT * 2)(INPUT(1, UNION(ki=KEYBDINPUT(0, code, 4, 0, 0))), INPUT(1, UNION(ki=KEYBDINPUT(0, code, 6, 0, 0))))
            if self.user.SendInput(len(events), events, ctypes.sizeof(INPUT)) != len(events):
                raise RuntimeError("Windows blocked typing. Select a normal, non-administrator app.")
            # Windows 11 Notepad (WinUI) drops or repeats characters that arrive with no gap
            # ("abc jarvis" became "abc zzzzz"); 10 ms per character typed it exactly.
            time.sleep(TYPING_INTERVAL)


# Player controls and answers to prompts are not worth remembering as conversation turns.
QUIET_KINDS = {"media_control", "spotify_control", "spotify_volume", "click_control", "choose_control",
               "confirm_suggestion", "select_context", "island_choice", "approval_answer", "cancel_current",
               "queue_status", "memory_list", "memory_conversations", "list_controls", "ask"}


def media_session_open(actions):
    """Whether a bare "pause"/"play" belongs to Spotify or Jarvis's YouTube rather than a visible button."""
    if getattr(actions, "last_media", None):
        return True
    from .media_player import spotify_now, youtube_state
    return bool(spotify_now() or youtube_state(actions))


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
        self.ui_memory = UIMemory(state_file("ui_memory.json", base))
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
        if not config.get('_ui_verification', False):
            self.knowledge.attach_conversations(Path(base) / '.jarvis-runtime/conversations.sqlite3',
                config.get('memory', {}).get('conversation_sessions', {}))
            self.knowledge.attach_selector(config.get('context_selector', {'enabled': False}))
        self.knowledge.memory = self.memory
        self.knowledge.client.memory = self.memory
        from .memory_curator import MemoryCurator
        long_term = dict(config.get("memory", {}).get("long_term", {}))
        long_term["enabled"] = bool(self.memory.enabled and long_term.get("enabled", True))
        self.curator = MemoryCurator(self.memory.vault, long_term)
        self.memory.curator = self.curator
        self.knowledge.curator = self.curator
        self.weather_watch = None
        from .repo_learning import RepoLearner, REGISTRY
        self.repo_learner = RepoLearner(self, config.get("repo_learning", {}))
        self.repo_learner.enabled = bool(self.repo_learner.enabled and self.memory.enabled)
        REGISTRY["learner"] = self.repo_learner
        from .context_hub import prompt_block
        self.memory.situation = lambda question="": prompt_block(self, question)  # Several live contexts at once.
        from .quick_answers import QuickAnswers
        self.knowledge.quick = QuickAnswers(self.memory, config.get("weather", {}), settings=config)
        from .brain import Brain
        self.brain = Brain(self, base, config.get("brain", {}))
        self.brain.client.context_provider = self.knowledge.planning_context
        from .live_app_context import LiveAppContext
        self.live_app = LiveAppContext()
        self.brain.client.app_context_provider = self.live_app.snapshot
        self.knowledge.app_snapshot_provider = self.live_app.snapshot
        self.knowledge.live_app_provider = lambda cancelled: self.live_app.refresh(self._ui(),cancelled)
        self.task_active = False
        self.suggest_enabled = False
        self.suggest_until = 0
        self.dictation_active = False
        self.next_suggestion = 0
        self.recycler = recycler
        self.queue = queue.Queue(maxsize=128)
        # Tasks wait in order; each has its own cancel token so one can be skipped.
        self.queue_lock = threading.Lock()
        self.pending_tasks = []
        self.current_item = None
        self.last_media = None  # "youtube" or "spotify": where an unqualified "play X" goes.
        self.whatsapp_prompts = []  # Questions a WhatsApp step is waiting on (contact choice, preview, call).
        self.approvals_waiting = 0
        self.decision_handler = None  # Set by the app: answers the island approval card by voice.
        self.whatsapp_watcher = None
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
        from .anticipation import Anticipation
        anticipation_options = dict(config.get('anticipation', {}))
        if config.get('_ui_verification', False):
            anticipation_options['enabled'] = False
        self.anticipation = Anticipation(self.base, anticipation_options, report,
            busy=lambda: (self.closed.is_set() or self.queue.unfinished_tasks > 0
                or self.knowledge.queue.unfinished_tasks > 0 or self.task_active
                or self.dictation_active or bool(self.pending_question)
                or bool(self.pending_open) or bool(self.projects.pending)
                or bool(self.ui_controls and self.ui_controls.pending)),
            model=config.get('brain', {}).get('planner', 'qwen3.5:4b'))
        self.knowledge.on_request = self.anticipation.observe_request
        from .realtime import Realtime
        realtime_options = dict(config.get('realtime', {}))
        if config.get('_ui_verification', False):
            realtime_options['enabled'] = False
        self.realtime = Realtime(self.base, realtime_options, report,
            busy=lambda: self.anticipation.busy())
        self.knowledge.realtime = self.realtime
        self.brain.client.realtime_provider = lambda goal, cancelled: self.realtime.context(goal, cancelled, refresh=False)

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
        self.anticipation.start()
        self.realtime.start()

    def cancel(self):
        realtime = getattr(self, 'realtime', None)
        if realtime is not None:
            realtime.cancel()
        anticipation = getattr(self, 'anticipation', None)
        if anticipation is not None:
            anticipation.cancel()
        self.generation += 1  # Running and queued work all belong to older generations.
        lock = getattr(self, 'queue_lock', None)
        if lock is not None:
            with lock:
                self.pending_tasks.clear()
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
        from .whatsapp import answer_prompt
        if answer_prompt(self, command):
            return  # A reply to a waiting WhatsApp question (contact choice, preview approval, call).
        if command.kind in {'approval_answer', 'whatsapp_answer'}:
            if self.approvals_waiting and self.decision_handler:
                self.decision_handler(command.value == 'yes')
            else:
                self.report('spoken_reply', 'Nothing is waiting for your approval right now.')
            return
        if command.kind == 'task' and command.extra == 'unparsed':
            from .commands import Command
            if self.pending_question or self.pending_open:
                command = Command('task', command.value)  # Likely an answer; keep the reply path.
            else:
                # Conversation or task? Decide off the audio thread; a tiny model may be needed.
                threading.Thread(target=self._route_unparsed, args=(command.value,),
                                 name='Jarvis intent', daemon=True).start()
                return
        if command.kind == 'cancel_task':
            # Matching may consult a tiny model; keep it off the audio thread.
            threading.Thread(target=lambda: self.report('spoken_reply', self._cancel_task(command)),
                             name='Jarvis cancel task', daemon=True).start()
            return
        if command.kind in {'end_conversation', 'cancel_current', 'cancel_all', 'queue_status'}:
            self.report('spoken_reply', self._queue_control(command.kind))
            if command.kind == 'end_conversation':
                self.report('state', 'Listening for Jarvis')
            return
        realtime = getattr(self, 'realtime', None)
        if realtime is not None:
            realtime.cancel()
            if command.kind in {'ask', 'task', 'realtime'}:
                reply = realtime.controls(command.value)
                if reply is not None:
                    self.report('answer', reply)
                    return
        anticipation = getattr(self, 'anticipation', None)
        if anticipation is not None:
            if command.kind in {'ask', 'task'}:
                from .anticipation import command as anticipation_command
                control = anticipation_command(command.value)
                if control:
                    from .commands import Command
                    command = Command('anticipation', control)
            if command.kind == 'anticipation':
                message = anticipation.handle(command.value, command.extra)
                self.report('anticipation_reply', message)
                if command.value in {'show', 'accept'}:
                    self.report('island_navigation', ('Prepared', ''))
                return
            anticipation.observe_request(command.kind, command.value)
        from .island_choices import navigation, task_answer
        local = navigation(command.value) if command.kind in {'task', 'ask', 'play_media', 'open'} else None
        if local:
            self.report('island_navigation', local)
            return  # Games/view changes never supersede a background task.
        answer = task_answer(getattr(self, 'task_state', None), command.value) if command.kind in {'ask','task'} else None
        if answer is not None:
            if getattr(self, 'knowledge', None) is not None:
                self.knowledge.record_pair(command.value, answer)
            self.report('answer', answer)
            return
        if command.kind == 'memory_choice':
            try:
                self.knowledge.choose_memory(command.extra, int(command.value))
            except (ValueError, TypeError) as exc:
                self.report('question', str(exc))
            return
        if getattr(getattr(self, 'knowledge', None), 'pending_memory', None):
            try:
                if self.knowledge.memory_reply(command):
                    return
            except ValueError as exc:
                self.report('question', str(exc))
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
            self.report("answer", "New conversation started. Previous sessions remain in saved memory.")
            return
        if command.kind == "sleep":
            if anticipation is not None:
                anticipation.handle('pause')
            self.cancel()
            self.report("state", "Listening for Jarvis Ã‚Â· queued tasks cancelled")
            return
        if command.kind in {'write_text', 'compose_text'}:
            command = self._with_write_target(command)
        # A new request never replaces running work: it waits its turn while questions
        # and conversation continue on their own worker.
        token = threading.Event()
        with self.queue_lock:
            ahead = len(self.pending_tasks) + (self.current_item is not None)
            self.pending_tasks.append((token, command))
        try:
            if command.kind in {'task', 'code_task', 'clarified_task', 'resume_task'}:
                self.knowledge.prepare_context(command.value)
            self.queue.put_nowait((self.generation, command, token))
        except queue.Full:
            with self.queue_lock:
                self.pending_tasks = [item for item in self.pending_tasks if item[0] is not token]
            self.report("warning", "The task queue is full; that request was not added.")
            return
        if ahead and command.kind in QUEUED_ANNOUNCED:
            self.report("spoken_reply", "Okay, I'll do that next." if ahead == 1 else
                        "Okay, that's queued. " + str(ahead) + " tasks are ahead of it.")

    def _with_write_target(self, command):
        """Remember the window the user was in when asking; a queued write still lands there."""
        from .commands import Command
        data = json.loads(command.extra or '{}')
        if not data.get('target') and self.desktop is not None:
            try:
                hwnd = self.desktop.user.GetForegroundWindow()
                pid = ctypes.c_ulong()
                self.desktop.user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if hwnd and pid.value != os.getpid():
                    data['hwnd'] = int(hwnd)
            except (AttributeError, OSError):
                pass
        return Command(command.kind, command.value, json.dumps(data))

    def _route_unparsed(self, text):
        from .commands import Command
        from .conversation_intent import quick_kind, model_kind
        kind = quick_kind(text)
        if kind is None:
            options = {'model': self.config.get('context_selector', {}).get('model', 'qwen3.5:0.8b'), 'timeout_seconds': 3.0}
            kind = model_kind(text, options, self.closed.is_set)
        if not self.closed.is_set():
            self.submit(Command('ask' if kind == 'chat' else 'task', text))

    def _cancel_task(self, command):
        """Cancel the queued or running task the user described; never guess between ties."""
        from .task_queue import match, describe, model_choice
        with self.queue_lock:
            current, pending = self.current_item, list(self.pending_tasks)
        items = ([current] if current else []) + pending
        if not items:
            return "There are no tasks to cancel."
        options = {'model': self.config.get('context_selector', {}).get('model', 'qwen3.5:0.8b'), 'timeout_seconds': 3.0}
        verdict, found = match(command.value, current[1] if current else None, [c for _, c in pending], model_choice(options))
        if verdict == 'ambiguous':
            return ("I'm not sure which one you mean: " + "; or ".join(describe(items[i][1]) for i in found[:3]) +
                    ". Say a bit more, or its number from the queue.")
        if verdict == 'none':
            return "I couldn't find a task matching " + command.value[:60] + ". Say \"what's in the queue\" to hear them."
        chosen = items[found]
        if command.extra == 'except':
            keep = chosen[0]
            stopped = [item for item in items if item[0] is not keep]
        else:
            stopped = [chosen]
        with self.queue_lock:
            for token, _ in stopped:
                token.set()  # A waiting task is skipped when reached; the running one stops.
            self.pending_tasks = [item for item in self.pending_tasks if item[0] not in {t for t, _ in stopped}]
        if command.extra == 'except':
            return ("Okay, I cancelled everything except " + describe(chosen[1]) + "." if stopped
                    else "That is the only task, so nothing else was cancelled.")
        running = current is not None and chosen[0] is current[0]
        return ("Stopped " if running else "Removed ") + describe(chosen[1]) + (
            "." if running else " from the queue.")

    def _queue_control(self, kind):
        """Spoken queue controls: cancel one task, cancel all, report, or end the call."""
        def describe(command):
            return (command.value or command.kind.replace('_', ' ')).splitlines()[0][:80]
        with self.queue_lock:
            current, pending = self.current_item, list(self.pending_tasks)
        if kind == 'queue_status':
            if not current and not pending:
                return "Nothing is running and the queue is empty."
            parts = (["Working on: " + describe(current[1]) + "."] if current else [])
            if pending:
                # Numbered so "remove number 2" refers to what was heard.
                parts.append("Waiting: " + "; ".join(str(i) + ", " + describe(command) for i, (_, command)
                                                    in enumerate(pending[:5], 1)) +
                             ("; and " + str(len(pending) - 5) + " more." if len(pending) > 5 else "."))
            return " ".join(parts)
        if kind == 'cancel_current':
            if not current:
                return "Nothing is running right now."
            current[0].set()
            return "Stopped " + describe(current[1]) + "." + (" Moving on to the next task." if pending else "")
        if kind == 'cancel_all':
            self.cancel()
            with self.queue_lock:
                for token, _ in self.pending_tasks:
                    token.set()
                self.pending_tasks.clear()
                if self.current_item:
                    self.current_item[0].set()
            return "Stopped all tasks and cleared the queue." if current or pending else "There were no tasks to stop."
        count = len(pending) + (current is not None)
        return "Okay, talk to you later." + (
            " I'll keep working on " + str(count) + (" task" if count == 1 else " tasks") + " in the background." if count else "")

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
        folder_reply = bool(pending and pending["slot"] == "folder" and command.kind == "open_folder")
        if pending and time.monotonic() - pending["time"] > 180:
            self.pending_question = None
            if short_reply(command) or folder_reply:
                self.report("question", "That task question expired. Repeat the original request.")
                return Command("clarification_blocked", "That task question expired. Repeat the original request.")
            pending = None
        if pending and (short_reply(command) or folder_reply):
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
                import re
                answer = re.sub(r"^(?:(?:please\s+)?(?:use|in|inside)\s+|(?:the\s+)?folder\s+is\s+)", "", answer, flags=re.I).strip()
                answer = re.sub(r"^the\s+(?=folder\b|[a-z]:[\\/])", "", answer, flags=re.I).strip().strip('\"\'')
                choices = pending.get("choices", [])
                index = choice_index(answer, choices) if choices else None
                if index is not None:
                    if not 0 <= index < len(choices):
                        self.pending_question = pending
                        self.report("question", pending["question"])
                        return Command("clarification_blocked", "That folder number is not in the list.")
                    answer = choices[index]
                try:
                    answer = self.catalog.resolve(answer, "folder")
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
        from .utility_host import OwnedServer
        watcher = getattr(self, 'whatsapp_watcher', None)
        if watcher is not None:
            watcher.close()
        weather = getattr(self, 'weather_watch', None)
        if weather is not None:
            weather.close()
        learner = getattr(self, 'repo_learner', None)
        if learner is not None:
            learner.close()
        curator = getattr(self, 'curator', None)
        if curator is not None and curator.thread is not None:
            # Summarise the open conversation into Obsidian, bounded so shutdown never hangs.
            closing = threading.Thread(target=curator.close, name='Jarvis memory close', daemon=True)
            closing.start()
            closing.join(45)
        utility_server=getattr(self,'utility_server',None)
        if isinstance(utility_server,OwnedServer):utility_server.close();self.utility_server=None
        realtime = getattr(self, 'realtime', None)
        if realtime is not None:
            realtime.close()
        anticipation = getattr(self, 'anticipation', None)
        if anticipation is not None:
            anticipation.close()
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
            self.ui_controls.live_app = getattr(self,'live_app',None)
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
        self.approvals_waiting += 1  # "approve" / "don't send" by voice answers the card too.
        try:
            approved = not cancelled() and self.approval_handler(kind, detail, cancelled) and not cancelled()
        finally:
            self.approvals_waiting -= 1
        if not approved:
            raise ValueError("Action cancelled; approval was not given.")

    def start_background_memory(self):
        """Long-term memory curator, repository learning and bad-weather watch (all off the response path)."""
        if self.curator.enabled:
            self.curator.start()
        if self.repo_learner.enabled:
            self.repo_learner.start()
        settings = self.config.get("weather_alerts", {})
        if settings.get("enabled", True):
            from .weather_watch import WeatherWatch
            self.weather_watch = WeatherWatch(self, settings).start()

    def start_whatsapp_watch(self):
        """New-message and incoming-call watcher (config whatsapp.watch_messages / watch_calls)."""
        settings = self.config.get("whatsapp", {})
        if settings.get("enabled", True) and (settings.get("watch_messages", True) or settings.get("watch_calls", True)):
            from .whatsapp import Watcher
            self.whatsapp_watcher = Watcher(self, float(settings.get("poll_seconds", 2))).start()

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
        if (command.kind in {"spotify_control", "spotify_volume"} and command.extra == "auto") or (
                command.kind == "click_control" and command.extra == "click" and command.value in {"play", "pause"}
                and media_session_open(self)):
            # No service named: control whichever of Spotify/YouTube is actually playing.
            from .media_player import resolve
            command = resolve(self, command)
            self.media_resolved = command  # The island card shows the service that was actually controlled.
        if command.kind == "media_control" and not command.extra:
            # "pause", "next", "play it again": whichever service is playing (or Jarvis last played on).
            from .media_player import active_service
            if active_service(self) == "spotify":
                from .spotify import control
                if command.value == "restart":
                    control("seek_-36000", cancelled)
                    return "Playing it again from the start on Spotify."
                return control(command.value, cancelled)
            command = Command("media_control", command.value, "youtube")
        if command.kind in {'windows_catalog', 'windows_command'}:
            from .windows_commands import catalog, search, execute as windows_execute
            if command.kind == 'windows_catalog':
                return json.dumps(search(command.value) if command.value != '.' else {
                    'commands':493, 'categories':sorted({r['category'] for r in catalog()}),
                    'usage':'search windows commands camera; windows command 1; windows command 137 {"path1":"D:\\notes.txt"}'},ensure_ascii=False)
            return windows_execute(self,json.loads(command.value),json.loads(command.extra or '{}'),cancelled)
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
        if command.kind == 'open':
            from .windows_commands import match as windows_match, execute as windows_execute
            ident=windows_match('open '+command.value)
            if ident and ident<=94 and command.value.casefold() not in self.apps:
                self.open_target_pending=True
                self.typing_failed=True
                return windows_execute(self,[ident],{},cancelled)
        browser = getattr(self, "browser_automation", None)
        if browser is not None and command.kind in {"context_search", "media_search", "media_control", "select_context", "click_control"}:
            handle = self.external_handle() or (self.desktop.user.GetForegroundWindow() if self.desktop else None)
            owned_player = (command.kind == "media_control" and command.extra == "youtube"
                            and getattr(self, "last_media", None) == "youtube" and "youtube.com/watch" in browser.last_url)
            if (owned_player or browser.owns_handle(handle)) and "youtube.com" in browser.last_url:
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
                if self.config.get('agent_runtime', {}).get('direct_execution', False):
                    from .direct_execution import run as run_direct
                    result = run_direct(self, command.value, cancelled)
                if result is None and self.config.get("agent_runtime", {}).get("fast_workflows", False):
                    from .fast_workflows import run
                    result = run(self, command.value, cancelled)
                if result is None:
                    result = self.brain.run(command.value, cancelled)
                from .gmail_workflows import UnreadSearchResult
                paused = result and not isinstance(result, UnreadSearchResult) and any(word in result.casefold() for word in
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
            selected=bool(command.extra and Path(command.extra).is_absolute())
            project = Path(command.extra).resolve(strict=True) if selected else self._resolve_project(command.extra)
            self.task_active = True
            try:
                self.task_state.start(command.value, "code_task", project)
                coder = Coder(self, self.brain.client)
                # Learned repositories for this kind of task: saved memory first, otherwise GitHub (then saved).
                try:
                    coder.reference_repositories = self.repo_learner.prepare(command.value, cancelled)
                except Exception as exc:
                    coder.reference_repositories = []
                    self.report("warning", "Coding without repository references: " + str(exc)[:160])
                result = coder.run(project, command.value, cancelled, selected=selected)
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
            from .coding_processes import Processes
            from uuid import uuid4
            run=Path(self.base)/'.jarvis-runtime/commands'/uuid4().hex;run.mkdir(parents=True)
            commands=Processes(self.root,run,self.report,cancelled)
            try:
                result=commands.start(['cmd.exe','/d','/s','/c',command_text],timeout_seconds=60,trusted=True)
                chunks=[result['output']]
                while result['running']:
                    result=commands.poll(result['session_id']);chunks.append(result['output'])
                output=''.join(chunks)[-12000:];exit_code=result['exit_code']
            finally:commands.close()
            self.report("command_output", f"> {command_text}\n{output}\nExit code: {exit_code}")
            self.last_command = (command_text, exit_code, output[-2000:])
            return f"Command finished with exit code {exit_code}"
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
        if command.kind in {"whatsapp_send", "whatsapp_reply"}:
            from . import whatsapp
            data = json.loads(command.extra or "{}")
            self.task_state.start(command.kind.replace("_", " ") + " " + command.value, command.kind)
            try:
                if command.kind == "whatsapp_send":
                    return whatsapp.send_message(self, command.value, data.get("instruction", ""), bool(data.get("verbatim")), cancelled)
                if data.get("auto"):
                    return whatsapp.auto_reply(self, command.value, data.get("preview", ""), cancelled)
                return whatsapp.reply_unread(self, command.value, data.get("instruction", ""), cancelled)
            except whatsapp.WhatsAppError as exc:
                self.report("media_card", whatsapp.card("error", command.value or "WhatsApp", str(exc)[:90]))
                raise
        if command.kind in {"memory_save", "memory_forget", "memory_list", "memory_conversations"}:
            from .memory_curator import execute as memory_execute
            answer = memory_execute(self, command)
            if command.kind == "memory_list" and not command.value:
                profile = self.memory.profile_text()
                basics = [line[2:] for line in profile.splitlines() if line.startswith("- ")][:6]
                if basics:
                    answer = "From your profile: " + "; ".join(basics) + ". " + answer
            return answer
        if command.kind in {"repo_learn", "repo_list", "repo_explain", "repo_forget"}:
            from .repo_learning import execute as repo_execute
            return repo_execute(self, command, cancelled)
        if command.kind == "api_health":
            from .capability_guide import check_apis
            return check_apis(self, cancelled)
        if command.kind == "weather_alerts":
            from .weather_watch import WeatherWatch
            watch = self.weather_watch or WeatherWatch(self, self.config.get("weather_alerts", {}))
            return watch.summary()
        if command.kind == "messenger_send":
            from .messengers import send
            return send(self, command.value, json.loads(command.extra or "{}"), cancelled)
        if command.kind == "play_media":
            # Search, choose, play and verify directly (no planning model); see media_player.py.
            from .media_player import play
            return play(self, command.value, command.extra or None, cancelled)
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
                self.last_media = "youtube"
                return self._browser().request("navigate", cancelled, value="youtube", new_task=True)["message"]
            args = browser_args(self.apps, command.extra or "chrome")
            url = url_for(command.value, command.kind == "browser_search")
            if cancelled():
                return
            subprocess.Popen([*args, url], shell=False)
            self.open_target_pending = self.typing_failed = True
            if self.desktop:
                self.desktop.target = None
                # Focus the browser so the next observation inspects the page, not the old window.
                from urllib.parse import urlsplit
                from .window_focus import focus_app
                host = (urlsplit(url).hostname or '').removeprefix('www.').split('.')[0]
                hwnd = focus_app(Path(args[0]).name, host, cancelled=cancelled)
                if hwnd:
                    self.desktop.target = hwnd
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
            return f"Opened {path}."
        if command.kind == "open":
            from .names import rank_spelling, common
            from .commands import Command
            from .browser import SITES
            # Spotify exists in both the app and site catalogs. Prefer its
            # registered native app; browser requests still use browse.
            if common(command.value) == 'spotify' and 'spotify' not in self.apps:
                from .spotify import open_app
                self.last_media = "spotify"
                return open_app(cancelled)
            if common(command.value) in SITES and common(command.value) != 'spotify':
                return self.execute(Command("browse", command.value, "chrome"), cancelled)
            aliases = rank_spelling(command.value, self.apps)
            # An exact configured name ('chrome') wins over longer matches ('google chrome').
            aliases = [alias for alias in aliases if common(alias) == common(command.value)][:1] or aliases
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
                    return f"Launched {command.value}."
            else:
                if not isinstance(args, list) or not args or not all(isinstance(x, str) for x in args):
                    raise ValueError(f"Unknown app '{command.value}'. Add its executable to config/config.json or run scan_pc.ps1.")
                subprocess.Popen(args, shell=False)
                expected = Path(args[0]).name
            # Give the new app a chance to take focus. Never type into the old one.
            for attempt in range(50):
                if cancelled():
                    return
                if attempt in {8, 25}:
                    # Focus-stealing prevention can leave the old window in front.
                    from .window_focus import windows, focus
                    rows = windows(expected)
                    if rows:
                        focus(rows[0][0])
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
            return f"Opened {command.value}; it has not come to the front yet."
        if command.kind == "write_help":
            from .writing import HELP
            return HELP
        if command.kind in {"write_text", "compose_text"}:
            # No dictation mode: one composed or verbatim piece of text, then back to normal.
            from .writing import write_exact, compose
            self.open_target_pending = False
            self.typing_failed = False
            self.desktop.target = None
            return (write_exact if command.kind == "write_text" else compose)(self, command, cancelled)
        if command.kind == "type":
            self.desktop.type(command.value, cancelled)
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
                generation, command, token = self.queue.get(timeout=0.2)
            except queue.Empty:
                self._suggest()
                continue
            with self.queue_lock:
                self.pending_tasks = [item for item in self.pending_tasks if item[0] is not token]
                self.current_item = (token, command)
            try:
                cancelled = lambda: self.closed.is_set() or generation != self.generation or token.is_set()
                if not cancelled():
                    from .progress import status
                    phases = {'open': 'Opening', 'open_folder': 'Opening folder', 'open_file': 'Opening file',
                              'code_task': 'Preparing code', 'task': 'Planning task', 'clarified_task': 'Resuming task', 'browse': 'Opening website',
                              'media_search': 'Searching', 'run_command': 'Running command'}
                    status(self.report, phases.get(command.kind, 'Working'),
                           '' if command.kind in {'type', 'dictate', 'run_command'} else command.value)
                    result = self.execute(command, cancelled)
                    if result and not cancelled() and (command.kind in {"media_control", "spotify_control", "spotify_volume"} or (
                            command.kind == "click_control" and command.value in {"play", "pause"}
                            and getattr(self, "media_resolved", None))):
                        from .media_player import control_card
                        threading.Thread(target=control_card, args=(self, command), daemon=True,
                                         name="jarvis-media-card").start()
                    if result and not cancelled():
                        if command.kind in {'task', 'code_task', 'clarified_task', 'resume_task'}:
                            state = self.task_state.snapshot() or {}
                            self.knowledge.record_pair(state.get('goal') or command.value, str(result), kind='task')
                        elif command.kind not in QUIET_KINDS:
                            from .memory_curator import describe
                            self.knowledge.record_pair(describe(command), str(result), kind='task')
                        self.report("action", result)
                        if command.kind in {"task", "code_task", "clarified_task", "resume_task", "open", "browse", "browser_search",
                                            "create", "create_in_folder", "modify_in_folder", "delete_in_folder",
                                            "play_media", "spotify_control", "spotify_open_playlist", "close_app",
                                            "write_help", "write_text", "compose_text"} or (
                                command.kind == "media_control" and command.value == "status"):
                            if not str(result).startswith("Task paused, waiting for your answer"):
                                self.report("spoken_reply", result)  # The question itself was already spoken.
            except Exception as exc:
                if generation in self.superseded_generations and generation != self.generation:
                    self.report("state", "Previous task replaced by your newer request.")
                    self.superseded_generations.discard(generation)
                elif token.is_set() or generation != self.generation:
                    self.report("state", "Task cancelled.")
                else:
                    self.report("warning", str(exc))
                    if command.kind in QUEUED_ANNOUNCED:
                        # In a spoken conversation an unexplained silence is a failure too.
                        title = (command.value or "that").splitlines()[0][:80]
                        self.report("spoken_reply", "I couldn't finish " + title + ". " + str(exc)[:200])
            finally:
                from .progress import status
                with self.queue_lock:
                    self.current_item = None
                status(self.report, 'Ready' if generation == self.generation and not token.is_set() else 'Cancelled', active=False)
                self.superseded_generations.discard(generation)
                self.queue.task_done()
