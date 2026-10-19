# Compatibility and reproducibility

Read actual installed distributions/executable versions; no assumptions that the isolated worktree contains copied environments/assets. Launcher check remains repair_required there even though the original install has ten environments. CPU brain and CUDA F5/training groups are distinct; version metadata alone does not prove ABI/device correctness. nvcc missing on PATH is not proof bundled CUDA runtimes are missing.

Lockfile map shows ranged/unhashed project requirements plus integration resolved/Node lockfiles. Pip HTTP cache and nine locally built wheels are an inventory, not a complete offline wheelhouse. Clean rebuild, offline installation, unsupported-major migration, package mutation while workers run and tested uninstall/rollback are BLOCKED because no such changes were authorized. No dependencies changed; no before/after migration success invented.

The supported safe journey exercised is installed-runtime readiness and local metadata/model-tag inventory, with explicit isolated missing-environment diagnostics. It does not certify a clean install or full live application startup. Whole relevant release checks stopped after P1 reproduction.
