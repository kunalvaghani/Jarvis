# Phase 2 — Execution-method compatibility matrix

Date 2026-10-17 IST, this machine (Windows 11, Office 16, Blender 4.4.3, UE 5.8 manifest, VS Code with versioned
install layout, Chrome). "Tested" names the test in `tests/test_phase02_execution_strategy.py` and whether it used the
real software. Catalogue source: `jarvis/execution_strategy.py:METHODS`.

| Method ID | Registry tool | Tier | Operations | Targets | Verification | Refuses writes when | Available here | Tested (real/mock) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `xlsx.openpyxl` | `office_xlsx` | api | read, inspect, write | .xlsx | independent readback of every cell, formula and sheet | macros, charts, pivot tables, external links, drawings, signatures | yes (.venv-skills openpyxl 3.1.5) | P02_01, 01b, 08, 08c, 08d — **real** |
| `xlsx.excel_com` | `office_automation` | structured | write | .xlsx, .xlsm | readback + macro-part hash + feature set | signatures | yes (Excel 16) | P02_07 chart workbook — **real Excel** |
| `xlsx.gui` | `type_text` | gui | write | .xlsx/.xlsm/.xls | observation only | — | recommended only | planner rule P02_planner_* (no live GUI typing) |
| `docx.python_docx` | `office_docx` | api | read, inspect, write | .docx | text/paragraph-count readback + table cells | macros, signatures, tracked changes | yes (python-docx 1.2.0) | P02_02, 02b — **real** |
| `docx.word_com` | `office_automation` | structured | write | .docx, .docm | text readback + feature set | signatures | yes (Word 16) | P02_02c — **real Word** |
| `docx.gui` | `type_text` | gui | write | .docx/.docm/.doc | observation | — | recommended only | planner rule |
| `pdf.pypdf` | `pdf_document` | api | read(text), inspect, compose (new file) | .pdf | reread page count/text of the new file | encrypted sources; never edits in place | yes (pypdf 6.20.0) | P02_03 — **real** |
| `blender.background` | `blender_task` | api | create (new .blend + optional glTF/OBJ/STL), inspect | .blend | second Blender process reads back names, transforms, meshes | existing output (no overwrite) | yes (D:\Blender 4.4.3) | P02_04, 04b — **real Blender** |
| `blender.gui` | `select` | gui | create | .blend | observation | — | recommended only | — |
| `unreal.manifest` | `unreal_task` | api | inspect | unreal | manifest read | — (read-only) | yes (UE 5.8 Build.version) | P02_unreal — **real file read** |
| Unreal editor Python / commandlet on a project | — | — | — | — | — | **not implemented**: needs a configured disposable project | — | NOT RUN |
| `web.realtime_api` | `realtime_query` | api | read | web | provider response | documented providers only | when `actions.realtime` exists | ranking P02_05b (mock availability) |
| `web.http_text` | `scrape_web` | api | read | web | observation | public pages only | yes | ranking only |
| `web.dom` / `web.dom_fill` | `browser_inspect` / `browser_fill` | structured | read / write | web | DOM state | — | yes (Playwright 1.63, Chrome) | P02_05 loopback page — **real headless Chrome** |
| `vscode.cli` | `vscode_cli` | api | inspect (version, extensions), open | vscode | CLI output (open = unverified) | — | yes | P02_vscode version/list — **real**; `open` NOT RUN live (would open a window in the user's session) |
| `windows.open` / `windows.uia` | `open` / `select` | api / structured | open / write | app | observation / native state | — | yes | P02_06 disposable Win32 app — **real UIA** |
| `windows.visual` | `save_file` | gui | write | app | observation | visual fallback disabled unless configured | config-dependent | existing visual-fallback suites |

## Desktop control provider order (behaviour change)

`execution_adapters.desktop_order()` is now used by `execution_router.execute` when no explicit provider list is given:

| Setting `execution_strategy.desktop_order` | Effective order |
| --- | --- |
| `structured_first` (new default) or missing/malformed | ufo → windows-mcp → cua → open-computer-use → agent-s → **jarvis-pointer** |
| `pointer_first` | **jarvis-pointer** → ufo → windows-mcp → cua → open-computer-use → agent-s (pre-Phase-2 behaviour) |

The cyan-cursor pointer is still used whenever no UIA pattern can prepare the action (P02_09b/09c). `PRIORITY` keeps the
historical catalogue order for compatibility; `integration_status` now also reports `effective_order`.
