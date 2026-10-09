"""Real Qwen selection and Jarvis dispatch; inspect only, no draft mutation."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from jarvis.actions import Actions, Desktop
from jarvis.brain import BrainClient
from jarvis.tools import ToolRegistry


def main():
    base = Path(__file__).resolve().parents[2]
    config = json.loads((base / 'config/config.json').read_text())
    config['_ui_verification'] = True
    config['memory'] = {**config.get('memory', {}), 'enabled': False}
    app = Actions(config, base, lambda *args: None, Desktop())
    app.approval_handler = lambda *args: False  # Inspection needs no write approval.
    client = BrainClient(base, config['brain'])
    report = {'date': datetime.now(timezone.utc).isoformat(), 'passed': False,
              'scope': 'Actual Qwen next-step proposal and regular Jarvis dispatcher. Existing logged-in Chrome inspection only; no email write or send.'}
    started = time.monotonic()
    try:
        goal = 'Inspect Gmail in my existing logged-in Chrome and tell me whether Compose is available. Only inspect; do not create, edit or send any email.'
        proposal = client.request('next_step', lambda: False, goal=goal,
            tools=ToolRegistry(app).catalog(goal), completed=[],
            screen={'title': 'Gmail in Chrome', 'controls': []}, apps=['chrome'], steps_left=5)
        report['proposal'] = proposal
        assert not proposal.get('done') and not proposal.get('question')
        assert len(proposal['steps']) == 1
        step = proposal['steps'][0]
        assert step['action'] == 'skill_gmail_chrome'
        assert json.loads(step['content']) == {'operation': 'inspect'}
        result = app.brain.dispatch(step, lambda: False)
        evidence = json.loads(result.evidence)
        assert evidence['gmail_in_existing_chrome'] and evidence['compose_available']
        assert not evidence['sent'] and not evidence['credentials_copied']
        report.update(passed=True, evidence=evidence)
    except Exception as error:
        report.update(error_type=type(error).__name__, error=str(error)[:1000])
    finally:
        client.close()
        app.close()
        report['seconds'] = round(time.monotonic() - started, 3)
        (base / 'artifacts/reports/gmail-task-routing.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
