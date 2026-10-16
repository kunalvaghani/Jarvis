"""Isolated Hermes planning; proposed actions still pass Jarvis's execution gates."""
from pathlib import Path

from .brain import BrainClient, validate_plan
from .task_graph import MAX_PLAN_STEPS
from .planner_settings import settings

REVISION = "cbc569e23cb045b58b067f37cf5514feb44e0828"


def readiness(base):
    base = Path(base)
    if not (base / ".venv-hermes/Scripts/python.exe").is_file():
        return "Hermes runtime missing. Run launchers/Setup Jarvis Hermes.cmd."
    source = base / "integrations/hermes-agent"
    if not (source / "run_agent.py").is_file():
        return "Hermes source missing. Run launchers/Setup Jarvis Hermes.cmd."
    return ""


def validate_proposal(proposal, request):
    """Treat a Hermes tool call/final response as untrusted planning input."""
    if not isinstance(proposal, dict):
        raise ValueError("Hermes returned an invalid proposal.")
    if not isinstance(request, dict) or not isinstance(request.get('operation'), str) or request['operation'] not in {'plan', 'replan'}:
        raise ValueError('Invalid planner request operation.')
    budget = request.get('steps_left', request.get('max_task_actions', 20))
    if type(budget) is not int or not 0 <= budget <= MAX_PLAN_STEPS:
        raise ValueError('Invalid remaining task budget.')
    if not isinstance(proposal.get("question"), str) or len(proposal['question']) > 500:
        raise ValueError("Hermes omitted its clarification field.")
    steps = proposal.get("steps")
    if not isinstance(steps, list) or len(steps) > MAX_PLAN_STEPS:
        raise ValueError("Hermes proposed an invalid step list.")
    if steps and proposal["question"]:
        raise ValueError("Return either steps with question='' or a clarification with steps=[].")
    if request["operation"] == "replan":
        if not isinstance(proposal.get("done"), bool) or not isinstance(proposal.get("reason"), str) or len(proposal['reason']) > 4000:
            raise ValueError("Hermes omitted replanning status.")
        if proposal["done"] and (steps or proposal["question"]):
            raise ValueError("Hermes claimed completion with remaining work.")
        if len(steps) > budget:
            raise ValueError("Hermes exceeded the remaining task budget.")
    if steps:
        tools = request.get('tools', [])
        if not isinstance(tools, list) or any(not isinstance(t, dict) or not isinstance(t.get('action'), str) for t in tools):
            raise ValueError('Invalid planner tool catalogue.')
        allowed = {tool['action'] for tool in tools}
        if any(not isinstance(step, dict) or not isinstance(step.get('action'), str) or step['action'] not in allowed for step in steps):
            raise ValueError("Hermes proposed a tool unavailable for this task.")
        validate_plan({"steps": steps}, request.get("completed", []),
                      budget)
        from .task_recovery import action_key
        completed, failures = request.get('completed', []), request.get('failures', [])
        if not isinstance(completed, list) or not isinstance(failures, list):
            raise ValueError('Invalid planner history.')
        if any(not isinstance(s, dict) or not isinstance(s.get('action'), str) for s in completed):
            raise ValueError('Invalid completed action history.')
        forbidden = {action_key(s) for s in completed}
        for failure in failures:
            if isinstance(failure, dict):
                step = failure.get('step', failure)
                if isinstance(step, dict) and isinstance(step.get('action'), str):
                    forbidden.add(action_key(step))
        for step in steps:
            key = action_key(step)
            if key in forbidden:
                raise ValueError('Planner repeated a completed, failed or duplicate action; proposal rejected.')
            forbidden.add(key)
    elif not proposal["question"] and not proposal.get("done", False):
        raise ValueError("Hermes returned no plan or clarification.")
    keys = ('question', 'steps', 'done', 'reason') if request['operation'] == 'replan' else ('question', 'steps')
    return {key: proposal[key] for key in keys if key in proposal}


class HermesClient(BrainClient):
    worker_module = "jarvis.hermes_worker"
    worker_environment = ".venv-hermes"
    worker_log = ".jarvis-runtime/logs/hermes-worker.log"

    def __init__(self, base, options):
        super().__init__(base, options)
        self.timeout_seconds = settings(options, 'hermes')['timeout_seconds']

    def _request_once(self, operation, cancelled, **data):
        if operation not in {"plan", "replan"}:
            raise ValueError("Hermes only supports task planning and replanning.")
        result = super()._request_once(operation, cancelled, **data)
        proposal = validate_proposal(result, {"operation": operation, **data})
        return {**proposal, "model_used": result.get("model_used", ""), "backend": "hermes"}
