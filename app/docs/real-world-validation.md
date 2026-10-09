# Live task validation — 2026-09-27

These tests used the installed `qwen3.5:4b` on CPU, actual Jarvis source and Git
history, real scoped disk writes, and the live official Python documentation.
Model answers, tool results and generated code were not mocked. This is
component/agent validation, not a microphone, desktop or third-party account/MCP
provider trial. Each coding attempt used a new workspace; failed writes were not
replayed. Only test-owned Ollama servers were stopped.

## Tasks and observed results

| # | Real task | Observed result |
| --- | --- | --- |
| 1 | Audit actual deletion and command-approval implementation | Source read and acceptance passed; correctly identified Recycle Bin and approval gates. |
| 2 | Investigate duplicate-action and uncertain-effect recovery | Actual source read passed. Answer-quality issue: changing state does not grant permission to retry an uncertain effect. |
| 3 | Map the application inside a repository containing a large upstream tree | Passed after application source was prioritized over reference trees. Bounded maps can omit symbols from large files. |
| 4 | Audit hierarchical instructions and skill discovery | Actual source read and keyword check passed. Prose misstated instruction order and confused byte/character bounds. |
| 5 | Inspect actual MCP allowlist, approval, protocol and timeout enforcement | Source read and acceptance passed. This inspected implementation, not a real external MCP provider. |
| 6 | Inspect working-tree modifications and recent commits in one batch | Passed on rerun; first answer retrieved real data but omitted the required literal tool identifiers. |
| 7 | Identify and remember manifest HTTP library and MCP capability | Passed with an explicit manifest question: `requests`, `approved_mcp_stdio_tools`. |
| 8 | Resume a persisted conversation and recall the manifest findings | Passed; recalled both exact names from saved context without replaying tools. |
| 9 | Fork the saved conversation and explain the findings | Latest memory/explanation check passed without an approval exemption or sandbox claim. Earlier answers falsely exempted MCP approval or invented secure sandbox execution; those failures remain preserved. |
| 10 | Run three independent source investigations of recovery, policy and CLI sessions | All three completed in distinct sessions after CPU queue deadlines were corrected. One recovery explanation overstated the approval requirement; factual review remains necessary. |
| 11 | Append a meeting action item and verify exact disk bytes | Passed; preserved CRLF and verified readback and SHA-256. |
| 12 | Fetch live Python JSON documentation and compare `load` with `loads` | Passed after navigation, inline-span, no-match validation and output-budget fixes: a real 10,120-character source excerpt and correct file-stream/string comparison. |
| 13 | Generate and run a complete three-file CSV expense application | Passed all ten real CLI cases after explicit failure feedback and a Jarvis-generated repair in a fresh copy. The first runnable build passed only 4/10 because stdout was Python dictionary syntax. Earlier attempts failed syntax/target-file validation. |

Automatic checks require tool evidence and requested answer terms. A keyword
pass is not a guarantee of factual accuracy. The table explicitly records the
manual answer-quality findings. In particular, MCP always requires approval
for each server start/call, instruction guidance runs from broad to specific,
and uncertain external actions must never be automatically replayed.

## Preserved evidence

- [Consolidated results and scope](../artifacts/reports/real-world-summary-20260927.json).
- [First complete thirteen-task run](../artifacts/projects/real-world-20260927T082342Z/results.json): 8 automatic passes, 5 failures.
- [First focused rerun](../artifacts/projects/real-world-20260927T084542Z/results.json): 5 automatic passes, 2 failures.
- [Second focused rerun](../artifacts/projects/real-world-20260927T090000Z/results.json): 4 automatic passes, 1 generation failure. Its web status was a false positive: the no-match message itself contained the search term; it is not credited as successful source research.
- [Corrected live web check](../artifacts/projects/real-world-20260927T090850Z/results.json): actual 10,120-character documentation excerpt and a correct `load`/`loads` comparison.
- [Local model-template inspection](../artifacts/reports/model-template-diagnostic-20260927.json): installed Qwen template is only `{{ .Prompt }}`; the corrected client resolves it to explicit `qwen_chatml` roles without changing the model.
- [Rerun using corrected role delivery](../artifacts/projects/real-world-20260927T091238Z/results.json): manifest, resume, fork and live source research passed; the runnable expense app initially passed 4/10 CLI cases. The six failures all exposed Python dictionary output instead of JSON.
- [Feedback-guided Jarvis repair and ten passing CLI cases](../artifacts/projects/real-world-20260927T092312Z/results.json), [repaired entry point](../artifacts/projects/real-world-20260927T092312Z/expense_app/main.py), [calculator](../artifacts/projects/real-world-20260927T092312Z/expense_app/ledger.py), and [generated usage guide](../artifacts/projects/real-world-20260927T092312Z/expense_app/README.md).
- [Generated model responses from the focused build](../artifacts/projects/real-world-20260927T084542Z/generated-responses.jsonl), including the rejected Python-file README output.
- [Earlier failed source-inspection baseline](../artifacts/projects/real-world-20260927T081626Z/results.json): five completed tasks failed because requested source/tool observations were missing. Startup and interrupted attempts remain in separate artifact directories.

Raw local server logs and private source/session context are excluded from Git.
Saved results contain the test goals, observed answers and component evidence.
No screenshot or live desktop success is claimed.

## Reproduction and changes

From the application directory:

```powershell
.\.venv\Scripts\python.exe -u scripts/verification/verify_real_world.py
.\.venv\Scripts\python.exe -u scripts/verification/verify_real_world.py --tasks 7,8,9,12,13
.\.venv\Scripts\python.exe -u scripts/verification/verify_real_world.py --repair-from artifacts/projects/real-world-20260927T091238Z/expense_app
```

Run conversation tests 7–9 together. The harness now exits nonzero when an
automatic task fails, retains generated responses, and checks ten expense CLI
cases: normal totals, refunds, decimal precision, blank category, empty input,
invalid amount, missing columns, quoted category, header-only invalid input and
nonfinite amount. Every input CSV must remain unchanged. Earlier build attempts
used the original seven-case specification; neither reached CLI acceptance.
The final repair copied only the three generated files into a fresh workspace,
provided the observed JSON-output failure as an explicit new goal, and used
Jarvis's real coding workflow to modify `main.py`. It then reran all ten CLI
cases. The original failed application and its results were preserved. This
demonstrates a successful feedback-guided repair, not a first-attempt autonomous
build or a general guarantee of coding correctness. Planning also created an
unnecessary empty nested `expense_app` directory in the build attempts.

The trials prompted source-read preflight, source-first repository traversal,
bounded correction of conflicting answer/tool responses, longer queued CPU
deadlines, navigation-free focused web excerpts, a larger bounded toolkit-text
answer budget, and explicit target-file and permission guidance. Inline HTML spans
now preserve adjacent names and whitespace, and no-match messages cannot satisfy
the harness's source check. The installed prompt-only Qwen template was inspected
through local Ollama metadata; inference now supplies explicit role delimiters
using the existing raw Qwen path. Native chat templates keep `/api/chat`. A regression
test teardown now collects Tk callback/variable cycles on the owning thread.

All **376 regression tests passed** after these changes. Launcher readiness
reported `ready` with no missing requirements. Those results are separate from
the live failures above. No models, dependencies or UI were changed.
All completed full/focused trial reports confirm their owned Ollama server was
stopped. The tests used the current Windows/Python environment; cross-platform
and other Python-version compatibility were not certified.
