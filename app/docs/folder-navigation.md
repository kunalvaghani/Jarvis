# Folder navigation and preferences

Updated 2026-10-01.

## What failed and what changed

The earlier parser passed phrases such as “Ollama folder in D drive” to generic application/file lookup as one name. Indexed fuzzy search also required typo words to occur in the name before ranking candidates. A spoken drive is now a folder constraint, and folder lookup supplies bounded spelling candidates before fuzzy ranking.

Examples:

- “Jarvis, open Ollama folder in D drive.”
- “Jarvis, open Ollama in D drive.”
- “Jarvis, open folder Downloads.”
- “Jarvis, open folder parent-name folder-name.”
- “Jarvis, open folder D:\some\actual\folder.”

Configured `folders` aliases take precedence and must point to an existing folder on the requested drive. This installation includes the user-reported Ollama speech forms “Olamind” and “Olamide”, grounded in the actual Ollama folder. They are explicit aliases, not a general claim that unrelated recognition errors can be understood.

Drive-root entries are read live, without recursively scanning the disk. Deeper folders use the existing [catalogue index](../scripts/catalog/build_catalog_index.py); known folder-open history also supplies existing candidates. Exact names win before partial/close spelling matches. An explicit drive request favors its root folder over identically named dependency folders. Requests stay on the specified drive and recheck folder existence. Names that literally end in “folder” retain their exact-name match.

Folder opening can use a higher open count among equally named candidates. Ties and unclear spelling still present numbered choices. A file-write destination uses unambiguous resolution rather than the folder-opening preference. Generic file opening and deletion retain their existing contracts.

## Usage memory

Successful `os.startfile` dispatches from folder/project opening update the private, Git-ignored `.jarvis-runtime/folder-usage.json`. Up to 500 recent folders retain their open count, latest request and UTC timestamp. Cancelled requests and failed launches are not counted. The configured Obsidian vault receives `Jarvis Folder Usage.md`, linked from Jarvis Brain. A corrupt index is preserved and preference learning stops until it is repaired; ordinary lookup remains available. Memory save failure is recorded without replaying the launch.

Counts cover folder opens requested through Jarvis. Manual Explorer activity outside these handlers is not counted. A count means Windows accepted the launch request; it does not independently prove Explorer displayed the folder. All PC paths and usage details remain in local ignored runtime/vault files, not this document.

## Custom skills

See [adding personal skills](skills-and-learning.md#adding-personal-skills) for the new `custom-skills` folder and creation helper. Folder preferences choose paths; workflow guides supply planning context. Neither grants permission to write/delete files or installs missing app integrations.

## Verification

2026-10-01 live check: [actual folder lookup and Explorer evidence](../artifacts/reports/folder-lookup-check.json) resolved all five reported/corrected Ollama phrases to the existing requested folder. Four configured-alias lookups took **0.0043–0.0049 seconds**; the unconfigured close spelling “Olama” took **0.149 seconds**. One real Explorer launch was independently checked through a fresh `Shell.Application` folder path and confirmed in **0.881 seconds**. These times exclude microphone recognition and speech output. The verification opened the folder once and did not replay any action.

Run `.venv\Scripts\python.exe -m scripts.verification.verify_folder_lookup` for actual read-only resolution checks. Add `--live` to explicitly open that folder once and check Explorer. The test targets this installation's existing Ollama path.

Regression tests cover parsed qualifiers, live unindexed folders, indexed misspellings, literal suffix names, drive confinement, persisted preferences, write-destination ambiguity, deleted targets, ties, failed launches, disk write failure and corrupt history. Custom-skill checks cover catalogue/context/vault copies, helper validation, duplicate names and oversized guides. Final regression/readiness results are recorded in the application README.

2026-10-01 regression/readiness: **547 tests passed in 30.589 seconds**. Launcher readiness returned `ready`, no missing components, and native Qwen planning. These checks are separate from the single live Explorer check above. Updated folder guidance and tool descriptions were refreshed in the configured Obsidian vault; no personal custom guide was invented or installed.
