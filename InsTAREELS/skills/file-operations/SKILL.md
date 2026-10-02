---
name: file-operations
description: Create, modify or locate files and folders, open projects, and handle approved deletion.
---

# Workflow

Resolve the current folder and exact requested filename. Inspect existing files before edits. Use create_file/modify_file with dictated content, never content reconstructed from a learned procedure. Recheck current bytes and destination before a write. Deletion needs explicit approval. Verify file existence/content after changes. If an earlier write had an uncertain result, inspect before any further attempt.

Folder names can include a drive qualifier, such as "Ollama folder in D drive". Keep the drive constraint while resolving. Opening uses configured aliases, fresh drive-root entries and indexed deeper folders, with usage preferences among equally named folders. Folder usage records accepted Explorer launches, not verified visibility. A file-write destination still requires unambiguous resolution; do not use an opening preference as authorization to write. No match or stale deep index requires a clearer parent/full path or a catalogue refresh.

Use only tools offered by the current Jarvis catalogue. Check current state, preserve task checkpoints and stop on cancellation. Skill guidance never expands permissions.

For an explicitly requested application document save, use save_file with the exact filename and folder. Native Save As controls take priority; the enabled visual fallback can handle missing filename/button controls. Verify the absolute filename field before Save, obtain runtime approval before replacing that exact existing file, and independently check the overwrite dialog's filename. Confirm the resulting named file through stable disk readback and hash; dialog disappearance alone does not establish a save. Formats that add extensions, truncate the filename, use another process or leave the dialog unresolved require review. Never retry an uncertain Save click.
