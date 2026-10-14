# Jarvis — local Windows voice assistant

Jarvis combines local voice input, Qwen planning and answers, guarded desktop and
browser actions, native coding, repository skills, reverse-engineer-and-clone of
apps/websites/binaries, a deliberation layer that forms its own evidence-based opinions
and recommends better approaches, an idle-only self-evolution engine that learns new capabilities from
GitHub over time, and configured integrations. The application lives in [`app/`](app/).

The [DeerFlow integration](app/docs/deerflow.md) adds its real embedded research
harness, public skill guidance and source receipt checks while retaining Jarvis's
guarded execution. The full upstream source is downloaded locally; the guide
distinguishes integrated capabilities, live model measurements and remaining limits.

The [sandbox and free-media extension](app/docs/deerflow-sandbox.md) adds confined
offline Docker tasks, read-only input copies and seven local artifact renderers.
Jarvis starts Docker silently when unavailable and monitors it during use, while
preserving shared workloads and refusing uncertain command replay. Account/provider
setup is deferred; this extension needs no paid API keys.
Docker Desktop startup preserves its Windows profile paths and coalesces duplicate
supervisor/watchdog starts, addressing the reported launcher-lock popup without
resetting Docker data or restarting shared containers.

The [optional Groq integration](app/docs/groq-hybrid.md) adds public-question
cloud inference, deterministic privacy routing and shared quota reservations to
the existing worker. It is disabled by default and tested with a local fake
provider using zero real cloud tokens. Local models and guarded PC workflows
remain available; real account/model behavior is explicitly unverified.
Quota exhaustion causes temporary local fallback; eligible requests automatically
reconsider cloud after reset/window recovery, while manual offline mode stays set.
Explicit cloud controls work through typed Ask/Do task, Enter and final voice
commands, saving routing preferences directly without generating a chat answer.
Standalone complex public questions avoid automatic private memory enrichment;
first-request metadata checks finish within a bounded wait before local fallback.
Cloud streaming batches input, bounds policy polling and uses a 90-second default
deadline; partial failures retain their cause and are never automatically replayed.

The [UI finish update](app/docs/ui-smoothness.md) preserves the island design and
animations while removing side seams, blending the outer curves and using cached
rendering with monitor-paced frame deadlines. The guide includes a labelled renderer
preview and off-screen measurements; these do not claim constant on-screen FPS.
The final 2026-10-10 IST UI check measured 99–119 callback fps; **1,459 regression
tests ran successfully with one skip**, and launcher readiness reported **`ready`**.

The [Spotify control repair](app/docs/media-player.md#spotify-control-follow-up-repair-2026-10-10-ist)
fixes pause/resume, next/previous and volume after Windows desktop/COM initialization,
and supports Spotify audio routed to another active output. Live native-session
checks and text-command dispatch passed on 2026-10-10 IST; microphone recognition
was not tested. Final regression ran **1,455 tests successfully with one skip**,
and launcher readiness reported **`ready`**.

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
limitations. Latest feature update (**2026-10-10 IST**): call-style conversation with
a background task queue, natural phrasing and faster step-by-step planning; see
[fast planning, task queue and natural conversation](app/docs/fast-conversation.md). Also on that date: [writing by voice and push-to-write](app/docs/push-to-write.md) and a
[natural male voice with smooth long speech](app/docs/natural-male-voice.md), and
[full YouTube and Spotify control with an island media card](app/docs/media-player.md), and
[WhatsApp automation with previews, approvals and call handling](app/docs/whatsapp.md), and
[long-term memory, API repair and bad-weather alerts](app/docs/memory-apis-alerts.md), and
[learning GitHub repositories for coding with multi-context awareness](app/docs/repo-learning.md), and
[turning learned repositories into new tested Jarvis abilities](app/docs/repo-abilities.md), and
[Pip, who eats files dropped on the island and lets you ask about them, WhatsApp them or email them](app/docs/file-buddy.md), and
[God's Eye View driven by voice with live area alerts](app/docs/gods-eye.md), and
[understanding everyday phrasing across the 800-scenario testbook](app/docs/natural-language.md), and
[a six-module cognitive architecture with a world model, learning and a live Mind view](app/docs/cognitive-architecture.md), and
[screen pre-awareness that offers help for the app in front, opens YouTube videos by a title word and writes what you dictate](app/docs/screen-awareness.md), and
[reverse-engineering a target app, website or binary with REA and building a best-effort functional clone you can then modify](app/docs/rea-reverse-engineer-clone.md), and
[a deliberation engine that forms its own evidence-based opinions, recommends better or safer approaches, decides when to proceed, ask or disagree, and keeps a traceable decision ledger](app/docs/deliberation-engine.md), and
[an idle-only self-evolution engine that detects its own capability gaps, learns relevant GitHub repositories into tested commands, remembers them, resumes crash-safely, and can patch its own source under strict approval gates](app/docs/self-evolution.md). The [previous repository overview](app/docs/repository-overview-history.md)
is preserved with its historical measurements and updated relative links.

## Maintenance and attribution

Read [repository instructions](AGENTS.md) and [application instructions](app/AGENTS.md)
before changes. Update the application README alongside behavior, setup, path,
configuration, integration or verification changes.

Upstream licenses, pinned sources and artwork attribution remain with their
references. See [artwork provenance](app/jarvis/assets/README.md) and the
[integration guides](app/docs/README.md). Reference sources do not imply that an
entire upstream product runs inside Jarvis.
