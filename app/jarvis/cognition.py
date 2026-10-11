"""Jarvis's cognitive architecture: one continuous perceive -> remember -> reason -> decide -> act -> learn loop.

The six modules match the architecture diagram (Multimodal Perception, Working Memory, Long-Term Memory, Core
Reasoning & World Model, Executive Control & Meta-Learning, Action / Tool Output). They are wired around the
subsystems Jarvis already has rather than replacing them:

- Perception: speech and typed commands, the focused window (vision), background sensors (God's Eye, weather,
  WhatsApp, repository browsing) and feedback from every action. Each percept gets a salience score.
- Working memory: a bounded workspace (goal, focus, active task, pending decisions, session style and seven
  attention slots) that every answer and task plan sees through context_hub.situation().
- Long-term memory: one recall interface over episodic memory (conversation summaries, Obsidian activity),
  declarative memory (curated facts) and procedural memory (skill and experience memory, coding lessons, learned
  repositories, plus the per-action outcome statistics kept here).
- World model: before an action runs it predicts the effects, whether they are reversible or external, whether
  approval is needed, the expected time and the chance of success, and lists what it is uncertain about.
- Executive control: proceeds, or asks when a consequential action rests on an unresolved reference. After the
  action it compares outcome with prediction, learns timing and reliability, treats corrections ("no, that's
  wrong") as negative feedback, and consolidates lessons into the Obsidian vault.
- Action: Actions.execute; its result flows back into perception, closing the loop.

Nothing here sends, types or clicks by itself: it observes, predicts, asks and learns.
"""
import json
import math
import re
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

MODULES = ("perception", "working_memory", "long_term_memory", "reasoning", "executive", "action")

# --- World model: what each kind of command does to the world -------------------------------------------------------
READ_ONLY = {"ask", "queue_status", "jarvis_status", "system_info", "behavior", "memory_list", "memory_conversations",
             "repo_list", "repo_explain", "api_health", "weather_alerts", "gods_eye_explain", "gods_eye_status",
             "repeat_last", "project_recent", "project_list", "windows_catalog", "context_search", "list_controls",
             "whatsapp_read", "cognition_predict", "realtime", "screen_info"}
SENDS = {"whatsapp_send", "whatsapp_reply", "messenger_send"}
WRITES = {"create", "modify", "delete", "rename", "create_in_folder", "modify_in_folder", "delete_in_folder",
          "write_text", "compose_text", "type", "dictate", "memory_save", "memory_forget", "code_task", "run_command"}
UI = {"click_control", "choose_control", "select_context", "windows_command", "close_app", "screen_act"}
MEDIA = {"play_media", "media_search", "media_control", "spotify_control", "spotify_volume", "spotify_search",
         "spotify_open_playlist", "media_related"}
VIEW = {"gods_eye_show", "gods_eye_camera", "gods_eye_view", "gods_eye_cameras", "open", "open_folder", "open_file",
        "open_project", "browse", "browser_search", "messenger_focus"}
SESSION = {"conversation_style", "stop_speaking", "end_conversation", "cancel_task", "cancel_current", "cancel_all",
           "approval_answer", "resume_task", "memory_summarize", "repo_learn", "repo_forget", "gods_eye_update"}
DEFAULT_SECONDS = {"ask": 6, "task": 40, "code_task": 300, "play_media": 12, "whatsapp_send": 25, "whatsapp_reply": 30,
                   "gods_eye_show": 20, "gods_eye_camera": 2, "open": 3, "api_health": 25, "weather_alerts": 6,
                   "repo_learn": 90, "media_search": 8}
PRONOUN = re.compile(r"^(?:it|that|this|him|her|them|that one|the other one|the same one|this person|that person)$", re.I)
CORRECTION = re.compile(r"^(?:no[,.!]?\s+(?:i (?:meant|said)|that'?s (?:wrong|not)|not that)|that'?s (?:wrong|not what i (?:asked|meant))|"
                        r"wrong (?:one|answer|person|song|place)|that didn'?t work|it didn'?t work|you got (?:it|that) wrong)", re.I)
APPROVAL_KINDS = SENDS | {"delete", "delete_in_folder", "run_command"}


def recipient(command):
    """Who a send goes to, as said: 'him' in "message him on Telegram", 'her' in "send it to her"."""
    if command.kind == "messenger_send":
        return (command.value or "").strip()
    if command.kind == "whatsapp_send":
        parts = re.split(r"\s+to\s+", command.value or "")
        return parts[-1].strip() if len(parts) > 1 else ""
    return ""


def describe(command):
    """Readable form of a request: free text as said, structured commands as 'kind: value'."""
    value = (command.value or "").splitlines()[0][:200] if command.value else ""
    if command.kind in {"task", "ask", "realtime", "code_task", "cognition_predict"} and value:
        return ("what would happen if I " + value) if command.kind == "cognition_predict" else value
    return command.kind.replace("_", " ") + (": " + value if value and not value.startswith("{") else "")


def effect_of(kind):
    if kind in READ_ONLY:
        return "reads information only", True, False
    if kind in SENDS:
        return "sends a message to another person", False, True
    if kind in WRITES:
        return "writes or changes text, files or memory on this PC", kind not in {"delete", "delete_in_folder", "run_command"}, False
    if kind in UI:
        return "operates an app or window on screen", True, False
    if kind in MEDIA:
        return "controls music or video playback", True, False
    if kind in VIEW:
        return "opens or moves a view (app, website, folder or God's Eye)", True, False
    if kind in SESSION:
        return "changes Jarvis's own session state or queue", True, False
    if kind == "task":
        return "runs a planned multi-step task on the desktop or online", False, False
    return "an action whose effects aren't modelled yet", False, False


class Percept:
    __slots__ = ("source", "modality", "content", "salience", "at")

    def __init__(self, source, modality, content, salience):
        self.source, self.modality, self.content = source, modality, str(content)[:300]
        self.salience, self.at = max(0., min(1., salience)), time.time()

    def weight(self, now):
        return self.salience * math.exp(-(now - self.at) / 120.)  # Attention fades over about two minutes.

    def as_dict(self):
        return {"source": self.source, "modality": self.modality, "content": self.content,
                "salience": round(self.salience, 2), "age_s": round(time.time() - self.at, 1)}


class Cognition:
    def __init__(self, actions, options=None):
        self.actions = actions
        self.options = options or {}
        self.enabled = self.options.get("enabled", True)
        self.lock = threading.RLock()
        self.percepts = deque(maxlen=200)
        self.inbox = deque(maxlen=200)
        self.attention = []
        self.workspace = {"goal": "", "focus": "", "active_task": "", "pending": "", "style": [], "last_action": ""}
        self.activity = {name: 0. for name in MODULES}  # When each module last worked (for the live view).
        self.latency = {name: 0. for name in MODULES}
        self.counts = {name: 0 for name in MODULES}
        self.last_prediction = None
        self.last_outcome = None
        self.lessons = deque(maxlen=50)
        self.cycles, self.cycle_started = 0, time.time()
        self.stop = threading.Event()
        self.thread = None
        base = Path(getattr(actions, "base", "."))
        self.stats_path = base / ".jarvis-runtime" / "cognition" / "procedures.json"
        self.state_path = base / ".jarvis-runtime" / "cognition" / "state.json"
        self.stats = self._load_stats()
        self.hz = float(self.options.get("cycle_hz", 4))

    # --- persistence ------------------------------------------------------------------------------------------------
    def _load_stats(self):
        try:
            return json.loads(self.stats_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_stats(self):
        try:
            self.stats_path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.stats_path.with_suffix(".tmp")
            temp.write_text(json.dumps(self.stats, ensure_ascii=False, indent=1), encoding="utf-8")
            temp.replace(self.stats_path)
        except OSError:
            pass

    def _mark(self, module, started=None):
        now = time.time()
        self.activity[module] = now
        self.counts[module] += 1
        if started is not None:
            self.latency[module] = round((time.perf_counter() - started) * 1000, 2)

    # --- 1. perception ----------------------------------------------------------------------------------------------
    def perceive(self, source, modality, content, salience=.5):
        """Any module reports something it sensed; the loop folds it into working memory."""
        if not self.enabled or not content:
            return
        started = time.perf_counter()
        percept = Percept(source, modality, content, salience)
        with self.lock:
            self.percepts.append(percept)
            self.inbox.append(percept)
        self._mark("perception", started)

    def perceive_command(self, command):
        if command.kind in {"island_choice", "memory_choice"}:
            return
        text = describe(command)
        self.perceive("you", "speech", text, .9)
        if CORRECTION.match(text.strip()):
            self.feedback(-1., "you corrected the last action: " + text[:80])
        with self.lock:
            if command.kind not in {"approval_answer", "repeat_last", "stop_speaking"}:
                self.workspace["goal"] = text[:200]

    def perceive_window(self, title):
        if title and title != getattr(self, "_last_window", None):
            self._last_window = title
            self.perceive("screen", "vision", title, .5)

    # --- 2. working memory ------------------------------------------------------------------------------------------
    def update_workspace(self):
        started = time.perf_counter()
        actions, now = self.actions, time.time()
        with self.lock:
            percepts = list(self.percepts)
        self.attention = sorted(percepts, key=lambda p: p.weight(now), reverse=True)[:7]
        current = getattr(actions, "current_item", None)
        prompts = getattr(actions, "whatsapp_prompts", None) or []
        pending = getattr(prompts[-1], "question", "") if prompts else ("approval card waiting" if getattr(actions, "approvals_waiting", 0) else "")
        with self.lock:
            self.workspace.update({
                "active_task": ((current[1].value or current[1].kind)[:120] if current else ""),
                "queued": len(getattr(actions, "pending_tasks", []) or []),
                "pending": pending[:160],
                "style": list((getattr(actions, "session_style", {}) or {}).values()),
                "focus": next((p.content for p in reversed(percepts) if p.modality == "vision"), self.workspace.get("focus", "")),
            })
        self._mark("working_memory", started)

    def working_memory(self):
        with self.lock:
            snapshot = dict(self.workspace)
        snapshot["attention"] = [p.source + ": " + p.content[:90] for p in self.attention]
        return {k: v for k, v in snapshot.items() if v not in ("", [], 0, None)}

    # --- 3. long-term memory ----------------------------------------------------------------------------------------
    def recall(self, query, limit=4):
        """Episodic, declarative and procedural memories relevant to a query, labelled by kind."""
        started = time.perf_counter()
        actions, found = self.actions, {}
        curator = getattr(actions, "curator", None)
        if curator is not None and getattr(curator, "enabled", False):
            try:
                facts = curator.relevant(query, limit)
                if facts:
                    found["declarative"] = [f["text"] for f in facts]
                rows = curator.conversations(query)
                if rows:
                    found["episodic"] = [r["date"] + ": " + r["title"] for r in rows[-limit:]]
            except Exception:
                pass
        skills = getattr(actions, "skills", None)
        if skills is not None:
            try:
                guidance = skills.context(query) or {}
                names = [row.get("name", "") for row in guidance.get("skills", []) if isinstance(row, dict)]
                cases = (guidance.get("experience_context") or {}).get("cases", [])
                if names or guidance.get("procedures") or cases:
                    found["procedural_skills"] = {"skills": names, "procedures": len(guidance.get("procedures", [])),
                                                  "past_cases": len(cases)}
            except Exception:
                pass
        learner = getattr(actions, "repo_learner", None)
        if learner is not None and getattr(learner, "enabled", False):
            try:
                repos = learner.relevant(query, 2)
                if repos:
                    found["procedural_repositories"] = [name for _, name, _ in repos]
            except Exception:
                pass
        lessons = self.relevant_lessons(query, limit)
        if lessons:
            found["procedural_lessons"] = lessons[-limit:]
        self._mark("long_term_memory", started)
        return found

    def relevant_lessons(self, query, limit=3):
        words = set(re.findall(r"\w{4,}", (query or "").casefold()))
        return [lesson for lesson in self.lessons if words & set(re.findall(r"\w{4,}", lesson.casefold()))][-limit:]

    # --- 4. reasoning & world model ---------------------------------------------------------------------------------
    def predict(self, command):
        """Simulate the action before it runs: effects, reversibility, approval, time, odds and uncertainty."""
        started = time.perf_counter()
        effect, reversible, external = effect_of(command.kind)
        stat = self.stats.get(command.kind, {})
        attempts = stat.get("attempts", 0)
        success = (stat.get("successes", 0) + 1) / (attempts + 2)  # Laplace prior: unknown means 50/50.
        seconds = stat.get("mean_seconds") or DEFAULT_SECONDS.get(command.kind, 5)
        uncertain = []
        text = command.value or ""
        who = recipient(command)
        if who and PRONOUN.match(who) and not self._referent():
            uncertain.append("it isn't clear who '" + who + "' is")
        if attempts >= 3 and success < .5:
            uncertain.append("this kind of action failed " + str(stat.get("failures", 0)) + " of the last " + str(attempts) +
                             " times" + (" (last: " + stat["last_failure"][:80] + ")" if stat.get("last_failure") else ""))
        if command.kind == "task" and not text.strip():
            uncertain.append("there's no goal for the task")
        prediction = {"kind": command.kind, "target": text[:120], "effect": effect, "reversible": reversible,
                      "external": external, "needs_approval": command.kind in APPROVAL_KINDS or external,
                      "expected_seconds": round(seconds, 1), "success_chance": round(success, 2), "uncertain": uncertain,
                      "at": time.time()}
        self.last_prediction = prediction
        self._mark("reasoning", started)
        return prediction

    def _referent(self):
        """Something recent in working memory that 'it/that/her' can point at (a draft, a chat, a task)."""
        actions = self.actions
        if getattr(actions, "whatsapp_prompts", None) or getattr(actions, "current_item", None):
            return True
        return bool(self.last_outcome and time.time() - self.last_outcome["at"] < 300)

    def explain(self, prediction):
        parts = ["That " + prediction["effect"]]
        parts.append("it can be undone" if prediction["reversible"] else "it can't simply be undone")
        if prediction["needs_approval"]:
            parts.append("I'd show you a preview and wait for your approval first")
        parts.append("it usually takes about " + _seconds(prediction["expected_seconds"]))
        parts.append("based on past runs it succeeds about " + str(round(prediction["success_chance"] * 100)) + "% of the time"
                     if self.stats.get(prediction["kind"], {}).get("attempts", 0) >= 3 else "I don't have enough history yet to estimate how often it works")
        text = parts[0] + "; " + "; ".join(parts[1:]) + "."
        if prediction["uncertain"]:
            text += " I'm unsure because " + "; ".join(prediction["uncertain"]) + "."
        return text

    # --- 5. executive control & meta-learning -----------------------------------------------------------------------
    def deliberate(self, command):
        """Proceed, or a clarifying question when a consequential action rests on an unresolved reference."""
        if not self.enabled:
            return None
        started = time.perf_counter()
        prediction = self.predict(command)
        question = None
        if any(u.startswith("it isn't clear") for u in prediction["uncertain"]):
            question = ("Before I send anything: " + prediction["uncertain"][0] + ". "
                        "Say it again with their name and I'll go ahead.")
        self._mark("executive", started)
        return question

    def evaluate(self, command, prediction, ok, seconds, detail=""):
        """Compare outcome with prediction and learn: timing, reliability, and a lesson after repeated failure."""
        started = time.perf_counter()
        kind = command.kind
        stat = self.stats.setdefault(kind, {"attempts": 0, "successes": 0, "failures": 0, "mean_seconds": 0.})
        stat["attempts"] += 1
        stat["successes" if ok else "failures"] += 1
        stat["mean_seconds"] = round(seconds if not stat["mean_seconds"] else .7 * stat["mean_seconds"] + .3 * seconds, 2)
        stat["last_at"] = datetime.now().isoformat(timespec="seconds")
        if not ok:
            stat["last_failure"] = str(detail)[:200]
        surprise = abs((1. if ok else 0.) - (prediction or {}).get("success_chance", .5))
        self.last_outcome = {"kind": kind, "target": (command.value or "")[:120], "ok": ok, "seconds": round(seconds, 1),
                             "detail": str(detail)[:200], "surprise": round(surprise, 2), "at": time.time()}
        self.perceive("action", "feedback", ("done: " if ok else "failed: ") + kind + " " + (command.value or "")[:60],
                      .4 if ok else .8)
        recent_failures = stat["failures"] >= 3 and stat["failures"] / stat["attempts"] > .5
        if not ok and recent_failures:
            self.consolidate(kind + " has failed " + str(stat["failures"]) + " of " + str(stat["attempts"]) +
                             " times; last reason: " + str(detail)[:120])
        self._save_stats()
        self._mark("executive", started)

    def feedback(self, reward, note):
        """Your correction or praise adjusts the last action's record (meta-learning from people, not just tools)."""
        outcome = self.last_outcome
        if not outcome:
            return
        stat = self.stats.setdefault(outcome["kind"], {"attempts": 0, "successes": 0, "failures": 0, "mean_seconds": 0.})
        if reward < 0 and outcome["ok"]:
            stat["successes"] = max(0, stat.get("successes", 0) - 1)
            stat["failures"] = stat.get("failures", 0) + 1
            stat["corrections"] = stat.get("corrections", 0) + 1
            outcome["ok"] = False
            self.consolidate("You corrected " + outcome["kind"] + " for '" + outcome["target"][:60] + "': " + note[:100])
            self._save_stats()

    def consolidate(self, lesson):
        """Executive -> long-term memory: keep the lesson, and write it to the Obsidian vault."""
        lesson = datetime.now().strftime("%Y-%m-%d %H:%M") + " " + lesson
        self.lessons.append(lesson)
        memory = getattr(self.actions, "memory", None)
        if memory is not None and hasattr(memory, "record"):
            try:
                memory.record("Jarvis lesson", lesson)
            except Exception:
                pass
        self._mark("long_term_memory")

    # --- 6. action (wrapped by Actions.execute) ---------------------------------------------------------------------
    def act(self, command, run):
        """Run one action inside the loop: predict, act, evaluate, feed the result back to perception."""
        if not self.enabled:
            return run()
        prediction = self.predict(command)
        started = time.perf_counter()
        self._mark("action")
        with self.lock:
            self.workspace["last_action"] = command.kind + " " + (command.value or "")[:80]
        try:
            result = run()
        except Exception as exc:
            self.evaluate(command, prediction, False, time.perf_counter() - started, str(exc))
            raise
        text = str(result or "")
        ok = not re.match(r"^(?:i couldn'?t|couldn'?t|failed|error|not available|nothing was sent|cancelled)", text, re.I)
        self.evaluate(command, prediction, ok, time.perf_counter() - started, "" if ok else text)
        self.latency["action"] = round((time.perf_counter() - started) * 1000, 1)
        return result

    # --- the loop -------------------------------------------------------------------------------------------------
    def start(self):
        if self.enabled and not self.thread:
            self.thread = threading.Thread(target=self.run, name="Jarvis cognitive loop", daemon=True)
            self.thread.start()
        return self

    def close(self):
        self.stop.set()

    def run(self):
        period = 1. / max(.5, min(20., self.hz))
        last_write = 0.
        while not self.stop.wait(period):
            try:
                self.tick()
                if time.time() - last_write > 1.:
                    self.write_state()
                    last_write = time.time()
            except Exception:
                pass

    def tick(self):
        with self.lock:
            batch = list(self.inbox)
            self.inbox.clear()
        if batch or self.cycles % 4 == 0:
            self.update_workspace()
        self.cycles += 1

    def measured_hz(self):
        elapsed = max(1e-6, time.time() - self.cycle_started)
        return round(self.cycles / elapsed, 1)

    def snapshot(self):
        now = time.time()
        stats = sorted(self.stats.items(), key=lambda kv: kv[1].get("attempts", 0), reverse=True)[:8]
        return {
            "cycle_hz": self.measured_hz(), "cycles": self.cycles,
            "modules": {name: {"active": now - self.activity[name] < 1.5, "last_s": round(now - self.activity[name], 1) if self.activity[name] else None,
                               "latency_ms": self.latency[name], "events": self.counts[name]} for name in MODULES},
            "working_memory": self.working_memory(),
            "last_prediction": self.last_prediction, "last_outcome": self.last_outcome,
            "lessons": list(self.lessons)[-5:],
            "procedures": {k: {"attempts": v.get("attempts", 0), "success": round(v.get("successes", 0) / max(1, v.get("attempts", 1)), 2),
                               "mean_s": v.get("mean_seconds")} for k, v in stats},
        }

    def write_state(self):
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps(self.snapshot(), ensure_ascii=False, default=str), encoding="utf-8")
        except OSError:
            pass

    def status_text(self):
        s = self.snapshot()
        active = [name.replace("_", " ") for name, m in s["modules"].items() if m["active"]]
        wm = s["working_memory"]
        text = ("My cognitive loop is running at " + str(s["cycle_hz"]) + " cycles a second. "
                + ("Active right now: " + ", ".join(active) + ". " if active else "")
                + ("Working memory holds: goal '" + wm["goal"][:80] + "'" if wm.get("goal") else "Working memory is clear")
                + ("; task '" + wm["active_task"][:60] + "'" if wm.get("active_task") else "")
                + ("; waiting on '" + wm["pending"][:60] + "'" if wm.get("pending") else "") + ". ")
        if s["last_outcome"]:
            o = s["last_outcome"]
            text += ("Last action: " + o["kind"] + (" worked" if o["ok"] else " failed") + " in " + _seconds(o["seconds"]) + ". ")
        best = [k + " " + str(round(v["success"] * 100)) + "%" for k, v in s["procedures"].items() if v["attempts"] >= 3][:4]
        if best:
            text += "Learned reliability: " + ", ".join(best) + ". "
        if s["lessons"]:
            text += "Latest lesson: " + s["lessons"][-1][17:][:140] + "."
        return text.strip()


def _seconds(value):
    value = float(value or 0)
    if value < 1:
        return "under a second"
    return (str(round(value, 1)) + " seconds") if value < 90 else (str(round(value / 60)) + " minutes")


# Descriptions for the live view (what each node does in Jarvis, and the code behind it).
NODES = {
    "perception": ("Multimodal Perception", "Vision · Speech · Sensors", "Input tier",
                   "Speech (faster-whisper), typed commands, the focused window, God's Eye, weather, WhatsApp and repository "
                   "browsing, and feedback from every action, each scored for salience.",
                   "engine.py, voice_input.py, screen_worker.py, gods_eye.py, weather_watch.py, whatsapp.py",
                   "Inbound sensors → working memory"),
    "working_memory": ("Working Memory", "Active Context & Workspace", "Dynamic workspace",
                       "Goal, focus, active task, queue, pending decisions, session style and seven attention slots, "
                       "shared with every answer and plan.",
                       "cognition.py workspace + context_hub.py situation",
                       "Perception → core reasoning"),
    "long_term_memory": ("Long-Term Memory", "Episodic & Procedural Store", "Knowledge store",
                         "Episodic: conversation summaries and Obsidian activity. Declarative: curated facts. Procedural: skills, "
                         "experience, coding lessons, learned repositories and per-action outcome statistics.",
                         "memory_curator.py, conversation_memory.py, obsidian_memory.py, skill_memory.py, experience_memory.py, "
                         "repo_learning.py",
                         "Core reasoning ↔ executive consolidation"),
    "reasoning": ("Core Reasoning & World Model", "Simulation & Inference Engine", "Processing core",
                  "Local models plan and answer (qwen3.5:9b). Before acting, the world model predicts effects, reversibility, "
                  "approval needs, time and success odds, and flags uncertainty.",
                  "brain.py planner, knowledge_worker.py, cognition.py predict()",
                  "Working memory ↔ long-term memory → executive"),
    "executive": ("Executive Control & Meta-Learning", "Planning & Self-Correction", "Control & adaptation",
                  "Decides to proceed or ask, checks outcomes against predictions, learns timing and reliability, takes your "
                  "corrections as feedback, and writes lessons to the vault.",
                  "cognition.py deliberate()/evaluate()/consolidate(), task_recovery.py, approvals",
                  "Core reasoning → action, and consolidation into long-term memory"),
    "action": ("Action / Tool Output", "Actuators · Code · APIs", "Output actuation",
               "Desktop and app control, writing, media, WhatsApp, Gmail, God's Eye, coding agents, Windows commands and "
               "82 live data providers; every result feeds back into perception.",
               "actions.py execute(), commands.py, tools and integrations",
               "Executive → the world → perception (feedback loop)"),
}
