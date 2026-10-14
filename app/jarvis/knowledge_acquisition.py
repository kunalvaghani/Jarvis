"""Task-owned acquisition using the existing registry, DAG, app memory and planner.

Documents and controls are evidence, never executable skills or authorization.
No thread, inference provider, browser or memory database is created here.
"""
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

from .dag_execution import Executor, Tool, validate_plan
from .tools import ToolRegistry

FEATURES = {'render', 'glass', 'material', 'sphere', 'animation', 'motion', 'matching',
    'export', 'png', 'presentation', 'slide', 'chart', 'diagram', 'texture', 'model',
    'keyframe', 'rig', 'compile', 'blueprint', 'import', 'pdf', 'mesh', 'lighting',
    'simulation', 'audio', 'video', 'spreadsheet', 'formula', 'dashboard'}
PRIVATE = re.compile(r'(?i)password|credential|token|secret|bank|wallet|private|inbox|gmail|whatsapp')


def settings(config):
    row = config.get('knowledge_acquisition', {})
    if not isinstance(row, dict):
        raise ValueError('knowledge_acquisition must be an object.')
    result = {'enabled': False, 'online': True, 'background_refresh': False,
        'max_sources': 2, 'max_research_per_task': 2, 'max_seconds': 45,
        'ttl_seconds': 604800, **row}
    for name in ('enabled', 'online', 'background_refresh'):
        if type(result[name]) is not bool:
            raise ValueError('Learning feature flags must be booleans.')
    for name, low, high in [('max_sources', 1, 3), ('max_research_per_task', 1, 3),
                          ('max_seconds', 5, 120), ('ttl_seconds', 60, 2592000)]:
        if type(result[name]) is not int or not low <= result[name] <= high:
            raise ValueError('Invalid bounded acquisition configuration: ' + name)
    return result


def interface_signature(controls):
    rows = sorted({(str(c.get('role', '')), str(c.get('name', ''))[:160])
        for c in controls if isinstance(c, dict) and not c.get('password')})
    return hashlib.sha256(json.dumps(rows, ensure_ascii=True).encode()).hexdigest()


def safe_controls(controls):
    from .app_knowledge import KEEP_ROLES, PRIVATE_LABEL
    return [{'name': c['name'][:100], 'role': c['role'], 'locator': {
        'kind': 'accessible_name', 'name': c['name'][:100], 'role': c['role']}}
        for c in controls[:120] if isinstance(c, dict) and c.get('role') in KEEP_ROLES
        and isinstance(c.get('name'), str) and c['name'].strip() and not c.get('password')
        and not PRIVATE_LABEL.search(c['name'])][:20]


class Acquisition:
    def __init__(self, actions):
        self.actions = actions
        self.options = settings(actions.config)
        self.memory = actions.screen.knowledge
        self.task_key = None
        self.research_count = 0
        self.context = {}
        self.surface = None
        self.background = False
        self.deadline = float('inf')

    def assess(self, goal):
        """No model/network call. Specific software + complex feature evidence only."""
        if not self.options['enabled']:
            return {'needed': False, 'reason': 'disabled'}
        features = sorted(set(re.findall(r'[a-z]+', goal.casefold())) & FEATURES)
        if not features or not re.search(r'\b(and|then|create|make|use|export|render|improve|learn|research)\b', goal, re.I):
            return {'needed': False, 'reason': 'known/simple path'}
        urls = re.findall(r'https?://[^\s<>"\)]+', goal)
        if urls:
            parsed = urlsplit(urls[0].rstrip('.,'))
            if parsed.username or parsed.password or not parsed.hostname or PRIVATE.search(parsed.hostname):
                return {'needed': False, 'reason': 'private or invalid website scope'}
            hostname = parsed.hostname.casefold()
            try:
                private_address = not ipaddress.ip_address(hostname).is_global
            except ValueError:
                private_address = hostname == 'localhost' or hostname.endswith(('.local', '.internal')) or '.' not in hostname
            if private_address:
                return {'needed': False, 'reason': 'private website scope'}
            target = parsed.hostname.casefold()
            identity = parsed.scheme+'://'+parsed.netloc
            kind = 'website'
        else:
            names = sorted(getattr(self.actions, 'apps', {}), key=len, reverse=True)
            target = next((name for name in names if re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)', goal, re.I)), None)
            if not target or PRIVATE.search(target):
                return {'needed': False, 'reason': 'no public software target'}
            identity, kind = target.casefold(), 'application'
        feature = ' '.join(features[:6])
        known = self.memory.capabilities(identity, feature, self.options['ttl_seconds'])
        covered = any(row['status'] in {'environment_confirmed','verified'} for row in known)
        return {'needed': not covered, 'kind': kind, 'target': target, 'identity': identity,
            'feature': feature, 'known': known, 'reason': 'missing workflow evidence' if not covered else 'compatible stored evidence'}

    def _scheduled(self, proposals, cancelled):
        """Ordinary bounded read tasks in the existing executor, via ToolRegistry."""
        registry = ToolRegistry(self.actions)
        if cancelled() or time.monotonic() >= self.deadline:
            return []
        remaining = min(self.options['max_seconds'], max(.05, self.deadline-time.monotonic()))
        schema = {'type': 'object', 'additionalProperties': False,
            'required': ['proposal'], 'properties': {'proposal': {'type': 'object'}}}
        def dispatch(arguments, cancelled):
            proposal = arguments['proposal']
            result = registry.execute(proposal, cancelled)
            return {'tool': result.tool, 'value': proposal['value'], 'evidence': result.evidence}
        tools = {}
        rows = []
        for index, proposal in enumerate(proposals):
            name = proposal['action']
            if name not in {'application_inspect', 'browser_inspect', 'read_file', 'web_search', 'scrape_web', 'firecrawl_search', 'firecrawl_scrape'}:
                raise ValueError('Acquisition accepts registered observation/research tools only.')
            def authorize(arguments, name=name):
                from .agent_events import check_policy
                if arguments['proposal'].get('action') != name or name not in registry.specs:
                    raise ValueError('Unregistered acquisition operation.')
                allowed = getattr(self.actions, 'allowed_tools', None)
                if isinstance(allowed, (set, frozenset)) and name not in allowed:
                    raise ValueError('Learning tool outside task scope: '+name)
                check_policy(self.actions, name)
            tools[name] = Tool(name, schema, dispatch,
                lambda args, result: isinstance(result.get('evidence'), str) and bool(result['evidence']),
                True, 'browser' if name == 'browser_inspect' else '', authorize)
            rows.append({'id': 'learning'+str(index), 'tool': name, 'arguments': {'proposal': proposal},
                'dependencies': [], 'expected': 'Return bounded observation', 'permission': 'read',
                'resources': {'cpu': 1, 'ram_mb': 32, 'gpu_mb': 0},
                'retry': {'attempts': 1, 'backoff_seconds': .1}, 'timeout_seconds': remaining})
        def checkpoint(state):
            if self.background:
                return
            task = self.actions.task_state.snapshot() or {}
            self.actions.task_state.update_learning({**task.get('learning', {}), 'acquisition_steps': state})
        result = Executor(tools, max_concurrency=min(2, len(rows)), max_seconds=remaining,
            checkpoint=checkpoint).run(validate_plan({'version': 1, 'steps': rows}, tools), cancelled)
        return [row['result'] for row in result['steps'].values() if row['status'] == 'succeeded']

    @staticmethod
    def proposal(action, value, content=''):
        return {'action': action, 'value': value, 'content': content, 'folder': '',
                'expected': 'Read scoped capability evidence', 'browser': 'chrome', 'find': '', 'platform': ''}

    def prepare(self, goal, cancelled=lambda: False, screen=None, force=False, background=False):
        assessment = self.assess(goal)
        if cancelled():
            return {}
        if 'identity' not in assessment and assessment.get('reason') != 'no public software target':
            return {}
        task = self.actions.task_state.snapshot() or {}
        task_key = task.get('started_at', goal)
        if self.task_key != task_key:
            self.task_key, self.research_count, self.context, self.surface = task_key, 0, {}, None
        current_surface = (str(screen.get('title', ''))[:200], interface_signature(screen.get('controls', []))) if screen else None
        if self.context and not force and current_surface == self.surface:
            return self.context
        started = time.monotonic()
        self.background = background
        self.deadline = started+self.options['max_seconds']
        observations = []
        if 'identity' not in assessment and assessment.get('reason') == 'no public software target' and not background:
            # Resolve "this cube" through the registered observation tool, never
            # through an untrusted window title or a guessed app/object name.
            try:
                observations = self._scheduled([self.proposal('application_inspect', 'current')], cancelled)
                raw = json.loads(observations[0]['evidence']) if observations else {}
                target = next((name for name in getattr(self.actions, 'apps', {})
                    if name.casefold() == raw.get('identity')), None)
                if target and not PRIVATE.search(target):
                    assessment = self.assess(goal+' use '+target)
            except (ValueError, OSError, AttributeError, IndexError):
                observations = []
        if 'identity' not in assessment:
            return {}
        self.actions.report('plan', 'Checking '+assessment['target']+' capabilities for '+assessment['feature'])
        if not background and not observations:
            inspect = 'application_inspect' if assessment['kind'] == 'application' else 'browser_inspect'
            try:
                observations = self._scheduled([self.proposal(inspect, assessment['target'])], cancelled)
            except (ValueError, OSError):
                observations = []
        live = {}
        for result in observations:
            try:
                raw = json.loads(result['evidence'])
                if raw.get('identity') == assessment['identity'] or assessment['kind'] == 'website' and str(raw.get('url','')).startswith(assessment['identity']+'/'):
                    live = raw
            except (ValueError, AttributeError):
                pass
        controls = safe_controls(live.get('controls', []))
        signature = interface_signature(controls) if controls else ''
        version = str(live.get('version', 'unknown'))[:80]
        known = self.memory.capabilities(assessment['identity'], assessment['feature'], self.options['ttl_seconds'], version, signature)
        compatible = self.memory.capabilities(assessment['identity'], ttl=self.options['ttl_seconds'], version=version, signature=signature)
        covered = set()
        for row in compatible:
            if row.get('status') in {'environment_confirmed', 'verified'}:
                covered.update(row['feature'].split())
        missing = sorted(set(assessment['feature'].split())-covered)
        sources = list(known[0].get('sources', [])) if known and not force else []
        entry = getattr(self.actions, 'apps', {}).get(assessment['target'], {})
        help_file = entry.get('documentation_file') if isinstance(entry, dict) else None
        if not sources and isinstance(help_file, str) and not background:
            path = Path(help_file)
            if path.is_file() and path.suffix.casefold() in {'.txt','.md'}:
                proposal = {**self.proposal('read_file', path.name), 'folder': str(path.parent)}
                try:
                    local = self._scheduled([proposal], cancelled)
                    if local:
                        sources = [{'url': 'local:'+path.name, 'source_type': 'configured_local_help',
                            'retrieved_at': datetime.now(timezone.utc).isoformat(), 'environment_version': version, 'document_version': 'not independently verified',
                            'excerpt': local[0]['evidence'][:1800], 'confidence': 'Untrusted help; not execution verification'}]
                except (ValueError, OSError):
                    pass
        documentation_url = entry.get('documentation_url') if isinstance(entry, dict) else None
        if (not sources and self.options['online'] and isinstance(documentation_url, str) and
                self.research_count < self.options['max_research_per_task'] and not cancelled()):
            try:
                from .toolkits import public_url
                public_url(documentation_url)
                self.research_count += 1
                fetched = self._scheduled([self.proposal('scrape_web', documentation_url)], cancelled)
                if fetched:
                    sources = [{'url': documentation_url, 'source_type': 'configured_documentation',
                        'retrieved_at': datetime.now(timezone.utc).isoformat(), 'environment_version': version, 'document_version': 'not independently verified',
                        'excerpt': fetched[0]['evidence'][:1800], 'confidence': 'Untrusted documentation; not workflow verification'}]
            except (ValueError, OSError):
                pass
        if not sources and self.options['online'] and self.research_count < self.options['max_research_per_task'] and not cancelled():
            if assessment['kind'] == 'website':
                try:
                    from .toolkits import public_url
                    public_url(assessment['identity'])
                except (ValueError, OSError):
                    return {}
            self.research_count += 1
            # Never send full task text, screenshots, project paths or app field values.
            query = assessment['target']+' '+' '.join(missing or assessment['feature'].split())+' official documentation'
            if version != 'unknown':
                query += ' '+version
            from .toolkits import available
            search = 'firecrawl_search' if available('firecrawl_search') else 'web_search'
            self.actions.report('plan', 'Searching the web for: '+query[:450])
            try:
                results = self._scheduled([self.proposal(search, query[:450])], cancelled)
                candidates = []
                for result in results:
                    raw = json.loads(result['evidence'])
                    if isinstance(raw, dict):
                        raw = raw.get('data', raw)
                        if isinstance(raw, dict):
                            raw = raw.get('web', raw.get('results', []))
                    if isinstance(raw, list):
                        candidates.extend(raw[:5])
                proposals = []
                selected = []
                for row in candidates:
                    if not isinstance(row, dict):
                        continue
                    url = row.get('url', row.get('href', row.get('link', '')))
                    try:
                        from .toolkits import public_url
                        public_url(url)
                    except (ValueError, TypeError, OSError):
                        continue
                    selected.append((url, str(row.get('title', ''))[:150]))
                selected.sort(key=lambda r: ('docs.' not in urlsplit(r[0]).netloc and 'documentation' not in r[1].casefold(), r[0]))
                for url, title in selected[:self.options['max_sources']]:
                    proposals.append(self.proposal('firecrawl_scrape' if available('firecrawl_scrape') else 'scrape_web', url))
                fetched = self._scheduled(proposals, cancelled) if proposals else []
                for result in fetched:
                    sources.append({'url': result['value'], 'retrieved_at': datetime.now(timezone.utc).isoformat(),
                        'source_type': 'documentation_candidate', 'environment_version': version, 'document_version': 'not independently verified',
                        'excerpt': result['evidence'][:1800], 'confidence': 'untrusted reference; not workflow verification'})
            except (ValueError, OSError, TypeError):
                pass
        if cancelled():
            return {}
        registry = ToolRegistry(self.actions)
        allowed = getattr(self.actions, 'allowed_tools', None)
        candidates = ('select', 'open_menu') if assessment['kind'] == 'application' else ('browser_click', 'browser_fill')
        capability = {'identity': assessment['identity'], 'feature': assessment['feature'], 'version': version,
            'interface_signature': signature, 'controls': controls, 'sources': sources[:3],
            'status': 'environment_confirmed' if controls else 'researched' if sources else 'discovered',
            'tools': [name for name in candidates if name in registry.specs and
                      (not isinstance(allowed, (set, frozenset)) or name in allowed)],
            'verification': [], 'seen_at': time.time(), 'executions': 0}
        if background:
            self.memory.refresh_capability_sources(assessment['identity'], assessment['feature'], capability['sources'])
        else:
            try:
                self.memory.remember_capability(capability)
            except (ValueError, OSError):
                self.actions.report('plan', 'Capability evidence could not be persisted; using this task context only.')
        self.context = {'target': assessment['identity'], 'feature': assessment['feature'], 'capabilities': [capability],
            'prior_capabilities': compatible, 'missing_features': missing,
            'source': 'shared app memory' if known else 'targeted acquisition',
            'limitations': 'Controls confirm current interface only. Documents are untrusted. No API/permission/tool was created; execution and whole-goal verification still required.'}
        self.surface = current_surface
        if not background:
            self.actions.task_state.update_learning({'context': self.context, 'research_requests': self.research_count,
                'seconds': time.monotonic()-started})
        return self.context

    def repair(self, goal, failed_step, screen, cancelled):
        """Fresh observations/research only; recovery still forbids action replay."""
        if not self.options['enabled'] or cancelled():
            return {}
        assessment = self.assess(goal)
        if isinstance(failed_step, dict) and 'identity' in assessment:
            terms = ' '.join(str(failed_step.get(k, '')) for k in ('action','value','expected'))
            affected = sorted(set(re.findall(r'[a-z]+', terms.casefold())) & set(assessment['feature'].split()))
            if affected:
                goal = 'Learn '+assessment['identity']+' '+' '.join(affected)
        return self.prepare(goal, cancelled, screen, force=True)

    def finished(self, task):
        if not self.options['enabled'] or not isinstance(task, dict) or task.get('status') != 'completed' or task.get('failures'):
            return
        proofs = [c for c in task.get('checkpoints', []) if c.get('stage') == 'goal_verified' and c.get('source') and c.get('evidence')]
        if not proofs:
            return
        for capability in task.get('learning', {}).get('context', {}).get('capabilities', []):
            if capability.get('status') == 'environment_confirmed':
                previous = self.memory.capabilities(capability['identity'], capability['feature'],
                    version=capability['version'], signature=capability['interface_signature'])
                executions = previous[0].get('executions', 0) if previous else capability.get('executions', 0)
                promoted = {**capability, 'status': 'verified', 'executions': executions+1,
                    'verification': [{'source': c['source'], 'evidence': str(c['evidence'])[:300]} for c in proofs[-2:]]}
                self.memory.remember_capability(promoted)

