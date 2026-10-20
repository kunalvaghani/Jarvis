# Rollback / offline reproducibility

No package/model migration or uninstall occurred, so actual package rollback is NOT RUN. Source patch is reviewable and reversible; preserve new tests/evidence and revert only that patch if rejecting it, never reset user work. Do not claim a documented rollback plan is tested uninstall proof.

For authorized follow-up: produce complete per-interpreter Windows/native/CUDA hash locks and wheelhouse; snapshot the approved artifact set; stage without replacing running workers; verify imports, CLI entrypoints, dependency graph, ABI/fidelity and enabled/disabled routes; compare actual readback; preserve old env/weights and switch routing only after postconditions. Exercise failed promotion and restored routing in a disposable fixture, then authorize real promotion separately. Venv relocation must be addressed first. No blind deletion/recreation or download is authorized by this report.
