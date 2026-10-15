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
        # Wall-clock corrections cannot amplify salience or overflow exp().
        return self.salience * math.exp(-max(0., now - self.at) / 120.)

    def as_dict(self):
        return {"source": self.source, "modality": self.modality, "content": self.content,
                "salience": round(self.salience, 2), "age_s": round(time.time() - self.at, 1)}


class Cognition:
    def __init__(self, actions, options=None):
        self.actions = actions
        if options is not None and not isinstance(options, dict):
            raise ValueError('cognition options must be an object')
        self.options = options if options is not None else {}
        self.enabled = self.options.get("enabled", True)
        rate = self.options.get('cycle_hz', 4)
        if type(self.enabled) is not bool:
            raise ValueError('cognition.enabled must be a boolean')
        if type(rate) not in (int, float) or not math.isfinite(rate):
            raise ValueError('cognition.cycle_hz must be a finite number')
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
        self._cycle_clock = time.monotonic()
        self.stop = threading.Event()
        self.thread = None
        base = Path(getattr(actions, "base", "."))
        self.stats_path = base / ".jarvis-runtime" / "cognition" / "procedures.json"
        self.state_path = base / ".jarvis-runtime" / "cognition" / "state.json"
        self.stats = self._load_stats()
        self.hz = max(.5, min(20., float(rate)))
        self._flush = threading.Event()
        self.writer_thread = None
        self._writer_restarts = 0
        self._stats_dirty = False
        self._stats_io = threading.Lock()
        self.persistence_error = None
        self.dropped_events = 0
        self.rejected_events = 0
        self.tick_errors = 0
        self.tick_error = None
        self.tick_overruns = 0
        self._last_tick = self._cycle_clock
        self.tick_duration_ms = 0.
        from scipy.special import betaincinv
        self._beta_quantile = betaincinv  # Prime outside the loop, not on its first tick.

    # --- persistence ------------------------------------------------------------------------------------------------
    def _load_stats(self):
        try:
            if self.stats_path.stat().st_size > 2_000_000:
                return {}
            value = json.loads(self.stats_path.read_text(encoding="utf-8"))
            return dict(list(value.items())[:512]) if isinstance(value, dict) else {}
        except (OSError, ValueError, RecursionError):
            return {}

    def _save_stats(self):
        if self.thread and self.thread.is_alive() and not self.stop.is_set():
            with self.lock:
                self._stats_dirty = True
            self._flush.set()
            return
        try:
            self._write_stats()
        except OSError as exc:
            self.persistence_error = type(exc).__name__
            # Statistics failure cannot change an external action's outcome.

    def _write_stats(self):
        with self._stats_io:
            return self._write_stats_serial()

    def _write_stats_serial(self):
        with self.lock:
            data = json.dumps(self.stats, ensure_ascii=True, indent=1)
            self._stats_dirty = False
        try:
            self.stats_path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.stats_path.with_suffix(".tmp")
            temp.write_text(data, encoding="utf-8")
            temp.replace(self.stats_path)
        except OSError:
            with self.lock:
                self._stats_dirty = True
            raise

    def _mark(self, module, started=None):
        now = time.time()
        with self.lock:
            self.activity[module] = now
            self.counts[module] += 1
            if started is not None:
                self.latency[module] = round((time.perf_counter() - started) * 1000, 2)

    # --- 1. perception ----------------------------------------------------------------------------------------------
    def perceive(self, source, modality, content, salience=.5):
        """Any module reports something it sensed; the loop folds it into working memory."""
        if not self.enabled or not content:
            return
        if any(type(value) is not str for value in (source, modality, content)) or len(source) > 64 or len(modality) > 32:
            with self.lock:
                self.rejected_events += 1
            raise ValueError('cognition percept must contain bounded text labels and text content')
        content = content[:300].encode('utf-8', errors='replace').decode('utf-8')
        started = time.perf_counter()
        salience = salience if type(salience) in (int,float) and math.isfinite(salience) else .5
        # Caller-provided sensor scores cannot eclipse a deliberate voice command
        # or current-window observation. Critical alerts remain in their own UI.
        salience = 1. if modality == 'speech' and source == 'you' else (.85 if source == 'screen' and modality == 'vision' else min(.7, salience))
        percept = Percept(source, modality, content, salience)
        with self.lock:
            self._offer(self.percepts, percept)
            self._offer(self.inbox, percept)
        self._mark("perception", started)

    def _offer(self, queue, percept):
        if len(queue) == queue.maxlen:
            now = percept.at
            lowest = min(queue, key=lambda p:(p.weight(now), p.at))
            self.dropped_events += 1
            if (percept.weight(now), percept.at) <= (lowest.weight(now), lowest.at):
                return
            queue.remove(lowest)
        queue.append(percept)

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
        if type(title) is not str:
            raise ValueError('cognition window title must be text')
        title = title[:300].encode('utf-8', errors='replace').decode('utf-8')
        with self.lock:
            if title != getattr(self, "_last_window", None):
                self._last_window = title
                # Window observations are current context, not historical attention.
                for queue in (self.percepts, self.inbox):
                    stale = [p for p in queue if p.source == 'screen' and p.modality == 'vision']
                    for percept in stale:
                        queue.remove(percept)
                self.attention = [p for p in self.attention if not (p.source == 'screen' and p.modality == 'vision')]
                self.workspace['focus'] = title
                self.perceive("screen", "vision", title, .5)

    # --- 2. working memory ------------------------------------------------------------------------------------------
    def update_workspace(self):
        started = time.perf_counter()
        actions, now = self.actions, time.time()
        with self.lock:
            percepts = list(self.percepts)
            window = getattr(self, '_last_window', None)
        attention = sorted(percepts, key=lambda p:(p.weight(now), p.at), reverse=True)[:7]
        current = getattr(actions, "current_item", None)
        prompts = getattr(actions, "whatsapp_prompts", None) or []
        pending = getattr(prompts[-1], "question", "") if prompts else ("approval card waiting" if getattr(actions, "approvals_waiting", 0) else "")
        with self.lock:
            # A window may change while external workspace attributes are read.
            current_window = getattr(self, '_last_window', None)
            if current_window != window:
                attention = [p for p in attention if not (p.source == 'screen' and p.modality == 'vision')
                             or p.content == current_window]
            self.attention = attention
            self.workspace.update({
                "active_task": ((current[1].value or current[1].kind)[:120] if current else ""),
                "queued": len(getattr(actions, "pending_tasks", []) or []),
                "pending": pending[:160],
                "style": list((getattr(actions, "session_style", {}) or {}).values()),
                "focus": current_window if current_window is not None else next(
                    (p.content for p in reversed(percepts) if p.modality == "vision"), self.workspace.get("focus", "")),
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
        with self.lock:
            stat = self._stat(self.stats.get(command.kind))
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
        a, b = stat.get('successes', 0)+1, attempts-stat.get('successes', 0)+1
        prediction['confidence_interval'] = [round(float(self._beta_quantile(a,b,p)),4) for p in (.025,.975)]
        prediction['confidence_method'] = 'Beta(1,1) posterior, equal-tailed 95% credible interval'
        prediction['history_samples'] = attempts
        self.last_prediction = prediction
        self._mark("reasoning", started)
        return prediction

    @staticmethod
    def _stat(value):
        value = value if isinstance(value, dict) else {}
        def count(key, default=0):
            number = value.get(key, default)
            return number if type(number) is int and 0 <= number <= 1_000_000_000 else default
        attempts = count('attempts')
        successes = min(attempts, count('successes'))
        seconds = value.get('mean_seconds', 0)
        seconds = seconds if type(seconds) in (int,float) and math.isfinite(seconds) and seconds >= 0 else 0
        return {**value, 'attempts':attempts,'successes':successes,'failures':attempts-successes,
            'mean_seconds':seconds,'last_failure':str(value.get('last_failure',''))[:200]}

    def procedure_stats(self, kind=None):
        """Validated copy for every consumer; never expose mutable history rows."""
        with self.lock:
            if kind is not None:
                return self._stat(self.stats.get(kind))
            return {key:self._stat(value) for key,value in self.stats.items()}

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
                     if prediction.get('history_samples', 0) >= 3 else "I don't have enough history yet to estimate how often it works")
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
        with self.lock:
            lesson = self._evaluate_locked(command, prediction, ok, seconds, detail, started)
        if lesson:
            self.consolidate(lesson)
        self._save_stats()
        self._mark('executive', started)

    def _evaluate_locked(self, command, prediction, ok, seconds, detail, started):
        kind = command.kind
        stat = self.stats[kind] = self._stat(self.stats.get(kind))
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
            return kind + " has failed " + str(stat["failures"]) + " of " + str(stat["attempts"]) + " times; last reason: " + str(detail)[:120]
        return None

    def feedback(self, reward, note):
        """Your correction or praise adjusts the last action's record (meta-learning from people, not just tools)."""
        with self.lock:
            outcome = self.last_outcome
            if not outcome or reward >= 0 or not outcome['ok']:
                return
            stat = self.stats[outcome['kind']] = self._stat(self.stats.get(outcome['kind']))
            stat['successes'] = max(0, stat['successes']-1)
            stat['failures'] += 1
            stat['corrections'] = stat.get('corrections',0)+1
            outcome['ok'] = False
            lesson = "You corrected " + outcome['kind'] + " for '" + outcome['target'][:60] + "': " + note[:100]
        self.consolidate(lesson)
        self._save_stats()

    def consolidate(self, lesson):
        """Executive -> long-term memory: keep the lesson, and write it to the Obsidian vault."""
        lesson = datetime.now().strftime("%Y-%m-%d %H:%M") + " " + lesson
        with self.lock:
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
        state = getattr(self.actions, 'task_state', None)
        prior_task = state.snapshot() if command.kind == 'task' and state is not None else None
        self._mark("action")
        with self.lock:
            self.workspace["last_action"] = command.kind + " " + (command.value or "")[:80]
        try:
            result = run()
        except Exception as exc:
            self.evaluate(command, prediction, False, time.perf_counter() - started, str(exc))
            raise
        text = str(result or "")
        pending = getattr(self.actions, 'pending_opinion', None)
        current_task = state.snapshot() if command.kind == 'task' and state is not None else None
        execution_started = (current_task or {}).get('started_at') != (prior_task or {}).get('started_at')
        if command.kind == 'task' and not execution_started and isinstance(pending, dict) and pending.get('goal') == command.value:
            # A recommendation awaiting consent is not an executed procedure.
            self.perceive('action', 'feedback', 'awaiting approval: task', .4)
            self.latency['action'] = round((time.perf_counter() - started) * 1000, 1)
            return result
        ok = not re.match(r"^(?:i couldn'?t|couldn'?t|failed|error|not available|nothing was sent|cancelled|task (?:paused|cancelled|failed)|paused)", text, re.I)
        self.evaluate(command, prediction, ok, time.perf_counter() - started, "" if ok else text)
        self.latency["action"] = round((time.perf_counter() - started) * 1000, 1)
        return result

    # --- the loop -------------------------------------------------------------------------------------------------
    def start(self):
        if self.enabled and not self.thread:
            self.cycle_started, self._cycle_clock = time.time(), time.monotonic()
            self.cycles = 0
            self.writer_thread = threading.Thread(target=self._writer, name='Jarvis cognition persistence', daemon=True)
            self.writer_thread.start()
            self.thread = threading.Thread(target=self.run, name="Jarvis cognitive loop", daemon=True)
            self.thread.start()
        return self

    def close(self):
        self.stop.set()
        self._flush.set()
        for worker in (self.thread, self.writer_thread):
            if worker and worker is not threading.current_thread():
                worker.join(timeout=2)

    def persistence_healthy(self):
        return bool(self.writer_thread and self.writer_thread.is_alive() and not self.persistence_error)

    def repair_persistence(self):
        with self.lock:
            if self.stop.is_set() or not self.thread or not self.thread.is_alive():
                return False
            if self.writer_thread and self.writer_thread.is_alive():
                self._flush.set()
                return not self.persistence_error
            if self._writer_restarts >= 3:
                return False
            self._writer_restarts += 1
            self.writer_thread = threading.Thread(target=self._writer,name='Jarvis cognition persistence',daemon=True)
            self.writer_thread.start()
            return True

    def _writer(self):
        """One coalescing slot; disk latency never holds the tick thread's lock."""
        final_flushes = 0
        while True:
            self._flush.wait(1.)
            if self._flush.is_set() or self.stop.is_set():
                self._flush.clear()
                try:
                    if self._stats_dirty:
                        self._write_stats()
                    self.write_state()
                    self.persistence_error = None
                except Exception as exc:
                    self.persistence_error = type(exc).__name__
            if self.stop.is_set():
                # Updates admitted during an in-flight flush must survive shutdown.
                # Never busy-loop on a disk fault or let shutdown replay an action.
                if self._stats_dirty and not self.persistence_error and final_flushes < 2:
                    final_flushes += 1
                    self._flush.set()
                    continue
                return

    def run(self):
        period = 1. / max(.5, min(20., self.hz))
        deadline = time.monotonic()+period
        last_write = 0.
        while not self.stop.wait(max(0,deadline-time.monotonic())):
            started = time.monotonic()
            try:
                self.tick()
                self.tick_error = None
                if time.monotonic() - last_write > 1.:
                    if not self.writer_thread.is_alive():
                        self.repair_persistence()
                    self._flush.set()
                    last_write = time.monotonic()
            except Exception as exc:
                self.tick_errors += 1
                self.tick_error = type(exc).__name__
            finally:
                self._last_tick = time.monotonic()
                self.tick_duration_ms = (self._last_tick - started) * 1000
                if self.tick_duration_ms > period * 1000:
                    self.tick_overruns += 1
            deadline += period
            if deadline <= time.monotonic():
                deadline = time.monotonic()+period  # No catch-up burst after overload.

    def tick(self):
        with self.lock:
            batch = bool(self.inbox)
            self.inbox.clear()
        if batch or self.cycles % 4 == 0:
            self.update_workspace()
        self.cycles += 1

    def measured_hz(self):
        elapsed = max(1e-6, time.monotonic() - self._cycle_clock)
        return round(self.cycles / elapsed, 1)

    def snapshot(self):
        with self.lock:
            return self._snapshot_locked()

    def _snapshot_locked(self):
        now = time.time()
        stats = sorted(((k,self._stat(v)) for k,v in self.stats.items()), key=lambda kv: kv[1]['attempts'], reverse=True)[:8]
        return {
            "cycle_hz": self.measured_hz(), "cycles": self.cycles,
            'dropped_events':self.dropped_events,'persistence_error':self.persistence_error,
            'rejected_events': self.rejected_events,
            'persistence_worker_alive':bool(self.writer_thread and self.writer_thread.is_alive()),
            'persistence_worker_restarts':self._writer_restarts,
            'tick_errors': self.tick_errors, 'tick_error': self.tick_error,
            'tick_overruns': self.tick_overruns, 'tick_duration_ms': round(self.tick_duration_ms, 3),
            'tick_degraded': bool(self.tick_error or (self.thread and self.thread.is_alive() and
                time.monotonic() - self._last_tick > max(1., 3. / self.hz))),
            "modules": {name: {"active": now - self.activity[name] < 1.5, "last_s": round(now - self.activity[name], 1) if self.activity[name] else None,
                               "latency_ms": self.latency[name], "events": self.counts[name]} for name in MODULES},
            "working_memory": self.working_memory(),
            "last_prediction": self.last_prediction, "last_outcome": self.last_outcome,
            "lessons": list(self.lessons)[-5:],
            "procedures": {k: {"attempts": v.get("attempts", 0), "success": round(v.get("successes", 0) / max(1, v.get("attempts", 1)), 2),
                               "mean_s": v.get("mean_seconds")} for k, v in stats},
        }

    def write_state(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.snapshot(),ensure_ascii=True,default=str),encoding='utf-8')
        temporary.replace(self.state_path)

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
