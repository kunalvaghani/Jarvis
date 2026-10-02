# Runtime tools, skills and program memory

Implemented and checked **2026-10-01**. This connects the existing Obsidian catalogue and skill library to runtime discovery and planning. It adds no dependencies or services.

## How selection works

`jarvis/capabilities.py` recognizes task families and ranks real registered tools using task terms, intent associations and tool names referenced by relevant guides. It supplements the existing keyword search; it is a local selector, not a new trained model. The planner still decides arguments and remaining steps from current observations.

| Task | Runtime context and tools |
| --- | --- |
| Coding and debugging | Repository instructions/map, file reads, project skills, Git observations and code/test drafts. The existing Qwen coding runner generates and validates saved files with streaming. |
| Browser automation | DOM inspection/navigation/fill/click, with inspection retained as a prerequisite. |
| YouTube and Spotify | Their own media guides and search/control adapters. Existing direct workflows run first; Spotify retains native app preference. |
| Files and folders | Open, list, search and read; edits retain a read prerequisite. |
| Research and GitHub | Public search/page extraction and repository/PR reads; updates still use approved tools. |
| Integrations | MCP status/discovery/calls, email, calendar, Jira and Slack where applicable. Missing environment configuration is reported by variable **name only**. |

`ToolRegistry.search` and deferred `catalog(goal)` share this selector. Task scopes filter both discovery and catalogues. Relevant guides can bind known tool names, including through optional `tools: [...]` metadata. Unknown names never become executable handlers. Discovery retains prerequisites even if this makes the default 12-result list slightly longer, with a hard maximum of 30. Tools discovered earlier in the same task remain available for replanning.

The new read-only **`runtime_capabilities`** tool returns selected tools, local guide references, matching rechecked program references and missing provider configuration. It loads discovered tools for subsequent planning without starting programs or executing task steps. Ordinary planning/replanning and coding requests also receive bounded `capability_context`; coding keeps executable tool catalogues out of its generation prompt and continues through its existing runner. Optional Hermes planning receives the same context.

Relevant native and personal guide bodies and verified learned procedures still reach tasks through `skill_context`. The existing 210 pinned Hermes guides/resources remain reference guidance, with platform/prerequisite checks and bounded retrieval. This change does not turn upstream helper scripts, paid services or unconfigured integrations into runnable tools. Tool execution continues to enforce policy, current scope, cancellation and approvals; uncertain actions are never replayed.

## Personal skills directly in Obsidian

Create `Jarvis Skills/Personal/<name>/SKILL.md` in the configured vault. For example:

```markdown
---
name: focus-session
description: Prepare a focused study session in the selected project.
tools: [repository_map, read_file, search_files]
---

Inspect the current project and relevant notes. Use current paths and tools.
Verify the requested result and adapt previous steps to fresh observations.
```

Use **“Jarvis, use $custom:focus-session …”** or a task matching its description. Source guides under Jarvis's `custom-skills/<name>/SKILL.md` also reload during discovery, context retrieval and `skill_list`/`skill_read folder=@jarvis`. New/changed/deleted guides are detected without restarting once this upgrade is loaded. Guide bodies remain bounded to 8,000 bytes, with at most 50 per source. Duplicate names, linked paths and invalid metadata report errors; personal guides cannot replace bundled names. Explicit project `$name` and upstream `$hermes:name` namespaces are unchanged.

`Jarvis Skills/Personal` contains user-authored sources. `Jarvis Skills/Builtins` and `Jarvis Skills/Custom` are synchronized copies of application sources; edit the original source for those guides. Runtime hot reload does not automatically rewrite catalogue notes on each lookup. Run `refresh_skill_memory.py` to refresh their Obsidian links and current tool notes.

`Jarvis Runtime Capabilities.md` is linked from the Brain and Skills notes and describes task routing, registered tools and guide bindings. The current tool note refresh preserves the historical project/app scan timestamp; it does not claim that those inventories were rescanned.

## Programs remembered by Jarvis

The existing `Jarvis Index.json` reloads when it changes. Exact normalized saved app names can now launch through `open` when no configured alias matches. Existing absolute `.exe` or `.lnk` paths are rechecked each time; canonical AppsFolder IDs must have valid syntax. Install directories, missing paths, Python scripts and strings containing command arguments are not launch targets. Duplicate entries for one launch target collapse; multiple distinct targets require an explicit executable path. Configured aliases take precedence and memory launchers are not permanently added to configuration.

App retrieval excludes generic task words and uses whole phrase boundaries, reducing unrelated catalogue matches. Shell ID syntax is not proof that an app remains installed. Launch dispatch is not independent task completion evidence; the existing focus and task-result checks still apply. This does not inventory every portable program or automatically run Python/Git/npm commands. Requested command/test execution retains the existing approval and coding verification rules.

## Research basis

Firecrawl was used to read the official [Hermes tool-search documentation](https://hermes-agent.nousresearch.com/docs/user-guide/features/tool-search) and [Agent Skills integration guide](https://agentskills.io/client-implementation/adding-skills-support). Their metadata discovery, selective guide loading and real-tool availability patterns informed this independent Jarvis implementation. The pinned installed Hermes revision is unchanged. Firecrawl research access in Codex is separate from Jarvis's runtime integrations; this update uses its existing public web adapters and does not add Firecrawl credentials or paid calls.

## Verification and limits

- **2026-10-01 regression/readiness:** all **566 tests passed in 30.771 seconds**, including 11 new routing, prerequisite, scope, unavailable-provider, hot-reload, stale-path, dispatch and no-replay checks. Existing coding and desktop regressions passed. Launcher readiness reported `ready`, no missing components and native Qwen planning. The snapshot refresh required a rerun outside the filesystem sandbox after its initial copy failed. Documentation links and `git diff --check` passed.
- **Actual configured memory retrieval:** [seven routing checks](../artifacts/runtime-capabilities-check.json) found all expected tool/guide combinations. Across 70 retrieval preparations, median **21.861 ms**, maximum **54.900 ms**. This includes catalogue selection, relevant memory and skill retrieval; it excludes inference, voice, app launch and task execution.
- **Actual Obsidian refresh:** nine local guides, 210 Hermes references, 70 registered tools and the linked runtime capability note were connected, with zero guide errors. Existing learned procedures were preserved; no synthetic procedure was added to the real vault.

These checks do not establish end-to-end model planning accuracy, live program launch success, or a five-second guarantee. Existing measured [media automation](automation-upgrade.md) and [CPU coding latency](streaming-coding.md) retain their original context. Restart Jarvis once to load this code upgrade; subsequent personal guide edits reload at runtime.
