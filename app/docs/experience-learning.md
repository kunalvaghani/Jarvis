# Learning from experience

Updated 2026-10-02. Jarvis now keeps useful successful, failed, unverified and uncertain cases alongside its verified procedure memory. A new task retrieves relevant cases, compares their conditions with current observations and uses them as planning references. This feature changes memory and inference context; it does not change model weights or automatically replay old actions.

## Research and implementation

Firecrawl and GitHub were used to review [Memento](https://github.com/Memento-Teams/Memento/tree/42fbbcac63dd58ed6856c0761357345a58e4f032), its [paper](https://arxiv.org/abs/2508.16153), [case retrieval](https://github.com/Memento-Teams/Memento/blob/42fbbcac63dd58ed6856c0761357345a58e4f032/memory/np_memory.py) and [positive/negative prompting](https://github.com/Memento-Teams/Memento/blob/42fbbcac63dd58ed6856c0761357345a58e4f032/client/no_parametric_cbr.py). The reviewed upstream implementation loads an embedding model with Torch/Transformers on CUDA and uses its own model clients and MCP services.

Jarvis uses an independent standard-library adaptation of the case-based approach in [experience_memory.py](../jarvis/experience_memory.py). It integrates with existing task checkpoints, Obsidian procedures and native/Hermes/DeepSeek Harness planning. It does **not** install or run Memento's full agent, embedding model, reinforcement learning algorithm or training system. Retrieval uses word overlap with small verification, condition-match and recency bonuses. This is suitable for a bounded local case bank but is less capable at matching paraphrases than embedding retrieval.

Memento is MIT licensed, copyright 2025 Agent-on-the-Fly; the reviewed [license](../integrations/references/memento/MEMENTO-LICENSE) is retained for attribution. Existing optional Qwen training in this repository is separate. Microsoft Agent Lightning integration remains future work: it would need consented training data, evaluated runs, a training algorithm, compute and held-out evaluation before selecting new weights.

## What Jarvis records

| Case information | Meaning and limits |
| --- | --- |
| Goal, task kind and selected project | Bounded descriptions used to find related cases. Coding cases stay within the same normalized project path. |
| Initial conditions | Observed window title, executable name/fingerprint, UI label/type fingerprint, available tool fingerprint and selected project manifest fingerprint, when available. |
| Verification source and evidence | The independently checked goal checkpoint, with its original scope. Dispatch alone is insufficient. Older checkpoints without a source are labelled `goal_checkpoint`. |
| Failure report and category | Recorded reason, action type and whether the action was not executed or may already have taken effect. Categories are text-based classifications, not independently proven root causes. |
| Observed Close outcome | The window was destroyed, became hidden, remained visible, or observation stopped before a result was established. |
| Verified recovery | A non-executed failure, fresh alternative plan and later verified goal outcome. This does not prove which alternative caused success. |

Executable fingerprints hash the path, size and modification time; they are change indicators rather than semantic app versions or authenticity checks. UI fingerprints hash up to 150 labels/types, excluding IDs, handles, coordinates and editable values. Tool fingerprints describe current adapters. Project fingerprints hash bounded `package.json`, `package-lock.json`, `pyproject.toml`, `requirements/runtime.txt`, `Cargo.toml` and `go.mod` files when readable. They do not detect every application setting, screen layout, source-code change or remote website update. Missing observations remain missing.

If a completed task has fresh goal evidence and no uncertain action, it can be a positive experience. A verified recovery retains its earlier failure report. It does not enter the stricter procedure catalogue, which still requires no failures. Cancelled/interrupted/failed tasks with dispatched actions remain uncertain, even if earlier progress was verified. Startup captures retained interrupted tasks without resuming their actions.

## How cases affect execution

Planning/replanning and coding requests receive up to four relevant cases in `skill_context.experience_context`: up to two positive and two negative/unverified cases, with a 6,000-character case budget. Negative cases have reserved slots so successes cannot bury failure evidence. Context excludes executable plans and action payloads.

Cases list changed and missing conditions and always require fresh inspection. Native, Hermes and DeepSeek Harness planners are instructed to avoid recorded failure patterns and respect each proof's scope. A language model can still ignore a lesson or misunderstand observations; these references are not a guarantee that a mistake never recurs. Existing policies, approvals, current-state action decisions and independent result checks remain responsible for execution.

Exact recent navigation procedures can still avoid initial plan inference, but their recorded conditions must be compatible with the current observations and their latest relevant exact-goal case must be verified. Changed/missing conditions, a newer failed/unverified case, a corrupt case bank or a legacy procedure without a condition baseline requires fresh planning. A later verified success can restore the shortcut. Mutating workflows remain reference-only.

Explicit compiled workflows and simple parsed commands keep their existing handlers; they record outcomes but do not gain a new model planning call. Thus a simple Close command learns its observed behavior without adding planning latency. An uncertain external effect is never replayed automatically.

### Close-window example

After sending one Windows `WM_CLOSE`, Jarvis checks window existence/visibility. If the window becomes hidden, it records **hidden after Close; tray presence and process exit are not established**. If it disappears, Jarvis records that the window no longer exists and still does not claim the process exited. A visible Save prompt or other remaining window does not count as verified completion. The mechanism does not force-terminate processes or infer tray membership.

Later model-planned Close tasks can retrieve this observation and inspect the current application before deciding. An app update that changes its executable or UI fingerprint marks the old case as changed. Closing an app's visible window and fully quitting its background process remain different verification scopes.

Coding evidence also keeps its scope: file readback and Python/JSON syntax checks do not establish functional correctness. Calculator-specific functional checks are labelled separately.

## Configuration and local files

Restart Jarvis once to load the implementation. No additional dependencies, external API keys, background service or training download is required. Existing `memory.enabled` and the configured vault must be usable. [config/config.json](../config/config.json) now includes:

```json
"experience_learning": {
  "enabled": true,
  "max_cases": 300,
  "max_age_days": 90
}
```

This object is nested under `memory`. Omission uses these defaults. `max_cases` is clamped to 20–500 and `max_age_days` to 1–365; invalid numeric options fall back to defaults. Set `enabled` to false to stop case learning/retrieval without disabling other skill memory. Existing files are preserved.

The vault receives `Jarvis Experiences.json` (versioned lookup, latest cases, at most 4 MB) and `Jarvis Experiences.md` (readable case history). `Jarvis Brain` and procedure notes link the experiences. The configured age excludes old cases from retrieval; count/size limits remove old entries from this case index. Existing daily execution logs and procedure notes retain their previous behavior. Ask **“What is in your experience memory?”** for case counts and verification/recovery counts.

Case content stays in the configured local vault; retrieved summaries reach the selected planner, which is currently local Qwen. Credentials identified by the existing filter are redacted. Typed, shell and other action content is omitted; coding goal descriptions retain relevance while quoted source content is omitted. Raw source, screenshots and reusable control identities are not copied to the bank. This is conservative redaction, not a comprehensive personal-information detector: task descriptions, titles, selected project paths and short error summaries may still be personal.

Writes are atomic. Corrupt, oversized or linked vault indexes are preserved and case learning is disabled with a reported error; other valid guidance remains available. A write error never changes a completed external action into a retry. Intentional Stop closes the bank. Repair filesystem availability or inspect/preserve the damaged index, then restart; do not overwrite it blindly.

## Verification

The [verification helper](../scripts/verification/verify_experience_learning.py) uses temporary vaults and synthetic Spotify state, without reading/writing the real configured vault or operating on user apps:

```powershell
.venv\Scripts\python.exe -m scripts.verification.verify_experience_learning
# Optional real local model proposal; still performs no desktop action:
.venv\Scripts\python.exe -m scripts.verification.verify_experience_learning --live-harness
```

Its [result artifact](../artifacts/reports/experience-learning-check.json) records persistence across restart, retrieval of positive/uncertain cases, changed-condition detection, delivery to the planner and any optional inference result. [Regression tests](../tests/test_experience_memory.py) also cover failure-slot retrieval, scoped coding, verified recovery, payload omission, interruption/cancellation, retention, malformed/linked indexes, Stop and injected disk errors. Close tests use controlled Win32 doubles for hidden/destroyed/remaining windows and check that only one close request is submitted. These tests are not live Spotify or desktop success measurements.

2026-10-02 regression/readiness: **618 tests passed in 33.479 seconds**, including 26 case-learning checks. Launcher readiness reported `ready`, no missing components and `deepseek-harness` as planner. All 186 repository-relative links in the two READMEs and the experience/skills guides resolved; `git diff --check` passed. No dependencies or owned-service setup changed.

2026-10-02 isolated feature check: real persistence, restart, positive/uncertain retrieval, changed-layout detection and planner-boundary delivery passed in temporary vaults. One real local Harness/Qwen turn received these persisted cases and proposed `close_app` with expected result `Window hidden` in **79.344 seconds**. It was never executed. These synthetic observations do not establish live Spotify behavior, process termination, a speed advantage, or a measured improvement across repeated user tasks.
