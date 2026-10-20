# Exact proposed changes for Claude

source-only.patch is the retained uncommitted P34–P37 production diff against the pinned SHA; it is not already integrated into claude. V2 needed no further production repair. New V2 changes update two legacy telemetry schema assertions to recognize bounded clock fields and verify their types, plus reproducible audit harness configuration/cwd fixes. No privilege, privacy, retry or executor behavior relaxed.

test-change.patch includes tracked test edits plus new independently added test files. patch-manifest.json hashes every proposed source/test path. Read earlier per-prompt findings and the cumulative handoff before selectively applying; preserve original user configuration. New tests are not included by ordinary git diff until added, so the generated patch includes them explicitly. Candidate commit remains null. After Claude integrates accepted changes, provide the resulting committed SHA and rerun this review; no auto-merge/deployment.
