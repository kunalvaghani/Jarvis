"""Pip's brain: which emotion it shows, chosen many times a second from you, Jarvis, the screen and its own mood.

Highest priority first:

1. Reactions to you:
   * a click on Pip is a boop (surprised, then a giggle);
   * a double-click is love;
   * 4 quick clicks make it dizzy, and 7 make it "ouch";
   * dragging the island is "whee", and hovering over Pip makes it curious;
   * a file dragged over the island makes it hungry; a drop makes it eat.
2. The file-drop card: eating, reading, question, sending, done.
3. Jarvis:
   * an approval card is waiting: approval;
   * a question is waiting: question;
   * Jarvis is speaking: talking;
   * you're speaking: listening;
   * thinking, and working.
4. Jarvis events (short reactions):
   * errors: error;
   * finished actions: finished;
   * a WhatsApp message: surprised; a call: excited;
   * a repository being learned: searching; once learned: proud;
   * weather alerts: sad.
5. What you're doing (the app in front, sampled every two seconds):
   * music: dancing with headphones;
   * code or a terminal: focused, with glasses;
   * video: watching;
   * chat apps: chatty;
   * documents: reading.
6. Your activity:
   * no input for 5 minutes: bored;
   * 15 minutes: sleeping (sooner late at night, wearing a beanie);
   * back at the keyboard after a break: greeting.
7. Its own mood:
   * energy drains while awake and refills while asleep;
   * affection grows with boops and pets, and fades slowly;
   * boredom builds when nothing happens.

   These colour the resting face (sleepy, bored, shy). A little fidget plays every 15–40 seconds: wink, curious
   look, yawn, a hum-dance, laugh or shy.

Outfits follow the context and the date:

* glasses while coding, headphones with music, a beanie at night;
* a witch hat at the end of October, a santa hat in December, a party hat on 1 January;
* a bow when it's very fond of you.

Everything here is cheap: the app in front and the idle time are sampled every two seconds, and the rest is
arithmetic.
"""
from collections import deque
from datetime import datetime
import random
import re
import time

from .island_buddy import TINTS, mix, mood_for, pose_for

CATEGORIES = [
    ("music", r"^(?:spotify|musicbee|foobar2000|itunes|applemusic|aimp)\.exe$", r"spotify|apple music|soundcloud|music\.youtube"),
    ("video", r"^(?:vlc|mpc-hc64|mpc-be64|potplayermini64|netflix|primevideo)\.exe$",
     r"youtube|netflix|prime video|hotstar|disney\+|twitch|jiocinema|- vlc"),
    ("code", r"^(?:code|cursor|windsurf|zed|devenv|pycharm64|idea64|webstorm64|clion64|rider64|sublime_text|notepad\+\+|"
             r"windowsterminal|wt|cmd|powershell|pwsh|android studio|studio64)\.exe$", r"visual studio code|github|stack overflow|localhost"),
    ("chat", r"^(?:whatsapp|whatsapp\.root|telegram|discord|slack|ms-teams|teams|signal)\.exe$",
     r"whatsapp|instagram.*messages|messenger|telegram|discord|slack"),
    ("docs", r"^(?:winword|excel|powerpnt|acrord32|acrobat|sumatrapdf|onenote|obsidian|notion)\.exe$", r"\.pdf|google docs|notion"),
    ("game", r"^(?:minecraft|javaw|valorant|leagueclient|cs2|r5apex|fortnite|robloxplayerbeta|steam)\.exe$", r"roblox|minecraft"),
]
CONTEXT_EMOTION = {"music": "dancing", "code": "focused", "video": "watching", "chat": "chatty", "docs": "reading",
                   "game": "excited"}
FIDGETS = ["wink", "curious", "yawn", "dancing", "laughing", "shy", "surprised"]


def categorize(process, title):
    process, title = (process or "").casefold(), (title or "").casefold()
    for name, exe, words in CATEGORIES:
        if re.search(exe, process) or (words and re.search(words, title)):
            return name
    return "browser" if process in {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "arc.exe"} else "other"


def foreground():
    """(process name, window title) of the app in front, or ('', '')."""
    try:
        import ctypes
        import psutil
        user = ctypes.windll.user32
        hwnd = user.GetForegroundWindow()
        pid = ctypes.c_ulong()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        length = user.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        user.GetWindowTextW(hwnd, buffer, length + 1)
        import os
        if pid.value == os.getpid():
            return "", ""
        return psutil.Process(pid.value).name(), buffer.value
    except Exception:
        return "", ""


def idle_seconds():
    """Seconds since the last keyboard or mouse input anywhere (GetLastInputInfo)."""
    try:
        import ctypes

        class Info(ctypes.Structure):
            _fields_ = [("size", ctypes.c_uint), ("time", ctypes.c_uint)]
        info = Info(ctypes.sizeof(Info), 0)
        ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info))
        return max(0., (ctypes.windll.kernel32.GetTickCount() - info.time) / 1000)
    except Exception:
        return 0.


class Buddy:
    def __init__(self, options=None, clock=time.monotonic, sense=True, rng=None):
        options = options if isinstance(options, dict) else {}
        self.clock = clock
        self.sense = sense                      # Sample the app in front and idle time (off in tests).
        self.bored_after = float(options.get("bored_after_seconds", 300))
        self.sleep_after = float(options.get("sleep_after_seconds", 900))
        self.random = rng or random.Random()
        now = clock()
        self.reactions = []                     # [priority, emotion, until, started]
        self.react("greeting", 3., 50, now)     # Hello when Jarvis starts.
        self.energy, self.affection, self.boredom = 1., .5, 0.
        self.clicks = deque(maxlen=12)
        self.music_until = 0.
        self.context, self.context_title, self.next_sense = "other", "", 0.
        self.idle = 0.
        self.was_away = False
        self.next_fidget = now + self.random.uniform(15, 40)
        self.fidget = None
        self.emotion, self.since = "greeting", now
        self.tint = TINTS["white"]
        self.last = now
        self.events = deque(maxlen=40)          # (time, what) — for docs, tests and the Mind view.

    # --- reactions -----------------------------------------------------------------------------------------------
    def react(self, emotion, seconds, priority=60, now=None):
        now = self.clock() if now is None else now
        self.reactions = [r for r in self.reactions if r[1] != emotion and r[2] > now]
        self.reactions.append([priority, emotion, now + seconds, now])

    def note(self, what, now):
        self.events.append((now, what))
        self.boredom = 0.

    def poke(self, now=None):
        """A click on Pip."""
        now = self.clock() if now is None else now
        self.clicks.append(now)
        recent = [c for c in self.clicks if now - c < 2.]
        self.note("poke", now)
        if len(recent) >= 7:
            self.react("ouch", 2.5, 95, now)
            self.affection = max(0., self.affection - .15)
            return "ouch"
        if len(recent) >= 4:
            self.react("dizzy", 3., 90, now)
            return "dizzy"
        self.affection = min(1., self.affection + .05)
        self.react("surprised", .6, 85, now)
        self.react("laughing", 1.6, 80, now)
        return "boop"

    def pet(self, now=None):
        """A double-click on Pip."""
        now = self.clock() if now is None else now
        self.affection = min(1., self.affection + .2)
        self.note("pet", now)
        self.react("love", 3., 92, now)
        return "love"

    def drag(self, now=None):
        now = self.clock() if now is None else now
        self.note("drag", now)
        self.react("whee", .5, 88, now)

    def hover(self, now=None):
        now = self.clock() if now is None else now
        if not any(r[1] == "curious" and r[2] > now for r in self.reactions):
            self.note("hover", now)
        self.react("curious", .8, 40, now)

    def file_over(self, now=None):
        now = self.clock() if now is None else now
        self.react("hungry", .7, 97, now)

    def dropped(self, now=None):
        now = self.clock() if now is None else now
        self.note("drop", now)
        self.reactions = [r for r in self.reactions if r[1] != "hungry"]
        self.react("eating", 2.5, 98, now)

    def event(self, kind, message, now=None):
        """Things Jarvis reports to the island (Island.notify)."""
        now = self.clock() if now is None else now
        if kind == 'voice_interrupt':
            self.react('surprised', 1.2, 72, now)
        elif kind in {"partial", "voice_transcript"} and message:
            self.react("listening", 2.5, 45, now)
        elif kind in {"warning", "fatal", "answer_error"} and message:
            self.note("error", now)
            self.react("error", 3., 70, now)
        elif kind == "action" and message:
            self.note("done", now)
            self.react("finished", 2.2, 65, now)
        elif kind == "awareness" and isinstance(message, dict):
            self.react("curious", 2., 38, now)  # A proactive note: low priority, below errors and speech.
        elif kind == "media_card" and isinstance(message, dict):
            service, phase = message.get("service"), message.get("phase")
            if service in {"spotify", "youtube"}:
                if phase == "playing":
                    self.music_until = now + 240
                elif phase in {"paused", "error"}:
                    self.music_until = 0.
            elif service == "whatsapp":
                if phase == "message":
                    self.note("message", now)
                    self.react("surprised", 2., 72, now)
                elif phase == "call":
                    self.react("excited", 6., 74, now)
                elif phase == "sent":
                    self.react("finished", 2.2, 65, now)
            elif service == "github":
                if phase == "learning":
                    self.react("searching", 4., 35, now)
                elif phase == "learned":
                    self.react("proud", 4., 66, now)
                elif phase == "error":
                    self.react("sad", 3., 66, now)
            elif service == "weather" and phase == "alert":
                self.react("sad", 4., 68, now)

    # --- the loop ------------------------------------------------------------------------------------------------
    def sense_world(self, now):
        if not self.sense or now < self.next_sense:
            return
        self.next_sense = now + 2.
        process, title = foreground()
        self.context, self.context_title = (categorize(process, title), title) if process else (self.context, self.context_title)
        idle = idle_seconds()
        if self.was_away and idle < 3:
            self.note("welcome back", now)
            self.react("greeting", 3., 55, now)
        self.was_away = idle >= self.bored_after
        self.idle = idle

    def update(self, now=None, status="STANDBY", speaking=False, listening=False, card_phase=None, question=False,
               approval=False, look=None):
        """Choose the emotion and return (emotion, pose)."""
        now = self.clock() if now is None else now
        dt = max(0., min(1., now - self.last))
        self.last = now
        self.sense_world(now)
        hour = datetime.now().hour
        night = hour >= 23 or hour < 5
        resting = status == "STANDBY" and not speaking
        # Its own feelings.
        if self.emotion == "sleeping":
            self.energy = min(1., self.energy + dt / 300)
        else:
            self.energy = max(0., self.energy - dt / (4 * 3600) * (2 if night else 1))
        self.affection += (.5 - self.affection) * dt / 1800
        if resting and self.context in {"other", "browser"}:
            self.boredom = min(1., self.boredom + dt / 900)
        elif not resting:
            self.boredom = max(0., self.boredom - dt / 30)
        self.reactions = [r for r in self.reactions if r[2] > now]
        emotion, started = self.choose(now, status, speaking, listening, card_phase, question, approval, night)
        if emotion != self.emotion:
            self.emotion, self.since = emotion, started if started is not None else now
        pose = pose_for(emotion, now - self.since, look, self.outfit(emotion, night))  # Each animation starts at 0.
        # Colours blend smoothly from one emotion to the next.
        target = pose["tint"]
        self.tint = mix(self.tint, target, min(1., dt * 6))
        pose["tint"] = self.tint
        return emotion, pose

    def choose(self, now, status, speaking, listening, card_phase, question, approval, night):
        if self.reactions:
            top = max(self.reactions, key=lambda r: (r[0], r[3]))
            if top[0] >= 80 or not card_phase:
                return top[1], top[3]
        if card_phase:
            return mood_for(card_phase), None
        if approval:
            return "approval", None
        if question:
            return "question", None
        if speaking:
            return "talking", None
        if self.reactions:
            top = max(self.reactions, key=lambda r: (r[0], r[3]))
            if top[0] >= 60:
                return top[1], top[3]
        if status in {"THINKING"}:
            return "thinking", None
        if status in {"WORKING"}:
            return "working", None
        if self.reactions:
            top = max(self.reactions, key=lambda r: (r[0], r[3]))
            return top[1], top[3]
        if now < self.music_until or self.context == "music":
            return "dancing", None
        if self.idle >= self.sleep_after or (night and self.idle >= self.bored_after):
            return "sleeping", None
        if self.context in CONTEXT_EMOTION and self.idle < 60:
            return CONTEXT_EMOTION[self.context] if self.context != "game" else "watching", None
        if self.idle >= self.bored_after:
            return "bored", None
        # A fidget now and then.
        if self.fidget and now < self.fidget[1]:
            return self.fidget[0], self.fidget[2]
        if now >= self.next_fidget:
            choice = self.random.choice(FIDGETS if self.energy > .35 else ["yawn", "curious", "wink"])
            self.fidget = (choice, now + (3.5 if choice == "yawn" else 2.2), now)
            self.next_fidget = now + self.random.uniform(15, 40)
            return choice, now
        if self.energy < .25 or night:
            return "sleepy", None
        if self.boredom > .75:
            return "bored", None
        if self.affection > .85:
            return "shy" if int(now / 6) % 3 == 0 else "idle", None
        return "idle", None

    def outfit(self, emotion, night):
        today = datetime.now()
        items = []
        if emotion == "focused":
            items.append("glasses")
        if emotion in {"sleeping", "sleepy"} and night:
            items.append("beanie")
        if today.month == 12 and emotion not in {"dancing"}:
            items.append("santa")
        elif today.month == 10 and today.day >= 25 and emotion not in {"dancing", "sleeping"}:
            items.append("witch")
        elif today.month == 1 and today.day == 1:
            items.append("party")
        if self.affection > .9 and emotion in {"idle", "love", "shy"}:
            items.append("bow")
        return items


def look_at(cursor, center, reach=(700., 450.)):
    """Yaw and pitch (-1..1) from Pip's centre on screen towards the pointer."""
    dx, dy = cursor[0] - center[0], cursor[1] - center[1]
    return (max(-1., min(1., dx / reach[0])), max(-1., min(1., dy / reach[1]) * .8 - .05))
