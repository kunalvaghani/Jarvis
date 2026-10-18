# Upgrade Phase 5 of 8 — Safe cloud architect escalation and Show Me Once

Date 2026-10-18 IST. Branch `claude` (commit in [commit.txt](commit.txt)). `main` was not modified.
No Codex review evidence exists for this phase.

**Verdict: PASS for every locally executable check; real-provider checks BLOCKED (not authorized).**
No mandatory security failure remains open.

## What changed

| Part | Module | Summary |
| --- | --- | --- |
| A. Cloud architect | [`jarvis/cloud_architect.py`](../../../jarvis/cloud_architect.py) | Optional and **disabled by default**. Free-tier Groq only, used after three verified local reasoning failures and with consent. A refuse-don't-redact privacy gate runs on an allowlisted payload. Advice is untrusted: code is only AST-screened and then checked in the network-less Docker sandbox. A passing result becomes a provisional skill candidate. |
| B. Show Me Once | [`jarvis/demonstration.py`](../../../jarvis/demonstration.py) | Jarvis asks, with approval, for one user click. A low-level hook runs in its own process, ignores Jarvis's injected input, clicks outside the selected window and password fields. It stores a UIA selector without RuntimeIds, before/after state and a postcondition. It replays structurally, verifies the result and promotes it to a provisional skill. Recording resumes after interruption only with fresh consent. |
| C. Failure routing | [`jarvis/deliberation.py`](../../../jarvis/deliberation.py), [`jarvis/brain.py`](../../../jarvis/brain.py) | `classify_failure` + `FailureRouter`: each route is used at most once per task, at most three escalations per task. Authorization stops pause the task. Repeated unknown-UI failures offer Show Me Once. Planner-structure and repeated-weakness evidence is queued for later phases. |

Design, eligibility, the privacy model, security findings (K1–K4, J1–J2) and config defaults:
[security-and-design.md](security-and-design.md). Rollback and checklist: [rollback-and-codex-checklist.md](rollback-and-codex-checklist.md).
Diff: [source.patch](source.patch), [files-changed.txt](files-changed.txt).

## Results (2026-10-18)

| Check | Result | Classification | Evidence |
| --- | --- | --- | --- |
| Preflight related suites | 520 passed / 5 skipped | PASS | [pre-upgrade-relevant.log](pre-upgrade-relevant.log) |
| Phase 5 tests (privacy adversarial, mocked cloud replies, malicious output, consent/quota/plan gates, recursion, sandbox verification, real hook, UIA capture/replay, interruption, failure routing, brain trigger) | 38 passed / 0 skipped | PASS | [full-regression.xml](full-regression.xml) |
| Full regression | **3,315 passed / 147 skipped / 0 failed** (14 min 48 s) | PASS | [full-regression.log](full-regression.log) |
| `python -m jarvis.launcher --check` | `ready` | PASS | [launcher-check.json](launcher-check.json) |
| Privacy trace: 9 adversarial payloads | all kept local, **0 outbound requests** | PASS | [escalation-benchmark.json](escalation-benchmark.json) |
| Real Groq request | not made — no explicit authorization for a real provider test | BLOCKED | — |
| Physical user click during demonstration | a UIA `Invoke` stands in for the human click (MOCK input); hook, capture, replay and verification are real | PASS (capture/replay) / NOT RUN (physical click) | benchmark |
| Desktop exploration (from Phase 4) | still disabled without a verified VM | BLOCKED | Phase 4 |

## Measurements

From [escalation-benchmark.json](escalation-benchmark.json) (cloud provider MOCK):

| Measure | Value |
| --- | --- |
| Privacy gate, generic problem | p50 4.62 ms (n=20) |
| Refusal path (eligibility + gate) | p50 11.3 ms, max 398 ms (first-call imports) |
| Advice code verification in the Docker sandbox | 956 ms → `verified_candidate` |
| Outbound payload keys | `category, constraints, examples, question, statement` |
| Failure routing | 0.012 ms per call |
| Demonstration capture (incl. 400 ms settle) | 3.9 s |
| Structured replay + postcondition verification | 14.1 s (UFO provider), verified |

The Phase 1 baseline harness ([metrics-before.json](metrics-before.json) → [metrics-after.json](metrics-after.json)) showed no
regression. Intent routing stayed at 2,400/2,400 and privacy routing at 15/16 with 0 private cases marked public (unchanged).
DAG execution success stayed at 1.0 and catalog size at 94. Latencies were within noise or lower.

## Limitations

- **No real cloud consultation was performed.** The architect stays disabled until the user enables it, a free-tier
  configuration exists and consent is granted.
- Redaction is not a privacy guarantee. The gate refuses rather than redacts, so most real project problems will
  (correctly) stay local unless restated generically.
- The low-level hook gets no input while an elevated or system window is in the foreground (Windows UIPI). See J1.
- Capture and replay are slow because each observation walks the full UIA tree (J2). Production replay against the user's
  real application happens at the next real use, not automatically.
- Pillar A/C/training routes record evidence in `.jarvis-runtime/learning-queues/`. Their consumers arrive in later
  phases.
