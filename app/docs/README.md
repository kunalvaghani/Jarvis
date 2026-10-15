# Jarvis documentation

- [GPU/model/voice/UI Phase 2, configuration, current rendered preview and verification limits — 2026-10-15 IST](phase2-gpu-voice-ui.md)

Start with the [application guide](../README.md) and [project structure](project-structure.md).
For a one-page overview of features, skills, tools, models, workflows, software
and repositories and how they connect, see the [system map](system-map.md).

## Project and runtime

- [F5/Kokoro/Piper audit, live synthesis checks, fallback and acoustic/resource limits — 2026-10-15 IST](../artifacts/jarvis-audit/modules/05-voice-tts/inventory.md)

- [Prompts 02–04 completion, full regression, benchmarks and acoustic blockers — 2026-10-15 IST](../artifacts/jarvis-audit/final-report.md)
- [Wake/STT lifecycle, cleanup, source bindings and live-validation gaps](../artifacts/jarvis-audit/modules/04-voice-stt/inventory.md)

- [Intent/reflex follow-up, scoped fixes and remaining cases — 2026-10-15 IST](../artifacts/jarvis-audit/modules/03-intent-direct/inventory.md)

- [Perception/cognition fixes, fixture results, benchmarks and remaining cases — 2026-10-15 IST](../artifacts/jarvis-audit/modules/02-perception-cognition/inventory.md)

- [Architecture inventory follow-up, 32 case proofs, typed contracts and open gaps — 2026-10-15 IST](../artifacts/jarvis-audit/modules/01-architecture-inventory/inventory.md)

- [Whole-system audit evidence, catalog progress, open risks and continuation — 2026-10-15 IST](../artifacts/jarvis-audit/final-report.md)

- [Core architecture and cognitive audit, tests and benchmarks — 2026-10-14 IST](../artifacts/cognition_audit_report.md)

- [Integrated autonomous learning, compatibility and rollback — 2026-10-14 IST](autonomous-learning.md)
- [Learning release tests, native/browser/model checks and benchmarks — 2026-10-14 IST](learning-validation.md)

- [Hierarchical DAG execution, compatibility and rollback — 2026-10-14 IST](hierarchical-execution.md)
- [Pre/post upgrade benchmarks and production acceptance limits — 2026-10-14 IST](hierarchical-benchmarks.md)

- [Optional Groq hybrid inference, quota protection and offline verification — 2026-10-14 IST](groq-hybrid.md)
- [Pre-implementation hybrid architecture map — 2026-10-14 IST](groq-architecture.md)

- [DeerFlow Docker sandbox, free media and live verification — 2026-10-14 IST](deerflow-sandbox.md)

- [DeerFlow integration, local harness and measured source research — 2026-10-13–14 IST](deerflow.md)

- [Fast planning, task queue and natural conversation — 2026-10-10 IST](fast-conversation.md)
- [Writing by voice and push-to-write — 2026-10-10 IST](push-to-write.md)
- [Natural male voice and smooth long speech — 2026-10-10 IST](natural-male-voice.md)
- [Crash recovery](CRASH_RECOVERY.md)
- [GPU allocation by inference phase](gpu-priority.md)
- [Free natural speech and configured-model recovery](natural-voice-and-model-repair.md)
- [Ollama output and Jarvis timeouts](ollama-output-timeouts.md)
- [Project structure and relocation](project-structure.md)
- [Qwen3.5:9b primary model and native tools](qwen35-9b.md)
- [Runtime tools, skills and program memory](runtime-capabilities.md)
- [Session memory and background context selection](session-context.md)

## Voice and interface

- [Generated butler-style conversation and measured latency — 2026-10-14 IST](natural-conversation.md)

- [F5-TTS reference voice, CUDA setup and measured limits — 2026-10-14 IST](f5-voice.md)

- [UI edge finish and animation pacing — 2026-10-10 IST](ui-smoothness.md)
- [Jarvis Dynamic Island](dynamic-island.md)
- [Sharp display, live progress and commands during speech](hd-display-and-voice-input.md)
- [Historical Jarvis HUD](hud-interface.md)
- [Jarvis's own cursor and physical clicks](independent-cursor.md)
- [Interactive Jarvis island](interactive-island.md)
- [Screen pre-awareness: offers for the app in front, YouTube by title word, hands-free writing (2026-10-11)](screen-awareness.md)
- [Cognitive architecture: perceive, remember, reason, decide, act, learn (2026-10-11)](cognitive-architecture.md)
- [Understanding everyday phrasing: the 800-scenario testbook (2026-10-11)](natural-language.md)
- [God's Eye View integration: voice-driven globe, live area data and alerts (2026-10-11)](gods-eye.md)
- [Pip: drop a file on the island, then ask about it, WhatsApp it or email it (2026-10-12)](file-buddy.md)
- [REA reverse-engineer-and-clone: ingest a target, analyze it, build a best-effort clone, then iterate (2026-10-12)](rea-reverse-engineer-clone.md)
- [Deliberation engine: evidence-based opinions, recommendations, risk-tiered decisions and a decision ledger (2026-10-13)](deliberation-engine.md)
- [Self-evolution engine: idle-only capability-gap detection, GitHub learning backlog, crash-safe resume and gated self-modification (2026-10-13)](self-evolution.md)
- [Turning learned repositories into new Jarvis abilities (2026-10-11)](repo-abilities.md)
- [Learning GitHub repositories for coding, and multi-context awareness (2026-10-11)](repo-learning.md)
- [Long-term memory, API repair and bad-weather alerts (2026-10-10)](memory-apis-alerts.md)
- [WhatsApp automation, incoming calls and voice approvals (2026-10-10)](whatsapp.md)
- [Full YouTube and Spotify control with the island media card (2026-10-10)](media-player.md)
- [YouTube and native Spotify controls](media-controls.md)
- [Smooth island growth during long output](smooth-island-growth.md)
- [Streaming Ollama answers in the island](streaming-answers.md)
- [Visual interaction and checked Save outcomes](visual-interaction.md)
- [One expanding glass notch](voiceos-notch.md)

## Coding and development

- [Claude Code with local Qwen for Jarvis](claude-code-local.md)
- [Codex with local Qwen3.5 9B](codex-code-local.md)
- [Agent runtime additions](codex-runtime-integration.md)
- [Planned Codex workloads with LocalGithub](codex-workloads.md)
- [Coding experience curriculum](coding-curriculum.md)
- [Multilingual coding and animated UI verification](multilingual-coding.md)
- [Native Jarvis coding](native-coding.md)
- [PC context and dedicated Qwen training](pc-model-training.md)
- [Existing Python scripts and GUI edits](python-gui-edits.md)
- [Dedicated Qwen model and actual weight training](qwen-weight-training.md)
- [Streaming script creation and editing](streaming-coding.md)
- [Jarvis web and app development](web-app-development.md)

## Integrations and automation

- [Autonomous coding improvements](agenticseek-integration.md)
- [Idle-time anticipation](anticipation.md)
- [Automation upgrade](automation-upgrade.md)
- [Conservative local voice-command cleanup](command-cleanup.md)
- [DeepSeek Harness: how it works and how Jarvis uses it](deepseek-harness.md)
- [Ordered Windows execution providers](execution-providers.md)
- [Learning from experience](experience-learning.md)
- [Folder navigation and preferences](folder-navigation.md)
- [Gmail API — 2026-10-09 IST](gmail-api.md)
- [Gmail drafts in existing Chrome](gmail-drafts.md)
- [Hermes Agent integration](hermes-agent.md)
- [Hermes skills and route comparison](hermes-skills-and-comparison.md)
- [Planning and natural speech integrations](jarvis-repository-integrations.md)
- [Longer plans and execution checks](plan-execution.md)
- [Green public APIs, idle reader and serious alerts](realtime-data.md)
- [Repository-derived skills](repository-skills.md)
- [Skills and execution learning](skills-and-learning.md)
- [One observed next step and verified repeat navigation](step-planning.md)
- [SuperAGI toolkit integration](superagi-toolkits.md)
- [Ultron memory adaptation](ultron-integration.md)
- [Curated utility skills](utility-skills.md)
- [Imported Windows command execution](windows-commands.md)

## Audits and history

- [Jarvis feature and performance audit](FEATURE_AUDIT.md)
- [Response speed without changing models](gar-response-speed.md)
- [Jarvis hardware and model audit — 27 September 2026](MODEL_AUDIT.md)
- [Production validation and repair — 2026-10-07–08 IST](production-validation.md)
- [Live task validation — 2026-09-27](real-world-validation.md)
- [Repository overview archive — 2026-10-09 IST](repository-overview-history.md)
- [Jarvis system audit — 2026-10-07 IST](system-audit.md)
