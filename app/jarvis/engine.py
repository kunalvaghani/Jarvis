"""Incremental command boundaries for spoken commands.

Partial hypotheses may change. Only complete clauses separated by 'then' are
committed early; most commands wait for a final ASR segment. There is no
dictation mode: "write ..." is one command (composed or exact text), and
free speech is typed only while the push-to-write keys are held.
"""
import re
import time
from .commands import Command, parse

WAKE = re.compile(r"\b(?:hey\s+)?jarvis\b", re.I)
LEADING_WAKE = re.compile(r"^\W*(?:(?:hey|hi|ok|okay|yo)\W+)?jarvis\b", re.I)
BOUNDARY = re.compile(r"\s+(?:and then|then|next command)\s+", re.I)
OPEN_PREFIX = re.compile(r"^(?:(?:please|can you|could you|would you)\s+)*(?:open|launch|start)\s+", re.I)
AND_WRITE = re.compile(r"\s+and\s+(?=(?:please\s+)?(?:write|type|click|select|choose)\b)", re.I)
STOP = re.compile(r"\b(?:go to sleep|stop listening|cancel|stop all tasks)\b", re.I)
# Kept whole (never split on "then") and run only from final speech.
WHOLE = {"ask", "task", "code_task", "toolkit", "anticipation", "realtime", "windows_command", "windows_catalog",
         "write_text", "compose_text", "whatsapp_send", "whatsapp_reply", "messenger_send"}
FINAL_ONLY = WHOLE | {"run_command", "modify", "browse", "browser_search", "context_search", "media_search",
    "media_control", "play_media", "spotify_control", "spotify_open_playlist", "spotify_volume", "close_app",
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

    def reset(self):
        self.active = False
        self._reset_segment()

    def activate(self, now=None):
        """A deliberate Start listening click also wakes the command engine."""
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
                        self._dispatch(Command("task", clause, "unparsed"))
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
