# Compatibility — checked 2026-10-16 IST

Official sources inspected with Firecrawl; [exact URLs/dates](upstream-checks.json). [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs) documents local JSON schema use and says Ollama cloud does not currently support this feature. Complete typed responses remain independently validated; schema shape does not prove code correctness. Documentation has no package release date; loopback /api/version returned0.40.0. Official Ollama v0.40.5 release notes display14 Oct19:45 (timezone unstated), while the search excerpt shows an Oct15 signature-verification timestamp. These are recorded separately rather than asserting that signature date as release date. Notes describe larger Nemotron support, cloud and Responses fixes plus llama.cpp/MLX updates; none establishes a local9B/4GB performance win. No runtime upgrade was installed. No live code-generation/model-quality comparison was run.

[Git for Windows](https://git-scm.com/install/windows) reports2.56.0(2), released2026-10-05; installed **git version 2.49.1.windows.1** is older. [Official worktree reference](https://git-scm.com/docs/git-worktree) checked for checkout behavior; worktrees share repository metadata and are not a security sandbox. Existing installed Git executed owned fixture integration; newer Git was not installed/tested. LocalGithub public utility was read in the configured sibling checkout; no claim its live remote services or latest release were validated.

Python3.10.6, pytest8.4.2, Requests2.34.2, psutil7.2.2 retained. Prior [module20 compatibility](../20-self-evolution/compatibility.md) records official pytest9.1.1 release2026-06-19 and Python3.10 end-of-life2026-10-01; no claim those issues were resolved. Existing finite command/tool names and manual legacy adapters retained. Model failure stops the owned native run; it does not switch to cloud or replay partial effects.

- **JRV-21-003 BLOCKED:** Overlapping ownership is rejected; automatic same-function conflict resolution is absent.
- **JRV-21-009 BLOCKED:** Bounded path/import context exists, but no verified large-repository semantic symbol retrieval oracle.
- **JRV-21-010 BLOCKED:** Dependency installs are excluded; no approved lockfile/environment rollout contract.
- **JRV-21-019 BLOCKED:** Worktrees and receipts are retained without replay; no durable crash-resume orchestration protocol.
- **JRV-21-032 BLOCKED:** Local activity journals retain code and raw exception strings; complete credential-redacted observability is absent.

Launcher ready; []. No dependency installation, paid API requirement or model download.
