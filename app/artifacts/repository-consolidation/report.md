# Jarvis repository consolidation

Date: 2026-10-16 IST. Repository: `kunalvaghani/Jarvis`.

## Preserved inputs and merge decisions

The initial branch heads were:

| Branch | Commit | Disposition |
| --- | --- | --- |
| main | 1efc854c24e994bcc8bd4fe61bc31300496ee15f | Main history retained through merge ancestry |
| audit/12-tool-registry | 9bf5528e6d490fc3bbe92d0c62bcffae6c0946b6 | Pending audit work committed as f624d20 |
| audit/phase2-gpu-voice-ui | b41f14948d9fd1e89378bca0e400492202c1b064 | Integrated in d626c55 |
| codex/hierarchical-dag-upgrade | 8155e2e03918e56b86fc621a9c6e88eb9b10abe5 | Already included in original main |
| codex/jarvis-prove-fix-audit | bf549f2b25dae297b3d334b0390fe165603303e8 | Already included in original main |

Main was merged into the preserved audit branch as 97090ec before integrating
the voice branch. No history was rebased or force-pushed. The separate worktree
was clean apart from ignored runtime files and logs.

Two conflicts were reconciled explicitly. The newer dictation key state update
is retained before injection, so a failed injection still observes Alt release.
Speech retains explicit worker `safe_to_retry` confirmation and per-request
audio progress checks. The older branch's speculative retry after an EOF or
unconfirmed failure was excluded because missing audio acknowledgement does
not prove silence. The branch's speech formatting, numeral normalization,
ability-forge inference memory fallback, and historical probe artifacts were
retained. Source history remains recoverable in the merge parents and bundle.

Git previously tracked 1,844 paths under `InsTAREELS/`, although it is now a
Windows junction to `app/`. Every such tracked path had an `app/` counterpart.
Duplicate index entries were removed without deleting junction contents.
New clones use the canonical `app/` tree, consistent with existing setup docs.

## Fresh verification

- Focused voice/dictation/ability suite: **173 passed, 2 skipped**, 33.73 seconds.
  [JUnit evidence](targeted.xml), [console output](../repository-consolidation-targeted.txt).
- Complete regression: **3,174 passed, 147 skipped, zero failures**, 561.51 seconds.
  [JUnit evidence](full-regression.xml), [console output](full-regression.txt).
  One existing pywinauto STA COM threading warning was reported. The skips
  retain their individual reasons in JUnit; they are not live-validation passes.
- All 410 captured runtime/test Python files remained unchanged during the run:
  [source hashes](source-hashes.json).
- Launcher readiness: **ready**. [Readiness output](launcher-check.json) checks
  dependencies and configured services; optional Groq inference was not live checked.
- All five original branch heads are ancestors of integrated revision d626c55:
  [executed ancestry assertions](merge-ancestry.json).
- Git connectivity validation exited successfully; existing dangling blobs were
  retained. A token-format scan of 457 preserved changed paths found only two
  repeated-character synthetic tokens from privacy regression test names.
- Final local/remote branch and worktree verification: pending at report preparation.

These checks establish integration regression behavior. They do not certify
blocked live integrations, model quality, or the full audit catalog. The
[prior audit report](../jarvis-audit/final-report.md) retains its unresolved
cases and original measurements. Historical hash receipts refer to their
original source revisions; this integration changes some of those files.

## Recovery and cleanup

Before modification, all refs were saved in a verified Git bundle and dirty
files were saved in SHA-256-verified ZIP archives. The secondary archive also
contains all 93 ignored runtime/log/cache files (1,912,253 uncompressed bytes).
The primary archive contains 457 changed/untracked files, including the
compatibility-path views of canonical files. Runtime state and secrets remain
local and are excluded from commits.

Local recovery directory, relative to the repository:
`app/.jarvis-runtime/repository-consolidation/20261016-230549/`.
It contains `all-refs.bundle`, `manifest.json`, `primary-files.zip`,
`secondary-files.zip`, staged/working binary patches and raw status inventories.
The original branch names and commit hashes are in the manifest. Use
`git bundle verify` before restoring. Restore into a separate directory, then
inspect the archive paths and patches before applying them. Do not extract the
legacy `InsTAREELS` paths over the active junction.

The intended final topology is one primary checkout on `main` and exactly
`main`, `codex`, and `claude` locally and on origin, initially at the same tested
commit. Obsolete branch deletion follows ancestor checks and successful push;
worktree removal follows archive verification. The original commits stay
reachable from main's merge ancestry and the local recovery bundle.
