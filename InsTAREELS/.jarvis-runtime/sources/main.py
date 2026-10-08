import json
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import queue
import threading
import time

from jarvis.display import enable_high_dpi
enable_high_dpi()  # Must precede Tk/native window creation, including verification entry points.

# Publish actual interpreter identity before loading UI/native dependencies.
_session = os.environ.get("JARVIS_SESSION_ID")
if _session and os.environ.get("JARVIS_UI_VERIFY") != "1":
    _runtime = Path(__file__).resolve().parent / ".jarvis-runtime"
    _runtime.mkdir(exist_ok=True)
    (_runtime / ("heartbeat-" + _session + ".json")).write_text(json.dumps({
        "session": _session, "pid": os.getpid(), "at": time.time(), "status": "starting"}), encoding="utf-8")
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from jarvis.actions import Actions, Desktop
from jarvis.audio import Listener
from jarvis.engine import Engine
from jarvis.commands import Command
from jarvis.speech import Speech
from jarvis.recovery import Watchdog, OllamaService, restart_thread, record, ui_loop

BASE = Path(__file__).resolve().parent


class App:
    def __init__(self, root):
        self.root = root
        self.config = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
        if os.environ.get("JARVIS_UI_VERIFY") == "1":
            self.config["memory"] = {"enabled": False}
            self.config['_ui_verification'] = True
        self.events = queue.Queue()
        self.closing = False
        self.listening_requested = False
        self.repair_offset = 0
        from jarvis.runtime_health import RuntimeHealth
        self.runtime_health = RuntimeHealth()
        self.speech = Speech(self.config.setdefault("speech", {"enabled": True, "language": "auto"}), self.report)
        self.speech.start()
        self.listener = None
        self.session = 0
        self.actions = Actions(self.config, BASE, self.report, Desktop())
        self.actions.start()
        anticipation_busy = self.actions.anticipation.busy
        self.actions.anticipation.busy = lambda: (anticipation_busy() or self.speech.speaking.is_set()
            or bool(getattr(self, 'capture_count', 0)) or bool(getattr(self, 'ui_activity', '')))
        self.external_handle = 0
        self.actions.external_handle = lambda: self.external_handle
        self.capture_count = 0
        self.command_window = None
        self.actions.knowledge.screen_handle = lambda: self.external_handle
        from jarvis.interface import build_interface
        build_interface(self)
        self.load_microphones()
        self.actions.approval_handler = self.request_approval
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.panel.withdraw()
        root.after(40, self.animate_island)
        root.after(150, self.exclude_orb_from_capture)
        root.after(300, self.remember_external_window)
        root.after(80, self.drain)
        self.watchdog = Watchdog(self.report)
        selector = self.actions.knowledge.context_selector
        if selector:
            self.watchdog.register('Context selector', selector.healthy, selector.repair,
                lambda: not self.closing and not selector.closed.is_set() and selector.options['enabled'])
        self.watchdog.register('Anticipation', self.actions.anticipation.healthy,
            self.actions.anticipation.repair,
            lambda: not self.closing and not self.actions.anticipation.closed.is_set()
                and self.actions.anticipation.options['enabled']
                and not self.actions.anticipation.paused
                and not self.actions.anticipation.microphone_stopped)
        self.watchdog.register('Realtime observations', self.actions.realtime.healthy,
            self.actions.realtime.repair,
            lambda: not self.closing and self.actions.realtime.options['enabled']
                and not self.actions.realtime.closed.is_set() and not self.actions.realtime.paused
                and not self.actions.realtime.microphone_stopped and not self.actions.realtime.storage_failed)
        self.watchdog.register('Island media observations',self.desk.media.healthy,self.desk.media.repair,
            lambda:not self.closing and not self.desk.media.closed)
        self.ollama_service = OllamaService()
        from jarvis.model_recovery import ModelRecovery
        self.model_recovery = ModelRecovery(BASE, self.config, self.report, lambda: self.closing)
        self.watchdog.register("Ollama", self.ollama_service.healthy, self.ollama_service.repair,
            lambda: not self.closing and (self.config.get("brain", {}).get("enabled")
                or self.config.get("knowledge", {}).get("enabled") or self.config.get("command_cleanup", {}).get("enabled")
                or self.config.get('context_selector', {}).get('enabled')))
        for name, worker in (("Action worker", self.actions), ("Question worker", self.actions.knowledge), ("Speech worker", self.speech)):
            self.watchdog.register(name, lambda worker=worker: worker.thread.is_alive(),
                lambda worker=worker, name=name: restart_thread(worker, name), lambda: not self.closing)
        self.watchdog.register("Microphone", self.listener_healthy, self.repair_listener,
            lambda: self.listening_requested and not self.closing)
        self.watchdog.register("UI Automation worker", self.actions.ui_healthy, self.actions.repair_ui,
            lambda: not self.closing and not self.actions.closed.is_set())
        self.watchdog.register("Browser automation worker", self.actions.browser_healthy, self.actions.repair_browser,
            lambda: not self.closing and not self.actions.closed.is_set())
        self.watchdog.register("Configured models", self.model_recovery.healthy, self.model_recovery.repair,
            lambda: not self.closing)
        from jarvis.harness import healthy as harness_healthy, repair as repair_harness
        self.watchdog.register("Harness inference", lambda: harness_healthy(self.actions.brain.client),
            lambda: repair_harness(self.actions.brain.client),
            lambda: not self.closing and not self.actions.closed.is_set()
                and self.config.get('brain', {}).get('harness', {}).get('enabled', False))
        self.watchdog.register("God's Eye service", self.gods_eye_healthy, self.repair_gods_eye,
            lambda: not self.closing and self.actions.gods_eye_view is not None)
        self.watchdog.register('Development preview',
            lambda: self.actions.development_tools is None or self.actions.development_tools.healthy(),
            lambda: self.actions.development_tools is None or self.actions.development_tools.repair(),
            lambda: not self.closing and not self.actions.closed.is_set())
        if not self.config.get('_ui_verification', False):
            self.watchdog.start()
            self.root.after(100, self.runtime_tick)
        if os.environ.get("JARVIS_RESUME_TASK") != "1" and os.environ.get("JARVIS_UI_VERIFY") != "1":
            self.root.after(350, self.greet_startup)
        if os.environ.get("JARVIS_AUTOLISTEN") == "1" and not self.config.get('_ui_verification', False):
            self.root.after(600, self.toggle_listening)
        if os.environ.get("JARVIS_RESUME_TASK") == "1" and not self.config.get('_ui_verification', False):
            self.root.after(1200, self.resume_interrupted_task)
        elif not self.config.get('_ui_verification', False) and self.actions.task_state.unfinished():
            self.report("repair", "Unfinished task retained. Say resume last task to inspect and continue it.")

    def resume_interrupted_task(self):
        if not self.closing and self.actions.generation == 0 and self.actions.queue.empty():
            self.actions.submit(Command("resume_task", extra="automatic"))

    def greet_startup(self):
        def deliver():
            greeting = self.actions.knowledge.quick.startup_greeting()
            if not self.closing:
                self.report("answer", greeting)
        threading.Thread(target=deliver, name="jarvis-startup-greeting", daemon=True).start()

    def listener_healthy(self):
        if not self.listener or not self.listener.thread.is_alive():
            return False
        audio_limit = 90 if self.listener.capture_started else 300
        return time.monotonic() - self.listener.last_audio < audio_limit and (
            self.listener.decode_started is None or time.monotonic() - self.listener.decode_started < 180)

    def repair_listener(self):
        if self.listener and self.listener.thread.is_alive():
            self.listener.stop()
            if self.actions.task_active:
                return False  # Do not sacrifice a running task to repair unrelated audio resources.
            if os.environ.get("JARVIS_SUPERVISED") == "1":
                record(BASE, "Microphone/decoder stalled; restarting Jarvis to release its audio and CUDA resources.")
                os._exit(72)
            return False
        self.report("restart_listener", "")
        return False

    def gods_eye_healthy(self):
        from jarvis.gods_eye_view import ready
        return ready()

    def repair_gods_eye(self):
        service = self.actions.gods_eye_view
        service.close()
        service.start(lambda: self.closing)
        return self.gods_eye_healthy()

    def runtime_tick(self):
        if self.closing or self.config.get('_ui_verification', False):
            return
        if self.actions.memory.error:
            self.report("warning", "Obsidian memory stopped: " + self.actions.memory.error)
            self.actions.memory.error = None
        try:
            runtime = BASE / ".jarvis-runtime"
            runtime.mkdir(exist_ok=True)
            if os.environ.get("JARVIS_SUPERVISED") == "1" and (runtime / "stop").exists():
                self.close()
                return
            session = os.environ.get("JARVIS_SESSION_ID")
            if session:
                temporary = runtime / ("heartbeat-" + session + ".tmp")
                temporary.write_text(json.dumps({"session": session, "pid": os.getpid(), "at": time.time(),
                    "status": "running", "listening_requested": self.listening_requested,
                    "health": self.runtime_health.snapshot(self)}), encoding="utf-8")
                os.replace(temporary, runtime / ("heartbeat-" + session + ".json"))
            repairs = runtime / "repairs.jsonl"
            if repairs.is_file():
                with repairs.open("r", encoding="utf-8") as source:
                    source.seek(self.repair_offset)
                    for line in source:
                        try:
                            self.log_line("repair", json.loads(line)["message"])
                        except (ValueError, KeyError):
                            pass
                    self.repair_offset = source.tell()
        except Exception:
            self.report("repair", "Runtime status update failed; will retry.")
        finally:
            if not self.closing:
                self.root.after(2000, self.runtime_tick)

    @ui_loop(40)
    def animate_island(self):
        listening = self.listener is not None and self.listener.thread.is_alive()
        speaking = self.speech.speaking.is_set()
        status = "WORKING" if self.actions.task_active or self.island.activity.active else "THINKING" if self.ui_activity else "SPEAKING" if speaking else "LISTENING" if listening else "STANDBY"
        self.hud_status.set(status)
        self.island.tick(status, self.level["value"], speaking=speaking, listening=listening)
        self.desk.tick(self.island.surface_open and not self.capture_count and self.panel.state()!='withdrawn')
        moving = any(abs(a-b) > .5 for a,b in zip(self.island.motion.size,self.island.motion.target))
        self.root.after(16 if moving else 33, self.animate_island)

    def toggle_panel(self, _event=None):
        if not self.island.expanded:
            self.show_panel()
        else:
            self.hide_panel()

    def show_panel(self):
        self.island.expand(True)

    def hide_panel(self):
        self.island.expand(False)
        self.island.message_until = self.island.attention_until = 0.
        self.panel.withdraw()

    def show_menu(self, event):
        self.menu.tk_popup(event.x_root, event.y_root)

    @staticmethod
    def exclude_window_from_capture(window):
        """Windows 10 2004+: omit this window from OS screen captures."""
        try:
            user = ctypes.WinDLL("user32", use_last_error=True)
            user.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
            user.GetAncestor.restype = wintypes.HWND
            user.SetWindowDisplayAffinity.argtypes = (wintypes.HWND, wintypes.DWORD)
            user.SetWindowDisplayAffinity.restype = wintypes.BOOL
            hwnd = user.GetAncestor(window.winfo_id(), 2)  # GA_ROOT, not Tk's client child.
            return bool(hwnd and user.SetWindowDisplayAffinity(hwnd, 0x11))
        except (AttributeError, OSError, tk.TclError):
            return False

    def exclude_orb_from_capture(self):
        self.exclude_window_from_capture(self.root)

    def remember_external_window(self):
        try:
            self.actions.live_app.observe_window(self.external_handle)
            import win32gui
            import win32process
            hwnd = win32gui.GetForegroundWindow()
            if (hwnd and win32gui.IsWindowVisible(hwnd)
                    and win32process.GetWindowThreadProcessId(hwnd)[1] != os.getpid()
                    and win32gui.GetWindowText(hwnd).strip()):
                self.external_handle = hwnd
                self.actions.live_app.observe_window(hwnd)
                self.actions.memory.observe_window(win32gui.GetWindowText(hwnd),
                    win32process.GetWindowThreadProcessId(hwnd)[1])
                self.actions.anticipation.observe_window(win32gui.GetWindowText(hwnd), hwnd)
            elif not hwnd or not win32gui.IsWindowVisible(hwnd) or not win32gui.GetWindowText(hwnd).strip():
                self.actions.anticipation.observe_window('', 0)
        except Exception:
            pass
        self.root.after(300, self.remember_external_window)

    def report(self, kind, message):
        if getattr(self, 'runtime_health', None) is not None:
            self.runtime_health.observe(kind, message)
        if kind in {'partial', 'final'} and message and getattr(self, 'actions', None) is not None:
            self.actions.anticipation.cancel()
            self.actions.realtime.cancel()
        if kind in {"action", "answer"} and isinstance(message, str):
            self.actions.memory.record("Jarvis " + kind, message)
        if kind == "state":
            self.actions.suggest_enabled = message.startswith("Awake")
            if self.actions.suggest_enabled:
                self.actions.suggest_until = time.monotonic() + self.config.get("wake_timeout_seconds", 90)
        elif kind in {"partial", "final"} and self.actions.suggest_enabled:
            self.actions.suggest_until = time.monotonic() + self.config.get("wake_timeout_seconds", 90)
        self.events.put((kind, message))

    def request_approval(self, kind, detail, cancelled):
        answer = {"approved": False}
        ready = threading.Event()
        self.report("approval", (kind, detail, answer, ready, cancelled))
        while not ready.wait(.1):
            if cancelled():
                return False
        return answer["approved"] and not cancelled()

    def show_command_prompt(self):
        self.desk.show('Console')
        self.show_panel()
        self.island.focus_pending = True

    def run_command(self):
        value = self.command_entry.get().strip()
        if value:
            self.command_entry.delete(0, "end")
            self.actions.submit(Command("run_command", value))

    def load_microphones(self):
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            hosts = sd.query_hostapis()
            labels = ["System default microphone"]
            selected = 0
            for index, device in enumerate(devices):
                if device["max_input_channels"] > 0:
                    self.mic_devices.append(index)
                    labels.append(f"{device['name']} Â· {hosts[device['hostapi']]['name']} [{index}]")
                    if self.config.get("microphone") in (index, device["name"]):
                        selected = len(labels) - 1
            self.mic_choice["values"] = labels
            self.mic_choice.current(selected)
        except Exception as exc:
            self.log_line("warning", f"Microphone discovery failed: {exc}")

    def log_line(self, kind, message):
        if not message:
            return
        self.log.configure(state="normal")
        self.log.insert("end", f"{time.strftime('%H:%M:%S')}  {kind.upper():8} {message}\n", (kind,))
        if int(self.log.index("end-1c").split(".")[0]) > 600:
            self.log.delete("1.0", "100.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    @ui_loop(80)
    def drain(self):
        for _ in range(300):
            try:
                kind, message = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'realtime_alert':
                text = message['message'] + ' Source: ' + message['reference']
                self.log_line('warning', text)
                if not self.actions.anticipation.busy() and not self.actions.realtime.microphone_stopped:
                    self.live.set(message['message'][:450])
                    self.island.notify('warning', message['message'])
                    self.speech.say(message['message'])
                continue
            self.island.notify(kind, message)
            self.desk.notify(kind,message)
            if kind == 'anticipation':
                continue  # Silent preparations appear only in Prepared; never speak/pop up.
            if kind.startswith('island_'):
                continue
            if kind == 'task_status':
                continue  # Live metadata is shown in the header; never log generated code chunks.
            elif kind == 'answer_stream':
                self.ui_activity = 'thinking' if message.get('active', True) else ''
                continue  # UI-thread preview only; never speak/log/store every partial token.
            elif kind == 'answer_error':
                self.ui_activity = ''
                self.log_line('warning', message)
                continue
            elif kind == "partial":
                if message:
                    self.live.set(message)
            elif kind == "state":
                self.state.set(message)
            elif kind == "screen_capture":
                if self.capture_count == 0:
                    self.hide_panel()
                    self.root.withdraw()
                self.capture_count += 1
            elif kind == "screen_capture_done":
                if self.capture_count:
                    self.capture_count -= 1
                if self.capture_count == 0 and self.root.state() == "withdrawn":
                    self.root.deiconify()
                    self.root.attributes("-topmost", True)
                    self.exclude_orb_from_capture()
            elif kind == "screen":
                self.log_line(kind, message)
            elif kind == "approval":
                continue  # Nonblocking explicit approval card owns this decision.
            elif kind == "command_output":
                if self.command_window and self.command_window.winfo_exists():
                    self.command_output.configure(state="normal")
                    self.command_output.insert("end", message + "\n\n")
                    self.command_output.see("end")
                    self.command_output.configure(state="disabled")
                self.log_line("command", message[-1000:])
            elif kind == "show_command_prompt":
                self.show_command_prompt()
            elif kind == "question":
                self.question.set(message[:700])
                self.log_line(kind, message)
            elif kind in {"thinking", "answer"}:
                self.ui_activity = "thinking" if kind == "thinking" else ""
                self.log_line(kind, message)
                if kind == "answer":
                    self.live.set(message[:450])
                    self.speech.say(message)
            elif kind == "spoken_reply":
                self.ui_activity = ""
                self.live.set(message[:450])
                self.speech.say(message)
            elif kind == "level":
                self.level["value"] = message
            elif kind == "backend":
                self.backend.set(message)
                self.log_line(kind, message)
            elif kind in {"fatal", "listener_stopped"}:
                self.state.set("Microphone off")
                self.toggle.configure(text="Start listening")
                self.mic_choice.configure(state="readonly")
                self.level["value"] = 0
                self.log_line(kind, message)
            elif kind == "restart_listener":
                if self.listening_requested and (not self.listener or not self.listener.thread.is_alive()):
                    self.toggle_listening()
            elif kind == "repair":
                record(BASE, message)
            else:
                self.log_line(kind, message)
        self.root.after(80, self.drain)

    def toggle_listening(self):
        if self.config.get('_ui_verification', False):
            return
        if self.listener and self.listener.thread.is_alive():
            self.stop()
            return
        self.session += 1
        self.listening_requested = True
        self.actions.anticipation.microphone_started()
        self.actions.realtime.microphone_started()
        session = self.session
        self.config["microphone"] = self.mic_devices[self.mic_choice.current()]
        (BASE / "config.json").write_text(json.dumps(self.config, indent=2) + "\n", encoding="utf-8")
        self.mic_choice.configure(state="disabled")
        if not self.actions.task_active:
            self.actions.desktop.target = None
            self.actions.typing_failed = False
            self.actions.open_target_pending = False
        # Generation check also prevents a stopping recognizer enqueueing new work.
        def submit(command):
            if session == self.session:
                self.speech.interrupt()
                self.actions.submit(command)
        engine = Engine(submit, self.report, self.config.get("wake_timeout_seconds", 90))
        from jarvis.voice_input import VoiceInput
        from jarvis.command_cleanup import CommandCleanup
        voice_input = VoiceInput(self.speech)
        self.listener = Listener(BASE / self.config["model_path"], self.config.get("microphone"), engine, self.report, self.config["whisper"], activate_on_start=True,
                                 playback=self.speech.output_recent, input_filter=voice_input.filter,
                                 references=self.speech.output_references,
                                 command_cleanup=CommandCleanup(self.config.get('command_cleanup'), self.report))
        self.listener.start()
        self.toggle.configure(text="Stop listening")

    def stop(self):
        realtime = getattr(getattr(self, 'actions', None), 'realtime', None)
        if realtime is not None:
            realtime.cancel(microphone=True)
        anticipation = getattr(getattr(self, 'actions', None), 'anticipation', None)
        if anticipation is not None:
            anticipation.cancel(microphone=True)
        if getattr(self,'desk',None) is not None:
            self.desk.cancel_approvals()
            self.desk.media.repair()  # Cancel only an owned outstanding media child; never replay it.
        self.listening_requested = False
        self.session += 1
        if self.listener:
            self.listener.stop()
        self.actions.cancel()
        self.speech.cancel()
        self.ui_activity = ""
        self.state.set("Stopping microphoneâ€¦")
        self.toggle.configure(text="Start listening")

    def preview_command(self):
        self.desk.show('History', reveal=True)
        self.show_panel()
        engine = Engine(lambda c: self.log_line("preview", repr(c)), self.log_line)
        engine.activate()
        engine.feed(self.preview.get(), final=True)

    def ask_question(self):
        text = self.preview.get().strip()
        if text:
            self.actions.submit(Command("ask", text))

    def send_input(self):
        """Enter uses the same command/question routing as spoken instructions."""
        text = self.preview.get().strip()
        if text:
            from jarvis.audio import command_text
            engine = Engine(self.actions.submit, self.report)
            engine.activate()
            engine.feed(command_text(text), final=True)

    def ask_screen(self):
        text = self.preview.get().strip() or "What is visible in this window?"
        self.report("question", text)
        self.actions.knowledge.submit(text, screen=True)

    def do_task(self):
        text = self.preview.get().strip()
        if text:
            self.actions.submit(Command("task", text))

    def close(self):
        self.closing = True
        self.desk.close()
        if os.environ.get("JARVIS_SUPERVISED") == "1" and not self.config.get('_ui_verification', False):
            (BASE / ".jarvis-runtime" / "stop").touch()
        self.watchdog.close()
        self.model_recovery.close()
        self.stop()
        self.speech.close()
        self.actions.close()
        self.root.destroy()

    def save_speech_settings(self, _event=None):
        self.speech.options["enabled"] = self.speak_enabled.get()
        if not self.speech.options["enabled"]:
            self.speech.cancel()
        language = {"Auto": "auto", "English": "en", "Hindi": "hi"}[self.answer_language.get()]
        self.speech.options["language"] = language
        self.config["knowledge"]["answer_language"] = language
        if not self.config.get('_ui_verification', False):
            (BASE / "config.json").write_text(json.dumps(self.config, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    App(tk.Tk()).root.mainloop()
