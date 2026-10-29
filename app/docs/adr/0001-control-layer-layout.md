# ADR 0001: Control-layer layout, branch and document locations

Date: 2026-10-30 · Status: accepted

## Context

The rework prompt names default paths (`jarvis/control/`, `routes/`, `mcp_servers/`, `docs/rework/`, `docs/adr/`, `PROGRESS.md`, `benchmarks/`) relative to "the repo". This repository keeps the application in `app/` (root `AGENTS.md`), with modules in the flat `app/jarvis/` package and documentation in `app/docs/`. The user already created and pushed branch `claude_ControlArchitect` for this work.

## Decision

| Prompt default | Used here |
|---|---|
| branch `rework/control-layer` | existing `claude_ControlArchitect` |
| `docs/architecture/control-architecture.md` | `app/docs/architecture/control-architecture.md` |
| `jarvis/control/` | `app/jarvis/control/` (first sub-package in `jarvis/`; keeps the new layer separate from the flat legacy modules it replaces) |
| `routes/` | `app/jarvis/control/routes/` (executors are part of the control package, not a top-level package) |
| `mcp_servers/` | `app/jarvis/control/mcp_servers/` |
| `docs/rework/`, `docs/adr/` | `app/docs/rework/`, `app/docs/adr/` |
| `PROGRESS.md` | `app/docs/rework/PROGRESS.md`, linked from `app/docs/CLAUDE_HANDOFF.md` |
| `benchmarks/` | `app/benchmarks/` |

New code targets the **existing runtime interpreter, Python 3.10.6** (`app/.venv`). The prompt asks for 3.11+; moving every Jarvis subsystem to a new interpreter is a separate decision for the user (see PROGRESS open questions). The new code avoids 3.11-only syntax and stdlib so either choice works.

## Consequences

Relative links in `app/README.md` and the root `README.md` point into `app/docs/rework/`. Launcher, runtime manifest and recovery rules from `app/AGENTS.md` apply to every new long-running service under `jarvis/control/`.
