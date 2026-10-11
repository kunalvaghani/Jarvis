"""Screen pre-awareness: notice the app in front, offer the one thing you most likely want there, and do it.

Flow:
1. main.py reports every foreground change (observe). After you've stayed in an app for dwell_seconds,
   and only when Jarvis is listening, idle and not speaking, Jarvis reads the app's controls (learning its
   buttons) and asks the app's question once ("You're on YouTube. Want me to open one of the videos on screen?").
2. Your next words answer it (answer, called from Actions.submit before normal routing):
   - "yes" -> the app's mode: open a video named by one word of its title, start writing what you say,
     answer about the screen, press a named button, run a command, or type a sum into the calculator;
   - "no" -> fine, and that app isn't asked again for a while (three no's mute it until you resume);
   - anything else -> treated as the follow-up when it fits (for example just saying the word from a video's
     title), otherwise the offer is dropped and your words are handled normally.
3. The action runs on the task queue (kind "screen_act"), looking at the screen again first: nothing is pressed
   from a stale list, and destructive buttons (delete, send, buy...) are never pressed from a fuzzy match.

Private windows (mail, chats, banking, incognito, sign-in pages) never get unprompted questions.
"""
import json
import re
import threading
import time
from difflib import SequenceMatcher

from .app_knowledge import PROFILES, AppKnowledge, PRIVATE_TITLE, profile_for

YES = re.compile(r"^(?:yes|yeah|yep|yup|sure|ok(?:ay)?|alright|please|go ahead|do it|of course|why not|definitely|"
                 r"sounds good|yes please|sure thing|please do)\b[\s,.!]*(.*)$", re.I)
NO = re.compile(r"^(?:no|nope|nah|not now|no thanks|not really|later|maybe later|i'?m good|leave it|never ?mind|don'?t)\b", re.I)
STOP_WORDS = {"the", "a", "an", "one", "video", "that", "this", "open", "play", "please", "about", "with", "called", "named",
              "song", "on", "of", "to", "for", "it", "is", "i", "want", "watch", "show", "me", "click", "select", "jarvis"}
ORDINALS = {"first": 1, "1st": 1, "one": 1, "second": 2, "2nd": 2, "two": 2, "third": 3, "3rd": 3, "three": 3,
            "fourth": 4, "4th": 4, "four": 4, "fifth": 5, "5th": 5, "five": 5}
DEFAULTS = {"enabled": True, "dwell_seconds": 4, "cooldown_minutes": 10, "offer_seconds": 45, "ask_unknown_apps": True,
            "dictation_idle_seconds": 120}


def words(text):
    from .names import normalize
    return [w for w in normalize(text).split() if w not in STOP_WORDS]


NOT_VIDEO = re.compile(r"^(?:youtube(?: home)?|go to channel\b.*|.*\bchannel\b.*|home|shorts|subscriptions|you|history)$", re.I)


def videos(controls, title=""):
    """Video results on screen: YouTube's own video filter, minus the logo, channel links and channel names."""
    from .ui_controls import _category
    found = _category(controls, "video", title)
    return [c for c in found if not NOT_VIDEO.match(c["name"].strip()) and len(c["name"].split()) >= 3]


def match_titles(query, titles):
    """Indexes of the titles that best match a spoken word or phrase (exact words first, then near spellings)."""
    wanted = words(query)
    if not wanted:
        return []
    scored = []
    for index, title in enumerate(titles):
        have = words(title)
        if not have:
            continue
        total = 0.
        for word in wanted:
            best = max((1. if word == h else SequenceMatcher(None, word, h).ratio()) for h in have)
            if best >= (.84 if len(word) > 4 else .99):
                total += best
            elif any(h.startswith(word) and len(word) >= 3 for h in have):
                total += .8
        if total:
            scored.append((total, index))
    if not scored:
        return []
    top = max(score for score, _ in scored)
    return [index for score, index in sorted(scored, key=lambda x: -x[0]) if score >= top - .01]


def ordinal(text):
    found = re.search(r"\b(first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th|one|two|three|four|five|\d)\b", text.casefold())
    if not found:
        return None
    token = found[1]
    return int(token) if token.isdigit() else ORDINALS[token]


def safe_sum(expression):
    """Arithmetic only: digits, + - * / ( ) . % and spoken operators."""
    text = expression.casefold()
    for spoken, symbol in (("plus", "+"), ("minus", "-"), ("times", "*"), ("multiplied by", "*"), ("x", "*"),
                           ("divided by", "/"), ("over", "/"), ("percent of", "/100*"), ("percent", "/100")):
        text = re.sub(r"\b" + spoken + r"\b", symbol, text)
    text = re.sub(r"\b(?:what(?:'s| is)|calculate|work out|equals?|the|of)\b", "", text).replace("×", "*").replace("÷", "/")
    text = text.replace(",", "").strip(" ?=")
    if not text or not re.fullmatch(r"[\d\s.+\-*/()%]+", text):
        return None
    import ast
    import operator
    ops = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
           ast.Mod: operator.mod, ast.USub: operator.neg, ast.UAdd: operator.pos}

    def value(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in ops:
            return ops[type(node.op)](value(node.left), value(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in ops:
            return ops[type(node.op)](value(node.operand))
        raise ValueError("not arithmetic")
    try:
        result = value(ast.parse(text, mode="eval").body)
    except (ValueError, SyntaxError, ZeroDivisionError):
        return None
    return text.replace(" ", ""), (int(result) if float(result).is_integer() else round(result, 8))


class ScreenAwareness:
    def __init__(self, actions, options=None):
        self.actions = actions
        self.options = {**DEFAULTS, **(options or {})}
        self.enabled = bool(self.options["enabled"])
        self.knowledge = AppKnowledge(actions.base, getattr(actions, "apps", {}))
        self.can_offer = lambda: False  # Set by the app: listening, not speaking.
        self.focus = None  # {handle, title, exe, class, since}
        self.offer = None  # {key, mode, stage, handle, ...}
        self.asked = {}  # app key -> when it was last asked
        self.declined = {}  # app key -> consecutive no's
        self.muted = set()
        self.reading = False
        self.lock = threading.RLock()

    # --- watching ---------------------------------------------------------------------------------------------------
    def observe(self, handle, title, executable, window_class=""):
        with self.lock:
            if self.focus and self.focus["handle"] == handle and self.focus["title"] == title:
                return
            self.focus = {"handle": int(handle or 0), "title": title or "", "exe": executable or "", "class": window_class or "",
                          "since": time.monotonic()}

    def current(self):
        with self.lock:
            return dict(self.focus) if self.focus else None

    def busy(self):
        a = self.actions
        return bool(getattr(a, "current_item", None) or getattr(a, "pending_tasks", None) or getattr(a, "whatsapp_prompts", None)
                    or getattr(a, "pending_question", None) or getattr(a, "dictation_active", False)
                    or getattr(a, "approvals_waiting", 0) or getattr(a, "task_active", False))

    def tick(self):
        """Called a few times a second (main.py). Expires offers and asks when the moment is right."""
        if not self.enabled:
            return
        now = time.monotonic()
        offer = self.offer
        if offer and now - offer["time"] > self.options["offer_seconds"]:
            self.offer = None
        self._dictation_timeout(now)
        focus = self.current()
        if (self.offer or self.reading or not focus or now - focus["since"] < self.options["dwell_seconds"]
                or self.busy() or not self.can_offer()):
            return
        profile = profile_for(focus["exe"], focus["title"], focus["class"])
        key = self.knowledge.app_key(focus["exe"], focus["title"], focus["class"])
        if key in self.muted or now - self.asked.get(key, -1e9) < self.options["cooldown_minutes"] * 60:
            return
        if PRIVATE_TITLE.search(focus["title"]) or (profile and profile["private"] and profile.get("mode") not in {"command"}):
            return
        if profile is None and not self.options["ask_unknown_apps"]:
            return
        self.asked[key] = now
        self.reading = True
        threading.Thread(target=self._prepare, args=(focus, profile, key), name="Jarvis screen awareness", daemon=True).start()

    @staticmethod
    def profile(key):
        return next((p for p in PROFILES if p["key"] == key), {})

    def _snapshot(self, handle, cancelled=lambda: False):
        import os
        ui = self.actions._ui()
        return ui.runner({"operation": "list", "handle": handle, "owner_pid": os.getpid()}, cancelled)

    def _prepare(self, focus, profile, key, forced=False):
        """Read the screen, learn the buttons, and ask the app's question if it still makes sense."""
        try:
            snapshot = self._snapshot(focus["handle"])
            controls = snapshot.get("controls", [])
            if not (profile and profile["private"]):  # Chats and mail: never keep their labels.
                self.knowledge.learn(focus["exe"], focus["title"], controls, focus["class"])
            if self.current() is None or self.current()["handle"] != focus["handle"] or (self.busy() and not forced):
                return
            offer = {"key": key, "handle": focus["handle"], "title": focus["title"], "exe": focus["exe"], "class": focus["class"],
                     "stage": "confirm", "time": time.monotonic()}
            if profile and profile.get("question"):
                offer.update(mode=profile["mode"], question=profile["question"], profile=profile["key"])
                if profile["mode"] == "video":
                    shown = videos(controls, snapshot.get("title", ""))
                    if not shown:
                        return  # Nothing to open on this page yet.
                    offer["count"] = len(shown)
            elif profile is None or not profile.get("private"):
                buttons = self.knowledge.buttons(key, 6)
                if not buttons:
                    return
                name = profile["name"] if profile else re.sub(r"\.exe$", "", focus["exe"].split("\\")[-1], flags=re.I)
                offer.update(mode="click", profile=profile["key"] if profile else None,
                             question=f"Want me to press something in {name}? I can see {', '.join(buttons[:3])} and more.")
            else:
                return
            self.offer = offer
            self.actions.report("screen_offer", offer["question"])
        except Exception:
            pass  # A protected or closing window: just don't ask.
        finally:
            self.reading = False

    # --- answering --------------------------------------------------------------------------------------------------
    def answer(self, command):
        """Your reply to the open offer. True when it was consumed here."""
        offer = self.offer
        if not offer or time.monotonic() - offer["time"] > self.options["offer_seconds"]:
            self.offer = None
            return False
        if command.kind == "confirm_suggestion":
            text = command.value
        elif command.kind in {"task", "ask", "play_media", "open", "media_search", "click_control", "browser_search",
                              "context_search", "realtime", "spotify_search"}:
            text = (command.value or "").strip()
        else:
            self.offer = None  # A different request: drop the offer, handle it normally.
            return False
        text = re.sub(r"^(?:jarvis[, ]+)", "", text, flags=re.I).strip()
        profile = self.profile(offer.get("profile"))
        if offer["stage"] == "confirm":
            yes, no = YES.match(text), NO.match(text)
            if no:
                self.offer = None
                self.declined[offer["key"]] = self.declined.get(offer["key"], 0) + 1
                if self.declined[offer["key"]] >= 3:
                    self.muted.add(offer["key"])
                    self.actions.report("spoken_reply", "Okay. I'll stop asking about this app; say 'resume screen suggestions' to undo.")
                else:
                    self.actions.report("spoken_reply", "Okay.")
                return True
            self.declined.pop(offer["key"], None)
            rest = yes[1].strip() if yes else text  # "yes, the lofi one" or just "lofi".
            # Without a yes, only a short follow-up that isn't its own request counts ("lofi", "the second one").
            follow_up = command.kind in {"task", "play_media", "click_control", "open"} and len(text.split()) <= 6
            if not yes and (offer["mode"] not in {"video", "click", "command", "calc"} or not follow_up):
                self.offer = None
                return False
            if offer["mode"] in {"dictate", "screen", "run"}:
                self.offer = None
                self._queue(offer, "")
                return True
            if not rest:
                offer["stage"], offer["time"] = "detail", time.monotonic()
                self.actions.report("screen_offer", profile.get("followup") or "Go ahead.")
                return True
            self.offer = None
            self._queue(offer, rest)
            return True
        if offer["stage"] == "choose":
            choice = ordinal(text)
            self.offer = None
            if choice and 1 <= choice <= len(offer["choices"]):
                self._queue(dict(offer, chosen=offer["choices"][choice - 1]), offer["choices"][choice - 1])
            else:
                self._queue(offer, text)
            return True
        self.offer = None  # detail stage: this is the follow-up.
        self._queue(offer, text)
        return True

    def _queue(self, offer, detail):
        from .commands import Command
        data = {k: offer.get(k) for k in ("key", "mode", "handle", "title", "exe", "class", "profile", "chosen")}
        data["detail"] = detail
        self.actions.submit(Command("screen_act", json.dumps(data)))

    # --- acting -----------------------------------------------------------------------------------------------------
    def act(self, data, cancelled=lambda: False):
        profile = self.profile(data.get("profile"))
        mode, detail = data["mode"], (data.get("detail") or "").strip()
        if mode == "dictate":
            return self.start_dictation(data["handle"], cancelled)
        if mode in {"screen", "ask"}:
            question = profile.get("prompt", "") if mode == "screen" else detail
            if not question:
                return "Ask me anything about what's on screen."
            self._front(data["handle"])
            self.actions.knowledge.submit(question, screen=True)
            return ""
        if mode == "run":
            from .commands import parse
            self.actions.submit(parse(profile["run"]))
            return ""
        if mode == "command":
            from .commands import parse
            text, app = detail.strip(" ."), profile.get("app")
            # Messaging: "mom saying I'll be late" / "tell John that I'm on my way" -> "message mom on whatsapp saying ...".
            said = re.match(r"^(?:(?:send a message to|message|text|tell|send)\s+)?(.+?)\s*,?\s+(?:saying|that|to say)\s+(.+)$", text, re.I)
            if app and said:
                command_text = f"message {said[1]} on {app} saying {said[2]}"
            elif app and re.match(r"^(?:send|message|text|tell|reply)\b", text, re.I):
                command_text = text if app in text.casefold() else text + " on " + app
            else:
                command_text = profile["template"].format(x=text)
            try:
                command = parse(command_text)
            except ValueError:
                return "I didn't catch that. Try again with the full request."
            self.actions.submit(command)
            return ""
        if mode == "calc":
            worked = safe_sum(detail)
            if not worked:
                return "I can only type plain arithmetic into the calculator, like 25 times 4."
            expression, result = worked
            self._front(data["handle"])
            from .actions import Desktop
            desktop = getattr(self.actions, "desktop", None) or Desktop()
            desktop.target = None
            desktop.capture()
            desktop.type(expression + "=", cancelled)  # The calculator accepts typed sums; = shows the result.
            return f"{expression.replace('*', ' times ').replace('/', ' divided by ')} is {result}."
        if mode in {"video", "click"}:
            return self._press(data, profile, cancelled)
        return "I'm not sure what to do here."

    def _front(self, handle):
        from .window_focus import focus
        try:
            focus(int(handle))
        except Exception:
            pass

    def _press(self, data, profile, cancelled):
        import os
        from .ui_controls import _safe, label_key, matches
        handle, detail = int(data["handle"]), (data.get("detail") or "").strip()
        ui = self.actions._ui()
        self._front(handle)
        snapshot = ui.runner({"operation": "list", "handle": handle, "owner_pid": os.getpid()}, cancelled)
        controls = snapshot.get("controls", [])
        if data["mode"] == "video":
            choices = videos(controls, snapshot.get("title", ""))
            if not choices:
                return "I can't see any videos on screen right now."
            if data.get("chosen"):
                picked = [c for c in choices if c["name"] == data["chosen"]]
            else:
                picked = [choices[i] for i in match_titles(detail, [c["name"] for c in choices])]
            if not picked:
                sample = "; ".join(c["name"][:60] for c in choices[:3])
                return f"None of the videos on screen has '{detail}' in its title. I can see: {sample}."
            if len(picked) > 1:
                names = [c["name"] for c in picked[:4]]
                self.offer = {**{k: data.get(k) for k in ("key", "mode", "handle", "title", "exe", "class", "profile")},
                              "stage": "choose", "choices": names, "time": time.monotonic()}
                listing = "; ".join(f"{i}. {n[:70]}" for i, n in enumerate(names, 1))
                self.actions.report("screen_offer", f"{len(names)} videos match '{detail}': {listing}. Which one? Say first, second, or a word.")
                return ""
            result = ui._activate(handle, snapshot, picked[0], "select", cancelled)
            return "Opening " + picked[0]["name"][:90] + ". " + (result if not str(result).lower().startswith(("selected", "clicked", "activated")) else "")
        roles = set(profile.get("roles") or ["Button", "SplitButton", "MenuItem", "TabItem", "ListItem", "Hyperlink", "CheckBox"])
        pool = [c for c in controls if c["role"] in roles] or controls
        found = matches(pool, detail) if detail else []
        if not found:
            return f"I can't see '{detail}' on screen. Things I can press here include: " + ", ".join(c["name"][:40] for c in pool[:6]) + "."
        if len(found) > 1:
            exact = [c for c in found if label_key(c["name"]) == label_key(detail)]
            found = exact[:1] or found
        if len(found) > 1:
            ui.pending = {"handle": handle, "signature": snapshot["signature"], "time": time.monotonic(), "choices": found[:10],
                          "verb": profile.get("verb", "select")}
            from .ui_controls import choice_text
            return "A few things match. Say select option number: " + choice_text(found[:10])
        if not _safe(found[0]):
            return f"'{found[0]['name']}' could delete or send something, so I won't press it from a guess. Say 'click {found[0]['name']}' to do it yourself."
        verb = profile.get("verb", "select")
        return ui._activate(handle, snapshot, found[0], verb, cancelled)

    # --- hands-free writing -------------------------------------------------------------------------------------------
    def start_dictation(self, handle=None, cancelled=lambda: False):
        writer = getattr(self.actions, "hands_free", None)
        if writer is None:
            return "Hands-free writing needs the microphone on. Start listening, then ask again."
        if handle:
            self._front(handle)
            try:
                from .window_focus import focus
                import ctypes
                if focus(int(handle)):
                    user = ctypes.WinDLL("user32")
                    for vk, up in ((0x11, 0), (0x23, 0), (0x23, 2), (0x11, 2)):  # Ctrl+End: cursor to the end of the text.
                        user.keybd_event(vk, 0, up, 0)
                    time.sleep(.4)  # Let the app settle: Notepad drops keys typed straight after focus and Ctrl+End.
                    focus_info = self.current() or {}
                    profile = profile_for(focus_info.get("exe", ""), focus_info.get("title", ""), focus_info.get("class", ""))
                    if profile and profile["category"] in {"notes", "documents"}:
                        # Start on a new line: dictation glued onto the last word ("test:Hello") set off Notepad's
                        # autocorrect, which swallowed a keystroke ("Hello from" became "Hello rrom"; 2026-10-11).
                        from .actions import Desktop
                        desktop = Desktop()
                        desktop.capture()
                        desktop.type("\n", cancelled)
            except Exception:
                pass
        writer(True)
        return "Go ahead, I'm writing what you say. Say 'stop writing' when you're done."

    def _dictation_timeout(self, now):
        writer = getattr(self.actions, "hands_free_state", None)
        if writer is None:
            return
        state = writer()
        if state and now - state > self.options["dictation_idle_seconds"]:
            self.actions.hands_free(False)
            self.actions.report("spoken_reply", "I stopped writing after two minutes of quiet.")

    # --- commands -----------------------------------------------------------------------------------------------------
    def command(self, value):
        focus = self.current() or {}
        if value == "apps":
            return self.knowledge.summary()
        if value == "this_app":
            if not focus:
                return "I can't tell which app is in front right now."
            return self.knowledge.explain_current(focus["exe"], focus["title"], focus["class"])
        if value == "buttons":
            if not focus:
                return "I can't tell which app is in front right now."
            try:
                snapshot = self._snapshot(focus["handle"])
                self.knowledge.learn(focus["exe"], focus["title"], snapshot.get("controls", []), focus["class"])
            except Exception:
                pass
            key = self.knowledge.app_key(focus["exe"], focus["title"], focus["class"])
            names = self.knowledge.buttons(key, 15)
            return ("Buttons I can see in this app: " + ", ".join(names) + ".") if names else "This app doesn't show me any named buttons."
        if value == "pause":
            self.enabled = False
            self.offer = None
            return "Okay, I won't ask about what's on screen until you say 'resume screen suggestions'."
        if value == "resume":
            self.enabled, self.muted, self.declined, self.asked = True, set(), {}, {}
            return "Screen suggestions are back on. I'll offer help when you open an app."
        if value == "mute_app":
            key = self.knowledge.app_key(focus.get("exe", ""), focus.get("title", ""), focus.get("class", ""))
            self.muted.add(key)
            self.offer = None
            return "Okay, I won't ask about this app any more."
        if value == "offer_now":
            if not focus:
                return "I can't tell which app is in front right now."
            key = self.knowledge.app_key(focus["exe"], focus["title"], focus["class"])
            self.muted.discard(key)
            self.offer = None
            profile = profile_for(focus["exe"], focus["title"], focus["class"])
            self.asked[key] = time.monotonic()
            self._prepare(focus, profile, key, forced=True)
            return "" if self.offer else "I don't have a suggestion for this screen right now."
        if value == "dictate":
            return self.start_dictation(focus.get("handle") if focus else None)
        raise ValueError("Unknown screen command " + value)
