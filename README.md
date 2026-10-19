# Jarvis — local Windows voice assistant

**Independent audit checkpoint — 2026-10-19 IST:** `claude` commit `36fbf3ce925080f7f54afa87eaf1d9b88414142d` was pinned in a separate `codex-review` worktree, an audit-specific exception to the earlier three-branch convention. Four narrow repairs and fresh test evidence are isolated for review; nothing was merged into `claude` or `main`. See the [independent verdict](app/artifacts/jarvis-audit/codex-independent-review/15-final-verdict.md) and [application audit notes](app/README.md#independent-audit-checkpoint-2026-10-19). Full live acceptance remains unfinished.

**Repository consolidation — 2026-10-16 IST:** Development uses exactly three
branches: `main` (integrated code), `codex`, and `claude`. Use `app/` for all source
changes; `InsTAREELS` is an ignored local compatibility junction. Historical
branch work and pending audits were preserved before integration. See the
[consolidation record](app/artifacts/repository-consolidation/report.md) for
merge decisions, fresh checks, recovery instructions, and remaining limitations.

<!-- prompt34-repair -->
**2026-10-20 — Prompt 34 P34-001/P34-002 repaired: missing dependencies and models are reported as `repair_required`, and nothing is installed or downloaded without an explicit, bounded, single-use authorization. Still BLOCKED until Codex re-verifies.** Full regression 3,511 passed / 0 failed. [Repair record](app/artifacts/jarvis-audit/modules/34-dependencies/2026-10-20-claude-repair-146ba83/repair.md).
<!-- /prompt34-repair -->

<!-- prompt33-p33-004 -->
**2026-10-20 — Prompt 33 P33-004 completed: account labels are display-only; a credential change during a pending approval is refused unless independently verified (no verifier registered yet, so it fails closed). Still BLOCKED until Codex re-verifies.** Full regression 3,473 passed / 0 failed. [Repair record](app/artifacts/jarvis-audit/modules/33-mcp-integrations/2026-10-19-claude-repair-cd8861c/repair.md).
<!-- /prompt33-p33-004 -->

<!-- prompt33-followup -->
**2026-10-19 — Prompt 33 follow-up: P33-004 (provider account binding), P33-002 and P33-003 repaired; still BLOCKED until Codex re-verifies.** Full regression 3,469 passed / 0 failed. [Repair record](app/artifacts/jarvis-audit/modules/33-mcp-integrations/2026-10-19-claude-repair-2c4ea56/repair.md).
<!-- /prompt33-followup -->

<!-- prompt32-33 -->
**2026-10-19 — Prompt 32/33 defects P32-001, P32-002, P33-001, P33-002 and P33-003 repaired; still BLOCKED until Codex re-verifies.** Full regression 3,449 passed / 0 failed. [Repair record](app/artifacts/jarvis-audit/modules/33-mcp-integrations/2026-10-19-claude-repair/repair.md).
<!-- /prompt32-33 -->

<!-- prompt31-p31-001 -->
**2026-10-19 — Prompt 31 approval defects P31-001 (unbound callbacks) and P31-002 (receipt replay) repaired; Prompt 31 remains BLOCKED until Codex re-verifies.** Full regression 3,421 passed / 0 failed. [P31-002 record](app/artifacts/jarvis-audit/modules/31-ui-island-pip/2026-10-19-claude-repair-p31-002/repair.md).
<!-- /prompt31-p31-001 -->

<!-- upgrade-phase08 -->
**2026-10-19 — Upgrade Phase 8 of 8 (final integration and verification): PARTIALLY VERIFIED.** Full regression **3,379 passed / 147 skipped (BLOCKED environment dependencies) / 0 failed**; launcher ready. Re-audit repairs: a cloud architect entry point and a pre-existing citation regex bug. Live Groq, GGUF export, VM exploration, Unreal projects and physical-click demonstrations remain BLOCKED. [Architecture](app/docs/upgrade-architecture.md) · [Final Codex handoff](app/artifacts/jarvis-audit/final-codex-handoff/README.md).
<!-- /upgrade-phase08 -->

<!-- upgrade-phase07 -->
**2026-10-19 — Upgrade Phase 7 of 8 (AZR-inspired self-play + local LoRA): pipeline PASS; one checkpoint qualified as experimental only.** Oracle-verified deduction/abduction/induction tasks, sandboxed execution, leak-free versioned datasets, and preemptible, resumable LoRA training on the 4 GB GPU are in place. Held-out accuracy rose from 0/165 to 9/165; the checkpoint is not promoted, and Ollama export is BLOCKED. Full regression **3,361 passed / 147 skipped / 0 failed**. [Application details](app/README.md) · [Phase 7 evidence](app/artifacts/jarvis-audit/phase-07/README.md).
<!-- /upgrade-phase07 -->

<!-- upgrade-phase06 -->
**2026-10-19 — Upgrade Phase 6 of 8 (DGM + autoresearch + EEVEE self-evolution): PASS for locally executable checks.** Bounded, literal-only experiments run in an isolated lab repository and are judged by a sealed ten-domain retention gate. Qualified candidates are approval-gated proposals with rollback; one DAG-ordering proposal qualified and was not deployed. Full regression **3,340 passed / 147 skipped / 0 failed**; launcher ready. [Application details](app/README.md) · [Phase 6 evidence](app/artifacts/jarvis-audit/phase-06/README.md).
<!-- /upgrade-phase06 -->

<!-- upgrade-phase05 -->
**2026-10-18 — Upgrade Phase 5 of 8 (cloud architect escalation + Show Me Once): PASS for locally executable checks; real-provider checks BLOCKED (not authorized).** An optional, off-by-default free-tier cloud consultation sits behind a strict privacy gate and sandbox verification. Consented one-click demonstrations become verified provisional skills. Failure routing is bounded. Full regression **3,315 passed / 147 skipped / 0 failed**; launcher ready. [Application details](app/README.md) · [Phase 5 evidence](app/artifacts/jarvis-audit/phase-05/README.md).
<!-- /upgrade-phase05 -->

<!-- upgrade-phase04 -->
**2026-10-18 — Upgrade Phase 4 of 8 (exploration + ReasoningBank + OpenViking): PASS for locally executable checks.** Verified-outcome lessons for the planner, a read-only hierarchical vault index on a local OpenViking server, and sandbox-only exploration. Full regression **3,277 passed / 147 skipped / 0 failed**; launcher ready. [Application details](app/README.md) · [Phase 4 evidence](app/artifacts/jarvis-audit/phase-04/README.md).
<!-- /upgrade-phase04 -->

<!-- upgrade-phase03 -->
**2026-10-17 — Upgrade Phase 3 of 8 (living skills + MCP synthesis): PASS for locally executable checks.** Stable skill identities and verified-outcome telemetry, gated CAPTURED/FIX/DERIVED evolution, and sandboxed approval-gated MCP tool generation. Full regression **3,257 passed / 147 skipped / 0 failed**. [Application details](app/README.md) · [Phase 3 evidence](app/artifacts/jarvis-audit/phase-03/README.md).
<!-- /upgrade-phase03 -->

<!-- upgrade-phase02 -->
**2026-10-17 — Upgrade Phase 2 of 8 (API/code-first execution): PASS for locally executable checks.** Document, PDF, Blender, Unreal-manifest and VS Code adapters joined the existing tool registry; Jarvis prefers APIs, then structured UI automation, and uses the cyan cursor last (configurable). Full regression **3,223 passed / 147 skipped / 0 failed**; launcher ready. [Application details](app/README.md) · [Phase 2 evidence](app/artifacts/jarvis-audit/phase-02/README.md).
<!-- /upgrade-phase02 -->

<!-- upgrade-phase01 -->
**2026-10-17 — Upgrade Phase 1 of 8 (audit, repair, baseline): PASS for locally executable checks.** Full regression **3,193 passed / 147 skipped / 0 failed** (baseline had 1 load-dependent failure); launcher ready. ToolRegistry input contract, cognition memory-failure visibility and evidence-preserving tests fixed; shared execution-outcome contract added for the next phases. No live account/microphone/desktop acceptance. [Application details](app/README.md) · [Phase 1 evidence](app/artifacts/jarvis-audit/phase-01/README.md).
<!-- /upgrade-phase01 -->

<!-- prompt30-audit -->
**2026-10-16 — Optional planner audit (Prompt 30): partial.** Hermes/Harness proposal and worker boundaries now have stronger configuration, concurrency, cancellation and replay checks; Laya can ask safely when unavailable. Live accuracy/privacy/resource/trace acceptance remains incomplete. [Application details](app/README.md) · [Audit evidence](app/artifacts/jarvis-audit/final-report.md).
<!-- /prompt30-audit -->

<!-- prompt29-audit -->
**2026-10-16 — REA bridge audit (Prompt 29): partial.** Bounded configuration/evidence handling, concurrent session/ledger safety and durable no-replay fences now have regression coverage. Interactive clone fidelity, remote freshness and complete privacy isolation remain blocked. [Application details](app/README.md) · [Audit evidence](app/artifacts/jarvis-audit/final-report.md).
<!-- /prompt29-audit -->

<!-- prompt28-audit -->
**Sandbox/DeerFlow audit — 2026-10-16 IST:** Stronger mount/checkpoint/identity/write/timeout guards and media proof added. **20 catalog fixture PASS / 12 BLOCKED**; full regression **3,065 passed / 124 skipped / 0 failures**, launcher **ready**. Owned offline math, all seven literal media recipes and nonzero/no-replay/cleanup fixtures passed; format proof levels vary. General research/source-quality, approval/quota/privacy/resource/recovery and platform patch acceptance remain incomplete.
[Evidence, limitations and rollback](app/artifacts/jarvis-audit/modules/28-sandbox-deerflow/inventory.md).
<!-- /prompt28-audit -->

<!-- prompt27-audit -->
**God’s Eye audit — 2026-10-16 IST:** Location opt-outs, primary-flight freshness, honest empty-feed answers, safer camera-pack origins, cancellation and durable notification checkpoints added. **20 catalog fixture PASS / 12 BLOCKED**; full regression **3,036 passed / 112 skipped / 0 failures**, launcher **ready**. Closed-view budgets, complete signal freshness/privacy/schema/renderer acceptance remain incomplete. No live globe/camera/feed validation.
[Evidence, limitations and rollback](app/artifacts/jarvis-audit/modules/27-gods-eye/inventory.md).
<!-- /prompt27-audit -->

<!-- prompt26-audit -->
**Realtime/weather audit — 2026-10-16 IST:** Monotonic read cadence, explicit temperature units/source age, timezone/day handling and fail-closed notification checkpoints added. Modelled-hazard suppression is opt-in (default 0); default cadence is preserved. **Prompt 26: 20 fixture PASS / 12 BLOCKED**; full regression **3,005 PASS / 100 skips / 0 failures**, launcher **ready**. 82 registered endpoints constructed with fixtures; no live API, geolocation or alert trial. All-provider freshness/schema/privacy/resource/trace contracts remain incomplete.
[Evidence, limitations and rollback](app/artifacts/jarvis-audit/modules/26-realtime-data/inventory.md).
<!-- /prompt26-audit -->

<!-- prompt25-audit -->
**Media audit — 2026-10-16 IST:** Unrelated/ambiguous selection refuses playback; Spotify song/source/artist checks, Unicode matching and uncertain-playback fallback guards added. **16 Prompt25 fixture PASS/16 BLOCKED**; full regression **2,971 PASS/89 skips/0 failures**, launcher **ready**. No live playback/volume trial. Durable event/tab dedupe, full privacy/resource/recovery contracts and pycaw upgrade validation remain incomplete.
[Evidence, limits and rollback](app/artifacts/jarvis-audit/modules/25-media/inventory.md).
<!-- /prompt25-audit -->

<!-- prompt24-audit -->
**WhatsApp audit — 2026-10-16 IST:** Fresh recipient/draft checks, expiring serialized approval, bounded request parsing and durable text-send non-replay checkpoints added. **14 Prompt24 fixture PASS /18 BLOCKED**; full regression **2,939 PASS /73 skips /0 failures**, launcher **ready**. No live WhatsApp action. Stable contact IDs, groups, outgoing calls, attachments and complete privacy/resource contracts remain incomplete.
[Evidence and rollback](app/artifacts/jarvis-audit/modules/24-whatsapp/inventory.md).
<!-- /prompt24-audit -->

<!-- prompt23-audit -->
**Gmail audit — 2026-10-16 IST:** Approval now refuses False/changed fields, draft writes recheck freshness after approval, and damaged journals fail closed. FileBuddy attachment drafts now require approval and durable non-replay records. **24 Prompt23 fixture PASS /8 BLOCKED**; full regression **2,900 PASS /56 skips /0 failures**, launcher **ready**. No live Gmail trial. Adapter source verification is stale until separately reviewed; account isolation, complete privacy/resource/replay/observability contracts remain incomplete.
[Evidence and rollback](app/artifacts/jarvis-audit/modules/23-gmail/inventory.md).
<!-- /prompt23-audit -->

<!-- prompt22-audit -->
**Web/app audit — 2026-10-16 IST:** Strict preview URL/test-plan validation, service-worker/WebSocket isolation and reused health opener added. **18 Prompt22 fixture PASS /14 BLOCKED**. Full regression **2,855 PASS /48 skips /0 failures**; launcher **ready**. Real authored build and isolated headless browser checks passed; HMR, warning classification, safe restart, host confinement, dependency compatibility, crash continuation and complete redaction remain incomplete.
[Evidence and rollback](app/artifacts/jarvis-audit/modules/22-web-development/inventory.md).
<!-- /prompt22-audit -->

<!-- prompt21-audit -->
**Native coding audit — 2026-10-16 IST:** Promotion now refuses earlier attempts and uses frozen bytes bound to combined test hashes. Damaged or oversized save journals stop safely. **27 Prompt21 fixture PASS /5 BLOCKED**; full regression **2,827 PASS /41 skips**,0 failures. Conflict resolution, semantic retrieval, dependency rollout, crash continuation and credential-redacted journals remain incomplete. Launcher **ready**; live local-model coding acceptance was not run.
[Evidence and rollback](app/artifacts/jarvis-audit/modules/21-native-coding/inventory.md).
<!-- /prompt21-audit -->

<!-- prompt20-audit -->
**Idle evolution audit — 2026-10-16 IST:** Interrupted discovery is recoverable; uncertain learning writes stay in `needs_review`. Daily budgets and a three-attempt cap persist, saver/resource failures defer, and private/negative topics are screened before public discovery. Patches require fresh code/test-bound evaluation and approval; rollback refuses later edits.
Verification: **2,796 full regression PASS /36 skips**; **28 Prompt20 fixture PASS /4 BLOCKED**. Native game preemption, safe automatic write resume, privacy/canary and lockfile rollout remain open. Launcher **repair_required**.
[Evidence, limitations and rollback](app/artifacts/jarvis-audit/modules/20-self-evolution/inventory.md).
<!-- /prompt20-audit -->

<!-- prompt19-audit -->
**Ability-forge audit — 2026-10-16 IST:** Review now binds code/version/scope; network runs require fresh approval and a durable non-replay checkpoint. Wrong-type output withdraws the new version and can restore prior approved metadata without execution. Oversized code is rejected before parsing.
Verification: **2,756 full regression PASS /32 skips**; **32 Prompt19 catalog fixture PASS**. Voice abilities use process guard rails, not Docker isolation. Launcher **repair_required**; live model/account/voice acceptance and supported Python migration remain open.
[Evidence, limits and rollback](app/artifacts/jarvis-audit/modules/19-ability-forge/inventory.md).
<!-- /prompt19-audit -->

<!-- prompt18-audit -->
**Repository-learning audit — 2026-10-16 IST:** Coding references now pin commits, verify cached excerpt hashes, restrict license-sensitive excerpt transfer, bound downloads/browser checks and screen discovery queries for private markers. Pinned duplicate learning reuses memory; corrupt indexes are preserved. Saved-memory relevance warm p50/p95 **1.2128/1.2665 → 0.6546/0.7882 ms**, identical scores/top3 names on 500 repositories with 80 keywords each.
Verification: **2,706 full regression PASS / 32 skips**; **30 Prompt 18 catalog PASS /2 BLOCKED**. Arbitrary repository behavior validation and durable in-flight job recovery remain incomplete. Derived caching adds cold work/memory; launcher **repair_required**.
[Evidence, limits and rollback](app/artifacts/jarvis-audit/modules/18-repo-learning/inventory.md).
<!-- /prompt18-audit -->


<!-- prompt17-audit -->
**Document audit — 2026-10-16 IST:** Bounded extraction/context, multilingual tokenization, stale-source checks, atomic session writes and drop admission guards added. Warm BM25 lookup p50/p95 **0.8772/0.9154 → 0.0550/0.0591 ms** on 1,500 identical chunks; top5 IDs/pages/text identical; scores match to 10 decimal places.
Verification: **2,654 full regression PASS / 40 skips**; **28 Prompt 17 catalog PASS /4 BLOCKED**. Cross-document conflicts, semantic citation faithfulness, hard parser resource isolation and operation traces remain incomplete. Launcher **repair_required**. Installed pypdf 6.20.0 predates the 6.20.1 cyclic-tree security fix; no dependency installation performed.
[Evidence, limitations and rollback](app/artifacts/jarvis-audit/modules/17-rag-documents/inventory.md).
<!-- /prompt17-audit -->


<!-- prompt16-audit -->
**Memory audit — 2026-10-16 IST:** Bounded record/model validation, conservative subject/polarity guards, broader secret screening before clipping and Stop/readback guards added. Canonical facts flush before replacement; failed precommit restores RAM. Equivalent500-fact lexical retrieval warm median 15.40→5.40ms with a small temporary allocation increase.
Verification: **2,616 full regression PASS / 36 skips**; **28 Prompt16 catalog PASS /4 BLOCKED**. Global erase, durable unavailable-vault writes, general document freshness and memory lifecycle correlation remain incomplete. Launcher **repair_required**; real vault/model/Obsidian GUI were not tested.
[Evidence, limits and rollback](app/artifacts/jarvis-audit/modules/16-memory/inventory.md).
<!-- /prompt16-audit -->

<!-- prompt15-audit -->
**App/site knowledge audit — 2026-10-16 IST:** Fresh surface/version and task UUID checks prevent stale context reuse; login observations suppress research/control hints; bounded inputs and numeric public versions fail closed. Source preference uses configured origin, with explicit URL version hints marked stale. Cache lookup warm median 3.52→0.45 ms on synthetic records.
Verification: **2,576 full regression PASS / 32 skips**; **31 Prompt15 catalog PASS / 1 BLOCKED** (plugin identity namespace missing). Launcher **repair_required**. Owned headless browser fixture passed; live accounts/native GUI/model/production readiness remain unverified.
[Evidence, limits and rollback](app/artifacts/jarvis-audit/modules/15-app-research/inventory.md).
<!-- /prompt15-audit -->


<!-- prompt14-audit -->
**Browser/DOM audit — 2026-10-15 IST:** Nine reproduced defects fixed: validate
before opening, preserve controller settings, wait for semantic targets, report
labels/sign-in and reject malformed replies, stale URLs and renamed click targets.
DOM summaries use one browser round trip and omit field values.
[Executed cases, measurements, limits and rollback](app/artifacts/jarvis-audit/modules/14-browser-playwright/inventory.md).
Verification: **2,536 regression PASS / 31 skips**;
**165 targeted PASS / 4 blocked skips**; Prompt14 **30 PASS / 2 BLOCKED**.
Launcher: **repair_required**; [current check](app/artifacts/jarvis-audit/modules/14-browser-playwright/readiness.json).
Verified downloads and explicit tab selection remain missing production adapters.
Headless fixtures do not certify live accounts, arbitrary autosave or production readiness.
<!-- /prompt14-audit -->

[GPU, model, voice and UI Phase 2 — 2026-10-15 IST](app/docs/phase2-gpu-voice-ui.md)
adds bounded contexts, shared CUDA inference leases, shared-memory audio buffers,
safer Push-to-Write and coalesced UI telemetry. [Measured verification and remaining gates](app/artifacts/phase2_gpu_voice_verified.md)
keep live results separate from fixtures; the F5 first-audio target remains unmet.

<!-- prompt13-audit -->
**Desktop-control audit — 2026-10-15 IST:** Eight reproduced defects fixed:
COM/Win32/Python permission denial stops fallback; delayed touch rechecks target/window admission;
DPI context is restored; malformed pointer settings and IPC frames fail closed;
request text is bounded and router errors carry categories/UUIDs.
Provider order stays pointer → UFO → Windows-MCP → CUA → OpenComputerUse → Agent-S.
[Assertions, measured tradeoffs and rollback](app/artifacts/jarvis-audit/modules/13-desktop-control/inventory.md).
Verification: **2,423 regression PASS / 21 blocked skips**;
**191 targeted PASS / 2 blocked skips**; Prompt13 **30 PASS / 2 BLOCKED**,
launcher **repair_required** (Docker/Ollama unavailable; F5 check timed out). Live150% DPI and secure desktop remain unverified; no live
Notepad/Calculator or production desktop success is claimed.
<!-- /prompt13-audit -->

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
Updated **2026-10-15 IST** with a workflow-to-skill/tool/model connection table,
configuration status and links to inventory sources. This is documentation review;
it adds no live feature or readiness results.

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
