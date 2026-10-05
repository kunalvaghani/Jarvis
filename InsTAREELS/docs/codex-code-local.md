# Codex with local Qwen3.5 9B

Jarvis's default coding executor changed from Claude Code to **Codex CLI** on
2026-10-05 IST. Ollama runs the installed **Qwen3.5 9B** weights locally. No paid
model API, Claude subscription or OpenAI API key is required. The user's global
Codex settings and this desktop chat's model are untouched.

## Folder selection and progress

An explicit project folder or source-file path wins, followed by a freshly
observed File Explorer folder, then remembered scope when no folder is open.
An explicit file selects its parent project. Codex reads current source before
modifying it; the original task and bounded project/language guidance accompany
the prompt. Plain folder creation retains Jarvis's direct execution.

The 2026-10-05 destination-parser repair accepts both `in folder TestCodes folder`
and `in TestCodes folder`. In `create an app to monitor my health in folder
TestCodes folder`, the destination is `TestCodes`; the app's purpose is not part
of the folder name. If a folder is missing or ambiguous, a full existing path,
folder name, `use the folder TestCodes`, or `open folder TestCodes` answers the
pending folder question. Jarvis resolves the answer to a concrete existing path
and resumes the original goal once through the configured Codex executor. The
confirmed path overrides the old unresolved scope, including an old absolute
path. Resumed completion is reported in the island and spoken aloud.

An invalid answer leaves the question pending. Expiry, cancellation and uncertain
previous writes retain their existing guards. A folder reply does not approve
replaying file mutations. Tests of this handoff replace the native Codex boundary
with a recording test double: they verify request/folder routing and completion
delivery without generating or manually editing an application. Earlier actual
Codex creation/edit and app browser checks remain separate evidence below.
The actual existing catalog was also checked read-only: the reported utterance
resolved to its existing `TestCodes` destination without rescanning the PC.

Jarvis starts the installed native executable in that folder using
`codex exec --json --ephemeral`. This is the programmatic CLI, without a separate
terminal window. The existing island displays visible response text, file/tool
activity, source previews, checked saves and the final result. The Responses
relay supplies incremental text; tool arguments may arrive together when
Ollama buffers them. Activity updates appear every four seconds during waits.
Hidden reasoning is disabled. The island keeps mounted widgets and expanded
height through completion, while respecting manual collapse.

## Local configuration and checked file tools

Each task receives an isolated `CODEX_HOME` under
`.jarvis-runtime/codex-code/<run>/home/`. Its provider uses `wire_api = "responses"`
and an ephemeral loopback relay to `http://127.0.0.1:11434/v1/responses`.
The relay flattens Codex's MCP tool namespaces for Ollama, restores them on
returned calls, and flattens subsequent input history consistently. Only Jarvis
Read, Glob, Grep, Write and Edit tools reach the model. Native shell, web, hooks,
plugins and subagents are disabled; native execution stays read-only. Those
five bounded MCP tools have explicit approval in the isolated profile and
enforce their own source boundary before accessing files.

Existing files must have a fresh Read hash before changes. A successful owned
atomic save and readback also supplies a fresh observation for the next exact
edit; an external byte change requires another Read. Read results expose plain
source rather than JSON-escaped source, and syntax failures put the actual error
ahead of long source lines. Available syntax checks run before saves; original
bytes are backed up once. Exact edits require
a unique match unless replacing all matches was explicit. Atomic replacement
and disk readback confirm saves. Hidden files, linked paths, dependencies,
oversized files and paths outside the selected project are rejected. Attempted
identical mutations are not replayed. Completion credits only applied receipts
whose proposed hashes still match disk, rather than the model's claims.
Native compilation and actual UI behavior require independent checks.

Stop/Quit closes only the owned Codex, MCP and relay process tree through the
existing action worker. Shared Ollama remains running. Local model/tool support,
required MCP connection, bounded relay startup, stream errors, total deadline
and final completion/exit are checked. Failures retain partial source and private
receipts; inference retries are disabled and no executor fallback replays edits.

## Setup

Install native Codex CLI and Ollama first, with `qwen3.5:9b` locally available:

```powershell
.venv\Scripts\python.exe setup_codex_code.py
```

This creates `jarvis-codex-qwen3.5:9b` using the same installed model weights:
32K context, 20 GPU layers, temperature 0.2 and up to 6,000 output tokens on this
4GB GPU. Ollama recommends at least 64K for Codex; the smaller setting bounds
memory use and limits large-repository tasks. Local 9B generation can still take
minutes. Streaming avoids a short whole-response timeout; it does not increase
inference speed. No new Python dependencies were added.

The `brain` object in `config.json` selects:

```json
"coding_backend": "codex",
"codex_model": "jarvis-codex-qwen3.5:9b",
"max_coding_seconds": 1800
```

Direct `qwen3.5:9b` is also accepted; other models and cloud fallback are rejected.
Optional `brain.codex_executable` names an installed native executable. Discovery
otherwise checks PATH and the desktop app's versioned native binaries. The
stream watchdog is 30 minutes and the total deadline is bounded to 60–3,600
seconds. Source files have a 20,000-character limit; tasks 6,000 characters.
Split larger work into modules. Restart through **Stop Jarvis.cmd**, then
**Start Jarvis.cmd** to load this configuration.

The older Claude implementation and dated records remain historical/optional
code; they are not the configured executor.

## Installed files but `/api/show` returns 404

On 2026-10-05 IST, the active port 11434 was forwarded into WSL. Its Ollama
store initially listed only Gemma, while the Qwen files existed in the separate
Windows cache at `D:\Ollama\models`. A missing model's `/api/show` returned 404;
the presence of Windows manifest folders did not make those weights visible to
the running server.

`brain.ollama_cache_roots` now lists that cache and `D:\OllamaModels`.
**Setup Jarvis Brain.cmd**, or the following model-only setup, first checks the
active server, then restores available cached single-GGUF models over the local
Ollama blob/create APIs before attempting a registry download:

```powershell
.venv\Scripts\python.exe setup_brain.py --ollama-only
```

Setup validates manifest sizes, contained blob paths, GGUF format and metadata
checksums. Ollama validates the uploaded weights' expected SHA-256. Renderer,
parser, parameters, system/template and license metadata accompany the import.
Existing server blobs are reused. Original cache files remain intact; copying
into a separate server store consumes additional disk space. Multi-part models
require the normal Ollama import/pull workflow rather than guessed filenames.

The base model is ensured before creating Jarvis's local Codex alias; alias names
are never pulled from the public registry. A coding request can recreate a
missing alias from an already visible base model, but does not start a large
weight upload/download. Missing weights produce an actionable setup message
before changing project files. Background recovery also uses this setup path.

The actual restore made Qwen3.5 9B, its Codex alias, the configured 0.8B audio
model and 0.5B context model visible without registry downloads or stopping the
shared server. Gemma remained installed. The fresh [model visibility receipt](../artifacts/codex-model-restore-check.json)
records all four configured model lookups returning 200 and the cached base
weight present on the server by its SHA-256. Restored server visibility takes effect
immediately; restart Jarvis once through Stop/Start to load the updated recovery
and preflight code.

## Verification on 2026-10-05 IST

The [actual local CLI fixture](../artifacts/codex-code-live-check.json) passed
Codex 0.160.0/Qwen source creation and fresh-source editing, original-backup
verification and a Python run printing `5`. The refreshed run after restoring
active-server model visibility observed 215 progress events and five completed
local inference requests with thinking disabled. Earlier passing
228-event/five-request, 266-event/five-request and 378-event/seven-request runs remain historical
evidence. Early
namespace/approval failures remain in history; repairs used fresh owned fixtures.

The [generated counter app](../artifacts/codex-app-live-check.json) passed actual
Chrome heading, increment-twice, reset, 390px overflow and JavaScript-error checks.
The first generated file animated its control ancestors and failed browser
stability checks. A fresh-source Qwen/Codex edit moved motion off the controls;
the retest passed with 385 progress events. The initial failure is preserved in
history. This covers the small owned app's tested interactions, not arbitrary
generated applications or all visual/accessibility details.

The [island replay](../artifacts/codex-code-island-check.json) passed 90 authored
events in actual off-screen Tk widgets, with zero view unmaps/layout rebuilds,
monotonic growth and preserved completion handoff. This rendered preview is
not a desktop screenshot or live microphone test.

![Rendered Jarvis island with authored Codex file activity](../artifacts/codex-code-island-preview.png)

The [full regression/readiness receipt](../artifacts/coding-regression-check.json)
records **1,021 passing tests** and launcher status `ready` after the destination
and reply repair. The previous 1,013-test model-cache repair and 1,006-test pass
remain in history. Eight new destination/handoff tests include the exact spoken
request, confirmed-folder path selection, invalid-answer recovery, expiry,
uncertain-write blocking, worker completion delivery and the Codex boundary.
These use owned temporary folders and a recording native Codex test double.
Fault tests include
Stop, failed relay startup, failed agent turns and total deadline cleanup without
replay. Checks also cover namespace round-tripping, local-only routing, stale
reads, backups, invalid syntax, duplicate mutations and divergent disk readback.
[Multilingual UI results](multilingual-coding.md) are separate from CLI completion.

```powershell
.venv\Scripts\python.exe verify_codex_code.py
.venv\Scripts\python.exe verify_codex_app.py
.venv\Scripts\python.exe verify_codex_island.py
.venv\Scripts\python.exe verify_coding_regression.py
```

Private task prompts, source logs and backups remain ignored under
`.jarvis-runtime/codex-code/`. No credentials or private recordings are published.

## Primary references

- [Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
- [Ollama's Codex integration](https://docs.ollama.com/integrations/codex)
- [Ollama Responses API compatibility](https://docs.ollama.com/api/openai-compatibility)
- [Ollama blob and model creation API](https://github.com/ollama/ollama/blob/main/docs/api.md)

These were checked against the installed CLI and actual local requests. The
user-supplied screenshot was a reference, not validation.
