"""Hermes AIAgent JSONL worker exposing one proposal tool, no external actions."""
import contextlib
import copy
import json
import os
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent.parent
PROTOCOL = sys.stdout
home = BASE / ".jarvis-runtime/hermes-home"
home.mkdir(parents=True, exist_ok=True)
# Jarvis owns this separate profile. Disable upstream deferred execution bridges.
(home / "config.yaml").write_text((BASE / "integrations/profiles/hermes/hermes-config.yaml").read_text(encoding="utf-8"), encoding="utf-8")
os.environ.update(HERMES_HOME=str(BASE / ".jarvis-runtime/hermes-home"),
                  HERMES_DISABLE_LAZY_INSTALLS="1", PYTHONUTF8="1",
                  NO_PROXY="127.0.0.1,localhost,::1")
# All upstream diagnostic output goes to the worker log, never the JSONL channel.
with contextlib.redirect_stdout(sys.stderr):
    from run_agent import AIAgent
    from tools.registry import registry
    from .brain_worker import RULES, SCHEMAS
    from .agent_context import compact_context
    from .hermes import validate_proposal
    from .hermes_ollama import start_provider


def predict(request):
    if request.get("operation") not in {"plan", "replan"}:
        raise ValueError("Unsupported Hermes operation.")
    options = request["options"]
    model = options.get("hermes", {}).get("model", options.get("planner", "qwen3.5:4b"))
    budget = max(10, min(180, float(options.get("hermes", {}).get("timeout_seconds", 120))))
    schema = copy.deepcopy(SCHEMAS[request["operation"]])
    schema["properties"]["question"]["description"] = "Empty string when the task is clear. Only ask a question if information is missing; then steps must be empty. Never copy the user goal into question."
    if request["operation"] == "replan":
        schema["properties"]["done"]["description"] = "True only when fresh observations confirm the complete user goal, with steps=[] and question=''. Otherwise false."
        schema["properties"]["reason"]["description"] = "Brief evidence-based reason for completion or the revised plan."
    schema["properties"]["steps"]["items"]["properties"]["action"]["enum"] = [t["action"] for t in request.get("tools", [])]
    proposals, agents = [], []

    def submit(args):
        try:
            proposal = validate_proposal(args, request)
        except ValueError as exc:
            print("Proposal validation rejected: " + str(exc), file=sys.stderr, flush=True)
            raise
        if not proposals:
            proposals.append(proposal)
        agents[0].interrupt(tool_reason="jarvis_proposal_ready")
        return {"accepted": True, "execution": "Jarvis will independently validate, approve and verify the proposal."}

    registry.register(name="submit_jarvis_plan", toolset="jarvis_planning",
        schema={"name": "submit_jarvis_plan", "description": "Submit the next Jarvis plan, clarification or verified completion assessment. This proposes work; it does not execute actions.", "parameters": schema},
        handler=submit)
    server, endpoint = start_provider(schema, model, budget, RULES)
    try:
        agent = AIAgent(model=model, provider="custom", api_mode="chat_completions",
        base_url=endpoint, api_key="ollama",
        enabled_toolsets=["jarvis_planning"], max_iterations=3,
        quiet_mode=True, save_trajectories=False, skip_context_files=True,
        load_soul_identity=False, skip_memory=True, skip_background_review=True,
        checkpoints_enabled=False, run_budget_seconds=budget, max_tokens=4000,
        reasoning_config={"enabled": False},
        request_overrides={"stream": False},
        ephemeral_system_prompt=RULES + "You are Jarvis's planning engine. Propose supported steps with submit_jarvis_plan. Inspect current failures and observations when replanning; never repeat uncertain actions. Completion is only an assessment for Jarvis to independently verify.")
    except Exception:
        server.shutdown()
        server.server_close()
        registry.deregister("submit_jarvis_plan")
        raise
    agents.append(agent)
    try:
        print("Hermes provider: " + str(agent.client.base_url) + " mode=" + agent.api_mode + " client=" + type(agent.client).__name__, file=sys.stderr, flush=True)
        if str(agent.client.base_url).rstrip("/") != endpoint:
            raise ValueError("Hermes provider route changed unexpectedly: " + str(agent.client.base_url))
        names = {tool["function"]["name"] for tool in agent.tools}
        if names != {"submit_jarvis_plan"}:
            raise ValueError("Hermes tool isolation failed; planning stopped: " + ", ".join(sorted(names)))
        if request.get("check_only"):
            return {"status": "ready", "tools": sorted(names)}
        data = {k: v for k, v in request.items() if k != "options"}
        result = agent.run_conversation("Perform " + request["operation"] + ". Use submit_jarvis_plan. For a clear executable task question MUST be an empty string. For planning, steps must contain supported actions. For replanning, assess the latest screen and completed steps: if they confirm the whole goal, submit done=true, steps=[], question='', reason=brief evidence. Otherwise propose remaining steps with done=false. Never repeat already completed or uncertain actions. Unused folder/content/platform fields are empty strings; unused browser is chrome. Do not ask to confirm a clear request. Task context follows as reference data:\n" + json.dumps(compact_context(data), ensure_ascii=False))
        if proposals:
            proposal = proposals[0]
        else:
            # Some local models answer with JSON rather than calling a tool.
            # This still comes from Hermes's inference loop and must pass identical validation.
            final = result.get("final_response", "")
            if not final:
                raise ValueError("Hermes did not submit a valid proposal (" + str(result.get("exit_reason", result.get("error", "iteration budget exhausted")))[:180] + ").")
            proposal = validate_proposal(json.loads(final), request)
        return {**proposal, "model_used": model, "backend": "hermes"}
    finally:
        agent.close()
        registry.deregister("submit_jarvis_plan")
        server.shutdown()
        server.server_close()


def main():
    if "--check" in sys.argv:
        with contextlib.redirect_stdout(sys.stderr):
            result = predict({"operation": "plan", "options": {}, "check_only": True,
                              "tools": [{"action": "open"}]})
        PROTOCOL.write(json.dumps(result) + "\n")
        return
    for line in sys.stdin:
        try:
            with contextlib.redirect_stdout(sys.stderr):
                result = predict(json.loads(line))
            response = {"result": result}
        except Exception as exc:
            response = {"error": "Hermes planning failed: " + str(exc)}
        PROTOCOL.write(json.dumps(response, ensure_ascii=False) + "\n")
        PROTOCOL.flush()


if __name__ == "__main__":
    main()
