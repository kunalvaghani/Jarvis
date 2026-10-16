# Phase 2 — Integration evidence, fallback paths, security findings and limitations

## ToolRegistry integration (no second registry)

* The nine new tools (`office_xlsx`, `office_docx`, `pdf_document`, `office_automation`, `blender_task`, `unreal_task`,
  `vscode_cli`, `execution_methods`, `strategy_execute`) are entries in the existing `toolkits.TOOLS` table and therefore in
  `tools.SPECS` (107 → 116 specs). Dispatch path: `ToolRegistry.execute` → `_execute` → `toolkits.execute` →
  `app_adapters.execute` / `execution_strategy.strategy_tool`.
* `strategy_execute` never calls an adapter directly: each attempt is a nested `ToolRegistry(actions).execute(...)`, so
  task scope (`allowed_tools`), `.jarvis/policy.json` deny rules, `APPROVAL_CLAIMS` stripping, lifecycle events and runtime
  approval apply to every method attempt. Measured: 2 `tool.started` rows per strategy edit
  ([execution-benchmark.json](execution-benchmark.json)).
* `ToolRegistry.execute` now calls `execution_strategy.observe` after each call, which writes one categorical
  `tool.outcome` row (Phase 1 contract) for catalogued methods. Not-dispatched categories (`invalid_arguments`,
  `unavailable`, `cancelled`) are not recorded, so refusals do not count against a method's reliability.
* The dated Prompt 01 registry inventory (`modules/01-architecture-inventory/source-inventory.json`) was regenerated with its
  own generator (`verify_architecture.inventory`) because a Prompt 01 test requires it to list every registered tool; the
  previous version is preserved here as [prompt01-source-inventory-before-phase02.json](prompt01-source-inventory-before-phase02.json).

## Planner integration (capabilities.py + brain.py)

* `capabilities.ROUTES` gained `documents`, `modeling_3d` and `vscode` intents; `runtime_context` adds
  `execution_strategy` (method order per named file/app) to `capability_context`, which every planner already receives;
  the native planner system prompt states the API → structured → GUI order.
* `Brain.validate_remaining` rejects a GUI step (`type_text`, `select`, `fill_text`, `save_file`, `shortcut`,
  `open_menu`, `handle_dialog`) aimed at a named document while an eligible API/structured method exists; the rejection
  text names the tool, and the existing replan loop receives it as validation feedback. GUI is allowed again for that
  target once `strategy_execute` reports every API/structured method unavailable (session-scoped), or when only GUI tools
  are in scope. Writes through the new adapters must name the file and contain write intent.

## Tested fallback paths

| Path | Trigger | Expected | Test | Real/Mock |
| --- | --- | --- | --- | --- |
| Feature-based exclusion | workbook with a chart | openpyxl ineligible at planning; native Excel writes; chart part survives; Excel caches recalculated values | P02_07 | real Excel |
| Outage before input | API handler raises `ToolUnavailable` | next eligible method runs | P02_07c | mock handlers |
| Failure after possible dispatch | API handler raises `ValueError` | plan stops; no second method | P02_07c | mock handlers |
| All methods unavailable | requirements missing | `ToolUnavailable` naming the GUI fallback; nothing changed; GUI unlocked for that target | P02_07d, planner test | mock availability |
| Read-only transient error | `OSError` on read | exactly one retry (2 attempts); writes 1 attempt | P02_07e | mock handler |
| Measured unreliability | 10 failed API outcomes, 10 verified structured | API demoted, structured selected; demoted API still used when it is the only authorized method | P02_measured_* | real event log |
| Desktop structured → pointer | UIA patterns absent | providers decline before input; cyan pointer dispatches once | P02_09b/09c | mock geometry/providers |
| Desktop structured first | disposable Win32 app | UFO `ValuePattern`/`Invoke`; pointer never called | P02_06 | real UIA |

## Security and data-preservation findings

| ID | Finding | Status |
| --- | --- | --- |
| S1 | Writes require runtime approval per operation (`actions._approve`); denial leaves the file byte-identical and creates no backup (P02_08). | Enforced |
| S2 | Paths are confined by `toolkits.scoped_path` to the user-named folder; traversal, absolute and hidden names are refused (P02_08b). | Enforced |
| S3 | Telemetry rows contain no file names, cell coordinates or values; a fake credential written into a cell never appears in the event log (P02_08c). | Enforced |
| S4 | No write is retried by the engine; read-only retries are bounded to 2 attempts (P02_07e). | Enforced |
| S5 | Transactions: temporary copy → independent readback → backup in `.jarvis-runtime/backups/documents` → hash-checked atomic replace; a concurrent change aborts with no overwrite (P02_08d); a locked file reports "no change committed". | Enforced |
| S6 | Feature preservation: macro, chart, pivot, link, drawing, signature and tracked-change parts are detected from the package listing before parsing; methods that cannot preserve them are ineligible. Native Office edits verify the `vbaProject.bin` hash and that no detected feature disappeared. | Enforced (macro-hash path not exercised with a real macro workbook — see U3) |
| S7 | Native Office runs as a *new* hidden instance with `AutomationSecurity = ForceDisable` and Excel `EnableEvents = False`, so workbook macros do not execute during automation; only the PID of that instance may be stopped after a bounded wait, after checking name and start time. Observed: no leftover EXCEL/WINWORD processes after the suite. | Enforced |
| S8 | Blender runs only the shipped templates with `--background --factory-startup --disable-autoexec`; `.blend` files are opened with `use_scripts=False`; object names/types/vectors are validated before launch (P02_04b). Existing outputs are never overwritten. | Enforced |
| S9 | Web methods: documented realtime providers and public HTTP text only; no undocumented endpoints, authentication or rate-limit bypass were added. | By construction |
| S10 | Worker processes (`document_worker`, `office_com_worker`, Blender, VS Code CLI) run in an owned Windows job object with timeouts and output budgets. They are **not** security sandboxes for untrusted code; they parse documents with maintained libraries. | Documented limitation |
| S11 | `pypdf` 6.20.0 (pre-existing pin) predates the 6.20.1 cyclic-tree fix recorded by Prompt 17; PDF parsing runs in a separate bounded worker process. No dependency upgrade was made in this phase. | Open (pre-existing) |

## Defects found and fixed during Phase 2

| ID | Defect | Root cause | Fix | Proof |
| --- | --- | --- | --- | --- |
| F1 | Native Word reported success but did not replace text; independent verification refused the commit (original unchanged). | Late-bound COM ignores named `Find.Execute` arguments. | Set `Find` properties and pass `Replace=wdReplaceAll` positionally. | P02_02c real Word passes |
| F2 | File-name extraction captured whole phrases ("set cell B2 to 5 in budget.xlsx"). | Regex allowed spaces in unquoted names. | Unquoted names without spaces; quoted names may contain spaces (`files_in`). | capability-context test |
| F3 | VS Code CLI not found. | Current VS Code keeps `cli.js` in a versioned folder named by `code.cmd`. | Read the path from `code.cmd`; fall back to the flat layout. | P02_vscode real |
| F4 | Import cycles between `toolkits` and the new adapters. | `ToolUnavailable` lived in `toolkits`. | Moved to dependency-free `jarvis/tool_errors.py`, re-exported by `toolkits` (same class object). | identity check + suites |
| F6 | Three Prompt 02/03/04 completion cases (`tests/audit_contract_helpers.trace_contract`) and one Prompt 01 test asserted an exact list of event rows. | New `tool.outcome` rows are expected additions. | Assertions now check lifecycle rows exactly **and** require every outcome row to share a lifecycle `call_id` (stricter on correlation, not weaker on lifecycle). | run 2 full regression |
| F5 | **Operator error during this phase:** `config/config.json` was written with unescaped backslashes and was invalid JSON for under a minute. | Shell/Python quoting in an edit script. | Corrected immediately; confirmed no Jarvis/launcher process was running at the time. | `json.loads` of config; launcher `--check` |

## Remaining unsupported cases

| ID | Case | Why |
| --- | --- | --- |
| U1 | Unreal editor Python / commandlets on a project | Needs a disposable `.uproject`; running the editor on a user project writes `Saved/`, `Intermediate/` and DDC data. Only the engine manifest is read. |
| U2 | Live GUI-coordinate execution timing | Typing into the user's live Office session was not performed; the GUI step count is an authored reference plan. |
| U3 | Real macro-enabled workbook/document | Creating a genuine `vbaProject.bin` requires enabling "Trust access to the VBA project object model", a user security setting that was not changed. Detection and hash checks are unit-tested on package listings only. |
| U4 | `.xls`/`.doc` binary formats | Only GUI or future native conversions; API methods cover Open XML. |
| U5 | DOCX text split across formatted runs | python-docx refuses rather than flattening formatting; native Word handles it. |
| U6 | New formulas written by openpyxl have no cached value until Excel recalculates | Reported in the result `note`; native Excel path caches values. |
| U7 | `vscode_cli open` live check | Would open a window in the user's VS Code session; verification state is reported as `unverified`. |
| U8 | Strategy routing for web reads | Web methods are ranked by `execution_methods`; `strategy_execute` runs document/3D/editor targets only. |
