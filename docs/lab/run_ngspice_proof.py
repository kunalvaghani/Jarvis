"""Operator-assisted B6 proof through real text ingress, Actions, brain and sandbox.

Explicit invocation only after Linux proof approval. Does not start voice/UI or
modify shipped configuration. --learn uses six solver calls; --reuse uses one.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'app'))
from jarvis.actions import Actions
from jarvis.engine import Engine
from jarvis.neural.service import BrainService
from jarvis.discovery.memory import LabMemory
from jarvis.discovery.contracts import Source, Tool, Skill
from jarvis.discovery.learning import LearningGate, NGSPICE_LICENSE_REVIEW
from jarvis.discovery.adapters.ngspice import environment, RUNTIME

CONFIG = {'neural': {'mode': 'act', 'learning': 'shadow'},
          'lab': {'enabled': True, 'sim': True, 'learning': True}}
JOURNAL = ROOT / 'app/.jarvis-runtime/lab-validation/ngspice-brain-proof.sqlite3'
STATE = ROOT / 'app/.jarvis-runtime/lab-validation/ngspice-brain-state.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--learn', action='store_true')
    parser.add_argument('--reuse', action='store_true')
    parser.add_argument('--requalify', action='store_true', help='explicit new qualification after owned source changed')
    args = parser.parse_args()
    if args.learn == args.reuse:
        parser.error('choose exactly one of --learn or --reuse')
    started = time.monotonic()
    service = BrainService(CONFIG, JOURNAL)
    actions = Actions.__new__(Actions)
    actions.config, actions.base, actions._neural_service, actions.allowed_tools = CONFIG, ROOT/'app', service, None
    memory = LabMemory(service.journal)
    gate = LearningGate(memory, service.registry, CONFIG)
    try:
        if args.learn:
            if STATE.exists() and not args.requalify:
                raise ValueError('proof state exists; inspect/resume instead of replaying learning')
            if STATE.exists():
                previous = json.loads(STATE.read_text(encoding='utf-8'))
                gate.recheck(previous['candidate'])
                previous_state = STATE.with_name('ngspice-brain-state.previous-' + previous['candidate'].split('.')[-1].replace('@','-') + '.json')
                if previous_state.exists():
                    raise ValueError('this qualification was already archived; inspect before replay')
                previous_state.write_bytes(STATE.read_bytes())
            source = Source(id='debian-ngspice-44.2',
                locator='https://deb.debian.org/debian/pool/main/n/ngspice/libngspice0_44.2+ds-1_amd64.deb',
                sha256='d1b9dec8b93f8785c6e8bf6ecea05fc94d6b4c7e60ee8e7df0589e3a2a62822a',
                license=NGSPICE_LICENSE_REVIEW, author='Debian Electronics Team')
            tool = Tool(id='ngspice-shared-44.2', name='ngspice', version='44.2+ds-1',
                        environment=str(RUNTIME), license=NGSPICE_LICENSE_REVIEW)
            episode, candidate = gate.qualify(tool, source, 'discovery.electronics.divider@v1')
            if candidate is None:
                raise ValueError('actual ngspice golden qualification failed')
            state = {'episode': episode.id, 'candidate': candidate.node_id}
            STATE.write_text(json.dumps(state), encoding='utf-8')
            guide = ROOT / 'app/jarvis/skills/discovery/ngspice-divider/SKILL.md'
            memory.put(Skill(id='ngspice-divider-guide', path=str(guide.relative_to(ROOT/'app')),
                             sha256=hashlib.sha256(guide.read_bytes()).hexdigest(), tool_ids=(tool.id,)))
            goals = ('lab simulate divider 5 V 1000 ohm 1000 ohm',
                     'lab simulate divider 9 V 2000 ohm 1000 ohm',
                     'lab simulate divider 0 V 1000 ohm 2000 ohm')
        else:
            state = json.loads(STATE.read_text(encoding='utf-8'))
            goals = ('lab simulate divider 8 V 1000 ohm 3000 ohm',)
        records = []
        for goal in goals:
            commands = []
            engine = Engine(commands.append, lambda *args: None)
            engine.activate()
            engine.feed(goal, final=True, raw=goal)
            if not commands:
                raise ValueError('text ingress did not produce a command')
            before = time.monotonic()
            answer = actions.execute(commands[0])
            last = service.journal.rows('SELECT goal_id FROM goals ORDER BY rowid DESC LIMIT 1')[0]['goal_id']
            if service.journal.goal(last)['state'] != 'verified':
                raise ValueError('brain goal was not independently verified')
            if args.learn:
                gate.observe_use(state['episode'], state['candidate'], last)
            fired = [s.get('target_node') for s in service.journal.signals(last) if s['type'] == 'neuron.fired']
            records.append({'request': goal, 'goal_id': last, 'seconds': time.monotonic()-before,
                            'fired': fired, 'answer': answer})
        capability = memory.get(state['candidate'])
        if args.reuse and state['candidate'] not in records[-1]['fired']:
            raise ValueError('fresh session did not fire the qualified learned neuron')
        result = {'date_local': '2026-11-04 Asia/Calcutta', 'mode': 'learn' if args.learn else 'fresh-process-reuse',
                  'operator_assisted': True, 'voice_acceptance': 'NOT_RUN', 'seconds': time.monotonic()-started,
                  'capability': capability.model_dump(mode='json'), 'goals': records,
                  'experiment_records': len(memory.list('Experiment')), 'runtime': environment()}
        target = ROOT / ('docs/lab/evidence/ngspice-brain-learn.json' if args.learn else
                         'docs/lab/evidence/ngspice-brain-reuse.json')
        target.write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps({k: v for k, v in result.items() if k not in ('goals', 'runtime')}))
    finally:
        service.journal.close()


if __name__ == '__main__':
    main()
