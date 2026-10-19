# Remaining Claude repair

At `cd8861ce720ade303485ee2023430dd8c6b4f0ba`, P33-004 is still P1/PARTIAL. Keep the passing P33-001/002/003 and original P32 controls intact.

Do not call a credential's principal verified from a user-configured label. Safe immediate behavior: if the credential changes during pending approval and its actual principal cannot be established, reject before dispatch and obtain fresh approval/context. Alternatively retain the approved credential snapshot rather than swapping in an unverified replacement. Allow automatic rotation only with independently checked provider principal/workspace/scope evidence bound to the approved identity, never label equality alone. Do not send a write to discover the account, log tokens, or introduce blind retries. Missing identity verification must fail closed; no live account/network setup is required to implement the refusal.

Reproduce with `python -m pytest artifacts/jarvis-audit/modules/33-mcp-integrations/2026-10-19-independent-cd8861c/test_configured_identity.py -q`. Preserve both parameterized assertions: stable A succeeds and B's token never writes. Add a separate real or explicitly mocked identity-verification boundary test for legitimate same-principal rotation; existing tests that assume every changed token with label A belongs to A are not identity evidence.

Rerun the 57 original/follow-up checks, 223 direct regressions, 19 focused cross-pillar checks, and this case. Supply exact fix SHA. Codex source repairs remain reserved to Claude under the supplied read-only confirmation contract. STOP at current P1; do not start module 34 or deploy.
