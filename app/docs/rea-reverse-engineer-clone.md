# REA reverse-engineer-and-clone

Jarvis integrates the external [REA framework](https://github.com/morluto/rea)
("Reverse Engineer Anything", MIT) as an on-demand analysis provider and adds a
four-phase workflow: **ingest → reverse engineer → best-effort clone → iterate**.

REA is not vendored. It is a caller-supplied Node.js program that Jarvis invokes
through its bounded `--json` command-line interface. Every byte REA returns is
treated as untrusted analysis evidence, never as instructions. Reconstruction is
best-effort and must be proven with real tests — Jarvis never claims a byte-exact
or guaranteed 1:1 clone.

Use REA only on software you own or are authorized to examine. See the retained
[license](../integrations/rea-upstream/LICENSE) and
[disclaimer](../integrations/rea-upstream/DISCLAIMER.md), and the reviewed revision
in [source-manifest.json](../integrations/rea-upstream/source-manifest.json).

## Prerequisites

- **Node.js** `^22.19.0 || ^24.11.0 || >=26.0.0` plus npm.
- **REA installed**, exposing its CLI entry. Install with `npm install --global rea-agents`
  (or keep a local checkout/`npx` install) and point `rea.entry` at the absolute
  `scripts/rea.mjs`. The published `dist/mcp/main.js` is the MCP server entry, not a CLI replacement.
- **External engines, per target** — REA installs or licenses none of these:
  - Native binaries: Hopper, Ghidra or IDA.
  - Android APK decompilation: headless JADX and a JDK.
  - Websites: a Chrome-family browser.
  - Static JavaScript/Electron and .NET analysis need no extra engine.

The Jarvis bridge launches REA as an **absolute, non-shim** executable (`node.exe …`);
`.cmd`/`.bat`/`.ps1`/`.sh` wrappers are refused for safety. On Windows, set
`rea.node_path` to your `node.exe` if it is not on `PATH`, and `rea.entry` to the
`.mjs`/`.js` entry (not the `rea.cmd` shim).

## Configuration

`config/config.json` → `rea`:

| Key | Default | Meaning |
| --- | --- | --- |
| `enabled` | `true` | Master switch for the bridge. |
| `node_path` | `null` | Absolute Node executable; when null, the bridge resolves `node` from `PATH`. |
| `entry` | `null` | Absolute path to REA's CLI dispatcher (`scripts/rea.mjs` or a separately reviewed compatible CLI wrapper). Required before any analysis. |
| `allow_commands` | `["analyze-javascript-application"]` | Allowlist of REA subcommands the planner may run. Extend deliberately. |
| `analysis_timeout_seconds` | `600` | Per-analysis deadline (10–3600). |
| `max_input_mb` | `200` | Maximum local target file size accepted at ingest. |

Run `rea_status` (say **“check rea status”**) to see whether the runtime and entry
resolve and which commands are allowlisted. If it reports `ready: false`, Jarvis
says exactly what is missing and does not pretend analysis ran.

## Workflow

Sessions live under `.jarvis-runtime/rea/<session>/` with `session.json`, a
`ledger.md` reconstruction ledger, and an `evidence/` directory of stored REA output.

1. **Ingest** — `rea_ingest` registers one validated target: an absolute local
   directory, an absolute local file within `max_input_mb`, or a public HTTPS URL.
   Private, loopback, reserved and credentialed destinations, and symlinked or
   runtime-internal paths, are refused. Ingest performs no fetch or analysis.
   Natural language: **“reverse engineer the app `D:/apps/example`”**.
2. **Reverse engineer** — `rea_analyze` runs one allowlisted command on the session
   target. It spawns the configured Node/REA program, requires explicit approval of
   the exact program and call, and is never retried on uncertain failure. Output is
   stored as untrusted evidence and appended to the ledger. REA returns pseudocode,
   module graphs, routes, imports and the evidence behind each conclusion — it does
   not emit a finished codebase.
3. **Best-effort clone** — record concrete obligations with `rea_record` (kind
   `obligation`), then reconstruct through the existing [project-coding](../skills/project-coding/SKILL.md)
   workflow (local Qwen coder and LocalGithub worktrees). Save behavioral tests
   first, verify each part, test the combined project, and report what is verified,
   approximate, and unknown.
4. **Iterate** — capture each follow-up change with `rea_record` (kind `modification`)
   and apply it to the cloned source through the same coding workflow, extending
   tests and rerunning the original checks.

Read any session back with `rea_ledger` (session id), or list all sessions with
`rea_ledger .` (say **“list rea sessions”**).

## Tools

| Tool | Approval | Effect |
| --- | --- | --- |
| `rea_status` | none | Report readiness; starts nothing. |
| `rea_ingest` | none | Register a validated target and create the session workspace. |
| `rea_analyze` | user | Run one allowlisted REA command; spawns Node/REA; never retried. |
| `rea_ledger` | none | Read a session ledger and evidence index, or list sessions. |
| `rea_record` | none | Append an obligation, modification instruction or note to the ledger. |

## Limitations

- The clone is a best-effort functional reconstruction verified by tests, not a
  guaranteed 1:1 reproduction. REA evidence can be partial, and some targets require
  engines that may be absent.
- Native, Android and website analyses depend entirely on REA's external engines and
  their own licenses; Jarvis supplies no keys or activations.
- The bridge uses REA's CLI, not its MCP server, to avoid the MCP protocol-version
  coupling and 60-second call cap in Jarvis's generic MCP bridge; long native analyses
  therefore use the configurable `analysis_timeout_seconds` deadline instead.
- Jarvis performs no analysis on ingest and never acts on REA output without approval.

## Verification

- Unit tests: `python -m unittest tests.test_rea_tools`.
- Touched regression suites: `python -m unittest tests.test_toolkits tests.test_capabilities tests.test_tools`.
- Readiness: `python -m jarvis.launcher --offline-check`.

See [Current validation and update history](../README.md#current-validation-and-update-history)
for dated results. As of 2026-10-12, wiring/unit and readiness checks passed, and a live
end-to-end run was verified: REA 6.4.0 (installed via npm on Node v24.14.0) statically analyzed
a sample JavaScript application through the bridge in ~3.8s, returning ~73 KB of valid REA JSON
evidence stored in the session and ledger. Native, Android and website targets still require
REA's own external engines, which were not exercised.

## Prompt 29 audit — 2026-10-16

UUID session IDs remove same-second collisions. Session-scoped exclusive lock files prevent cross-process overlap and retain crash evidence; a process RLock serializes local operations. Append-only, fsync-backed ledger updates preserve notes without rereading/copying the entire ledger. Ledger append is bounded but not a transactional journal: a disk failure can leave a partial untrusted note.

Configuration now rejects malformed objects, empty/invalid allowlists, nonfinite/bool/invalid timeouts and input limits. Configured timeout range stays 10–3600 seconds; max_input_mb is explicitly 1–200. JSON tool input is bounded before parsing. Session checkpoints have typed identity/state/count validation and a 64 KiB limit. Target/session/evidence/ledger/program ancestors reject symlinks and Windows reparse points. UTF-8 surrogate text is rejected before writes.

Analysis rechecks cancellation, paths and program size/mtime after approval. It atomically persists attempt_id/attempted before launching; errors/cancellation set uncertainty, with generic TaskState uncertainty for caught failures. Successful evidence and ledger are saved before marking completed. Attempted/uncertain/crash-lock sessions refuse a new execution. A hard crash before the catch remains protected by the durable attempt and lock. No cache bypasses a fresh approval or reuses stale analysis.

Node stdout uses a temporary file with periodic size checks and a 200,000-byte accepted readback cap; this is not a hard disk quota between checks. JSON must be a nonempty finite object. Nonzero, offline, malformed, oversized, cancellation and worker-disconnect fixtures never claim success. Windows OwnedJob closes only the tested owned process tree. NODE_PATH is no longer inherited; other user-profile paths remain for existing dependencies and do not provide privacy confinement. A separate actual owned Node fixture read back null for fake GROQ_API_KEY, OPENAI_API_KEY, NODE_PATH and NODE_OPTIONS and REA_DISABLE_TELEMETRY=1. This proves environment filtering, not that third-party REA honors the telemetry flag or lacks network/profile access. Outputs explicitly state untrusted and behavior unverified. Tool names and natural-language routing remain stable.

One synthetic 1 MB ledger append: warm p50/p95 15.66780/18.52820 → 7.62825/9.49900 ms; peak temporary Python allocation 13011648 → 12004 bytes.

Full regression/readiness are fixture and dependency checks, not current live REA/clone acceptance. Installed REA 6.4.0 / Node 24.14.0 remain unchanged; official current versions checked are REA 6.5.0 / Node 24.22.0 on the installed major line. The older live 2026-10-12 result above remains historical. [Current evidence and 13 blockers](../artifacts/jarvis-audit/modules/29-reverse-engineering/inventory.md).
