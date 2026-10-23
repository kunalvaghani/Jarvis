"""Project Intelligence & Requirement Awareness Engine (PIRAE).

Conversational project collaboration on top of existing Jarvis services:

- requirements and a versioned specification persist in ProjectStore (project_model.py);
- every planned unit of work is an ordinary task in the existing durable TaskIngress/scheduler,
  attached to one workflow group per project, with dependencies, locks, approvals, overnight mode
  and recovery unchanged;
- implementation uses the existing coder (`code_task` with the project workspace) or the existing
  planner (`In folder ..., ...`); a small deterministic `project_step` creates the isolated workspace
  (new files only) and runs acceptance checks;
- the awareness engine receives conflicts and gaps as observations and decides whether to interrupt.

Nothing here approves tools, edits reference projects, overwrites existing folders or replays an
uncertain effect. A requirement is "verified" only from recorded evidence, never because a tool ran.
"""
import hashlib
import json
import os
import re
import threading
import time
from pathlib import Path

from .commands import Command
from .project_model import ProjectStore, slug
from .project_requirements import (QUESTIONS, classify, clean, conflicts, plan_questions, polarity, project_type,
                                   prohibited_topics, related, requirement_text, topics, words)

SKIP_DIRS = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', 'build', 'dist', '.jarvis-runtime', 'target', '.idea', '.vs'}
LANGUAGES = {'.py': 'Python', '.cs': 'C#', '.cpp': 'C++', '.c': 'C', '.js': 'JavaScript', '.ts': 'TypeScript', '.tsx': 'TypeScript',
             '.java': 'Java', '.go': 'Go', '.rs': 'Rust', '.html': 'HTML', '.css': 'CSS', '.blend': 'Blender', '.uproject': 'Unreal',
             '.md': 'Markdown', '.ipynb': 'Jupyter'}
NETWORK = re.compile(r'\b(?:import\s+(?:requests|httpx|aiohttp|boto3|urllib\.request|socket|websocket\w*|openai|anthropic|firebase\w*|azure\w*|google\.cloud)'
                     r'|from\s+(?:requests|httpx|aiohttp|boto3|openai|anthropic|azure|google\.cloud)\b|fetch\(|axios|https?://(?!localhost|127\.0\.0\.1))', re.I)
TERMINAL = {'COMPLETED', 'PARTIAL', 'FAILED', 'CANCELLED'}
ROUTINE_TECH = {'Python': ['Python with Tkinter', 'Python with PySide6', 'C# with WPF'],
                None: ['Python with Tkinter', 'C# with WPF', 'Electron with TypeScript']}


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def snapshot(root, limit=2000, max_bytes=20 << 20):
    """Read-only inventory: relative path -> size and hash. Nothing is written into the folder."""
    files, languages, truncated = {}, {}, False
    for folder, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]
        for name in names:
            if len(files) >= limit:
                truncated = True
                break
            path = Path(folder) / name
            try:
                size = path.stat().st_size
                files[path.relative_to(root).as_posix()] = {'size': size, 'sha256': sha256(path) if size <= max_bytes else None}
            except OSError:
                continue
            language = LANGUAGES.get(path.suffix.casefold())
            if language and language != 'Markdown':
                languages[language] = languages.get(language, 0) + 1
    return files, languages, truncated


class ProjectIntelligence:
    def __init__(self, actions, options=None, clock=time.time, store_path=None):
        self.actions, self.clock = actions, clock
        options = {} if options is None else options
        if not isinstance(options, dict) or type(options.get('enabled', False)) is not bool:
            raise ValueError('project_intelligence options must be an object with a boolean enabled flag')
        self.options = options
        self.enabled = options.get('enabled', False)
        self.ask_threshold = float(options.get('ask_threshold', .4))
        self.default_threshold = float(options.get('default_threshold', .2))
        self.max_attempts = int(options.get('max_repair_attempts', 2))
        if not 0 < self.default_threshold < self.ask_threshold <= 1 or not 0 <= self.max_attempts <= 5:
            raise ValueError('Invalid project_intelligence thresholds or max_repair_attempts')
        workspace = options.get('default_workspace')
        if workspace is not None and not isinstance(workspace, str):
            raise ValueError('project_intelligence.default_workspace must be a folder path or null')
        self.default_workspace = Path(workspace) if workspace else None
        self.lock = threading.RLock()
        self.decisions = {}
        self.last_reconcile = 0.
        self.store = None
        if self.enabled:
            base = Path(actions.base)
            self.store = ProjectStore(Path(store_path or base / '.jarvis-runtime' / 'projects.sqlite3'), clock)
            self.state_dir = base / '.jarvis-runtime' / 'projects'
            self.decisions = self.store.setting('decisions', default={}) or {}

    # --- routing --------------------------------------------------------------------------------------------------
    def claims(self, command):
        """Cheap check used by Actions: is this utterance about a project?"""
        if not self.enabled or command.kind not in {'task', 'ask', 'project'} or command.extra not in {'', 'unparsed'}:
            return False
        if command.kind == 'project':
            return True
        project = self.store.active()
        return classify(command.value, has_project=project is not None, pending=self._open_question(project))[0] != 'none'

    def handle(self, command):
        """Answer one utterance from project state. Returns the reply; never raises into the conversation."""
        if not self.enabled:
            return 'Project intelligence is off (config project_intelligence.enabled).'
        with self.lock:
            try:
                self.reconcile(force=True)
                return self._handle(command.value)
            except ValueError as exc:
                return str(exc)

    def _handle(self, text):
        project = self.store.active()
        question = self._open_question(project)
        intent, details = classify(text, has_project=project is not None, pending=question)
        if intent == 'none':
            if re.match(r"^(?:do not|don'?t|never|stop)\b", clean(text), re.I):
                return 'No active project, so no constraint was recorded and nothing was changed.'
            return 'There is no active project for that. Say "create a new project" to start one.'
        if intent == 'new_project':
            return self._new_project(text, details)
        if question and question.get('conflict') and re.search(r'\bkeep R\d+\b', text, re.I):
            return self._on_answer(project, text, details)
        if question and intent in {'answer', 'location', 'reference', 'constraint', 'add_requirement', 'modify_requirement'} \
                and question['slots'] and (intent == 'answer' or set(question['slots']) & {'objective', 'location', 'references'}):
            return self._answer(project, question, text)
        handler = getattr(self, '_on_' + intent)
        return handler(project, text, details)

    # --- discovery ----------------------------------------------------------------------------------------------
    def _new_project(self, text, details):
        subject, objective = details['subject'], details.get('objective') or ''
        split = re.match(r'(.+?)\s+(?:that|which|to|for|called)\s+(.+)', subject, re.I)
        if split:
            subject, objective = split[1], (split[2] + ' ' + objective).strip()
        subject = re.sub(r'\b(?:project|one)\b', '', subject, flags=re.I).strip() or 'project'
        if not objective and len(words(subject)) >= 3:
            objective = 'Create ' + ('an ' if subject[0] in 'aeiou' else 'a ') + subject  # The request already describes it.
        kind = project_type(subject + ' ' + objective)
        project = self.store.create(subject.title() if subject != 'project' else 'New project', objective, kind, subject)
        if subject != 'project':
            self.store.add_requirement(project['id'], 'Deliver ' + ('an ' if subject[0] in 'aeiou' else 'a ') + subject,
                                       kind='deliverable', category='explicit', evidence=text)
        if objective:
            self._set_objective(project['id'], objective, text)
        self._remember(project['id'], 'created')
        return self._advance(self.store.get(project['id']))

    def _set_objective(self, identity, objective, evidence):
        objective = requirement_text(objective)
        project = self.store.get(identity)
        project.update(objective=objective, description=objective, type=project['type'] or project_type(objective) or 'software')
        if project['name'] in {'New project'} or len(project['name']) < 4 or project['name'].casefold() == project['subject'].casefold():
            first = re.split(r',?\s+(?:and|then|plus|but)\s+|[;.]', objective)[0]
            first = re.sub(r'^(?:create|build|make|develop|write|design)\s+(?:an?\s+)?', '', first, flags=re.I)
            project['name'] = ' '.join(w if w.isupper() else w.title() for w in re.findall(r"[A-Za-z0-9][\w'-]*", first)
                                       if w.casefold() not in {'a', 'an', 'the', 'my', 'our', 'to', 'of', 'for'})[:60].strip() or project['name']
            project['slug'] = slug(project['name'])
        self.store.save(project)
        self.store.add_requirement(identity, objective, kind='objective', category='explicit', evidence=evidence)
        # The objective's own clauses become inferred functional requirements; the user can correct them.
        clauses = [c.strip() for c in re.split(r',?\s+(?:and|then|plus)\s+|;\s*', objective) if len(words(c)) >= 2]
        for clause in clauses if len(clauses) > 1 else []:
            self.store.add_requirement(identity, requirement_text(clause), kind='functional', category='inferred',
                                       source='objective clause', evidence=objective)
        if project['type'] == 'software':
            for text in ('Automated tests cover the core behaviour', 'A README explains how to install and run it'):
                self.store.add_requirement(identity, text, kind='deliverable', category='inferred', source='software default',
                                           evidence='Standard deliverable for software projects; remove it if not wanted')

    def _slots(self, project):
        requirements = self.store.requirements(project['id'])
        has = lambda kind: any(r['kind'] == kind for r in requirements)
        slots = {'objective': 0. if has('objective') else 1.,
                 'location': 0. if project['workspace'] else .3 if self.default_workspace else .9,
                 'references': 0. if project['references'] or project.get('references_declined') else .6}
        if project['type'] == 'software':
            stated = any(re.search(r'\b(?:python|c#|c\+\+|rust|go|java|typescript|javascript|electron|wpf|tkinter|qt|pyside|react|flutter)\b',
                                   r['text'], re.I) for r in requirements)
            inferred = any(ref.get('languages') for ref in project['references'])
            decided = any(d.get('slot') == 'technology' for d in project['decisions'])
            slots['technology'] = 0. if stated or decided else .3 if inferred else .6
        return slots

    def _advance(self, project):
        """Ask only what is worth asking; otherwise default, plan and start the safe work."""
        from .engineering_judgment import engine_for
        engineering = engine_for(self.actions)
        if engineering:
            project['engineering'] = engineering.project_contract(project, self.store.requirements(project['id'], include_inactive=True))
        plan = plan_questions(self._slots(project), ask_threshold=self.ask_threshold, default_threshold=self.default_threshold)
        project['clarification'] = plan
        self.store.save(project)
        asks = [d for d in plan if d['action'] == 'ask']
        if asks and asks[0]['slot'] == 'objective':
            return self._ask(project, ['objective'])
        if asks:
            slots = [asks[0]['slot']]
            # Cheap related questions ride along with a question that has to be asked anyway.
            slots += [d['slot'] for d in plan if d['slot'] != slots[0] and d['action'] == 'provisional' and d['slot'] in {'references', 'location'}]
            return self._ask(project, slots[:2])
        if not project['workspace'] and self.default_workspace:
            self._set_location(project, str(self.default_workspace), 'configured default workspace', default=True)
            project = self.store.get(project['id'])
        reply = self._start(project)
        technology = next((d for d in plan if d['slot'] == 'technology'), None)
        if technology and technology['uncertainty'] > 0:
            reply += ' ' + self._technology_choice(self.store.get(project['id']), routine=technology['action'] != 'default')
        return reply

    def _open_question(self, project):
        return next((q for q in (project or {}).get('questions', []) if q['status'] == 'open'), None) if project else None

    def _ask(self, project, slots):
        open_question = self._open_question(project)
        if open_question and open_question['slots'] == slots:
            return open_question['text']
        text = ' '.join(QUESTIONS[s].format(subject=project['subject'] if project['subject'] != 'project' else 'project') for s in slots)
        project['questions'] = [q for q in project['questions'] if q['status'] != 'open'] + [
            {'id': len(project['questions']) + 1, 'slots': slots, 'text': text, 'asked_at': self.clock(), 'status': 'open',
             'scores': [d for d in project.get('clarification', []) if d['slot'] in slots]}]
        project['status'] = 'waiting_for_answer' if 'objective' in slots or 'location' in slots else project['status']
        self.store.save(project)
        return text

    def _answer(self, project, question, text):
        slots = list(question['slots'])
        handled = []
        for clause in self._clauses(text):
            intent, details = classify(clause, has_project=True)
            if intent == 'location' or (intent in {'none', 'answer'} and 'location' in slots and 'location' not in handled
                                         and re.search(r'[\\/]|\bfolder\b|\bdrive\b|^[a-z]:', clause, re.I) and 'objective' not in slots):
                self._set_location(self.store.get(project['id']), details.get('target') or clause, clause)
                handled.append('location')
            elif intent == 'reference':
                self._add_reference(self.store.get(project['id']), details.get('target') or clause, text)
                handled.append('references')
            elif intent == 'constraint':
                self._constraint(self.store.get(project['id']), clause, in_answer=True)
            elif 'objective' in slots and 'objective' not in handled:
                self._set_objective(project['id'], clause, text)
                handled.append('objective')
            elif re.fullmatch(r"(?:no|none|nope|no reference|no references|start fresh|from scratch)", clean(clause), re.I) and 'references' in slots:
                project = self.store.get(project['id'])
                project['references_declined'] = True
                self.store.save(project)
                handled.append('references')
            else:
                self._on_add_requirement(self.store.get(project['id']), clause, {}, quiet=True)
        project = self.store.get(project['id'])
        for row in project['questions']:
            if row['id'] == question['id']:
                row.update(status='answered', answered_at=self.clock(), answer=text[:500], resolved=handled)
        self.store.save(project)
        notes = []
        if 'location' in slots and not project['workspace']:
            return self._ask(project, ['location'])
        if project['workspace']:
            notes.append(f"Saving it in {project['workspace']}" + (' (new folder name chosen because the original exists)'
                                                                   if project.get('workspace_renamed') else '') + '.')
        for ref in project['references']:
            if ref['path'] in text or ref.get('registered_at', 0) >= question['asked_at']:
                notes.append(f"Using {ref['name']} as a read-only reference ({ref['files']} files"
                             + (', ' + ', '.join(list(ref['languages'])[:2]) if ref['languages'] else '') + ').')
        return ' '.join(notes + [self._advance(project)]).strip()

    @staticmethod
    def _clauses(text):
        parts = re.split(r'(?<=[.!?;])\s+|,\s*(?=(?:but|and)\s+(?:do not|don\'?t|never|use|save|keep|make)\b)', str(text).strip())
        return [re.sub(r'^(?:but|and)\s+', '', p, flags=re.I).strip() for p in parts if p and p.strip(' .,')]

    def _roots(self):
        config = getattr(self.actions, 'config', {}) or {}
        roots = [Path(p) for p in config.get('project_roots', []) if isinstance(p, str)]
        roots += [Path(p) for p in self.options.get('search_roots', []) if isinstance(p, str)]
        if self.options.get('search_home', True):
            home = Path.home()
            roots += [home, home / 'Documents']  # "my Projects folder" often lives here.
        return [r for r in dict.fromkeys(roots) if r.is_dir()]

    def _set_location(self, project, phrase, evidence, default=False):
        phrase = clean(phrase)
        path = Path(phrase.strip('"\''))
        if not path.is_absolute():
            name = re.sub(r'^(?:my|the|in|into|under)\s+', '', phrase, flags=re.I)
            name = re.sub(r'\s+(?:folder|directory|dir)$', '', name, flags=re.I).strip()
            candidates = []
            for root in self._roots():
                if root.name.casefold() == name.casefold():
                    candidates.append(root)
                try:
                    candidates += [c for c in root.iterdir() if c.is_dir() and c.name.casefold() == name.casefold()]
                except OSError:
                    continue
            candidates = list(dict.fromkeys(c.resolve() for c in candidates))
            if len(candidates) != 1:
                raise ValueError(f"I couldn't find exactly one folder named '{name}' (found {len(candidates)}). "
                                 'Tell me the full path and I will use it.' if len(candidates) != 1 else '')
            path = candidates[0]
        if not path.is_dir():
            raise ValueError(f'{path} is not an existing folder. Give me an existing folder; I only create the project folder inside it.')
        for ref in project['references']:
            if Path(ref['path']) == path or Path(ref['path']) in path.parents:
                raise ValueError('That location is inside a read-only reference project. Choose a different folder.')
        target, renamed = path / project['slug'], False
        index = 2
        # Never overwrite: an existing non-empty folder gets a new name.
        while target.exists() and (not target.is_dir() or any(target.iterdir())):
            target, renamed = path / f"{project['slug']}-{index}", True
            index += 1
        project.update(workspace=str(target), workspace_state='planned', workspace_parent=str(path), workspace_renamed=renamed)
        self.store.save(project)
        self.store.add_requirement(project['id'], f'Store the project in {target}', kind='location',
                                   category='assumption' if default else 'explicit', evidence=evidence)
        if renamed:
            self._decide(project['id'], 'workspace', f'Used {target.name} because {project["slug"]} already exists; nothing was overwritten',
                         'confirmed safe default')

    def _add_reference(self, project, phrase, evidence):
        phrase = clean(phrase)
        path = Path(phrase.strip('"\''))
        if not path.is_absolute() or not path.is_dir():
            wanted = [w for w in words(phrase) if w not in {'old', 'previous', 'earlier', 'existing', 'original', 'code', 'reference'}]
            from .projects import project_paths
            roots = self._roots() + ([Path(project['workspace_parent'])] if project.get('workspace_parent') else [])
            folders = {p.resolve() for p in project_paths(roots)}
            for root in roots:
                try:
                    folders |= {c.resolve() for c in root.iterdir() if c.is_dir() and not c.name.startswith('.')}
                except OSError:
                    continue
            def score(folder):
                name = re.findall(r'[a-z0-9]+', re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', folder.name).casefold())
                return sum(1 for w in wanted if any(n.startswith(w[:5]) or w.startswith(n[:5]) for n in name if len(n) >= 3))
            scored = sorted(((score(f), f) for f in folders if project.get('workspace') is None or f != Path(project['workspace'])),
                            key=lambda pair: -pair[0])
            best = [f for s, f in scored if s and s == scored[0][0]] if scored else []
            if len(best) != 1:
                names = ', '.join(f.name for f in best[:5])
                raise ValueError(f"Which project should I use as reference? I found {len(best)} matches" + (f': {names}' if names else '')
                                 + '. Say its folder name or full path.')
            path = best[0]
        files, languages, truncated = snapshot(path)
        readme = next((path / n for n in ('README.md', 'readme.md', 'README.txt') if (path / n).is_file()), None)
        reference = {'name': path.name, 'path': str(path), 'editable': False, 'files': len(files), 'truncated': truncated,
                     'languages': dict(sorted(languages.items(), key=lambda kv: -kv[1])[:5]),
                     'readme': readme.read_text(encoding='utf-8', errors='replace')[:600] if readme else '',
                     'components': sorted({Path(f).stem for f in files if Path(f).suffix.casefold() in LANGUAGES and Path(f).suffix.casefold() != '.md'})[:60],
                     'registered_at': self.clock()}
        self.state_dir.mkdir(parents=True, exist_ok=True)
        baseline = self.state_dir / f"{project['id']}-reference-{len(project['references']) + 1}.json"
        baseline.write_text(json.dumps(files), encoding='utf-8')
        reference['baseline'] = str(baseline)
        project = self.store.get(project['id'])
        project['references'] = [r for r in project['references'] if r['path'] != str(path)] + [reference]
        self.store.save(project)
        self.store.add_requirement(project['id'], f'Do not modify the reference project {path.name}', kind='constraint', category='explicit'
                                   if re.search(r"don'?t|do not|never|without (?:modifying|changing)", evidence, re.I) else 'inferred',
                                   polarity='prohibit', evidence=evidence + ' (references are read-only unless you grant permission)')
        if languages:
            top = next(iter(reference['languages']))
            self.store.add_requirement(project['id'], f'Prefer {top}, matching the reference project', kind='preference', category='inferred',
                                       source='reference project', evidence=f'{languages[top]} {top} files in {path.name}')
            self._decide(project['id'], 'technology', f'{top}, because the reference project {path.name} uses it ({languages[top]} files), '
                         'so its components can be adapted', 'inferred default (reversible)')

    def _constraint(self, project, clause, in_answer=False):
        low = clean(clause).casefold()
        if in_answer and re.fullmatch(r"(?:but )?(?:do not|don'?t|never) (?:modify|change|touch|edit) (?:it|that|them|the reference|the old one)", low):
            return  # The reference registration already recorded this as an explicit read-only constraint.
        return self._on_constraint(project, clause, {}, quiet=True)

    # --- decisions --------------------------------------------------------------------------------------------------
    def _decide(self, identity, slot, text, kind, automatic=False):
        project = self.store.get(identity)
        project['decisions'].append({'slot': slot, 'text': text[:300], 'kind': kind, 'automatic': automatic,
                                     'at': self.clock(), 'version': project['version']})
        self.store.save(project)
        self.store.event(identity, 'decision', {'slot': slot, 'text': text, 'kind': kind, 'automatic': automatic})

    def _technology_choice(self, project, routine=True):
        """A reversible routine choice before any implementation; silence picks the default after 20 s."""
        ingress = self._ingress() if routine else None
        languages = [lang for ref in project['references'] for lang in ref['languages']]
        options = list(dict.fromkeys(ROUTINE_TECH.get(languages[0] if languages else None, ROUTINE_TECH[None])))
        confidence = .9 if languages else .86
        reason = f"it matches the reference project ({languages[0]})" if languages else 'it needs no extra installation on this PC'
        if ingress is None:
            self._decide(project['id'], 'technology', f'{options[0]}, because {reason}', 'provisional default', automatic=True)
            self._plan(self.store.get(project['id']))
            return f'I will use {options[0]} because {reason} (a reversible default; say "use ... instead" to change it).'
        identity = ingress.decisions.create(None, f"Project {project['name']}: technology", options, 0, confidence,
                                            reversible=True, sensitive=False)
        self.decisions[identity] = {'project': project['id'], 'slot': 'technology', 'reason': reason}
        self.store.setting('decisions', self.decisions)
        self.actions.report('task_decision', {'id': identity, 'status': 'PENDING'})
        return (f'For the technology I recommend {options[0]} because {reason}. Choose in the Queue view, or I will use it '
                'after 20 seconds; architecture work waits for this choice while setup continues.')

    def observe_report(self, kind, message):
        if not self.enabled or kind != 'task_decision' or not isinstance(message, dict) or message.get('id') not in self.decisions:
            return
        ingress = self._ingress()
        decision = next((d for d in ingress.decisions.rows() if d['id'] == message['id']), None) if ingress else None
        if not decision or decision['status'] == 'PENDING':
            return
        with self.lock:
            meta = self.decisions.pop(message['id'])
            self.store.setting('decisions', self.decisions)
            if decision['status'] == 'SELECTED':
                choice = decision['options'][decision['choice']]
                why = meta['reason'] if decision['choice'] == decision['recommended'] else 'you chose it'
                self._decide(meta['project'], meta['slot'], f'{choice}, because {why}', 'automatic routine choice' if decision['automatic']
                             else 'user-confirmed', automatic=decision['automatic'])
                self.store.add_requirement(meta['project'], 'Use ' + choice, kind='preference',
                                           category='assumption' if decision['automatic'] else 'confirmed',
                                           source='routine decision', evidence=decision.get('justification', ''))
            else:
                self._decide(meta['project'], meta['slot'], 'Decision deferred: ' + decision.get('justification', ''), 'deferred')
            self._plan(self.store.get(meta['project']))

    # --- planning and execution through the existing scheduler ---------------------------------------------------
    def _ingress(self):
        ingress = getattr(self.actions, 'ingress', None)
        from .task_ingress import TaskIngress
        return ingress if isinstance(ingress, TaskIngress) else None

    def _start(self, project):
        project['status'] = 'active'
        self.store.save(project)
        submitted = self._plan(self.store.get(project['id']))
        project = self.store.get(project['id'])
        milestones = ', '.join(m['title'] for m in project['plan']['milestones'])
        if not any(d['slot'] == 'architecture' for d in project['decisions']):
            self._decide(project['id'], 'architecture', f'Milestones {milestones}; one task per requirement so a later change touches only '
                         'its own task; tests and acceptance checks run after the features they cover', 'planner default')
        if self._ingress() is None:
            return f"Plan ready ({milestones}), but the durable task queue is off, so nothing was started."
        return (f"Project {project['name']} registered with {len(self.store.requirements(project['id']))} requirements "
                f"(spec v{project['version']}). Plan: {milestones}. Queued {submitted} task(s) in dependency order; "
                'setup starts now and later steps wait for their prerequisites.')

    def _blueprint(self, project):
        """Plan proportional to the project: (key, title, milestone, requirements, depends, command-factory)."""
        requirements = self.store.requirements(project['id'])
        features = [r for r in requirements if r['kind'] in {'functional', 'preference'} and not r['text'].startswith('Use ')
                    and not r['text'].startswith('Prefer ')] or [r for r in requirements if r['kind'] == 'objective']
        software = project['type'] == 'software'
        technology = next((d['text'].split(',')[0] for d in reversed(project['decisions']) if d['slot'] == 'technology' and d['kind'] != 'deferred'), None)
        stated_tech = any(r['kind'] == 'preference' and re.search(r'\b(?:python|c#|c\+\+|rust|go|java|typescript|electron|wpf|tkinter|qt|pyside)\b', r['text'], re.I)
                          and r['category'] in {'explicit', 'confirmed'} for r in requirements)
        tech_ready = not software or technology or stated_tech or self._slots(project).get('technology', 0) == 0
        rows = [('workspace', 'Create the isolated workspace and specification', 'Setup', [r['id'] for r in requirements if r['kind'] == 'location'], [], True)]
        if software and len(features) > 1:
            rows.append(('architecture', 'Initial architecture and module skeleton', 'Architecture',
                         [r['id'] for r in requirements if (r['kind'] in {'objective', 'deliverable'} and 'concept:testing' not in topics(r['text']))
                          or (r['kind'] == 'preference' and r['text'].startswith(('Use ', 'Prefer ')))],
                         ['workspace'], tech_ready))
            base = ['architecture']
        else:
            base = ['workspace']
        for row in features:
            rows.append(('feature:' + row['id'], row['text'], 'Interface' if 'concept:interface' in topics(row['text']) else 'Features',
                         [row['id']], base, tech_ready))
        if software:
            rows.append(('tests', 'Automated tests for the current requirements', 'Verification',
                         [r['id'] for r in features] + [r['id'] for r in requirements if r['kind'] == 'deliverable' and 'concept:testing' in topics(r['text'])],
                         ['feature:' + r['id'] for r in features], tech_ready))
        rows.append(('verify', 'Acceptance checks against the current requirements', 'Verification', [r['id'] for r in requirements],
                     [k for k, *_ in rows if k != 'workspace'] or ['workspace'], True))
        return rows

    def _command(self, project, key, task):
        title, requirement_ids = task['title'], task['requirements']
        if task.get('repair_note'):
            title += '. ' + task['repair_note']
        spec = self._spec_text(project)
        if key in {'workspace', 'verify'}:
            return Command('project_step', json.dumps({'project': project['id'], 'op': key, 'version': project['version']}))
        relevant = [r for r in self.store.requirements(project['id']) if r['id'] in requirement_ids]
        focus = '; '.join(r['id'] + ': ' + r['text'] for r in relevant) or title
        instruction = (f"{title}. Focus: {focus}. Follow the authoritative project specification v{project['version']} "
                       f"(REQUIREMENTS.md in the workspace). Constraints: {spec['constraints'] or 'none'}. "
                       'Never modify reference projects. Report what you changed and how you verified it.')
        if project['type'] == 'software':
            return Command('code_task', instruction, project['workspace'])
        return Command('task', f"In folder {project['workspace']}, {instruction}")

    def _plan(self, project):
        """Submit every planned task whose prerequisites are satisfied in the plan; return how many were submitted."""
        if not project or not project.get('workspace') or project['status'] == 'paused':
            return 0
        ingress = self._ingress()
        rows = self._blueprint(project)
        tasks = project['plan']['tasks']
        extras = [(k, t['title'], t['milestone'], t['requirements'], t['depends'], True) for k, t in tasks.items()
                  if k.startswith(('conformance:', 'followup:'))]
        verify = rows.pop()
        rows += extras + [(verify[0], verify[1], verify[2], verify[3], verify[4] + [k for k, *_ in extras], verify[5])]
        for key in ('tests', 'verify'):
            task = tasks.get(key)
            if task and task['status'] == 'done' and task.get('spec_version', 0) < project['version'] and \
                    any(t['status'] == 'planned' or t.get('spec_version', 0) > task.get('spec_version', 0) for k, t in tasks.items() if k != key):
                task.update(status='planned', revision=task['revision'] + 1)  # Earlier evidence no longer covers this spec.
                if ingress and task.get('task_id'):
                    ingress.scheduler.graph.invalidate(task['task_id'], f"Specification changed to v{project['version']}")
        project['plan']['milestones'] = [{'title': m, 'tasks': [k for k, _, mm, *_ in rows if mm == m]}
                                         for m in dict.fromkeys(r[2] for r in rows)]
        live_keys = {r[0] for r in rows}
        for key, task in tasks.items():
            if key not in live_keys and task['status'] == 'planned':
                task['status'] = 'obsolete'
        submitted = 0
        if ingress is not None and not project.get('workflow'):
            project['workflow'] = ingress.scheduler.graph.create_workflow(project=project['name'], goal=project['objective'] or project['name'])
        for key, title, milestone, requirement_ids, depends, ready in rows:
            current = tasks.get(key)
            if current and current['status'] == 'submitted' and key in {'tests', 'verify'} and ingress is not None:
                self._retarget(project, key, current, [tasks[d]['task_id'] for d in depends if tasks.get(d, {}).get('task_id')])
            if current and current['status'] in {'submitted', 'done', 'blocked', 'obsolete'}:
                continue
            tasks[key] = current = {**(current or {}), 'title': title, 'milestone': milestone, 'requirements': requirement_ids,
                                    'depends': depends, 'status': 'planned', 'revision': (current or {}).get('revision', 0),
                                    'attempts': (current or {}).get('attempts', 0)}
            prerequisites = [tasks.get(d) for d in depends]
            if not ready or ingress is None or any(p is None or p['status'] not in {'submitted', 'done'} for p in prerequisites):
                continue
            identity = self._submit(project, key, current, [p['task_id'] for p in prerequisites])
            if identity:
                current.update(status='submitted', task_id=identity, spec_version=project['version'])
                submitted += 1
        self.store.save(project)
        return submitted

    def _retarget(self, project, key, task, dependencies):
        """An unstarted verification task waits for newly planned work and checks the current spec."""
        ingress = self._ingress()
        row = self._task_row(task)
        if not row or row['state'] not in {'QUEUED', 'READY', 'WAITING_DEPENDENCY'}:
            return
        if sorted(row['spec'].get('dependencies', [])) != sorted(dependencies):
            try:
                ingress.scheduler.control('dependencies', row['id'], dependencies)
                current = ingress.store.get(row['id'])
                ingress.store.transition(row['id'], current['state'], 'Project plan dependencies updated',
                                         spec={**current['spec'], 'dependencies': dependencies})
            except ValueError:
                return
        if task.get('spec_version') != project['version']:
            self._refresh_unstarted(project, key, task, row)

    def _submit(self, project, key, task, dependencies):
        ingress = self._ingress()
        priority = next((50 for row in self.store.requirements(project['id']) if row['kind'] == 'priority'
                         and topics(row['text'][len('Prioritise '):]) & topics(task['title']) and key not in {'workspace', 'verify'}), None)
        command = self._command(project, key, task)
        previous = getattr(ingress.local, 'identity', None)
        try:
            # On the ingress thread an identity means "route a follow-up"; a project task is a new admission.
            ingress.local.identity = None
            identity = ingress.submit(command, idempotency_key=f"project:{project['id']}:{key}:{task['revision']}",
                                      workflow=project['workflow'], dependencies=dependencies)
            if identity and priority:
                stored = ingress.store.setting('admission_overrides:' + identity) or {}
                ingress.store.setting('admission_overrides:' + identity, {**stored, 'priority': priority, 'explicit_priority': True})
            return identity
        finally:
            ingress.local.identity = previous

    def _task_row(self, task):
        ingress = self._ingress()
        return ingress.store.get(task['task_id']) if ingress and task.get('task_id') else None

    def reconcile(self, force=False):
        """Fold queue outcomes back into the plan; bounded repair attempts; submit newly unblocked work."""
        if not self.enabled or (not force and self.clock() - self.last_reconcile < 5):
            return
        self.last_reconcile = self.clock()
        with self.lock:
            for project in self.store.all():
                if project['status'] in {'discovering', 'waiting_for_answer'} or not project['plan']['tasks']:
                    continue
                changed = False
                for key, task in project['plan']['tasks'].items():
                    row = self._task_row(task) if task['status'] == 'submitted' else None
                    if not row or row['state'] not in TERMINAL:
                        continue
                    changed = True
                    if row['state'] == 'COMPLETED':
                        task['status'] = 'done'
                    elif row['state'] == 'CANCELLED' and task.get('superseded'):
                        task['status'] = 'planned'  # Replaced by a newer requirement version.
                    elif task['attempts'] < self.max_attempts and row['state'] in {'FAILED', 'PARTIAL'} and key not in {'workspace', 'verify'} \
                            and not row['checkpoint'].get('uncertain'):
                        # A new diagnostic attempt with fresh inspection; never a replay of an uncertain effect.
                        task.update(attempts=task['attempts'] + 1, revision=task['revision'] + 1, status='planned',
                                    repair_note='The previous attempt failed: ' + row['outcome'][:200]
                                    + '. Inspect the current files, find the cause and fix it before continuing')
                        self.store.event(project['id'], 'repair_attempt', {'task': key, 'attempt': task['attempts'], 'outcome': row['outcome'][:300]})
                    else:
                        task['status'] = 'blocked'
                        task['blocked_reason'] = f"{row['state']}: {row['outcome'][:200]}" + (' (uncertain effect: inspect before retrying)'
                                                                                             if row['checkpoint'].get('uncertain') else '')
                if changed:
                    self.store.save(project)
                    self._plan(self.store.get(project['id']))
                    self._evaluate(self.store.get(project['id']))

    def dispatch_guard(self, identity):
        """Called before a project task executes: refuse work superseded by a newer requirement version."""
        if not self.enabled or not identity:
            return
        ingress = self._ingress()
        row = ingress.store.get(identity) if ingress else None
        if not row or not str(row['idem']).startswith('project:'):
            return
        parts = row['idem'].split(':')
        project_id, key = parts[1], ':'.join(parts[2:-1])  # Keys such as feature:R3 contain colons.
        project = self.store.get(project_id)
        task = (project or {}).get('plan', {}).get('tasks', {}).get(key)
        if task is None or task.get('task_id') != identity or task.get('superseded') or project['status'] == 'paused':
            active = ingress.scheduler.active.get(identity)
            if active:
                active['item'][2].set()  # Cooperative cancellation: recorded as CANCELLED, not a failure.
            raise ValueError(f'Superseded by project specification v{project["version"] if project else "?"}; not executed')

    # --- live changes ---------------------------------------------------------------------------------------------
    def _impact(self, project, requirement_ids=(), topic_set=frozenset(), reason='', mode='update'):
        """Adjust only the affected tasks. mode: update (refresh instructions), stop (incompatible), remove."""
        from .engineering_judgment import engine_for
        engineering = engine_for(self.actions)
        if engineering:
            project['engineering'] = engineering.project_contract(project, self.store.requirements(project['id'], include_inactive=True))
            self.store.save(project)
        ingress = self._ingress()
        notes = {'updated': [], 'replaced': [], 'paused': [], 'cancelled': [], 'followups': []}
        tasks = project['plan']['tasks']
        for key, task in list(tasks.items()):
            if key in {'workspace'}:
                continue
            linked = set(task['requirements']) & set(requirement_ids)
            text_topics = topics(task['title'])
            touched = linked or (topic_set and (topic_set & text_topics))
            if not touched or task['status'] not in {'submitted', 'done'}:
                continue
            row = self._task_row(task)
            state = row['state'] if row else None
            if key in {'tests', 'verify'} and mode != 'remove':
                if state in TERMINAL:
                    task.update(status='planned', revision=task['revision'] + 1)  # Re-verify against the new spec.
                    if ingress:
                        ingress.scheduler.graph.invalidate(row['id'], reason)
                    notes['followups'].append(key)
                elif state is not None and state != 'RUNNING':
                    self._refresh_unstarted(project, key, task, row)
                    notes['updated'].append(key)
                continue
            if state is None or state in {'RECEIVED', 'CLASSIFYING'}:
                continue
            if state in {'QUEUED', 'READY', 'WAITING_DEPENDENCY', 'PAUSED', 'WAITING_USER'}:
                if mode == 'update':
                    self._refresh_unstarted(project, key, task, row)
                    notes['updated'].append(key)
                else:
                    ingress.scheduler.control('cancel', row['id'])
                    task.update(superseded=True, status='obsolete' if mode == 'remove' else 'planned', revision=task['revision'] + 1)
                    notes['cancelled'].append(key)
            elif state in {'RUNNING', 'VERIFYING'}:
                if mode == 'update':
                    notes['followups'].append(key)  # Compatible: let it finish, then apply the change.
                else:
                    ingress.scheduler.control('pause', row['id'])  # Safe checkpoint; completed effects preserved.
                    task.update(superseded=True, status='blocked', blocked_reason='Paused: ' + reason + ' (inspect in-flight changes)')
                    notes['paused'].append(key)
            elif state == 'COMPLETED':
                notes['followups'].append(key)
        for key in [k for k in notes['followups'] if k not in {'tests', 'verify'}]:
            original = tasks[key]
            follow = 'followup:' + key + ':v' + str(project['version'])
            tasks[follow] = {'title': ('Remove the implementation of ' if mode == 'remove' else 'Bring the existing work in line with spec v'
                                       + str(project['version']) + ': ') + reason, 'milestone': original['milestone'],
                             'requirements': original['requirements'] + list(requirement_ids), 'depends': [key], 'status': 'planned',
                             'revision': 0, 'attempts': 0}
        self.store.save(project)
        return notes

    def _refresh_unstarted(self, project, key, task, row):
        """Update an admitted, unstarted task in place: no duplicate task, same identity and dependencies."""
        ingress = self._ingress()
        command = self._command(project, key, task)
        from dataclasses import asdict
        with ingress.scheduler.lock:
            current = ingress.store.get(row['id'])
            if current['state'] not in {'QUEUED', 'READY', 'WAITING_DEPENDENCY', 'PAUSED', 'WAITING_USER'}:
                return False
            ingress.store.transition(row['id'], current['state'], f"Instruction refreshed for project spec v{project['version']}",
                                     command=asdict(command))
            item = ingress.scheduler.items.get(row['id'])
            if item:
                ingress.scheduler.items[row['id']] = (item[0], command, item[2])
        task['spec_version'] = project['version']
        return True

    def _kind_for(self, text, prohibit):
        if prohibit:
            return 'constraint'
        t = topics(text)
        if t and t <= {'concept:interface'} | {w for w in words(text) if w in {'dark', 'light', 'modern', 'minimal', 'clean', 'futuristic', 'sleek'}}:
            return 'preference'
        return 'functional'

    def _on_add_requirement(self, project, text, details, quiet=False):
        body = requirement_text(text)
        prohibit = polarity(body) == 'prohibit'
        row = self.store.add_requirement(project['id'], body, kind=self._kind_for(body, prohibit), category='explicit',
                                         polarity='prohibit' if prohibit else 'require', evidence=text)
        found = conflicts(row, self.store.requirements(project['id']))
        if found:
            return self._conflict(self.store.get(project['id']), row, found, quiet)
        project = self.store.get(project['id'])
        notes = self._impact(project, topic_set=topics(body) & {t for t in topics(body) if t.startswith('concept:')},
                             reason=f"{row['id']} added: {body}") if project['plan']['tasks'] else {}
        submitted = self._plan(self.store.get(project['id']))
        self._evaluate(self.store.get(project['id']))
        if quiet:
            return ''
        return ' '.join(part for part in (f"Added {row['id']}: {body} (spec v{row['created_version']}).",
                        f'Queued {submitted} new task(s).' if submitted else '', self._summary_of(notes), 'Other work continues.') if part)

    def _on_modify_requirement(self, project, text, details):
        body = requirement_text(text)
        candidates = [r for r in related(body, self.store.requirements(project['id'])) if r['kind'] in {'functional', 'preference', 'constraint', 'objective'}]
        if not candidates:
            return self._on_add_requirement(project, text, details)
        best = candidates[0]
        tied = [r for r in candidates[1:] if topics(r['text']) & topics(body) == topics(best['text']) & topics(body)]
        if tied and best['kind'] != 'preference':
            return (f"Does that change {best['id']} ({best['text']}) or {tied[0]['id']} ({tied[0]['text']})? "
                    'Say "change R1" with the new wording.')
        if best['kind'] == 'objective':
            # A change in look or quality refines the objective; record it as a new preference.
            return self._on_add_requirement(project, text, details)
        row = self.store.update_requirement(project['id'], best['id'], text=body, change={'op': 'modify', 'from': best['text'], 'to': body},
                                            evidence=text)
        project = self.store.get(project['id'])
        notes = self._impact(project, [best['id']], reason=f"{best['id']} changed to: {body}")
        submitted = self._plan(self.store.get(project['id']))
        return (f"Updated {best['id']}: {body} (spec v{row['updated_version']}). " + self._summary_of(notes)
                + (f'Queued {submitted} task(s). ' if submitted else '') + 'Unrelated work continues.').strip()

    def _on_remove_requirement(self, project, text, details):
        body = requirement_text(re.sub(r'^(?:remove|drop|delete|get rid of|take out|forget about|no longer (?:need|want)|skip)\s+', '',
                                       requirement_text(text), flags=re.I))
        active = [r for r in self.store.requirements(project['id']) if r['kind'] in {'functional', 'preference', 'deliverable'}]
        if re.fullmatch(r'(?:that|this|it|the last)(?: one| feature| requirement| change)?', body.casefold()):
            target = max(active, key=lambda r: r['updated_version'], default=None)
        else:
            target = next(iter(related(body, active)), None)
        if target is None:
            return f'I could not find an active requirement matching "{body}". Say "show the requirements" to see them.'
        self.store.update_requirement(project['id'], target['id'], status='removed', change={'op': 'remove', 'text': target['text']},
                                      evidence=text)
        project = self.store.get(project['id'])
        notes = self._impact(project, [target['id']], reason=f"{target['id']} removed: {target['text']}", mode='remove')
        self._plan(self.store.get(project['id']))
        return f"Removed {target['id']} ({target['text']}). " + self._summary_of(notes) + 'Other work continues.'

    def _on_constraint(self, project, text, details, quiet=False):
        body = requirement_text(text)
        verbs = {'editing': 'edit', 'changing': 'change', 'modifying': 'modify', 'touching': 'touch'}
        body = re.sub(r'^stop (editing|changing|modifying|touching)\b', lambda m: 'Do not ' + verbs[m[1].casefold()], body, flags=re.I)
        prohibit = polarity(body) == 'prohibit' or bool(re.match(r'^(?:keep the old|do not change|don\'?t change)', body, re.I))
        row = self.store.add_requirement(project['id'], body, kind='constraint', category='explicit',
                                         polarity='prohibit' if prohibit else 'require', evidence=text)
        found = conflicts(row, self.store.requirements(project['id']))
        project = self.store.get(project['id'])
        resolved = []
        for other in found:
            req = self.store.requirement(project['id'], other['requirement'])
            if req['category'] in {'inferred', 'assumption', 'recommendation'}:
                # The newer explicit constraint wins over Jarvis's own inference; recorded, reversible.
                self.store.update_requirement(project['id'], req['id'], status='superseded', change={'op': 'supersede', 'by': row['id']},
                                              source='constraint', evidence=body)
                resolved.append(req['id'])
        explicit = [f for f in found if f['requirement'] not in resolved]
        topic_set = prohibited_topics(body) if prohibit else topics(body)
        pronoun = re.search(r'\b(?:that|this) (?:module|file|part|component)\b', body, re.I)
        project = self.store.get(project['id'])
        if pronoun:
            running = [k for k, t in project['plan']['tasks'].items() if (self._task_row(t) or {}).get('state') == 'RUNNING']
            topic_set = topic_set | {w for k in running for w in topics(project['plan']['tasks'][k]['title'])}
        notes = self._impact(project, resolved + [f['requirement'] for f in explicit], topic_set=topic_set,
                             reason=f"{row['id']}: {body}", mode='stop' if prohibit else 'update')
        project = self.store.get(project['id'])
        project['plan']['tasks']['conformance:' + row['id']] = {
            'title': f"Review the existing work for conformance with {row['id']} ({body}) and replace anything that violates it",
            'milestone': 'Verification', 'requirements': [row['id']], 'depends': ['workspace'], 'status': 'planned', 'revision': 0, 'attempts': 0}
        self.store.save(project)
        self._plan(self.store.get(project['id']))
        if explicit:
            return self._conflict(self.store.get(project['id']), row, explicit, quiet, notes)
        self._evaluate(self.store.get(project['id']))
        if quiet:
            return ''
        return (f"Recorded constraint {row['id']}: {body} (spec v{row['created_version']}). "
                + (f"Superseded my own earlier assumption(s) {', '.join(resolved)}. " if resolved else '')
                + self._summary_of(notes) + 'Compatible work continues.').strip()

    def _conflict(self, project, row, found, quiet=False, notes=None):
        """Explicit requirements that contradict each other: explain, record, ask; never silently pick one."""
        self.store.update_requirement(project['id'], row['id'], status='conflicting', change={'op': 'conflict', 'with': [f['requirement'] for f in found]})
        for other in found:
            self.store.update_requirement(project['id'], other['requirement'], status='conflicting', change={'op': 'conflict', 'with': [row['id']]})
        project = self.store.get(project['id'])
        text = (f"{row['id']} ({row['text']}) conflicts with " + '; '.join(f"{f['requirement']} ({f['text']})" for f in found)
                + f" on {', '.join(s.replace('concept:', '') for s in found[0]['shared'])}. Which should win? Say \"keep {row['id']}\" or "
                f"\"keep {found[0]['requirement']}\". Affected tasks are on hold; unrelated work continues.")
        project['questions'] = [q for q in project['questions'] if q['status'] != 'open'] + [
            {'id': len(project['questions']) + 1, 'slots': [], 'conflict': [row['id']] + [f['requirement'] for f in found],
             'text': text, 'asked_at': self.clock(), 'status': 'open'}]
        self.store.save(project)
        self._observe('project.requirement.conflict', project, {'detail': text[:280], 'signature': row['id']})
        return text + (' ' + self._summary_of(notes) if notes else '')

    def _on_answer(self, project, text, details):
        question = self._open_question(project)
        keep = re.search(r'\bkeep (R\d+)\b', text, re.I)
        if question and question.get('conflict') and keep and keep[1].upper() in question['conflict']:
            winner = keep[1].upper()
            for rid in question['conflict']:
                if rid != winner:
                    self.store.update_requirement(project['id'], rid, status='superseded', category='rejected',
                                                  change={'op': 'resolve_conflict', 'winner': winner}, evidence=text)
            self.store.update_requirement(project['id'], winner, status='active', category='confirmed', change={'op': 'confirm'}, evidence=text)
            project = self.store.get(project['id'])
            for row in project['questions']:
                if row['id'] == question['id']:
                    row.update(status='answered', answer=text[:300])
            self.store.save(project)
            notes = self._impact(project, question['conflict'], reason=f'conflict resolved in favour of {winner}')
            self._plan(self.store.get(project['id']))
            return f"Keeping {winner}; the other requirement is superseded. " + self._summary_of(notes)
        return self._on_add_requirement(project, text, details)

    def _on_accept_recommendation(self, project, text, details):
        return self.accept_recommendation(project, int(details['target']))

    def _on_priority(self, project, text, details):
        target = details.get('target') or text
        if re.fullmatch(r'(?:this|that|it)', target.strip(), re.I):
            graph = self._group(project)
            if graph:
                self._ingress().group_control('urgent', graph)
            return f"Project {project['name']} is now the highest priority group."
        rows = related(target, self.store.requirements(project['id']))
        wanted = topics(target)
        ingress = self._ingress()
        raised = []
        for key, task in project['plan']['tasks'].items():
            if (set(task['requirements']) & {r['id'] for r in rows[:2]}) or (wanted & topics(task['title']) and key not in {'verify', 'workspace'}):
                row = self._task_row(task)
                if row and row['state'] not in TERMINAL and ingress:
                    ingress.scheduler.control('urgent', row['id'], 50)
                    raised.append(key)
        self.store.add_requirement(project['id'], 'Prioritise ' + clean(target), kind='priority', category='explicit', evidence=text)
        return (f"Prioritised {len(raised)} task(s) for {clean(target)}." if raised else
                f"Recorded the priority for {clean(target)}; matching work will be prioritised when it is queued.")

    def _on_revert(self, project, text, details):
        versions = self.store.versions(project['id'])
        change = next((v for v in reversed(versions) if v['change'].get('op') in {'add', 'modify', 'remove'}
                       and not v['change'].get('reverted')), None)
        if change is None:
            return 'There is no requirement change to undo.'
        op, rid = change['change']['op'], change['change']['requirement']
        if op == 'add':
            self.store.update_requirement(project['id'], rid, status='removed', change={'op': 'revert', 'of': change['version']}, evidence=text)
        elif op == 'remove':
            self.store.update_requirement(project['id'], rid, status='active', change={'op': 'revert', 'of': change['version']}, evidence=text)
        else:
            self.store.update_requirement(project['id'], rid, text=change['change']['from'], change={'op': 'revert', 'of': change['version']}, evidence=text)
        project = self.store.get(project['id'])
        notes = self._impact(project, [rid], reason=f'reverted spec v{change["version"]}', mode='remove' if op == 'add' else 'update')
        self._plan(self.store.get(project['id']))
        return f"Reverted the change from spec v{change['version']} ({op} {rid}). " + self._summary_of(notes)

    def _on_permission(self, project, text, details):
        target = details.get('target', '')
        for ref in project['references']:
            if set(words(target)) & set(words(ref['name'])) or 'reference' in target:
                ref['editable'] = True
                self.store.save(project)
                self._decide(project['id'], 'reference', f"You allowed edits to {ref['name']}", 'user-confirmed')
                return (f"Noted: {ref['name']} may be edited. I still won't change it unless a task needs to, "
                        'and existing approvals for file changes still apply.')
        return 'That is not one of the registered references, so nothing changed.'

    def _on_pause(self, project, text, details):
        project['status'] = 'paused'
        self.store.save(project)
        group = self._group(project)
        if group:
            self._ingress().group_control('pause', group)
        return f"Paused project {project['name']}. Running steps stop at their next safe checkpoint; nothing was undone."

    def _on_resume(self, project, text, details):
        project['status'] = 'active'
        self.store.save(project)
        group = self._group(project)
        if group:
            self._ingress().group_control('resume', group)
        submitted = self._plan(self.store.get(project['id']))
        blocked = [k for k, t in project['plan']['tasks'].items() if t['status'] == 'blocked']
        return (f"Resumed {project['name']}; {submitted} task(s) queued." + (f" Still blocked: {', '.join(blocked)} — "
                'started work is never replayed blindly; inspect it with "what are the blockers".' if blocked else ''))

    def _on_switch(self, project, text, details):
        target = details.get('target', '')
        wanted = set(words(target))
        scored = sorted(((len(wanted & set(words(' '.join((p['name'], p['objective'], p['subject'], p['type'] or ''))))), p)
                         for p in self.store.all()), key=lambda pair: -pair[0])
        matches = [p for n, p in scored if n and n == scored[0][0]]
        if len(matches) != 1:
            return 'Projects: ' + '; '.join(f"#{p['number']} {p['name']}" for p in self.store.all()) + '. Say "switch to" and one of these names.'
        self.store.setting('active_project', matches[0]['id'])
        return f"Switched to {matches[0]['name']}."

    def _on_overnight(self, project, text, details):
        ingress = self._ingress()
        if ingress is None:
            return 'The durable queue is off, so overnight work is unavailable.'
        submitted = self._plan(project)
        ingress.control(Command('task', 'run the queue overnight'))
        return (f"Overnight mode is on for the queue, including {project['name']} ({submitted} more task(s) queued). "
                'Approvals, locked-desktop gates and the 20-second routine-choice policy still apply.')

    def _group(self, project):
        ingress = self._ingress()
        if ingress is None or not project.get('workflow'):
            return None
        with ingress.store.lock:
            row = ingress.store.db.execute('SELECT group_id FROM workflows WHERE id=?', (project['workflow'],)).fetchone()
        return row[0] if row else None

    @staticmethod
    def _summary_of(notes):
        if not notes:
            return ''
        parts = [f"{name} {', '.join(keys)}" for name, keys in (('updated in place:', notes.get('updated', [])),
                 ('cancelled before start:', notes.get('cancelled', [])), ('paused at a safe checkpoint:', notes.get('paused', [])),
                 ('follow-up planned after:', notes.get('followups', []))) if keys]
        return ('Tasks ' + '; '.join(parts) + '. ') if parts else ''

    # --- grounded answers -----------------------------------------------------------------------------------------
    def trace(self, project):
        """Requirement -> planned work -> execution -> artifacts -> verification -> acceptance."""
        rows = []
        checks = project.get('verification', {}).get('requirements', {})
        for req in self.store.requirements(project['id'], include_inactive=True):
            tasks = [(k, t) for k, t in project['plan']['tasks'].items() if req['id'] in t['requirements'] and k != 'verify']
            states = [(self._task_row(t) or {}).get('state', t['status']) for _, t in tasks]
            check = checks.get(req['id'])
            if req['status'] != 'active':
                status = req['status']
            elif check and check['result'] == 'fail':
                status = 'failed verification'
            elif check and check['result'] == 'pass' and (not tasks or all(s == 'COMPLETED' for s in states)):
                status = 'verified (static check)' if 'static' in check['method'] else 'verified'
            elif tasks and all(s == 'COMPLETED' for s in states):
                status = 'implemented, not verified'
            elif any(s in {'FAILED', 'blocked'} for s in states):
                status = 'blocked'
            elif any(s == 'RUNNING' for s in states):
                status = 'in progress'
            else:
                status = 'pending'
            rows.append({'id': req['id'], 'text': req['text'], 'category': req['category'], 'kind': req['kind'], 'status': status,
                         'tasks': [{'key': k, 'number': (self._task_row(t) or {}).get('number'), 'state': s} for (k, t), s in zip(tasks, states)],
                         'verification': check})
        return rows

    def _states(self, project):
        return {k: (self._task_row(t) or {}).get('state', t['status']) for k, t in project['plan']['tasks'].items()}

    def _on_progress(self, project, text, details):
        states = self._states(project)
        done = sum(1 for s in states.values() if s in {'COMPLETED', 'done'})
        running = [project['plan']['tasks'][k]['title'][:60] for k, s in states.items() if s == 'RUNNING']
        question = self._open_question(project)
        trace = self.trace(project)
        verified = sum(1 for r in trace if r['status'].startswith('verified'))
        return (f"{project['name']} (spec v{project['version']}, {project['status']}): {done} of {len(states)} planned tasks completed"
                + (f"; running: {'; '.join(running)}" if running else '') + f"; {verified} of {sum(1 for r in trace if r['status'] not in {'removed', 'superseded'})} "
                'requirements verified.' + (f" Waiting for you: {question['text']}" if question else '') + ' ' + self._next(project, states)).strip()

    def _next(self, project, states):
        nxt = next((project['plan']['tasks'][k]['title'][:70] for k, s in states.items() if s in {'QUEUED', 'READY', 'WAITING_DEPENDENCY', 'planned'}), None)
        return f'Next: {nxt}.' if nxt else ''

    def _on_remaining(self, project, text, details):
        rows = [r for r in self.trace(project) if not r['status'].startswith('verified') and r['status'] not in {'removed', 'superseded', 'rejected'}]
        if not rows:
            return 'Every active requirement has recorded verification evidence.'
        return 'Remaining: ' + '; '.join(f"{r['id']} {r['text'][:60]} ({r['status']})" for r in rows[:8]) + '.'

    def _on_completed(self, project, text, details):
        states = self._states(project)
        done = [project['plan']['tasks'][k]['title'][:60] for k, s in states.items() if s in {'COMPLETED', 'done'}]
        files = self.files(project)
        verified = [r['id'] + (' (static)' if 'static' in r['status'] else '') for r in self.trace(project) if r['status'].startswith('verified')]
        return ((f"Completed tasks: {'; '.join(done)}." if done else 'No planned task has completed yet.')
                + (f" Files in the workspace: {', '.join(files[:8])}{' …' if len(files) > 8 else ''}." if files else '')
                + (f" Verified requirements: {', '.join(verified)}." if verified else ' No requirement is verified yet.'))

    def _on_blockers(self, project, text, details):
        blockers = []
        question = self._open_question(project)
        if question:
            blockers.append('waiting for your answer: ' + question['text'])
        for key, task in project['plan']['tasks'].items():
            row = self._task_row(task)
            if task['status'] == 'blocked':
                blockers.append(f"{key}: {task.get('blocked_reason', 'blocked')}")
            elif row and row['state'] in {'WAITING_APPROVAL', 'WAITING_USER', 'PAUSED'}:
                blockers.append(f"{key}: task #{row['number']} is {row['state'].lower().replace('_', ' ')}")
        pending = [m for m in self.decisions.values() if m['project'] == project['id']]
        blockers += [f"routine choice pending for {m['slot']}" for m in pending]
        return ('Blockers: ' + '; '.join(blockers) + '.') if blockers else 'Nothing is blocking the project right now.'

    def _on_why(self, project, text, details):
        target = (details.get('target') or '').casefold()
        broad = target.strip() in {'architecture', 'approach', 'design', 'option', 'plan'}
        rows = [d for d in project['decisions'] if not target or (broad and d['slot'] in {'technology', 'architecture', 'workspace'})
                or set(words(target)) & set(words(d['slot'] + ' ' + d['text']))]
        if not rows:
            return 'I have not recorded a decision about that yet; nothing was chosen silently.'
        return ' '.join(f"{d['slot'].title()}: {d['text']} ({d['kind']}{', automatic' if d['automatic'] else ''}, spec v{d['version']})." for d in rows[-3:])

    def _on_design(self, project, text, details):
        groups = {}
        for req in self.store.requirements(project['id'], include_inactive=True):
            groups.setdefault(req['category'] if req['status'] == 'active' else req['status'], []).append(f"{req['id']} {req['text']}")
        spec = '; '.join(f"{k}: {', '.join(v)}" for k, v in groups.items())
        milestones = ' → '.join(f"{m['title']} ({len(m['tasks'])})" for m in project['plan']['milestones'])
        return f"Spec v{project['version']} — {spec}. Plan: {milestones or 'not planned yet'}."

    def _on_missing(self, project, text, details):
        findings = self._evaluate(project)
        return ('Possible gaps (suggestions only, not requirements until you accept them): '
                + '; '.join(f"#{i + 1} {f['text']}" for i, f in enumerate(findings)) + '. Say "accept recommendation N".') if findings \
            else 'I found no missing tests, conflicts, unmeasurable requirements or unresolved references.'

    def _on_better_way(self, project, text, details):
        findings = [f for f in self._evaluate(project) if f['kind'] in {'reuse', 'simplify'}]
        if not findings:
            return 'I have no evidence-backed alternative to suggest right now.'
        return 'Ideas (not adopted unless you accept them): ' + '; '.join(f['text'] for f in findings) + '.'

    def _evaluate(self, project):
        """Proactive requirement reasoning. Findings stay recommendations; awareness decides whether to interrupt."""
        if not project:
            return []
        requirements = self.store.requirements(project['id'])
        findings = []
        if project['type'] == 'software' and not any(concept == 'concept:testing' for r in requirements for concept in topics(r['text'])):
            findings.append({'kind': 'missing', 'text': 'No requirement asks for tests; I recommend automated tests for the core behaviour'})
        for req in requirements:
            if req['kind'] in {'functional', 'preference'} and re.search(r'\b(?:faster|better|nicer|improve|optimi[sz]e|good|modern)\b', req['text'], re.I) \
                    and not re.search(r'\d', req['text']):
                findings.append({'kind': 'measurable', 'text': f"{req['id']} ({req['text']}) has no measurable target; tell me one or I will verify it qualitatively"})
        for ref in project['references']:
            reusable = sorted({c for c in ref['components'] for r in requirements if set(words(c)) & set(words(r['text']))})[:4]
            if reusable:
                findings.append({'kind': 'reuse', 'text': f"{ref['name']} has components related to the requirements ({', '.join(reusable)}); "
                                 'they could be adapted (copied, never edited in place)'})
        functional = [r for r in requirements if r['kind'] == 'functional']
        if len(functional) > 8:
            findings.append({'kind': 'simplify', 'text': f'{len(functional)} functional requirements; delivering a first version with the top 5 would reduce risk'})
        for row in self.store.requirements(project['id'], include_inactive=True):
            if row['status'] == 'conflicting':
                findings.append({'kind': 'conflict', 'text': f"{row['id']} is in conflict and waits for your decision"})
        project = self.store.get(project['id'])
        old = {f['text'] for f in project.get('recommendations', [])}
        project['recommendations'] = findings
        self.store.save(project)
        for finding in findings:
            if finding['text'] not in old:
                self._observe('project.requirement.' + {'conflict': 'conflict', 'missing': 'missing'}.get(finding['kind'], 'changed'), project,
                              {'detail': finding['text'][:280], 'signature': finding['kind'] + ':' + finding['text'][:40],
                               'severity': .4 if finding['kind'] in {'conflict', 'missing'} else .2})
        return findings

    def accept_recommendation(self, project, number):
        rows = project.get('recommendations', [])
        if not 1 <= number <= len(rows):
            return 'There is no recommendation with that number.'
        finding = rows[number - 1]
        text = 'Automated tests cover the core behaviour' if finding['kind'] == 'missing' else finding['text']
        row = self.store.add_requirement(project['id'], text, kind='functional', category='confirmed', source='accepted recommendation',
                                         evidence=finding['text'])
        self._plan(self.store.get(project['id']))
        return f"Accepted as {row['id']}: {text}."

    def _observe(self, kind, project, values):
        awareness = getattr(self.actions, 'awareness', None)
        if awareness is not None and getattr(awareness, 'enabled', False):
            try:
                awareness.observe(kind, 'project intelligence', 'project', values, sensor='tasks', project=project['name'][:80],
                                  retention='days')
            except Exception:
                pass  # Awareness is optional; project state is already persisted.

    def _remember(self, identity, why):
        memory = getattr(self.actions, 'memory', None)
        project = self.store.get(identity)
        if memory is not None and hasattr(memory, 'record') and project:
            try:
                memory.record('Jarvis project', f"{project['name']} ({why}): {project['objective'][:200]}")
            except Exception:
                pass  # Semantic memory is a retrieval aid; ProjectStore is authoritative.

    # --- project_step: workspace creation and acceptance checks (runs on the existing action worker) -------------
    def _spec_text(self, project):
        requirements = self.store.requirements(project['id'])
        lines = [f"# {project['name']} — requirements v{project['version']}", '', f"Objective: {project['objective']}", '']
        for category in ('explicit', 'confirmed', 'inferred', 'assumption'):
            rows = [r for r in requirements if r['category'] == category]
            if rows:
                lines += [f'## {category.title()}'] + [f"- {r['id']} [{r['kind']}{', must not' if r['polarity'] == 'prohibit' else ''}] {r['text']}" for r in rows] + ['']
        if project['references']:
            lines += ['## Read-only references'] + [f"- {r['name']}: {r['path']}" + (' (edits allowed)' if r['editable'] else ' (do not modify)')
                                                    for r in project['references']] + ['']
        constraints = '; '.join(r['text'] for r in requirements if r['kind'] == 'constraint')
        return {'markdown': '\n'.join(lines), 'constraints': constraints}

    def run_step(self, value, cancelled=lambda: False):
        data = json.loads(value)
        project = self.store.get(data['project'])
        if project is None:
            raise ValueError('Unknown project')
        if data['op'] == 'workspace':
            return self._create_workspace(project, cancelled)
        if data['op'] == 'verify':
            return self._verify(project)
        raise ValueError('Unknown project step')

    def _owned_write(self, project, path, text):
        """Write a Jarvis-generated file; replace it only if it still has the content Jarvis last wrote."""
        written = project.setdefault('generated', {})
        key = path.name
        if path.exists():
            if written.get(key) != sha256(path):
                return False  # Someone edited it; never overwrite their change.
            temporary = path.with_suffix(path.suffix + '.tmp')
            temporary.write_text(text, encoding='utf-8')
            temporary.replace(path)
        else:
            with path.open('x', encoding='utf-8') as stream:
                stream.write(text)
        written[key] = sha256(path)
        ingress = self._ingress()
        if ingress and getattr(ingress.scheduler.local, 'identity', None):
            ingress.scheduler.record_effect({'kind': 'file', 'path': str(path), 'bytes': path.stat().st_size, 'sha256': written[key],
                                             'verification': 'fresh byte readback'})
        return True

    def _create_workspace(self, project, cancelled):
        workspace = Path(project['workspace'])
        for ref in project['references']:
            if Path(ref['path']) == workspace or Path(ref['path']) in workspace.parents:
                raise ValueError('Refusing to create the workspace inside a reference project')
        if workspace.exists() and any(workspace.iterdir()) and project['workspace_state'] != 'created':
            raise ValueError(f'{workspace} is not empty; nothing was overwritten. Choose another location.')
        workspace.mkdir(parents=False, exist_ok=True)
        if cancelled():
            return 'Workspace creation stopped'
        spec = self._spec_text(project)
        project = self.store.get(project['id'])
        self._owned_write(project, workspace / 'REQUIREMENTS.md', spec['markdown'])
        self._owned_write(project, workspace / 'PROJECT.md', f"# {project['name']}\n\n{project['objective']}\n\n"
                          'Managed with Jarvis project intelligence. REQUIREMENTS.md is the authoritative specification.\n')
        project.update(workspace_state='created')
        self.store.save(project)
        return f"Created workspace {workspace} with REQUIREMENTS.md v{project['version']}"

    def _verify(self, project):
        """Acceptance checks. Each result records its method; static checks are labelled as static."""
        workspace = Path(project['workspace'])
        requirements = self.store.requirements(project['id'])
        results = {}
        sources = {}
        if workspace.is_dir():
            for folder, dirs, names in os.walk(workspace):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]
                for name in names:
                    path = Path(folder) / name
                    if path.suffix.casefold() in LANGUAGES and path.suffix.casefold() != '.md' and path.stat().st_size < 2_000_000:
                        sources[path.relative_to(workspace).as_posix()] = path.read_text(encoding='utf-8', errors='replace')
        for req in requirements:
            text = req['text']
            if req['kind'] == 'constraint' and text.startswith('Do not modify the reference project'):
                ref = next((r for r in project['references'] if text.endswith(r['name'])), None)
                if ref:
                    before = json.loads(Path(ref['baseline']).read_text(encoding='utf-8'))
                    after, _, _ = snapshot(Path(ref['path']))
                    changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
                    results[req['id']] = {'result': 'fail' if changed else 'pass', 'method': 'size/SHA-256 comparison with the registration snapshot',
                                          'evidence': changed[:10] or f"{len(after)} files unchanged"}
            elif req['polarity'] == 'prohibit' and 'concept:network' in prohibited_topics(text):
                hits = [f"{name}: {m.group(0)}" for name, body in sources.items() for m in [NETWORK.search(body)] if m]
                results[req['id']] = {'result': 'fail' if hits else 'pass' if sources else 'not checked',
                                      'method': 'static scan for network/cloud client imports and remote URLs (not a network-disabled runtime test)',
                                      'evidence': hits[:10] or f'{len(sources)} source files scanned'}
            elif req['kind'] == 'location':
                results[req['id']] = {'result': 'pass' if workspace.is_dir() else 'fail', 'method': 'folder exists', 'evidence': str(workspace)}
            elif req['kind'] in {'functional', 'objective', 'preference'}:
                keys = [w for w in words(text) if len(w) > 3][:6]
                found = sorted({name for name, body in sources.items() for k in keys if k[:6] in body.casefold()})
                results[req['id']] = {'result': 'evidence' if found else 'not checked', 'method': 'static keyword trace in source (not behavioural verification)',
                                      'evidence': found[:8]}
        tests = sorted(name for name in sources if re.search(r'(?:^|/)tests?/|test_|_test\.|\.test\.', name))
        test_requirement = next((r for r in requirements if 'concept:testing' in topics(r['text'])), None)
        if test_requirement:
            results[test_requirement['id']] = {'result': 'evidence' if tests else 'fail', 'method': 'test files present (execution not performed by this check)',
                                               'evidence': tests[:10]}
        project = self.store.get(project['id'])
        project['verification'] = {'version': project['version'], 'at': self.clock(), 'requirements': results}
        self.store.save(project)
        findings = [{'claim': f"{rid}: {r['result']} — {r['method']}", 'evidence': r['evidence']} for rid, r in results.items()]
        ingress = self._ingress()
        if ingress and getattr(ingress.scheduler.local, 'identity', None):
            ingress.scheduler.publish_output({'project': project['id'], 'spec_version': project['version'], 'checks': results},
                                             findings=findings[:40], verified=True)
        failed = [rid for rid, r in results.items() if r['result'] == 'fail']
        return (f"Acceptance checks for spec v{project['version']}: {sum(r['result'] == 'pass' for r in results.values())} passed, "
                f"{len(failed)} failed{(' (' + ', '.join(failed) + ')') if failed else ''}, "
                f"{sum(r['result'] in {'evidence', 'not checked'} for r in results.values())} need behavioural verification.")

    # --- reports and UI ---------------------------------------------------------------------------------------------
    def files(self, project):
        workspace = Path(project['workspace'] or '')
        if not project.get('workspace') or not workspace.is_dir():
            return []
        rows = []
        for folder, dirs, names in os.walk(workspace):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]
            rows += [(Path(folder) / n).relative_to(workspace).as_posix() for n in names]
            if len(rows) > 500:
                break
        return sorted(rows)

    def report(self, project):
        ingress = self._ingress()
        states = self._states(project)
        decisions = [d for d in (ingress.decisions.rows() if ingress else []) if d['question'].startswith(f"Project {project['name']}:")]
        trace = self.trace(project)
        return {'project': project['name'], 'workspace': project['workspace'], 'spec_version': project['version'], 'status': project['status'],
                'completed_features': [r for r in trace if r['status'].startswith('verified') or r['status'] == 'implemented, not verified'],
                'remaining_features': [r for r in trace if r['status'] in {'pending', 'in progress', 'blocked', 'failed verification'}],
                'files': self.files(project), 'verification': project.get('verification', {}),
                'engineering': project.get('engineering'),
                'automatic_decisions': [d for d in decisions if d.get('automatic')] + [d for d in project['decisions'] if d['automatic']],
                'failed_or_blocked': {k: project['plan']['tasks'][k].get('blocked_reason', s) for k, s in states.items()
                                      if s in {'FAILED', 'blocked', 'WAITING_APPROVAL', 'WAITING_USER', 'PAUSED'}},
                'decisions': project['decisions'], 'requirement_versions': len(self.store.versions(project['id'])),
                'next_steps': [f['text'] for f in project.get('recommendations', [])] + [self._next(project, states)],
                'note': 'From persisted project, task and verification records. Static checks are labelled; nothing is inferred from task titles.'}

    def write_report_companion(self, path):
        path = Path(path)
        rows = [self.report(p) for p in self.store.all() if p['plan']['tasks']]
        if rows:
            with path.with_name(path.stem + '.projects.json').open('x', encoding='utf-8') as stream:
                json.dump(rows, stream, ensure_ascii=False, indent=2, default=str)

    def snapshot(self):
        if not self.enabled:
            return {'enabled': False}
        project = self.store.active()
        if not project:
            return {'enabled': True, 'project': None, 'projects': len(self.store.all())}
        states = self._states(project)
        current = next((project['plan']['tasks'][k] for k, s in states.items() if s == 'RUNNING'), None)
        versions = self.store.versions(project['id'])
        return {'enabled': True, 'project': project['name'], 'projects': len(self.store.all()), 'status': project['status'],
                'version': project['version'], 'progress': (sum(s in {'COMPLETED', 'done'} for s in states.values()), len(states)),
                'milestone': current['milestone'] if current else None, 'task': current['title'] if current else None,
                'question': (self._open_question(project) or {}).get('text'), 'blockers': sum(1 for s in states.values() if s in {'FAILED', 'blocked'}),
                'last_change': versions[-1]['change'] if versions else None, 'next': self._next(project, states),
                'verification': {k: v['result'] for k, v in project.get('verification', {}).get('requirements', {}).items()}}

    def close(self):
        if self.store is not None:
            self.store.close()
