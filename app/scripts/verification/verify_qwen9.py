"""Bounded local 9B readiness, real function feedback, vision and code fixtures."""
import ast
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import time

from jarvis.brain import BrainClient, validate_plan
from jarvis.knowledge_worker import session
from jarvis.native_tools import plan
from jarvis.tools import SPECS, ToolRegistry

BASE = Path(__file__).resolve().parents[2]


class FixtureActions:
    def __init__(self, base, config):
        self.base, self.config, self.apps = base, config, config['apps']
        self.task_state = self.skills = self.allowed_tools = None
    def report(self, *args):
        pass


def verify():
    config = json.loads((BASE / 'config/config.json').read_text(encoding='utf-8'))
    results = []
    def check(name, function):
        started = time.monotonic()
        try:
            passed, detail = function()
            results.append({'name': name, 'passed': bool(passed), 'seconds': round(time.monotonic() - started, 3), 'detail': detail})
        except Exception as exc:
            # HTTP errors can include signed/provider URLs; do not dump exception text.
            results.append({'name': name, 'passed': False, 'seconds': round(time.monotonic() - started, 3), 'error_type': type(exc).__name__})
        print(json.dumps(results[-1]), flush=True)
    with session() as client:
        model = 'qwen3.5:9b'
        show = client.post('http://127.0.0.1:11434/api/show', json={'model': model}, timeout=10).json()
        tags = client.get('http://127.0.0.1:11434/api/tags', timeout=10).json()
        # Ollama may report the name in either name/model; preserve the actual tag metadata.
        metadata = [r for r in tags['models'] if r.get('name', r.get('model')) == model]
        check('capabilities', lambda: (set(show.get('capabilities', [])) >= {'completion', 'vision', 'tools'},
            {'capabilities': show.get('capabilities'), 'details': show.get('details'), 'tags': metadata}))
        with tempfile.TemporaryDirectory() as directory:
            actions = FixtureActions(Path(directory), config)
            registry = ToolRegistry(actions)
            offered = [r for r in registry.catalog() if r['action'] == 'integration_status']
            goal = 'Use integration_status to report how many tools are registered. After the verified result, finish with that count.'
            completed = []
            def native_feedback():
                first = plan(client, model, 'Propose one read-only integration status request.',
                    {'goal': goal, 'tools': offered, 'completed': []})
                steps = validate_plan(first)
                if len(steps) != 1 or steps[0]['action'] != 'integration_status':
                    return False, {'proposal': first}
                result = registry.execute(steps[0], lambda: False).evidence
                completed.append({**steps[0], 'verified': True, 'result': result})
                second = plan(client, model, 'The read completed. Report its registered tool count using jarvis_finish.',
                    {'goal': goal, 'tools': offered, 'completed': completed,
                     'screen': {'tool_results': [{'result': result}]}})
                return second['done'] and str(len(SPECS)) in second['reason'], {
                    'selected': steps[0]['action'], 'registered_tools': len(SPECS),
                    'feedback_received': completed[0]['verified'], 'final': second['reason']}
            check('native_read_and_tool_feedback', native_feedback)
    brain = BrainClient(BASE, config['brain'])
    try:
        def vision():
            encoded = base64.b64encode((BASE / 'artifacts/media/next-step-fixture.png').read_bytes()).decode('ascii')
            result = brain.request('next_step', lambda: False, goal='Select Advanced tab in Notepad',
                step_number=1, completed=[], images=[encoded],
                screen={'title': 'Example - Notepad', 'controls': ['Overview', 'Advanced', 'Help']},
                tools=[{'action': 'select', 'description': 'Select a unique visible named tab.'}])
            steps = validate_plan(result)
            return (result.get('native_tool_calling') is True and len(steps) == 1 and
                    steps[0]['action'] == 'select' and steps[0]['value'].casefold() == 'advanced'), result
        check('vision_native_next_action_no_desktop_input', vision)
        def coding():
            result = brain.request('code_edit', lambda: False, goal='Create a Python function add(a, b) that returns a + b.',
                path='fixture.py', reason='Simple syntax fixture', current='', plan=[], files=[])
            source = result.get('content', '')
            tree = ast.parse(source)
            functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'add']
            return bool(functions), {'model': result.get('model_used'), 'source': source,
                                    'scope': 'Syntax/function presence only; generated code was not executed or saved as application code.'}
        check('configured_coder_json_syntax_fixture', coding)
    finally:
        brain.close()
    return {'date': datetime.now(timezone.utc).isoformat(), 'model': 'qwen3.5:9b',
        'checks': results, 'passed': all(r['passed'] for r in results),
        'scope': 'Local fixture inference and one real read-only metadata tool dispatch. No desktop input, live voice or external account actions; not a general accuracy or five-second benchmark.'}


if __name__ == '__main__':
    result = verify()
    output = BASE / 'artifacts/reports/qwen9-check.json'
    if output.exists():
        history_path = BASE / 'artifacts/reports/qwen9-check-history.json'
        history = json.loads(history_path.read_text(encoding='utf-8')) if history_path.exists() else []
        history.append(json.loads(output.read_text(encoding='utf-8')))
        history_path.write_text(json.dumps(history, indent=2) + '\n', encoding='utf-8')
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': result['passed'], 'checks': len(result['checks'])}), flush=True)
    raise SystemExit(0 if result['passed'] else 1)
