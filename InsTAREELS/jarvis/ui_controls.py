"""Voice UI matching and a bounded, cancellable Windows UI Automation worker."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from ctypes import wintypes
import ctypes
from difflib import SequenceMatcher


UNSAFE_INFERRED = re.compile(r"\b(delete|remove|erase|send|submit|publish|post|purchase|buy|pay|checkout|upload|transfer|permission|administrator|close)\b", re.I)
NAVIGATION = {"home", "shorts", "subscriptions", "you", "history", "search", "library", "explore", "trending", "settings", "sign in"}


def label_key(text):
    from .names import normalize
    return normalize(text.replace("&", ""))


def matches(controls, label):
    query = label_key(label)
    if not query:
        return []
    exact = [c for c in controls if label_key(c["name"]) == query]
    if exact:
        return exact
    # Profiles expose both an Open action and a More actions menu for the same name.
    profiles = [c for c in controls if label_key(c["name"]) == "open " + query.removeprefix("open ").removesuffix(" profile") + " profile"]
    if profiles:
        return profiles
    phrase = [c for c in controls if f" {query} " in f" {label_key(c['name'])} "]
    if phrase:
        return phrase
    from .names import rank, spelling_score
    labels = rank(query, [c["name"] for c in controls if not UNSAFE_INFERRED.search(c["name"])])
    # Never fuzzy-match opposite playback states or destructive controls.
    if query in {"pause", "play", "close", "delete", "remove"}:
        return []
    if UNSAFE_INFERRED.search(query):
        return []
    if labels:
        return [c for c in controls if c["name"] in labels and not UNSAFE_INFERRED.search(c["name"])]
    # Compare against word windows too: accessible labels often append a site or app name.
    if len(query) < 3:
        return []
    scored = []
    size = len(query.split())
    for control in controls:
        name = label_key(control["name"])
        if UNSAFE_INFERRED.search(name):
            continue
        words = name.split()
        windows = [" ".join(words[i:i + size]) for i in range(max(1, len(words) - size + 1))]
        score = max(max(SequenceMatcher(None, query, part).ratio(), spelling_score(query, part)) for part in windows)
        if score >= (.74 if len(query) <= 5 else .79):
            scored.append((score, control))
    if not scored:
        return []
    best = max(score for score, _ in scored)
    return [control for score, control in scored if score >= best - .05]


def _safe(control):
    return not UNSAFE_INFERRED.search(control["name"])


def _ordered(controls):
    return sorted(controls, key=lambda c: (c["rect"][1], c["rect"][0]))


def _category(controls, category, title=""):
    roles = {"button": {"Button", "SplitButton", "RadioButton", "CheckBox"},
             "link": {"Hyperlink"}, "option": {"Button", "SplitButton", "MenuItem", "ListItem", "RadioButton", "CheckBox", "ComboBox"},
             "item": {"ListItem", "TreeItem", "TabItem", "MenuItem"},
             "result": {"Hyperlink", "ListItem", "TreeItem"},
             "video": {"Hyperlink", "ListItem"}}
    choices = [c for c in controls if c["role"] in roles[category] and _safe(c)]
    if category == "video":
        choices = [c for c in choices if (len(label_key(c["name"])) >= 8
                   and label_key(c["name"]) not in NAVIGATION
                   and ("video" in label_key(c.get("context", ""))
                        or ("youtube" in title.casefold() and c["rect"][0] >= 120)))]
    if category == "result":
        choices = [c for c in choices if label_key(c["name"]) not in NAVIGATION]
    seen = set()
    ordered = []
    for control in _ordered(choices):
        key = label_key(control["name"])
        if key not in seen:
            ordered.append(control)
            seen.add(key)
    return ordered


def choice_text(controls):
    return "; ".join(f"{index}. {item['name']} ({item['role']})" + (f" — {item['context']}" if item.get("context") else "") for index, item in enumerate(controls, 1))


class UIControls:
    def __init__(self, desktop, runner=None, memory=None, external_handle=None):
        self.desktop = desktop
        self.runner = runner or self._worker
        self.pending = None
        self.memory = memory
        self.offer = None
        self.seen_contexts = set()
        self.last_handle = None
        self.external_handle = external_handle or (lambda: 0)

    def clear_pending(self):
        self.pending = None
        self.offer = None

    def suggest(self, cancelled=lambda: False, force=False):
        if not self.memory or cancelled():
            return None
        # Avoid querying accessibility until there is something to remember.
        if not self.memory.read()["contexts"]:
            return None
        handle = self._handle()
        if handle != self.last_handle:
            self.seen_contexts.clear()
            self.clear_pending()
            self.last_handle = handle
        if self.pending and time.monotonic() - self.pending["time"] < 45 and not force:
            return None
        snapshot = self.runner({"operation": "list", "handle": handle, "owner_pid": os.getpid()}, cancelled)
        context = snapshot.get("context")
        if not context or (context in self.seen_contexts and not force) or cancelled():
            return None
        self.seen_contexts.add(context)
        candidate = self.memory.candidate(context, snapshot["controls"])
        if candidate is None:
            return None
        control, verb = candidate
        self.desktop.target = handle
        self.pending = None
        self.offer = {"handle": handle, "signature": snapshot["signature"], "context": context,
                      "control": control, "verb": verb, "time": time.monotonic()}
        return f"You previously used '{control['name']}' in {snapshot.get('title', 'this app')}. Use it again? Say yes or no."

    def _activate(self, handle, snapshot, control, verb, cancelled):
        if cancelled():
            return "UI action cancelled"
        result = self.runner({"operation": "activate", "handle": handle, "owner_pid": os.getpid(),
            "signature": snapshot["signature"], "control": control, "verb": verb}, cancelled)
        self.desktop.target = handle
        if self.memory and not cancelled():
            context = snapshot.get("context")
            self.seen_contexts.add(context)
            self.last_handle = handle
            try:
                self.memory.remember(context, control, verb)
            except (OSError, ValueError) as exc:
                return result["message"] + f". Could not save button memory: {exc}"
        return result["message"]

    def answer(self, yes, cancelled):
        offer, self.offer = self.offer, None
        if not offer or time.monotonic() - offer["time"] > 45:
            raise ValueError("No current suggestion to confirm. Say suggest a button or name the option you want.")
        handle = self._handle()
        snapshot = self.runner({"operation": "list", "handle": handle, "owner_pid": os.getpid()}, cancelled)
        if handle != offer["handle"] or snapshot.get("context") != offer["context"]:
            raise ValueError("The app changed; the suggestion was cancelled. Say which option you want.")
        if not yes:
            choices = snapshot["controls"][:40]
            self.pending = {"handle": handle, "signature": snapshot["signature"], "time": time.monotonic(), "choices": choices, "verb": "select"}
            return "Which one would you like instead? Say its name or select option number: " + choice_text(choices)
        if snapshot["signature"] != offer["signature"] or offer["control"] not in snapshot["controls"]:
            raise ValueError("The options changed since I asked. Say suggest a button again or name your choice.")
        return self._activate(handle, snapshot, offer["control"], offer["verb"], cancelled)

    def _handle(self):
        foreground = self.desktop.user.GetForegroundWindow()
        pid = wintypes.DWORD()
        self.desktop.user.GetWindowThreadProcessId(foreground, ctypes.byref(pid))
        candidates = (self.desktop.target, self.external_handle()) if pid.value == os.getpid() else (foreground,)
        for hwnd in candidates:
            if hwnd and self.desktop.user.IsWindow(hwnd) and self.desktop.user.IsWindowVisible(hwnd):
                self.desktop.user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value != os.getpid():
                    return int(hwnd)
        raise ValueError("Select the destination app first, then say the button or option name.")

    def _worker(self, request, cancelled):
        if cancelled():
            raise RuntimeError("UI action cancelled")
        base = Path(__file__).resolve().parent.parent
        process = subprocess.Popen([sys.executable, "-m", "jarvis.ui_worker", json.dumps(request)],
            cwd=base, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            encoding="utf-8", errors="replace", creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.monotonic() + 20
        try:
            while True:
                if cancelled():
                    raise RuntimeError("UI action cancelled. Check the app before repeating it; a click may already have occurred.")
                if time.monotonic() >= deadline:
                    raise RuntimeError("The app's controls did not respond in time. Check the app before repeating the command.")
                try:
                    output, error = process.communicate(timeout=0.1)
                    break
                except subprocess.TimeoutExpired:
                    continue
            if process.returncode:
                raise RuntimeError(error.strip()[-700:] or "Windows UI Automation failed.")
            result = json.loads(output)
            if result.get("error"):
                raise ValueError(result["error"])
            return result
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()

    def execute(self, command, cancelled=lambda: False):
        if cancelled():
            return "UI action cancelled"
        if command.kind == "confirm_suggestion":
            return self.answer(command.value == "yes", cancelled)
        if command.kind == "suggest_control":
            return self.suggest(cancelled, force=True) or "No remembered option is available here yet. Say list buttons and choose one."
        if command.kind == "forget_ui_memory":
            if self.memory:
                self.memory.clear()
            self.clear_pending()
            self.seen_contexts.clear()
            return "Remembered button choices cleared."
        offer = self.offer
        self.offer = None
        handle = self._handle()
        snapshot = self.runner({"operation": "list", "handle": handle, "owner_pid": os.getpid()}, cancelled)
        controls = snapshot["controls"]
        verb = command.extra or "select"
        if command.kind == "select_context":
            ordinal, category = command.value.split(":", 1)
            if category not in {"video", "result", "option", "button", "item", "link"}:
                raise ValueError("Unknown selection category.")
            pending = self.pending
            current = (pending and time.monotonic() - pending["time"] <= 45
                       and pending["handle"] == handle and pending["signature"] == snapshot["signature"])
            if ordinal == "this" and offer and time.monotonic() - offer["time"] <= 45:
                if (offer["handle"] == handle and offer["signature"] == snapshot["signature"]
                        and offer["control"] in controls and _safe(offer["control"])):
                    self.pending = None
                    return self._activate(handle, snapshot, offer["control"], offer["verb"], cancelled)
            if category == "option" and pending and not current:
                self.pending = None
                raise ValueError("The app or its options changed. Say list buttons again.")
            if category == "option" and current:
                choices = [c for c in pending["choices"] if c in controls]
                verb = pending["verb"]
            else:
                choices = _category(controls, category, snapshot.get("title", ""))
            if ordinal == "this":
                choices = [c for c in choices if _safe(c)]
                pointer = wintypes.POINT()
                user = getattr(self.desktop, "user", None)
                if user and user.GetCursorPos(ctypes.byref(pointer)):
                    hits = [c for c in choices if c["rect"][0] <= pointer.x < c["rect"][2]
                            and c["rect"][1] <= pointer.y < c["rect"][3]]
                    if hits:
                        choices = [min(hits, key=lambda c: (c["rect"][2] - c["rect"][0]) * (c["rect"][3] - c["rect"][1]))]
                if len(choices) != 1:
                    if not choices:
                        raise ValueError("No matching visible option. Point to it or say its name.")
                    self.pending = {"handle": handle, "signature": snapshot["signature"], "time": time.monotonic(), "choices": choices[:40], "verb": verb}
                    return "Point to the option or say select option number: " + choice_text(choices[:40])
            else:
                index = int(ordinal) - 1
                if not 0 <= index < len(choices):
                    raise ValueError(f"Only {len(choices)} visible {category} choices were found. Say list buttons or name one.")
                choices = [choices[index]]
                if not _safe(choices[0]):
                    raise ValueError("Name that control explicitly to select it.")
        elif command.kind == "choose_control":
            pending, self.pending = self.pending, None
            if not pending or time.monotonic() - pending["time"] > 45:
                raise ValueError("Say list buttons or name a control first; the previous choices have expired.")
            if pending["handle"] != handle or pending["signature"] != snapshot["signature"]:
                raise ValueError("The app or its controls changed. Say list buttons again.")
            index = int(command.value) - 1
            if not 0 <= index < len(pending["choices"]):
                raise ValueError("That option number is not in the displayed list.")
            choices = [pending["choices"][index]]
            verb = pending["verb"]
        elif command.kind == "list_controls":
            choices = controls[:40]
        else:
            choices = matches(controls, command.value)
        if not choices:
            self.pending = None
            opposite = {"pause": "play", "play": "pause"}.get(label_key(command.value))
            if opposite and matches(controls, opposite):
                return "The player is already paused." if opposite == "play" else "The player is already playing."
            raise ValueError("No matching visible, enabled control. Open its menu/dropdown first or say list buttons. Some custom interfaces do not expose named controls.")
        if command.kind == "list_controls" or len(choices) > 1:
            choices = choices[:40]
            self.pending = {"handle": handle, "signature": snapshot["signature"], "time": time.monotonic(), "choices": choices, "verb": verb}
            return "Say select option number: " + choice_text(choices)
        self.pending = None
        if command.kind == "click_control" and label_key(command.value) != label_key(choices[0]["name"]):
            # Returned evidence makes the selected interpretation visible in the action log.
            result = self._activate(handle, snapshot, choices[0], verb, cancelled)
            return "Understood '" + command.value + "' as '" + choices[0]["name"] + "'. " + result
        return self._activate(handle, snapshot, choices[0], verb, cancelled)
