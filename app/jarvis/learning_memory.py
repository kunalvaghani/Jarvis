"""Wires ReasoningBank, the OpenViking vault index and isolated exploration into Jarvis.

Everything here is optional: when a component is disabled or unavailable, Jarvis
behaves as before and the reason is kept in `status()`. Planner context receives
only bounded lessons and vault hits (summaries + source paths), never raw logs.
"""
import threading
import time
from pathlib import Path

DEFAULTS = {
    'reasoning_bank': {'enabled': True, 'lessons_per_plan': 3, 'char_budget': 1200},
    'viking_memory': {'enabled': False},
    'exploration': {'enabled': False, 'applications': ['blender'], 'max_episodes_per_day': 6},
}


def options(config, name):
    section = config.get(name, {}) if isinstance(config, dict) else {}
    return {**DEFAULTS[name], **(section if isinstance(section, dict) else {})}


def trajectory_from_task(task):
    """A finished Jarvis task as a ReasoningBank trajectory (steps, failures, independent verification)."""
    steps = [{'action': str(step.get('action', ''))[:60], 'target': str(step.get('value', ''))[:80],
              'verified': step.get('verified') is True, 'call_id': step.get('call_id')}
             for step in ((task.get('plan') or {}).get('completed') or []) if isinstance(step, dict)]
    steps += [{'action': str(f.get('action', ''))[:60], 'target': str(f.get('value', ''))[:80],
               'error': str(f.get('reason', ''))[:300]} for f in task.get('failures') or [] if isinstance(f, dict)]
    verification = [str(c.get('evidence', ''))[:300] for c in task.get('checkpoints') or []
                    if isinstance(c, dict) and c.get('stage') == 'goal_verified']
    if steps and verification:
        steps[-1 if not steps[-1].get('error') else 0]['final'] = True
    conditions = task.get('conditions') or {}
    return {'task_id': task.get('task_id', ''), 'source': 'task', 'goal': task.get('goal', ''),
            'status': task.get('status', ''), 'steps': steps, 'verification': verification,
            'conditions': {'application': conditions.get('app_name', ''), 'surface': conditions.get('surface', '')}}


def sandbox_registry_factory(actions):
    """ToolRegistry bound to one disposable sandbox folder; only blender_task in that folder is approved."""
    from types import SimpleNamespace
    from .tools import ToolRegistry

    def factory(folder):
        folder = Path(folder).resolve()

        def approve(kind, detail, cancelled):
            import json
            data = json.loads(detail)
            if kind != 'blender_task' or not (folder / data.get('file', '')).resolve().is_relative_to(folder):
                raise ValueError('Exploration may only write inside its disposable sandbox.')
        sandbox = SimpleNamespace(base=actions.base, config=getattr(actions, 'config', {}), allowed_tools={'blender_task'},
                                  report=lambda *args: None, task_state=None, _approve=approve,
                                  _task_folder=lambda name, cancelled: str(folder))
        return ToolRegistry(sandbox)
    return factory


class LearningMemory:
    def __init__(self, actions, config):
        self.actions, self.config = actions, config if isinstance(config, dict) else {}
        self.bank = self.viking = self.explorer = None
        self.errors = {}
        self.lock = threading.Lock()
        self._health = (0., False)
        base = Path(actions.base)
        if options(self.config, 'reasoning_bank')['enabled']:
            try:
                from .reasoning_bank import ReasoningBank
                self.bank = ReasoningBank(base)
            except Exception as exc:  # Broad by design: optional memory must not stop Jarvis.
                self.errors['reasoning_bank'] = type(exc).__name__ + ': ' + str(exc)[:200]
        viking = options(self.config, 'viking_memory')
        memory = getattr(actions, 'memory', None)
        vault = getattr(memory, 'vault', None)
        if viking['enabled'] and vault:
            from .viking_memory import VikingMemory
            candidate = VikingMemory(base, vault, viking)
            if candidate.available():
                self.viking = candidate
            else:
                self.errors['viking_memory'] = 'OpenViking environment or vault unavailable.'
        exploration = options(self.config, 'exploration')
        if exploration['enabled']:
            from .exploration import Explorer
            self.explorer = Explorer(base, self.bank, getattr(actions, 'skills', None), exploration['applications'])

    def attach(self):
        brain = getattr(self.actions, 'brain', None)
        client = getattr(brain, 'client', None)
        if client is not None and self.bank is not None:
            client.lesson_provider = self.lessons
        memory = getattr(self.actions, 'memory', None)
        if memory is not None and self.viking is not None:
            memory.viking_provider = self.vault_hits
        return self

    def lessons(self, goal, cancelled=lambda: False):
        settings = options(self.config, 'reasoning_bank')
        if self.bank is None or cancelled():
            return []
        result = self.bank.retrieve(goal, None, settings['lessons_per_plan'], settings['char_budget'])
        return [{k: row[k] for k in ('id', 'kind', 'title', 'content', 'conditions', 'confidence', 'trust')}
                for row in result['lessons']]

    def vault_hits(self, goal, limit=3):
        """Bounded hierarchical hits; skipped (not waited for) when the owned server is not ready."""
        if self.viking is None:
            return []
        stamp, healthy = self._health
        if time.monotonic() - stamp > 30:
            healthy = self.viking.healthy()
            self._health = (time.monotonic(), healthy)
        if not healthy:
            return []
        rows = self.viking.find(goal, limit)['results']
        return [{'source_path': r['source_path'], 'level': r['level'], 'score': r['score'],
                 'summary': r['summary'][:300], 'summary_is_generated': r['summary_is_generated'], 'stale': r['stale']}
                for r in rows if r['source_path']]

    def learn_from_task(self, task):
        if self.bank is None or not isinstance(task, dict) or task.get('status') not in {'completed', 'failed', 'paused'}:
            return None
        try:
            return self.bank.learn(trajectory_from_task(task))
        except Exception as exc:  # Broad by design: learning never changes a task outcome.
            self.errors['learn'] = type(exc).__name__ + ': ' + str(exc)[:200]
            return None

    def maintenance(self, cancelled=lambda: False, registry_factory=None):
        """Idle work: incremental vault index, lesson compaction and one isolated exploration episode."""
        report = {}
        if self.viking is not None and not cancelled():
            try:
                report['vault_index'] = self.viking.index(cancelled)
            except Exception as exc:  # Broad by design: the next idle window retries; nothing was replayed.
                report['vault_index_error'] = type(exc).__name__ + ': ' + str(exc)[:200]
        if self.bank is not None and not cancelled():
            report['compaction'] = self.bank.compact()
        if self.explorer is not None and registry_factory is not None and not cancelled():
            from .exploration import BlenderSandboxEnv, IsolationUnavailable
            if 'blender' in self.explorer.approved:
                try:
                    report['exploration'] = self.explorer.episode('blender', BlenderSandboxEnv(registry_factory), cancelled)
                except IsolationUnavailable as exc:
                    report['exploration_blocked'] = str(exc)
        return report

    def status(self):
        return {'reasoning_bank': self.bank is not None, 'viking_memory': self.viking is not None,
                'exploration': self.explorer is not None, 'errors': dict(self.errors)}
