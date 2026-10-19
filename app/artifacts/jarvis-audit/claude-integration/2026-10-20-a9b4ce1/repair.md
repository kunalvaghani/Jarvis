# Claude integration of Codex P34–P37 repairs, and P34-R1/R2/R3 repairs (2026-10-20 IST)

Branch `claude`. This responds to the cumulative handoff in [CLAUDE_HANDOFF.md](../../../../docs/CLAUDE_HANDOFF.md) (P99-R1). No Codex re-verification of either commit exists yet. Release remains **NOT READY**. Nothing was merged, pushed, deployed, installed or downloaded, and no live account, device or model was used.

## 1. Integration — commit `3fbfbf68b6e5cd964191db2c3245efbc2f5a3772`

I reviewed Codex's uncommitted codex-review diff against `a9b4ce1` file by file and accepted all of it. I checked these points:

- `TaskState.running_identity` exists.
- `win32process` is imported in `demonstration.py`.
- The `CloudArchitect` constructor has no network side effects.
- The redaction pattern does not match inside identifiers.
- Lifetime checks accept Jarvis's own one-hour grants.

The diff was applied with `git apply` (`config/config.json` excluded, so the user's configuration is preserved). Codex's 5 new test files, `docs/CLAUDE_HANDOFF.md` and its 16 evidence packets were copied **byte-identically** (`diff -rq` clean); none of them existed on `claude` before. A scan of the packets found only synthetic credential fixtures (`AKIAAAAA…`, `ghp_aaaa…`, `xoxb-…FAKE`). Targeted check: Codex's new P34–P37 tests plus the affected suites, **317 passed / 1 skipped** (native symlink privilege, BLOCKED).

## 2. P34-R1/R2/R3 repairs — the commit after `3fbfbf6`

| ID | Repair | Tests (mocked transport and filesystem fixtures) |
| --- | --- | --- |
| P34-R1 approved download race | `scripts/setup/setup_brain.approved_pull` fetches the manifest **by approved digest** (re-hashed). It fetches layers by digest with per-layer and total byte caps, Range resume, and a hash check before an atomic publish. The tag manifest is written only after every layer verifies, and an existing manifest is never overwritten. There is no Ollama `/api/pull` of the mutable tag. Ollama must then list the approved digest. Partial layers are kept; no retry. | Digest-only URLs and zero `/api/pull`; refusals for over budget, oversized layer, tampered layer, existing manifest, unlisted digest and invalid revision, with partials kept and nothing published; Range resume |
| P34-R2 venv relocation | No relocation. The old environment moves to `<env>.previous-<id>`, the new one is built at its final path, and pip install, the import check and `pip --version` run in place. Any failure moves the attempt to `<env>.failed-<id>` and restores the previous environment. | Built at the final path; rollback after a pip install, import or `pip --version` failure (3 cases) |
| P34-R3 lock snapshot | The lock is copied to `.jarvis-runtime/repair-staging/<id>/requirements.lock` and re-hashed against the approval before the build. pip reads only that copy; wheels are bound by `--require-hashes`. | Lock replaced after validation: refused, zero builds. Lock replaced during the build: pip reads the approved copy |

P34 tests: `test_prompt34_dependency_repair.py` plus Codex's `test_prompt34_completion.py` and `test_prompt34_remaining_routes.py`, **66 passed**. Codex's P34 boundary packets (`independent-146ba83`, `completion-a9b4ce1`), unchanged: **4 + 4 passed** (run separately because both files share a basename). Model recovery, Ollama, model selection, launcher readiness and recovery suites with the 146ba83 packet: **38 passed**.

## 3. Final full regression (both commits' source)

| Check | Result |
| --- | --- |
| Full regression (2026-10-20 03:45–04:03 IST) | **3,601 passed / 0 failed / 148 skipped (all BLOCKED)** — [log](full-regression.log), [xml](full-regression.xml) |
| `python -m jarvis.launcher --check` | `ready` — [launcher-check.json](launcher-check.json) |

## Still open

- **P34-R1:** the live registry/CDN transport and whether the running Ollama server, especially one in WSL, reads the written manifest are NOT RUN. A mismatch fails closed.
- **P34-R2:** a real console-script check needs an authorized hash-locked rebuild, which is NOT RUN. P34-R4 POSIX/WSL is NOT RUN.
- Every P35–P37 and P99-R2..R6 item, and every live acceptance gate in the handoff, remains as listed there.
