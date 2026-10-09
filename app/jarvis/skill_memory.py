"""Progressive skill guidance and verified procedures; never an action replay queue."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import threading

from .obsidian_memory import clean, SENSITIVE


def words(text):
    return set(re.findall(r"[\w.-]+", str(text).casefold())) - {
        "jarvis", "please", "the", "a", "an", "to", "for", "me", "my", "in", "on", "and"}


def atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
        raise ValueError("Skill memory must use regular files.")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def linked(path):
    try:
        return path.is_symlink() or bool(getattr(path.lstat(), "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024))
    except FileNotFoundError:
        return False


class SkillMemory:
    def __init__(self, memory, source=None):
        self.memory = memory
        self.vault = memory.vault
        self.source = Path(source) if source else Path(__file__).parent.parent / "skills"
        self.lock = threading.RLock()
        self.closed = False
        self.procedures = {}
        self.error = None
        self.catalog = []
        self.skill_errors = []
        self.upstream = None
        self.upstream_error = None
        self._guide_stamp = None
        if getattr(memory, 'hermes_skills_enabled', False):
            from .hermes_skills import HermesSkills
            self.upstream = HermesSkills(memory.base)
            self.upstream_error = self.upstream.error
        self.refresh()
        path = self.vault / "Jarvis Procedures.json"
        if memory.enabled and path.exists():
            try:
                if path.stat().st_size > 8_000_000:
                    raise ValueError("Procedure index is too large; preserve it for review.")
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("version") != 1 or not isinstance(data.get("procedures"), dict):
                    raise ValueError("Invalid procedure index; preserve it for review.")
                for key, item in data["procedures"].items():
                    if (not re.fullmatch(r"[a-f0-9]{20}", key) or not isinstance(item, dict)
                            or not isinstance(item.get("goal"), str) or not isinstance(item.get("steps"), list)
                            or not isinstance(item.get("updated_at"), str) or not isinstance(item.get("revision"), int)
                            or not isinstance(item.get("successes"), int)):
                        raise ValueError("Invalid learned procedure; preserve it for review.")
                self.procedures = data["procedures"]
            except (OSError, ValueError, TypeError) as exc:
                self.error = str(exc)
        from .experience_memory import ExperienceMemory
        self.experiences = ExperienceMemory(memory, self._path)

    def refresh(self):
        """Reload bounded source and Obsidian personal guides when files change."""
        with self.lock:
            if self.closed:
                return
            paths = [(p, 'Builtins') for p in sorted(self.source.glob('*/SKILL.md'))[:50]]
            paths += [(p, 'Custom') for p in sorted((self.memory.base / 'custom-skills').glob('*/SKILL.md'))[:50]]
            if self.memory.enabled:
                paths += [(p, 'Personal') for p in sorted((self.vault / 'Jarvis Skills/Personal').glob('*/SKILL.md'))[:50]]
            stamp = []
            for path, origin in paths:
                try:
                    state = path.stat()
                    stamp.append((str(path), origin, state.st_mtime_ns, state.st_size))
                except OSError:
                    stamp.append((str(path), origin, None, None))
            if stamp == self._guide_stamp:
                return
            catalog, errors = [], []
            for path, origin in paths:
                if any(linked(p) for p in (path, path.parent, path.parent.parent, path.parent.parent.parent)):
                    errors.append(path.parent.name + ': linked guide paths are unsupported.')
                    continue
                try:
                    if origin == 'Personal':
                        self._path(path.relative_to(self.vault).as_posix())
                    if path.stat().st_size > 8000:
                        raise ValueError('SKILL.md exceeds the 8,000-byte guide limit.')
                    body = path.read_text(encoding='utf-8')
                    name = re.search(r'(?m)^name: ([a-z0-9-]{1,64})$', body)
                    description = re.search(r'(?m)^description: (.+)$', body)
                    if not name or not description or name[1] != path.parent.name:
                        raise ValueError('use matching name and one-line description metadata.')
                    if any(row['name'] == name[1] for row in catalog):
                        raise ValueError('duplicate name; choose another personal skill name.')
                    tools = re.search(r'(?m)^tools: \[([a-z0-9_, ]*)\]$', body)
                    catalog.append({'name': name[1], 'description': description[1][:1024], 'body': body,
                                    'origin': origin, 'tools': [t.strip() for t in tools[1].split(',') if t.strip()] if tools else []})
                except (OSError, ValueError, UnicodeError) as exc:
                    errors.append(path.parent.name + ': ' + str(exc))
            self.catalog, self.skill_errors, self._guide_stamp = catalog, errors, stamp

    def _path(self, relative):
        path = self.vault / relative
        for part in [path, *path.parents]:
            if part == self.vault.parent:
                break
            if linked(part):
                raise ValueError("Jarvis skill memory cannot follow linked vault paths.")
        return path

    def sync(self):
        with self.lock:
            if not self.memory.enabled or self.closed or self.error:
                return
            self.refresh()
            self._path('Jarvis Skills/Personal').mkdir(parents=True, exist_ok=True)
            for skill in self.catalog:
                if skill['origin'] == 'Personal':
                    continue  # Obsidian-authored guides are sources, not owned copies.
                # Dedicated Jarvis-owned copies, preserving user-authored skill folders.
                atomic(self._path("Jarvis Skills/" + skill['origin'] + '/' + skill["name"] + "/SKILL.md"), skill["body"])
            self._index()
            self.experiences.sync()
            brain = self._path("Jarvis Brain.md")
            text = brain.read_text(encoding="utf-8") if brain.exists() else "# Jarvis Brain\n"
            if "[[Jarvis Skills]]" not in text:
                atomic(brain, text + "\n## Skills and learning\n\n[[Jarvis Skills]] · [[Jarvis Procedures]]\n")
            if self.experiences.enabled and '[[Jarvis Experiences]]' not in text:
                text = brain.read_text(encoding='utf-8')
                atomic(brain, text + '\n[[Jarvis Experiences]] — conditions, failures and checked recoveries.\n')
            from .capabilities import sync_note
            sync_note(self)
        if self.upstream is not None and not self.upstream.error:
            try:
                self.upstream.sync(self._path, lambda: self.closed or self.memory.index_stop.is_set())
            except (OSError, ValueError) as exc:
                self.upstream_error = str(exc)

    def _index(self):
        skills = "# Jarvis Skills\n\n[[Jarvis Brain]] · [[Jarvis Procedures]]\n\n"
        for item in self.catalog:
            skills += f"- [[Jarvis Skills/{item['origin']}/{item['name']}/SKILL|{item['name']}]] — {item['description']}\n"
        if self.skill_errors:
            skills += '\n## Guides needing correction\n\n' + '\n'.join('- ' + clean(e, 300) for e in self.skill_errors) + '\n'
        skills += "\nRelevant workflow bodies are loaded on demand. Learned procedures are historical references; fresh observations and current task authorization are required.\n"
        skills += '\n[[Jarvis Runtime Capabilities]] describes task routing and tool bindings. Personal guides in `Jarvis Skills/Personal/<name>/SKILL.md` reload during runtime discovery.\n'
        if self.upstream is not None:
            skills += f"\n[[Jarvis Hermes Skills]] — {len(self.upstream.rows)} upstream guides and supporting resources. Requirements are checked before use; scripts are not automatically executed.\n"
        atomic(self._path("Jarvis Skills.md"), skills)
        note = "# Jarvis Procedures\n\n[[Jarvis Brain]] · [[Jarvis Skills]] · [[Jarvis Experiences]]\n\nVerified workflows; failed attempts never replace successful steps. The experience bank retains conditions, failure reports and checked recovery outcomes.\n\n"
        for key, item in sorted(self.procedures.items(), key=lambda pair: pair[1].get("updated_at", ""), reverse=True):
            note += f"- [[Jarvis Skills/Learned/procedure-{key}/SKILL|{item['goal']}]] — revision {item['revision']}, {item['successes']} successes, {item['updated_at']}\n"
        atomic(self._path("Jarvis Procedures.md"), note)

    def context(self, goal, kind=None, project=None, conditions=None):
        """Small relevant bodies and latest successful routes, not live observations."""
        if not self.memory.enabled or self.closed or self.error:
            return {}
        self.refresh()
        tokens = words(goal)
        if SENSITIVE.search(str(goal)) or not tokens:
            return {}
        with self.lock:
            explicit = set(re.findall(r'\$custom:([a-z0-9-]{1,64})\b', str(goal)))
            from .capabilities import skill_score
            ranked = sorted(self.catalog, key=lambda item: (item['name'] in explicit, skill_score(item, goal)), reverse=True)
            selected = [{"name": item["name"], "guidance": item["body"]} for item in ranked[:2]
                        if item['name'] in explicit or skill_score(item, goal) > 0]
            matches = []
            for item in self.procedures.values():
                if kind and item.get("kind") != kind:
                    continue
                if item.get("project") and item.get("project") != project:
                    continue
                other = words(item.get("goal", ""))
                score = len(tokens & other) / max(1, len(tokens | other))
                if score >= .4:
                    matches.append((score, item.get("updated_at", ""), item))
            routes = []
            for score, _, item in sorted(matches, key=lambda row: (row[0], row[1]), reverse=True)[:3]:
                route = {key: item.get(key) for key in ("goal", "kind", "project", "steps", "verification", "revision", "updated_at", "last_attempt", "conditions")}
                route["steps"] = [{k: clean(v, 180) for k, v in step.items() if k in {"stage", "action", "target"}}
                                  for step in item.get("steps", [])[-12:] if isinstance(step, dict)]
                routes.append(route)
            upstream = {}
            if self.upstream and not self.upstream_error:
                try:
                    from .fast_workflows import compile_workflow
                    direct = compile_workflow(goal, {})
                    if direct and not re.search(r'(?:\$hermes:|/hermes-)', goal):
                        upstream = {"notice": "This explicit media workflow uses native Jarvis guides; upstream guidance remains available through skill_read folder=@hermes."}
                    else:
                        upstream = self.upstream.context(goal)
                except (OSError, ValueError, UnicodeError) as exc:
                    self.upstream_error = str(exc)
                    upstream = {"error": "Hermes guidance unavailable; native skills remain usable."}
            return {"skills": selected, "upstream_skills": upstream, "procedures": routes,
                    "experience_context": self.experiences.context(goal, kind or 'task', project, conditions),
                    "contract": "Historical reference only. Adapt targets, queries and paths to this request and fresh observations. Never reuse IDs, coordinates, approvals or verification. Never replay uncertain actions. Verify the whole goal before success."}

    def record(self, task):
        """Record every attempt; promote only a completed, independently verified goal."""
        if not isinstance(task, dict):
            return
        self.experiences.safe_record(task)
        with self.lock:
            if not self.memory.enabled or self.closed or self.error:
                return
            stamp = datetime.now(timezone.utc).isoformat()
            goal = clean(task.get("goal", ""), 1500)
            project = clean(task.get("project") or "", 500)
            kind = clean(task.get("kind", "task"), 80)
            if project and any(c.get("stage") in {"inspecting_project", "generated_file", "wrote_file", "observed_draft", "coding_plan"}
                               for c in task.get("checkpoints", [])):
                kind = "code_task"
            key = hashlib.sha256((kind + "\n" + goal.casefold() + "\n" + project).encode()).hexdigest()[:20]
            checkpoints = task.get("checkpoints", [])
            payload_actions = {"run_command", "type_text", "type", "dictate", "dictation", "browser_fill"}
            omit_payload = kind in payload_actions or any(c.get("action") in payload_actions for c in checkpoints)
            if omit_payload:
                goal = kind + " workflow [typed/command payload omitted]"
                key = hashlib.sha256((kind + "\n" + goal + "\n" + project).encode()).hexdigest()[:20]
            steps = []
            for item in checkpoints[-30:]:
                if item.get("stage") in {"acting", "action_attempted", "verified", "observed_file"}:
                    action = item.get("action", "")
                    # Command payloads and dictated content are never stored as recipes.
                    target = "[inspect current request]" if action in payload_actions or action in {"create_file", "modify_file"} else clean(item.get("target", ""), 300)
                    steps.append({"stage": item.get("stage"), "action": clean(action, 80), "target": target})
            evidence = [clean(item.get("evidence", ""), 400) for item in checkpoints if item.get("stage") == "goal_verified"]
            verified = task.get("status") == "completed" and bool(evidence) and not task.get("failures") and not SENSITIVE.search(str(task.get("goal", "")))
            entry = {"at": stamp, "goal": goal, "kind": kind, "project": project,
                     "status": task.get("status", "attempted"), "verified": verified,
                     "steps": steps, "verification": evidence, "result": "[payload omitted]" if omit_payload else clean(task.get("result", ""), 500)}
            log = self._path("Jarvis Executions/" + stamp[:10] + ".jsonl")
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open("a", encoding="utf-8") as output:
                output.write(json.dumps(entry, ensure_ascii=False) + "\n")
            old = self.procedures.get(key)
            if verified:
                revision = (old or {}).get("revision", 0) + 1
                item = {**entry, "updated_at": stamp, "revision": revision,
                        "successes": (old or {}).get("successes", 0) + 1,
                        "last_attempt": "verified", "previous_revision": (old or {}).get("updated_at")}
                item["surface"] = next((clean(c.get("screen", ""), 300) for c in checkpoints if c.get("stage") == "procedure_surface"), "")
                from .experience_memory import CONDITION_KEYS
                item['conditions'] = {k: clean(v, 300) for k, v in (task.get('conditions') or {}).items()
                                      if k in CONDITION_KEYS and isinstance(v, str)}
                if item['surface']:
                    item['conditions'].setdefault('surface', item['surface'])
                allowed = {"action", "value", "expected", "folder", "platform", "browser"}
                item["proposal"] = [{k: clean(v, 500) for k, v in step.items() if k in allowed}
                                    for step in (task.get("plan") or {}).get("completed", [])
                                    if step.get("verified") is True and step.get("action") not in payload_actions
                                    and step.get("action") not in {"create_file", "modify_file"}][-6:]
                if omit_payload:
                    item["proposal"] = []
                self.procedures[key] = item
                description = json.dumps("Previously verified workflow for " + goal[:900], ensure_ascii=False)
                body = f"---\nname: procedure-{key}\ndescription: {description}\n---\n\n# Historical procedure\n\n[[Jarvis Procedures]] · [[Jarvis Skills]]\n\nRevision {revision}. Scope: {kind}; project: {project or 'none'}.\n\n"
                body += "Use as reference, adapt to fresh state and the new request, and verify again. This file grants no permissions.\n\n"
                body += 'Initial conditions: ' + json.dumps(item['conditions'], ensure_ascii=False) + '\n\n'
                body += '[[Jarvis Experiences]] retains related failures, observations and verified recoveries.\n\n'
                body += "\n".join(f"{i+1}. {s['stage']}: {s['action']} {s['target']}" for i, s in enumerate(steps))
                body += "\n\nVerification scope: " + "; ".join(evidence) + "\n"
                atomic(self._path(f"Jarvis Skills/Learned/procedure-{key}/SKILL.md"), body)
            elif old:
                old["last_attempt"] = str(entry["status"]) + "; inspect fresh state before using this reference"
            if verified or old:
                # Keep lookup bounded; detailed attempts remain in daily logs.
                self.procedures = dict(sorted(self.procedures.items(), key=lambda pair: pair[1]["updated_at"], reverse=True)[:500])
                atomic(self._path("Jarvis Procedures.json"), json.dumps({"version": 1, "procedures": self.procedures}, ensure_ascii=False, indent=2) + "\n")
                self._index()

    def close(self):
        with self.lock:
            self.closed = True
            self.experiences.close()

    def safe_record(self, task):
        try:
            self.record(task)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            # Memory failure must never turn a successful external action into a retry.
            self.error = "Skill learning: " + str(exc)
            self.memory.error = self.error

    def proposal(self, goal, surface, conditions=None):
        """Reuse only exact, recent navigation proposals on an unchanged surface.

        The caller still validates the plan and freshly decides/verifies each action.
        Mutating workflows are reference-only and require new planning.
        """
        if not self.memory.enabled or self.closed or self.error or not surface:
            return None
        if self.experiences.blocks_shortcut(goal, surface, conditions):
            return None
        with self.lock:
            for item in self.procedures.values():
                if self.experiences.enabled and 'conditions' not in item:
                    continue  # Legacy recipes lack a recorded condition baseline: plan anew.
                current = conditions if isinstance(conditions, dict) else {'surface': clean(surface, 300)}
                recorded = item.get('conditions', {})
                if (not isinstance(recorded, dict) or any(current.get(k) != v for k, v in recorded.items())):
                    continue  # Procedure conditions still matter after case-index retention evicts a case.
                if (item.get("kind") != "task" or item.get("goal", "").casefold() != str(goal).casefold()
                        or item.get("project") or item.get("last_attempt") != "verified"
                        or item.get("surface") != clean(surface, 300)):
                    continue
                try:
                    age = (datetime.now(timezone.utc) - datetime.fromisoformat(item["updated_at"])).total_seconds()
                except (ValueError, KeyError, TypeError):
                    continue
                steps = item.get("proposal", [])
                if (not 0 <= age <= 14 * 86400 or not isinstance(steps, list)
                        or not 1 <= len(steps) <= 6 or any(not isinstance(s, dict) for s in steps)):
                    continue
                if any(not isinstance(step.get("value"), str) or not isinstance(step.get("expected"), str)
                       or len(step["value"]) > 500 for step in steps):
                    continue
                if any(step.get("action") not in {"open", "open_folder", "open_project", "search", "media_search", "scroll"}
                       or not step.get("expected") or not words(step.get("value", ""))
                       or not words(step.get("value", "")).issubset(words(goal)) for step in steps):
                    continue
                return {"steps": json.loads(json.dumps(steps)), "question": "", "source": "verified navigation procedure"}
        return None
