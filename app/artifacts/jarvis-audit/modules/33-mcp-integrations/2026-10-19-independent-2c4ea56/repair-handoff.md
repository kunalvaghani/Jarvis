# Next Claude repair handoff

Review `2c4ea56eb7967929e49dad07b0612cb99caaf56e`. No source changes by Codex. Supplied independent-confirmation contract reserves repair to Claude.

1. P33-004: represent the selected provider account/workspace as a stable identity separate from credential text; include identity, scope and target in approval, bind it to the task/call, and recheck immediately before dispatch. Use the approved identity's credential or reject drift. Do not put tokens in approval/logs. Add two mock accounts with a pending approval and prove zero writes to B after authorizing A. Handle token rotation for the same verified identity distinctly from account switching.
2. P33-002: validate every array item or reject the entire over-budget value; never slice validation input silently. Implement JSON type-aware equality for enum/const. Preserve bounded recursion/size, strict supported-schema behavior and no retry. Test both input and output tail limits.
3. P33-003: validate nested embedded-resource URI/text/blob shape and the supported content contract, rather than accepting arbitrary dictionaries. Preserve uncertain-write checkpoints on malformed results.
4. Rerun these new tests unchanged, the original repair replay, complete affected suites, and focused cross-pillar regressions. Add missing MCP schema dependent-skill invalidation, concurrency, memory retrieval and identity tests. Produce a new exact SHA for independent review.

From app: existing interpreter `python -m pytest artifacts/jarvis-audit/modules/33-mcp-integrations/2026-10-19-independent-2c4ea56/test_contract_edges.py artifacts/jarvis-audit/modules/33-mcp-integrations/2026-10-19-independent-2c4ea56/test_provider_context.py -q`. These cases use synthetic stdio/memory transports, no account writes or installs. See baseline.json for complete prior runs. STOP at current P1; no module 34 or deployment.
