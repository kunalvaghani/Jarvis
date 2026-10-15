# Jarvis — local Windows voice assistant

<!-- prompt12-audit -->
**Tool-registry audit — 2026-10-15 IST:** All 24 built-in tools now have typed argument
contracts checked before any report or dispatch. Approval claims inside a proposal are
stripped, malformed or deeply nested JSON gives typed errors, concurrent appends to one
file are serialized in-process, and emitted tool reports redact credentials. Tool
evidence is unchanged. Failure events carry a category and results carry a correlation ID.
`requests`/`urllib3` were already current. [Reproductions, changes, benchmarks and
limits](app/artifacts/jarvis-audit/modules/12-tool-registry/inventory.md).
Verification: **2,392 regression PASS / 9 blocked skips** (other modules); Prompt12
**32 PASS** (18 PASS / 13 FAIL on pre-change code), launcher **ready**. Warm p50 latency is
unchanged at about 40 ms. Offline fixtures only; live GUI, accounts and network not exercised.
<!-- /prompt12-audit -->

<!-- prompt11-audit -->
**Skill-selection audit — 2026-10-15 IST:** Bounded guide validation and provenance,
observed procedure reliability and reused description tokens retain existing tool,
policy and approval gates. Census:10 bundled/210 hash-verified Hermes/23 DeerFlow
guides. Utility validation is stale:0 offered; historical activation counts below
are dated results. Arbitrary PDF editing remains blocked.
[Executed assertions, measurements and limits](app/artifacts/jarvis-audit/modules/11-skill-selection/inventory.md).
Verification: **2,355 regression PASS / 9 blocked skips**;
**157 targeted PASS / 1 blocked skip**; Prompt11 **31 PASS / 1 BLOCKED**,
launcher **ready**. These fixtures do not certify live production acceptance.
<!-- /prompt11-audit -->

[DAG/cache audit — 2026-10-15 IST](app/artifacts/jarvis-audit/modules/10-dag-planning/inventory.md)
adds serialized effects, bound read restoration, task-owned checkpoints,
malformed-cache fallback, credential-template screening and content-free errors.
Warm source fingerprints reuse verified digests; cold-cache cost and live
acceptance remain separate from fixture success. Existing mail approvals remain
on the specialized path.
Verification: **2,314 regression PASS / eight existing blocked skips**, **180
targeted PASS / one existing blocked skip**; module10 **32/32 fixture PASS**,
launcher **ready**. Live production acceptance remains open.

[Risk/approval audit — 2026-10-15 IST](app/artifacts/jarvis-audit/modules/09-deliberation/inventory.md)
adds strict consent and model/configuration validation, cancellation of declined
proposals, risky-ambiguity clarification, independent inference deadlines and
redacted Unicode-safe ledger records. Mandatory unfamiliar-program research and
live consent acceptance remain open; measured fixture results are in the report.
Verification: **2,271 regression PASS / eight explicit blocked skips**, **204
targeted PASS / one blocked skip**; module09 **31 PASS / one BLOCKED**, launcher
**ready**. Whole-system production acceptance remains open.

[GPU/resource audit — 2026-10-15 IST](app/artifacts/jarvis-audit/modules/08-gpu-scheduler/inventory.md)
adds bounded lease-state validation, failure cleanup, unchanged-poll write
elimination and conservative optional-learning admission. Sequential cached 9B
cold/warm measurements are separate from the unresolved shared F5/Whisper lease
coordination and whole-system production acceptance.
Verification: **2,213 regression PASS / seven explicit blocked skips**, **219
targeted PASS / four blocked skips**; module08 **30 PASS / two BLOCKED**, launcher
**ready**.

[GPU/resource audit — 2026-10-15 IST](app/artifacts/jarvis-audit/modules/08-gpu-scheduler/inventory.md)
adds bounded lease-state validation, failure cleanup, unchanged-poll write
elimination and conservative optional-learning admission. Sequential cached 9B
cold/warm measurements are separate from the unresolved shared F5/Whisper lease
coordination and whole-system production acceptance.

[Routing/quota/privacy audit — 2026-10-15 IST](app/artifacts/jarvis-audit/modules/07-model-routing/inventory.md)
adds early local refusal, case-insensitive backoff, conservative usage accounting,
shared credential redaction and route/reservation trace IDs. Its matched fixture
measurements and actual cached local fallback are separate from live Groq,
billing and voice acceptance.
Verification: **2,173 regression PASS / five existing blocked skips**, **238
targeted PASS**, **32/32 module07 fixture cases PASS**; launcher **ready**.

[Question/context audit — 2026-10-15 IST](app/artifacts/jarvis-audit/modules/06-questions-context/inventory.md)
repairs private search fallback, selector cancellation, recent-question recall and
question transport isolation. Fixed context budgets reduce oversized selector
payloads; actual default-model samples and full regression evidence are reported
separately from fixture timings. Two-second answers and whole-system production
acceptance remain unproved.
Verification: **2,126 regression PASS / five existing blocked skips**, **206
targeted PASS**, all **32 module06 cases PASS**; launcher readiness **ready**.

[Speech audit — 2026-10-15 IST](app/artifacts/jarvis-audit/modules/05-voice-tts/inventory.md)
repairs pre-submission F5→Kokoro/Piper fallback, Stop races, backend ordering and
long-playback heartbeats. Actual cached CUDA and CPU fallback checks passed with
speaker playback disabled; current measurements, case blockers and regression
results are recorded separately from historical voice tests.
The full regression passed **2,073 tests**, with five explicit blocked skips;
launcher readiness is **ready**. Whole-system production acceptance remains open.

[Prompts 02–04 completion — 2026-10-15 IST](app/artifacts/jarvis-audit/final-report.md)
records 93 catalog cases proved by executed fixtures and three acoustic cases
blocked by missing labeled recordings/GPU headroom. Fixes cover final audio
resampling, duplicate utterance dispatch, bounded microphone shutdown and worker
ownership, stale task identity, and latest-document clarification. Paired CPU
benchmarks and full regression evidence are included; live speech accuracy and
whole-system production readiness remain unverified.

[Intent/reflex follow-up — 2026-10-15 IST](app/artifacts/jarvis-audit/modules/03-intent-direct/inventory.md)
records media paraphrase, corrected tab scope, latest-document routing and compound
punctuation fixes, with fake-transport assertions and paired parser measurements.
The [audit report](app/artifacts/jarvis-audit/final-report.md) records the completed
fixture fault matrix and remaining live acceptance and production release work.

[Perception/cognition follow-up — 2026-10-15 IST](app/artifacts/jarvis-audit/modules/02-perception-cognition/inventory.md)
records stale-window, configuration, text admission and outcome-accounting fixes,
tick diagnostics, paired measurements and task-ID disagreement regression proof.
Hard native sensor-hang containment remains unproved; production
readiness remains uncertified.

[Architecture audit follow-up — 2026-10-15 IST](app/artifacts/jarvis-audit/modules/01-architecture-inventory/inventory.md)
records all 32 architecture cases, bounded startup validation, metadata privacy,
source/health bindings and corrected map claims. [Current audit progress](app/artifacts/jarvis-audit/final-report.md)
keeps live-validation and release blockers separate from passing fixture tests.

[Initial audit pass — 2026-10-14 IST](app/artifacts/jarvis-audit/final-report-before-module01.md)
preserves all 1,184 supplied case IDs and records scoped fixes, a passing
1,851-test full regression, 26 catalog cases passed and 1,158 cases pending.
Whole-system production/security certification remains incomplete.

[Core cognition and routing audit](app/artifacts/cognition_audit_report.md) covers
4 Hz scheduling under slow storage, protected attention, immutable reflex dispatch,
cloud privacy, bulk-task approval and durable external-write non-replay. It includes
the requested async tests and measured before/after timings.

[Integrated knowledge acquisition](app/docs/autonomous-learning.md) connects
scoped local/public research to the existing planner, registry, app memory and
verified procedural skills. Known commands keep their fast paths; optional idle
refresh remains disabled. [Dated validation and limits](app/docs/learning-validation.md)
cover native/browser fixtures, public retrieval, real local planning and regressions.
Complex feature requests can also resolve the current configured app when its
name is omitted; invalid object names are rejected before application inspection.

[Hierarchical execution](app/docs/hierarchical-execution.md) extends the existing
planner and real tool registry with validated dependency graphs, bounded parallel
reads, checkpoints and verified read-plan reuse. Existing specialized workflows
remain available. [Measured benchmarks and production limits](app/docs/hierarchical-benchmarks.md)
distinguish the 2.52× controlled-read speedup from slower model planning.

[Generated natural conversation](app/docs/natural-conversation.md) replaces canned
social replies and startup greetings with brief contextual butler-style replies.
Warm text generation was measured below two seconds on selected synthetic turns;
speech and complex-question latency can be longer.

[F5-TTS speech](app/docs/f5-voice.md) is configured with CUDA and a reference from
the supplied Jarvis video, automatic pacing and incremental audio playback.
Completed conversation/Groq/verified-answer phrases reach speech while text
arrives; each audio chunk plays before the next finishes synthesis. F5's
per-phrase compute time can still delay first audio or cause gaps.
Local synthesis passed. It uses zero-shot conditioning; weights have not been
fine-tuned, and human voice comparison remains unverified.
Speech input cleanup repairs malformed Unicode that could previously stop F5
playback, while preserving the stored answer.

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

For a one-page overview of every feature, skill, tool, model, workflow, piece
of software and repository, and how they connect, see the
[system map](app/docs/system-map.md).

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
