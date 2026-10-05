# Qwen3.5:9b primary model and native tools

Updated **2026-10-04, Asia/Kolkata**. Restart once through the normal Stop/Start
Jarvis launchers. No model-weight training or new Python dependency was required.

Later on 2026-10-04, Ollama 0.35.1 exposed the same weights only under `latest`;
the exact `qwen3.5:9b` alias was restored. Planning deadlines now align at
300 seconds for HTTP and 330 seconds for the owned worker. Later synthetic
output checks and **843 regression tests** passed. Earlier measurements below
retain their original scope. [Current diagnosis and verification](ollama-output-timeouts.md).

## Download and selection

`ollama pull qwen3.5:9b` completed with digest verification. Installed Ollama
0.32.14 reports GGUF, Q4_K_M, approximately 9.7B parameters and **6,594,474,711
bytes** of downloaded assets. The manifest digest is
`6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7`.
Local `/api/show` confirms completion, vision, tools and thinking capabilities.
See the [Ollama model](https://ollama.com/library/qwen3.5:9b) and upstream
[Qwen model card](https://huggingface.co/Qwen/Qwen3.5-9B), licensed Apache-2.0.
Upstream benchmark scores do not measure Jarvis task accuracy.

In [config.json](../config.json), `knowledge.model`, `knowledge.screen_model`,
`brain.planner`, `brain.coder`, `brain.decision`, `brain.screen_model` and optional
Harness/Hermes model settings select `qwen3.5:9b`. Hermes remains disabled;
Harness remains available to its existing coding/legacy routes. Optional idle
synthesis uses the planner and remains off. Whisper, Kokoro, Piper, Laya and the
optional PC resolver retain their specialist roles. Old downloaded models remain.

`brain.allow_model_fallback: false` prevents silent older-model selection for
missing planner/vision models; questions and coding check their exact configured
model too. Inference remains on CPU (`num_gpu: 0`) to preserve the RTX 3050's
4 GB for Whisper. It fits the observed approximately 32 GB system RAM, with
substantial inference latency.

## Native proposals and execution

`brain.native_tool_calling: true` enables the documented
[Ollama tool-calling API](https://docs.ollama.com/capabilities/tool-calling) for
one-step planning and the configured read-only agent CLI. Real registered
descriptions become native function schemas; `message.tool_calls` becomes a
checked action proposal. Bounded verified results feed back as `role: tool`.
Thinking is disabled and context is sized within 4,096–16,384 tokens. Duplicate
descriptions/results and irrelevant schema fields are reduced.

Exactly one advertised call is accepted. Invented tools, excess arguments,
multiple calls, malformed JSON and truncated output stop before execution.
`jarvis_finish` and `jarvis_clarify` are planner control proposals, not extra
application tools. Finish still needs independent full-goal verification. Model
output cannot grant approval or bypass sensitive-control, exact-text, path,
credential, account-write, cancellation or fresh-state checks. Uncertain
external actions are never automatically replayed.

Jarvis's executor owns desktop input, files, commands and provider calls.
[Step planning](step-planning.md) retains the two-frame lifetime, background
prompt preparation and checked navigation reuse. Direct commands/media fast
paths still bypass unnecessary inference. Coding and ordinary answers retain
their validated generation pipelines with the new model.

## All registered tool categories

**82 application tools** have native schemas. The runtime offers relevant
configured tools first; `tool_search` loads other available tools. Registration
does not establish credentials, provider reachability or live task success.

| Category | Registered operations |
| --- | --- |
| Desktop/media | `open`, `media_control`, `select`, `fill_text`, `scroll`, `shortcut`, `open_menu`, `handle_dialog`, `save_file`, `close_app` |
| Browser | `browse`, `browser_search`, `media_search`, `browser_inspect`, `browser_navigate`, `browser_click`, `browser_fill` |
| Files/terminal | `create_file`, `modify_file`, `delete_file`, `list_files`, `read_file`, `append_file`, `search_files`, `run_command` |
| Planning/coding/development | `think`, `write_spec`, `write_tests`, `write_code`, `improve_code`, `development_native`, `development_status`, `development_verify`, `development_preview`, `development_feedback`, `development_practice` |
| App/tool discovery | `application_search`, `integration_status`, `runtime_capabilities`, `tool_search`, `toolkit_status` |
| Repository/guides | `repository_map`, `repository_instructions`, `skill_list`, `skill_read`, `git_status`, `git_diff`, `git_log`, `read_batch` |
| Approved MCP bridge | `mcp_status`, `mcp_list_tools`, `mcp_call` |
| GitHub | `review_pull_request`, `github_search`, `github_read_file`, `github_pull_request`, `github_pr_files`, `github_add_file`, `github_delete_file` |
| Local knowledge/resources | `knowledge_search`, `query_resource` |
| Public web research | `web_search`, `scrape_web`, `google_search`, `serp_search`, `searx_search`, `firecrawl_search`, `firecrawl_scrape`, `firecrawl_map` |
| Optional account services | `read_email`, `send_email`, `calendar_list`, `calendar_details`, `calendar_create`, `calendar_delete`, `slack_send`, `twitter_send`, `jira_projects`, `jira_search`, `jira_create`, `jira_edit`, `apollo_search` |

`application_search` reads current configured names without launching apps;
executable availability is checked when opening. `integration_status` reports
groups, configured app/guide counts, MCP metadata and missing environment-variable
names, without their values or provider starts.

## Plugins, skills and authorization

The existing [runtime integration guide](codex-runtime-integration.md) covers
project skills, declarative plugin skill bundles and trusted MCP stdio servers.
Local/custom/Hermes guides continue to feed relevant planning. Reference guides
do not install executables or grant credentials. Configure a trusted executable
and exact tool allowlist in `.jarvis/mcp.json` for the existing MCP bridge;
server starts/calls retain its approval requirements. The bridge supports stdio
tools, not remote HTTP MCP, resources or sampling.

Codex connectors/plugins are separate runtimes. Their sign-ins, auth tokens and
app-only tools cannot be automatically exported to Ollama/Jarvis. Compatible
services need their own adapter or configured MCP server and authorization.
Ollama's application launch examples describe separate agent applications;
downloading weights does not install or connect those agents. This update does
not establish every possible plugin as installed or functional.

## Firecrawl setup

Primary model/API research used the explicitly requested Firecrawl Codex plugin.
Jarvis now has three bounded public-read adapters:

- `firecrawl_search`: query and optional `content` JSON `{"limit": 1..5}`.
- `firecrawl_scrape`: one public URL, main-content markdown only.
- `firecrawl_map`: one public site and optional `content` JSON `{"search":"docs"}`;
  at most 20 URLs without subdomain expansion.

These use official v2 [search](https://docs.firecrawl.dev/api-reference/endpoint/search),
[scrape](https://docs.firecrawl.dev/api-reference/endpoint/scrape) and
[map](https://docs.firecrawl.dev/api-reference/endpoint/map) APIs. Set your own
**`JARVIS_FIRECRAWL_KEY`** in Windows user environment variables, then restart
Jarvis. Keep credentials out of the repository and shared logs. The key was
absent during verification; Jarvis's adapters passed mocked HTTP checks, not
a live account test. Existing public search/scrape alternatives remain available.
Service credits/limits depend on the separately authorized account.

No uploads, browser input/scripts or account navigation are exposed. Private,
loopback and credential-bearing URLs are rejected. Existing toolkit response-size
and transport deadlines apply, with no automatic request retry. Retrieved pages
remain untrusted reference data.

Examples: **“Find the configured Notepad application”**, **“Show my integration
status”**, and, after key setup, **“Use Firecrawl to compare public documentation
sources for this topic.”** `toolkit_status` names missing configuration.

## Verification and limits

On **2026-10-04 local time** (artifacts use UTC on 2026-10-03),
[803 regression tests and launcher readiness](../artifacts/qwen9-regression-check.json)
passed. Readiness reports `ready`, `qwen-native-tools` and Qwen3.5:9b for planner
and vision. The 18 new tests cover all schemas, malformed/multiple calls, strict
primary selection, sensitive guards, read-only sessions, long answers/queued
inference, missing keys, cancellation, provider failures and invalid options.

The [real local-model fixture checks](../artifacts/qwen9-check.json) passed:

| Check | Time | Scope |
| --- | ---: | --- |
| Capabilities/tag | 0.000 s | Metadata assertion only; HTTP retrieval time excluded |
| Native metadata read and result feedback | 68.859 s | Two real model calls, one isolated read-only registered dispatch; reported 82 tools |
| Screenshot to native next action | 73.750 s | Correct Advanced tab proposal on an authored fixture; no click |
| Configured coder | 31.188 s | Generated `add(a, b)` parsed successfully; code not executed |

The separate [configured runtime-catalog check](../artifacts/qwen9-catalog-check.json)
also passed: from 32 offered tools the model chose `application_search` for a
Notepad metadata request in **115.187 seconds**. The proposal was validated but
not executed. This is one broader-catalog choice, not evidence that all 82 tools
have been executed successfully by the model.

[Initial history](../artifacts/qwen9-check-history.json) preserves a tool-feedback
timeout. Compact metadata, relevant schema fields and reduced duplication were
then introduced, and the later feedback check passed. These fixtures do not
establish general coding quality, an accuracy percentage, every provider's live
functionality, voice latency or five-second completion. The earlier 4B vision
measurement remains in its original step-planning record.

Reproduce from the app directory:

```powershell
ollama pull qwen3.5:9b
.\.venv\Scripts\python.exe verify_qwen9.py
.\.venv\Scripts\python.exe verify_qwen9_catalog.py
.\.venv\Scripts\python.exe verify_qwen9_regression.py
```

Warm retention remains five minutes; loading and app transitions add time.
Model confidence is not an accuracy percentage. Measure verified outcomes on
representative requests before assigning one.
