# Rollback

Preserved dirty audit/12-tool-registry at commit 9bf5528e6d490fc3bbe92d0c62bcffae6c0946b6. Preimages: .jarvis-runtime/jarvis-audit/module28-pre. Review source.patch/source-hashes.json and restore matching hunks only, preserving inherited/user/later changes; no reset to HEAD or personal file deletion.

No dependency/platform/config update occurred. Owned fixture containers were already removed and output files preserved. Keep state.json and uncertain call records; do not clear/replay jobs. Pause affected tasks before rollback: older code lacks pending-call fencing, ancestor guards, strict write budgets, inspected-ID cleanup and media proof. Re-run focused/readiness after rollback. No live rollback trial was executed.
