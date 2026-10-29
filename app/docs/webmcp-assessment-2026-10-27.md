# Report B — experimental WebMCP assessment

Updated 2026-10-27 IST. **Experimental adapter retained; production routing disabled.** This browser work does not complete any original autonomous application acceptance gate. [Report A](autonomous-repair-acceptance.md) remains authoritative for those results.

## Installed support and decision

Real isolated launches observed Chrome **155.0.8059.86**, Playwright **1.63.0**, and working CDP. Default Chrome exposed no WebMCP interface. A separate ephemeral headless Chrome process with `--enable-features=WebMCP` exposed `document.modelContext.registerTool`, `getTools` and `executeTool`. `navigator.modelContext`, `navigator.modelContextTesting` and `unregisterTool` were absent in these observations. No normal browser profile, extension, package, model or production setting was changed. [Exact capability and fixture evidence](../artifacts/autonomous-repair/webmcp-assessment.json).

The current [Chrome imperative documentation](https://developer.chrome.com/docs/ai/webmcp/imperative-api) uses the Document interface and origin-bound tool discovery. The [community draft](https://webmachinelearning.github.io/webmcp/) remains experimental. [Playwright's native WebMCP class](https://playwright.dev/docs/api/class-webmcp) documents methods added in1.64, while the installed Python Page/Frame classes have no such member. Its Navigator terminology differs from the actual installed Chrome interface; runtime detection controls the experiment.

Upstream [Chrome DevTools MCP tools](https://raw.githubusercontent.com/ChromeDevTools/chrome-devtools-mcp/main/src/tools/webmcp.ts) include `list_webmcp_tools` and `execute_webmcp_tool`. No new MCP server was installed or started. Jarvis's existing trusted executable, exact allowlist and per-call approval boundaries remain intact. Direct use of the already-owned Playwright Page avoids a package upgrade or another controller.

Chrome's [declarative API](https://developer.chrome.com/docs/ai/webmcp/declarative-api) registers annotated forms, with separate user submission or `toolautosubmit` behavior. This experiment uses imperative registration; declarative execution has not been validated locally. No declarative support claim is inferred from the documentation.

## Adapter and boundaries

[PageTools](../jarvis/webmcp.py) accepts an existing owned Page and defaults to disabled. It creates no browser, scheduler, model or MCP server. Host policy pins exact origin, tool name, input/output schemas and operation. Tool selection is deterministic and requires one eligible match. Site descriptions and annotations never authorize actions; descriptions are omitted from the eligible offer. Every execution requires host authorization, an execution journal and independent result verification. Results remain marked untrusted.

The adapter binds actual document and tool objects, URL and registration epoch; navigation or `toolchange` invalidates the offer. Same-origin child tools are excluded from this main-document adapter. Schema and byte budgets are enforced; unsupported schema features are refused. Missing support is cached within the binding. Discovery is bounded; cancellation and deadlines abort pending execution. An attempted call with uncertain effects retires the binding and never triggers automatic replay or fallback. A fresh workflow must inspect the journal/state before another action.

The actual Chrome fixture returned structured results as JSON text. That encoding is explicitly pinned for the experiment, parsed once and then validated. The adapter does not guess mixed encodings. Hard hung-page/process deadlines, durable integration with the existing worker, capability-registry exposure and production approvals still require integration verification before rollout. There is no production enable flag or new production tool registration.

## Executed checks and matched measurements

The [real-browser fixture driver](../scripts/verification/verify_webmcp.py) passed **25 checks**, including structured search, filtering/sorting, an approved owned form, multi-step selection, dynamic state, registration changes, missing support with actual DOM fallback, invalid schemas/arguments, stale navigation, a new page, child-frame exclusion, timeout, cancellation, permission denial, untrusted descriptions and failed independent verification. These are supervisor-authored controlled fixtures, not Qwen-generated acceptance applications. Earlier failures and execution journals are retained.

Six initial [contract regressions](../tests/test_webmcp.py) passed. A later regression reproduced mutable offers changing internal dispatch metadata; returned offers now copy data, invocation pins the tool name, and lifecycle is rechecked after independent verification. The combined browser/capability/MCP suite then passed **21 tests in5.642 seconds**, including seven WebMCP contract tests. All25 real-browser checks passed again on the final adapter. Launcher readiness still reports DockerEngineUnavailable only, with required installed Ollama models and local Git available. Original calculator regressions are recorded separately in Report A.

Five matched pairs per task used the same owned browser, fixture, initial state, arguments and DOM result checks. The final measurement ran with no active coding inference or regression suite. Each route used zero model calls/tokens. Latest observed medians:

| Task | DOM | WebMCP | Verified trials per route |
| --- | --- | --- | --- |
| Search | 47ms | 31ms | 5 |
| Filters and sorting | 78ms | 62ms | 5 |
| Owned form | 63ms | 47ms | 5 |

Raw samples and min/max are retained in the evidence. Tool execution reduced the fixture's filter/form action count from three DOM actions to one tool call; discovery/polling and verification are included in elapsed time, not counted as user actions. These small local timings do not establish a meaningful production advantage or improved reliability.

CPU/RAM, coding performance impact, full browser restart, delegated cross-origin exposure, multi-step performance, repeated recovery rates and screenshot/vision comparisons are not accepted measurements. Physical desktop tooling remains blocked separately. The rollout decision is therefore **keep disabled**, retain the isolated adapter for further justified testing, and continue the original CLI/GUI-first repair campaign. Websites without WebMCP retain their existing browser acceptance requirements.
