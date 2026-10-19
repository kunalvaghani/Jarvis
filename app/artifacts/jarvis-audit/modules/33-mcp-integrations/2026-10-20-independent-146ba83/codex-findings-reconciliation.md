# Finding reconciliation at 146ba831e7ae5df1a953b0f910288c41c9ab4689

| Finding | Fix SHA | Fresh evidence | Status |
|---|---|---|---|
| P33-001 P1 source integrity | 2c4ea56 | Original real Docker drift rejection, code/spec/image/private-copy controls | FIXED |
| P33-002 P2 input schema/tail/equality | cd8861c | Original invalid argument + full array tail/enum/const/budget controls | FIXED |
| P33-003 P2 malformed output/resource | cd8861c | Original envelope + output tail/resource/content controls | FIXED |
| P33-004 P1 account-context drift | 146ba83 | Unlabelled, changed-label and stale-label B-token reproductions refuse; unchanged token succeeds; explicit mock verifier principal/workspace/scope checks | FIXED |
| P32-001 P1 ownership | 2c4ea56 | Native sibling preserved/descendant terminated controls | Retained FIXED |
| P32-002 P1 repair privacy | 2c4ea56 | Synthetic original/late/multiline/bootstrap canaries | Retained FIXED |

Exact complete source SHAs are in baseline/source-hash artifacts and reconciliation review-revisions.json. Current replay is 63 PASS, not a claim that every old author test survived unchanged. Five original independent fixtures are byte-identical. Four old author P33-004 tests that assumed labels proved identity were retired and replaced by explicit mock-verifier and fail-closed assertions, as documented in the reviewed diff/author report. No failing original Codex assertion was removed.

Neighbor retention: 223 direct regression checks; 19 focused cross-pillar; 4 new optional-route cases. Exact IDs/class/run/evidence in executed-results.jsonl. Upstream 3473/147 is author evidence only. Further full-module gates remain BLOCKED; no blanket release certification.
