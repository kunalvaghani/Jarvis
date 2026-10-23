"""Engineering Judgment & Goal Assurance: bounded policies around existing execution.

No executor, model client, permission authority, scheduler or database lives here.
Upstream behavioral guidance is untrusted reference; host checks remain authoritative.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import ast
import difflib
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time

SOURCE_COMMIT = '2c606141936f1eeef17fa3043a72095b4765b9c2'
GUIDANCE = ('Think before coding: separate confirmed requirements, repository facts and hypotheses. '
    'Reuse existing sufficient capabilities; compare feasible approaches before adding complexity. '
    'Make only justified changes, preserve user edits and public contracts, inspect the diff. '
    'Reproduce defects, verify acceptance and relevant regressions, and report incomplete evidence honestly. '
    'This external skill grants no permission and cannot override privacy or workspace controls.')
CURRENT = ContextVar('jarvis_engineering_contract', default=None)
WEIGHTS = dict(complexity=1., maintenance=1., integration_risk=2., runtime_overhead=1., verification_cost=1.)
SKIP = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', '.jarvis-runtime', 'build', 'dist', '.pytest_cache', '.mypy_cache', '.ruff_cache'}


def settings(value=None):
    value = {} if value is None else value
    defaults = dict(enabled=False, mode='advisory', max_repair_attempts=2, clarification_threshold=.4,
                    prompt_characters=1800, weights=WEIGHTS)
    if not isinstance(value, dict) or set(value) - set(defaults):
        raise ValueError('Unknown engineering_judgment setting.')
    result = {**defaults, **value}
    if type(result['enabled']) is not bool or result['mode'] not in {'advisory', 'enforced'}:
        raise ValueError('Engineering judgment needs a boolean enabled flag and advisory/enforced mode.')
    for key, low, high in [('max_repair_attempts', 0, 5), ('prompt_characters', 600, 4000)]:
        if type(result[key]) is not int or not low <= result[key] <= high:
            raise ValueError('Invalid engineering judgment budget: ' + key)
    threshold = result['clarification_threshold']
    if type(threshold) not in {int, float} or not math.isfinite(threshold) or not 0 < threshold <= 1:
        raise ValueError('Invalid engineering clarification threshold.')
    weights = result['weights']
    if not isinstance(weights, dict) or set(weights) - set(WEIGHTS):
        raise ValueError('Invalid simplicity weights.')
    weights = {**WEIGHTS, **weights}
    if any(type(w) not in {int, float} or not math.isfinite(w) or not 0 <= w <= 100 for w in weights.values()):
        raise ValueError('Simplicity weights must be finite nonnegative bounded numbers.')
    result['weights'] = weights
    return result


def applicability(goal, kind=None):
    text = str(goal or '')[:12000]
    if re.fullmatch(r'(?:please )?(?:open|launch|show|close|pause|play)\s+[^\n]{1,100}', text, re.I) and not re.search(r'\b(?:and|then|fix|modify|edit|refactor|implement)\b', text, re.I):
        return None
    if kind == 'code_task' or re.search(r'\b(?:code|coding|debug|refactor|connector|repository|scaffold|architecture|unit tests?|software|application development)\b|\.(?:py|js|tsx?|cs|cpp|rs)\b', text, re.I):
        return 'engineering'
    if re.search(r'\b(?:build|create|develop|fix|improve|repair|design)\b.*\b(?:app|application|program|website|project|tool|skill)\b', text, re.I):
        return 'engineering'
    if re.search(r'\b(?:blender|unreal|research|document|spreadsheet|report)\b', text, re.I):
        return 'project'
    return None


class RequirementValidationPolicy:
    def __init__(self, options=None):
        self.options = settings(options)

    def evaluate(self, objective, project=None, requirements=(), context=None):
        if not isinstance(objective, str) or len(objective) > 12000 or not isinstance(requirements, (list, tuple)):
            raise ValueError('Engineering validation needs a bounded objective and requirement list.')
        context = context or {}
        if not isinstance(context, dict):
            raise ValueError('Engineering context must be an object.')
        rows = [r for r in requirements if isinstance(r, dict) and r.get('status', 'active') in {'active', 'conflicting'}][:64]
        missing = list(context.get('missing', []))[:8]
        if not str(objective).strip():
            missing.append('objective')
        if applicability(objective) == 'engineering' and not project:
            missing.append('project destination')
        if re.fullmatch(r'(?:jarvis[, ]+)?(?:create|build|make|develop) (?:a |an |the )?(?:new )?(?:app|application|program|project)[.! ]*', objective, re.I) and not context.get('purpose'):
            missing.append('purpose and expected behavior')
        measured_target = context.get('performance_target') or re.search(r'\b\d+(?:\.\d+)?\s*(?:ms|milliseconds?|seconds?|percent|%)', objective, re.I)
        concrete_behavior = context.get('reproducible_failure') or re.search(
            r'\b(?:returns?|raises?)\s+(?:\d+|None\b|True\b|False\b|an? empty list|Untitled\b|["\'])', objective, re.I)
        if ((re.search(r'\bfaster\b', objective, re.I) and not measured_target) or
                (re.search(r'\b(?:more reliable|improve reliability)\b', objective, re.I) and not measured_target and not concrete_behavior)):
            missing.append('measured target or reproducible failure')
        conflicts = [r['text'] for r in rows if r.get('status') == 'conflicting']
        # Existing project requirement conflict handling owns the semantic comparison.
        conflicts += [str(c)[:300] for c in context.get('conflicts', [])[:8]]
        assumptions = [{'text': str(objective)[:2000], 'category': 'user_confirmed', 'source': 'current request'}]
        assumptions += [{'text': str(r.get('text', ''))[:500], 'category': r.get('category', 'unknown'),
                         'source': str(r.get('evidence') or r.get('source') or 'project requirements')[:200]} for r in rows]
        assumptions += [{'text': str(f.get('text', ''))[:500], 'category': 'verified_repository_fact',
                         'source': str(f['source'])[:200]} for f in context.get('facts', [])[:12]
                        if isinstance(f, dict) and f.get('verified') is True and f.get('source')]
        safe_default = not missing and not conflicts
        uncertainty = 1. if conflicts else .8 if missing else .1
        impact = .9 if conflicts or any('destination' in m or 'purpose' in m for m in missing) else .7
        score = round(uncertainty * impact, 3)  # Tunable heuristic, not a calibrated probability.
        return {'objective': objective[:6000], 'requirements': rows, 'assumptions': assumptions,
                'missing': list(dict.fromkeys(missing)), 'conflicts': conflicts,
                'clarification_value': score, 'heuristic_not_probability': True,
                'needs_clarification': bool(conflicts or missing and score >= self.options['clarification_threshold']),
                'safe_default': safe_default, 'question': 'Please clarify ' + '; '.join(conflicts or missing) if conflicts or missing else '',
                'investigation': 'Inspect existing facts and tests before asking for facts already present.'}


class SimplicityEvaluator:
    def __init__(self, options=None):
        self.options = settings(options)

    def choose(self, candidates, hard_requirements=(), confirmed=None):
        if not isinstance(candidates, list) or not 1 <= len(candidates) <= 20:
            raise ValueError('Supply one to twenty bounded architecture candidates.')
        feasible, rejected = [], []
        required = set(hard_requirements)
        for row in candidates:
            if not isinstance(row, dict) or not isinstance(row.get('id'), str):
                raise ValueError('Every approach needs an id.')
            missing = required - set(row.get('covers', []))
            if missing or row.get('speculative') or row.get('authorized') is False:
                rejected.append({'id': row['id'], 'missing': sorted(missing), 'reason': 'unmet requirement, speculative feature or unauthorized scope'})
                continue
            metrics = [row.get(key, 0) for key in WEIGHTS]
            if any(type(v) not in {int, float} or not math.isfinite(v) or v < 0 for v in metrics):
                raise ValueError('Approach costs must be finite nonnegative numbers.')
            cost = sum(self.options['weights'][k] * row.get(k, 0) for k in WEIGHTS)
            feasible.append({'id': row['id'], 'cost': round(cost, 4), 'reuse': bool(row.get('reuse'))})
        feasible.sort(key=lambda r: (r['cost'], not r['reuse'], r['id']))
        selected = next((r for r in feasible if r['id'] == confirmed), None) or next(iter(feasible), None)
        return {'selected': selected, 'feasible': feasible, 'rejected': rejected,
                'reason': 'Confirmed feasible user choice' if selected and selected['id'] == confirmed else 'Least configured cost among approaches satisfying every hard requirement'}

    def inspect_source(self, before, after, goal):
        """Signals for review, not proof that a type or safety abstraction is unnecessary."""
        try:
            old = {n.name for n in ast.walk(ast.parse(before or '')) if isinstance(n, ast.ClassDef)}
            tree = ast.parse(after)
        except SyntaxError:
            return {'signals': ['syntax_invalid'], 'automatic_rejection': False}
        added = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name not in old]
        required = bool(re.search(r'\b(?:concurrency|transaction|recovery|security|interface|framework|plugin)\b', goal, re.I))
        return {'new_types': added[:30], 'signals': ['new_abstractions_review'] if len(added) > 1 and not required else [],
                'necessary_complexity_may_apply': required, 'automatic_rejection': False}


class ChangeScopeGuardian:
    """Read-only bounded snapshots; no stashing, restoring, deleting or committing."""
    def __init__(self, root, expected=(), references=()):
        self.root = Path(root).resolve(strict=True)
        self.references = [Path(p).resolve() for p in references]
        self.expected = set(expected)
        self.before, self.complete = self.snapshot()

    def scoped(self, name):
        from .agent_context import scoped
        if any(part.casefold() in SKIP for part in Path(name).parts):
            raise ValueError('Repository metadata, runtime state and generated environments are not coding targets.')
        path = scoped(self.root, name)
        if any(path == p or path.is_relative_to(p) for p in self.references):
            raise ValueError('Reference projects remain read-only.')
        return path

    def snapshot(self):
        files, total, complete = {}, 0, True
        from .skill_memory import linked
        for folder, dirs, names in os.walk(self.root):
            dirs[:] = [d for d in dirs if d not in SKIP and not d.startswith('.venv') and not linked(Path(folder) / d)]
            for name in names:
                if len(files) >= 2000:
                    return files, False
                path = Path(folder) / name
                if linked(path):
                    complete = False; continue
                size = path.stat().st_size
                if size > 1_000_000 or total + size > 8_000_000:
                    complete = False; continue
                raw = path.read_bytes(); total += len(raw)
                files[path.relative_to(self.root).as_posix()] = hashlib.sha256(raw).hexdigest()
        return files, complete

    def propose(self, steps):
        mapping = {}
        for row in steps:
            name, reason = row.get('path'), row.get('reason')
            if not isinstance(name, str) or not isinstance(reason, str) or not reason.strip():
                raise ValueError('Each proposed file needs a requirement-related justification.')
            name = self.scoped(name).relative_to(self.root).as_posix()
            mapping[name] = reason[:500]
        self.expected.update(mapping)
        return mapping

    def inspect_content(self, before, after, suffix='.py'):
        findings = []
        if before != after and ''.join(before.split()) == ''.join(after.split()):
            findings.append('formatting_only')
        if suffix == '.py':
            try:
                tree = ast.parse(after)
                used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
                previous = ast.parse(before or '')
                old = {a.asname or a.name.split('.')[0] for n in ast.walk(previous) if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}
                introduced = {a.asname or a.name.split('.')[0] for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names} - old
                findings += ['possibly_unused_import:' + name for name in sorted(introduced - used)]
            except SyntaxError:
                findings.append('syntax_invalid')
        return {'findings': findings, 'diff_lines': len(list(difflib.unified_diff(before.splitlines(), after.splitlines()))),
                'note': 'Diff size is diagnostic only; imports may be intentional re-exports.'}

    def audit(self):
        after, complete = self.snapshot()
        changed = sorted(k for k in set(self.before) | set(after) if self.before.get(k) != after.get(k))
        outside = [p for p in changed if p not in self.expected]
        return {'changed': changed, 'unexpected': outside, 'complete': self.complete and complete,
                'verified': self.complete and complete and not outside,
                'before_hashes': {p: self.before.get(p) for p in changed[:100]},
                'after_hashes': {p: after.get(p) for p in changed[:100]}}


class GoalContractGenerator:
    def create(self, objective, project=None, validation=None, version=1):
        identity = hashlib.sha256(json.dumps([objective, str(project), version]).encode()).hexdigest()[:24]
        validation = validation or {}
        domain = validation.get('domain') or applicability(objective)
        criteria = [('behavior', 'Fresh original-goal or domain acceptance verification'),
                    ('scope', 'Before/after file hashes and justified scope'),
                    ('regression' if domain == 'engineering' else 'domain_checks',
                     'Relevant executed tests with current source identity' if domain == 'engineering' else 'Domain readback, reconciliation or asset/render validation')]
        return {'goal_id': identity, 'parent_project': str(project) if project else None, 'version': version,
                'objective': objective[:6000], 'validation': validation or {}, 'expected_artifacts': [],
                'required_behavior': [objective[:6000], *[r.get('text', '') for r in validation.get('requirements', [])]],
                'constraints': [r.get('text', '') for r in validation.get('requirements', []) if r.get('kind') == 'constraint'],
                'known_assumptions': validation.get('assumptions', []), 'domain': domain,
                'acceptance': [{'id': k, 'verified': False, 'method': method} for k, method in criteria],
                'test_commands': [], 'required_permissions': 'Existing tool/connector approvals; this contract grants none',
                'state': 'unverified', 'decisions': [], 'checks': [], 'repairs': []}


class GoalAssurance:
    @staticmethod
    def record(contract, criterion, *, method, evidence, passed, source_hashes=None):
        """Host verifier API. Never called from model-produced tool arguments."""
        if type(passed) is not bool or not method or not evidence:
            raise ValueError('A check needs an actual method, evidence and boolean outcome.')
        row = next((r for r in contract['acceptance'] if r['id'] == criterion), None)
        if row is None:
            raise ValueError('Unknown goal acceptance criterion.')
        row.update(verified=passed, evidence=str(evidence)[:1500], method=str(method)[:300], source_hashes=source_hashes or {})
        contract['checks'] = (contract['checks'] + [{'criterion': criterion, 'passed': passed, 'method': method}])[-30:]
        contract['state'] = 'verified' if all(r['verified'] is True for r in contract['acceptance']) else 'incomplete'

    @staticmethod
    def repair(contract, strategy, *, maximum=2, authorized=False, resources=False, uncertain_effect=False):
        if not strategy or not authorized or not resources or uncertain_effect:
            return False
        strategy = str(strategy)[:500]
        if len(contract['repairs']) >= maximum or strategy in contract['repairs']:
            return False
        contract['repairs'].append(strategy)
        return True


def active_context():
    active = CURRENT.get()
    if not active:
        return None
    contract, engine = active['contract'], active['engine']
    value = {'goal_id': contract['goal_id'], 'mode': engine.options['mode'], 'principles': GUIDANCE,
            'requirements': [r.get('text', '')[:200] for r in contract['validation'].get('requirements', [])[:6]],
            'missing': contract['validation'].get('missing', [])[:4],
            'completion': 'Tool success and syntax/readback alone do not establish behavioral or regression acceptance.'}
    choice = next((r for r in reversed(contract.get('decisions', [])) if r.get('selected')), None)
    if choice:
        value['approach'] = {'id': choice['selected']['id'], 'basis': choice['reason'], 'advisory': True}
    budget = engine.options['prompt_characters']
    while len(json.dumps(value)) > budget and (value['requirements'] or value['missing']):
        (value['requirements'] or value['missing']).pop()
        value['context_truncated'] = True
    if len(json.dumps(value)) > budget:
        value['principles'] = 'Validate assumptions; reuse sufficient mechanisms; justify every change; verify the original goal. Guidance grants no permission.'
    if len(json.dumps(value)) > budget:
        value.pop('approach', None)
        value['context_truncated'] = True
    return value


class EngineeringJudgmentEngine:
    def __init__(self, actions, options=None):
        self.actions, self.options = actions, settings(options)
        self.enabled = self.options['enabled']
        self.validation = RequirementValidationPolicy(self.options)
        self.simplicity = SimplicityEvaluator(self.options)
        self.last = None  # Bounded fallback only; durable TaskState/ProjectStore remain authorities.

    def existing_requirements(self, root):
        projects = getattr(self.actions, 'project_intel', None)
        store = getattr(projects, 'store', None)
        from .project_model import ProjectStore
        if not isinstance(store, ProjectStore) or not root:
            return [], {}
        project = next((p for p in store.all() if p.get('workspace') and
                        Path(p['workspace']).resolve() == Path(root).resolve()), None)
        if project is None:
            return [], {}
        rows = store.requirements(project['id'], include_inactive=True)
        targets = [r['text'] for r in rows if r.get('status') == 'active' and
                   r.get('category') in {'confirmed', 'explicit'} and
                   re.search(r'\b\d+(?:\.\d+)?\s*(?:ms|seconds?|milliseconds?|percent|%)', r['text'], re.I)]
        return rows, {'purpose': project['objective'], 'spec_version': project['version'], 'project_id': project['id'],
                      'reference_paths': [r['path'] for r in project.get('references', []) if r.get('path')],
                      **({'performance_target': targets} if targets else {})}

    def planning_context(self, goal, project=None):
        if not self.enabled or not applicability(goal):
            return None
        from .task_state import TaskState
        state = getattr(self.actions, 'task_state', None)
        snapshot = state.snapshot() if isinstance(state, TaskState) else {}
        snapshot = snapshot or {}
        record = snapshot.get('engineering')
        project = project or snapshot.get('project')
        rows, context = self.existing_requirements(project)
        version = context.get('spec_version', 1)
        if not record or record['objective'] != goal[:6000] or record.get('parent_project') != (str(project) if project else None) or record['version'] != version:
            validation = self.validation.evaluate(goal, project, rows, context)
            record = GoalContractGenerator().create(goal, project, validation, version)
            record['mode'] = self.options['mode']
            self.persist(record)
        if record['validation'].get('needs_clarification') and self.options['mode'] == 'enforced':
            from .clarification import TaskClarification
            raise TaskClarification(record['validation']['question'])
        token = CURRENT.set({'engine': self, 'contract': record})
        try:
            return active_context()
        finally:
            CURRENT.reset(token)

    def persist(self, contract):
        contract['updated_at'] = time.time()
        from .task_state import TaskState
        state = getattr(self.actions, 'task_state', None)
        if isinstance(state, TaskState):
            state.set_engineering(contract)
        self.last = json.loads(json.dumps(contract))

    @contextmanager
    def coding(self, root, goal, cancelled=lambda: False):
        if not self.enabled or not applicability(goal, 'code_task'):
            yield None; return
        root = Path(root).resolve(strict=True)
        if not root.is_dir() or root.parent == root or not isinstance(goal, str) or not goal.strip():
            raise ValueError('Name an individual project and a bounded development goal.')
        requirements, known = self.existing_requirements(root)
        validation = self.validation.evaluate(goal, root, requirements, known)
        validation['domain'] = 'engineering'
        validation['assumptions'].append({'text': 'Selected project directory exists.',
            'category': 'verified_repository_fact', 'source': 'Filesystem scope validation: ' + str(root)})
        contract = GoalContractGenerator().create(goal, root, validation, known.get('spec_version', 1))
        if known.get('project_id'):
            contract['project_id'] = known['project_id']
        contract['mode'] = self.options['mode']
        guardian = ChangeScopeGuardian(root, references=known.get('reference_paths', []))
        existing_sources = [p for p in guardian.before if Path(p).suffix in {'.py', '.js', '.ts', '.tsx', '.cs', '.cpp', '.go', '.rs'}]
        replacement = bool(re.search(r'\b(?:rewrite|replace entire|from scratch)\b', goal, re.I)) and not bool(
            re.search(r"\b(?:do not|don't|never|avoid|without)\s+(?:\w+\s+){0,2}(?:rewrite|replace|rewriting|replacing)", goal, re.I))
        choice = self.simplicity.choose([
            {'id': 'extend-existing' if existing_sources else 'minimal-new-implementation', 'covers': ['preserve behavior'],
             'reuse': bool(existing_sources), 'complexity': 1, 'integration_risk': 1},
            {'id': 'replace-implementation' if existing_sources else 'new-framework', 'covers': ['preserve behavior'],
             'complexity': 4, 'maintenance': 2, 'integration_risk': 3}],
            ['preserve behavior'], confirmed='replace-implementation' if replacement and existing_sources else None)
        contract['decisions'].append({**choice, 'costs_are_heuristics': True,
            'existing_source_evidence': existing_sources[:8],
            'scope': 'Advisory strategy comparison; coverage is a proposal, not acceptance evidence.'})
        session = {'engine': self, 'contract': contract, 'guardian': guardian}
        token = CURRENT.set(session)
        try:
            self.persist(contract)
            if cancelled():
                raise ValueError('Coding cancelled before engineering admission.')
            if validation['needs_clarification'] and self.options['mode'] == 'enforced':
                from .clarification import TaskClarification
                raise TaskClarification(validation['question'])
            yield session
        except BaseException:
            contract['state'] = 'blocked'
            raise
        finally:
            try:
                blocked = contract['state'] == 'blocked'
                audit = guardian.audit(); contract['scope'] = audit
                verified_sources = contract.get('verified_sources', {})
                if verified_sources and any(not guardian.scoped(p).is_file() or
                        hashlib.sha256(guardian.scoped(p).read_bytes()).hexdigest() != digest
                        for p, digest in verified_sources.items()):
                    for criterion in ('behavior', 'regression'):
                        GoalAssurance.record(contract, criterion, method='source freshness recheck',
                            evidence='Source changed after executable validation; fresh checks required.', passed=False)
                GoalAssurance.record(contract, 'scope', method='bounded file hash comparison', evidence=json.dumps(audit), passed=audit['verified'])
                if blocked:
                    contract['state'] = 'blocked'
                self.persist(contract)
                if self.options['mode'] == 'enforced' and not blocked and contract['state'] != 'verified':
                    raise ValueError('Engineering acceptance is incomplete; inspect the recorded goal checks. No changes are replayed or undone.')
            finally:
                CURRENT.reset(token)

    def proposal(self, steps):
        active = CURRENT.get()
        if not active or active['engine'] is not self:
            return
        try:
            mapping = active['guardian'].propose(steps)
        except ValueError as error:
            if self.options['mode'] == 'enforced':
                raise
            active['contract'].setdefault('warnings', []).append(str(error)[:300])
            self.persist(active['contract'])
            return
        active['contract']['file_requirements'] = {**active['contract'].get('file_requirements', {}), **mapping}
        active['contract']['expected_artifacts'] = list(active['contract']['file_requirements'])[:100]
        self.persist(active['contract'])

    def review_source(self, name, before, after):
        active = CURRENT.get()
        if not active or active['engine'] is not self:
            return
        review = active['guardian'].inspect_content(before, after, Path(name).suffix)
        if Path(name).suffix == '.py':
            review['simplicity'] = self.simplicity.inspect_source(before, after, active['contract']['objective'])
        active['contract']['change_reviews'] = [r for r in active['contract'].get('change_reviews', []) if r['path'] != name][-19:] + [{'path': name, **review}]
        self.persist(active['contract'])

    def explain(self, question):
        patterns = {'assumptions': r'what assumptions did you make', 'scope': r'what exactly did you modify',
                    'checks': r'how do you know (?:the task|it) is complete',
                    'decisions': r'why did you choose that approach|is there a simpler solution'}
        field = next((k for k, p in patterns.items() if re.fullmatch(p + r'[?.! ]*', question, re.I)), None)
        if not self.enabled or not field:
            return None
        from .task_state import TaskState
        state = getattr(self.actions, 'task_state', None)
        snapshot = state.snapshot() if isinstance(state, TaskState) else None
        record = (snapshot or {}).get('engineering') or self.last
        if not record:
            return 'No engineering decision record is available for that task.'
        value = record.get('validation', {}).get('assumptions', []) if field == 'assumptions' else record.get(field, [])
        return 'Recorded goal ' + record['goal_id'] + ' (' + record['state'] + '): ' + json.dumps(value, ensure_ascii=False)[:3000]

    def project_contract(self, project, requirements):
        previous = project.get('engineering')
        if previous and previous.get('version') == project['version']:
            return previous
        validation = self.validation.evaluate(project['objective'], project.get('workspace'), requirements,
            {'purpose': project['objective'], 'conflicts': [r['text'] for r in requirements if r.get('status') == 'conflicting']})
        contract = GoalContractGenerator().create(project['objective'], project['id'], validation, project['version'])
        contract['constraints'] = [r['text'] for r in requirements if r.get('kind') == 'constraint']
        if previous:
            contract['supersedes'] = previous['goal_id']
            contract['decisions'].append({'reason': 'Requirement version changed; old verification does not establish the revised objective.'})
        return contract

    def assess_proposal(self, goal, *, evidence=(), active_goal=None):
        validation = self.validation.evaluate(goal)
        evidence = evidence if isinstance(evidence, (list, tuple)) else []
        verified = [r for r in evidence if isinstance(r, dict) and r.get('verified') is True and r.get('source')]
        return {'active_goal': active_goal, 'evidence_count': len(evidence),
                'verified_evidence_count': len(verified), 'requires_confirmation': bool(evidence and not verified),
                'supported': bool(verified and active_goal), 'validation': validation,
                'permission': 'Unchanged existing consent and tool policies; judgment never authorizes execution'}


def engine_for(actions):
    value = getattr(actions, 'engineering', None)
    return value if isinstance(value, EngineeringJudgmentEngine) and value.enabled else None


def proposed_file(root, name):
    """Called by the existing host FileSession immediately before checked writes."""
    active = CURRENT.get()
    if not active or Path(root).resolve() != active['guardian'].root:
        return
    path = Path(name)
    if path.is_absolute():
        name = path.resolve().relative_to(active['guardian'].root).as_posix()
    active['engine'].proposal([{'path': str(name).replace('\\', '/'),
        'reason': 'Proposed implementation of active objective: ' + active['contract']['objective'][:300]}])


def reviewed_file(root, name, before, after):
    active = CURRENT.get()
    if active and Path(root).resolve() == active['guardian'].root:
        active['engine'].review_source(name, before, after)


def verified_coding_checks(root, result, plan):
    """Bind existing independent executable-check results, never model claims."""
    active = CURRENT.get()
    if not active or Path(root).resolve() != active['guardian'].root:
        return
    contract = active['contract']
    passed = result.get('runtime_verified') is True and result.get('passed') is True and bool(result.get('checks'))
    hashes = result.get('hashes', {})
    passed = passed and bool(hashes) and all((Path(root) / name).is_file() and
        hashlib.sha256((Path(root) / name).read_bytes()).hexdigest() == digest for name, digest in hashes.items())
    contract['verified_sources'] = dict(list(hashes.items())[:160])
    for criterion in ('behavior', 'regression'):
        GoalAssurance.record(contract, criterion, method='existing validate_project executable checks',
            evidence=json.dumps(result)[:1500], passed=passed)
    contract['test_commands'] = [str(c)[:500] for c in (plan or {}).get('checks', [])[:20]]
    active['engine'].persist(contract)


def repair_budget(default):
    active = CURRENT.get()
    if active and active['engine'].options['mode'] == 'enforced':
        return min(default, active['engine'].options['max_repair_attempts'])
    return default


def learning_view(task):
    """Keep observations, but do not teach an unverified engineering goal as success."""
    record = task.get('engineering')
    if not record:
        return task
    criteria = record.get('acceptance', [])
    verified = (record.get('state') == 'verified' and bool(criteria) and
                all(r.get('verified') is True and r.get('evidence') for r in criteria) and
                record.get('scope', {}).get('verified') is True and bool(record.get('verified_sources')))
    if verified:
        if any(c.get('stage') == 'goal_verified' for c in task.get('checkpoints', [])):
            return task
        # Compatibility projection of already-recorded host proof, not a new verifier.
        return {**task, 'checkpoints': [*task.get('checkpoints', []), {'stage': 'goal_verified',
            'source': 'engineering_assurance', 'evidence': 'Executable acceptance and scope checks for goal ' + record['goal_id']} ]}
    return {**task, 'checkpoints': [c for c in task.get('checkpoints', []) if c.get('stage') != 'goal_verified'],
            'verification': [], 'engineering_learning_note': 'Unverified engineering outcome; retain observations, no successful-procedure promotion.'}
