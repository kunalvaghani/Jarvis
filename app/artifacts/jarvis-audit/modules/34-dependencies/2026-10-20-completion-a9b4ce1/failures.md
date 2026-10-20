# Remaining limits and open review findings

No final executed regression failed. One skipped forced CUDA interruption test remains a release gate. Original P34-001 and P34-002 default unapproved admission reproductions now pass; full approved installer/download acceptance is not established.

P34-R1 (open source-review safety finding): setup_brain.approved_pull verifies digest and byte size for a registry tag, then pulls the mutable tag. The tag can change between checks; post-pull digest validation happens after download and cannot enforce the original byte budget. No registry exploit/download was attempted. Exact immutable transport needs implementation and injected race tests before approved downloads are release-ready.

P34-R2 (unverified compatibility risk): stage_environment builds a venv under a temporary name and renames it. Generated console scripts may embed the old absolute path. Import checks alone do not establish relocated executable correctness. No real install/rebuild was authorized; validate executables or redesign routing before promotion.

P34-R3 (unverified artifact race): lock and wheelhouse are checked then read again by pip. Hash requirements protect selected artifacts but do not freeze the reviewed lock against concurrent mutation. Snapshot/validate immutable artifacts at execution and test changes between check and launch. No exploit executed.

All remaining numbered-case acceptance limits and earlier prompt gaps are tracked in [Claude handoff](../../../../../docs/CLAUDE_HANDOFF.md). Continue safe independent work; these limits do not authorize installs, downloads, drivers or live side effects.
