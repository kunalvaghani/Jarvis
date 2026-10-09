"""Real DeepSeek Harness inference; Jarvis retains tool execution and verification."""
from pathlib import Path

from .brain import BrainClient
from .hermes import validate_proposal

SDK_VERSION = '0.1.5rc1'
REVIEWED_REVISION = '639ed015397290b3745d163aafe02ffee4aa3f84'


def validate_harness_proposal(proposal, request):
    result = validate_proposal(proposal, request)
    from .task_recovery import action_key
    forbidden = {action_key(row) for row in request.get('completed', []) if isinstance(row, dict)}
    for failure in request.get('failures', []):
        if isinstance(failure, dict):
            step = failure.get('step', failure)
            if isinstance(step, dict):
                forbidden.add(action_key(step))
    if any(action_key(step) in forbidden for step in result['steps']):
        raise ValueError('Harness repeated a completed or failed action; proposal rejected.')
    return result


def readiness(base):
    base = Path(base)
    if not (base / '.venv-harness/Scripts/python.exe').is_file():
        return 'DeepSeek Harness runtime missing. Run launchers/Setup Jarvis Harness.cmd.'
    if not (base / 'integrations/profiles/harness/harness-inference.patch.yml').is_file():
        return 'DeepSeek Harness inference profile missing.'
    return ''


class HarnessClient(BrainClient):
    worker_module = 'jarvis.harness_worker'
    worker_environment = '.venv-harness'
    worker_log = '.jarvis-runtime/logs/harness-worker.log'
    retry_delay_seconds = .5

    def __init__(self, base, options):
        super().__init__(base, options)
        self.timeout_seconds = max(10, min(300, float(options.get('harness', {}).get('timeout_seconds', 180))))

    def _request_once(self, operation, cancelled, **data):
        if operation not in {'plan', 'replan', 'agent', 'code_plan'}:
            raise ValueError('Harness supports planning, development planning, replanning and read-only agent inference.')
        result = super()._request_once(operation, cancelled, **data)
        if operation == 'code_plan':
            if data.get('development') is not True:
                raise ValueError('Harness coding plans require the scoped development workflow.')
            from .development_projects import batches
            batches(result)
            allowed=data.get('allowed_output_paths')
            if allowed is not None and {s['path'].casefold() for s in result['files']} != {p.casefold() for p in allowed}:
                raise ValueError('Harness plan exceeded the explicitly allowed output files; no action executed.')
        if operation in {'plan', 'replan'}:
            result = {**result, **validate_harness_proposal(result, {'operation': operation, **data})}
        elif operation == 'agent' and (not isinstance(result, dict) or not isinstance(result.get('final'), str)
              or not isinstance(result.get('calls'), list) or len(result['calls']) > 1):
            raise ValueError('Harness returned an invalid read-only agent response.')
        return {**result, 'backend': 'deepseek-harness'}


def healthy(brain_client):
    client = getattr(brain_client, 'harness', None)
    return client is None or client.process is None or client.process.poll() is None


def repair(brain_client):
    # Clear a dead owned worker. Next explicit inference starts it; no task replay.
    client = getattr(brain_client, 'harness', None)
    if client is not None:
        client.close()
    return healthy(brain_client)


class HarnessProvider:
    """Use the upstream inference loop within Jarvis's scoped read-only session."""
    def __init__(self, base, model='qwen3.5:4b', timeout_seconds=180):
        self.model, self.timeout_seconds = model, timeout_seconds
        self.client = HarnessClient(base, {'planner': model, 'harness': {'model': model, 'timeout_seconds': timeout_seconds}})

    def __call__(self, context):
        result = self.client.request('agent', lambda: False, context=context)
        return {key: result[key] for key in ('final', 'calls')}

    def close(self):
        self.client.close()
