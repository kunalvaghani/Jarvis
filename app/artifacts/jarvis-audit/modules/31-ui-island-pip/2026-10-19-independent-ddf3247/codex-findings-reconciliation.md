# Prompt 31 independent continuation — 2026-10-19 IST

| ID | Current status | Fix / evidence | Remaining |
|---|---|---|---|
| P31-001 | FIXED at original callback boundary | 1dd3e9c841fba8f439be0d1116e9a0c91da8c447; original four + nine repair test executions PASS | does not cover P31-002 |
| P31-002 | APPLIES / new FAIL | two requester replay assertions FAIL on ddf3247fd3d5ee6b151287c6cba358e8707090c6 | no fix SHA; independent review after repair |
| IR-001 | prior narrow fix retained; fresh privacy PASS | tests/test_independent_review.py | real secure-input acceptance |
| IR-002 | prior narrow fix retained; fresh admission PASS | tests/test_independent_review.py | live GPU race/contention |
| IR-003 | prior fix retained, no new dedicated rerun in continuation | earlier packet | broader runtime acceptance |
| IR-004 | UNVERIFIED runtime; source retained | historical deep-path lab evidence | no fresh direct lab-specific reproduction |

Prior artifacts are hashed and unchanged. Prior checkpoint 36fbf3c, fix 32fdbfe and packet bc71fb7 remain historical. Exact new pin ddf3247 includes Claude repair 1dd3e9c. Source code repaired by Codex: none. Full old failure reconciliation remains incomplete. [New ledger](../../../reconciliation/2026-10-19-independent-ddf3247/findings-ledger.csv).
