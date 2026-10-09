---
name: file-operations
description: Create, modify or locate files and folders, open projects, and handle approved deletion.
---

# Workflow

Resolve the current folder and exact requested filename. Inspect existing files before edits. Use create_file/modify_file with dictated content, never content reconstructed from a learned procedure. Recheck current bytes and destination before a write. Deletion needs explicit approval. Verify file existence/content after changes. If an earlier write had an uncertain result, inspect before any further attempt.

For image resizing or metadata removal, choose skill_image_process or skill_strip_exif. For dataset inspection/conversion use skill_csv_profile/skill_csv_parquet. Use skill_config_validate before treating JSON/YAML as valid syntax; it does not validate an unspecified schema. Choose skill_markdown_pdf for an existing Markdown document, skill_calendar_ics for a local invitation, skill_subtitles_srt for timed segments, and skill_zip_extract for a filtered safe extraction. Encryption uses skill_file_crypto with a local DPAPI key_id; never put keys in prompts. skill_agent_state uses JSON, never pickle. Named renaming and formatting use skill_regex_rename and skill_format_python. Inspect a dry-run rename before requesting the mutation. Only tools with current validation appear; unavailable symlink privileges must not trigger escalation or a replacement shortcut. See docs/utility-skills.md for all argument contracts.

Folder names can include a drive qualifier, such as "Ollama folder in D drive". Keep the drive constraint while resolving. Opening uses configured aliases, fresh drive-root entries and indexed deeper folders, with usage preferences among equally named folders. Folder usage records accepted Explorer launches, not verified visibility. A file-write destination still requires unambiguous resolution; do not use an opening preference as authorization to write. No match or stale deep index requires a clearer parent/full path or a catalogue refresh.

Use only tools offered by the current Jarvis catalogue. Check current state, preserve task checkpoints and stop on cancellation. Skill guidance never expands permissions.

For an explicitly requested application document save, use save_file with the exact filename and folder. Native Save As controls take priority; the enabled visual fallback can handle missing filename/button controls. Verify the absolute filename field before Save, obtain runtime approval before replacing that exact existing file, and independently check the overwrite dialog's filename. Confirm the resulting named file through stable disk readback and hash; dialog disappearance alone does not establish a save. Formats that add extensions, truncate the filename, use another process or leave the dialog unresolved require review. Never retry an uncertain Save click.
