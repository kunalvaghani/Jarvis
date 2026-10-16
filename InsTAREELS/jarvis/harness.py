"""Real DeepSeek Harness inference; Jarvis retains tool execution and verification."""
from pathlib import Path

from .brain import BrainClient
from .hermes import validate_proposal
from .planner_settings import settings

SDK_VERSION = '0.1.5rc1'
REVIEWED_REVISION = '639ed015397290b3745d163aafe02ffee4aa3f84'


def validate_harness_proposal(proposal, request):
    return validate_proposal(proposal, request)


def validate_agent_response(result, context):
    from .agent_session import SESSION_TOOLS
    if (not isinstance(result, dict) or not isinstance(result.get('final'), str) or len(result['final']) > 40000
            or not isinstance(result.get('calls'), list) or len(result['calls']) > 1):
        raise ValueError('Harness returned an invalid read-only agent response.')
    tools = context.get('tools', []) if isinstance(context, dict) else []
    if not isinstance(tools, list) or any(not isinstance(t, dict) or not isinstance(t.get('action'), str) for t in tools):
        raise ValueError('Invalid read-only tool catalogue.')
    allowed = {t['action'] for t in tools} & SESSION_TOOLS
    for call in result['calls']:
        if (not isinstance(call, dict) or set(call) != {'action', 'value', 'content'}
                or not isinstance(call.get('action'), str) or call['action'] not in allowed
                or any(not isinstance(call.get(k), str) or len(call[k]) > 16000 for k in ('value', 'content'))):
            raise ValueError('Harness proposed an unavailable or invalid read-only tool call.')
    return {'final': result['final'], 'calls': result['calls']}


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
        self.timeout_seconds = settings(options, 'harness')['timeout_seconds']

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
            result = {**{k: result[k] for k in ('model_used', 'harness_session_id', 'harness_events') if k in result},
                      **validate_harness_proposal(result, {'operation': operation, **data})}
        elif operation == 'agent':
            result = validate_agent_response(result, data.get('context'))
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
