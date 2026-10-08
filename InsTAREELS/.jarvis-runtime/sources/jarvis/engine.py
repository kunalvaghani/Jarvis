"""Incremental command boundaries and conservative streaming dictation.

Partial hypotheses may change. Only complete clauses separated by 'then'
are committed early; delete/rename wait for a final ASR segment. Dictation
uses a common prefix, retaining three words until a later update.
"""
import re
import time
from .commands import Command, parse

WAKE = re.compile(r"\b(?:hey\s+)?jarvis\b", re.I)
BOUNDARY = re.compile(r"\s+(?:and then|then|next command)\s+", re.I)
OPEN_PREFIX = re.compile(r"^(?:(?:please|can you|could you|would you)\s+)*(?:open|launch|start)\s+", re.I)
AND_WRITE = re.compile(r"\s+and\s+(?=(?:please\s+)?(?:write|type|dictate|click|select|choose)\b)", re.I)
STOP = re.compile(r"\b(?:stop dictation|stop writing|stop typing|go to sleep|stop listening|cancel|stop all tasks)\b", re.I)


class Engine:
    def __init__(self, submit, report, timeout=90):
        self.submit, self.report, self.timeout = submit, report, timeout
        self.active = False
        self.dictating = False
        self.last_speech = 0.0
        self.done = {}
        self.typed = {}
        self.previous = {}
        self.pending = {}
        self.segment_wake = False
        self.suppressed = False
        self.started_dictation = set()

    def reset(self):
        self.active = self.dictating = False
        self._reset_segment()

    def activate(self, now=None):
        """A deliberate Start listening click also wakes the command engine."""
        self.reset()
        self.active = True
        self.last_speech = time.monotonic() if now is None else now
        self.report("state", "Awake · say a command, for example open notepad")

    def _reset_segment(self):
        self.done.clear()
        self.typed.clear()
        self.previous.clear()
        self.pending.clear()
        self.segment_wake = False
        self.suppressed = False
        self.started_dictation.clear()

    def feed(self, text, final=False, now=None):
        now = time.monotonic() if now is None else now
        text = " ".join(text.split())
        if self.suppressed:
            if final:
                self._reset_segment()
            return
        wake = WAKE.search(text)
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
            self.active = self.dictating = False
            self.report("state", "Listening for Jarvis")
        if not self.active:
            if final:
                if text:
                    self.report("ignored", "Waiting for wake word. Say 'Jarvis open notepad' to activate commands.")
                self._reset_segment()
            return
        if text or wake:
            self.last_speech = now
        if not self.dictating:
            # Whisper may finalize 'open notepad' before the next 'and write'.
            text = re.sub(r"^and\s+(?=(?:please\s+)?(?:write|type|dictate|click|select|choose)\b)", "", text, flags=re.I)
        clauses = []
        try:
            is_question = parse(text).kind in {"ask", "task", "code_task", "toolkit", "anticipation", "realtime", "windows_command", "windows_catalog"} and not self.dictating
        except ValueError:
            is_question = False
        for part in ([text] if is_question else BOUNDARY.split(text)):
            # A planned multi-step task stays intact, including its exact file text.
            clauses.extend(AND_WRITE.split(part, maxsplit=1) if not is_question and OPEN_PREFIX.match(part) else [part])
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
            # Never act on deletion/rename from a revisable partial.
            if index in self.pending and not final:
                continue
            try:
                if self.dictating:
                    control = STOP.search(clause)
                    payload = clause[:control.start()].strip() if control else clause
                    self._dictate(index, payload, complete)
                    if control and complete:
                        self.dictating = False
                        self._dispatch(parse(control[0]))
                    if complete:
                        self.done[index] = clause
                elif complete:
                    command = parse(clause)
                    if self.typed.get(index) and command.kind != "dictate":
                        raise ValueError("Speech changed after dictation began; revised command skipped.")
                    if not final and (command.kind in {"windows_command", "windows_catalog", "anticipation", "realtime", "task", "code_task", "toolkit", "run_command", "modify", "browse", "browser_search", "context_search", "media_search", "media_control", "play_media", "spotify_control", "spotify_open_playlist", "spotify_volume", "close_app", "ask", "forget_chat", "delete", "rename", "click_control", "select_context", "choose_control", "list_controls", "confirm_suggestion", "suggest_control", "forget_ui_memory"} or self.pending):
                        self.pending[index] = clause
                        continue
                    if command.kind == "dictate":
                        self._begin_dictation(index)
                        self.dictating = True
                        control = STOP.search(command.value)
                        payload = command.value[:control.start()].strip() if control else command.value
                        self._dictate(index, payload, True)
                        if control:
                            self.dictating = False
                            self._dispatch(parse(control[0]))
                        else:
                            self.report("state", "Dictating · say stop dictation then your next command")
                    else:
                        self._dispatch(command)
                    self.done[index] = clause
                elif not self.pending:
                    m = re.match(r"^(?:please )?(?:write|type|dictate) (.*)", clause, re.I)
                    if m:
                        self._begin_dictation(index)
                        control = STOP.search(m[1])
                        self._dictate(index, m[1][:control.start()].strip() if control else m[1], False)
            except ValueError as exc:
                if not self.dictating and str(exc).startswith("Command not understood:"):
                    if final:
                        self._dispatch(Command("task", clause))
                        self.done[index] = clause
                    else:
                        self.pending[index] = clause
                    continue
                if complete:
                    self.report("warning", str(exc))
                    self.done[index] = clause
            if self.suppressed:
                break
        if final:
            self._reset_segment()

    def _dispatch(self, command):
        if command.kind == "sleep":
            self.active = self.dictating = False
            self.suppressed = True
        elif command.kind == "stop_dictation":
            self.dictating = False
            self.report("state", "Awake · ready for commands")
        self.submit(command)

    def _begin_dictation(self, index):
        if index not in self.started_dictation:
            self.submit(Command("begin_dictation"))
            self.started_dictation.add(index)

    def _dictate(self, index, text, final):
        words = text.split()
        sent = self.typed.get(index, [])
        if words[:len(sent)] != sent:
            raise ValueError("Dictation revised after typing; this segment was stopped to avoid duplicates.")
        previous = self.previous.get(index, [])
        common = 0
        for old, new in zip(previous, words):
            if old != new:
                break
            common += 1
        end = len(words) if final else min(common, max(0, len(words) - 3))
        if end > len(sent):
            self.submit(Command("type", " ".join(words[len(sent):end]) + " "))
            self.typed[index] = words[:end]
        self.previous[index] = words
