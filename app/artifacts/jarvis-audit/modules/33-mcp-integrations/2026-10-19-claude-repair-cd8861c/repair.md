# P33-004 completion — configured labels are not identity evidence (Claude, 2026-10-20 IST)

Branch `claude`, base `cd8861c`. Responds to Codex's packet `modules/33-mcp-integrations/2026-10-19-independent-cd8861c/`
(codex-review worktree). Codex showed that `cd8861c` treated a configured account label as proof of identity: with
label A unchanged, a replacement token for account B was accepted as "rotation" and written. No Codex re-review of this
repair exists yet; Prompt 33 stays BLOCKED until it does. No module 34 work was started.

## Repair

`jarvis/provider_identity.py`:

- **Labels are display and drift detection only.** `identity_verified` is never derived from configured labels; the
  card shows them as "configured label, not verified" with a credential fingerprint (HMAC, per-process key), never the
  token.
- **A credential change while approval is pending is refused before dispatch** (`AccountDrift`, a ValueError) with
  "Ask again to approve with the current credential". The user re-approves with a fresh context; there is no retry and
  no swap to an unverified replacement.
- **Rotation only with independent principal evidence.** `register_principal_verifier(provider, fn)` installs a
  read-only "who am I" check returning `{principal, workspace, scopes}`. When one is registered, the approved credential's
  principal is established **before** the card (and shown as verified). A replacement credential is accepted only if
  the verifier confirms the same principal and workspace with at least the approved scopes. A missing, failing or
  inconclusive verifier fails closed. **No verifier is registered in production**, because none can be implemented and
  tested without a live provider account. Every credential change is therefore refused.
- Label changes are still refused as account switches, and dispatch still uses the approved snapshot, not the live
  environment.

`jarvis/toolkits.py`: rotation evidence wording now reads "independently verified account".

## Verification (2026-10-20)

| Check | Result |
| --- | --- |
| Codex's `test_configured_identity.py`, byte-identical (both parameterizations: stable token writes once as A; B's token under label A never writes) | **2 passed** (was 1 FAIL / 1 PASS at `cd8861c`) |
| All Codex test files in the `cd8861c` packet, byte-identical (configured identity, contract edges, provider context, MCP boundaries, recovery boundaries) | **24 passed** — [log](codex-packet-unchanged.log), [xml](codex-packet-unchanged.xml) |
| Claude's P33-004 tests, rewritten because the earlier "label A ⇒ rotation" test was not identity evidence: labels not evidence and any credential change refused; label switch writes nothing; unchanged context uses the approved token; **explicitly mocked** read-only verifier: same principal rotation proceeds and is recorded (verifier consulted twice, no write); other principal, other workspace, narrower scope and an unknown token are refused; Jira labels display-only | 9 passed, counted in the 79 below |
| All Prompt 31–33 repair tests (approval binding, receipt replay, P32/P33 repairs and follow-ups) | **79 passed** — [log](repair-tests.log) |
| Codex's **57** original/follow-up checks (IDs taken from Codex's `repair-replay.xml`) | 53 still-existing IDs **all pass**. The other 4 are Claude's earlier P33-004 tests, removed because Codex ruled them not identity evidence ([list](codex-repair-replay-replaced.txt)); the whole current `test_prompt33_followup.py` ran with them (8 new P33-004 tests). Unique tests: 61, all passing (pytest reported 77 because 16 IDs were passed twice) — [log](codex-repair-replay.log), [xml](codex-repair-replay.xml) |
| Codex's **223** direct regressions (IDs from Codex's `regression.xml`) | **223 passed** — [log](codex-regression.log), [xml](codex-regression.xml) |
| Codex's **19** focused cross-pillar checks (IDs from Codex's `cross-pillar.xml`) | **19 passed** — [log](codex-cross-pillar.log), [xml](codex-cross-pillar.xml) |
| Full regression (2026-10-20 00:21–00:40 IST) | **3,473 passed / 0 failed / 147 skipped (all BLOCKED)** — [log](full-regression.log), [xml](full-regression.xml) |
| `python -m jarvis.launcher --check` | `ready` — [launcher-check.json](launcher-check.json) |

## Not addressed (still open)

- No real principal verifier exists. Google tokeninfo/userinfo, GitHub `/user`, Slack `auth.test` and Jira `myself` are
  natural read-only candidates, but they need live accounts to implement and verify. Until then a rotated token always
  requires fresh approval.
- Gmail API OAuth tools and Firecrawl reads are outside this repair. Live account scopes, consent and multi-process
  behaviour remain BLOCKED or NOT RUN.
