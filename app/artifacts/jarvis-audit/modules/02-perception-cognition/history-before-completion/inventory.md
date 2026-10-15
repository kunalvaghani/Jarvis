# Module 02 inventory — 2026-10-15 IST

**PARTIAL:** {'PASS': 18, 'FAIL': 0, 'BLOCKED': 0, 'SKIPPED': 0, 'NOT RUN': 14}. No whole-system production certification. [Cases](tests.jsonl), [remaining IDs](remaining-case-ids.txt).

Checkout commit `e9f6f735bc310d11e3cdecfbf95a85d96b170ec2`, existing branch `codex/jarvis-prove-fix-audit`; prior dirty work preserved. Windows main Python 3.10.6; RTX 3050 Laptop 4096 MiB and 31.35 GiB RAM from the October 14 inventory. No dependency, model or GPU allocation added.

| Claim / boundary | Implementation | Evidence / limit |
| --- | --- | --- |
| Voice ingress/order | `jarvis/engine.py:64` `feed` | Engine final segments dispatch immediately; attention is observational. |
| Sensor ingress | `jarvis/actions.py:121` `Actions.__init__` | filtered report accepts string alert messages; it does not parse sensor content as commands. |
| Bounded attention | `jarvis/cognition.py:209` `perceive` | 200 retained percepts/inbox entries; voice 1.0, screen .85, sensor <=.7; seven ranked slots. |
| Window lifecycle | `jarvis/cognition.py:249` `perceive_window` | Atomic old-window removal, empty-title invalidation and publication race filter. |
| Shared context | `jarvis/context_hub.py:26` `situation` | Local working memory enrichment; explicit private payload rejected by fake cloud boundary. |
| Idle preemption | `jarvis/self_evolution.py:321` `note_activity` | Cooperative cancellation; does not forcibly stop a non-cooperative native call. |
| Tick/persistence | `jarvis/cognition.py:577` `run` | Monotonic deadlines; owned coalescing writer; diagnostics for errors, duration, overrun and stale heartbeat. |
| Screen observation | `jarvis/screen_awareness.py:131` `observe` | Separate current-window/suggestion workflow, not tool execution on the cognitive tick. |
| Weather adapter | `jarvis/weather_watch.py:226` `check` | External read adapter; real provider/network not exercised by this module. |
| Recovery | `jarvis/task_state.py:22` `__init__` | Restarted running state becomes interrupted; uncertainty remains a resume blocker. |

Dependency order: sensor/Engine ingress → cognition attention → context_hub → independent Actions workers → outcome statistics; TaskState and approval gates govern writes. Tick metrics do not certify executor identity, actual sensor/parser isolation, voice naturalness or cloud availability.

Executed commands from app: `.venv/Scripts/python.exe -m pytest tests/test_perception_cognition_audit.py tests/test_cognition.py tests/test_cognition_and_routing.py tests/test_self_evolution.py tests/test_audit_resilience.py -q --junitxml=artifacts/jarvis-audit/modules/02-perception-cognition/cases-and-contracts.xml` (108 PASS); full `-m pytest tests -q --junitxml=artifacts/jarvis-audit/modules/02-perception-cognition/full-regression.xml` (1927 PASS).

Owned user journey: Engine wake → final open command captured, voice ranked above weather without losing weather; two final commands retain order. Destructive task proposal reaches the real approval boundary with a fake executor that must remain uncalled. These are fixture journeys, not live microphone or desktop interaction.

External side effects: zero live sends, account writes, personal deletes, OS changes or installs; only owned fixture/runtime metadata writes. No new long-running service. Existing start/close, writer recovery budget and Stop semantics retained.

Launcher `-m jarvis.launcher --check` returned `ready`, scope `dependencies_and_configured_services`; saved at private `.jarvis-runtime/jarvis-audit/module02-pre/readiness-final.json`. It does not certify live voice/accounts or overall production. Compileall and git whitespace checks passed.

Next exact unresolved case: **JRV-02-008**. Later module audits must finish every remaining ID rather than infer success from neighboring tests.
