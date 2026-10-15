"""Jarvis's self-evolution engine: autonomous, idle-only capability expansion.

This is the orchestration brain that closes the Discover -> Analyze -> Learn -> Integrate ->
Remember -> Repeat loop over the subsystems Jarvis already has. It does NOT reimplement them:

- GitHub discovery, download and static understanding: jarvis/repo_learning.py (RepoLearner),
  repo_analysis.py, repo_acquisition.py.
- Capability extraction, sandboxed generation, validation, registry and activation:
  jarvis/repo_abilities.py (AbilityForge), which auto-builds abilities from a learned repo.
- Idle detection style and resource gating: jarvis/anticipation.py, gpu_scheduler.py.
- Persistent memory: Obsidian via obsidian_memory.py / skill_memory.py.
- Opinions and risk decisions: jarvis/deliberation.py.

What this module adds (the genuine gaps):
1. CapabilityGapDetector - mines Jarvis's own weaknesses from cognition reliability stats and the
   deliberation decision ledger into concrete, evidence-backed improvement gaps.
2. SelfImprovementPlanner + a persistent, scored, crash-safe Improvement Backlog.
3. SelfEvolution - an owned idle thread that, only while idle and resourced, pops the top backlog
   item, synthesizes a discovery query, drives RepoLearner.search/learn (the forge then auto-builds),
   records the outcome, mirrors to Obsidian, and shows an island "capability" card. Checkpointed and
   resumable; preempted by any user task.
4. SafeEvolutionManager - gated self-modification of Jarvis's own source: propose -> isolate worktree
   -> build -> test -> require explicit approval -> deploy with backup -> roll back on regression.
   Never autonomous, never silently disables its checks.

Downloaded code and repository text remain untrusted (handled by the reused subsystems). Nothing here
executes repository code in-process; abilities run out of process through the existing forge.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

DEFAULTS = dict(
    enabled=True,
    idle_seconds=90,          # Quiet time before a learning step may start.
    poll_seconds=5.0,         # Idle-thread tick.
    cooldown_seconds=600,     # Between learning jobs.
    max_jobs_per_day=4,
    max_backlog=200,
    min_available_mb=3072,    # Skip learning when free RAM is low.
    max_cpu_percent=55,       # Skip when the machine is already busy.
    explore=True,             # When idle with no detected gaps, study a relevant topic anyway.
    explore_topics=[          # Short, Python-oriented discovery queries (concise = better matches).
        "windows automation python", "speech recognition python", "text to speech python",
        "local llm inference python", "semantic search python", "web scraping python",
        "pdf extraction python", "file organizer python", "task scheduler python",
        "image processing python", "clipboard manager python", "system monitor python",
    ],
    weights=dict(usefulness=3.0, reuse=2.0, performance=1.5, relevance=2.5, cost=1.5, risk=2.0),
    self_modification=dict(enabled=True, auto_deploy=False),  # Core patches always need approval.
)

# Map a weak/ missing capability to a GitHub discovery query. Conservative and generic.
QUERY_HINTS = {
    "run_command": "windows command automation python",
    "click_control": "windows ui automation accessibility python",
    "select": "windows ui automation uiautomation python",
    "media_control": "media player control python",
    "code_task": "python code generation refactoring tool",
    "knowledge_search": "semantic search retrieval index python",
    "browser_inspect": "browser automation dom extraction python",
    "scrape_web": "web scraping extraction python",
}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _settings(options):
    merged = dict(DEFAULTS)
    for key, value in (options or {}).items():
        if key in {"weights", "self_modification"} and isinstance(value, dict):
            merged[key] = {**DEFAULTS[key], **value}
        elif key in merged:
            merged[key] = value
    return merged


def _signature(kind, subject):
    return kind + ":" + re.sub(r"[^a-z0-9]+", "-", str(subject).casefold()).strip("-")[:60]


class CapabilityGapDetector:
    """Read-only mining of Jarvis's own records into evidence-backed improvement gaps."""

    def __init__(self, actions):
        self.actions = actions

    def detect(self):
        gaps = {}

        def add(kind, subject, summary, evidence, query, usefulness=2.0, performance=1.0):
            sig = _signature(kind, subject)
            if sig not in gaps:
                gaps[sig] = {"signature": sig, "kind": kind, "subject": str(subject)[:80],
                             "summary": summary[:300], "evidence": [str(e)[:200] for e in evidence if e][:4],
                             "suggested_query": query, "usefulness": usefulness, "performance": performance}

        # 1. Unreliable action kinds from the cognition world model's learned statistics.
        cognition = getattr(self.actions, "cognition", None)
        from .cognition import Cognition
        if isinstance(cognition, Cognition):
            stats = cognition.procedure_stats()
        else:
            raw = getattr(cognition, 'stats', {})
            stats = {k:Cognition._stat(v) for k,v in raw.items()} if isinstance(raw, dict) else {}
        for kind, st in stats.items():
            attempts, failures = st.get("attempts", 0), st.get("failures", 0)
            if attempts >= 3 and failures / max(1, attempts) > 0.5:
                add("reliability", kind,
                    f"The '{kind}' action has failed {failures} of {attempts} recent attempts.",
                    [st.get("last_failure", "")],
                    QUERY_HINTS.get(kind, kind.replace("_", " ") + " python library"),
                    usefulness=2.5, performance=2.0)

        # 2. Failed/rejected strategies from the deliberation decision ledger.
        delib = getattr(self.actions, "deliberation", None)
        if delib is not None and hasattr(delib, "decisions"):
            failed = {}
            try:
                for row in delib.decisions(80):
                    outcome = row.get("outcome")
                    if isinstance(outcome, dict) and outcome.get("ok") is False:
                        key = (row.get("goal") or "")[:60]
                        if key:
                            failed[key] = failed.get(key, 0) + 1
            except Exception:
                failed = {}
            for goal, count in failed.items():
                if count >= 2:
                    add("recurring-failure", goal,
                        f"A task like '{goal}' has failed {count} times after deliberation.",
                        [], " ".join(re.findall(r"[a-z]{4,}", goal.casefold())[:5]) + " python",
                        usefulness=2.0, performance=1.5)

        # 3. Repeated similar user requests -> a reusable capability may help.
        history = list(getattr(self.actions, "command_history", []) or [])
        counts = {}
        for text in history:
            norm = re.sub(r"\s+", " ", str(text).casefold()).strip()[:60]
            if len(norm) >= 8:
                counts[norm] = counts.get(norm, 0) + 1
        for text, count in counts.items():
            if count >= 3:
                add("recurring-request", text,
                    f"You have asked '{text}' {count} times; a dedicated capability could help.",
                    [], " ".join(re.findall(r"[a-z]{4,}", text)[:5]) + " python tool",
                    usefulness=3.0, performance=1.0)

        return list(gaps.values())


class SelfEvolution:
    """Owned idle thread that turns gaps into learned capabilities, crash-safely."""

    def __init__(self, actions, options=None, notify=None, busy=None, clock=time.monotonic):
        self.actions = actions
        self.options = _settings(options)
        self.enabled = bool(self.options["enabled"])
        self.notify = notify or (lambda kind, message: None)
        self.busy = busy or (lambda: False)
        self.clock = clock
        self.detector = CapabilityGapDetector(actions)
        self.evolution = SafeEvolutionManager(actions, self.options.get("self_modification", {}))
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.thread = None
        self.last_activity = clock()
        self.jobs_today = []            # Wall-clock timestamps of jobs started today.
        self.next_job_at = 0.0
        self.inflight = False
        self.directory = Path(actions.base) / ".jarvis-runtime" / "self-evolution"
        self.backlog_path = self.directory / "backlog.json"
        self.checkpoint_path = self.directory / "checkpoint.json"
        self.backlog = []
        self.storage_failed = False
        self._load()

    # --- persistence (crash-safe, atomic) --------------------------------------------------------
    def _load(self):
        try:
            if self.backlog_path.is_file():
                data = json.loads(self.backlog_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and isinstance(data.get("items"), list):
                    self.backlog = [i for i in data["items"] if isinstance(i, dict) and i.get("signature")]
        except (OSError, ValueError):
            self.storage_failed = True

    def _save(self):
        if self.storage_failed:
            return
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            tmp = self.backlog_path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"version": 1, "updated": _now(),
                                       "items": self.backlog[-self.options["max_backlog"]:]},
                                      ensure_ascii=False, indent=1), encoding="utf-8")
            tmp.replace(self.backlog_path)
        except OSError:
            self.storage_failed = True

    def _write_checkpoint(self, item, stage, extra=None):
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            tmp = self.checkpoint_path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"signature": item["signature"], "stage": stage,
                                       "at": _now(), **(extra or {})}, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.checkpoint_path)
        except OSError:
            pass

    def _clear_checkpoint(self):
        try:
            self.checkpoint_path.unlink(missing_ok=True)
        except OSError:
            pass

    # --- scoring + backlog -----------------------------------------------------------------------
    def score(self, item):
        w = self.options["weights"]
        return round(
            w["usefulness"] * item.get("usefulness", 2.0)
            + w["reuse"] * item.get("reuse", 1.0)
            + w["performance"] * item.get("performance", 1.0)
            + w["relevance"] * item.get("relevance", 1.0)
            - w["cost"] * item.get("cost", 1.0)
            - w["risk"] * item.get("risk", 1.0), 3)

    def _learned_names(self):
        learner = getattr(self.actions, "repo_learner", None)
        index = getattr(learner, "index", {}) if learner is not None else {}
        return {name.casefold() for name in (index or {})}

    def refresh_backlog(self):
        """Fold freshly detected gaps into the persistent backlog, deduped and scored."""
        with self.lock:
            existing = {i["signature"]: i for i in self.backlog}
            acquisition = getattr(self.actions, 'acquisition', None)
            if acquisition is not None and acquisition.options['enabled'] and acquisition.options['background_refresh']:
                for key, app in list(acquisition.memory.learned.items())[:1000]:
                    if not key.startswith('capability:') or not isinstance(app, dict):
                        continue
                    for capability in list(app.get('capabilities', {}).values())[:24]:
                        if time.time()-capability.get('seen_at', 0) <= acquisition.options['ttl_seconds']:
                            continue
                        subject = capability.get('identity', '')
                        feature = capability.get('feature', '')
                        sig = _signature('knowledge_refresh', subject+' '+feature)
                        if sig not in existing:
                            row = {'signature': sig, 'kind': 'knowledge_refresh', 'subject': subject, 'feature': feature,
                                'summary': 'Refresh outdated capability evidence', 'evidence': ['Stored evidence exceeded its validity window'],
                                'status': 'pending', 'created': _now(), 'attempts': 0, 'usefulness': 1, 'reuse': 1,
                                'relevance': 1, 'performance': 1, 'cost': .2, 'risk': 0, 'outcome': None}
                            self.backlog.append(row)
                            existing[sig] = row
            for gap in self.detector.detect():
                sig = gap["signature"]
                row = existing.get(sig)
                if row is None:
                    row = {**gap, "status": "pending", "created": _now(), "attempts": 0,
                           "reuse": 1.0, "relevance": 2.0, "cost": 1.0, "risk": 1.0, "outcome": None}
                    self.backlog.append(row)
                    existing[sig] = row
                else:
                    # Refresh evidence/summary but never resurrect a done/rejected item automatically.
                    if row.get("status") == "pending":
                        row["summary"], row["evidence"] = gap["summary"], gap["evidence"]
            if self.options.get("explore", True) and not any(i.get("status") == "pending" for i in self.backlog):
                self._seed_explore(existing)  # Idle with nothing to fix -> study a relevant topic anyway.
            for row in self.backlog:
                row["score"] = self.score(row)
            self._save()
            return list(self.backlog)

    def _seed_explore(self, existing):
        """Queue one exploratory learning topic so a genuinely idle Jarvis still makes progress."""
        topics = self.options.get("explore_topics", []) or []
        for topic in topics:
            sig = _signature("explore", topic)
            if sig not in existing:
                item = {"signature": sig, "kind": "explore", "subject": topic.replace(" python", "").strip(),
                        "summary": "Explore a useful tool: " + topic, "evidence": [], "suggested_query": topic,
                        "status": "pending", "created": _now(), "attempts": 0, "outcome": None,
                        "usefulness": 1.5, "performance": 1.0, "reuse": 1.0, "relevance": 1.0, "cost": 1.0, "risk": 1.0}
                self.backlog.append(item)
                existing[sig] = item
                return
        # Every topic has been tried; re-queue the oldest that did not yield a capability, to retry later.
        stale = sorted((i for i in self.backlog if i.get("kind") == "explore"
                        and i.get("status") in {"exhausted", "failed"}), key=lambda i: i.get("created", ""))
        if stale:
            stale[0]["status"] = "pending"

    def next_job(self):
        with self.lock:
            pending = [i for i in self.backlog if i.get("status") == "pending"]
            pending.sort(key=lambda i: (-i.get("score", 0), i.get("created", "")))
            return pending[0] if pending else None

    # --- idle gating -----------------------------------------------------------------------------
    def _what(self, item):
        """A short human phrase for what Jarvis is learning, for the island card."""
        return (item.get("subject") or item.get("summary") or "a new skill").strip()[:48]

    def _card(self, phase, title, subtitle="", detail=""):
        """Build a Dynamic Island 'Learning' card (service 'evolve') and send it."""
        try:
            from .media_player import card
            self.notify("media_card", card("evolve", phase, title, subtitle, detail=detail))
        except Exception:
            self.notify("media_card", {"service": "evolve", "phase": phase, "title": title,
                                       "subtitle": subtitle, "detail": detail})

    def note_activity(self):
        """Called on every user command: pause learning and interrupt any in-flight step."""
        self.last_activity = self.clock()
        self.stop_current()

    def stop_current(self):
        self._interrupt = True

    def _resources_ok(self):
        try:
            import psutil
        except Exception:
            return False  # Unknown capacity must not start optional learning.
        try:
            available_mb = psutil.virtual_memory().available / (1024 * 1024)
            if available_mb < self.options["min_available_mb"]:
                return False
            if psutil.cpu_percent(interval=None) > self.options["max_cpu_percent"]:
                return False
            battery = psutil.sensors_battery()
            if battery and not battery.power_plugged and battery.percent < 20:
                return False
        except Exception:
            return False
        return True

    def _idle(self):
        if self.stop.is_set() or not self.enabled or self.storage_failed or self.inflight:
            return False
        if self.busy():
            return False
        if self.clock() - self.last_activity < self.options["idle_seconds"]:
            return False
        if self.clock() < self.next_job_at:
            return False
        day = datetime.now(timezone.utc).date().isoformat()
        self.jobs_today = [t for t in self.jobs_today if t == day]
        if len(self.jobs_today) >= self.options["max_jobs_per_day"]:
            return False
        return self._resources_ok()

    # --- the idle loop ---------------------------------------------------------------------------
    def start(self):
        if self.enabled and not self.storage_failed and self.thread is None:
            self.thread = threading.Thread(target=self._run, name="Jarvis self-evolution", daemon=True)
            self.thread.start()
        return self

    def close(self):
        self.stop.set()
        self.stop_current()

    def _run(self):
        while not self.stop.wait(self.options["poll_seconds"]):
            try:
                if self._idle():
                    self.refresh_backlog()
                    job = self.next_job()
                    if job is not None:
                        self.run_job(job)
            except Exception:
                self.next_job_at = self.clock() + self.options["cooldown_seconds"]

    def _cancelled(self):
        return self.stop.is_set() or getattr(self, "_interrupt", False) or self.busy()

    def run_job(self, item):
        """Drive one learning job through the existing pipeline. Checkpointed; never replays writes."""
        with self.lock:
            if item.get("status") != "pending":
                return None
            item["status"] = "learning"
            item["attempts"] = item.get("attempts", 0) + 1
            self.inflight = True
            self._interrupt = False
            self.next_job_at = self.clock() + self.options["cooldown_seconds"]
            self.jobs_today.append(datetime.now(timezone.utc).date().isoformat())
            self._save()
        try:
            self._write_checkpoint(item, "discover")
            if item.get('kind') == 'knowledge_refresh':
                from .knowledge_acquisition import Acquisition
                acquisition = Acquisition(self.actions)  # Task-owned context, same stores/dispatcher.
                if not acquisition.options['background_refresh']:
                    return self._finish(item, 'skipped', 'Background documentation refresh disabled', None)
                goal = 'Learn '+item['subject']+' '+item['feature']
                context = acquisition.prepare(goal, self._cancelled, force=True, background=True)
                if self._cancelled():
                    return self._pause(item, 'knowledge_refresh')
                refreshed = any(row.get('sources') for row in context.get('capabilities', []))
                return self._finish(item, 'researched' if refreshed else 'failed',
                    'Documentation refreshed; no application action or plugin activated' if refreshed else 'No documentation available for refresh', None)
            what = self._what(item)
            self._card("learning", "Learning: " + what, item["summary"][:96], "Finding a skill to learn")
            learner = getattr(self.actions, "repo_learner", None)
            if learner is None or not getattr(learner, "enabled", False):
                return self._finish(item, "skipped", "repository learning is unavailable", None)
            query = item.get("suggested_query") or item.get("subject")
            candidates = []
            try:
                candidates = learner.search(query) or []
            except Exception as exc:
                return self._finish(item, "failed", "discovery failed: " + str(exc)[:120], None)
            if self._cancelled():
                return self._pause(item, "discover")
            learned_names = self._learned_names()
            pick = next((c for c in candidates if isinstance(c, dict)
                         and c.get("full_name", "").casefold() not in learned_names), None)
            if pick is None:
                return self._finish(item, "exhausted", "no new candidate repository found", None)
            full_name = pick["full_name"]
            self._write_checkpoint(item, "learn", {"repo": full_name})
            self._card("learning", "Learning: " + what, "from " + full_name, "Reading the project")
            try:
                learner.learn(full_name, reason="self-evolution", cancelled=self._cancelled)
            except Exception as exc:
                return self._finish(item, "failed", "learning failed: " + str(exc)[:120], full_name)
            if self._cancelled():
                return self._pause(item, "learn")
            # The ability forge auto-builds from the learned repo on its own background thread and
            # emits its own island cards; we record the discovery and surface the capability summary.
            self._card("learned", "Learned: " + what, full_name, "Building a new capability")
            self._remember(item, full_name)
            return self._finish(item, "learned", "learned " + full_name, full_name)
        finally:
            with self.lock:
                self.inflight = False
            self._clear_checkpoint()

    def _pause(self, item, stage):
        with self.lock:
            item["status"] = "pending"  # Resume on a later idle tick; nothing uncertain was replayed.
            self._save()
        self._write_checkpoint(item, stage + ":paused")
        self._card("notice", "Learning paused", "resuming when you're idle",
                   "Your task comes first")
        return None

    def _finish(self, item, status, detail, repo):
        with self.lock:
            item["status"] = status
            item["outcome"] = {"detail": detail, "repo": repo, "at": _now()}
            item["score"] = self.score(item)
            self._save()
        return item

    def _remember(self, item, full_name):
        """Mirror the improvement backlog + a capability note into Obsidian, best-effort."""
        memory = getattr(self.actions, "memory", None)
        if memory is None or not hasattr(memory, "record"):
            return
        try:
            memory.record("Jarvis Improvement Backlog",
                          f"{_now()} — {item['kind']}: {item['summary']} -> learned `{full_name}` "
                          f"(evidence: {'; '.join(item.get('evidence', [])) or 'n/a'}).")
        except Exception:
            pass

    def status(self):
        with self.lock:
            counts = {}
            for item in self.backlog:
                counts[item.get("status", "pending")] = counts.get(item.get("status", "pending"), 0) + 1
            return {"enabled": self.enabled, "idle": self._idle(), "inflight": self.inflight,
                    "backlog": len(self.backlog), "by_status": counts,
                    "jobs_today": len(self.jobs_today), "storage_failed": self.storage_failed}


class SafeEvolutionManager:
    """Gated self-modification of Jarvis's own source: propose -> test in isolation -> approve -> deploy.

    Core deploys ALWAYS require explicit approval (via Actions._approve); backups are kept and a
    regression rolls back automatically. This manager never edits security/permission code and never
    disables its own checks.
    """

    PROTECTED = re.compile(r"(secret|credential|permission|approval|security|auth|token|_approve)", re.I)

    def __init__(self, actions, options=None):
        self.actions = actions
        self.options = {"enabled": True, "auto_deploy": False, **(options or {})}
        self.base = Path(actions.base).resolve()
        self.directory = self.base / ".jarvis-runtime" / "self-evolution" / "patches"

    def _target(self, relative):
        path = (self.base / relative).resolve()
        if not str(path).startswith(str(self.base)) or path.is_symlink():
            raise ValueError("Patch target must be a real file inside the project.")
        if path.suffix.lower() != ".py" or not str(relative).startswith(("jarvis/", "jarvis\\")):
            raise ValueError("Only Jarvis Python source files may be proposed for self-modification.")
        if self.PROTECTED.search(str(relative)):
            raise ValueError("Security/permission source is not eligible for autonomous self-modification.")
        return path

    def propose(self, relative, new_source, rationale=""):
        if not self.options.get("enabled", True):
            raise ValueError("Self-modification is disabled.")
        target = self._target(relative)
        if not target.is_file():
            raise ValueError("Patch target does not exist: " + str(relative))
        if not isinstance(new_source, str) or not new_source.strip():
            raise ValueError("A non-empty replacement source is required.")
        try:
            compile(new_source, str(target), "exec")  # Reject syntactically invalid patches up front.
        except SyntaxError as exc:
            raise ValueError("Proposed source does not parse: " + str(exc)) from None
        pid = "patch_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        folder = self.directory / pid
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "new.py").write_text(new_source, encoding="utf-8")
        (folder / "original.py").write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
        meta = {"id": pid, "relative": str(relative).replace("\\", "/"), "rationale": rationale[:500],
                "created": _now(), "status": "proposed", "tested": None}
        (folder / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
        return meta

    def _git_env(self):
        env = {k: v for k, v in os.environ.items() if k.upper() in
               {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC", "PATHEXT", "APPDATA", "LOCALAPPDATA"}}
        env.update(GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1")
        return env

    def _repo_root(self, env):
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=self.base, env=env,
                             capture_output=True, text=True, timeout=30)
        if out.returncode != 0:
            raise ValueError("Self-modification requires a git repository.")
        return Path(out.stdout.strip())

    def evaluate(self, pid, test_cmd=None, timeout=900):
        """Build+test the patch in an isolated git worktree. Returns the test result; deploys nothing.

        The worktree checks out the whole repository, so the patched file and the test working
        directory are resolved relative to the repo root (the base may be a subdirectory of it).
        """
        folder = self.directory / pid
        meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
        target = self._target(meta["relative"])
        worktree = folder / "worktree"
        env = self._git_env()
        try:
            repo_root = self._repo_root(env)
            rel_to_root = target.resolve().relative_to(repo_root)
            base_in_root = self.base.relative_to(repo_root)
            if worktree.exists():
                shutil.rmtree(worktree, ignore_errors=True)
            subprocess.run(["git", "worktree", "add", "--detach", str(worktree)], cwd=self.base, env=env,
                           capture_output=True, timeout=180, check=True)
        except (subprocess.SubprocessError, OSError, ValueError) as exc:
            meta.update(status="test_error", tested={"ok": False, "detail": "worktree setup failed: " + str(exc)[:160]})
            (folder / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
            return meta["tested"]
        try:
            (worktree / rel_to_root).write_text((folder / "new.py").read_text(encoding="utf-8"), encoding="utf-8")
            work_cwd = worktree / base_in_root  # Run tests from the app directory inside the worktree.
            cmd = test_cmd or [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]
            proc = subprocess.run(cmd, cwd=work_cwd, env=env, capture_output=True, text=True, timeout=timeout)
            ok = proc.returncode == 0
            tail = (proc.stderr or proc.stdout or "")[-400:]
            meta.update(status="tested" if ok else "test_failed", tested={"ok": ok, "detail": tail})
        except subprocess.TimeoutExpired:
            meta.update(status="test_failed", tested={"ok": False, "detail": "tests exceeded the time limit"})
        except (subprocess.SubprocessError, OSError) as exc:
            meta.update(status="test_error", tested={"ok": False, "detail": str(exc)[:200]})
        finally:
            subprocess.run(["git", "worktree", "remove", "--force", str(worktree)], cwd=self.base, env=env,
                           capture_output=True, timeout=60)
        (folder / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
        return meta["tested"]

    def deploy(self, pid, cancelled=lambda: False):
        """Deploy a tested patch after explicit approval; keep a backup; roll back on failure."""
        folder = self.directory / pid
        meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
        if not (meta.get("tested") or {}).get("ok"):
            raise ValueError("Only a patch whose tests passed can be deployed.")
        target = self._target(meta["relative"])
        approve = getattr(self.actions, "_approve", None)
        if approve is None:
            raise ValueError("Core self-modification needs interactive approval, which is unavailable.")
        approve("self_modification", json.dumps({"file": meta["relative"], "rationale": meta.get("rationale", ""),
                                                 "patch": pid}, ensure_ascii=False), cancelled)
        if cancelled():
            raise ValueError("Deployment cancelled during approval.")
        backup = folder / "deployed_backup.py"
        backup.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
        target.write_text((folder / "new.py").read_text(encoding="utf-8"), encoding="utf-8")
        meta.update(status="deployed", deployed_at=_now())
        (folder / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
        return meta

    def rollback(self, pid):
        folder = self.directory / pid
        meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
        backup = folder / "deployed_backup.py"
        if not backup.is_file():
            raise ValueError("No deployed backup to roll back.")
        target = self._target(meta["relative"])
        target.write_text(backup.read_text(encoding="utf-8"), encoding="utf-8")
        meta.update(status="rolled_back", rolled_back_at=_now())
        (folder / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
        return meta
