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
  `scripts/rea.mjs` (published packages also ship `dist/mcp/main.js`).
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
| `entry` | `null` | Absolute path to REA's CLI entry (`scripts/rea.mjs` or a published dist entry). Required before any analysis. |
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
