"""Golden qualification extends existing Registry proposals and Journal outcomes.

This gate can wrap only reviewed existing read-only foundation adapters. It cannot
load generated entry points, install packages, grant permission or approve writes.
"""
from __future__ import annotations

import json
import uuid
from .contracts import Capability, LearningEpisode, Source, Tool
from .golden import load, run

QUALIFIERS = {'discovery.units.convert@v1': ('pint_si_and_temperature', 'discovery.verify.units@v1')}
QUALIFIERS['discovery.electronics.divider@v1'] = ('ngspice_dc_divider', 'discovery.verify.divider@v1')
NGSPICE_LICENSE_REVIEW = 'Debian-ngspice-44.2-reviewed-mixed'
PERMISSIVE = frozenset({'BSD-3-Clause', 'MIT', 'Apache-2.0'})


class LearningGate:
    def __init__(self, memory, registry, config):
        from .catalog import enabled
        if not enabled(config, 'learning'):
            raise PermissionError('Lab learning is disabled')
        self.memory, self.registry = memory, registry
        self.journal = memory.journal
        self.config = config

    def _enabled(self):
        from .catalog import enabled
        if not enabled(self.config, 'learning'):
            raise PermissionError('Lab learning is disabled')

    def qualify(self, tool: Tool, source: Source, base_id: str):
        self._enabled()
        episode = LearningEpisode(id='learning-' + uuid.uuid4().hex, gap='qualify a reviewed scientific adapter',
                                  tool_id=tool.id, stage='gap')
        self.memory.put(episode)
        try:
            is_ngspice = base_id == 'discovery.electronics.divider@v1'
            if ((tool.license not in PERMISSIVE and not (is_ngspice and tool.license == NGSPICE_LICENSE_REVIEW))
                    or source.license != tool.license):
                raise PermissionError('tool needs the existing license/security approval flow')
            if base_id not in QUALIFIERS:
                raise PermissionError('no reviewed sandbox qualification adapter exists for this tool')
            from .sandbox.env_manager import units_environment
            from .adapters.ngspice import environment
            env = environment() if is_ngspice else units_environment()
            exact_source = (source.locator == 'https://deb.debian.org/debian/pool/main/n/ngspice/libngspice0_44.2+ds-1_amd64.deb'
                            and source.sha256 == 'd1b9dec8b93f8785c6e8bf6ecea05fc94d6b4c7e60ee8e7df0589e3a2a62822a')
            if (tool.name.casefold() != ('ngspice' if is_ngspice else 'pint')
                    or tool.version != ('44.2+ds-1' if is_ngspice else '0.25.2')
                    or tool.environment != env['environment']
                    or not env['ready' if is_ngspice else 'pins_match'] or (is_ngspice and not exact_source)):
                raise PermissionError('tool metadata differs from the reviewed qualification adapter')
            base = self.registry.get(base_id)
            if base is None or base.side_effect_class != 'read_only' or base.contract != 'explicit':
                raise PermissionError('qualification requires an existing explicit read-only adapter')
            from ..neural.policy import Context, eligibility
            if not eligibility(base, Context(config=self.config)).eligible:
                raise PermissionError('qualification adapter does not pass existing brain eligibility')
            self.memory.put(source)
            self.memory.put(tool.model_copy(update={'verification': 'UNVERIFIED'}))
        except (ValueError, PermissionError) as exc:
            self.memory.put(episode.model_copy(update={'revision': 2, 'stage': 'review_failed',
                                                       'failure_reason': 'license/security/schema review refused: ' + type(exc).__name__}))
            raise
        case, verifier = QUALIFIERS[base_id]
        receipt, ref = run(case, self.journal)
        episode = LearningEpisode(id=episode.id, revision=2, gap='qualify existing adapter for ' + tool.name, tool_id=tool.id,
                                  source_ids=(source.id,), stage='golden_passed' if receipt.passed else 'golden_failed',
                                  golden_ref=ref, failure_reason=None if receipt.passed else '; '.join(receipt.details))
        self.memory.put(episode)
        if not receipt.passed:
            return episode, None
        node_id = 'discovery.learned.' + uuid.uuid4().hex[:16] + '@v1'
        candidate = base.model_copy(update={'node_id': node_id, 'provider': 'jarvis.neural.learning',
                                           'source': 'discovery-qualified:' + base_id,
                                           'requirements': tuple(dict.fromkeys((*base.requirements, 'flag:lab.learning')))})
        proposed = self.registry.propose(candidate.model_dump(), proposer='discovery.golden')
        self.memory.put(Capability(id=node_id, neuron_id=node_id, verification='LEARNED_UNVERIFIED',
                                   intents=('reuse qualified ' + tool.name,), golden_ref=ref,
                                   source_ids=(source.id,), justification='Golden passed; independent qualified uses still required.'))
        self.memory.put(episode.model_copy(update={'revision': 3, 'stage': 'registered'}))
        return episode.model_copy(update={'revision': 3, 'stage': 'registered'}), proposed

    def observe_use(self, episode_id: str, node_id: str, goal_id: str):
        self._enabled()
        episode = self.memory.get(episode_id)
        candidate = self.registry.get(node_id)
        capability = self.memory.get(node_id)
        if not isinstance(episode, LearningEpisode) or not isinstance(capability, Capability) or candidate is None:
            raise ValueError('missing qualification history')
        if not candidate.source.startswith('discovery-qualified:') or candidate.provider != 'jarvis.neural.learning':
            raise PermissionError('not a golden-qualified learned adapter')
        base_id = candidate.source.removeprefix('discovery-qualified:')
        if base_id not in QUALIFIERS or capability.golden_ref != episode.golden_ref:
            raise ValueError('qualification history does not match the capability')
        load(self.journal, episode.golden_ref, QUALIFIERS[base_id][0])
        goal = self.journal.goal(goal_id)
        plan = json.loads(goal['plan']) if goal and goal.get('plan') else {}
        steps = plan.get('steps', [])
        if not goal or goal.get('state') != 'verified' or not any(s['neuron'] in (base_id, node_id) for s in steps):
            raise ValueError('use must be an independently verified Journal goal for this adapter')
        verifier_id = next((s['neuron'] for s in steps if s['step_id'] == plan.get('goal_verifier')), None)
        events = self.journal.signals(goal_id)
        if verifier_id != QUALIFIERS[base_id][1] or not any(
                s['type'] == 'verification.passed' and s.get('target_node') == verifier_id for s in events):
            raise ValueError('missing independent verifier evidence')
        goals = tuple(dict.fromkeys((*episode.successful_goal_ids, goal_id)))
        if goals == episode.successful_goal_ids:
            return capability  # Idempotent: repeated finish hooks cannot promote faster.
        promoted = len(goals) >= 3
        if promoted and candidate.status == 'proposed':
            # Only the reviewed read-only wrapper is activated; eligibility still checks every flag and policy.
            if candidate.side_effect_class != 'read_only':
                raise PermissionError('write-capable learned neurons require user activation')
            self.registry.approve(node_id, approver='discovery.code_checked_golden')
        if promoted and capability.verification != 'VERIFIED':
            capability = capability.model_copy(update={'revision': capability.revision + 1, 'verification': 'VERIFIED',
                                                       'justification': 'Golden and three distinct independently verified Journal goals passed.'})
            self.memory.put(capability)
        self.memory.put(episode.model_copy(update={'revision': episode.revision + 1, 'successful_goal_ids': goals,
                                                   'stage': 'promoted' if promoted else 'registered'}))
        return capability

    def recheck(self, node_id: str):
        self._enabled()
        candidate = self.registry.get(node_id)
        capability = self.memory.get(node_id)
        if candidate is None or not isinstance(capability, Capability) or not candidate.source.startswith('discovery-qualified:'):
            raise ValueError('unknown learned capability')
        base_id = candidate.source.removeprefix('discovery-qualified:')
        try:
            if base_id == 'discovery.electronics.divider@v1':
                from .adapters.ngspice import environment
                if not environment()['ready']:
                    raise ValueError('reviewed ngspice runtime changed')
            load(self.journal, capability.golden_ref, QUALIFIERS[base_id][0])
        except ValueError:
            if candidate.status == 'active':
                self.registry.disable(node_id, 'golden regression or changed implementation', actor='lifecycle')
            self.memory.put(capability.model_copy(update={'revision': capability.revision + 1, 'verification': 'DEGRADED',
                                                           'justification': 'Golden evidence no longer matches current implementation.'}))
            return False
        return True
