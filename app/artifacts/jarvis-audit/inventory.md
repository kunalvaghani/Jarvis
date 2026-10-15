# Reality inventory — 2026-10-14 IST

**2026-10-15 follow-up:** [Prompt 01 inventory](modules/01-architecture-inventory/inventory.md)
supersedes the architecture case status and census below. Its source, health,
claim and entry-point tables retain operational gaps. This whole-system
inventory remains a dated baseline; current catalog totals are in summary.json.

Commit `e9f6f735bc310d11e3cdecfbf95a85d96b170ec2`; branch `codex/jarvis-prove-fix-audit`. The initial dirty work is preserved in the private rollback snapshot. See [environment](environment.json), [37-module map](module-map.json), [catalog provenance](catalog-provenance.json), and [system-map link census](system-map-links.json). Both supplied and checkout maps were read; byte equality is reported in provenance (line ending differences need not mean changed claims).

Observed: 225 Python modules, 9 interpreter environments, 14 integration folders, 82 registered realtime entries. These are census counts, not proof of 82 healthy live endpoints. Each module's real candidate paths and existing assertion suites are below. Missing inferred filenames are recorded, not silently invented. Catalog candidate mapping is a work queue; it does not mean those cases ran.

Actual config/service evidence: Cognition/Actions/Brain are imported and instantiated by `main.py`/`actions.py`; ToolRegistry in `jarvis/tools.py` executes fixed names and scope/policy gates; UIA provider order includes the JarvisPointer before UFO/Windows-MCP/CUA/OpenComputerUse/AgentS (`execution_adapters.PROVIDERS`). Browser uses owned Playwright transport; the fresh local DOM journey passed. LocalGithub is a real local git checkout. Ollama /api/version returned 0.40.0, /api/tags and /api/show were read; configured required Qwen tags are installed. Hermes planner is disabled, DeepSeek Harness enabled. F5 is selected and has its separate CUDA torch environment. Configured does not imply a worker currently running. Launcher `ready` covers dependencies/configured services, not all live feature operations.

Memory, coding, Gmail/WhatsApp, adapters, God's Eye, DeerFlow, Hermes/Harness and REA have executable regression candidates and actual modules, with the boundaries in [security findings](security-findings.md). Account-backed and third-party live actions were not run. Native UIA smoke was blocked by Windows foreground denial. No universal autonomous app control is proven.

## Dependency order and deviations

```mermaid
flowchart LR
  Inventory --> Policy[Permissions and recovery]
  Policy --> Core[Cognition, intent, voice, model admission]
  Core --> Planning[Deliberation, DAG, registry, skills]
  Planning --> Workflows[Desktop, browser, memory, coding, accounts, data]
  Workflows --> Integration[Learning, sandbox, harnesses, REA, UI]
  Integration --> Gates[Security, soak, benchmarks, E2E]
```

The 37 prompts arrived after a narrow cognition audit was underway, so repaired core faults and an initial regression preceded pack ingestion. Full regression exercised the existing suites in pytest order; catalog-specific cases remain dependency ordered for continuation. [Static import graph](dependency-graph.json) and [static cycles](static-import-cycles.json) include lazy imports; cycles are candidates for review, not proof of runtime circular-import failures. No dead-code/duplicate-code completeness claim is made.

| Module | Real candidates / missing names | Executable regression paths | Catalog evidence | Status |
| --- | --- | --- | --- | --- |
| 01 architecture-inventory | `docs/system-map.md`, `jarvis`, `config/config.json`, `config/runtime_manifest.json`, `scripts`, `tests`, `README.md` | `tests/test_project_structure.py`, `tests/test_capabilities.py`, `tests/test_runtime_health.py` | {'NOT RUN': 32} | PARTIAL |
| 02 perception-cognition | `jarvis/cognition.py`, `jarvis/engine.py`, `jarvis/context_hub.py`, `jarvis/screen_awareness.py`, `jarvis/weather_watch.py` | `tests/test_cognition.py`, `tests/test_cognition_and_routing.py`, `tests/test_screen_awareness.py` | {'PASS': 4, 'NOT RUN': 28} | PARTIAL |
| 03 intent-direct | `jarvis/commands.py`, `jarvis/engine.py`, `jarvis/actions.py`, `jarvis/intent_catalog.py`, `docs/natural-language.md`, `docs/windows-commands.md` | `tests/test_jarvis.py`, `tests/test_intent_testbook.py`, `tests/test_natural_names.py`, `tests/test_windows_commands.py` | {'NOT RUN': 29, 'PASS': 3} | PARTIAL |
| 04 voice-stt | `jarvis/voice_input.py`, `jarvis/engine.py`, `config/config.json`, `docs/fast-conversation.md`, `docs/push-to-write.md` | `tests/test_whisper.py`, `tests/test_command_cleanup.py`, `tests/test_push_to_write.py` | {'NOT RUN': 32} | PARTIAL |
| 05 voice-tts | `jarvis`, `docs/f5-voice.md`, `config/config.json`; unresolved: jarvis/speech_worker.py | `tests/test_f5_speech.py`, `tests/test_speech.py`, `tests/test_answer_stream.py`, `tests/test_natural_voice.py` | {'NOT RUN': 32} | PARTIAL |
| 06 questions-context | `jarvis/knowledge_worker.py`, `jarvis/context_hub.py`, `jarvis/conversation_memory.py`, `jarvis`, `docs/natural-conversation.md` | `tests/test_knowledge.py`, `tests/test_quick_answers.py`, `tests/test_natural_conversation.py` | {'NOT RUN': 32} | PARTIAL |
| 07 model-routing | `jarvis/knowledge_worker.py`, `jarvis/brain.py`, `jarvis/groq_adapter.py`, `jarvis/gpu_scheduler.py`, `config/config.json`, `docs/groq-hybrid.md` | `tests/test_groq.py`, `tests/test_inference_limits.py`, `tests/test_model_selection.py`, `tests/test_ollama_models.py` | {'NOT RUN': 29, 'PASS': 3} | PARTIAL |
| 08 gpu-scheduler | `jarvis/gpu_scheduler.py`, `jarvis/brain.py`, `config/config.json`, `docs/gpu-priority.md`; unresolved: jarvis/speech_worker.py | `tests/test_gpu_scheduler.py`, `tests/test_model_recovery.py` | {'NOT RUN': 32} | PARTIAL |
| 09 deliberation | `jarvis/deliberation.py`, `jarvis/cognition.py`, `jarvis/brain.py`, `jarvis/task_recovery.py`, `docs/deliberation-engine.md` | `tests/test_deliberation.py` | {'PASS': 3, 'NOT RUN': 29} | PARTIAL |
| 10 dag-planning | `jarvis/brain.py`, `jarvis/task_recovery.py`, `jarvis`, `docs/hierarchical-execution.md` | `tests/test_hierarchical.py`, `tests/test_task_graph.py`, `tests/test_plan_execution.py`, `tests/test_task_state.py` | {'NOT RUN': 31, 'PASS': 1} | PARTIAL |
| 11 skill-selection | `jarvis/capabilities.py`, `jarvis/skill_memory.py`, `skills`, `custom-skills`, `docs`, `.venv-skills` | `tests/test_skill_memory.py`, `tests/test_hermes_skills.py`, `tests/test_capabilities.py` | {'NOT RUN': 31, 'PASS': 1} | PARTIAL |
| 12 tool-registry | `jarvis/actions.py`, `jarvis/toolkits.py`, `jarvis/tools.py`, `jarvis/native_tools.py`, `jarvis/capabilities.py` | `tests/test_tools.py`, `tests/test_native_tools.py`, `tests/test_toolkits.py`, `tests/test_agent_runtime.py` | {'PASS': 5, 'NOT RUN': 27} | PARTIAL |
| 13 desktop-control | `jarvis/desktop_actions.py`, `jarvis/actions.py`, `integrations/execution-primitives`, `integrations/execution-upstream`, `docs/windows-commands.md` | `tests/test_ui_controls.py`, `tests/test_visual_fallback.py` | {'NOT RUN': 32} | PARTIAL |
| 14 browser-playwright | `jarvis/browser_automation.py`, `jarvis/browser_worker.py`, `jarvis/app_knowledge.py`, `docs`, `tests` |  | {'NOT RUN': 32} | PARTIAL |
| 15 app-research | `jarvis/knowledge_acquisition.py`, `jarvis/app_knowledge.py`, `jarvis/browser_worker.py`, `docs/autonomous-learning.md` | `tests/test_knowledge_acquisition.py`, `tests/test_live_app_context.py` | {'NOT RUN': 32} | PARTIAL |
| 16 memory | `jarvis/memory_curator.py`, `jarvis/conversation_memory.py`, `jarvis/obsidian_memory.py`, `jarvis/skill_memory.py`, `jarvis/experience_memory.py`, `jarvis/context_hub.py` | `tests/test_obsidian_memory.py`, `tests/test_cognition.py` | {'NOT RUN': 31, 'PASS': 1} | PARTIAL |
| 17 rag-documents | `jarvis`, `docs/file-buddy.md`, `jarvis/native_tools.py`, `jarvis/memory_curator.py` | `tests/test_buddy.py` | {'NOT RUN': 32} | PARTIAL |
| 18 repo-learning | `jarvis/repo_learning.py`, `jarvis/repo_tools.py`, `jarvis/toolkits.py`, `docs/repo-learning.md`, `integrations` | `tests/test_repo_learning.py`, `tests/test_repository_skills.py` | {'NOT RUN': 32} | PARTIAL |
| 19 ability-forge | `jarvis/repo_abilities.py`, `jarvis/repo_learning.py`, `jarvis/capabilities.py`, `docs/repo-abilities.md` | `tests/test_repo_abilities.py`, `tests/test_repository_skill_isolation.py` | {'NOT RUN': 32} | PARTIAL |
| 20 self-evolution | `jarvis/self_evolution.py`, `jarvis/anticipation.py`, `jarvis/repo_learning.py`, `jarvis/repo_abilities.py`, `docs/self-evolution.md` | `tests/test_self_evolution.py`, `tests/test_anticipation.py` | {'NOT RUN': 32} | PARTIAL |
| 21 native-coding | `jarvis/native_coding.py`, `jarvis/coding_activity.py`, `jarvis/coding_console.py`, `jarvis/coding_curriculum.py`, `jarvis/coding_files.py`, `jarvis/coding_languages.py`, `jarvis/coding_lessons.py`, `jarvis/coding_operations.py`, `jarvis/coding_processes.py`, `jarvis/coding_programs.py`, `jarvis/coding_training_data.py`, `docs/native-coding.md`; unresolved: LocalGithub path and integration | `tests/test_native_coding.py` | {'NOT RUN': 32} | PARTIAL |
| 22 web-development | `jarvis/native_coding.py`, `jarvis/browser_automation.py`, `jarvis`, `docs/web-app-development.md` | `tests/test_development.py` | {'NOT RUN': 32} | PARTIAL |
| 23 gmail | `jarvis/gmail_api.py`, `jarvis/gmail_writes.py`, `docs/gmail-api.md` | `tests/test_gmail_api.py`, `tests/test_gmail_writes.py`, `tests/test_gmail_workflows.py` | {'NOT RUN': 32} | PARTIAL |
| 24 whatsapp | `jarvis/whatsapp.py`, `jarvis/messengers.py`, `docs/whatsapp.md` | `tests/test_whatsapp.py` | {'NOT RUN': 32} | PARTIAL |
| 25 media | `jarvis/media_player.py`, `jarvis/spotify.py`, `jarvis/actions.py`, `docs/media-player.md` | `tests/test_media_player.py`, `tests/test_media_routes.py`, `tests/test_spotify.py`, `tests/test_media_process_ownership.py` | {'NOT RUN': 32} | PARTIAL |
| 26 realtime-data | `jarvis/realtime.py`, `jarvis/realtime_sources.py`, `jarvis/weather_watch.py`, `docs/realtime-data.md` | `tests/test_realtime.py`, `tests/test_memory_weather.py` | {'NOT RUN': 31, 'PASS': 1} | PARTIAL |
| 27 gods-eye | `jarvis/gods_eye.py`, `integrations/gods-eye-view-src`, `docs/gods-eye.md` | `tests/test_gods_eye.py`, `tests/test_gods_eye_view.py`, `tests/test_gods_eye_cameras.py` | {'NOT RUN': 32} | PARTIAL |
| 28 sandbox-deerflow | `jarvis/deerflow.py`, `jarvis/deerflow_sandbox.py`, `jarvis/docker_runtime.py`, `docs/deerflow.md`, `docs/deerflow-sandbox.md` | `tests/test_deerflow.py`, `tests/test_repository_skill_isolation.py` | {'NOT RUN': 32} | PARTIAL |
| 29 reverse-engineering | `jarvis/rea_tools.py`, `integrations`, `docs/rea-reverse-engineer-clone.md` | `tests/test_rea_tools.py` | {'NOT RUN': 31, 'PASS': 1} | PARTIAL |
| 30 harness-planners | `jarvis/brain.py`, `jarvis`, `integrations`, `docs/deerflow.md`, `config/config.json` | `tests/test_hermes.py`, `tests/test_harness.py`, `tests/test_model_selection.py` | {'NOT RUN': 32} | PARTIAL |
| 31 ui-island-pip | `jarvis`, `docs/dynamic-island.md`, `docs/file-buddy.md`, `docs/independent-cursor.md` | `tests/test_buddy.py`, `tests/test_island.py`, `tests/test_hud.py`, `tests/test_independent_cursor.py` | {'NOT RUN': 32} | PARTIAL |
| 32 service-recovery | `jarvis/launcher.py`, `jarvis/recovery.py`, `config/runtime_manifest.json`, `docs/CRASH_RECOVERY.md`, `Start Jarvis.cmd`, `Stop Jarvis.cmd` | `tests/test_recovery.py`, `tests/test_task_recovery.py`, `tests/test_launcher_readiness.py`, `tests/test_task_state.py` | {'NOT RUN': 32} | PARTIAL |
| 33 mcp-integrations | `jarvis/mcp_bridge.py`, `jarvis/toolkits.py`, `config/config.json`, `docs/superagi-toolkits.md` | `tests/test_toolkits.py`, `tests/test_agent_runtime.py` | {'NOT RUN': 32} | PARTIAL |
| 34 dependencies | `requirements`, `.venv`, `.venv-brain`, `.venv-deerflow`, `.venv-f5`, `.venv-harness`, `.venv-hermes`, `.venv-hermes-bootstrap`, `.venv-skills`, `.venv-training`, `config/runtime_manifest.json`, `scripts`, `integrations`, `Start Jarvis.cmd`; unresolved: package*.json | `tests/test_launcher_readiness.py`, `tests/test_project_structure.py`, `tests/test_ollama_models.py` | {'NOT RUN': 31, 'PASS': 1} | PARTIAL |
| 35 security | `jarvis/deliberation.py`, `jarvis/actions.py`, `jarvis/capabilities.py`, `jarvis/knowledge_worker.py`, `jarvis/toolkits.py`, `config/config.json` | `tests/test_groq.py`, `tests/test_repository_skill_isolation.py`, `tests/test_toolkits.py`, `tests/test_agent_runtime.py` | {'NOT RUN': 30, 'PASS': 2} | PARTIAL |
| 36 observability | `jarvis`, `scripts`, `tests`, `artifacts`, `config/runtime_manifest.json` | `tests/test_agent_runtime.py`, `tests/test_runtime_health.py`, `tests/test_cognition_and_routing.py` | {'NOT RUN': 32} | PARTIAL |
| 37 e2e | `docs/system-map.md`, `tests`, `scripts`, `config`, `artifacts`; unresolved: entire jarvis/ | `tests/test_hierarchical.py`, `tests/test_knowledge_acquisition.py`, `tests/test_task_routing.py` | {'NOT RUN': 32} | PARTIAL |
