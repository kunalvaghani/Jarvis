"""Isolated Hermes planning; proposed actions still pass Jarvis's execution gates."""
from pathlib import Path

from .brain import BrainClient, validate_plan

REVISION = "cbc569e23cb045b58b067f37cf5514feb44e0828"


def readiness(base):
    base = Path(base)
    if not (base / ".venv-hermes/Scripts/python.exe").is_file():
        return "Hermes runtime missing. Run Setup Jarvis Hermes.cmd."
    source = base / "integrations/hermes-agent"
    if not (source / "run_agent.py").is_file():
        return "Hermes source missing. Run Setup Jarvis Hermes.cmd."
    return ""


def validate_proposal(proposal, request):
    """Treat a Hermes tool call/final response as untrusted planning input."""
    if not isinstance(proposal, dict):
        raise ValueError("Hermes returned an invalid proposal.")
    if not isinstance(proposal.get("question"), str):
        raise ValueError("Hermes omitted its clarification field.")
    steps = proposal.get("steps")
    if not isinstance(steps, list) or len(steps) > 6:
        raise ValueError("Hermes proposed an invalid step list.")
    if steps and proposal["question"]:
        raise ValueError("Return either steps with question='' or a clarification with steps=[].")
    if request["operation"] == "replan":
        if not isinstance(proposal.get("done"), bool) or not isinstance(proposal.get("reason"), str):
            raise ValueError("Hermes omitted replanning status.")
        if proposal["done"] and (steps or proposal["question"]):
            raise ValueError("Hermes claimed completion with remaining work.")
        if len(steps) > request.get("steps_left", 6):
            raise ValueError("Hermes exceeded the remaining task budget.")
    if steps:
        allowed = {tool["action"] for tool in request.get("tools", [])}
        if any(step.get("action") not in allowed for step in steps if isinstance(step, dict)):
            raise ValueError("Hermes proposed a tool unavailable for this task.")
        validate_plan({"steps": steps}, request.get("completed", []))
    elif not proposal["question"] and not proposal.get("done", False):
        raise ValueError("Hermes returned no plan or clarification.")
    return {key: proposal[key] for key in ("question", "steps", "done", "reason") if key in proposal}


class HermesClient(BrainClient):
    worker_module = "jarvis.hermes_worker"
    worker_environment = ".venv-hermes"
    worker_log = "hermes-worker.log"

    def __init__(self, base, options):
        super().__init__(base, options)
        self.timeout_seconds = max(10, min(180, float(options.get("hermes", {}).get("timeout_seconds", 120))))

    def _request_once(self, operation, cancelled, **data):
        if operation not in {"plan", "replan"}:
            raise ValueError("Hermes only supports task planning and replanning.")
        result = super()._request_once(operation, cancelled, **data)
        proposal = validate_proposal(result, {"operation": operation, **data})
        return {**proposal, "model_used": result.get("model_used", ""), "backend": "hermes"}
