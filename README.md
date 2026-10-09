# Jarvis — local Windows voice assistant

Jarvis combines local voice input, Qwen planning and answers, guarded desktop and
browser actions, native coding, repository skills and configured integrations.
The application lives in [`app/`](app/).

## Start and stop

Use [Start Jarvis.cmd](<app/Start Jarvis.cmd>) for supervised hidden startup and
[Stop Jarvis.cmd](<app/Stop Jarvis.cmd>) for deliberate shutdown. Setup and
maintenance shortcuts are grouped in [`app/launchers/`](app/launchers/).

Follow the [application guide](app/README.md#start) for requirements, setup,
configuration and usage. Settings are in `app/config/config.json`; dependencies
are grouped under `app/requirements/`, with `app/requirements.txt` as the main
installation entry point.

## Project navigation

| Location | Purpose |
| --- | --- |
| [app/jarvis](app/jarvis/) | Application package, assets, bundled data and templates. |
| [app/scripts](app/scripts/) | Maintenance commands grouped by purpose; use `python -m scripts.<group>.<command>`. |
| [app/tests](app/tests/) | Regression tests and controlled fixtures. |
| [app/docs](app/docs/README.md) | Documentation index, architecture, integration guides and historical evidence. |
| [app/examples](app/examples/) | Maintained examples. |
| [app/integrations](app/integrations/) | Active adapters and upstream checkouts, grouped profiles and attributed references. |
| [app/artifacts](app/artifacts/) | Preserved reports, media, training runs, generated projects, research, fixtures and logs. |
| [app/skills](app/skills/) | Bundled skill guidance. |

Local environments, models, credentials, runtime state and user workspaces remain
ignored. On this installation, an ignored `InsTAREELS` junction points to `app`
so existing local absolute paths continue working. New checkouts use `app`.

## Verification and history

The [project-structure guide](app/docs/project-structure.md#verification-record)
records the **2026-10-09–10 IST** reorganization and fresh checks: **1,315 regression
tests ran successfully with one skip**, launcher readiness is `ready`, and all seven existing
Python environments resolve correctly. Jarvis remains
deliberately stopped; Ollama was briefly restarted with approval and retained all
14 available models. Relocation checks do not claim new live email, microphone,
desktop or model-training validation.

The [application guide](app/README.md) retains dated feature verification and
limitations. The [previous repository overview](app/docs/repository-overview-history.md)
is preserved with its historical measurements and updated relative links.

## Maintenance and attribution

Read [repository instructions](AGENTS.md) and [application instructions](app/AGENTS.md)
before changes. Update the application README alongside behavior, setup, path,
configuration, integration or verification changes.

Upstream licenses, pinned sources and artwork attribution remain with their
references. See [artwork provenance](app/jarvis/assets/README.md) and the
[integration guides](app/docs/README.md). Reference sources do not imply that an
entire upstream product runs inside Jarvis.
