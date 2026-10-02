# Skills and execution learning

Updated 2026-10-02. Jarvis retrieves relevant workflow guidance and learns procedures from verified task completion, using the configured Obsidian vault. [Experience learning](experience-learning.md) now adds successful and failed cases, condition comparisons and scoped recovery evidence. This supplements the existing tool/app/project inventory and explicitly selected project skills.

## Research and design

Firecrawl was used to read the [Agent Skills specification](https://agentskills.io/specification), [reference repository](https://github.com/agentskills/agentskills) and [Hermes skills documentation](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills). The specification uses a skill directory containing `SKILL.md`, with name/description metadata and optional supporting resources. Metadata supports discovery before loading the relevant body. Hermes documents on-demand skills and workflow learning. Jarvis implements its own small procedure layer around its existing executor; no upstream scripts or skill marketplace packages are automatically executed.

The nine current Jarvis guides are in [skills](../skills/): YouTube, Spotify, project coding, file operations, app navigation, web research, form entry, runtime questions and browser navigation. The procedure-memory layer requires no paid service or model training. The browser upgrade adds Playwright; see [automation setup and verification](automation-upgrade.md).

## Obsidian files and usage

The existing `memory.enabled` and `memory.vault` settings in [config.json](../config.json) control this integration. Startup synchronizes these dedicated Jarvis-owned notes:

- `Jarvis Skills.md`: linked catalogue of available workflows.
- `Jarvis Skills/Builtins/<name>/SKILL.md`: copies of the bundled guides, refreshed on startup.
- `Jarvis Procedures.md` and `Jarvis Procedures.json`: successful routes, revision counts, latest verification scope and last-attempt status.
- `Jarvis Skills/Learned/procedure-<id>/SKILL.md`: human-readable guidance for each successful workflow.
- `Jarvis Executions/YYYY-MM-DD.jsonl`: sanitized attempt records, using UTC dates.
- `Jarvis Experiences.json` and `Jarvis Experiences.md`: bounded case bank with conditions, reported failures, observed outcomes and verified recoveries.

Jarvis Brain links the catalogue and procedures for Obsidian graph navigation. Ask “What skills do you have?” for the current list. Relevant procedures can also appear in recall questions about previous steps. Run `.venv\Scripts\python.exe refresh_skill_memory.py` from the application folder to refresh the owned skill notes without launching Jarvis. The configured vault must be writable.

For project-specific skills, keep using `.agents/skills/<name>/SKILL.md` or `.jarvis/skills/<name>/SKILL.md` in the selected project and explicitly name `$name` in the coding request. This preserves the existing project guidance contract. Bundled Jarvis guides are matched automatically; arbitrary downloaded scripts do not gain execution authority.

## Adding personal skills

Global personal guides now live in `custom-skills/<name>/SKILL.md` inside the Jarvis application folder. They apply across tasks and coding. Run from that folder:

```powershell
.venv\Scripts\python.exe add_skill.py focus-session --description "Open my project and prepare a focus work session"
```

Edit the generated `custom-skills/focus-session/SKILL.md` with ordered steps, relevant tool names, when it applies, and a visible completion check. Keep matching name and one-line description metadata:

```markdown
---
name: focus-session
description: Open my project and prepare a focus work session
---

# Workflow

Ask for the project only if it is not named in the request or current context.
Resolve its existing folder. Use the open tool with its full path.
Inspect the fresh Explorer folder before reporting it is ready.
```

To supply an existing instruction file, add `--instructions-file "path\to\instructions.md"` to the creation command. The helper refuses to overwrite an existing guide. Names use lowercase letters/digits and hyphens, at most 64 characters; the complete guide must fit 8,000 UTF-8 bytes. Up to 50 personal guides are discovered alongside up to 50 bundled guides. Personal guides cannot replace bundled names. Invalid/duplicate/oversized guides are reported under **Guides needing correction** in the Obsidian skill catalogue while other guides remain available.

Guides now reload during runtime discovery/context retrieval after this upgrade is loaded. Startup copies application guides to `Jarvis Skills/Custom/<name>/SKILL.md` and links them from `Jarvis Skills.md`. You can also author guides directly under the vault's `Jarvis Skills/Personal/<name>/SKILL.md`, with optional `tools: [read_file, search_files]` bindings to registered tools. Personal source guides are preserved during synchronization. See [runtime capabilities](runtime-capabilities.md) for routing, source locations and limits. To refresh the Obsidian catalogue notes immediately, run:

```powershell
.venv\Scripts\python.exe refresh_skill_memory.py
```

The application file is the editable source; the vault copy is refreshed from it. The `custom-skills` contents are Git-ignored. Describe a matching task for automatic relevance matching, or explicitly request **“Use $custom:focus-session …”**. Explicit custom selection gets priority in the bounded two-guide context. Project `$name` and upstream `$hermes:name` remain separate namespaces. Planners can use `skill_list`/`skill_read` with `folder=@jarvis` to discover/read loaded local guides.

A skill supplies planning guidance. Adding an API/app capability still requires implementing/configuring its tool. Guides do not automatically execute supporting scripts, install missing integrations or guarantee fixed latency. Verification, cancellation and approvals apply to custom guides and learned procedures.

## Learning and reuse

1. Direct commands record their handler outcome; managed desktop/media/coding tasks record their checkpoints and completion status.
2. A completed task becomes a procedure only after a separate `goal_verified` checkpoint, with no recorded failures. Action dispatch and partial progress are insufficient.
3. Another verified success replaces the current step reference and increments its revision/success count. Daily logs preserve prior attempts. Failure leaves the last successful steps intact and flags them for fresh inspection.
4. Planning/replanning and coding receive up to two relevant guide bodies and three matching procedure references. Coding procedures are scoped to the selected project. The in-memory lookup index retains the latest 500 procedures; older procedure notes and execution logs remain in the vault.
5. Exact navigation requests can skip initial plan inference and its initial visual summary when a recent successful proposal matches the current window title and recorded case conditions. This is limited to opening, searching and scrolling, requires named arguments from the new request, and expires after 14 days. Changed/missing conditions, a newer failed/unverified case or a legacy procedure without a baseline requires fresh planning. The existing plan validation, policy, fresh observations, action decisions and independent verification still run. A failed later attempt disables this shortcut until another verified success.
6. Planning/replanning and coding additionally receive up to four relevant experiences, including negative cases. A completed, independently verified recovery can become a positive case while retaining its failure report; it does not replace the stricter no-failures procedure recipe. See [case retrieval, proof scopes and configuration](experience-learning.md).

Similar requests and changed window titles use the saved route as planner reference. Edits, commands, submissions and coding require fresh planning. Separately, supported explicit media/native-app workflows compile directly and exact unique user-named controls can avoid decision-model inference; all retain fresh result checks. See [automation upgrade](automation-upgrade.md). Saved target descriptions never become reusable control IDs, window handles, coordinates, approvals or verification results. An uncertain external action is never automatically replayed. Simple parsed commands retain their existing fast handlers.

Coding verification explicitly reports its scope: file readback and Python/JSON syntax checks are not proof of functional correctness. The calculator creation path records its actual functional checks when those pass. A direct command without independent goal verification is logged but does not become a verified procedure.

Obvious credential-bearing text is redacted. Typed and shell payloads are omitted from procedure goals/results and reusable proposals; generated source/content and screen images are not copied into recipe steps. This is conservative redaction rather than a general detector of all personal information: requested task descriptions and short outcome summaries can still contain personal context. These vault files remain local and are not included in repository documentation.

Corrupt procedure indexes are preserved, learning is suspended, and skill-memory questions report the error. Memory write failures are exposed through the existing memory error field and do not turn a completed action into a replay. Intentional Stop closes the learning layer. Restart after repairing filesystem availability; preserve and inspect a malformed index rather than blindly overwriting it.

## Verification

Initial 2026-10-01 installation: the real configured Obsidian vault received all eight guides and the linked catalogue. It contained zero verified learned procedures at installation; synthetic test procedures were kept in temporary vaults.

The [local lookup measurement](../artifacts/skill-lookup-check.json) averaged 0.0492 ms across 1,000 lookups with eight guides in a temporary vault. It excludes model inference, UI observation, network calls and desktop actions. No claim is made that every task finishes in five seconds. Saved procedures reduce repeated discovery/planning; full execution speed and live desktop accuracy need a visible interactive desktop and actual task measurements.

2026-10-01 regression/readiness: all 501 tests passed (31.441 seconds), including 12 new checks for success revisions, failed/partial/uncertain attempts, project scoping, payload redaction, corrupted memory, Stop, write failure isolation, proposal expiry/changed targets and planner/coder context delivery. Launcher readiness reported `ready`, no missing components, and Hermes as the planning backend. `git diff --check` passed. These are regression and readiness checks, not live desktop task-success measurements.

**Later automation upgrade, 2026-10-01:** The actual vault was refreshed to nine guides and 69 tools / 41 direct operations. The measured live YouTube and native Spotify tasks used temporary task journals; no synthetic success was inserted into the actual procedure catalogue. Those live measurements and later regression results are in [automation upgrade](automation-upgrade.md). Normal verified Jarvis tasks still update the real vault.

**Hermes reference integration, 2026-10-01:** 210 pinned upstream guides and supporting files were copied to the real vault, with 168 declaring Windows support. Relevant full bodies/metadata reach tasks and coding within a bounded context budget; helpers and unavailable services are not automatically executed. Native nine-guide learning and success revision rules remain intact. [Source inventory, retrieval, requirements and comparison](hermes-skills-and-comparison.md).
