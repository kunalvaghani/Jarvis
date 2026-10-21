"""Persisted reference view of ToolRegistry; never a source of executable tools.

Only static registration metadata is saved. Live configuration, task scope and
executor admission remain authoritative. No credentials, arguments, responses,
application titles or account identities enter this manifest.
"""
from datetime import datetime, timezone
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import threading


class CapabilityModel:
    def __init__(self, base):
        self.base = Path(base)
        self.lock = threading.RLock()
        self.records = {}
        self.status = 'not_loaded'
        self._signature = None

    def refresh(self, specs, cancelled=lambda: False, force=False):
        """Reconcile registrations, changing only stale rows; one atomic save.

        Interrupted preparation keeps the last complete manifest. Disk data is
        compared with host registrations and cannot introduce a capability.
        """
        from .agent_context import scoped, bounded_text
        from .skill_memory import atomic
        from .tools import _FIELDS, KIT_TOOLS
        from .agent_tools import TOOLS as AGENT_TOOLS
        with self.lock:
            signature = tuple((spec, KIT_TOOLS.get(spec.name),
                               tuple(sorted(_FIELDS.get(spec.name, (set(), set()))[0])),
                               tuple(sorted(_FIELDS.get(spec.name, (set(), set()))[1])))
                              for spec in specs.values())
            if not force and signature == self._signature and self.status in {'current', 'memory_only'}:
                return not cancelled()
            try:
                path = scoped(self.base, '.jarvis-runtime/capabilities.json')
                saved = json.loads(bounded_text(path, 1_000_000)) if path.is_file() else {}
                saved = saved.get('capabilities', {}) if isinstance(saved, dict) and saved.get('version') == 1 else {}
                if not isinstance(saved, dict):
                    saved = {}
            except (OSError, ValueError, RecursionError):
                saved = {}
            records = {}
            now = datetime.now(timezone.utc).isoformat(timespec='seconds')
            for spec in specs.values():
                if cancelled():
                    return False
                toolkit = KIT_TOOLS.get(spec.name)
                required, optional = _FIELDS.get(spec.name, ({'value'}, {'content', 'folder'}))
                metadata = {'name': spec.name, 'description': spec.description,
                            'backend': spec.backend, 'approval': spec.approval,
                            'required_configuration': list(toolkit[2]) if toolkit else [],
                            'arguments': {'required': sorted({'action'} | required),
                                          'optional': sorted(optional),
                                          'contract': 'executor_validation_required'},
                            'implementation': ('jarvis/agent_tools.py' if spec.name in AGENT_TOOLS else
                                               'jarvis/toolkits.py' if toolkit else 'jarvis/tools.py'),
                            'verification': 'fresh_executor_postcondition_required',
                            'recovery': 'observe_fresh_state_no_uncertain_action_replay'}
                digest = hashlib.sha256(json.dumps(metadata, sort_keys=True).encode()).hexdigest()
                previous = saved.get(spec.name)
                # Even a matching claimed fingerprint cannot smuggle saved fields.
                current = {**metadata, 'registration_revision': digest}
                if (isinstance(previous, dict)
                        and {k: v for k, v in previous.items() if k != 'updated_at'} == current
                        and isinstance(previous.get('updated_at'), str) and len(previous['updated_at']) <= 40):
                    records[spec.name] = {**current, 'updated_at': previous['updated_at']}
                else:
                    records[spec.name] = {**current, 'updated_at': now}
            if cancelled():
                return False
            self.records = records
            self._signature = signature
            try:
                # Revalidate after preparation; cache failure must not disable tools.
                path = scoped(self.base, '.jarvis-runtime/capabilities.json')
                if records != saved:
                    atomic(path, json.dumps({'version': 1, 'capabilities': records}, indent=2) + '\n')
                self.status = 'current'
            except (OSError, ValueError):
                self.status = 'memory_only'
            return True

    def describe(self, specs, names, allowed=None):
        """Bounded relevant self-knowledge, with current availability (no probes)."""
        from .toolkits import TOOLS, available
        from .execution_contracts import read_outcomes, outcome_metadata
        names = list(dict.fromkeys(names))[:16]
        # Reuse the existing bounded journal, rather than a second learning store.
        # Historical adapter claims are advisory and are never promotion proof.
        metrics = {}
        try:
            for event in read_outcomes(self.base) if names else []:
                name = event.get('tool')
                if not isinstance(name, str) or name not in specs:
                    continue
                observation = outcome_metadata(event)
                item = metrics.setdefault(name, {'observed_calls': 0, 'reported_verified': 0,
                                                  'reported_failed': 0, 'latencies': []})
                item['observed_calls'] += 1
                item['reported_verified'] += observation.get('verification') == 'verified'
                item['reported_failed'] += observation.get('verification') == 'failed'
                if 'latency_ms' in observation:
                    item['latencies'].append(observation['latency_ms'])
        except (OSError, ValueError):
            pass
        with self.lock:
            # A changed registration is reconciled before exposing metadata.
            self.refresh(specs)
            rows = []
            for name in dict.fromkeys(names):
                if name not in specs or name not in self.records:
                    continue
                if isinstance(allowed, (set, frozenset)) and name not in allowed:
                    continue
                row = deepcopy(self.records[name])
                row['configured'] = name not in TOOLS or available(name)
                row['connection_health'] = 'not_probed'
                row['trust'] = 'reference_only_not_authorization'
                samples = metrics.get(name)
                row['performance'] = None
                if samples:
                    samples = dict(samples)
                    times = sorted(samples.pop('latencies'))
                    row['performance'] = {**samples,
                        'latency_p50_ms': times[len(times) // 2] if times else None,
                        'latency_p95_ms': times[math.ceil(.95 * len(times)) - 1] if times else None,
                        'scope': 'bounded_historical_journal_not_revision_bound_acceptance'}
                rows.append(row)
                if len(rows) >= 16:
                    break
            return {'status': self.status, 'capabilities': rows,
                    'contract': 'Registration/configuration is not connection health or verified success. '
                                'MCP schemas and principal identity require existing live discovery. '
                                'Argument summaries do not replace executor validation.'}


def model_for(actions):
    """Reuse the reference model across short-lived ToolRegistry instances."""
    model = getattr(actions, '_capability_model', None)
    base = getattr(actions, 'base', None)
    if base is None:
        return None
    if not isinstance(model, CapabilityModel):
        model = CapabilityModel(base)
        actions._capability_model = model
    return model
