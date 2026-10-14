# Knowledge acquisition verification — 2026-10-14 IST

See [architecture, compatibility, configuration and rollback](autonomous-learning.md).
Results below distinguish fixture execution, real inference, public transport and
release regression checks. They do not certify control of arbitrary applications.

## Release checks

### Current-app research repair

The subsequent real task “make this cube into a circle into a sphere” paused in
Blender without acquisition: the original detector required the app name in the
goal. Runtime checkpoints also showed `application_inspect` proposed with object
names `Cube` and `Modifier`, rejected as unconfigured applications. No source
search was recorded. This was a detection/integration gap in the initial release;
the prior fixture tests did not exercise this implicit current-app wording.

The repaired path resolves the actual current configured executable through the
registered observation, then acquires feature evidence. Explicit configured GUI
aliases cover Blender's launcher/GUI split. It rejects unconfigured object names
before dispatch, supplies one read-only correction to the existing model, and
retains learned context in native correction messages. Simple-command bypass
and private-origin rules remain covered.

84 affected tests passed, including the exact sphere wording, no guessed target
from another executable, no public query containing full goal text, and correction
without dispatch. A real registered web search for `blender sphere official
documentation` and two public scrapes passed in **2.828 seconds**. See the
[public search evidence](../artifacts/reports/learning-search-repair.json).
This live check used an explicit Blender target and no scene actions; implicit
foreground resolution is regression-tested. One retrieved manual was for Blender
2.82, so those search results are untrusted references and do not establish 4.4
compatibility or prove the requested conversion. No user scene was modified.

A second actual search with installed version **4.4.3.0** completed in **3.562
seconds**, retrieving official 4.4 release notes and the latest mesh-primitives
manual. See [version-aware search](../artifacts/reports/learning-search-versioned.json).
These pages establish successful internet retrieval, not an exact conversion recipe.
The [owned native current-app check](../artifacts/reports/learning-native-current.json)
also passed with the app name omitted: real process identity/UIA resolution,
configured local help, guarded click, SVG readback and verified memory promotion.
It uses an authored planner and synthetic app, not the user's Blender scene.

Final repair release: **1,785 tests passed in 295.241 seconds**; launcher readiness
reported **`ready`**. Configuration JSON, documentation links and whitespace checks
also passed. [Repair release evidence](../artifacts/reports/learning-current-app-validation.json)
preserves these results separately from the initial learning release below.

The pre-change suite passed **1,765 tests in 280.195 seconds**. The first integrated
release run executed 1,779 tests and exposed one catalog compatibility failure:
the new tool declared a backend outside the established seven backend categories.
It now uses the existing desktop backend. The final result is recorded below after
the complete rerun. Catalog/acquisition focused checks passed 20 tests; learning,
skill-memory, UI, DAG and idle-scheduler focused checks passed during development.

Final full release regression: **1,781 tests passed in 306.851 seconds** after
the compatibility correction and final targeted-repair/skill tests. No tests were
skipped in that discovery run. Source compilation also passed. The existing
pywinauto COM-mode warning appeared without a failing test.

Launcher readiness reported **`ready`**, with configured dependencies/models and
services available. This is a readiness check: optional Groq live inference,
hosted LocalGithub services, microphone capture and speaker playback were not
tested by it. An initial sandbox test run failed because Windows denied fixture
atomic file replacement. The release suite ran outside that sandbox, using owned
fixtures; no permissions logic was removed to make tests pass.

New acquisition tests cover simple-command bypass, sanitized scoped queries,
untrusted source payloads, compatible offline/restart reuse, missing-feature
research, changed version/interface rejection, cancellation and policy denial,
task research budgets, task-scoped tool mappings, continued-conversation context,
private origins, corrupt cache rejection, persistence failure, background source
refresh without proof/expiry changes, affected-feature repair, and actual shared
SkillMemory learned-procedure registration. The broader suite retains established
voice, provider, parser, coding, integrations, GUI/browser, permissions, lifecycle,
recovery, memory and DAG regressions. Many tests are controlled fixtures/mocks;
passing them is not a live test of every external integration.

## Integrated execution evidence

| Check | Actual operations | Result | Limit |
|---|---|---|---|
| Native fixture | Real Windows executable version and UIA controls; configured local help; Brain/ToolRegistry click; independent SVG and event readback; verified shared memory | Passed, 2.609 s | Owned synthetic native app; authored planner and deterministic oracle |
| Browser fixture | Existing BrowserSession/BrowserAutomation/UITransport in real headless Chrome; registry click; fresh independent DOM readback; verified shared memory | Passed, 2.329 s | Locally intercepted synthetic page; authored planner; no account or third-party export |
| Public documentation | Actual registered `scrape_web` retrieval of Python 3.10 tkinter docs | Passed, 0.531 s | Retrieval and relevant text, not workflow/API compatibility proof |
| Local model and acquired help | Actual configured Qwen planner receives acquisition context; production DAG/ToolRegistry reads two synthetic scoped files; independent readback | Passed, 86.578 s | Read-only file task; no general GUI model-quality claim |
| Procedure registration | Actual shared SkillMemory writes learned declarative `SKILL.md` after proof and retrieves acquired capability guidance | Passed in regression | Reference guidance, not unrestricted executable skill |

Machine-readable evidence: [native](../artifacts/reports/learning-native.json),
[browser](../artifacts/reports/learning-website.json),
[public docs](../artifacts/reports/learning-public-docs.json),
[local model](../artifacts/reports/learning-live.json),
[release summary](../artifacts/reports/learning-validation.json).
Native/browser timing includes fixture startup and workflow verification; it is
not first-token/first-audio latency. The public URL is selected from the runtime
version, but the document version remains explicitly unverified in provenance.

Early native fixture pilots needed the actual owning Python executable, a fresh
control choice and a matching decision. Early local-model pilots were rejected
when the fixture's read-only scope omitted the requested analysis tool, then when
its wording selected the normal GUI route instead of the DAG route. Final fixture
requests were aligned with the intended route and scope; runtime guards stayed
enabled. The final model check completed with acquired help and both exact file
descriptions. These are bounded integrations, not arbitrary-app demonstrations.

## Before/after measurements

The immutable [baseline](../artifacts/reports/learning-baseline.json) was collected
before acquisition implementation. The [upgraded sample](../artifacts/reports/learning-upgraded.json)
uses the same script and workload: 400 real parser calls and 100 shared app-memory
lookups. It ran alongside release tests, so these single samples are susceptible
to contention and are not production latency distributions. Their source
inventories record paths, SHA-256, classes/functions and imports; final source
hashes also accompany the release summary. The later catalog-label fix does not
change the measured parser path.

| Metric | Before | After |
|---|---:|---:|
| Parser median | 2.37475 ms | 2.43115 ms |
| Parser p95 | 2.8555 ms | 3.0689 ms |
| Parser p99 | 8.5779 ms | 9.1330 ms |
| App-memory lookup median | 0.0124 ms | 0.0146 ms |
| Deterministic simple-task gap assessment | Unsupported automatic path | 0.0018 ms |
| Benchmark process peak working set | 36.840 MiB | 37.145 MiB |

No speedup is claimed from this sample. Known command routing remains measured
in milliseconds, and the new detector requires no model or network for simple
commands. Whole-process production RAM/VRAM, peak inference allocation, idle
refresh CPU load, repeat-task latency distributions, and comparable pre-change
unknown-app/unknown-site end-to-end times were **not measured**. A missing baseline
feature is marked unsupported rather than assigned an invented runtime. Offline
cache reuse is verified functionally, not presented as a timed speedup.

## Remaining production limits

The installed runtime, regression suite and bounded integrations provide evidence
for this extension, not universal autonomous intelligence. Detection is currently
limited to configured software (named or resolved from the current executable),
explicit public URLs and an allowlist of
feature vocabulary. Generic API/SDK discovery does not create tools. Unsupported
GUI surfaces, custom-rendered controls, inaccessible apps, authentication, changed
interfaces and ambiguous user goals can require clarification or a specialized
integration. The capability index is bounded and conservative; cached knowledge
is reference evidence and still needs live validation.

No Blender glass render, Unreal motion-matching project, or third-party
presentation export was tested. The existing established workflow routes remain
available but those examples are not certified by synthetic fixtures. Internet
source instructions cannot directly execute; central admission/permissions remain
the action boundary, while model semantic accuracy remains imperfect. Prompt
injection tests demonstrate the tested guards, not immunity to all adversarial text.

There is no two-second complex-task guarantee. Local planning, network retrieval
and F5 synthesis can be substantially slower. Earlier conversation/voice and DAG
measurements remain in their own dated reports and are not replaced by these
learning measurements. Background refresh is opt-in and disabled by default;
resource/cancellation paths are covered by regression, not a long-running battery
or 24-hour soak test. Enable it only with those limits understood.

## Reproduction

From `app/`, using the existing environment:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m jarvis.launcher --check
.\.venv\Scripts\python.exe -m scripts.verification.verify_learning_native
.\.venv\Scripts\python.exe -m scripts.verification.verify_learning_website
.\.venv\Scripts\python.exe -m scripts.verification.verify_learning_public
.\.venv\Scripts\python.exe -m scripts.verification.verify_learning_live
```

The native script briefly focuses only its owned window and restores prior focus.
The browser script uses an isolated profile and locally intercepted page. The
public script fetches one official URL; the live script uses the configured local
planner and synthetic files. Reports contain synthetic/public data, no credentials
or private audio. Preserve existing reports before deliberately rerunning them.
The parser benchmark refuses to overwrite baseline/upgraded artifacts.
