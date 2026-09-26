# Autonomous coding improvements

Reviewed [agenticSeek](https://github.com/Fosowl/agenticSeek) at commit
`d057a3a6daff54265c165baf59fa902c40606f0d`, particularly its CoderAgent,
FileAgent, file finder and coder prompt. Its bounded generate/check/feedback
workflow informed these independently implemented improvements. No upstream
runtime code or prompt is imported into Jarvis. Downloaded reference sources
remain in `integrations/agenticseek-*`; the upstream GPLv3 license is retained
at `integrations/AGENTICSEEK-LICENSE`.

Jarvis now discovers relevant sibling sources and project configuration,
prioritizes Python imports, and supplies bounded context to planning and edits.
Hidden files and common credential filenames are excluded from context discovery.
Newly generated sibling code is shared with subsequent files in a multi-file task.

For existing files, the model can propose exact find/replace operations. Every
match must be unique; edits are materialized and validated before writing.
Python edits preserve unrelated top-level functions and classes. Validation
feedback allows at most three inference attempts, without replaying writes.
Ordinary text replacement requests retain the desktop file-edit workflow.

Before project commits, `.jarvis-runtime/coding/<id>/` preserves original bytes,
a unified diff and before/after hashes. Task checkpoints record the review path
and each attempted write. An uncertain commit blocks automatic replay and requires
fresh inspection; backups are not automatically restored. Existing files are
checked for concurrent changes and committed atomically one file at a time.
The entire multi-file task is not a filesystem transaction.

Tasks remain limited to three small files and three directories. More source
extensions are recognized, including C, Go, Java, Rust, SQL and PowerShell.
Python and JSON receive syntax validation; other languages require project checks
by the user. Jarvis does not execute arbitrary generated programs or install
dependencies automatically. The existing known calculator template keeps its
bounded functional checks. No new dependency or long-running service was added.

Validation covers exact edits, ambiguous-match correction, interface retention,
related-source selection, multi-file consistency and an injected failure after
atomic replacement. The live local-model workflow creates a Python helper and
then adds subtraction. Recovery shutdown/backoff remains covered by the existing
regression suite.
