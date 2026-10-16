# Prompt21 audit — 2026-10-16 IST

**27 catalog PASS /5 BLOCKED /0 FAIL /0 SKIPPED /0 NOT RUN.** [All32 exact IDs/assertions](tests.jsonl). Baseline {'PASS': 74, 'FAIL': 0, 'SKIPPED': 0, 'seconds': 132.764}; final dedicated {'PASS': 30, 'FAIL': 0, 'SKIPPED': 5, 'seconds': 13.064}; full {'PASS': 2827, 'FAIL': 0, 'SKIPPED': 41, 'seconds': 477.819}. [Commands/results](commands.txt), [full XML](full-regression.xml), [skip reasons](full-regression-skip-reasons.json).

Tests use owned temporary projects, actual local Git worktrees/merges and Python unit checks, scripted model proposals, fake loopback HTTP and injected failures. Five independent file sessions execute twenty rounds each; no concurrent GPU models. The existing two-worker assembly test exercises the shared workload engine with a fake executor; native single-worker integration also runs in baseline/full regression. This does not prove two live model workers or model-generated code quality. No account sends, personal deletes, OS changes, dependency installs, learned scripts, model downloads, real project promotion or deployment were run.

| Documented claim | Implementation / caller | Executed evidence / limit |
| --- | --- | --- |
| Native coding | native_coding.run/infer, coding_backend selection | Typed proposal/schema checks, test-first repair bounded to three rounds, malformed/timeout/disconnect stop; selected local Qwen3.5:9b only; no automatic backend replay |
| File isolation | coding_files.FileSession, claude_code_guard, codex_files.execute | Independent session state, assigned paths, read freshness, immutable tests, exact patches and prevalidation; trusted local fixture execution, not an OS sandbox |
| Uncertain writes | FileSession.uncertain and file-events.jsonl | Unmatched attempted save stops; malformed/oversized journals fail closed; rejected syntax records remain legitimate |
| Assembly | codex_workload.run/workload_contract | At most two workers, exact nonoverlapping ownership, dependency order and combined checks; same-function conflict resolution absent |
| LocalGithub | localgithub public loader; sibling src/local_github/gitops.py | Actual installed public utility creates owned Git worktrees; missing-path error; no private LocalGithub configuration or remote sends |
| Promotion | codex_workload.promote, combined validation hashes | Refuses any prior promotion journal; freezes bounded payloads, binds actual run to tested hashes, checks fresh destination, backs up/readbacks; partial multi-file failure requires review |
| Commands | coding_programs.checked_argv, owned WindowsProcess | Shell delete/inline script/install refused, missing executable explicit, timeout/cancel retains partial state; trusted project tests still execute with host user permissions |
| Privacy | native_coding.infer→knowledge_worker local transport | Fake private payload with Groq enabled makes only loopback /api/show and /api/chat requests, proxy environment disabled; no universal semantic privacy oracle |
| Context / performance | project_files, planner context budget, streamed journal | Bounded file/path context, not semantic retrieval; benchmark covers journal inspection only, not TTFT/build/GPU latency |
| Recovery / diagnostics | owned request/receipt/activity and promotion journal | Correlatable owned run state retained; no automatic uncertain replay; no complete crash continuation/redaction contract |

- **JRV-21-003 BLOCKED:** Overlapping ownership is rejected; automatic same-function conflict resolution is absent.
- **JRV-21-009 BLOCKED:** Bounded path/import context exists, but no verified large-repository semantic symbol retrieval oracle.
- **JRV-21-010 BLOCKED:** Dependency installs are excluded; no approved lockfile/environment rollout contract.
- **JRV-21-019 BLOCKED:** Worktrees and receipts are retained without replay; no durable crash-resume orchestration protocol.
- **JRV-21-032 BLOCKED:** Local activity journals retain code and raw exception strings; complete credential-redacted observability is absent.

Read the Prompt21 contract, app maintenance instructions, system-map and native-coding guide; architecture/model claims were checked against actual callers/configuration. Run order: contract/source trace→baseline→reproduction→narrow fixes→upstream compatibility→equivalent benchmark→focused/full regression→readiness→ledger/docs. Kept inherited dirty branch **audit/12-tool-registry**, HEAD **9bf5528e6d490fc3bbe92d0c62bcffae6c0946b6** to preserve user/module14–20 work; a fresh checkout would omit it. No audit commit/reset. Initial inspection observed e1a33a0; before the accepted full run the checkout advanced to9bf5528 (added fixes till20), preserved without reset. Frozen source hashes bind the accepted run, not an assumed clean checkout. [Environment](environment.json), [changes](changes.md), [compatibility](compatibility.md), [rollback](rollback.md).

Journal inspection warm p50/p95 **6.5127/6.6623 → 6.0438/6.1355 ms**, peak traced allocation **677034 → 143314 bytes**. Same1,000 paired journal rows,25 samples/version (five initial calls,20 warm); same imported process/cache. Complete and uncertain outcomes match. Cold label means first calls, not fresh-process cold start. No inference/audio/GPU/end-to-end latency claim. [Raw samples](benchmarks.csv), [scope](benchmark-summary.json).
