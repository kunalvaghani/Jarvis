# Stage 6 — Security red-team matrix

Every row is enforced by code that a test attacks. No security test was weakened to pass. "Phase N" tests live in
`app/tests/test_phaseNN_*.py`; "P08" tests in `test_phase08_integration.py`.

| Attack | Defence | Tests (attacks) | Result |
| --- | --- | --- | --- |
| Prompt injection in web pages or tool results asking for writes, sends, deploys or cloud calls | Explicit-intent check for every external-write tool in `Brain.validate_remaining`; tool output is evidence, not instructions | P08 `redteam_injected_or_unrequested_external_writes_are_refused` (deploy, cloud consult, Slack, rollback); existing `test_toolkits.py` planner tests | PASS |
| Skill-file injection (claims of approval, forbidden or unregistered tools, secrets) | `validate_skill` | Phase 3 malicious-candidate cases; P08 skill injection | PASS |
| Malicious generated MCP code | AST screen + network-less, read-only, non-root container + approval | Phase 3 MCP synthesis tests | PASS (Docker present) |
| Cloud privacy leakage | Refuse-don't-redact gate, allowlist, provenance, `screen_payload`; card shows exact payload | Phase 5 nine adversarial cases (0 requests); P08 D8-1 private path refused before any card | PASS |
| Arbitrary filesystem access | Scoped paths; vault read-only; sandboxes mount nothing writable | existing file-scope and coding tests; Phase 4 vault hash; P08 vault write-site check | PASS |
| Unsafe external writes | Adapter writes approve themselves; toolkit writes need explicit intent + approval metadata | Phase 2 adapter approval tests; `test_toolkits.py` | PASS |
| Credential exposure | Secret screens in privacy gate, skill validation, prompt-slot text; minimal env for candidate processes | Phase 5, Phase 3, Phase 6 surface tests | PASS |
| Unauthorized actions | Only `Actions._approve` grants approval; plans/skills/advice cannot carry approval | `APPROVAL_CLAIMS` contract tests, Phase 5 malicious advice, Phase 6 promotion deny | PASS |
| Evaluation tampering | Evaluator sealed to committed blobs; excluded from lab; tree hash before/after | Phase 6 tampering tests (policy, held-out, extra file, planted evaluator); Phase 7 unsealed model gate | PASS |
| Malicious self-mutation | Literal-only surfaces checked twice (worker and gate); protected sources | Phase 6 malicious/non-literal/test-weakening candidates; P08 protected paths | PASS |
| Sandbox escape and resource exhaustion | Container limits; per-program fork with RLIMIT_CPU/AS and wall kill; memory caps on candidate processes | Phase 7 hostile induction programs; Phase 6 resource-exhausting candidate quarantined | PASS |
| Replay of uncertain non-idempotent operations | Execution contracts; DAG restore refuses effectful running steps; trainer/archives never replay | Phase 1 contract tests; P08 flow E crash test | PASS |
| Obsidian data corruption | Staged copies only; manifest/state in `.jarvis-runtime` | Phase 4 real vault hash; P08 static check | PASS |
| Model-generated incorrect training labels | Targets only from the oracle; proposer answers ignored | Phase 7 proposer test; P08 training-label test | PASS |
| Git branch contamination | Lab is a separate repository; canonical repository only read | Phase 6 real-repo snapshot test; P08 flow C (branches unchanged) | PASS |

Not covered by automated attack here: live web pages through a real browser with hostile content (the
Playwright/browser audits cover DOM handling, not adversarial prompt pages against the live planner LLM).
