# Claude repair handoff

Pinned SHA and raw assertions are in baseline.json/boundaries.xml. Reproduce from app with the existing interpreter: `python -m pytest artifacts/jarvis-audit/modules/33-mcp-integrations/2026-10-19-independent-0e3ad47/test_mcp_boundaries.py -q`. Docker tests need the existing labelled jarvis-mcp-runtime:1 image; do not install/rebuild silently.

1. P33-001: retain generated tool identity through configuration/dispatch, enforce approved implementation/spec/schema/image identity immediately before execution, and prevent mutation between validation and mounted execution. Disable drifted entries and dependent skills until revalidated/reapproved. Merely calling health earlier leaves a race. Include source/version identity in final approval. Preserve explicit per-call approval, sandbox and no-retry behavior.
2. P33-002: validate bounded advertised input schema and exact arguments before tools/call; define supported schema subset, reject unsupported schemas, pin schema/version and invalidate dependent skill contracts on change.
3. P33-003: validate MCP result envelopes/content/structured output/error flag types and output schema where supplied; raise typed failure while preserving uncertainty for attempted writes. Do not manufacture success or retry.
4. Run failing assertions unchanged, then the 94 baseline, 34 living-skill and 36 routing/recovery checks, plus concurrent registration and schema/skill lineage/account-switch cases still blocked here. Reverify prior Prompt 32 P1s independently. Produce exact fix SHA for new Codex confirmation.

Codex made no application source fix under the read-only independent-confirmation contract. STOP on P1; no module 34 or deployment.
