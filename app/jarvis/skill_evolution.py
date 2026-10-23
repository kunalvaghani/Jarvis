"""Living skill evolution: outcome attribution, trust lifecycle and CAPTURED/FIX/DERIVED.

Design follows OpenSpace (HKUDS/OpenSpace, MIT; see integrations notes in the
Phase 3 audit): stable identities, provisional -> trusted only after independent
verified use, attributable failure demotes, FIX has exactly one parent, DERIVED
specializes a parent, CAPTURED records only verified steps with separate
validation evidence. This is an original Jarvis implementation, not vendored code.

Nothing here grants permissions. Mutated guides are written only under the
Jarvis-owned `.jarvis-runtime/skills/evolved/`; Builtins, Obsidian and upstream
guides are never rewritten (a FIX for them is recorded as a proposal). A model
may draft text, but a candidate is accepted only after schema validation, secret
screening and an independent execution through ToolRegistry whose verified
outcome rows are checked here.
"""
from datetime import datetime, timedelta, timezone
import difflib
import json
from pathlib import Path
import re
import shutil
import uuid

from .skill_store import content_hash

NAME = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')
FORBIDDEN_FRONTMATTER = frozenset({'allowed-tools', 'allowed_tools', 'disable-model-invocation', 'user-invocable',
                                   'model', 'effort', 'hooks', 'context', 'agent', 'shell', 'approved', 'permissions',
                                   'trusted', 'trust', 'trust_state', 'admin', 'role', 'authorization', 'approval',
                                   'preapproved', 'bypass_approval', 'user_approved', 'requires_approval'})
NON_ATTRIBUTABLE = frozenset({'permission_denied', 'cancelled', 'tool_unavailable', 'timeout'})
FIXTURE_SAFE_TOOLS = frozenset({'office_xlsx', 'office_docx', 'pdf_document', 'blender_task', 'unreal_task',
                                'execution_methods', 'strategy_execute', 'read_file', 'list_files', 'search_files'})


def evolved_root(base):
    return Path(base) / '.jarvis-runtime' / 'skills' / 'evolved'


# ---- ranking -------------------------------------------------------------------------------------------------------
def living_score(relevance, metrics, row):
    """Relevance-gated adjustment: evidence reorders relevant skills, never makes irrelevant ones appear."""
    if relevance <= 0:
        return relevance
    metrics = metrics or {}
    verified = metrics.get('completed_verified_count', 0)
    failed = metrics.get('failed_count', 0)
    fallback = metrics.get('fallback_count', 0)
    samples = verified + failed + fallback
    reliability = (verified + 1) / (verified + failed + .5 * fallback + 2)
    confidence = samples / (samples + 3)
    score = relevance + 1.6 * confidence * (reliability - .5)
    last = metrics.get('last_verified_at')
    if last:
        try:
            if datetime.now(timezone.utc) - datetime.fromisoformat(last) < timedelta(days=30):
                score += .2
        except ValueError:
            pass
    if row.get('trust_state') == 'provisional':
        score -= .3
    elif row.get('trust_state') == 'demoted':
        score -= 3
    from .tools import SPECS
    approval = {spec.name for spec in SPECS if spec.approval == 'user'}
    if approval & set(row.get('tools', [])):
        score -= .1  # Riskier guidance needs a little more relevance to win.
    score -= min(.2, len(row.get('body', '')) / 40000)  # Longer guidance costs more planner context.
    return round(score, 4)


# ---- outcome attribution -------------------------------------------------------------------------------------------
def classify_failure(text):
    text = str(text).casefold()
    for cause, pattern in (('permission_denied', r'approval|denied|permission|not authori'),
                           ('cancelled', r'cancel'), ('tool_unavailable', r'unavailable|not installed|not configured'),
                           ('timeout', r'timed out|timeout|deadline'),
                           ('uncertain_effect', r'uncertain|may have taken effect|inspect it before'),
                           ('control_not_found', r'not found|no (?:such|visible|named) (?:control|button|element)|could not find|cannot find'),
                           ('precondition_changed', r'unknown worksheet|changed|precondition|no longer|moved|renamed'),
                           ('verification_failed', r'verif|does not match|did not match|readback')):
        if re.search(pattern, text):
            return cause
    return 'other'


def task_actions(task):
    used = set()
    for step in (task.get('plan') or {}).get('completed', []) or []:
        if isinstance(step, dict) and step.get('action'):
            used.add(step['action'])
    for checkpoint in task.get('checkpoints', []) or []:
        if isinstance(checkpoint, dict) and checkpoint.get('stage') in {'acting', 'action_attempted', 'verified', 'observed'}:
            if checkpoint.get('action'):
                used.add(checkpoint['action'])
    return used


def finish_outcomes(store, catalog, task):
    """Idempotent per (task, skill, event). Skills without tool bindings cannot be attributed and get no event."""
    task_id = task.get('task_id')
    if not isinstance(task_id, str) or not task_id:
        return []
    selected = store.selected_for(task_id)
    if not selected:
        return []
    rows = {row.get('skill_id'): row for row in catalog}
    used = task_actions(task)
    evidence = [str(c.get('evidence', ''))[:300] for c in task.get('checkpoints', []) or []
                if isinstance(c, dict) and c.get('stage') == 'goal_verified']
    failures = task.get('failures') or []
    completed = task.get('status') == 'completed'
    written = []
    for skill_id in selected:
        row = rows.get(skill_id)
        if row is None or not row.get('tools'):
            continue
        applied = bool(set(row['tools']) & used)
        if not applied:
            if used:  # A different executed route is a fallback; selection without execution is selected only.
                written.append((skill_id, 'fallback', store.event(skill_id, 'fallback', task_id, {'reason': 'bound tools unused'})))
            continue
        written.append((skill_id, 'applied', store.event(skill_id, 'applied', task_id)))
        refuted = any(isinstance(step, dict) and step.get('action') in row['tools'] and step.get('verified') is False
                      for step in (task.get('plan') or {}).get('completed', []) or [])
        if refuted:
            written.append((skill_id, 'failed', store.event(skill_id, 'failed', task_id, {'cause': 'verification_failed'})))
            store.failure(skill_id, task_id, 'verification_failed')
        elif completed and evidence and not failures:
            written.append((skill_id, 'completed_verified', store.event(skill_id, 'completed_verified', task_id,
                                                                         {'evidence': evidence[:3]})))
        elif completed:
            written.append((skill_id, 'fallback', store.event(skill_id, 'fallback', task_id,
                                                              {'reason': 'recovered or unverified'})))
        else:
            reason = ' '.join(str(f.get('reason', '')) for f in failures if isinstance(f, dict)) or str(task.get('result', ''))
            cause = classify_failure(reason)
            written.append((skill_id, 'failed', store.event(skill_id, 'failed', task_id, {'cause': cause})))
            store.failure(skill_id, task_id, cause, reason[:300])
        update_trust(store, skill_id)
    return written


def update_trust(store, skill_id):
    """Deterministic in the evidence since the active version: same evidence, same state.

    Imported guides are trusted unless their two latest attributable outcomes failed.
    Evolved guides become trusted after verified use in two tasks other than their source,
    are demoted when their latest outcome is an attributable failure, else stay provisional.
    """
    record = store.record(skill_id)
    if not record:
        return None
    metrics = store.metrics(skill_id, current_version=True)
    recent = metrics['recent_outcomes']
    attributable = bool(set(metrics['failure_causes']) - NON_ATTRIBUTABLE)
    if record['lineage_origin'] == 'imported':
        state = 'provisional' if recent[:2] == ['failed', 'failed'] and attributable else 'trusted'
    else:
        verified_tasks = set(store.tasks_with(skill_id, 'completed_verified', current_version=True)) - {record.get('source_task_id')}
        if recent and recent[0] == 'failed' and attributable:
            state = 'demoted'
        elif len(verified_tasks) >= 2 and (not recent or recent[0] == 'completed_verified'):
            state = 'trusted'
        else:
            state = 'provisional'
    if state != record['trust_state']:
        store.set_state(skill_id, trust_state=state)
    return state


def degraded(store, skill_id):
    """A previously working skill whose two latest attributable outcomes (this version) failed."""
    lifetime = store.metrics(skill_id)
    metrics = store.metrics(skill_id, current_version=True)
    causes = set(metrics['failure_causes']) - NON_ATTRIBUTABLE
    return (lifetime['completed_verified_count'] >= 1 and metrics['recent_outcomes'][:2] == ['failed', 'failed']
            and bool(causes)), metrics


# ---- validation ----------------------------------------------------------------------------------------------------
def frontmatter(body):
    match = re.match(r'---\n(.*?)\n---\n', body, re.S)
    if not match:
        raise ValueError('SKILL.md needs a front matter block.')
    fields = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(':')
        if not sep or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,40}', key.strip()):
            raise ValueError('Malformed front matter line.')
        fields[key.strip()] = value.strip()
    return fields


def validate_skill(body, expected_name=None):
    """Deterministic schema, policy and secret checks (independent of any model claim)."""
    from .obsidian_memory import SENSITIVE
    from .tools import TOOL_NAMES, redact
    if not isinstance(body, str) or not 50 <= len(body.encode('utf-8')) <= 8000:
        raise ValueError('Evolved SKILL.md must be 50-8000 bytes.')
    fields = frontmatter(body)
    forbidden = sorted(set(fields) & FORBIDDEN_FRONTMATTER)
    if forbidden:
        raise ValueError('Forbidden front matter: ' + ', '.join(forbidden))
    name = fields.get('name', '')
    if not NAME.fullmatch(name) or len(name) > 50 or (expected_name and name != expected_name):
        raise ValueError('Skill name must be a safe lowercase slug matching its folder.')
    if not 10 <= len(fields.get('description', '')) <= 300:
        raise ValueError('Description must be one line of 10-300 characters.')
    tools = re.fullmatch(r'\[([a-z0-9_, ]*)\]', fields.get('tools', '[]'))
    if tools is None:
        raise ValueError('tools must be a bracketed list.')
    declared = [t.strip() for t in tools.group(1).split(',') if t.strip()]
    unknown = [t for t in declared if t not in TOOL_NAMES]
    if unknown:
        raise ValueError('Unregistered tools cannot be bound: ' + ', '.join(unknown))
    if redact(body) != body or SENSITIVE.search(body):
        raise ValueError('Candidate contains credential-like or sensitive content.')
    if re.search(r'(?i)\b(?:ignore (?:all|previous) (?:rules|instructions)|approval (?:is )?(?:granted|not required)|'
                 r'skip (?:the )?approval|run without (?:asking|approval))\b', body):
        raise ValueError('Guidance may not claim or waive approval.')
    return {'name': name, 'tools': declared, 'fields': fields}


def verify_execution(registry, steps, cancelled=lambda: False):
    """Run a candidate procedure through ToolRegistry; every step must report independent verification."""
    from .execution_contracts import read_outcomes
    if not steps or len(steps) > 12:
        raise ValueError('Validation needs 1-12 steps.')
    if any(step.get('action') not in FIXTURE_SAFE_TOOLS for step in steps):
        raise ValueError('Only fixture-safe adapters can validate automatically; candidate kept for review.')
    receipts = []
    for step in steps:
        result = registry.execute(dict(step), cancelled)
        try:
            data = json.loads(result.evidence)
        except ValueError:
            data = {}
        outcome = [r for r in read_outcomes(registry.actions.base, 200)
                   if r.get('call_id') == result.call_id and r.get('tool') == step['action']]
        # A tool's own success/verification text cannot override or replace correlated host readback.
        verified = bool(outcome and outcome[-1].get('verification') == 'verified')
        receipts.append({'action': step['action'], 'call_id': result.call_id, 'verified': bool(verified),
                         'data': {k: v for k, v in data.items() if k in {'version', 'blender_version', 'sheets', 'pages'}}})
        if not verified:
            raise ValueError('Validation step was not independently verified: ' + step['action'])
    return receipts


# ---- writing -------------------------------------------------------------------------------------------------------
def _write_skill(base, name, body, provenance, replace=False):
    """Atomic directory publish; FIX replaces only the SKILL.md of an evolved skill."""
    root = evolved_root(base)
    root.mkdir(parents=True, exist_ok=True)
    folder = root / name
    if replace:
        if not folder.is_dir():
            raise ValueError('FIX target is not an evolved skill folder.')
        temporary = folder / ('.SKILL.md.' + uuid.uuid4().hex[:8])
        temporary.write_text(body, encoding='utf-8')
        temporary.replace(folder / 'SKILL.md')
        history = folder / 'provenance.json'
        rows = json.loads(history.read_text(encoding='utf-8')) if history.is_file() else []
        rows = rows if isinstance(rows, list) else [rows]
        history.write_text(json.dumps(rows + [provenance], indent=1, default=str), encoding='utf-8')
        return folder
    if folder.exists():
        raise ValueError('An evolved skill with this name already exists.')
    staging = root / ('.staging-' + uuid.uuid4().hex[:8])
    staging.mkdir()
    try:
        (staging / 'SKILL.md').write_text(body, encoding='utf-8')
        (staging / 'provenance.json').write_text(json.dumps([provenance], indent=1, default=str), encoding='utf-8')
        staging.rename(folder)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return folder


def _slug(text, limit=40):
    slug = re.sub(r'[^a-z0-9]+', '-', str(text).casefold()).strip('-')
    return '-'.join(slug.split('-')[:6])[:limit].strip('-') or 'workflow'


class SkillEvolution:
    """CAPTURED / FIX / DERIVED with validation, provenance, versions and rollback.

    `author(kind, context) -> str` drafts guidance (the local model in production);
    its output is untrusted until validate_skill and verify_execution pass.
    """

    def __init__(self, skills, registry, author=None, mode='autonomous'):
        if mode not in {'audit_only', 'fix_only', 'autonomous'}:
            raise ValueError('Unknown evolution mode.')
        self.skills, self.registry, self.author, self.mode = skills, registry, author, mode
        self.base = Path(skills.memory.base)

    def _store(self):
        self.skills.refresh()
        if self.skills.store is None:
            raise ValueError('Skill store unavailable: ' + str(self.skills.living_error))
        return self.skills.store

    def _catalog_row(self, skill_id):
        return next((row for row in self.skills.catalog if row.get('skill_id') == skill_id), None)

    def _allowed(self, kind):
        if self.mode == 'audit_only' or (self.mode == 'fix_only' and kind != 'fix'):
            raise ValueError('Evolution mode ' + self.mode + ' records ' + kind + ' as a candidate only.')

    def _engineering_guidance(self):
        from .engineering_judgment import GUIDANCE, settings
        return {'engineering_guidance': GUIDANCE} if settings(getattr(self.skills.memory, 'engineering_options', {}))['enabled'] else {}

    # CAPTURED ---------------------------------------------------------------------------------------------------------
    def capture(self, task, trace, validation_steps, cancelled=lambda: False):
        """trace: [{action, value, folder, content, call_id, verified}] from a finished task (failed steps included)."""
        self._allowed('captured')
        self._store()  # refresh catalog; fails closed when the store is unavailable
        if task.get('status') != 'completed':
            raise ValueError('Only a completed task can be captured.')
        from .execution_contracts import read_outcomes
        outcomes = {r['call_id']: r for r in read_outcomes(self.base, 2000)}
        kept, removed = [], 0
        for step in trace:
            outcome = outcomes.get(step.get('call_id'))
            if step.get('verified') is True and outcome and outcome.get('verification') == 'verified':
                if not any(k['action'] == step['action'] and k.get('content') == step.get('content') for k in kept):
                    kept.append(step)
                    continue
            removed += 1  # failed, unverified, uncorrelated or duplicate exploration
        if not kept:
            raise ValueError('No independently verified steps to capture.')
        best = max((s['skill'] for s in self._existing_matches(task.get('goal', ''))), default=0)
        if best >= 3:
            raise ValueError('An existing skill already covers this workflow; consider DERIVED instead.')
        name = 'captured-' + _slug(task.get('goal', ''))
        tools = sorted({step['action'] for step in kept})
        lines = []
        for number, step in enumerate(kept, 1):
            try:
                operation = json.loads(step.get('content') or '{}').get('operation', '')
            except (ValueError, AttributeError):
                operation = ''
            lines.append(f'{number}. `{step["action"]}`' + (f' with operation `{operation}`' if operation else '') +
                         ' on the file or target named in the new request.')
        description = ('Verified workflow captured from a completed task: ' + _slug(task.get('goal', ''), 80).replace('-', ' '))[:300]
        body = (f'---\nname: {name}\ndescription: {description}\ntools: [{", ".join(tools)}]\n---\n\n'
                f'# Captured workflow (provisional)\n\nOrigin: CAPTURED from task {task.get("task_id", "")[:12]}. '
                'Only steps with independent verification were kept; failed exploration was removed.\n\n'
                'Preconditions: the target named in the request exists in the folder the user identified; '
                'writes still require approval.\n\n## Steps\n\n' + '\n'.join(lines) +
                '\n\n## Verification\n\nEach step must return verification `verified` from its adapter readback.\n')
        if self.author is not None:
            drafted = self.author('captured', {'goal': task.get('goal'), 'steps': lines, 'name': name, 'tools': tools, **self._engineering_guidance()})
            if isinstance(drafted, str) and drafted.strip():
                body = drafted
        validate_skill(body, name)
        receipts = verify_execution(self.registry, validation_steps, cancelled)
        provenance = {'origin': 'captured', 'at': datetime.now(timezone.utc).isoformat(), 'source_task_id': task.get('task_id'),
                      'procedure_refs': [s['call_id'] for s in kept], 'validation_refs': [r['call_id'] for r in receipts],
                      'removed_steps': removed, 'body_sha256': content_hash(body)}
        folder = _write_skill(self.base, name, body, provenance)
        return self._register(folder, 'captured', [], 0, 'Captured from task ' + str(task.get('task_id', ''))[:32],
                              task.get('task_id'), provenance)

    def _existing_matches(self, goal):
        from .capabilities import skill_score, skill_ranking
        ranking = skill_ranking(goal)
        return [{'name': row['name'], 'skill': skill_score(row, goal, ranking)} for row in self.skills.catalog]

    def _register(self, folder, origin, parents, generation, summary, source_task, provenance):
        self.skills._guide_stamp = None
        self.skills.refresh()
        row = next((r for r in self.skills.catalog if r['origin'] == 'Evolved' and r['name'] == folder.name), None)
        if row is None or not row.get('skill_id'):
            shutil.rmtree(folder, ignore_errors=True)
            raise ValueError('Evolved skill did not load; candidate removed. ' + '; '.join(self.skills.skill_errors[-2:]))
        store = self.skills.store
        store.add_lineage(row['skill_id'], origin, parents, generation, summary)
        store.set_state(row['skill_id'], trust_state='provisional')
        if source_task:
            store.set_source_task(row['skill_id'], source_task)
        row['trust_state'] = 'provisional'
        return {'skill_id': row['skill_id'], 'name': row['name'], 'origin': origin, 'trust_state': 'provisional',
                'provenance': provenance}

    # FIX --------------------------------------------------------------------------------------------------------------
    def fix(self, skill_id, observation, validation_steps, cancelled=lambda: False):
        """observation: fresh evidence of changed DOM/UIA/API behaviour (e.g. current control or sheet names)."""
        self._allowed('fix')
        store = self._store()
        row = self._catalog_row(skill_id)
        if row is None:
            raise ValueError('Unknown skill.')
        is_degraded, metrics = degraded(store, skill_id)
        if not is_degraded:
            raise ValueError('Skill is not degraded; FIX needs repeated attributable failures after earlier success.')
        if self.author is None:
            raise ValueError('FIX needs an author to draft a repair.')
        drafted = self.author('fix', {'body': row['body'], 'failure_causes': metrics['failure_causes'], **self._engineering_guidance(),
                                      'observation': observation})
        validate_skill(drafted, row['name'])
        old_lines, new_lines = row['body'].splitlines(), drafted.splitlines()
        diff = '\n'.join(difflib.unified_diff(old_lines, new_lines, 'before', 'after', lineterm=''))
        changed = sum(1 for line in diff.splitlines() if line[:1] in '+-' and not line.startswith(('+++', '---')))
        engineering = bool(self._engineering_guidance())
        if changed == 0 or (changed > max(6, len(old_lines) // 2) and not engineering):
            raise ValueError('Repair is not minimal (changed lines: ' + str(changed) + ').')
        if engineering and not observation:
            raise ValueError('An engineering FIX needs an observed defect, not a speculative rewrite.')
        if set(validate_skill(drafted)['tools']) - set(row.get('tools', [])):
            raise ValueError('A FIX may not bind new tools; use DERIVED with review.')
        version, previous = store.add_version(skill_id, drafted, diff, 'candidate', {'observation': observation,
            **({'engineering_review': {'changed_lines': changed, 'size_is_diagnostic_only': True,
                'scope': 'Observed repair; no new tool bindings; existing isolated execution checks still required'}} if engineering else {})})
        if row['origin'] != 'Evolved':
            store.mark_version(skill_id, version, 'proposed')
            return {'skill_id': skill_id, 'status': 'proposed', 'version': version,
                    'reason': row['origin'] + ' guides are not rewritten automatically; review the proposed diff.', 'diff': diff}
        try:
            receipts = verify_execution(self.registry, validation_steps, cancelled)
        except Exception:
            store.mark_version(skill_id, version, 'rejected')
            raise
        folder = evolved_root(self.base) / row['name']
        backup = (folder / 'SKILL.md').read_text(encoding='utf-8')
        try:
            _write_skill(self.base, row['name'], drafted, {'origin': 'fixed', 'version': version, 'previous_version': previous,
                                                           'validation_refs': [r['call_id'] for r in receipts],
                                                           'at': datetime.now(timezone.utc).isoformat()}, replace=True)
            self.skills._guide_stamp = None
            self.skills.refresh()
            store.activate_version(skill_id, version)
            store.new_epoch(skill_id)
        except BaseException:
            (folder / 'SKILL.md').write_text(backup, encoding='utf-8')  # restore the previous working guide
            store.mark_version(skill_id, version, 'rejected')
            raise
        store.add_lineage(skill_id, 'fixed', [f'{skill_id}@v{previous}'], (store.record(skill_id) or {}).get('lineage_generation', 0) + 1,
                          'Repaired after: ' + ', '.join(sorted(metrics['failure_causes'])))
        store.set_state(skill_id, trust_state='provisional', enabled=True)
        return {'skill_id': skill_id, 'status': 'fixed', 'version': version, 'previous_version': previous,
                'diff': diff, 'validation': receipts}

    def rollback(self, skill_id, version):
        store = self._store()
        row = self._catalog_row(skill_id)
        if row is None or row['origin'] != 'Evolved':
            raise ValueError('Only evolved skills are rolled back automatically.')
        target = store.activate_version(skill_id, version)
        store.new_epoch(skill_id)
        _write_skill(self.base, row['name'], target['body'], {'origin': 'rollback', 'version': version,
                                                               'at': datetime.now(timezone.utc).isoformat()}, replace=True)
        self.skills._guide_stamp = None
        self.skills.refresh()
        return {'skill_id': skill_id, 'active_version': version}

    # DERIVED ----------------------------------------------------------------------------------------------------------
    def derive(self, skill_id, specialization, validation_steps, cancelled=lambda: False):
        """specialization: {application, version, preconditions[], notes[]}; the parent stays unchanged."""
        self._allowed('derived')
        store = self._store()
        parent = self._catalog_row(skill_id)
        if parent is None:
            raise ValueError('Unknown parent skill.')
        application = _slug(specialization.get('application', ''), 20)
        version = re.sub(r'[^0-9.]', '', str(specialization.get('version', '')))[:12]
        if not application or not version:
            raise ValueError('DERIVED needs an application and version.')
        name = (parent['name'][:30].rstrip('-') + '-' + application + '-' + version.replace('.', '-'))[:50].strip('-')
        preconditions = [str(p)[:200] for p in specialization.get('preconditions', [])][:6]
        notes = [str(n)[:300] for n in specialization.get('notes', [])][:8]
        body = (f'---\nname: {name}\ndescription: Specializes {parent["name"]} for {application} {version}; '
                f'use only when these preconditions hold.\ntools: [{", ".join(parent.get("tools", []))}]\n---\n\n'
                f'# {parent["name"]} for {application} {version} (provisional)\n\nOrigin: DERIVED from `{parent["name"]}` '
                f'({skill_id}). Follow the parent guidance; this file lists only the differences.\n\n## Preconditions\n\n' +
                '\n'.join('- ' + p for p in [f'{application} version is {version}'] + preconditions) +
                '\n\n## Differences from the parent\n\n' + ('\n'.join('- ' + n for n in notes) or '- None beyond the preconditions.') + '\n')
        if self.author is not None:
            drafted = self.author('derived', {'parent': parent['body'], 'name': name, 'specialization': specialization, **self._engineering_guidance()})
            if isinstance(drafted, str) and drafted.strip():
                body = drafted
        validate_skill(body, name)
        if len(body) > len(parent['body']) + 2000 and parent['body'].strip() in body:
            raise ValueError('DERIVED must not copy the whole parent guide.')
        receipts = verify_execution(self.registry, validation_steps, cancelled)
        reported = [str(r['data'].get(key, '')) for r in receipts for key in ('blender_version', 'version')]
        if not any(value == version or value.startswith(version + '.') for value in reported):
            raise ValueError('Validation did not observe ' + application + ' ' + version + '; precondition unproven.')
        provenance = {'origin': 'derived', 'parent': skill_id, 'application': application, 'version': version,
                      'validation_refs': [r['call_id'] for r in receipts], 'at': datetime.now(timezone.utc).isoformat()}
        folder = _write_skill(self.base, name, body, provenance)
        parent_generation = (store.record(skill_id) or {}).get('lineage_generation', 0)
        result = self._register(folder, 'derived', [skill_id], parent_generation + 1,
                                f'Specialized for {application} {version}', None, provenance)
        store.set_state(result['skill_id'], compatibility={'application': application, 'version': version})
        return result
