# Prompt 32 independent audit — 2026-10-19 IST

Native ownership before/after is in owned-process-trace.json: two same-name python.exe trees with distinct roles/creation times; matching-session sibling PID accepted; both application and sibling not alive after application stop; test-owned cleanup complete. This is the final targeted replay trace; initial boundary XML/log remains separately retained.

Log privacy before: synthetic API-key/Bearer content passed through recovery.record and the real launcher exception branch. After: parsed repairs.jsonl still contains the canary. Expected omission assertions fail. No real user content.

Exact authored fixture file outputs are preserved in [API-key sample](synthetic-api-key-repairs.jsonl), [Bearer sample](synthetic-bearer-repairs.jsonl), and [launcher exception sample](synthetic-launcher-repairs.jsonl). These three output-export reruns are duplicates of the original privacy assertions, not new root causes. repair-output-readback.xml/txt records that export/check step.

No-replay journey: fake Gmail provider accepts one POST then raises timeout. Durable Gmail journal/TaskState retains uncertainty; another invocation raises instead of posting again. WhatsApp fake transport timeouts and DAG running-write restore likewise refuse replay. See precise test IDs and assertions in final-targeted.xml/txt. These are synthetic providers with actual local state, not real account sends.
