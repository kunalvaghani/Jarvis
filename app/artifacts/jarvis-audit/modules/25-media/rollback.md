# Rollback

Dirty branch audit/12-tool-registry, commit9bf5528e6d490fc3bbe92d0c62bcffae6c0946b6 preserved. A clean HEAD worktree would omit inherited fixes, so scoped preimages are in .jarvis-runtime/jarvis-audit/module25-pre. Review source.patch and hashes; restore only matched module25 hunks and preserve later/user edits. New files listed in files-changed.json. No commit/reset/install/config/profile change. Do not restart media or replay uncertain playback while rolling back; inspect fresh state first. Re-run focused assertions and launcher --check after rollback. No live rollback trial.
