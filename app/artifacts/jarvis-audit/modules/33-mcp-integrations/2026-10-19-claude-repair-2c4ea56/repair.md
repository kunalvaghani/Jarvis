# Prompt 33 follow-up repairs — P33-004, P33-002, P33-003 and the added coverage (Claude, 2026-10-19 IST)

Branch `claude`, base `2c4ea56`. Responds to Codex's handoff from
`modules/33-mcp-integrations/2026-10-19-independent-2c4ea56/` (codex-review worktree). That handoff confirmed P32-001,
P32-002 and P33-001 fixed, reproduced P33-004 (P1) and reported P33-002/P33-003 as partial. No Codex re-review of this
repair exists yet; Prompt 33 stays BLOCKED until it does. No module 34 work was started.

## Repairs

| ID | Codex finding | Repair |
| --- | --- | --- |
| **P33-004** (P1) | An approved write re-read `os.environ` at dispatch; switching credentials while the card was pending sent account A's event as account B | New `jarvis/provider_identity.py`. Before the card is shown, `ProviderContext` captures the provider's **account identity** (non-secret keys: `JARVIS_GOOGLE_ACCOUNT`, `JARVIS_GITHUB_ACCOUNT`, `JARVIS_SLACK_WORKSPACE`, `JARVIS_TWITTER_ACCOUNT`, Jira URL + user, email SMTP host + user), per-process HMAC fingerprints of each credential, and a snapshot of the `JARVIS_*` settings. The card shows provider, account, `identity_verified` and target, never a token. Immediately before dispatch `recheck()` refuses an **account switch** (identity changed) and refuses any credential change when the identity is not configured (`unverified`). For an unchanged verified identity it treats a changed token as **rotation**: allowed, using that account's current token, recorded in task evidence. `remote_tool` dispatches with the approved context's settings, not the live environment. Post-call redaction covers current and approved-context credentials. |
| **P33-002** (P2, partial) | Only `value[:1000]` was validated; `enum`/`const` used Python equality (`False == 0`, `True == 1`) | Every array item and object field is validated. A schema-independent size pre-check counts every node of the whole value: more than 10,000 items in any array or object, or 100,000 nodes in total, rejects the **whole** value, and nothing is sliced. `json_equal` makes booleans distinct from numbers (`1 == 1.0` still holds) and compares containers deeply; it is used for `enum` and `const`. Recursion depth stays bounded; the strict supported-schema rule and no-retry behaviour are unchanged. |
| **P33-003** (P2, partial) | `{type: resource, resource: {}}` was accepted | Content blocks are checked against the supported contract. Each block type has required fields with types, typed optional fields (`annotations`, `_meta`, and for links `title`/`description`/`mimeType`/`size`), and unknown fields are rejected. An embedded resource needs a non-empty `uri` plus **exactly one** string `text` or `blob`, with typed optional `mimeType`/`title`/`name`/`_meta`/`annotations`. Malformed results still raise `ContractError` after the `action_attempted` checkpoint, so the effect stays uncertain and resume is blocked. |
| Added: dependent skills | Missing MCP schema dependent-skill invalidation | `mcp_synthesis.invalidate_dependent_skills` disables skills whose guidance or tools reference a drifted generated server. It records `{'disabled_by': 'mcp_drift', 'server': …}` in the skill store and marks the live catalog row, so `SkillMemory.context` no longer **retrieves** them. Every drift path in the bridge passes the session's skills. A healthy `health()` restores exactly those skills (`restore_dependent_skills`). |

Files: `jarvis/provider_identity.py` (new), `jarvis/toolkits.py`, `jarvis/mcp_contract.py`, `jarvis/mcp_synthesis.py`,
`jarvis/mcp_bridge.py`, `tests/test_prompt33_followup.py` (new).

## Verification (2026-10-19)

| Check | Result |
| --- | --- |
| Codex's new `test_contract_edges.py` + `test_provider_context.py`, **byte-identical** copies (run from an ignored folder under `app/.jarvis-runtime` so their own path logic finds the repaired source) | **9 passed** (was 5 FAIL: array tail ×2, boolean enum/const ×2, empty resource; plus P33-004) — [log](codex-new-tests-unchanged.log), [xml](codex-new-tests-unchanged.xml) |
| Codex's original repair replay (`test_mcp_boundaries.py`, `test_recovery_boundaries.py`), byte-identical | **13 passed** — [log](codex-original-replay-unchanged.log) |
| Claude's added tests: verified account switch writes nothing; same-account token rotation proceeds and is recorded; unverified credential change refused; no token on the card; unchanged context dispatches with the approved token; Jira identity; over-budget arrays and nested values rejected whole; JSON equality; 10 content-block shapes; uncertain-write checkpoint kept after a malformed result; drift disables dependent skills, they are no longer retrieved and health restores them; drift through the bridge path; 16-thread concurrent registry updates | 20 passed; with the earlier Prompt 32/33 repair tests **48 passed** — [log](repair-tests.log) |
| All Prompt 32/33 tests together, two consecutive runs | 70 passed each run |
| Full regression (23:34–23:52 IST, Jarvis running) | **3,469 passed / 0 failed / 147 skipped (all BLOCKED)** — [log](full-regression.log), [xml](full-regression.xml) |
| `python -m jarvis.launcher --check` | `ready` — [launcher-check.json](launcher-check.json) |

## Not addressed (still open)

- **Identity is only as good as its configuration.** If a user switches the token *and* sets the account label to
  the new account, Jarvis cannot distinguish that from a legitimate account change; it is refused because the
  identity changed. If a user leaves the label unchanged while pointing the token at another account, it is treated as
  rotation. Real account verification (asking the provider "who am I") is not done, because the tests run with no
  network.
- Gmail API tools (OAuth token file in `gmail_api.py`) and Firecrawl reads were not changed in this repair.
- Live accounts, real scopes and consent, MCP schema-version history beyond the pinned digest, multi-process
  concurrent registration (the lock is in-process), and launcher `repair_required` in Codex's sandbox remain BLOCKED
  or NOT RUN.
