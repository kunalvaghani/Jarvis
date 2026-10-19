# Compatibility and readiness

Python 3.10.6 host; existing Docker Linux engine 29.8.2. See protocol.json for actual labelled image ID/SDK and launcher-check.json for read-only readiness. SDK direct build pin is mcp==2.3.0; historical image package inventory is retained unchanged. No dependencies fetched or changed. Exact stdio protocol 2025-11-25 is supported; other versions fail negotiation. HTTP MCP and token-refresh orchestration are unsupported in this bridge.

Fresh runs: baseline 94 PASS; Phase 3 34 PASS; neighbors 36 PASS; boundary 5 PASS/3 FAIL. Total 169 PASS/3 FAIL, no skips. Isolated worktree uses the original installed interpreter/utility dependencies through the saved read-only wrapper; reviewed source/cwd and test data remain isolated. Launcher exits 1 / repair_required for missing isolated environments and model assets; Docker availability is readiness, not a live-account test.

Full final acceptance stopped on unresolved P1. No new source was edited, so there is no after-fix success claim. Disabled server direct execution rejects; comprehensive enabled/disabled cloud/account routes and soak/concurrency acceptance remain BLOCKED.
