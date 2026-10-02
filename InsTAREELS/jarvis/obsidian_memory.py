"""Local, append-only Obsidian notes for observed Jarvis and foreground activity."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import threading
import time


SENSITIVE = re.compile(r"(?i)(password|passcode|secret|api[_ -]?key|access[_ -]?token|authorization|bearer|credential|private key)")
WORDS = re.compile(r"[\w.-]{3,}", re.UNICODE)
RECALL = re.compile(r"(?i)\b(remember|recall|did i|was i|what did|when did|worked on|opened|used today|yesterday|recently|history|activity)\b")
PERSONAL = re.compile(r"(?i)\b(my|mine|myself|i am|i'm|am i|family|brother|father|mother|birthday|birth date|age|hometown|home town|kunal|vaghani|jaydeep|rajeshbhai|alkaben|where do i live|where am i from|what job do i want|where do i want to work)\b")


def clean(value, limit=400):
    """Keep notes short and avoid storing obvious credential-bearing text."""
    value = " ".join(str(value).split())[:limit]
    return "[redacted sensitive text]" if SENSITIVE.search(value) else value.replace("`", "'")


class ObsidianMemory:
    def __init__(self, base, options=None):
        options = options or {}
        self.base = Path(base)
        self.hermes_skills_enabled = bool(options.get('hermes_skills', False))
        self.experience_options = options.get('experience_learning', {})
        self.enabled = bool(options.get("enabled", False))
        raw = options.get("vault", ".jarvis-runtime/obsidian-vault")
        self.vault = (Path(raw) if Path(raw).is_absolute() else Path(base) / raw).resolve()
        self.lock = threading.RLock()
        self.error = None
        self.linked_notes = set()
        self.window = None
        self.window_since = None
        self.last_observation = 0.0
        self.index_thread = None
        self.index_stop = threading.Event()
        self.index_attempt = 0.0
        self.index_data = None
        self.index_mtime = None

    def _index(self):
        from .memory_index import load_index
        if not self.enabled:
            return None
        with self.lock:
            try:
                stat = (self.vault / "Jarvis Index.json").stat()
                mtime = (stat.st_mtime_ns, stat.st_size)
            except OSError:
                return None
            if self.index_mtime != mtime:
                self.index_data = load_index(self.vault)
                self.index_mtime = mtime
            return self.index_data

    def task_context(self, goal):
        from .memory_index import context
        return context(self._index(), goal)

    def program_matches(self, name):
        from .capabilities import program_matches
        return program_matches(self._index(), name)

    def catalogue_answer(self, question):
        from .memory_index import catalogue_answer
        skills = getattr(self, "skills", None)
        if self.enabled and skills is not None and re.search(r'\b(?:learned experiences|experience memory|experience cases)\b', question, re.I):
            bank = getattr(skills, 'experiences', None)
            if bank is not None:
                if bank.error:
                    return 'Experience memory needs review: ' + bank.error
                if not bank.enabled:
                    return 'Experience learning is disabled in memory.experience_learning.'
                with bank.lock:
                    cases = list(bank.cases.values())
                return (f'Jarvis has {len(cases)} experience cases: '
                        f'{sum(c["verified"] for c in cases)} verified outcomes, '
                        f'{sum(c["uncertain"] for c in cases)} uncertain outcomes and '
                        f'{sum(c["recovered"] for c in cases)} verified recoveries. '
                        'Open Jarvis Experiences in Obsidian for conditions, reported failures and proof scopes. '
                        'These cases guide new plans; they do not update model weights or replay actions.')
        if self.enabled and skills is not None and re.search(r"\b(?:skills|learned procedures|learned workflows)\b", question, re.I):
            skills.refresh()
            if skills.error:
                return "Skill memory needs repair: " + skills.error
            upstream = getattr(skills, 'upstream', None)
            if upstream is not None:
                if skills.upstream_error:
                    return "Hermes skill reference needs repair: " + skills.upstream_error + ". Native Jarvis guides remain available."
                rows = upstream.search(question, include_unsupported=True)
                return (f"Jarvis has {len(skills.catalog)} local guides and {len(upstream.rows)} Hermes reference skills "
                        f"({sum(upstream.compatible(r) for r in upstream.rows)} declare Windows support; prerequisites still need checking). "
                        + 'Local guides: ' + ', '.join(s['name'] for s in skills.catalog[:20]) + '. '
                        + "Relevant Hermes skills: " + ', '.join(r['name'] for r in rows[:8])
                        + f". {len(skills.procedures)} verified procedures are saved in Obsidian. Full catalogue: Jarvis Hermes Skills.")
            return ("Jarvis skills: " + ", ".join(item["name"] for item in skills.catalog)
                    + f". {len(skills.procedures)} verified procedures are saved in Obsidian. Relevant guidance is retrieved for tasks and coding; results are checked again.")
        return catalogue_answer(self._index(), question)

    def project_matches(self, name):
        from .memory_index import project_matches
        return project_matches(self._index(), name)

    def ensure_index(self, config):
        """Refresh at most hourly off the response path; stop writes on intentional close."""
        if not self.enabled or self.index_stop.is_set():
            return
        with self.lock:
            now = time.monotonic()
            if (self.index_thread and self.index_thread.is_alive()) or (self.index_attempt and now - self.index_attempt < 3600):
                return
            self.index_attempt = now
            def refresh():
                from .memory_index import build_index, write_index
                try:
                    data = build_index(config, cancelled=self.index_stop.is_set)
                    with self.lock:
                        if not self.index_stop.is_set() and self.enabled:
                            write_index(self.vault, data)
                            self.index_data = data
                            stat = (self.vault / "Jarvis Index.json").stat()
                            self.index_mtime = (stat.st_mtime_ns, stat.st_size)
                except (OSError, ValueError) as exc:
                    self.error = "Memory catalogue refresh: " + str(exc)
            self.index_thread = threading.Thread(target=refresh, name="jarvis-memory-index", daemon=True)
            self.index_thread.start()

    def start(self):
        if not self.enabled:
            return
        (self.vault / "Daily").mkdir(parents=True, exist_ok=True)
        home = self.vault / "Jarvis Brain.md"
        if not home.exists():
            home.write_text("# Jarvis Brain\n\nDaily notes in `Daily/` contain observed foreground windows and Jarvis interactions. "
                "Window activity records visible titles and duration, not page contents or every action. "
                "Entries are local historical observations; Jarvis checks fresh PC state for current answers.\n", encoding="utf-8")
        for note in sorted((self.vault / "Daily").glob("????-??-??.md")):
            self._link_note(note)

    def _link_note(self, note):
        """Make the vault graph show the relationship without changing existing entries."""
        home = self.vault / "Jarvis Brain.md"
        link = f"[[Daily/{note.stem}|{note.stem}]]"
        if link not in home.read_text(encoding="utf-8"):
            with home.open("a", encoding="utf-8") as output:
                output.write(f"\n- {link}\n")
        if "[[Jarvis Brain]]" not in note.read_text(encoding="utf-8"):
            with note.open("a", encoding="utf-8") as output:
                output.write("\n[[Jarvis Brain]]\n")
        self.linked_notes.add(note)

    def _append(self, at, kind, detail):
        if not self.enabled:
            return
        note = self.vault / "Daily" / (at.strftime("%Y-%m-%d") + ".md")
        if not note.exists():
            note.write_text("# " + at.strftime("%Y-%m-%d") + "\n\n", encoding="utf-8")
        if note not in self.linked_notes:
            self._link_note(note)
        with note.open("a", encoding="utf-8") as output:
            output.write(f"- {at.strftime('%H:%M:%S')} UTC | {kind}: {clean(detail)}\n")

    def record(self, kind, detail):
        if not self.enabled or not detail:
            return
        with self.lock:
            try:
                self._append(datetime.now(timezone.utc), clean(kind, 40), detail)
            except OSError as exc:
                self.error = str(exc)
                self.enabled = False

    def observe_window(self, title, pid=None, now=None):
        """Summarize a foreground interval on switch or every five minutes."""
        if not self.enabled:
            return
        now = time.time() if now is None else now
        if now - self.last_observation < 3:
            return
        self.last_observation = now
        title = clean(title, 180)
        if not title:
            return
        identity = (title, pid)
        with self.lock:
            if identity == self.window and now - self.window_since < 300:
                return
            if self.window is not None:
                minutes = max(0, round((now - self.window_since) / 60, 1))
                at = datetime.fromtimestamp(now, timezone.utc)
                try:
                    self._append(at, "Foreground window", f"{self.window[0]} (observed about {minutes} min)")
                except OSError as exc:
                    self.error = str(exc)
                    self.enabled = False
                    return
            self.window, self.window_since = identity, now

    def close(self):
        self.index_stop.set()
        if not self.enabled:
            return
        with self.lock:
            if self.window is not None:
                minutes = max(0, round((time.time() - self.window_since) / 60, 1))
                try:
                    self._append(datetime.now(timezone.utc), "Foreground window",
                                 f"{self.window[0]} (observed about {minutes} min)")
                except OSError as exc:
                    self.error = str(exc)
                self.window = self.window_since = None

    def recall(self, question, limit=8):
        """Read a bounded set of relevant recent observations for one answer."""
        if not self.enabled:
            return []
        terms = {word.casefold() for word in WORDS.findall(question)} - {
            "what", "when", "where", "about", "this", "that", "have", "with", "from", "project", "computer", "today"}
        broad = bool(RECALL.search(question))
        lower = question.casefold()
        local_day = datetime.now().astimezone().date()
        requested_day = (local_day if "today" in lower else
                         local_day - timedelta(days=1) if "yesterday" in lower else None)
        candidates = []
        with self.lock:
            active = self.window
            active_since = self.window_since
        if active is not None:
            minutes = max(0, round((time.time() - active_since) / 60, 1))
            line = f"- current | Foreground window: {active[0]} (observed about {minutes} min so far)"
            hits = len(terms & {word.casefold() for word in WORDS.findall(line)})
            if (hits or broad) and (requested_day is None or requested_day == local_day):
                candidates.append((hits, datetime.now(timezone.utc).strftime("%Y-%m-%d"), line))
        for note in sorted((self.vault / "Daily").glob("????-??-??.md"), reverse=True)[:30]:
            try:
                lines = note.read_text(encoding="utf-8").splitlines()[-500:]
            except OSError:
                continue
            for line in lines:
                if not line.startswith("- "):
                    continue
                if requested_day is not None:
                    try:
                        timestamp = datetime.fromisoformat(note.stem + "T" + line[2:10]).replace(tzinfo=timezone.utc)
                    except ValueError:
                        continue
                    if timestamp.astimezone().date() != requested_day:
                        continue
                hits = len(terms & {word.casefold() for word in WORDS.findall(line)})
                if hits or broad:
                    candidates.append((hits, note.stem, line[:500]))
        candidates.sort(key=lambda item: (item[0], item[1], item[2][:10]), reverse=True)
        results = []
        skills = getattr(self, "skills", None)
        if skills is not None and (RECALL.search(question) or re.search(r"\bsteps\b", question, re.I)):
            for procedure in skills.context(question).get("procedures", [])[:3]:
                results.append({"source": "Jarvis Procedures.md", "observation": str(procedure)[:1800]})
        if PERSONAL.search(question):
            profile = self.vault / "Kunal Vaghani.md"
            source = self.profile_text()
            if source:
                results.append({"source": profile.name, "observation": source})
        results.extend({"date_utc": day, "observation": line} for _, day, line in candidates[:max(0, limit - len(results))])
        return results

    def profile_text(self):
        if not self.enabled:
            return ""
        try:
            return (self.vault / "Kunal Vaghani.md").read_text(encoding="utf-8")[:2000]
        except OSError:
            return ""
