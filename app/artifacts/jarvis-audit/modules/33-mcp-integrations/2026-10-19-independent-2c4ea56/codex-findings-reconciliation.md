# Exact finding reconciliation

Base `0e3ad4706b5120e5d0479d34333e5faa7b0931b5` → repair `2c4ea56eb7967929e49dad07b0612cb99caaf56e`. Original fixture files copied byte-for-byte into this directory so evidence never overwrites prior originals.

| Finding | Independent result | Remaining work |
|---|---|---|
| P33-001 P1 | FIXED: original drift repro PASS, code/spec/image/missing-pin rejection and private-copy controls PASS | Full schema-dependent skill lineage and concurrency not certified |
| P33-002 P2 | PARTIAL: original integer-string repro PASS | Array tails and JSON boolean/numeric enum/const FAIL |
| P33-003 P2 | PARTIAL: original malformed envelope repro PASS | Embedded resource contents and output array tail FAIL |
| P33-004 P1 | APPLIES/OPEN: new two-account switching fixture FAIL | No fix SHA |
| P32-001 P1 | FIXED for native sibling repro, normal stop and real-descendant controls PASS | Full live service acceptance remains open |
| P32-002 P1 | FIXED for original canaries/startup branch plus late/multiline/bootstrap controls PASS | Pattern redaction is not universal privacy proof |

Exact tests: executed-results.jsonl, repair-replay.xml, contract-edges.xml, provider-context.xml. Related retention: regression.xml and cross-pillar.xml. No author result copied into independent totals. Prior packet remains historical; no blanket full reconciliation completion.
