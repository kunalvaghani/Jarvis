# Hybrid inference architecture inspection — 2026-10-14 IST

This map was recorded before implementation. The application uses Python,
requests and local Ollama; there is no existing cloud inference router. The
existing model selection contract is `model_selection.installed_model` and
configuration names in brain/knowledge/helper sections. Manual configuration
of arbitrary installed local models must stay intact.

| Representative request | Existing path |
| --- | --- |
| Open Chrome / lower volume | engine → commands.parse and intent_catalog → Actions.execute → guarded local executor; no model required for direct commands |
| Explain a general concept | commands → Knowledge queue → QuickAnswers or context selection → QuestionClient persistent subprocess → knowledge_worker.answer → local chat → streamed UI → speech/memory record |
| Fix a private project / operate a window | Actions → deliberation and brain task loop → BrainClient/brain_worker or coding backend → model_selection/local Qwen → tool registry/policy checks → local executor/checkpoints |

`QuestionClient` enriches requests with private profile, situation, catalog and
memory. The entire request therefore cannot be forwarded to cloud. The new
gateway must build a minimal independent public payload, refusing ambiguous
follow-ups and all task/PC observations. Screen capture stays local unless a
separate exact upload authorization is implemented.

`gpu_scheduler` already has process-shared priorities, VRAM envelopes, speech
reserve, CPU admission, owned leases, warm residency and bounded unloading.
`command_cleanup`, `context_selector` and realtime use tiny local helper models;
they must not gain a cloud destination. `model_recovery` restores configured local
models without cloud fallback. Knowledge and brain have separate cancellable
worker transports and deadlines. Streaming progress reaches the existing island,
not a new UI. AgentSession, DeerFlow, Hermes, native coding, GitHub and Unreal/Windows
automation use their existing local harnesses/tools and permissions.

The integration will add a question-only optional cloud adapter at the existing
knowledge-worker choke point, a shared durable quota controller and metadata-only
route status. Native structured/tool/vision transport is separately testable;
cloud proposals confer no authority to execute PC actions. Existing local paths
and manually configured models remain the fallback; no parallel model race or
new orchestration loop is needed.
