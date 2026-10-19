# Findings at cd8861ce720ade303485ee2023430dd8c6b4f0ba

| Finding | Independent status | Evidence |
|---|---|---|
| P33-001 P1 | FIXED for reported integrity defect | Original Docker repro and identity/private-copy controls PASS |
| P33-002 P2 | FIXED for reported scalar/tail/equality defects | Original and new-edge repros PASS; whole-value budget controls PASS |
| P33-003 P2 | FIXED for reported envelope/resource/tail defects | Original and edge repros PASS; supported block controls PASS |
| P33-004 P1 | PARTIAL/OPEN | Original unlabelled switch PASS; unchanged-label/other-account-token FAIL |
| P32-001/002 P1 | Retained FIXED for original defects | Native sibling/descendant and synthetic privacy repros PASS |

Repair SHA for passing defects `cd8861ce720ade303485ee2023430dd8c6b4f0ba` (P33-001/P32 earlier repair 2c4ea56 retained); no remaining P33-004 fix SHA. Four audit fixture files byte-identical. Exact test/class/run IDs in executed-results.jsonl, affected regression.xml and cross-pillar.xml. Author full-suite results are not independent totals. Prior immutable packets and source hashes retained. Broader mandatory acceptance gates remain BLOCKED.
