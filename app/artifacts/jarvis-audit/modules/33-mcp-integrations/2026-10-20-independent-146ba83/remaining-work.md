# Remaining Prompt 33 acceptance

All four reported P33 findings now have independent passing repros. No source repair is pending for those findings. To complete the wider module:

1. Implement/review real read-only provider principal verification and validate scopes/consent/refresh against explicitly authorized accounts. Until then preserve credential-change refusal and fresh approval.
2. Prove full schema-version migration with dependent-skill compatibility tests and lineage, including memory references; current literal-reference invalidation/restore is narrower.
3. Exercise registration concurrently with another active task and multi-process readers/writers; the existing 16-thread drift-update test is narrower.
4. Establish ReasoningBank retrieval-to-call policy for disabled/provisional MCPs and actual tool/version identity.
5. Validate filesystem-policy narrowing for trusted external host servers, provider rate-limit read backoff, and Blender/Unreal API-unavailable MCP routes. Current generated Docker restrictions and no-write-retry controls do not prove those cases.
6. Complete full live/native startup/worker/service acceptance and representative resource measurements in a prepared environment; this worktree's launcher remains repair_required.

No module 34 work, deployment, account writes, packages or real verifier setup is authorized by this evidence packet. The selected fixture run is complete; release/full-module verdict remains NOT READY/BLOCKED under Prompt 33's missing-safety-evidence gate.
