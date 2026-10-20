# Confirmed findings

## P33-001 — P1: approved generated source integrity is not enforced at invocation

Registration screens/tests and stores code_sha256. mcp_synthesis.configurations discards that identity from returned config; mcp_bridge.execute starts the mounted source without verifying it. Health verifies only when called separately. Real offline Docker fixture registers a valid SHA256 tool, replaces its implementation after registration, and calls through ToolRegistry. It returns UNREVIEWED_SYNTHETIC_RESULT, despite a different current digest. Per-call approval shows command/path/arguments, not the changed source/hash. See generated-drift-observation.json and permission-manifest.json. This proves an execution integrity gap, not a container escape or demonstrated remote ability to edit host source. Container network/filesystem restrictions remained active.

Failing test: test_JRV_33_013_generated_source_change_rejected_before_call. Fix SHA: none. Status APPLIES / OPEN. Source: jarvis/mcp_synthesis.py configurations/health; jarvis/mcp_bridge.py execute.

## P33-002 — P2: advertised input schema is not validated before tools/call

The real local server advertises required integer count and additionalProperties=false. A string count reaches tools/call and is accepted as evidence. execute checks the allowlisted name and argument-object shape only. Test test_JRV_33_005_schema_invalid_call_must_not_reach_server fails. Source: mcp_bridge.execute. No real external write occurred. Schema version tracking and dependent-skill revalidation remain additionally BLOCKED, not falsely counted as this test's proof.

## P33-003 — P2: malformed tool result accepted as evidence

The local server returns content as a string and isError as string "false". The dict passes the check that isError is not literal True and becomes ToolResult evidence. Test test_JRV_33_006_malformed_result_must_raise_typed_error fails. This does not prove final task completion/verification accepts it. Source: mcp_bridge.execute.

Prior P32-001 ownership and P32-002 repair-log privacy remain OPEN on this unchanged SHA. No claim that Prompt 32 was repaired by starting 33.
