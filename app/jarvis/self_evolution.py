"""Jarvis's self-evolution engine: autonomous, idle-only capability expansion.

This is the orchestration brain that closes the Discover -> Analyze -> Learn -> Integrate ->
Remember -> Repeat loop over the subsystems Jarvis already has. It does NOT reimplement them:

- GitHub discovery, download and static understanding: jarvis/repo_learning.py (RepoLearner),
  repo_analysis.py, repo_acquisition.py.
- Capability extraction, guarded generation, validation, registry and activation:
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
   -> build -> test -> require explicit approval -> deploy with backup -> explicit stale-safe rollback.
   Never autonomous, never silently disables its checks.

Downloaded code and repository text remain untrusted (handled by the reused subsystems). Nothing here
executes repository code in-process; abilities run out of process through the existing forge.
"""
import json
import hashlib
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

DEFAULTS = dict(
    enabled=True,
    idle_seconds=90,          # Quiet time before a learning step may start.
    poll_seconds=5.0,         # Idle-thread tick.
    cooldown_seconds=600,     # Between learning jobs.
    max_jobs_per_day=4,
    max_backlog=200,
    max_attempts=3,
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
    if options is not None and not isinstance(options, dict):
        raise ValueError('self_evolution must be an object')
    merged = {**DEFAULTS,'weights':dict(DEFAULTS['weights']),
              'self_modification':dict(DEFAULTS['self_modification']),'explore_topics':list(DEFAULTS['explore_topics'])}
    for key, value in (options or {}).items():
        if key in {"weights", "self_modification"} and isinstance(value, dict):
            merged[key] = {**DEFAULTS[key], **value}
        elif key in merged:
            merged[key] = value
    for flag in ('enabled','explore'):
        if type(merged[flag]) is not bool:raise ValueError('Invalid evolution boolean: '+flag)
    ranges={'idle_seconds':(0,3600),'poll_seconds':(.1,60),'cooldown_seconds':(0,86400),
            'max_jobs_per_day':(0,100),'max_backlog':(1,1000),'max_attempts':(1,10),
            'min_available_mb':(0,65536),'max_cpu_percent':(0,100)}
    for key,(low,high) in ranges.items():
        v=merged[key]
        if type(v) not in (int,float) or not math.isfinite(v) or not low<=v<=high:
            raise ValueError('Invalid evolution bound: '+key)
        if key in {'max_jobs_per_day','max_backlog','max_attempts'} and type(v) is not int:
            raise ValueError('Evolution count must be integer: '+key)
    if not isinstance(merged['weights'],dict) or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=100 for v in merged['weights'].values()):
        raise ValueError('Invalid evolution weights')
    if not isinstance(merged['explore_topics'],list) or len(merged['explore_topics'])>100 or any(not isinstance(t,str) or len(t)>180 for t in merged['explore_topics']):
        raise ValueError('Invalid bounded evolution topics')
    modification=merged['self_modification']
    if not isinstance(modification,dict) or type(modification.get('enabled')) is not bool or modification.get('auto_deploy') is not False:
        raise ValueError('Self-modification requires boolean enabled and auto_deploy=false')
    return merged


def _battery_saver():
    """Read Windows power-saving state; unknown Windows state defers optional work."""
    if os.name!='nt':return False
    try:
        import ctypes
        class Power(ctypes.Structure):
            _fields_=[('ac',ctypes.c_ubyte),('flag',ctypes.c_ubyte),('percent',ctypes.c_ubyte),
                      ('saver',ctypes.c_ubyte),('life',ctypes.c_ulong),('full',ctypes.c_ulong)]
        status=Power()
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):return True
        return bool(status.saver)
    except Exception:return True


def _signature(kind, subject):
    return kind + ":" + re.sub(r"[^a-z0-9]+", "-", str(subject).casefold()).strip("-")[:60]


class CapabilityGapDetector:
    """Read-only mining of Jarvis's own records into evidence-backed improvement gaps."""

    def __init__(self, actions):
        self.actions = actions

    def detect(self):
        gaps = {}

        def add(kind, subject, summary, evidence, query, usefulness=2.0, performance=1.0):
            from .repo_learning import public_query
            from .anticipation import safe_topic
            if not safe_topic(str(subject)) or not public_query(str(query)) or re.search(r"\b(?:don't|do not|never|stop|cancel|reject|deny)\b",str(subject),re.I):
                return
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
        self.trace_id = uuid.uuid4().hex
        self._resource_checked = (-float('inf'),False)
        self.skill_repairs = {}         # skill_id -> failure causes awaiting a validated FIX.
        self._skills_checked_at = -float('inf')
        self._memory_checked_at = -float('inf')
        self.last_memory_report = None
        self._research_checked_at = -float('inf')
        self.last_research = None
        self._load()

    # --- persistence (crash-safe, atomic) --------------------------------------------------------
    def _load(self):
        try:
            if self.backlog_path.is_file():
                if self.backlog_path.stat().st_size>2**20:raise ValueError('backlog exceeds limit')
                data = json.loads(self.backlog_path.read_text(encoding="utf-8"))
                if not isinstance(data,dict):raise ValueError('backlog must be an object')
                if isinstance(data, dict) and isinstance(data.get("items"), list):
                    self.backlog = [i for i in data["items"] if isinstance(i, dict) and i.get("signature")]
                    for row in self.backlog:
                        if (not isinstance(row['signature'],str) or len(row['signature'])>200 or
                                type(row.get('attempts',0)) is not int or row.get('attempts',0)<0 or
                                type(row.get('score',0)) not in (int,float) or not math.isfinite(row.get('score',0))):
                            raise ValueError('Invalid backlog row')
                    self.backlog=self.backlog[-self.options['max_backlog']:]
                    self.jobs_today=[v for v in data.get('jobs_today',[]) if isinstance(v,str)][-100:]
                    for row in self.backlog:
                        if row.get('status')=='learning':
                            stage=row.get('stage','unknown')
                            row['status']='pending' if stage=='discover' else 'needs_review'
                            row['outcome']={'detail':'Interrupted '+stage+'; fresh state review required for uncertain writes','trace_id':self.trace_id}
        except (OSError, ValueError, TypeError, RecursionError):
            self.storage_failed = True

    def _save(self):
        if self.storage_failed:
            return
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            tmp = self.backlog_path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"version": 1, "updated": _now(),
                                       "jobs_today":self.jobs_today[-100:], "items": self.backlog[-self.options["max_backlog"]:]},
                                      ensure_ascii=True, indent=1), encoding="utf-8")
            tmp.replace(self.backlog_path)
        except OSError:
            self.storage_failed = True

    def _write_checkpoint(self, item, stage, extra=None):
        item['stage']=stage
        if extra:item.update(extra)
        self._save()
        if self.storage_failed:return False
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            tmp = self.checkpoint_path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"signature": item["signature"], "stage": stage,
                                       "trace_id":self.trace_id,"at": _now(), **(extra or {})}, ensure_ascii=True), encoding="utf-8")
            tmp.replace(self.checkpoint_path)
            return True
        except OSError:
            self.storage_failed=True
            return False

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
            self.backlog=self.backlog[-self.options['max_backlog']:]
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
                        and i.get("status") in {"exhausted", "failed"}
                        and i.get('attempts',0)<self.options['max_attempts']), key=lambda i: i.get("created", ""))
        if stale:
            stale[0]["status"] = "pending"

    def next_job(self):
        with self.lock:
            return min((i for i in self.backlog if i.get("status") == "pending"
                        and i.get('attempts',0)<self.options['max_attempts']),
                       key=lambda i:(-i.get('score',0),i.get('created','')),default=None)

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
        if _battery_saver():return False
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

    def skill_maintenance(self):
        """Idle-time living-skill upkeep: trust from verified outcomes and degraded-skill detection.

        Reports only state changes backed by stored evidence; a degraded skill becomes a FIX
        candidate, never an unvalidated rewrite.
        """
        skills = getattr(self.actions, 'skills', None)
        store = getattr(skills, 'store', None)
        if store is None:
            return []
        from .skill_evolution import degraded, update_trust
        notes = []
        for row in list(getattr(skills, 'catalog', [])):
            identifier = row.get('skill_id')
            if not identifier:
                continue
            before = row.get('trust_state')
            after = update_trust(store, identifier)
            if after and after != before:
                row['trust_state'] = after
                notes.append({'skill': row['name'], 'trust_state': after})
                metrics = store.metrics(identifier)
                self._card('learned' if after == 'trusted' else 'notice', 'Skill ' + after + ': ' + row['name'][:40],
                           str(metrics['completed_verified_count']) + ' independently verified uses',
                           'Trust follows recorded task outcomes; approvals are unchanged')
            bad, metrics = degraded(store, identifier)
            if bad and identifier not in self.skill_repairs:
                self.skill_repairs[identifier] = sorted(metrics['failure_causes'])
                notes.append({'skill': row['name'], 'fix_candidate': self.skill_repairs[identifier]})
                self._card('notice', 'Skill needs repair: ' + row['name'][:40],
                           'Repeated failures: ' + ', '.join(self.skill_repairs[identifier])[:80],
                           'A repair is applied only after validation')
        return notes

    def memory_maintenance(self):
        """Idle: incremental vault index, lesson compaction, one isolated exploration episode (all preemptible)."""
        learning = getattr(self.actions, 'learning', None)
        if learning is None:
            return None
        from .learning_memory import options, sandbox_registry_factory
        factory = None
        exploration = options(getattr(self.actions, 'config', {}), 'exploration')
        explorer = getattr(learning, 'explorer', None)
        if explorer is not None:
            day = datetime.now(timezone.utc).date().isoformat()
            count = explorer.state.get('episodes_today', {}).get(day, 0)
            if count < exploration['max_episodes_per_day']:
                factory = sandbox_registry_factory(self.actions)
                explorer.state['episodes_today'] = {day: count + 1}
        self.last_memory_report = learning.maintenance(self._cancelled, factory)
        verified = (self.last_memory_report or {}).get('exploration') or {}
        if verified.get('status') == 'completed':
            self._card('learned', 'Explored: ' + str(verified.get('goal_id', ''))[:40],
                       'Verified in an isolated sandbox', 'Lesson saved; no action taken on your files')
        return self.last_memory_report

    def research_options(self):
        settings = dict(enabled=True, max_experiments_per_day=1, budget_seconds=2400, check_interval_seconds=3600)
        settings.update((getattr(self.actions, 'config', {}) or {}).get('evolution_lab', {}) or {})
        if (type(settings['enabled']) is not bool or type(settings['max_experiments_per_day']) is not int
                or not 0 <= settings['max_experiments_per_day'] <= 10
                or type(settings['budget_seconds']) not in (int, float) or not 60 <= settings['budget_seconds'] <= 14400
                or type(settings['check_interval_seconds']) not in (int, float) or settings['check_interval_seconds'] < 60):
            raise ValueError('Invalid evolution_lab configuration')
        return settings

    def research_maintenance(self):
        """Idle: one bounded autoresearch experiment in the isolated lab. Never touches production.

        A qualified candidate becomes a proposal card; deploying it needs explicit approval later.
        """
        settings = self.research_options()
        if not settings['enabled']:
            return None
        state_path = self.directory / 'research-schedule.json'
        day = datetime.now(timezone.utc).date().isoformat()
        try:
            state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.is_file() else {}
        except (OSError, ValueError):
            state = {}
        if state.get('day') == day and state.get('count', 0) >= settings['max_experiments_per_day']:
            return None
        self.directory.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({'day': day, 'count': (state.get('count', 0) if state.get('day') == day else 0) + 1}),
                              encoding='utf-8')
        from .autoresearch import AutoResearch
        research = AutoResearch(self.actions.base)
        research.recover()
        self._card('learning', 'Improving myself', 'Testing one bounded change in an isolated copy', 'Your files are not touched')
        self.last_research = research.run_experiment(cancelled=self._cancelled, budget_seconds=settings['budget_seconds'])
        qualified = [p for p in self.last_research.get('proposals', []) if p.get('decision') == 'qualified']
        if qualified:
            self._card('notice', 'Improvement proposal ready', qualified[0]['hypothesis'][:96],
                       'Say "review improvement proposals"; nothing changes without your approval')
        return self.last_research

    def _run(self):
        while not self.stop.wait(self.options["poll_seconds"]):
            try:
                if self._idle() and self.clock() - self._skills_checked_at >= 600:
                    self._skills_checked_at = self.clock()
                    self.skill_maintenance()
                if self._idle() and self.clock() - self._memory_checked_at >= 1800:
                    self._memory_checked_at = self.clock()
                    self.memory_maintenance()
                if (self._idle() and self.clock() - self._research_checked_at
                        >= self.research_options()['check_interval_seconds']):
                    self._research_checked_at = self.clock()
                    self.research_maintenance()
                if self._idle():
                    self.refresh_backlog()
                    job = self.next_job()
                    if job is not None:
                        self.run_job(job, require_idle=True)
            except Exception as exc:
                self.notify('repair','Self-evolution deferred: '+type(exc).__name__)
                self.next_job_at = self.clock() + self.options["cooldown_seconds"]

    def _cancelled(self):
        if self.stop.is_set() or getattr(self, "_interrupt", False) or self.busy():return True
        when,ok=self._resource_checked
        if self.clock()-when>=1:
            ok=self._resources_ok();self._resource_checked=(self.clock(),ok)
        return not ok

    def run_job(self, item, require_idle=False):
        """Drive one learning job through the existing pipeline. Checkpointed; never replays writes."""
        with self.lock:
            if (item.get("status") != "pending" or self.inflight or self.stop.is_set() or self.storage_failed
                    or self.busy() or item.get('attempts',0)>=self.options['max_attempts']
                    or require_idle and not self._idle()):
                return None
            item["status"] = "learning"
            item["attempts"] = item.get("attempts", 0) + 1
            self.inflight = True
            self._interrupt = False
            self.next_job_at = self.clock() + self.options["cooldown_seconds"]
            self.jobs_today.append(datetime.now(timezone.utc).date().isoformat())
            self._save()
        try:
            if not self._write_checkpoint(item, "discover"):
                return self._finish(item,'needs_review','checkpoint storage unavailable',None)
            if self._cancelled():return self._pause(item,'discover')
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
            from .repo_learning import canonical_name,public_query
            if not isinstance(query,str) or len(query)>180 or not public_query(query):
                return self._finish(item,'skipped','Discovery requires a bounded public topic',None)
            candidates = []
            try:
                candidates = learner.search(query) or []
            except Exception as exc:
                return self._finish(item, "failed", "discovery failed: " + type(exc).__name__, None)
            if self._cancelled():
                return self._pause(item, "discover")
            learned_names = self._learned_names()
            if not isinstance(candidates,list) or len(candidates)>100:
                return self._finish(item,'failed','Malformed bounded discovery response',None)
            candidates=[c for c in candidates if isinstance(c,dict) and isinstance(c.get('full_name'),str)]
            pick = next((c for c in candidates if isinstance(c, dict)
                         and c.get("full_name", "").casefold() not in learned_names), None)
            if pick is None:
                return self._finish(item, "exhausted", "no new candidate repository found", None)
            full_name = pick["full_name"]
            try:full_name=canonical_name(full_name)
            except ValueError:return self._finish(item,'failed','Invalid repository identity',None)
            if not self._write_checkpoint(item, "learn", {"repo": full_name}):
                return self._finish(item,'needs_review','checkpoint storage unavailable',full_name)
            if self._cancelled():return self._pause(item,'discover')
            self._card("learning", "Learning: " + what, "from " + full_name, "Reading the project")
            try:
                learner.learn(full_name, reason="self-evolution", cancelled=self._cancelled)
            except Exception as exc:
                return self._finish(item, "needs_review", "learning outcome uncertain: " + type(exc).__name__, full_name)
            if self._cancelled():
                return self._pause(item, "learn")
            # The ability forge auto-builds from the learned repo on its own background thread and
            # emits its own island cards; we record the discovery and surface the capability summary.
            self._card("learned", "Learned: " + what, full_name, "Knowledge saved; new abilities still require approval")
            self._remember(item, full_name)
            return self._finish(item, "learned", "learned " + full_name, full_name)
        finally:
            with self.lock:
                self.inflight = False
            if item.get('status') not in {'pending','needs_review','learning'}:self._clear_checkpoint()

    def _pause(self, item, stage):
        with self.lock:
            item["status"] = "needs_review" if stage=='learn' else "pending"
            self._save()
        self._write_checkpoint(item, stage + ":paused")
        self._card("notice", "Learning paused", "fresh state review required" if stage=='learn' else "resuming when you're idle",
                   "Your task comes first")
        return None

    def _finish(self, item, status, detail, repo):
        with self.lock:
            item["status"] = status
            item["outcome"] = {"detail": detail, "repo": repo, "at": _now(),'trace_id':self.trace_id}
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
    rollback is explicit and refuses later edits. Named policy/runtime modules are excluded;
    a worktree is not a hostile-code sandbox or a semantic privacy oracle.
    """

    PROTECTED = re.compile(r"(secret|credential|permission|approval|security|auth|token|_approve)", re.I)

    def __init__(self, actions, options=None):
        self.actions = actions
        self.options = {"enabled": True, "auto_deploy": False, **(options or {})}
        self.base = Path(actions.base).resolve()
        self.directory = self.base / ".jarvis-runtime" / "self-evolution" / "patches"
        if type(self.options['enabled']) is not bool or self.options['auto_deploy'] is not False:
            raise ValueError('Self-modification requires explicit approval; auto_deploy must remain false.')
        self.validations = {}  # Process-owned receipts: edited JSON cannot forge an evaluation.
        self.lock = threading.RLock()

    def _target(self, relative):
        from .skill_memory import linked
        if not isinstance(relative,str) or len(relative)>300 or '..' in relative.replace('\\','/').split('/'):
            raise ValueError('Patch target has invalid scope.')
        candidate=self.base/relative
        if any(linked(p) for p in [candidate,*candidate.parents] if p!=self.base and self.base in p.parents):
            raise ValueError('Linked patch targets are refused.')
        path = (self.base / relative).resolve()
        if self.base not in path.parents or path.is_symlink():
            raise ValueError("Patch target must be a real file inside the project.")
        if path.suffix.lower() != ".py" or not str(relative).startswith(("jarvis/", "jarvis\\")):
            raise ValueError("Only Jarvis Python source files may be proposed for self-modification.")
        if self.PROTECTED.search(str(relative)):
            raise ValueError("Security/permission source is not eligible for autonomous self-modification.")
        if path.name in {'actions.py','self_evolution.py','cloud_policy.py','repo_abilities.py','repository_skills.py',
                         'tools.py','native_tools.py','commands.py','brain.py','knowledge_worker.py','deliberation.py',
                         'task_recovery.py','recovery.py','launcher.py','gpu_scheduler.py'}:
            raise ValueError('Core policy/runtime source is outside the patch scope.')
        return path

    def _folder(self,pid):
        from .skill_memory import linked
        if not isinstance(pid,str) or not re.fullmatch(r'patch_\d{8}T\d{12}',pid):
            raise ValueError('Invalid patch identifier.')
        folder=self.directory/pid
        if any(linked(p) for p in [folder,*folder.parents] if p!=self.base and self.base in p.parents):
            raise ValueError('Linked patch storage refused.')
        return folder

    def _binding(self,folder,meta):
        target=self._target(meta['relative'])
        original=(folder/'original.py').read_bytes();current=target.read_bytes()
        if original!=current:raise ValueError('Patch target changed since proposal; re-propose against fresh source.')
        digest=hashlib.sha256(meta['relative'].encode()+b'\0'+original+b'\0'+(folder/'new.py').read_bytes())
        # Bind neighboring source/tests and declared environment inputs too. A passing
        # receipt must not survive an edit to the code it exercised or its assertions.
        from .skill_memory import linked
        count=total=0
        for pattern in ('jarvis/*.py','tests/*.py','requirements/*.txt','config/runtime_manifest.json','pytest.ini','pyproject.toml'):
            for path in sorted(self.base.glob(pattern)):
                count+=1;total+=path.stat().st_size
                if count>1000 or total>20*2**20 or linked(path):raise ValueError('Evaluation input snapshot exceeds safe bounds or is linked.')
                digest.update(path.relative_to(self.base).as_posix().encode()+b'\0'+path.read_bytes())
        return digest.hexdigest()

    def propose(self, relative, new_source, rationale=""):
        if not self.options.get("enabled", True):
            raise ValueError("Self-modification is disabled.")
        target = self._target(relative)
        if not target.is_file():
            raise ValueError("Patch target does not exist: " + str(relative))
        if not isinstance(new_source, str) or not new_source.strip():
            raise ValueError("A non-empty replacement source is required.")
        if len(new_source)>1000000:raise ValueError('Patch source exceeds the size limit.')
        try:
            compile(new_source, str(target), "exec")  # Reject syntactically invalid patches up front.
        except SyntaxError as exc:
            raise ValueError("Proposed source does not parse: " + str(exc)) from None
        pid = "patch_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        folder = self._folder(pid)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "new.py").write_text(new_source, encoding="utf-8")
        (folder / "original.py").write_bytes(target.read_bytes())
        meta = {"id": pid, "relative": str(relative).replace("\\", "/"), "rationale": rationale[:500],
                "created": _now(), "status": "proposed", "tested": None}
        (folder / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
        return meta

    def _git_env(self):
        env = {k: v for k, v in os.environ.items() if k.upper() in
               {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC", "PATHEXT", "APPDATA", "LOCALAPPDATA"}}
        env.update(GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1")
        env.update(GIT_CONFIG_GLOBAL=os.devnull,GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='core.hooksPath',GIT_CONFIG_VALUE_0=os.devnull)
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
        folder = self._folder(pid)
        meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
        self.validations.pop(pid,None)
        binding=self._binding(folder,meta)
        approved_cmd=[sys.executable,'-m','pytest','tests','-q']
        if test_cmd is not None and test_cmd!=approved_cmd:raise ValueError('Evaluation requires the full pytest regression command.')
        target = self._target(meta["relative"])
        worktree = folder / "worktree"
        env = self._git_env()
        try:
            repo_root = self._repo_root(env)
            status=subprocess.run(['git','status','--porcelain'],cwd=self.base,env=env,capture_output=True,text=True,timeout=30)
            if status.returncode or status.stdout.strip():raise ValueError('Evaluation requires a clean source snapshot; dirty work is preserved.')
            rel_to_root = target.resolve().relative_to(repo_root)
            base_in_root = self.base.relative_to(repo_root)
            if worktree.exists():
                raise ValueError('Existing evaluation workspace preserved; review before reuse.')
            subprocess.run(["git", "worktree", "add", "--detach", str(worktree)], cwd=self.base, env=env,
                           capture_output=True, timeout=180, check=True)
        except (subprocess.SubprocessError, OSError, ValueError) as exc:
            meta.update(status="test_error", tested={"ok": False, "detail": "worktree setup failed: " + str(exc)[:160]})
            (folder / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
            return meta["tested"]
        try:
            (worktree / rel_to_root).write_text((folder / "new.py").read_text(encoding="utf-8"), encoding="utf-8")
            work_cwd = worktree / base_in_root  # Run tests from the app directory inside the worktree.
            cmd = approved_cmd
            proc = subprocess.run(cmd, cwd=work_cwd, env=env, capture_output=True, text=True, timeout=timeout)
            ok = proc.returncode == 0
            changed=subprocess.run(['git','diff','--name-only'],cwd=worktree,env=env,capture_output=True,text=True,timeout=30)
            ok=ok and changed.returncode==0 and set(changed.stdout.splitlines())=={rel_to_root.as_posix()}
            ok=ok and self._binding(folder,meta)==binding and (worktree/rel_to_root).read_bytes()==(folder/'new.py').read_bytes()
            tail = (proc.stderr or proc.stdout or "")[-400:]
            meta.update(status="tested" if ok else "test_failed", tested={"ok": ok, "detail": tail})
            if ok:self.validations[pid]=binding
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
        with self.lock:return self._deploy(pid,cancelled)

    def _deploy(self,pid,cancelled):
        """Deploy a tested patch after explicit approval; keep a backup; roll back on failure."""
        if not self.options['enabled'] or cancelled():raise ValueError('Self-modification disabled or cancelled.')
        folder = self._folder(pid)
        meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
        if ((meta.get("tested") or {}).get("ok") is not True or
                self.validations.get(pid)!=self._binding(folder,meta)):
            raise ValueError("Only a patch whose tests passed can be deployed.")
        target = self._target(meta["relative"])
        approve = getattr(self.actions, "_approve", None)
        if approve is None:
            raise ValueError("Core self-modification needs interactive approval, which is unavailable.")
        reviewed=self._binding(folder,meta)
        answer=approve("self_modification", json.dumps({"file": meta["relative"], "rationale": meta.get("rationale", ""),
                                                 "patch": pid,'binding':reviewed,'new_source':(folder/'new.py').read_text(encoding='utf-8')}, ensure_ascii=False), cancelled)
        if answer is not None and answer is not True:raise ValueError('Explicit approval was not given.')
        latest=json.loads((folder/'meta.json').read_text(encoding='utf-8'))
        if cancelled() or not self.options['enabled'] or latest.get('relative')!=meta['relative'] or self._binding(folder,meta)!=reviewed:
            raise ValueError("Deployment cancelled during approval.")
        backup = folder / "deployed_backup.py"
        backup.write_bytes(target.read_bytes())
        meta['status']='deploying'
        (folder/'meta.json').write_text(json.dumps(meta,indent=1),encoding='utf-8')
        self.validations.pop(pid,None)
        self._replace_source(target,(folder/'new.py').read_bytes())
        meta.update(status="deployed", deployed_at=_now())
        (folder / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
        return meta

    def rollback(self, pid):
        with self.lock:return self._rollback(pid)

    def _replace_source(self,target,source):
        temporary=target.with_name(target.name+'.'+uuid.uuid4().hex+'.tmp')
        with temporary.open('xb') as handle:handle.write(source)
        shutil.copymode(target,temporary)
        temporary.replace(target)

    def _rollback(self,pid):
        folder = self._folder(pid)
        meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
        backup = folder / "deployed_backup.py"
        if not backup.is_file():
            raise ValueError("No deployed backup to roll back.")
        target = self._target(meta["relative"])
        if meta.get('status')!='deployed' or target.read_bytes()!=(folder/'new.py').read_bytes():
            raise ValueError('Deployed source changed; automatic overwrite refused.')
        self._replace_source(target,backup.read_bytes())
        meta.update(status="rolled_back", rolled_back_at=_now())
        (folder / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
        return meta
