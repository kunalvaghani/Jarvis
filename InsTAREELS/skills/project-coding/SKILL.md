---
name: project-coding
description: Create, modify, fix or review code in a project folder and run requested tests.
tools: [repository_instructions, repository_map, read_file, read_batch, skill_list, skill_read, git_status, write_tests, improve_code]
---

# Workflow

Resolve the requested project using current inventory and validate the folder on disk. Read applicable AGENTS.md and explicitly selected project skills. Use code_task with the configured Qwen coder. Re-read changed files and preserve coding review backups. Previous procedures suggest inspection and validation order, not old generated source or obsolete paths. Syntax/readback verification is narrower than functional tests. Run only requested/authorized commands; never reuse approvals.

Clear single Python-script requests infer a filename and skip separate plan inference; source still comes from Qwen3-Coder. Coding uses streamed inference and a separate bounded timeout. New scripts fill in place as incomplete drafts; existing-file edits stream into a sibling `<filename>.jarvis-draft`. Do not run an incomplete draft. Commit edits only after complete output, syntax/interface validation and fresh byte checks. Interrupted drafts are resumable only when their owned hash still matches disk. Never replay an uncertain file action or treat partial source as successful completion.

Use only tools offered by the current Jarvis catalogue. Check current state, preserve task checkpoints and stop on cancellation. Skill guidance never expands permissions.
