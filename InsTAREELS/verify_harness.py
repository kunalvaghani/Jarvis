"""Real local SDK/Qwen turns with synthetic observations; never executes proposals."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time

from jarvis.harness import HarnessClient, SDK_VERSION

BASE = Path(__file__).resolve().parent


def main():
    client = HarnessClient(BASE, {'planner': 'qwen3.5:4b', 'harness': {'timeout_seconds': 180}})
    tools = [{'action': 'open', 'description': 'Open an explicitly named configured app.'}]
    rows = []
    scenarios = [
        ('plan', {'goal': 'Open Calculator.', 'tools': tools,
            'apps': ['calculator'], 'screen': {'title': 'Synthetic idle desktop', 'controls': []}}),
        ('replan', {'goal': 'Open Calculator.', 'tools': tools, 'steps_left': 3,
            'completed': [{'action': 'open', 'value': 'calculator', 'verified': True}],
            'screen': {'title': 'Calculator', 'trusted_evidence': ['Synthetic test observation: Calculator window is visible.']}}),
        ('agent', {'context': {'goal': 'Read sample.py and explain its result.',
            'repository_instructions': [], 'selected_skills': [],
            'tools': [{'action': 'read_file', 'description': 'Read a scoped file.'}],
            'observations': [{'action': 'read_file', 'value': 'sample.py', 'ok': True, 'result': 'print(2 + 3)'}]}}),
    ]
    try:
        for operation, data in scenarios:
            started = time.monotonic()
            try:
                result = client.request(operation, lambda: False, **data)
                ok = (bool(result.get('steps')) and result['steps'][0].get('value', '').casefold() == 'calculator' if operation == 'plan'
                    else result.get('done') is True and not result.get('steps') if operation == 'replan'
                    else bool(result.get('final')) and not result.get('calls') and '5' in result['final'])
                row = {'operation': operation, 'ok': ok, 'seconds': round(time.monotonic()-started, 3), 'result': result}
            except Exception as exc:
                row = {'operation': operation, 'ok': False, 'seconds': round(time.monotonic()-started, 3), 'error': str(exc)[:1000]}
            rows.append(row)
            print(json.dumps(row), flush=True)
    finally:
        client.close()
    report = {'date': datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat(), 'sdk_version': SDK_VERSION,
        'scope': 'Real upstream SDK and local Qwen inference; synthetic observations, no desktop actions or writes executed.',
        'checks': rows}
    (BASE / 'artifacts/harness-local-check.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return 0 if all(row['ok'] for row in rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())
