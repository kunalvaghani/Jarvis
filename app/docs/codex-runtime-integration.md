# Agent runtime additions

Updated 2026-09-27. These are independently implemented Python capabilities
inspired by the supplied Codex architecture research and upstream references.
No upstream agent source is imported or executed. Jarvis continues to use its
installed local models, Windows controls, existing coding workflow and recovery.

## What is available

| Capability | Jarvis implementation and scope |
| --- | --- |
| Observe/model/tool loop | Existing desktop planner plus `AgentSession` for headless project research; structured provider responses, tool observations and bounded turns. |
| Instructions | Coding reads root/parent `AGENTS.md` inside the nearest Git boundary, then target ancestors from broad to specific. All target guidance is validated before creating project folders/drafts. In an unversioned folder, scope starts at that folder. |
| Skills | Project `.agents/skills/<name>/SKILL.md` and `.jarvis/skills/<name>/SKILL.md`; `$name` in the coding/research goal explicitly loads the skill. Catalog discovery and `skill_read` are also available. Runtime rules and the user goal override skill text. |
| Plugins | Enabled `.jarvis/plugins/<bundle>/plugin.json` containing `{"enabled":true}` contributes its `skills/` directory. Bundles are declarative skill collections; no plugin code, installation or automatic MCP launch. |
| Tool discovery | `tool_search` ranks configured operations and exposes matches to the next planning step. Saved `agent_runtime.deferred_tools` is true; set false to expose the full configured toolkit catalog. Core desktop tools and discovery/status remain visible. |
| Repository mapping | Python top-level functions/classes and source paths, parsed without importing code. Up to 160 source files, 5,000-character map, sensitive filenames excluded. Application source folders are traversed before vendor/reference/artifact folders so large upstream trees cannot crowd out the application. |
| Git observations | `git_status`, `git_log`, and one-source-file `git_diff`. Fixed argument lists, no shell, external diff/textconv disabled, fsmonitor disabled, ten-second deadline and bounded output. No commit, push, reset or checkout. |
| Tool orchestration | `read_batch` runs at most four independent local observations concurrently and returns ordered per-call results/errors. Rejects writes, arbitrary commands, network tools and nested batches. |
| Events and hooks | Metadata-only `tool.started/completed/failed` JSONL events. Optional app `.jarvis/policy.json` denies tools or defines `before_tool` deny hooks. Hooks cannot execute code, change arguments, grant approvals or retry actions. |
| Context revision | Oversized older observations/references are excerpted with a notice. Original goal, current source and repository instructions remain intact. Durable task state still governs action replay protection. This is deterministic compaction, not an LLM summary or exact token estimator. |
| MCP | Explicitly trusted, enabled app `.jarvis/mcp.json` stdio servers; exact tool allowlist, approval for every server start/call, hidden owned process, initialized handshake, bounded pagination/output, timeout/cancellation and cleanup. No uncertain retry. Supports MCP 2025-11-25 tools only. |
| Headless sessions | Python `AgentSession` SDK, local Ollama provider, CLI and custom JSONL stdio API; source inspection only, no microphone/HUD required. Explicit relative file-read requests obtain registry observations before inference; unsupported/missing reads withhold completion. Conflicting answer/tool responses receive bounded correction without executing the rejected call. Resume restores conversation context and never replays calls. |
| Read-only agents | `research_parallel` / `team.run` runs at most three agents with separate histories and one-to-six model steps each. No shared desktop actions or file editing. Fork copies conversational context into a new session. Local Ollama request deadlines cover queued CPU work: 150 seconds per ordinary request, multiplied by team size, capped at 600 seconds. |
| Checked editing | Existing exact unique replacements, Python/JSON syntax checks, interface-preservation checks, in-memory inference correction, original-byte backups, diffs, atomic per-file writes and readback. Now receives instructions, selected skills and symbol map. |
| Safety/recovery | Existing visible shell/deletion/account approvals, durable task checkpoints, safe resume blockers, hidden launcher and service watchdog continue to apply. New observations are not a task replay queue. |

The registry now has **64 operations: 15 core + 37 earlier toolkit adapters + 12
agent/MCP operations**. Forty-six have no required account environment variables;
that count includes three MCP wrappers whose actual usefulness depends on local
server configuration, trust and approvals. Eighteen earlier account tools remain
credential-gated. Discovery does not verify a provider is reachable or a model is installed.

## Usage

The existing explicit toolkit syntax works in the text task input:

```text
tool repository_map {"value":".","folder":"Demo"}
tool git_status {"value":".","folder":"Demo"}
tool git_diff {"value":"main.py","folder":"Demo"}
tool skill_list {"value":".","folder":"Demo"}
tool tool_search {"value":"Git diff"}
tool read_batch {"value":".","folder":"Demo","content":"{\"calls\":[{\"action\":\"repository_map\",\"value\":\".\"},{\"action\":\"git_status\",\"value\":\".\"}]}"}
```

Copy the [example skill](../examples/skills/code-review/SKILL.md) into the target
project's `.agents/skills/code-review/SKILL.md`, then use a coding goal such as
`Modify main.py using $code-review to improve error handling`. Skill frontmatter
supports single-line `name` and `description`; names must be unique. Instruction
files are capped at 8,000 bytes each with a 6,000-character aggregate budget;
selected skill bodies have a separate 6,000-character aggregate budget. Oversized
or unreadable required guidance fails before edits rather than silently disappearing.

From the application directory:

```powershell
.\.venv\Scripts\python.exe -m jarvis.agent_cli --project . --goal "Map this project and explain the coding workflow"
.\.venv\Scripts\python.exe -m jarvis.agent_cli --project . --session <returned-session-id> --goal "Explain the previous finding"
.\.venv\Scripts\python.exe -m jarvis.agent_cli --project . --serve
.\.venv\Scripts\python.exe -m scripts.verification.verify_agent_runtime
.\.venv\Scripts\python.exe -m scripts.verification.verify_agent_runtime --live
```

The CLI needs an already-running local Ollama instance for inference and defaults
to `qwen3.5:4b`; `--model` explicitly changes that provider selection. The fixture
verification command needs no model. `--max-steps` is 1–20 (default 12).
All CLI output is JSONL. The stdio API accepts one JSON object per input line:

Explicit source-reading requests inspect up to eight named relative files through
the normal policy/scope checks before model inference. Explicit repository-map
requests and Git status/log read batches also obtain fresh evidence first.
The agent withholds premature answers when requested reads/tools lack successful
observations. This protects against an observed small-model failure where it
claimed to have read source without issuing a tool call; it does not establish
that every subsequent interpretation of source is correct.

```json
{"id":1,"method":"session.info"}
{"id":2,"method":"tool.list"}
{"id":3,"method":"turn.run","goal":"Read main.py and describe its entry point"}
{"id":4,"method":"session.fork"}
{"id":5,"method":"team.run","goals":["Map Python interfaces","Inspect repository guidance"]}
```

Lifecycle event lines can arrive before the matching `id` response. This is
Jarvis's small stdio API, not Codex app-server, ACP or an MCP server. Session ids
are 32 hexadecimal characters. Project scope must match when resuming; use the
returned fork id with a new CLI invocation to continue the fork. Python callers
may inject a different provider callable returning `{"final":"...","calls":[]}`
or one read tool in `calls`. Concurrent research requires a thread-safe provider.

## MCP and policy configuration

Copy [the disabled MCP example](../examples/mcp.example.json) to app
`.jarvis/mcp.json`, review the executable/server, replace paths and allowlisted
names, then explicitly set `enabled` and `trusted` to true. Executables must be
absolute files; scripts use an absolute interpreter plus script in `args`.
Shell scripts/batch launchers are refused. `env_names` lists environment variable
names to forward; never place secret values in the JSON or documentation.

```text
tool mcp_status {"value":"."}
tool mcp_list_tools {"value":"example"}
tool mcp_call {"value":"example","content":"{\"name\":\"exact_tool_name\",\"arguments\":{}}"}
```

MCP approval shows the server executable, configured arguments and exact call.
Discovery itself starts executable code and therefore also requires approval.
The server starts for one toolkit invocation and is closed afterward; no new
persistent supervised service is installed. Timeout is 1–60 seconds per protocol
operation, with at most five tool-list pages/100 entries and 1 MB total stdout.
MCP failure preserves uncertain task checkpoints; neither the bridge nor recovery
reissues a call. Tool annotations never waive approval. Server descriptions and
results remain untrusted. The selected stdio protocol version must negotiate
exactly; other versions, HTTP/SSE, resources, prompts, sampling and elicitation
are unsupported. An MCP server is a trusted executable with host access, not an OS
sandbox. Only its directly owned process is terminated; shared processes are untouched.

Copy [the policy example](../examples/agent-policy.json) to app `.jarvis/policy.json`
to enable those deny rules. Invalid policy fails closed. No policy file means
the existing authorization rules apply. The headless agent uses the same policy
and registry, but its tool surface independently excludes all writes/desktop/network tools.

## Persistence and limits

Tool audit metadata is stored in `.jarvis-runtime/agent-events.jsonl`; arguments,
source contents, responses and error messages are omitted. Session files under
`.jarvis-runtime/sessions/<id>.jsonl` retain user goals and final answers, plus
metadata events; intermediate source/tool contents stay in volatile context.
Session files are capped at 2 MB. These paths and Firecrawl excerpts are ignored
by Git. Goals and answers can still contain private information: treat local
session files as user data. No new UI assets or screenshots were needed.

Arbitrary JavaScript Code Mode, a real filesystem/network OS sandbox, remote
execution, unattended external writes, write-capable multi-agent scheduling,
Codex SDK/app-server protocol compatibility, proprietary weights/reasoning and
hosted account infrastructure are not implemented. Read batches provide controlled
orchestration without `eval`; read-only agents provide parallel research without
competing for the user's desktop. Existing coding limits remain three files and
three new folders per plan; other languages receive source output without a
functional build claim. Local small-model reliability must be checked separately.

## Supplied research coverage and upstream evidence

The document's implementation-oriented sections are mapped here so runtime
features are distinguished from language/build details and unavailable services:

| Supplied sections | Coverage |
| --- | --- |
| 1, 4–9, 34–36 | Existing desktop loop plus new headless provider/loop and structured sessions; no claim to reproduce Codex internal call names or transport. |
| 2–3 | Jarvis remains Python. No Rust rewrite or unrestricted embedded V8; controlled read batches substitute for a limited portion of Code Mode orchestration. |
| 10–15 | Shared tool specs/router, deferred catalog, tool search, validation and dispatch. |
| 16 | Existing exact replacement patching/backups; no arbitrary Codex apply_patch compatibility or deletion patches. |
| 17–18 | Existing approvals plus scope/deny policies; no OS sandbox claim. |
| 19–20 | Bounded observations, deterministic excerpts and durable state; no model-driven summarization. |
| 21–25 | Hierarchical repository guidance, explicit local skills and progressive discovery. |
| 26–28 | Approved stdio MCP, declarative plugin skill bundles, metadata events and deny hooks. |
| 29–33 | Bounded read-only agents, events, resumable/forked sessions and headless stdio API; no remote exec server or Codex/ACP compatibility. |
| 37–44 | Reference designs reviewed below, independently adapted to Jarvis; full upstream products are not bundled. |

Firecrawl retrieved these primary sources on **2026-09-27**; bounded local research
excerpts are saved in ignored `.firecrawl/agent-reference-*.md`. No upstream source
port was made, and upstream licenses do not become a blanket Jarvis license.

- [Codex core](https://github.com/openai/codex/blob/main/codex-rs/core/README.md): real platform sandbox policies; our checks are narrower application policy.
- [Codex tools](https://github.com/openai/codex/blob/main/codex-rs/tools/README.md): shared host-facing tool contracts and discovery.
- [Codex app-server](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md): protocol/events reference; Jarvis does not implement that protocol.
- [Goose architecture](https://github.com/aaif-goose/goose/blob/main/documentation/docs/goose-architecture/goose-architecture.md): interface/agent/extensions, MCP, error observations and context revision.
- [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent): compact model/action/observation loop and portable provider concept.
- [SWE-agent](https://github.com/SWE-agent/SWE-agent): configurable environments; current README directs new development toward mini-swe-agent.
- [Aider](https://github.com/Aider-AI/aider): repository maps, focused edits and Git review.
- [OpenHands](https://github.com/OpenHands/OpenHands): current repository describes Agent Canvas; SDK/agent-server ownership now lives in separate repositories. No server/backend deployment was installed.
- [Grok Build](https://github.com/xai-org/grok-build): Rust terminal/headless runtime, skills/plugins/hooks and protocol reference; no source port or CLI installation.
- [MCP stdio specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports): newline-delimited JSON-RPC transport used by the limited bridge.

## Verification

Run `python -m unittest discover -s tests`, `python -m scripts.verification.verify_agent_runtime`, and
`python -m jarvis.launcher --check` from the app directory. Optional `--live`
checks source inspection with the installed local model in a temporary fixture;
it performs no desktop, microphone, account or real MCP-provider actions.
Regression tests include real fixture stdio handshake/call, timeout, blocked
stdin, malformed/oversized output, cancellation, owned-process cleanup, denied
approval, allowlist rejection, policy hooks, scope, read batches, source guidance,
session resume/fork and isolated research-agent failures. Dated observed results
are recorded in [the application README](../README.md#current-validation-and-update-history).

`python -m scripts.verification.verify_real_world` runs thirteen live acceptance tasks against the
installed local model, the actual repository, real disk writes in a newly created
test workspace, official Python documentation and a generated three-file expense
application. It saves raw dated results under `artifacts/real-world-<UTC timestamp>/`.
No model or tool output is mocked. It starts a hidden test-owned Ollama server if
needed, stops only that owned server afterward, and reuses any existing server.
Microphone, desktop clicks and real third-party MCP/account writes are outside
this test's scope. Failed baseline attempts remain separate from corrected reruns.
For focused reruns, use `--tasks 6,7,8,9,10,12,13`; each run creates a fresh
workspace. Run conversation tests 7–9 together. Tool evidence and required answer
terms are checked automatically; those checks do not prove every sentence is
correct. Review the saved answers as well as the status. The generated application
faces ten real CLI cases for normal totals, refunds, decimal precision, blank
categories, empty input, invalid amounts, missing headers, quoted fields,
header-only invalid input and nonfinite amounts, with source CSV
preservation checked. Generated coding responses are retained for diagnosis.

The public-page `scrape_web` tool now excludes navigation/hidden content and
accepts optional JSON `content` such as `{"query":"json.loads"}` to return a
bounded excerpt around a literal match. Omitted text is marked. It does not
execute JavaScript or load authenticated browser content.

Local Qwen inference inspects `/api/show` metadata once per HTTP client/model.
When the installed template is only `{{ .Prompt }}`, the shared text client uses
the existing raw Qwen role-delimiter format so system guidance is included.
Native chat templates retain `/api/chat`. The model and its template are never
modified. Headless research uses the same client and keeps its bounded request
deadline. See [live findings and limits](real-world-validation.md).
