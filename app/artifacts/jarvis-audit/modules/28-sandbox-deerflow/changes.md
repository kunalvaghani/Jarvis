# Changes and keep/revert decisions

Retained fixes:

- Reject linked mount ancestors and non-immutable/wrong-architecture image IDs; pin new container IDs and target inspected IDs for exec/kill/cleanup.
- Bound and validate checkpoint reads; pending calls become uncertain on resume and cannot dispatch a different effect.
- Lock sandbox writes, use exclusive file creation, and apply the 20-effect budget consistently.
- Kill only the attested job after uncertain exec/timeout; preserve state and refuse replay.
- Validate Docker config types, including falsy non-object input; classify non-object worker JSON as a protocol error.
- Verify expected media files from disk with explicit format-specific proof levels.
- Replace whole-tree inventory materialization with bounded lexical traversal, preserving original per-file parent/link/resolved-root checks.

For 3,000 synthetic files and identical first 200 inventory rows, warm p50/p95 changed from 717.24235/797.70220 ms to 646.88830/739.16570 ms; peak temporary Python allocation 5313699 → 719966 bytes. Retain final traversal. The first candidate was slower despite lower peak allocation (candidate-1 samples preserved); redundant whole-application ancestor checks per file were replaced with the original per-file root/link checks, while validating application ancestors at traversal/directory boundaries. Platform Path sorting is retained, including Windows case ordering. Filesystem/antivirus timing varies; this is not a general render/container/model speedup. Five initial iterations are not cold processes. Budgets can refuse oversized/deep directories; symlink/path checks are best effort and do not prove handle-based race containment. Media validation adds I/O and does not establish semantic content correctness. Checkpoint refusal and uncertainty can require manual inspection; no replay/reset is a repair.

- `docs/deerflow-sandbox.md`
- `docs/deerflow.md`
- `docs/system-map.md`
- `jarvis/deerflow.py`
- `jarvis/deerflow_media.py`
- `jarvis/deerflow_sandbox.py`
- `jarvis/docker_runtime.py`
- `README.md`
- `../README.md`
- `scripts/verification/audit_catalog.py`
- `tests/test_audit_result_accounting.py`
- `tests/test_docker_sandbox.py`
- `tests/test_sandbox_deerflow_audit.py`
- `scripts/verification/verify_sandbox_deerflow_audit.py`
- `scripts/verification/verify_sandbox_deerflow_container.py`
- `scripts/verification/verify_sandbox_deerflow_renderers.py`
- `scripts/verification/report_sandbox_deerflow_audit.py`
- `scripts/verification/verify_sandbox_deerflow_artifacts.py`

Module/global generated artifacts are listed in generated-files.json. No commit/reset or unrelated diff was erased.
