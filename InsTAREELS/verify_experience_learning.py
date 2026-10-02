"""Verify real local persistence/retrieval using synthetic cases; optional inference, no actions."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import time
from unittest.mock import patch

from jarvis.brain import BrainClient
from jarvis.experience_memory import conditions
from jarvis.obsidian_memory import ObsidianMemory
from jarvis.skill_memory import SkillMemory
from jarvis.task_state import TaskState


def run(live_harness=False):
    base = Path(__file__).resolve().parent
    result = {'checked_at': datetime.now(timezone.utc).isoformat(),
              'fixture': 'Synthetic Spotify window; no user applications or configured vault accessed.',
              'external_actions': 0, 'model_weights_updated': False}
    with tempfile.TemporaryDirectory(prefix='jarvis-experience-') as temporary:
        memory = ObsidianMemory(temporary, {'enabled': True, 'vault': 'vault'})
        skills = SkillMemory(memory)
        state = TaskState(temporary)
        state.on_finish = skills.safe_record
        screen = {'title': 'Spotify', 'controls': [{'name': 'Close', 'role': 'Button', 'id': 'fresh-fixture'}]}
        tools = [{'action': 'close_app', 'backend': 'Windows',
                  'description': 'Request close of the identified window; does not force process exit.'},
                 {'action': 'open', 'backend': 'Windows', 'description': 'Open a named configured app.'}]
        baseline = conditions(snapshot=screen, tools=tools)
        state.start('Close Spotify', 'task')
        state.set_conditions(baseline)
        state.checkpoint('acting', action='close_app')
        state.record_failure({'action': 'close_app', 'attempted': True,
            'reason': 'Window became hidden after Close; process exit was not established.'})
        state.finish('failed', 'Requested process exit could not be verified.')
        state.start('Close Spotify window', 'task')
        state.set_conditions(baseline)
        evidence = 'Window became hidden after Close; tray presence and process exit are not established.'
        state.checkpoint('outcome_observed', action='close_app', source='window_state', evidence=evidence)
        state.checkpoint('goal_verified', source='window_state', evidence=evidence)
        state.finish('completed', 'Visible window closed; process exit not claimed.')
        loaded = SkillMemory(memory)
        memory.skills = loaded
        rows = loaded.context('Close Spotify', 'task', conditions=baseline)['experience_context']['cases']
        assert len(rows) == 2 and any(r['verified'] for r in rows) and any(r['uncertain'] for r in rows)
        changed = loaded.context('Close Spotify', 'task', conditions={**baseline, 'ui_fingerprint': 'updated-layout'})['experience_context']['cases']
        assert all('ui_fingerprint' in r['changed_conditions'] for r in changed)
        result.update(persist_restart_retrieve='passed', changed_conditions='passed',
                      cases=rows, condition_policy='Fresh inspection required for every case.')
        client = BrainClient(base, {})
        client.memory = memory
        client.condition_provider = lambda **kwargs: conditions(snapshot=kwargs.get('snapshot'), tools=tools)
        try:
            with patch.object(client, '_request_once', return_value={'question': '', 'steps': []}) as inference:
                client.request('plan', lambda: False, goal='Close Spotify', screen=screen, tools=tools)
                delivered = inference.call_args.kwargs['skill_context']['experience_context']['cases']
                assert any(c['failures'] for c in delivered)
                result['planner_context_delivery'] = 'passed (captured inference boundary; no model call)'
        finally:
            client.close()
        if live_harness:
            options = json.loads((base / 'config.json').read_text(encoding='utf-8'))['brain']
            client = BrainClient(base, options)
            client.memory = memory
            client.condition_provider = lambda **kwargs: conditions(snapshot=kwargs.get('snapshot'), tools=tools)
            started = time.monotonic()
            try:
                proposal = client.request('plan', lambda: False, goal='Close Spotify', screen=screen,
                    apps=['spotify'], tools=tools)
                result['live_inference'] = {'status': 'passed', 'seconds': round(time.monotonic()-started, 3),
                    'proposal_not_executed': proposal, 'scope': 'One local Harness/Qwen turn with synthetic state and persisted cases.'}
            except (OSError, ValueError) as exc:
                result['live_inference'] = {'status': 'failed', 'seconds': round(time.monotonic()-started, 3), 'error': str(exc)}
            finally:
                client.close()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live-harness', action='store_true')
    parser.add_argument('--output', default='artifacts/experience-learning-check.json')
    args = parser.parse_args()
    result = run(args.live_harness)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'cases'}, indent=2))
