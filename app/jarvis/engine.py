"""Incremental command boundaries for spoken commands.

Partial hypotheses may change. All external actions wait for final ASR speech.
Stable partials may prepare a deterministic intent category only. There is no
dictation mode: "write ..." is one command (composed or exact text), and
free speech is typed only while the push-to-write keys are held.
"""
import re
import time
import threading
from .commands import Command, parse

WAKE = re.compile(r"(?:\b(?:hey\s+)?jarvis\b|જાર્વિસ|जार्विस)", re.I)
LEADING_WAKE = re.compile(r"^\W*(?:(?:hey|hi|ok|okay|yo)\W+)?(?:jarvis\b|જાર્વિસ|जार्विस)", re.I)
BOUNDARY = re.compile(r"\s+(?:and then|then|next command)\s+", re.I)
OPEN_PREFIX = re.compile(r"^(?:(?:please|can you|could you|would you)\s+)*(?:open|launch|start)\s+", re.I)
AND_WRITE = re.compile(r"\s+and\s+(?=(?:please\s+)?(?:write|type|click|select|choose)\b)", re.I)
STOP = re.compile(r"\b(?:go to sleep|stop listening|cancel|stop all tasks)\b", re.I)
# Kept whole (never split on "then") and run only from final speech.
WHOLE = {"blender_request", "ask", "task", "code_task", "toolkit", "anticipation", "realtime", "windows_command", "windows_catalog", "ability_run",
         "write_text", "compose_text", "whatsapp_send", "whatsapp_reply", "messenger_send", "memory_save",
         "memory_forget", "memory_list", "memory_conversations",
         # Everyday phrasings from intent_catalog.py describe one request even when they say "then".
         "behavior", "conversation_style", "jarvis_status", "system_info", "whatsapp_read", "media_related",
         "memory_summarize", "messenger_focus", "gods_eye_show", "gods_eye_camera", "gods_eye_explain", "gods_eye_cameras",
         "cognition_predict", "screen_info", "awareness_control", "project", "code_intel"}
FINAL_ONLY = WHOLE | {"cloud_control", "run_command", "modify", "browse", "browser_search", "context_search", "media_search",
    "media_control", "play_media", "spotify_request", "spotify_control", "spotify_open_playlist", "spotify_volume", "close_app",
    "forget_chat", "delete", "rename", "click_control", "select_context", "choose_control", "list_controls",
    "confirm_suggestion", "suggest_control", "forget_ui_memory", "cancel_task"}


class Engine:
    def __init__(self, submit, report, timeout=90):
        self.submit, self.report, self.timeout = submit, report, timeout
        self.active = False
        self.last_speech = 0.0
        self.done = {}
        self.pending = {}
        self.segment_wake = False
        self.suppressed = False
        self.last_open = None
        self.lock = threading.RLock()

    def reset(self):
        with self.lock:
            self.active = False
            self._reset_segment()

    def activate(self, now=None):
        """A deliberate Start listening click also wakes the command engine."""
        with self.lock:
            self.reset()
            self.active = True
            self.last_speech = time.monotonic() if now is None else now
            self.report("state", "Awake · say a command, for example open notepad")

    def _reset_segment(self):
        self.opened = None
        self.done.clear()
        self.pending.clear()
        self.segment_wake = False
        self.suppressed = False

    def feed(self, text, final=False, now=None, raw=None):
        with self.lock:
            return self._feed(text,final,now,raw)

    def _feed(self, text, final=False, now=None, raw=None):
        now = time.monotonic() if now is None else now
        text = " ".join(text.split())
        if self.suppressed:
            if final:
                self._reset_segment()
            return
        wake = WAKE.search(text)
        if wake and self.active and not self.segment_wake and not LEADING_WAKE.match(text):
            wake = None  # Mid-sentence "Jarvis" during a conversation is part of what was said.
        if wake:
            if not self.active:
                self.report("state", "Awake · ready for commands")
            self.active = self.segment_wake = True
            text = text[wake.end():].strip(" ,.")
        elif self.segment_wake:
            # A revised hypothesis lost its wake word. Never reinterpret it.
            if final:
                self._reset_segment()
            return
        elif self.active and now - self.last_speech > self.timeout:
            self.active = False
            self.report("state", "Listening for Jarvis")
        if not self.active:
            if final:
                if text:
                    self.report("ignored", "Waiting for wake word. Say 'Jarvis open notepad' to activate commands.")
                self._reset_segment()
            return
        if text or wake:
            self.last_speech = now
        from .task_policy import queue_request
        explicit_queue = queue_request(text) or queue_request(raw or '')
        free_text = getattr(self, 'free_text', None)
        if final and text and free_text is not None and free_text() and not STOP.search(text) and not explicit_queue:
            # A question is waiting for words (a name, an email address, a message): pass them through whole,
            # never reinterpreted as a command. "Cancel" / "stop" still go through normal parsing.
            self._dispatch(Command("whatsapp_answer", text))
            self._reset_segment()
            return
        if not final:
            # Never dispatch even an apparently complete clause from revisable speech.
            return
        from .task_policy import queue_request
        source = raw or text
        leading = LEADING_WAKE.match(source)
        if leading:
            source = source[leading.end():].strip(' ,.')
        if queue_request(source):
            self._dispatch(Command('task', source, 'queue_request'))
            self._reset_segment()
            return
        from .voice_runtime import normalize_intent
        language = re.fullmatch(r'(?:answer|reply|respond|speak) in (english|hindi|gujarati|french)|(?:use|enable) automatic language|reply in (?:the )?same language', text, re.I)
        if language:
            selected = {'english': 'en', 'hindi': 'hi', 'gujarati': 'gu', 'french': 'fr'}.get((language[1] or '').lower(), 'auto')
            self.report('voice_language', selected)
            self._reset_segment()
            return
        text = normalize_intent(text)
        # Whisper may finalize 'open notepad' before the next 'and write ...'.
        continued = bool(re.match(r"^and\s+(?=(?:please\s+)?(?:write|type)\b)", text, re.I))
        text = re.sub(r"^and\s+(?=(?:please\s+)?(?:write|type|click|select|choose)\b)", "", text, flags=re.I)
        clauses = []
        try:
            whole = parse(text).kind in WHOLE
        except ValueError:
            whole = False
        for part in ([text] if whole else BOUNDARY.split(text)):
            # A planned multi-step task stays intact, including its exact text.
            clauses.extend(AND_WRITE.split(part, maxsplit=1) if not whole and OPEN_PREFIX.match(part) else [part])
        for index, clause in enumerate(clauses):
            complete = final or index < len(clauses) - 1
            clause = clause.strip()
            if not whole and index < len(clauses) - 1:
                clause = clause.rstrip(',;').rstrip()  # punctuation before a spoken command boundary
            if not clause:
                continue
            if index in self.done:
                if self.done[index] != clause:
                    self.report("warning", "Speech revised after a command was sent; remaining actions skipped.")
                    self.suppressed = True
                    break
                continue
            # Never act on deletion/rename/writing from a revisable partial.
            if index in self.pending and not final:
                continue
            if not complete:
                continue
            try:
                command = parse(clause)
                if raw:
                    from .writing import with_original_case
                    command = with_original_case(command, raw)
                if command.kind == "open":
                    self.opened = command.value
                    self.last_open = (command.value, now)
                if (command.kind in {"write_text", "compose_text"} and not index and continued
                        and self.last_open and now - self.last_open[1] < 15):
                    self.opened = self.last_open[0]  # "open X" and "and write ..." arrived as two segments.
                if command.kind in {"write_text", "compose_text"} and (index or continued) and getattr(self, "opened", None):
                    # "open notepad and write ..." writes into Notepad, never the previous window.
                    import json
                    data = json.loads(command.extra or "{}")
                    if not data.get("target"):
                        command = Command(command.kind, command.value, json.dumps({**data, "target": self.opened, "tail": ""}))
                if not final and (command.kind in FINAL_ONLY or self.pending):
                    self.pending[index] = clause
                    continue
                self._dispatch(command)
                self.done[index] = clause
            except ValueError as exc:
                if str(exc).startswith("Command not understood:"):
                    if final:
                        # Unrecognised speech may be conversation, not a task; Actions decides.
                        unparsed = Command("task", clause, "unparsed")
                        if raw:  # Keep the speaker's/typist's capitals when the words are the same.
                            from .writing import with_original_case
                            unparsed = with_original_case(unparsed, raw)
                        self._dispatch(unparsed)
                        self.done[index] = clause
                    else:
                        self.pending[index] = clause
                    continue
                self.report("warning", str(exc))
                self.done[index] = clause
            if self.suppressed:
                break
        if final:
            self._reset_segment()

    def _dispatch(self, command):
        if command.kind in {"sleep", "end_conversation"}:
            self.active = False
            self.suppressed = True
        self.submit(command)
