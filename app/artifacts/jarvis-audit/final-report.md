# Jarvis audit — Prompt 30, 2026-10-16 IST

**PARTIAL: 22 optional-planner catalog fixture PASS / 10 BLOCKED; no production or live model accuracy certification.**

Preserved dirty branch audit/12-tool-registry, commit 9bf5528e6d490fc3bbe92d0c62bcffae6c0946b6, canonical app/. Main Python 3.10.6, Windows-10-10.0.26200-SP0, RAM 33656832000 bytes. Target Ryzen 7 5800H / RTX 3050 Laptop 4 GB from the [historical hardware census](../../docs/MODEL_AUDIT.md); no GPU workload. [Current environment](modules/30-harness-planners/environment.json), [optional package/Python metadata](modules/30-harness-planners/optional-runtime.json), [actual configured routes](modules/30-harness-planners/configured-routes.json).

Deterministic planner/provider mocks; actual scoped reads of synthetic source; hash-checked public Hermes guide reads; five concurrent fixture requests × 20 rounds; actual owned Python JSONL worker echo, crash/restart and 100 response-isolation checks. No optional planner model inference, generated script installation, paid API, real desktop action, account operation, private recording or GPU workload ran. Model and SDK proposals remain distinct from real action or outcome proof. Launcher readiness may boot its already-installed owned check-only SDK transport; it is not a model accuracy test.

## Source-map-to-code evidence

| Documented claim | Source/entry and executed evidence | Limit |
| --- | --- | --- |
| Planner selection | BrainClient.request/_request → HarnessClient before HermesClient for plan/replan and scoped development code_plan | next_step, ordinary code_plan, code_edit, choose, decide and verify retain native routes; enabled Harness is not proof every task uses it |
| Hermes opt-in and guides | hermes.settings/validate_proposal + HermesSkills manifest/hashes | Disabled planner yields no HermesClient calls; 210 public guides remain discoverable/readable within explicit budgets; no helper script is executed |
| Trust boundary | validate_proposal → validate_plan → ToolRegistry; validate_agent_response → AgentSession | Unknown/unadvertised tools, duplicate/failed/completed action keys and invalid read calls refuse before dispatch; all execution stays with Jarvis |
| Configuration | planner_settings.settings → client and Harness worker; model_selection.required_models | Strict boolean flags, finite deadlines 10–180 Hermes / 10–300 Harness, bounded model names and recognized selector; enabled Harness model now included in readiness requirements |
| Laya | BrainClient._request_once choose + brain_worker.Models.predict | Missing checkpoint asks clarification without launch; missing import/file returns unavailable; unrelated native inference no longer requires Laya checkpoint. No new ranking-accuracy test |
| Concurrency and shutdown | Per-client request RLock; cancellable wait; bounded stdio reader | One response queue owner per client; eight pending messages and 8M-character protocol cap; dead worker detected even if EOF sentinel was dropped under backpressure. Separate clients lack shared task lease |
| Runtime disable | Effective cancel callback and flag recheck before returning optional result | In-flight disabled result discarded/cancelled; next explicit request takes current route; no new fallback executor |
| Recovery | Existing bounded one inference retry; original _on_code guard; TaskState pending uncertainty | Owned worker crash retries only inference; simulated uncertain external effect remains pending/paused. No external effect is executed by the fixture worker |
| Prompt/data boundary | Restricted Harness agent catalogue, profile IDs, structured parse, real readback | Malicious source remains data in tested read session; forged approval cannot expand read-only scope. Full cloud/log/semantic-accuracy oracle remains incomplete |
| Upstream isolation | harness_worker ACTIVE profile + OwnedJob; Hermes submit_jarvis_plan only; local Ollama adapters | Installed check-only readiness is narrower than model/SDK end-to-end privacy, trace and host-environment confinement |

```mermaid
flowchart LR
    Input[Jarvis request] --> Route{Operation and opt-in flags}
    Route -->|plan/replan/development plan| Harness[Harness priority when enabled]
    Route -->|plan/replan if Harness off| Hermes[Hermes when enabled]
    Route -->|other operations| Native[Native brain / Laya]
    Harness --> Proposal[Untrusted structured proposal]
    Hermes --> Proposal
    Native --> Proposal
    Proposal --> Validate[Caller validation and current tool catalogue]
    Validate --> Registry[Jarvis registry / approvals / checkpoints]
    Registry --> Readback[Independent observation]
```

## Actual test commands and outcomes

Baseline **49 PASS**. Twelve initial failing assertions reproduced and repaired; later EOF/backpressure failure repaired. Focused **236 PASS /10 explicit blocked skips / 0 FAIL**. Final full tests-directory suite **3165 PASS /147 SKIPPED / 0 FAIL**, JUnit suite duration 544.727s; console wall time and warnings are in the saved log. Launcher dependency/configuration readiness **ready**. All 395 frozen runtime/test files match after the full run. The superseded interrupted run is not counted.

For 50 replan-schema copies per batch, warm p50/p95 24.2095/25.4175 → 13.9932/14.9647 ms; peak temporary Python allocation 17884 → 76564 bytes. [Raw samples](modules/30-harness-planners/benchmarks.csv), [pre-upgrade baseline](modules/30-harness-planners/baseline-benchmarks.csv), [summary/scope](modules/30-harness-planners/benchmark-summary.json). Keep CPU overhead improvement with 58,680 bytes higher temporary peak allocation; no shared mutable branches or private-context cache. These 50-copy batches do not establish planner inference speed, tool-selection accuracy, cold SDK/RSS/VRAM, TTFT or first-audio performance. No optional planner was enabled based on them.

[Focused XML](modules/30-harness-planners/cases-and-contracts.xml) · [full XML](modules/30-harness-planners/full-regression.xml) · [full log](modules/30-harness-planners/full-regression.log) · [source freeze](modules/30-harness-planners/full-start-source-hashes.json) · [failures](modules/30-harness-planners/failures.md) · [commands](modules/30-harness-planners/commands.md) · [changes](modules/30-harness-planners/changes.md) · [exact files](modules/30-harness-planners/files-changed.json) · [diff](modules/30-harness-planners/source.patch) · [official upstream URLs/dates](modules/30-harness-planners/compatibility.md) · [retrieval provenance](modules/30-harness-planners/upstream-checks.json) · [rollback](modules/30-harness-planners/rollback.md).

## Exact 1,184-case accounting

All 1,184 unique case IDs retained: **{"PASS": 813, "FAIL": 0, "BLOCKED": 150, "SKIPPED": 0, "NOT RUN": 221}**. All 32 Prompt 30 IDs have executed assertions or concrete blockers; a narrow fixture pass cannot override a missing full-case contract. Prior modules remain dated evidence, not new live checks.

| Module/evidence | Status | PASS | BLOCKED | NOT RUN |
| --- | --- | ---: | ---: | ---: |
| [01-architecture-inventory](modules/01-architecture-inventory/inventory.md) | PARTIAL | 32 | 0 | 0 |
| [02-perception-cognition](modules/02-perception-cognition/inventory.md) | FIXTURE COMPLETE | 32 | 0 | 0 |
| [03-intent-direct](modules/03-intent-direct/inventory.md) | FIXTURE COMPLETE | 32 | 0 | 0 |
| [04-voice-stt](modules/04-voice-stt/inventory.md) | LIVE ACOUSTIC VALIDATION BLOCKED | 29 | 3 | 0 |
| [05-voice-tts](modules/05-voice-tts/inventory.md) | LIVE ACCEPTANCE BLOCKED | 30 | 2 | 0 |
| [06-questions-context](modules/06-questions-context/inventory.md) | 30 CURRENT FIXTURE PASS / 2 NATIVE ACCEPTANCE BLOCKED | 30 | 2 | 0 |
| [07-model-routing](modules/07-model-routing/inventory.md) | FIXTURE COMPLETE / LIVE CLOUD BLOCKED | 32 | 0 | 0 |
| [08-gpu-scheduler](modules/08-gpu-scheduler/inventory.md) | PARTIAL / SHARED SPEECH COORDINATION BLOCKED | 30 | 2 | 0 |
| [09-deliberation](modules/09-deliberation/inventory.md) | PARTIAL / MANDATORY UNFAMILIAR-PROGRAM RESEARCH BLOCKED | 31 | 1 | 0 |
| [10-dag-planning](modules/10-dag-planning/inventory.md) | FIXTURE COMPLETE / LIVE ACCEPTANCE UNVERIFIED | 32 | 0 | 0 |
| [11-skill-selection](modules/11-skill-selection/inventory.md) | 31 FIXTURE PASS / 1 BLOCKED; LIVE ACCEPTANCE UNVERIFIED | 31 | 1 | 0 |
| [12-tool-registry](modules/12-tool-registry/inventory.md) | 32 FIXTURE PASS; LIVE ACCEPTANCE UNVERIFIED | 32 | 0 | 0 |
| [13-desktop-control](modules/13-desktop-control/inventory.md) | 30 FIXTURE PASS / 2 BLOCKED; LIVE DESKTOP ACCEPTANCE UNVERIFIED | 30 | 2 | 0 |
| [14-browser-playwright](modules/14-browser-playwright/inventory.md) | 30 FIXTURE PASS / 2 BLOCKED; LIVE SITE ACCEPTANCE UNVERIFIED | 30 | 2 | 0 |
| [15-app-research](modules/15-app-research/inventory.md) | PARTIAL | 31 | 1 | 0 |
| [16-memory](modules/16-memory/inventory.md) | PARTIAL | 28 | 4 | 0 |
| [17-rag-documents](modules/17-rag-documents/inventory.md) | PARTIAL | 28 | 4 | 0 |
| [18-repo-learning](modules/18-repo-learning/inventory.md) | PARTIAL | 30 | 2 | 0 |
| [19-ability-forge](modules/19-ability-forge/inventory.md) | FIXTURE VERIFIED; LIVE/HARDENING GATES OPEN | 32 | 0 | 0 |
| [20-self-evolution](modules/20-self-evolution/inventory.md) | PARTIAL | 28 | 4 | 0 |
| [21-native-coding](modules/21-native-coding/inventory.md) | PARTIAL | 27 | 5 | 0 |
| [22-web-development](modules/22-web-development/inventory.md) | PARTIAL | 18 | 14 | 0 |
| [23-gmail](modules/23-gmail/inventory.md) | PARTIAL | 24 | 8 | 0 |
| [24-whatsapp](modules/24-whatsapp/inventory.md) | PARTIAL | 14 | 18 | 0 |
| [25-media](modules/25-media/inventory.md) | PARTIAL | 16 | 16 | 0 |
| [26-realtime-data](modules/26-realtime-data/inventory.md) | PARTIAL | 20 | 12 | 0 |
| [27-gods-eye](modules/27-gods-eye/inventory.md) | PARTIAL | 20 | 12 | 0 |
| [28-sandbox-deerflow](modules/28-sandbox-deerflow/inventory.md) | PARTIAL | 20 | 12 | 0 |
| [29-reverse-engineering](modules/29-reverse-engineering/inventory.md) | PARTIAL | 19 | 13 | 0 |
| [30-harness-planners](modules/30-harness-planners/inventory.md) | PARTIAL | 22 | 10 | 0 |
| [31-ui-island-pip](modules/31-ui-island-pip/inventory.md) | PARTIAL | 0 | 0 | 32 |
| [32-service-recovery](modules/32-service-recovery/inventory.md) | PARTIAL | 0 | 0 | 32 |
| [33-mcp-integrations](modules/33-mcp-integrations/inventory.md) | PARTIAL | 0 | 0 | 32 |
| [34-dependencies](modules/34-dependencies/inventory.md) | PARTIAL | 1 | 0 | 31 |
| [35-security](modules/35-security/inventory.md) | PARTIAL | 2 | 0 | 30 |
| [36-observability](modules/36-observability/inventory.md) | PARTIAL | 0 | 0 | 32 |
| [37-e2e](modules/37-e2e/inventory.md) | PARTIAL | 0 | 0 | 32 |


Tier totals:
```json
{
  "P0": {
    "PASS": 205,
    "BLOCKED": 35,
    "NOT RUN": 56
  },
  "P1": {
    "PASS": 440,
    "BLOCKED": 72,
    "NOT RUN": 117
  },
  "P2": {
    "PASS": 168,
    "BLOCKED": 43,
    "NOT RUN": 48
  }
}
```
Category totals:
```json
{
  "config": {
    "PASS": 29,
    "BLOCKED": 1,
    "NOT RUN": 7
  },
  "contract": {
    "PASS": 25,
    "BLOCKED": 5,
    "NOT RUN": 7
  },
  "edge": {
    "PASS": 57,
    "BLOCKED": 3,
    "NOT RUN": 14
  },
  "fault": {
    "PASS": 114,
    "BLOCKED": 6,
    "NOT RUN": 28
  },
  "idempotency": {
    "PASS": 25,
    "BLOCKED": 5,
    "NOT RUN": 7
  },
  "load": {
    "PASS": 28,
    "BLOCKED": 2,
    "NOT RUN": 7
  },
  "observability": {
    "PASS": 18,
    "BLOCKED": 12,
    "NOT RUN": 7
  },
  "performance": {
    "PASS": 21,
    "BLOCKED": 9,
    "NOT RUN": 7
  },
  "privacy": {
    "PASS": 21,
    "BLOCKED": 9,
    "NOT RUN": 7
  },
  "race": {
    "PASS": 25,
    "BLOCKED": 5,
    "NOT RUN": 7
  },
  "recovery": {
    "PASS": 50,
    "BLOCKED": 10,
    "NOT RUN": 14
  },
  "resource": {
    "PASS": 21,
    "BLOCKED": 9,
    "NOT RUN": 7
  },
  "scenario": {
    "PASS": 294,
    "BLOCKED": 69,
    "NOT RUN": 81
  },
  "security": {
    "PASS": 59,
    "BLOCKED": 1,
    "NOT RUN": 14
  },
  "semantic": {
    "PASS": 26,
    "BLOCKED": 4,
    "NOT RUN": 7
  }
}
```

## Remaining contracts and risk

- **JRV-30-007 BLOCKED:** The tested adapters keep private fixture text on local inference routes, but no complete SDK/host-environment/cloud request oracle proves that arbitrary private harness context cannot leak.
- **JRV-30-008 BLOCKED:** Step/action and protocol limits reject oversized plans; no complete token-overflow compaction and checkpoint-resume acceptance oracle across all optional planners.
- **JRV-30-009 BLOCKED:** Historical comparisons keep Hermes disabled and the current Harness SDK is pinned. No new matched live-model accuracy/latency trials establish a harness outcome advantage or a production downgrade threshold.
- **JRV-30-010 BLOCKED:** One BrainClient now serializes its stdio requests, but independent Brain/BrainClient instances sharing one TaskState lack a common task-generation lease.
- **JRV-30-021 BLOCKED:** No full fake-secret/Groq/telemetry/log/cache oracle. Upstream runtime environment and raw local Harness event exports can contain private task context.
- **JRV-30-023 BLOCKED:** Plan validation and real execution permissions are tested; no complete semantic do-X versus do-not-do-X model accuracy oracle.
- **JRV-30-024 BLOCKED:** Current registry and caller validations remain in force; no atomic observation/task-generation receipt binds all optional-planner proposals to execution across independent clients.
- **JRV-30-025 BLOCKED:** No host RAM-pressure/GPU-allocation failure experiment against concurrent core responsiveness. Fixtures use no GPU/model inference.
- **JRV-30-027 BLOCKED:** Schema-copy A/B uses20 warm+5 initial batches; no five cold full-planner processes with RSS/VRAM/TTFT/first-audio and matched live outcome accuracy.
- **JRV-30-032 BLOCKED:** Local task/turn IDs and failure events exist; complete optional-SDK trace correlation, secret redaction and retention/readback guarantees remain incomplete.

Per-client serialization does not grant task authority across independent clients. Prompt/output validation does not prove semantic intent, private-data non-disclosure, freshness or action success. Optional workers remain trusted host programs; local event logs/profile environments need full privacy/retention work. Eight queued text messages and an 8M-character cap are bounded backpressure, not a measured host-memory admission policy. There is no automatic switch to paid/cloud inference and no external-action retry added. Start/Stop/bootstrap/recovery/manifest interfaces remain compatible; no dependency or new service was declared. Shared source/profile/model upgrades need separately reviewed compatibility and resource tests. Existing historical slow/failed model comparisons remain valid context; native routes remain available.

## Deterministic resume

Next incomplete module case **JRV-30-007**; next untouched module **31/JRV-31-001**; oldest global unresolved **JRV-04-001**. [Module IDs](modules/30-harness-planners/remaining-case-ids.txt), [all remaining IDs](remaining-case-ids.txt). Implement privacy/cloud/log oracles, cross-client task-generation ownership, context-overflow recovery, matched live accuracy/latency, semantic negation/stale state and resource/trace acceptance. Follow commands.md, freeze, rerun focused/full/readiness, reconcile and verify. Never replay uncertain external actions. No installation or live account/system write is authorized by a fixture result. [Prior Prompt29 report](final-report-before-module30.md) preserves earlier metrics and limits.
