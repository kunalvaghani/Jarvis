# Phase 5 — Design, security findings and configuration defaults

Date 2026-10-18 IST. Branch `claude`. Predecessors: Phase 1 `e847b00`, Phase 2 `16d9b4d`, Phase 3 `6f88033`, Phase 4 `6691425`.
No Codex feedback existed at preflight. No real cloud request was made in this phase.

## Preflight review (existing behaviour verified from source and tests)

| Item | Existing behaviour | Phase 5 relationship |
| --- | --- | --- |
| Retry counts | Inference retried once (`BrainClient._request`); read-only DAG steps up to 3 attempts; effectful steps 1; planned recovery bounded by `max_recoveries` (5) | Unchanged; the router never adds actions, and cloud consultation does not count as an extra planning attempt |
| Failure categories | `ToolRegistry.failure_category`: invalid_arguments / unavailable / cancelled / failed; attempted effects become `TaskFailure(attempted=True)` and are never replayed | `deliberation.classify_failure` adds recovery categories on top; no-replay rule unchanged |
| Cloud privacy | `cloud_policy.classify` fail-closed; `screen_payload` hard outbound guard; Groq only on a confirmed free plan with dedicated quota | The architect path reuses both and adds its own stricter allowlist gate |
| UI interaction | Structured UIA first, cyan pointer as fallback (Phase 2); pointer clicks are Windows touch injection | Demonstration recorder ignores injected input, so Jarvis's own cursor never counts as a user demonstration |
| Preflight suites | 520 passed / 5 skipped ([log](pre-upgrade-relevant.log)) | — |

## Part A — sanitized cloud architect (`jarvis/cloud_architect.py`)

Eligibility (all required, any miss keeps the problem local and lists why):
config enabled (**default false**); Groq enabled on a confirmed **free** plan with dedicated quota (a paid plan is refused,
never upgraded); category algorithm/coding/planning; **three distinct verified local strategy failures** with reasoning
causes; no non-reasoning cause (missing credentials, permission denial, unsafe action, external outage, unavailable tool,
cancellation); fewer than five automatic planning attempts used; not already consulted for this problem (no recursion);
explicit user consent for the request or a named scope (expiring, `ConsentStore`); quota state not
UNKNOWN/EXHAUSTED/CRITICAL; provider ready.

Privacy gate (`privacy_gate`), applied before any request:
1. Explicit field allowlist (`category`, `statement`, `question`, `constraints`, `examples`, `provenance`).
2. Provenance must be classified `public_fact` or `synthetic`; it is not sent.
3. Refuses paths (drive, UNC, POSIX home), filenames with common extensions, emails, URLs, secrets (existing `SECRET`),
   private/app context (existing `PRIVATE`, `PRIVATE_APP`), snake_case Jarvis module and tool names, the Windows user and
   computer names, source snippets (≥2 code-like lines), log excerpts and long identifiers.
4. Size bound, then the existing `screen_payload` hard guard.
5. Exactly the allowlisted payload is sent; a local log records the payload and its SHA-256 (the payload is generic by
   construction, so logging it reveals nothing private).

**Redaction is not treated as a privacy guarantee**: the gate refuses instead of redacting, and any uncertainty keeps
the problem local.

Untrusted output: the system prompt states the model has no tools and cannot act. Returned text is never executed or
interpreted as instructions (`actions_taken` is always 0). At most one code block is accepted. It must pass an AST
screen (pure functions, stdlib allowlist, no file/process/network/introspection, no top-level execution) and then run
only against the problem's own examples **inside the network-less, read-only, non-root container** (Phase 3 runtime). A
passing result becomes a `verified_candidate` with a **provisional** CAPTURED skill suggestion; it is never trusted
automatically.

## Part B — Show Me Once (`jarvis/demonstration.py`)

| Requirement | Implementation |
| --- | --- |
| Request | Spoken through the existing `spoken_reply` path (F5): "I can't reliably find the Export button. Could you click it once while demonstration recording is enabled?" |
| Consent | `actions._approve('demonstration_recording', …)` naming the application, window, what is recorded (clicks only) and the step limit; declining installs nothing |
| Scope | Clicks whose top-level window is not the selected window are discarded |
| User vs Jarvis | Low-level hook flags: `LLMHF_INJECTED`/`LLMHF_LOWER_IL_INJECTED` → ignored (Jarvis's cursor uses touch injection) |
| Captured | UIA control type, AutomationId, name, class, ancestry (≤6 levels), before/after state (title, static texts, toggles), relative point only as fallback |
| Never stored | RuntimeIds, keyboard input, field values, anything in a password field (`IsPassword`; unknown → private) |
| Candidate | Minimal `SKILL.md` with preconditions (application, window class) and steps; validated by the Phase 3 `validate_skill` |
| Replay | Structured UIA (`execution_router`) in a safe context; selector must be unique; postcondition must re-appear |
| Promotion | `promote()` only after a verified replay → provisional evolved skill; trust follows the Phase 3 lifecycle |
| Multi-step / restart | Up to 10 steps; state checkpointed after each step; `resume()` keeps steps but requires fresh consent |
| Hook process | The low-level hook runs in its own small process (only `ctypes`) so a slow Jarvis process cannot make Windows drop the hook |

In production, `Brain.recover_task` offers Show Me Once when an unknown-UI failure recurs within a task (≥2 failures): the
task pauses (no automation while recording) and `Actions.request_demonstration` asks, records with consent and confirms.
Replay against the user's real application is not automatic; verification happens the next time the selector is used.

## Part C — failure routing (`deliberation.classify_failure`, `FailureRouter`)

| Category | Route |
| --- | --- |
| missing tool | `pillar_a_capability_discovery` (Phase 3 discovery / MCP synthesis) |
| broken skill (degraded) | `pillar_a_fix` |
| unknown UI | `show_me_once` (Phase 4 exploration for approved sandboxed apps) |
| reasoning failure | `local_replan_then_cloud_architect` |
| planner structure | `pillar_c_evidence` (generalized row in `.jarvis-runtime/learning-queues/planner-failures.jsonl`) |
| repeated reasoning weakness (≥3 for a goal class) | training candidate (`training-candidates.jsonl`) |
| permission / risky | `stop_request_authorization` (`Brain` pauses) |
| unknown | `stop_request_guidance` |

Loop prevention: each route at most once per task, at most three escalations per task (permission stops are always
honoured); cloud consultation at most once per problem. Ordinary local replanning keeps its existing `max_recoveries` bound.

## Security findings

| ID | Finding | Status |
| --- | --- | --- |
| K1 | Nine adversarial privacy cases (fake credential, private path, internal module name, source snippet, log excerpt, email, private URL, personal context, unclassified provenance) never reached the outbound request | PASS ([trace](escalation-benchmark.json): `adversarial_cases_leaked: 0`) |
| K2 | Malicious cloud output (OS commands, `eval` of `__import__`, file writes, prompt-injection text asking to run commands and approve actions) is inert | PASS (tests) |
| K3 | Paid plan, missing consent, expired consent, exhausted quota, offline provider and repeated consultation all keep the problem local | PASS (tests) |
| K4 | Jarvis's own injected input and clicks outside the scoped window or in password fields are never recorded; RuntimeIds are never persisted | PASS (real hook classification + UIA tests) |
| J1 | During testing, injected input stopped reaching any low-level hook. Root cause: a system process window (`GameInputSvc.exe`) held the foreground and Windows UIPI withholds injected input from lower-integrity senders. An initial hypothesis that importing `pywinauto` broke the hook was **disproved** (the hook works with `pywinauto` loaded once the disposable window has focus). The test now focuses its own window and skips as BLOCKED if it cannot. | Resolved; documented |
| J2 | Demonstration capture (3.9 s incl. 0.4 s settle) and replay (14.1 s) are slow because each observation walks the full UIA tree | Open (performance) |

## Configuration defaults (`config/config.json`)

```json
"cloud_architect": {"enabled": false, "consent_minutes": 30},
"demonstration": {"enabled": true, "max_steps": 10}
```

Enabling the cloud architect also requires the existing `groq` section to be enabled on a confirmed free account and the
user to grant consent per request or scope (`ConsentStore.grant`).
