# Prompt 32 and 33 repairs — P32-001, P32-002, P33-001, P33-002, P33-003 (Claude, 2026-10-19 IST)

Branch `claude`, base `0e3ad47`. Responds to Codex's independent packets
`modules/32-service-recovery/2026-10-19-independent-0e3ad47/` and
`modules/33-mcp-integrations/2026-10-19-independent-0e3ad47/` (in the `codex-review` worktree). No Codex re-review of
these repairs exists yet; Prompts 32 and 33 stay BLOCKED until Codex verifies them. No module 34 work was started.

## Repairs

| ID | Root cause (Codex) | Repair |
| --- | --- | --- |
| **P32-001** (P1) | `OwnedApplication.attach` opened a terminate handle for any PID named in a session-matching heartbeat | `attach` accepts only the launched child or a **live descendant created after it** (psutil tree walk), checked before a handle is opened and again after (an open handle blocks PID reuse). Invalid, dead, sibling and system PIDs are refused with `ValueError`. The supervisor treats a heartbeat whose PID fails this proof as not seen, so it confers nothing. The venv redirector case (real interpreter as grandchild) still works. |
| **P32-002** (P1) | `recovery.record` stored raw `str(message)[:1000]`; launcher and bootstrap passed raw exception text; the UI transcript replayed it | `recovery.safe_message` runs on the **whole** text before truncation (300 chars). It redacts Bearer/Basic credentials (first), key/token/password/secret/cookie assignments, known token formats, URL credentials and query strings, emails, user-profile paths and long hex/base64 runs, and collapses multiline text. `record` always uses it; the launcher records `type(exc).__name__` plus screened text; the transcript screens again on read (old rows). The bootstrap, which must work if the package is damaged, records only a fixed category and the exception type. |
| **P33-001** (P1) | Generated MCP identity (`code_sha256`) dropped from the configuration; execution started the mounted source unverified | `mcp_synthesis.configurations` now carries `generated_identity` (code, spec, schema and image pins). Registration pins `spec_sha256` and `schema_sha256`; a healthy `health()` re-pins. At each call `verified_execution_config` checks code (same text digest as registration), spec, image pin and the live labelled image, then mounts a **private copy of the verified bytes**, so later edits to the registered file cannot run. Drift or a missing pin marks the entry `drifted` (dropped from configuration until health/re-approval) **before approval or launch**. The advertised schema digest is checked again after `tools/list`. The approval card includes the approved identity. |
| **P33-002** (P2) | Arguments not validated against the advertised `inputSchema` | `jarvis/mcp_contract.validate_schema_value`: a bounded JSON-Schema subset (type, properties, required, additionalProperties, items, enum, const, numeric/length/item bounds). Annotation keywords are ignored; any other keyword makes the schema **unsupported**, and the call is refused rather than guessed. Runs before `tools/call`. |
| **P33-003** (P2) | Malformed result envelopes accepted as evidence | `validate_result`: object result, list of typed content blocks with their required fields, boolean `isError`, object `structuredContent`, and the advertised `outputSchema` when present. Failures raise `ContractError` (a `ValueError`), with no retry; the `action_attempted` checkpoint keeps the effect uncertain. |

Files: `jarvis/launcher.py`, `jarvis/recovery.py`, `jarvis_bootstrap.py`, `main.py`, `jarvis/mcp_contract.py` (new),
`jarvis/mcp_bridge.py`, `jarvis/mcp_synthesis.py`; tests `tests/test_prompt32_recovery_boundaries.py`,
`tests/test_prompt33_mcp_boundaries.py` (Codex's, copied), `tests/test_prompt32_33_repairs.py` (Claude's).

## Verification

| Check | Before (Codex at `0e3ad47`) | After |
| --- | --- | --- |
| Codex Prompt 32 boundary tests (repair-log canaries ×3, sibling PID, positive control) | 4 FAIL / 1 PASS | 5 PASS |
| Codex Prompt 33 boundary tests (schema-invalid call, malformed result, dead host, embedded instruction, namespacing, disabled server, ambient secret, generated-source drift on real Docker) | 3 FAIL / 5 PASS | 8 PASS |
| Claude's added tests (real redirector-style grandchild accepted and terminated; invalid/system/dead PIDs refused; late, multiline, URL and `Authorization: Bearer` canaries; bootstrap category only; schema subset; result envelopes; code/spec/image/missing-pin drift disables before approval; private copy unaffected by later edits) | — | 15 PASS (3 consecutive runs) |
| Phase 3 living-skill and MCP synthesis suite plus Prompt 33 tests | — | 42 PASS |
| All MCP/recovery/launcher-related suites (24 files) | — | 543 passed / 13 skipped before the final redaction-order fix; the affected files then re-ran green |
| Full regression (21:37–21:56 IST, Jarvis running) | — | **3,449 passed / 0 failed / 147 skipped (all BLOCKED)** — [log](full-regression.log), [xml](full-regression.xml) |
| `python -m jarvis.launcher --check` | — | `ready` — [launcher-check.json](launcher-check.json) |
| Repair tests recorded together | — | 28 passed — [log](repair-tests.log) |

In the copied Codex test files, only the evidence-output paths were changed from the test file's folder to `tmp_path`
(so the suite never writes into `tests/`). Every assertion is unchanged, as noted at the top of each file.

Two defects were found while writing the repair, by Claude's own tests, and fixed before commit:
(1) `Authorization: Bearer <token>` leaked the token because the key=value rule consumed only the word "Bearer", so
credential schemes are now redacted first; (2) the first integrity check hashed raw bytes while registration hashed
decoded text (CRLF on Windows), so it now uses the registration definition.

## Not addressed (still open)

- Schema version tracking and **dependent-skill revalidation** on drift: a drifted server is removed from the
  configuration, so skills that call it fail closed, but skills are not separately marked or revalidated.
- User-configured (non-generated) servers have no pinned schema; their arguments and results are now validated
  against what they advertise at call time.
- Prompt 32's further items (circuit-breaking budgets, optional-worker registration and health, durable uncertainty
  across paths, state migrations, live startup/audio/restart acceptance), Prompt 33's account, concurrency and memory
  gates, and launcher `repair_required` in Codex's sandbox remain BLOCKED or NOT RUN.
- Redaction is pattern-based; it reduces but cannot guarantee removal of every possible secret format.
