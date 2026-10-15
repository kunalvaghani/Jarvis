# Turning learned repositories into new Jarvis abilities

2026-10-15 IST resource follow-up: initial model selection checks installed model
size plus the configured RAM margin for both the30B preference and9B fallback.
If neither fits or capacity cannot be read, it reports a deferred inference rather
than selecting an unfittable fallback. This is an admission heuristic, not a peak
RAM guarantee; no30B native load or new ability installation was run for this
audit. [Cases and limitations](../artifacts/jarvis-audit/modules/08-gpu-scheduler/inventory.md).

Updated 2026-10-11 IST. When Jarvis learns a GitHub repository (see [repo-learning.md](repo-learning.md)), it now
also breaks the repository down into **abilities**: new spoken commands that do what the repository was made to
do. Learning `trentm/python-markdown2`, for example, gave Jarvis "convert notes.md to html" and "extract headings
from notes.md". All of this happens in the background, Jarvis's own code is never edited, and **every ability is
shown to you on the island, one at a time, before it is added**.

## Approving abilities on the island (follow-up, 2026-10-11 IST)

When an ability is ready, the island opens the **Approval** panel ("Approval required · learned ability"). It shows:

- the repository it came from;
- **Ability:** its name;
- **What it does:** a short summary;
- **Command:** the phrases you can say, e.g. `"convert <file> to html"`;
- **Inputs** and **Output** (a spoken answer and/or a file in `JarvisFiles/Abilities`);
- **Uses:** standard library only, or the packages, repository code or internet access it needs;
- **How it works:** the plan;
- its **self-test result**, or that it runs after you approve (when it needs packages);
- the **complete code** (`ability.py`), scrollable.

Click **Approve exact action** or **Deny**, or say "approve" / "reject":

| Your answer | What happens |
| --- | --- |
| Approve | Packages (if any) are installed into the ability's own environment, it is tested, and it is added to Jarvis for good. The island says **Added ability: … Say "…"**. If the install or test fails, it is not added and Jarvis is unchanged. |
| Deny | It is discarded ("Discarded: …"; files are kept under `.jarvis-runtime`), and Jarvis builds the next ability of that repository, or finishes. |
| No answer (the card lapses after 3 minutes) or Jarvis closes | Not a denial: it stays **waiting**. Jarvis shows it again about 90 seconds after the next start and then every 20 minutes while idle, up to three times; after that only when you say "show pending abilities". |

The builder waits for your answer before building the next ability, so cards never pile up.

**What changed from the first version:**

- Standard-library abilities used to switch on by themselves; now every ability waits for your OK.
- Learning no longer gives up on large repositories. `deepseek-ai/deepseek-harness` (273 MB) was refused as too
  large, so nothing happened after "build abilities from …". Repositories over the download limit are now read
  from one file-list API call plus the README, manifests and up to 45 key source files fetched from
  raw.githubusercontent.com (2.5 MB at most, no API quota).
- Failures are no longer only a passing card. They are kept, "list your abilities" says why (for example "Couldn't
  use big/repo (GitHub rate limit reached)"), and Jarvis says it out loud when you had asked for that repository.
- "build abilities from deepseek harness" and "… from deepseek-harness/repo" are looked up on GitHub. A placeholder
  such as "owner/repo" means the repository open in your browser.
- "learn this" / "learn it" learns the repository on screen; it used to go to the chat model.
- If the GitHub check for a viewed repository fails (rate limit or network), it is retried after a minute instead
  of being dropped.
- A repository learned before abilities existed gets its abilities built the next time you view it.

## How it works (`jarvis/repo_abilities.py`, `jarvis/ability_runner.py`)

1. **Break it down.** After a repository is saved to memory, a local coding model reads what was learned (purpose,
   README, structure, Python modules, manifests) and proposes up to two abilities. Each one has a name, 2–4 spoken
   command templates such as `convert {file} to html`, typed inputs (text, file, URL, number; they can be
   alternatives), the output (text, a file, or both), and an approach:
   - `standalone`: re-implements the idea with the Python standard library;
   - `packages`: uses PyPI packages;
   - `repo_code`: imports the repository's own Python modules.

   Frameworks, link lists, graphical apps, games, servers, anything needing accounts or keys, and anything that
   changes your existing files or system settings are skipped.
2. **Generate.** The model writes one file, `ability.py`, with `run(inputs, workdir)` and
   `sample_inputs(workdir)`, using the repository's key files as reference.
3. **Static check.** The file must parse and define both functions. It may not use processes, `eval`/`exec`,
   `ctypes`, the registry, `importlib`, `pickle` or `input()`, and may not import modules that are neither standard
   library nor declared. Network modules are allowed only when the ability declared network use.
4. **Test out of process.** The ability runs in its own Python process and virtual environment (`python -I -B`,
   cleared environment, hidden window), with a time and memory limit. Before the ability loads, an audit hook
   refuses:
   - new processes;
   - writes, deletes or renames outside its run folder and its own home folder;
   - reads outside Python, the ability, its run folder and Windows' own folders;
   - registry writes;
   - network connections, unless network use was approved.

   `sample_inputs()` builds test data, and `run()` must return the promised text or files. A failure, with its
   traceback, goes back to the model for up to two repairs.
5. **Merge atomically.** A passing ability gets a version folder (`v1`, `v2`, …). It is switched on, after you
   approve it, with a single registry write. Until then nothing changes. If Jarvis is closed mid-build, the unfinished build is simply not
   merged, and it starts again on the next launch. When an update fails, the working version stays live.

**What needs your OK.** Everything (see above). Standard-library abilities are tested before the card is shown. An
ability that installs packages, runs the repository's own code, or uses the internet is shown untested, and nothing
is installed or run until you approve. Packages are installed as binary wheels only (`--only-binary=:all:`, so no
package build scripts run) into that ability's own environment, never into Jarvis's.

**Built-in commands always win.** Learned phrases are matched after Jarvis's own commands. The one exception is the
general-question catch-all, which a learned phrase is allowed to beat: "convert notes.md to html" runs the ability,
while "convert 5 km to miles" is still answered as a question. At activation, any template that a specific built-in
command already understands (for example `open {file}`) is dropped.

**Keep Jarvis open.** While it builds, the island shows **Building … — keep Jarvis open**, then each step: breaking
the repository into abilities, writing the code, testing it safely, repairing. Each finished ability then opens
the approval card. At the end it shows **Added: … Say "…"** and "you can close Jarvis now", or **Waiting for your
OK**, or **No new ability from …** with the reason. If you ask "what abilities did you get from repos" mid-build,
it also tells you to keep it open.

## Opening a repository Jarvis already knows (2026-10-12 IST)

When a repository Jarvis has already learned, or has abilities from, stays open in the browser for about 3 seconds
(new repositories still wait 8 seconds before learning), the island says what Jarvis already has from it. It does
this at most once every 10 minutes per repository:

| Island card | When |
| --- | --- |
| **Already have abilities from owner/repo** · "2 abilities from it: summarize text, summarize file; failed testing: summarize document" · *Say "summarize the text in <text>"* | It has active abilities from that repository. |
| **Already learned owner/repo** · "waiting for your OK: …" · *Say "show pending abilities"* | Abilities from it still wait for your answer. |
| **Already learned owner/repo** · "building its abilities now" | It was learned before abilities existed, so they are built now. |
| **Already learned owner/repo** · "no abilities from it (reason)" | Its build found nothing suitable. |

Ask "what abilities do you have from this repo" (or "… from owner/repo") to hear the same by voice. The situation
snapshot also lists them under the repository on screen, so questions about "this repo" know about them.

**Fixed along the way**, found in this PC's registry:

- Abilities whose build was interrupted by a restart were left "queued" and looked "being built" forever. On start
  they are now marked "interrupted" (not shown); the repository is built again. An interrupted install that had
  already written its code goes back to waiting for approval.
- A repository held by the daily automatic-build limit (`cocoindex-io/cocoindex`, "daily build limit") was never
  picked up again. Held and interrupted repositories now resume at start and are rechecked hourly. They still count
  against the daily limit.

Checked with this PC's real data (2026-10-12 IST, simulated browser titles; the cards were printed, not shown):

- cocoindex: "Already have abilities from cocoindex-io/cocoindex | 2 abilities from it: summarize text, summarize
  file; failed testing: summarize document".
- agenttrail: "… 1 ability from it: extract task list; failed testing: visualize project activity".
- SwiftUI-Agent-Skill: "Already learned … no abilities from it yet".

## Abilities in coding tasks (2026-10-12 IST)

Approved abilities are also used when Jarvis codes, if they fit the task:

- **As tested reference code.** `coding_context()` now carries `learned_abilities`: up to two active abilities that
  match the coding goal. Each comes with what it does, its command, its packages, the repository it came from and its
  license, its last test result, and its code (about 3.5 KB). Every coding path receives this context: Jarvis's
  native workers, the workload planner (as a short summary), Codex and Claude Code. The worker is told to reuse the
  approach where it fits, adapted to the project, declaring the same packages and respecting the license.
- **As tools while coding.** The native coding worker has three new tools:
  - `learned_ability_search`: finds approved abilities by purpose.
  - `learned_ability_read`: returns one ability's full tested code.
  - `learned_ability_run`: runs an ability on a project file or on text, e.g. "summarize file" on the project's
    notes. File inputs must be existing files inside the project. The ability gets a copy and runs in its usual
    guarded process, so project files are never changed. Its outputs go to `JarvisFiles/Abilities/`.

Only abilities you approved and that are active are used; disabled, denied, failed or waiting ones never are. A goal
matches an ability when half the words of its name appear in the goal, or enough of its purpose and commands do. Word
forms and plurals count as the same word ("summarizes" matches "summarize file", "tasks" matches "extract task list").

**Checked live (2026-10-12 IST), with this PC's real approved abilities:**

| Coding goal | Abilities supplied |
| --- | --- |
| "add a function that summarizes a markdown file into a short paragraph" | summarize file, summarize text |
| "write a python script that summarizes a text file into bullet points" | summarize file, summarize text |
| "make a todo app that extracts tasks from my notes" | extract task list |
| snake game, React login page, CSV-to-JSON converter, upload button, README typo | none |

`learned_ability_run` ran the real "summarize file" ability on a copy of `repo-learning.md` inside a test project in
0.3 s. The project file was unchanged, and the summary was saved under `Abilities/summarize-file/`. That ability's
output is weak: its "key topics" were "the, and, repository, with, task", so the 9B-written code needs improvement,
and its reference value for coding is limited to the same degree. A full live coding task using an ability was not run
(about 30 minutes of model time while Jarvis was in use). The routing and tools are covered by
`tests/test_repo_abilities.py`.

## Using abilities

| Say | Does |
| --- | --- |
| *a learned phrase*, e.g. "convert notes.md to html" | Runs the ability. Files are found by full path, or by name in JarvisFiles, Downloads, Desktop or Documents. |
| "use markdown to html on notes.md" | Runs an ability by name; the input type is inferred (file, link, number or text). |
| "what abilities do you have from this repo" / "… from owner/repo" | What Jarvis already has from that repository (also shown on the island when you open it). |
| "list your abilities" / "what abilities did you get from repos" | Active abilities with an example phrase, plus what is waiting, building or failed. |
| "show pending abilities" | Shows every waiting ability on the island again, one card at a time. |
| "approve ability markdown to html" / "approve new abilities" | Approves by voice, without the card: installs, tests and adds it. |
| "deny ability markdown to html" / "reject new abilities" | Discards it. |
| "learn this" | Learns the repository open in the browser, then builds its abilities. |
| "how do I use the extract headings ability" | Its purpose and phrases. |
| "build abilities from psf/requests" / "… from deepseek harness" / "turn this repo into new commands" | Builds now (it learns the repository first if needed; loose names are looked up on GitHub). |
| "rebuild ability <name>" | Builds it again from its repository. |
| "disable ability <name>" / "enable ability <name>" / "forget ability <name>" | Turns it off or on, or removes it from the list (files are kept). |

Input files are **copied** into the run folder first; the ability never touches the original. Outputs are copied to
`JarvisFiles/Abilities/<ability>/` and never overwrite an earlier file (`output-1.html`, …). If an ability's file
changes after it was tested, Jarvis refuses to run it until it is rebuilt.

## The coding model

`model` defaults to `qwen3-coder:30b` (18 GB), because it is better at code. It is used only when its size plus
`memory_margin_gb` fits in free RAM at that moment. Otherwise the build uses `fallback_model` (`qwen3.5:9b`, the
model Jarvis already runs). The coder model is unloaded as soon as a build finishes.

### Building never slows Jarvis down (fix, 2026-10-11 IST)

**What went wrong.** Building abilities made Jarvis lag and, once, freeze:

- At 22:39 the approved "summarize text" ability (from `cocoindex-io/cocoindex`) was added.
- While the next ability was being built, the watchdog logged "Ollama stopped responding" again and again, and the
  microphone and UI automation workers had to be restarted.
- At 22:54 the interface stopped responding and was restarted.
- `psf/requests` failed to learn with a 240 s timeout.

**Why.** Builder calls used the scheduler's `background` role. That role never takes the GPU queue, so each call ran
`qwen3.5:9b` CPU-only (`num_gpu 0`, 16k context) and unloaded it afterwards. Ollama kept swapping between that copy
and the partly-GPU copy your questions use, and each code generation kept many CPU threads busy for minutes.

**Now:**

1. Builder calls use the same queue and settings as repo learning (`research`, below questions, planning and coding),
   so they share Jarvis's warm model instead of reloading it.
2. A call starts only after you have been quiet for `idle_seconds` (20 s), with no task running and no other model
   request queued.
3. Calls stream. If you speak, start a task, or any other model request is queued, the call is abandoned at once (the
   island shows "Paused building abilities") and repeated later.
4. While a call streams, Ollama's model runner runs at below-normal OS priority, so the microphone, the interface
   and the Ollama health check get the CPU first. Jarvis gives that runner 12 threads (`gpu_scheduler.cpu_threads`)
   on this 8-core PC. Priority is restored as soon as the call ends or yields, and on every Jarvis start (in case of
   a crash). Changing the thread or GPU settings instead would have forced Ollama to reload the model.

Live check after step 1–3 (23:00–23:12): builder calls were dispatched as `research` with 7 GPU layers, and no
CPU-only `background` calls remained. The interface didn't freeze. The Ollama health warnings continued during long
calls and the microphone restarted once, which led to step 4.

Live check with all four steps (23:20–23:33):

- Builder calls ran as `research` with 8–11 GPU layers.
- The microphone was never restarted.
- Ollama health warnings dropped to a few short blips during long calls.
- `cocoindex-io/cocoindex` produced "summarize file". The user approved it at 23:30 and it was added.

At 23:31 the launcher restarted a healthy Jarvis: "Runtime status update failed", then "startup did not become
responsive". My monitoring script was reading the heartbeat file every 30 s. On Windows, a file can't be replaced
while another process has it open, so Jarvis's heartbeat update failed. Then one launcher read found it unreadable,
and the launcher treated any unreadable heartbeat as a failed startup, even after valid ones. This was not caused by
the ability code, and it is fixed in [launcher.py](../jarvis/launcher.py) and `main.py`:

- After a valid heartbeat, only a 90-second gap counts as unresponsive.
- The heartbeat replace is retried for up to 0.2 s.

`tests/test_crash_resume.py` injects both a brief and a lasting unreadable heartbeat.

## Storage

- `.jarvis-runtime/abilities/registry.json`: every ability, its state, phrases, approval reasons, version, code
  hash, installed packages and last test.
- `.jarvis-runtime/abilities/<ability>/v<N>/ability.py`: the generated code (plus `repo/` for `repo_code`), its
  environment `env-v<N>/`, its `home/` and recent `runs/` (the six newest are kept).
- `.jarvis-runtime/abilities/_base-env/`: the shared standard-library environment.
- `.jarvis-runtime/abilities/builds.jsonl`: build events, including rejected proposals with the model's raw text.
- Obsidian: a short "Learned abilities" record. The situation snapshot lists active abilities, so questions such as
  "what can you do now" know about them.

## Settings (`config/config.json` → `repo_abilities`)

| Key | Default | Purpose |
| --- | --- | --- |
| `enabled` | `true` | Abilities from repositories (also needs `repo_learning`). |
| `auto_build` | `true` | Build after a repository is learned (asked or browsed). Repositories learned only as coding references are not built automatically. |
| `model` / `fallback_model` | `qwen3-coder:30b` / `qwen3.5:9b` | Coding model, and the model used when the first doesn't fit in free RAM. |
| `memory_margin_gb` | `4` | Free RAM required beyond the coder model's size. |
| `max_repairs` | `2` | Repair attempts after a failed check or test. |
| `max_builds_per_day` | `4` | Automatic builds per day (builds you ask for always run). |
| `test_timeout_seconds` / `run_timeout_seconds` | `120` / `180` | Time limits for the self-test and for a normal run. |
| `max_memory_mb` | `2048` | Memory limit for the ability's process tree. |
| `install_timeout_seconds` | `900` | Package installation limit. |
| `max_input_mb` | `200` | Largest input file. |
| `idle_seconds` | `20` | Quiet time after your last command before a build uses the model. |

`python -m jarvis.launcher --check` validates these values; an invalid value falls back to the last good config.

## Verification (2026-10-11 IST, this PC)

Live runs used a temporary base, vault and cache, so nothing was added to the real registry or vault. Free RAM was
about 13 GB, so every build used the `qwen3.5:9b` fallback; the 30B coder model was **not** exercised live.

| Check | Result |
| --- | --- |
| Learn → break down, first attempt | `trentm/python-markdown2` learned in 250 s. The model proposed "convert markdown to html" and "extract links", but both were rejected: they used alternative inputs (text *or* file) with one per phrase, which the first validator didn't allow. Fixed: alternative inputs are supported, and the island now gives the rejection reason. |
| Break down → generate → check | Second attempt: "markdown to html" and "extract headings", both using the `markdown2` package, written and statically checked in 1,363 s (about 23 minutes on the CPU-heavy 9B fallback). Both stopped at **waiting for approval**, with nothing installed. |
| Approval failure path | The first approval's `pip install` failed: PyPI's hostname didn't resolve at that moment (a manual retry minutes later worked). Both abilities were marked failed, the island said "Jarvis is unchanged", and nothing was merged. |
| Approval → install → test → activate | Re-approved: `markdown2==2.5.5` installed into each ability's own environment, and the self-tests passed in 2 s and 4 s ("Extracted 7 heading(s)…"). |
| Using them | "convert readme-test.md to html" and "extract headings from readme-test.md" ran in about 0.3 s each and saved `output.html` and `headings.txt`. Inline Markdown went to `output-1.html` (no overwrite). The original file was unchanged, and "convert 5 km to miles" was still answered as a question. |
| Routing found live | The phrases were first all dropped, because the general-question catch-all claims "convert …". Learned phrases now beat only that catch-all. "use markdown to html on …" split the name at the wrong "to"; fixed, preferring exact names. |
| Quality | The generated converter wraps headings in `<p>` tags: correct content, imperfect HTML. Generated code is only as good as the local model and its self-test. |

**Follow-up live check (2026-10-11 IST, about 21:44–22:10, temporary base, `qwen3.5:9b`):**

| Check | Result |
| --- | --- |
| Large repository | `deepseek-ai/deepseek-harness` (273 MB, previously refused) learned in 97 s from its key files: 11,166 paths listed, 39 modules analysed. |
| Approval card | "summarize webpage" was shown with its summary, commands ("summarize the webpage at <url>", "give me a summary of <url>"), packages `requests` and `beautifulsoup4`, internet use, plan, "Not run yet…", and the full 112-line code. The script answered approve. |
| Approve → install → test | Both packages were installed into the ability's own environment in 4 s. The self-test then failed: Wikipedia returned 403 to Python's default User-Agent, and two repairs did not fix it. The island said "Ability not added … Jarvis is unchanged", and the build moved on to the next ability ("extract text from pdf"). The code prompt now asks network abilities for a normal browser User-Agent and a stable test page. |
| Stopped early | The run was stopped while building the second ability, so it wouldn't compete for Ollama with the Jarvis app the user had just restarted. No ability from this repository was added. |
| Regression | 146 related tests passed (abilities, learning, island, intents, launcher, commands); `python -m jarvis.launcher --check` reported `ready`. The full suite was not re-run after this follow-up; it last passed 1,550 tests with one skip, before the follow-up. |

`tests/test_repo_abilities.py` (23 tests) covers static checks, spec cleaning, build → test → activate → use, phrase
routing (built-ins win; the general-question catch-all doesn't), island cards one at a time (approve keeps, deny moves
on, no answer stays pending, card content, lapse is not a denial), failure records, tamper refusal, repair and never-merged failures, a
failed update keeping the working version, the approval gate, repositories without a use case, resume after a quit,
skipping duplicate builds, and the real runner guard rails: blocked writes outside the run folder, private reads,
processes and network, and the time limit.

## Limits

- **Guard rails, not a sandbox.** Audit hooks stop mistakes in generated code. Native extensions in third-party
  packages can step around them, which is why packages, repository code and network need your approval. The Docker
  isolation used by [repository skills](repository-skills.md) is not used here, because Docker isn't required for
  Jarvis.
- Abilities are on-demand file, text and URL tasks. Graphical apps, games, services and anything interactive are out
  of scope, so many repositories (frameworks, apps) produce "No new ability" while their knowledge is still saved
  for coding.
- Builds on the 9B fallback take minutes to tens of minutes. The 30B coder model needs about 22 GB free RAM.
- A generated ability only promises what its self-test checked; review its output, and check licenses before
  sharing anything derived from unlicensed repositories.
