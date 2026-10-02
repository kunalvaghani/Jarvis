# Hermes Agent integration

Updated 2026-10-01. Later skill integration and route selection are described in [Hermes skills and comparison](hermes-skills-and-comparison.md); historical checks below retain their original configuration.

[Nous Research Hermes Agent](https://github.com/NousResearch/hermes-agent) is MIT licensed and free to install and modify. Jarvis uses local Ollama, with no paid model API or key. Optional upstream cloud models and services may charge separately. See the [local Ollama guide](https://hermes-agent.nousresearch.com/docs/guides/local-ollama-setup).

## Behavior

When `brain.hermes.enabled` is true, model-based `plan` and `replan` requests use the actual upstream `AIAgent` conversation/tool loop. Its only exposed tool is `submit_jarvis_plan`. Hermes proposes work, receives validation errors and can revise within three iterations. Jarvis supplies available tool descriptions, relevant Obsidian memory, app names, prior task experience, completed steps, failures and fresh observations. Notes and screen contents are reference data, never permission or instructions.

Jarvis executes validated proposals through its existing registry, approvals, checkpoints, decisions and independent verification. The six-action task budget remains. Completion assessments also require independent verification. Invalid output, unsupported tools, mixed clarification/action proposals and exceeded budgets stop planning. Uncertain external actions are never replayed by this integration.

Direct actions and everyday runtime answers retain their existing routes. Coding continues to use Qwen3-Coder; decisions and screen verification keep their configured models. The Dynamic Island remains the interface. This integration does not enable Hermes's independent desktop, terminal, gateway or messaging tools.

## Installation and configuration

Source is pinned to `cbc569e23cb045b58b067f37cf5514feb44e0828`, reviewed on 2026-09-30. Attribution: **Nous Research**, MIT, copyright 2025; the exact [license](../integrations/HERMES-LICENSE) is retained. Source checkout, environments, caches and the Hermes profile are excluded from Git.

The current planner preference may differ after the live comparison; enabling/disabling Hermes does not disable skill references. Run [Setup Jarvis Hermes.cmd](../Setup%20Jarvis%20Hermes.cmd) from the application directory to reproduce installation. Git and a Python launcher or Jarvis's main environment must be available. Setup verifies the pinned source, installs uv 0.12.21 and Python 3.14.7, then installs upstream core dependencies into `.venv-hermes`. It checks imports and tool isolation before enabling Hermes. A checkout at another revision is left unchanged and setup stops. Installation needs network access. Dependencies are declared in the pinned upstream `pyproject.toml`, referenced by [runtime_manifest.json](../runtime_manifest.json), and isolated from Jarvis's main requirements.

Current [configuration](../config.json):

```json
"hermes": {
  "enabled": false,
  "model": "qwen3.5:4b",
  "timeout_seconds": 120
}
```

This block is inside `brain`. Restart Jarvis after changes. Set `brain.hermes.enabled` to `false` to use the previous planner. A missing or broken enabled installation gives an actionable error; no paid service is substituted.

**Later measured preference (2026-10-01):** `enabled` is currently **false**. The comparison selected direct verified workflows first and native Qwen for other model-planned tasks; Hermes remains installed as an optional planner. All 210 indexed upstream skill references remain available regardless of that flag. [Measurements and limitations](hermes-skills-and-comparison.md#smaller-context-follow-up-and-selected-route).

| Application-relative path | Purpose |
| --- | --- |
| `integrations/hermes-agent` | Pinned upstream source |
| `.venv-hermes` | Hermes runtime |
| `.venv-hermes-bootstrap` | Setup-only uv runtime |
| `.jarvis-runtime/hermes-python` | Managed Python |
| `.jarvis-runtime/hermes-cache` | Installer cache |
| `.jarvis-runtime/hermes-home` | Jarvis-owned Hermes profile |
| `hermes-worker.log` | Local diagnostics, excluded from Git |

The managed [profile](../integrations/hermes-config.yaml) disables deferred execution bridges, compression and background review. It is separate from standalone Hermes profiles. Obsidian remains Jarvis's memory source.

The reusable hidden worker belongs to Jarvis. Cancellation/Stop kills it and closes its protocol and log handles. Worker loss allows one inference-only retry; timeout stops the request. Cancelled requests are not restarted. No external action executes in the inference worker.

## Local model compatibility

This PC's imported Qwen model has a raw `{{ .Prompt }}` template. Standard OpenAI-compatible requests produced inconsistent plans and timeouts. The adapter uses Jarvis's native Ollama driver for Qwen role formatting, disabled thinking and structured JSON. Real model output becomes a Hermes proposal tool call and passes the same validation as every proposal.

The SDK connects to a temporary loopback-only provider inside the owned worker. It forwards inference/model metadata to `127.0.0.1:11434` and has no desktop, shell, filesystem or messaging tools. The provider socket/thread close after each conversation, including initialization failures. The pinned Hermes version requires 64,000-token context; the adapter requests this on CPU. Memory use and latency can be substantial.

## Verification and limits

**2026-10-01 live local inference:** [verify_hermes.py](../verify_hermes.py) passed planning and completion assessment through Hermes and the actual local Qwen model. A Calculator-opening proposal took **37.09 seconds**, including worker startup; subsequent replanning took **16.75 seconds**. Replanning used **synthetic desktop observations**. Neither proposal was executed. [Saved evidence](../artifacts/hermes-readonly-check.json) contains only that synthetic task. Earlier standard-provider trials included a 120-second timeout and inconsistent output before adding the native adapter.

This verifies inference integration and proposal validation, not live desktop task completion or improved automation success rates. Five-second answers are not guaranteed. Long workflows and other models need task-specific live checks.

**2026-10-01 regression/readiness:** All **449 tests** passed. Tests cover proposal validation, current tool restrictions, clarification/completion rules, remaining budgets, memory routing, inference-only retry, pre-launch cancellation and provider socket shutdown. Launcher readiness reported `ready`, with `planning_backend: hermes`. These checks do not execute a live desktop workflow.

Run `.venv-hermes\Scripts\python.exe -m jarvis.hermes_worker --check` for imports and tool isolation without inference. Run `.venv\Scripts\python.exe verify_hermes.py` for read-only live inference. Normal launcher readiness checks Hermes when enabled.
