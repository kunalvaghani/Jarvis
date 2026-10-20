# Current findings

## P33-004 — P1 / NEWLY REPRODUCED: credential context can change after approval

JRV-33-022 executes the real ToolRegistry → toolkits.execute → remote_tool path with the API transport replaced by an in-memory ledger. Start with synthetic account A credential and event request. The approval callback simulates switching current credentials to account B while approval was pending. The returned approval detail contains action/calendar ID/event content but no account identity. remote_tool then rereads os.environ and dispatches POST with account B credential. The ledger records the account-A event body targeting B. No network call/event occurred.

Source: jarvis/toolkits.py execute approval and remote_tool environment lookup/calendar headers. Source is unchanged by 2c4ea56, so this is a preexisting uncovered boundary, not a new repair regression. Scope: a credential switch inside the running process; no claim that Windows externally changes an existing process environment or that current UI supplies an account-switch action. Stable-token mock read and denied-write controls pass. Actual account scopes/consent remain unverified.

Reproduce: test_provider_context.py::test_JRV_33_022_account_switch_during_approval_must_not_write_other_workspace. Evidence: provider-context.xml and account-switch-observation.json. Fix SHA NONE. Status APPLIES/OPEN.

## P33-002 — P2 / PARTIAL repair: input/output schema checks have gaps

The original string-for-integer transport assertion now passes. However validate_schema_value walks only value[:1000] without rejecting longer arrays; invalid element 1001 reaches real local tools/call. The same function accepts an invalid tail in outputSchema structured content. Native Python equality makes false satisfy enum [0], and true satisfy const 1. Three input edge assertions and one output assertion fail. Bounds must fail closed rather than silently accepting unchecked tails; JSON equality must distinguish booleans and numbers.

Tests: test_JRV_33_005_array_tail_is_validated_before_real_stdio_call; test_JRV_33_006_output_array_tail_is_validated; test_JRV_33_005_json_boolean_is_not_numeric_enum_or_const (2 parameterizations). Evidence contract-edges.xml and array-tail-observation.json. No provider effects in these tests.

## P33-003 — P2 / PARTIAL repair: nested resource contents remain unchecked

The original malformed content/isError assertion now passes. A real local server returning content=[{type:resource,resource:{}}] is still accepted as ToolResult evidence. validate_result verifies only resource is a dict; required URI and valid text/blob resource shape are not checked. test_JRV_33_006_empty_embedded_resource_is_not_valid_evidence fails; resource-observation.json preserves exact output. This proves evidence acceptance, not final goal verification.

## Verified original fixes

P33-001 FIXED for original source-drift reproduction and new identity/private-copy checks. P32-001 and P32-002 FIXED for original native sibling-process and synthetic repair-log failures. All original assertions unchanged (byte-identical copied fixture files); repair-replay.xml has 28 PASS. Full Prompt 32/33 acceptance remains BLOCKED by further requirements. No blanket privacy guarantee from pattern-based redaction, no account/live/concurrency certification.
