# Hermes skills and route comparison

Updated 2026-10-01.

## Is this the agent in the photographs?

Yes, Jarvis already has [Nous Research Hermes Agent](https://github.com/NousResearch/hermes-agent) installed. It uses the pinned revision `cbc569e23cb045b58b067f37cf5514feb44e0828`. The photographs show Hermes's CLI and Skills Hub commands, apparently with a different model/custom checkout. They cannot establish that exact checkout's source or task speed. This comparison uses our installed local Qwen3.5 4B configuration, not the model shown in the video.

Hermes's agent loop proposes validated plans; Jarvis executes them with its tools and checks. Its standalone desktop, terminal, messaging and skill-management tools are not enabled as a second unrestricted executor. See [integration details](hermes-agent.md). The [official skills documentation](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills) describes on-demand skill documents, platform conditions and required services; a skill document is not itself an installed application or connected account.

## Skills connected to Jarvis and Obsidian

The pinned source includes **58 bundled + 152 optional = 210 upstream reference skills**. All are indexed in [the source manifest](../integrations/profiles/hermes/hermes-skills.json). The real configured Obsidian vault received their full guides and supporting references/helpers under dedicated Jarvis-owned folders. Jarvis still has nine original guides and its existing learned procedures.

- `Jarvis Hermes Skills.md`: complete catalogue with Windows compatibility labels.
- `Jarvis Skills/Hermes/skills/<category>/<name>/`: bundled upstream guide and resources.
- `Jarvis Skills/Hermes/optional-skills/<category>/<name>/`: optional upstream guide and resources.
- `Jarvis Skills/Hermes/UPSTREAM-LICENSE.txt`: upstream attribution. Per-skill metadata and included resource/license files are preserved.
- `Jarvis Skills.md`: link to the Hermes catalogue alongside native workflows and procedures.

**168 declare Windows support; 42 are reference-only on this PC.** Platform compatibility does not verify prerequisites. Skills cover debugging, code review, GitHub, browser work, Obsidian, documents, spreadsheets, research, design, media, productivity and integrations. Some need CLIs, libraries, account setup or paid services. None of those helpers or services was executed, installed or enabled by copying this catalogue. Existing task permissions and the user's free-service preference still apply. No skill marketplace or additional model was installed.

Skill selection uses names, descriptions and tags. General task/coding requests receive relevant full bodies within a **4,000-byte upstream guidance budget**, or metadata pointing to the complete resource. Explicit `$hermes:<name>` or `/hermes-<name>` references use up to 12,000 bytes. Oversized bodies are not silently cut off. Larger guides remain available in full in Obsidian; a smaller supporting reference can be read through the existing tools. Known direct media workflows use their native Jarvis guide without loading unrelated upstream content.

The existing registry adds no tool names: `skill_list` with `folder: "@hermes"` and a query searches Windows-compatible upstream metadata; `skill_read` with that folder, exact skill name and optional relative resource path reads a complete bounded guide/reference. Project-local skill behavior is preserved. Guidance reaches both native Qwen and Hermes planning through the existing skill context, and Qwen3-Coder through coding context. Upstream tool names are reference vocabulary; only currently offered Jarvis tools can execute.

Resources are checked against indexed SHA-256 hashes. Changed copies, traversal and linked paths are rejected. A damaged upstream reference disables that guidance while native guides remain usable. Skill helpers are copied as files, never imported or executed automatically. Source directories and local vault contents stay outside Git; the repository records public metadata and checksums only.

## Initial matched live comparison

[scripts/verification/verify_hermes_comparison.py](../scripts/verification/verify_hermes_comparison.py) ran the same three public YouTube goals through direct compilation, the actual upstream Hermes planning loop and native Qwen planning. Both model planners used the same model weights and the same tool descriptions and memory/skill input. Their existing context settings differ: Hermes 64,000; native 16,384. The script validates the proposed task arguments, executes only the exact public goal through a common owned Chrome backend, and checks the real query/results or selected video/playback. It excludes voice recognition and spoken output.

This measures **planning plus shared execution**, not standalone Hermes's `computer_use` driver or the complete Jarvis vision/replanning loop. There is one trial per goal per route, ordered direct → Hermes → native; browser/model startup, cache, network and memory pressure can affect times. The sample does not establish universal accuracy.

| Initial route | Verified complete goals | Total seconds by case |
| --- | --- | --- |
| Jarvis direct | 1/3 | 4.844; 0.015 failure; 17.360 failure |
| Hermes planning + shared executor | 0/3 | 124.172; 123.329; 124.234 |
| Native Qwen planning + shared executor | 0/3 | 118.328; 120.515; 154.469 |

All Hermes trials timed out. Native Qwen produced one acceptable plan; another plan failed the exact-goal check, and another request timed out. Its acceptable plan's playback was not verified. Direct execution encountered a closed/disconnected browser on case two and a playback timeout on case three. The original report is preserved: [all initial successes/failures](../artifacts/reports/hermes-comparison.json). Playback timeout causes were not established; no click was replayed.

## Direct follow-up and changes

Explicit new browser tasks now recognize a context closure/disconnection even when the page wrapper has not marked itself closed. Background inspection/repair cannot reopen it. General skill retrieval now emphasizes task-specific words, limits body size, and avoids upstream content for a known direct media workflow.

The same three direct tasks were checked again after the browser change: **3/3 verified**, in **4.313, 0.250 and 3.266 seconds**. The last case observed actual non-ad playback, then paused the test video. [Separate follow-up report](../artifacts/reports/hermes-comparison-direct-followup.json). This is a later trial, not a replacement for the failed initial results. The improvement cannot be attributed entirely to code; cache, ads/loading and other runtime conditions may also differ.

## Setup, settings and verification

### Smaller-context follow-up and selected route

After bounding skill context, the first public goal was repeated through all three routes: direct **4.609 s, verified**; Hermes **124.406 s, timeout**; native Qwen **77.360 s, proposal failed the exact-goal check**. [Separate optimized-context report](../artifacts/reports/hermes-comparison-optimized.json). A returned proposal is not task completion.

The selected configuration keeps **direct verified workflows first**, and sets **`brain.hermes.enabled: false`** so other model-planned tasks use native Qwen. Native Qwen returned faster in the latest check, but neither model route demonstrated a verified-completion accuracy advantage. General planning still needs independent result checks and can remain slow. Hermes stays installed and can be explicitly re-enabled for further task-specific evaluation; its skills remain connected. No claim is made that standalone Hermes with another model would produce these same results.

**Final 2026-10-01 regression/readiness:** All **535 tests passed in 41.143 seconds**. Launcher readiness reported `ready`, no missing components, `planning_backend: qwen`. The actual vault synchronization reported nine native guides, 210 Hermes references, zero learned procedures at refresh and a connected catalogue. Synthetic procedures were not added to the real vault. The tools catalogue remains 69 tools / 41 direct operations. Documentation local links and whitespace checks passed. These are separate from the live task measurements.

`memory.hermes_skills: true` enables catalogue retrieval and startup synchronization. `agent_runtime.fast_workflows: true` keeps direct verified workflows first. `brain.hermes.enabled` controls only the model-planning backend; disabling it does not remove Hermes skills, source or installed runtime. Restart Jarvis after changing settings.

Hermes setup now rebuilds the checked skill manifest and preserves an existing planner preference. PyYAML 6.0.3 is declared for the catalogue builder; no new persistent service was added. The existing owned worker cancellation, bounded inference recovery, action checkpointing and no-replay rules remain intact. Vault refresh writes only the dedicated Jarvis reference area.

```powershell
.venv\Scripts\python.exe -m scripts.skills.build_hermes_skill_catalog
.venv\Scripts\python.exe -m scripts.skills.refresh_skill_memory
.venv\Scripts\python.exe -m scripts.skills.refresh_media_memory
.venv\Scripts\python.exe -m unittest discover -s tests -q
.venv\Scripts\python.exe -m jarvis.launcher --check
# Opt-in: opens an owned Chrome window and may play a public video.
.venv\Scripts\python.exe -m scripts.verification.verify_hermes_comparison --live
```

Rerunning the default benchmark overwrites its named report; pass `--output artifacts/<new-name>.json` to preserve previous evidence. `--route` chooses one route and `--cases 1` limits a follow-up to the first public goal. Prerequisite/platform/hash checks, complete reads, cancellation, copying without execution, reserved-source tools, namespace handling and reference-failure isolation have regression coverage. All 210 skill functions have not been executed or benchmarked. No new UI screenshot was generated for this backend change.
