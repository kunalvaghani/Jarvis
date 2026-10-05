# Multilingual coding and animated UI verification

Jarvis's coding path now supplies bounded language guidance for Python, C, C++,
C#, Java, JavaScript, TypeScript, React, HTML/CSS, Go, Rust, Kotlin, Swift, PHP,
Ruby and SQL. This is prompt guidance and source handling, not model training.
The catalogue in [coding_languages.py](../jarvis/coding_languages.py) links each
guide to its first-party documentation. Native project markers and source
extensions are recognized; requesting C#/C++/Java does not silently scaffold an
Electron app. Existing project conventions still take priority.

Coding tasks use [installed Codex with local Qwen3.5 9B](codex-code-local.md).
Explicit folder/source paths take priority, then a freshly observed File Explorer folder,
then remembered scope when no open folder is available. Existing files are read
for modifications. Each CLI task has streamed island activity, checked file
writes, original-byte backups and owned Stop handling. No paid model is used.

Examples:

```
create a C++ game with UI in "D:\Projects\Game"
edit "D:\Projects\Calculator\Main.cs" to add keyboard controls
create a React website in this folder
add UI to calculator.py
```

## Source checks and limitations

Python/JSON retain syntax checks. JavaScript and inline HTML scripts use
`node --check` when Node is installed; the actual syntax error is placed ahead
of long source lines in feedback. XML project/UI files are parsed without
external entities. Other languages retain disk readback with compiler/runtime
checks explicitly pending. JSX/TSX needs a project build and type check.
Syntax validation alone does not prove an interface or game works.
Unclosed HTML script blocks are rejected before writes. Explicit coding requests
that mention email/contact forms or GitHub APIs retain the coding route; actual
email or repository actions keep their existing integration workflow.

Native compilers and UI SDKs remain prerequisites: C/C++ needs a compiler and
the selected Win32/Qt/SDL toolkit; C# needs .NET with its actual Windows UI
target; Java needs a JDK, not just a JRE; SwiftUI needs an Apple SDK. Generated
files are bounded to 20,000 characters each. Split larger work into modules.
The direct Qwen backend remains selectable through `brain.coding_backend`.

## Nine authored UI contracts

The request for three games, three apps and three websites is exercised with
easy, medium and advanced levels relative to this suite. The test contracts
are authored independently; implementation starts with actual local Qwen drafts
through Jarvis. Historical Claude-generated fixtures are retained; reviewed
corrections to Breakout, Ledger, Board, Focus and all three websites are
attributed separately in the [correction receipt](../artifacts/multilingual-ui-corrections.json). Further
generation and inspected repairs use the configured local Codex backend.

| Category | Level | Project | Main checks |
|---|---:|---|---|
| Game | 1 | Orbit Catch | Moving target, scoring, pause/resume/reset |
| Game | 2 | Prism Pairs | Matching/mismatches, win, restart |
| Game | 3 | Neon Breakout | Canvas motion, paddle, pause/resume/reset |
| App | 1 | Focus Flow | Countdown, pause, completion, reset |
| App | 2 | Pocket Ledger | Input validation, total, filtering, persistence, deletion |
| App | 3 | Studio Board | React/TS kanban transitions, persistence, search, deletion |
| Website | 1 | Aster Studio | Portfolio filter/navigation, local contact confirmation |
| Website | 2 | Forma Market | Cart quantities/total, persistence, removal, demo checkout |
| Website | 3 | Atlas Escapes | Booking validation, local confirmation/history, cancellation |

`verify_multilingual_ui.py` runs an isolated Chrome against an ephemeral loopback
server with owned examples, checks actual controls, time-changing UI animation,
390px mobile overflow and reduced-motion rendering. It checks invalid input,
timer click stability, portfolio navigation, shop search/categories and checkout
keyboard dismissal, booking price order, favorite persistence, guest bounds and
dialog Escape/Cancel. Failed CLI checks return a nonzero exit status. React projects use the
already installed local Vite/TypeScript/React tooling. There are no remote
bookings, payments or messages. Failed checks feed the current source and
observed errors into a subsequent explicit repair task; uncertain actions are
never automatically replayed.

[Dated generation/browser receipt](../artifacts/multilingual-ui-check.json)
records each project's current result and previous attempts. A generated file
is not marked functionally verified until the browser checks pass. Screenshots
are real isolated browser captures when present, not upstream demos or a user's
desktop. This suite does not prove arbitrary app complexity or every language.

On **2026-10-05 IST**, all **nine fixtures passed together** in actual Chrome;
Board and Atlas also passed strict TypeScript checks and production builds.
Several Qwen drafts failed their first functional/build check and needed the
reviewed corrections above. The separate fresh Codex create/edit/backup/Python
fixture passed with the final plain-source Read settings. The full regression
suite passed **1,006 tests**, and launcher readiness reported `ready`.
View the [sources and real browser screenshots](../examples/multilingual/README.md).

## Reproduce

```
.venv\Scripts\python.exe setup_codex_code.py
.venv\Scripts\python.exe verify_codex_code.py
.venv\Scripts\python.exe verify_multilingual_ui.py --generate --backend codex
.venv\Scripts\python.exe verify_multilingual_ui.py --test
.venv\Scripts\python.exe verify_multilingual_ui.py --repair game-1-orbit --backend codex
.venv\Scripts\python.exe verify_coding_regression.py
```

This verification uses installed Chrome, Codex CLI, local Ollama, Node and the
existing development fixture dependencies. It does not install dependencies or
run user projects. Windows subprocess communication may require execution
outside a Codex filesystem sandbox. CLI event logs and original user-file
backups remain private under ignored `.jarvis-runtime/codex-code/`.

[Regression/readiness receipt](../artifacts/coding-regression-check.json) is
separate from live generation and functional browser results. Historical
measurements in other guides retain their original scope.
