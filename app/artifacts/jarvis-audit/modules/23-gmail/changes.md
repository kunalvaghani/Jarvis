# Retained changes / tradeoffs

- gmail_api.py: explicit False consent refused; argument snapshots bind approval, draft send/delete/update re-observe after approval and Stop is rechecked. Parsed draft info reused once. Bounded parameters parse before OAuth/session creation; malformed marker/search rows fail safely; missing OAuth deps give local guidance.
- gmail_writes.py: bounded64KiB journal read, exact operation/target/boolean-state checks; damaged state categorically refuses execution and preserves data. Existing request identity remains compatible.
- file_drop.py and attachment helper: existing standard approval card before draft; durable per-part identity journal prevents uncertain retry bypass from random MIME boundaries; bounded preflight reads and response cleanup. Selected file/recipient/body behavior retained; no automatic sends.
- New fake-service/security/concurrency/crash tests, explicit accounting, original-preimage benchmark and report/hash scripts. Document fixture now supplies an explicit fake approval. README, Gmail/FileBuddy guide and source-map updated; no dependency/configuration changes or UI redesign.

Same HTML-draft update CPU warm p50/p95 **10.0738/10.3053 → 8.4738/8.5884 ms**, traced peak **141482 → 123313 bytes**;50 calls, byte-identical MIME and result, one fake PUT/sample, zero real mailbox writes. Initial5 calls are not fresh-process cold starts. OAuth/network/browser/RSS/VRAM excluded. Reusing parsed draft info avoids a second decode; the new freshness guard adds one real GET after approval, so remote end-to-end latency may increase.

Keep safety checks and measured CPU/allocation improvement. No private metadata cache, TTL guess, automatic send retry, dependency install or whole-workflow speed claim. [Exact files](files-changed.json), [hash pairs](source-hashes.json), [scoped diff](source.patch).
