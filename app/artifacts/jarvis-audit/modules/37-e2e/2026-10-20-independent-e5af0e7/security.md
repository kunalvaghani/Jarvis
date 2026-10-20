# Security / side effects

Real child os._exit is confined to an owned fixture process. The only delivery side effect is one JSONL row in a temporary mock outbox. UI widgets are owned, hidden, and read programmatically. Speech is a Mock sink; mic, account send, network provider and desktop capture are inactive. A planner callback after restart raises immediately, so the test cannot silently infer or replay.

New dependency repair cases intercept commands/requests. The fresh full suite uses fake transports and owned files/Git/loopback/utility app fixtures; unsupported cases are explicit skips or exclusions. No package/model install, private recording or global setting changes. Local roots normalized in raw output with before/saved hashes.
