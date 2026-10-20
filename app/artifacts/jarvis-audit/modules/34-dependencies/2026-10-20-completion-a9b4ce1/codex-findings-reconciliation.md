# Finding-by-finding reconciliation

| ID | Before | Current evidence | Status / revision |
|---|---|---|---|
| P34-001 | 146ba83 startup missing import admitted pip without consent | Original JRV-34-012 boundary passes unchanged in final run | Default behavior fixed in a9b4ce1; lock/grant boundary hardened by local source.patch |
| P34-002 | 146ba83 low disk/no consent admitted model setup | Original JRV-34-011 boundary passes unchanged | Default behavior fixed in a9b4ce1; approved immutable-download safety still open P34-R1 |
| P34-local authorization defects | a9b4ce1: 13 failures/1 pass in new malicious/concurrent tests | 52 targeted pass, final relevant 227 pass/1 skip | Fixed in uncommitted source.patch, hashes identify exact files |
| P34-R1 | Mutable tag after manifest check | Code review, no live exploit | OPEN: implement immutable bounded transport |
| P34-R2 | Renamed staging venv | Code review only | UNVERIFIED: executable relocation acceptance |
| P34-R3 | Mutable lock/wheelhouse between check and execution | Code review only | UNVERIFIED: immutable snapshot acceptance |

Stable original case catalog was available and joined; revised 001–022 dispositions are in tests.jsonl. No planned row promoted to live acceptance. Exact target, neighbor and cross-system IDs are in executed-results.jsonl. Local repairs have no commit SHA yet: use base + patch + hashes. Earlier author 3,511 suite is separate historical evidence.
