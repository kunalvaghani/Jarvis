# Failures and production gates

Baseline74 PASS/0 FAIL in132.77s. New reproduction5 FAIL/74 PASS/5 explicit blockers in83.90s: replaying an earlier promotion attempt, absent tested-hash promotion binding, malformed JSON/signature handling and accepting unknown journal stages. The reproduction accidentally collected imported unittest classes too;74 passing assertions are not74 catalog cases. Failure count is assertions, not five independent defects.

First targeted1 FAIL/26 PASS/5 skips: race fixture mutated on Read instead of Write before payload freezing; fixed that fixture trigger. Subsequent29 PASS/5 skips, then final added existing-file edit/test and500-character path assertions: {'PASS': 30, 'FAIL': 0, 'SKIPPED': 5, 'seconds': 13.064}. Broad focused122 PASS/5 blocked skips in128.97s. One sandbox-only rerun10 FAIL/20 PASS/5 skips in3.20s hit Windows atomic replacement access denial; required-permission rerun passed. No product weakening to hide sandbox errors. Full {'PASS': 2827, 'FAIL': 0, 'SKIPPED': 41, 'seconds': 477.819};383 source/test hashes frozen and unchanged.

- **JRV-21-003 BLOCKED:** Overlapping ownership is rejected; automatic same-function conflict resolution is absent.
- **JRV-21-009 BLOCKED:** Bounded path/import context exists, but no verified large-repository semantic symbol retrieval oracle.
- **JRV-21-010 BLOCKED:** Dependency installs are excluded; no approved lockfile/environment rollout contract.
- **JRV-21-019 BLOCKED:** Worktrees and receipts are retained without replay; no durable crash-resume orchestration protocol.
- **JRV-21-032 BLOCKED:** Local activity journals retain code and raw exception strings; complete credential-redacted observability is absent.

Risk: worktrees and command allowlists do not confine malicious test code. LocalGithub utility Git global hooks/config isolation was not proved. Promotion is per-file atomic, not a transaction across all files; on partial failure keep backups/journals and inspect fresh state. Hash binding/cache remove the tested-source reread gap but do not promise safety against a hostile host changing files concurrently. Final actual assembly passes validation hashes; trusted direct promote callers can omit optional expected_hashes for compatibility. Journals cap8MiB/4096 rows/262144 characters per line and fail closed; inspect over-limit or damaged state rather than deleting journals. Streamed line parsing can allocate up to the bounded file limit. Action signatures/receipts are local trusted metadata, not signed human consent. Logs may contain private source and credentials: retain in ignored local runtime, do not publish live logs.

Readiness **ready**: []. Read-only launcher/configuration checks passed with Ollama reachable; no live model coding/GUI/GPU stress or guaranteed response-time acceptance. Existing Python3.10 end-of-life and older global gates remain. No production-ready certificate.
