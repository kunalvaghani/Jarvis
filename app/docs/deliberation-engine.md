# Deliberation engine — reasoning, opinions and decisions

## Audit follow-up — 2026-10-15 IST

[Prompt09 evidence and rollback](../artifacts/jarvis-audit/modules/09-deliberation/inventory.md)
separates isolated approval fixtures from live user/GUI acceptance. Proposal
approval now matches the whole reply. “Yes, only draft it” is a refinement;
“no” cancels without another inference call. Explicit requests for a different
approach still allow a new proposal. High-risk “maybe”/negated goals ask for
clarification before planning. This is conservative English pattern matching,
not a multilingual intent or universal prompt-injection guarantee.

Model opinions must match the existing worker schema, including typed claims,
finite confidence, bounded fields and lists. Invalid responses use a heuristic.
The worker's bounded `model_used` envelope label is accepted as metadata and
cannot grant approval or change risk. This boundary is covered through the actual
Models.predict/generate path with fake local transport and cloud enabled.
Goals over 16,384 characters are rejected; cancellation is checked before and
after inference. The real BrainClient consumes a per-request deadline locally,
without sending it as model data or changing the shared timeout. A stalled
native dependency cannot be made hard real-time by this Python deadline.
The limit covers each owned inference attempt, not context gathering or total
recovery time across attempts.

Configuration requires booleans, known assertiveness/risk enums, confidence
0–1, timeout 0.1–120 seconds, 1–10 alternatives and 1–10,000 ledger rows.
The worker schema still caps returned alternatives at four.

Actions require literal boolean `True` from the approval handler. Approval cards
serialize decisions, reject backward/expired clocks and cannot be used twice.
Tool/model output claiming consent grants no authority. Each account action
still invokes its own existing preview/approval path; probability never replaces
that gate. Folder deletion is unsupported by the individual-file command.

New decision records use UUIDs and ASCII-escaped JSON, preserving decoded Unicode.
Recognized credentials, email addresses, private paths and context labels are
redacted in new goal/recommendation/chosen/outcome fields. Pattern matching does
not identify all possible personal data; the ledger remains local. Historical
rows are preserved until normal rotation, not retrospectively scrubbed. Writes
atomically replace the rotating ledger; “append-only” below means logical
decision/outcome events within that retention window. The unused unbounded ID
cache was removed. `last_ledger_error` reports a categorical persistence error;
the ledger is diagnostic, not the authority granting an action permission.

There is no deterministic research-before-action gate for every unfamiliar
program. Local-model advice and planner tool availability are not proof that
research occurred. Shared BrainClient transport concurrency and live spoofed-UI
resistance are not certified by the concurrent ledger fixture.

Jarvis forms its own evidence-based opinions instead of blindly following whatever
approach it is given. The deliberation engine ([jarvis/deliberation.py](../jarvis/deliberation.py))
is one shared decision layer wired at the central task choke point — not a separate
feature and not a duplicated decision loop. It builds on the existing
[cognition loop](cognitive-architecture.md) (memory, learned reliability, the world
model) and the adaptive [planner](../jarvis/brain.py).

## What it does

For a non-trivial, free-form task Jarvis:

1. **Understands** the real objective (including implied goals).
2. **Gathers evidence** from systems it already has: cognition memory recall, learned
   per-action reliability, and relevant saved skills.
3. **Generates and compares alternatives** and forms a recommendation, using a bounded
   local-model inference op (`deliberate`) with a heuristic fallback.
4. **Classifies risk** (low / moderate / high) — a single source of truth in
   `classify_risk`, reusing the world model's reversible/external/approval signals plus
   goal-text signals (delete, deploy, pay, credentials, …).
5. **Estimates confidence**, blending the model's self-estimate with learned reliability
   and penalising unresolved references.
6. **Decides** whether to proceed silently, note a brief recommendation and proceed, or
   propose-and-wait — honouring the configured assertiveness.
7. **Records** the decision, its alternatives, confidence, risk and real outcome to a
   traceable ledger.

Model claims are typed — **fact / assumption / prediction / preference** — so an
assumption or an unknown preference is never presented as a fact. Confidence is an
estimate, never proof.

## Speak up only when it matters (default)

With `assertiveness: "when_it_matters"` Jarvis stays quiet and just does simple or
clearly-agreed low-risk work. It speaks only when it has something to say:

- **Genuine disagreement** (it sees a materially better/safer approach, with enough
  confidence) → it proposes its approach and waits for your go-ahead.
- **Real ambiguity** it cannot resolve itself → it asks one specific question.
- Otherwise it proceeds.

**High risk alone does not add a second confirmation.** Destructive, financial,
external or otherwise consequential actions are still gated by Jarvis's single existing
approval path; the deliberation layer never duplicates that gate.

## Conversational feedback

When Jarvis has proposed something and is waiting, your reply is interpreted:

| You say | Verdict | Jarvis does |
| --- | --- | --- |
| "go ahead", "do it", "yes" | approve | executes the agreed approach |
| "no", "stop", "cancel" | reject | cancels the pending proposal without execution or retry |
| "no, try something else" | reject/refine | generates a different alternative and proposes again |
| "you decide", "do what's best", "whatever" | vague | picks the best low-risk reversible option and proceeds; asks for confirmation only if high-risk |
| a refinement ("use Rust instead") | refine | regenerates with your preference; an unrelated new request is handled normally |

## Autonomous recovery

If a task fails or pauses, Jarvis forms an alternative approach and offers it rather than
replaying the uncertain action — uncertain file writes, commands, sends and clicks are
never re-run automatically.

## Configuration (`config.json` → `deliberation`)

| Key | Default | Meaning |
| --- | --- | --- |
| `enabled` | `true` | Master switch. |
| `assertiveness` | `"when_it_matters"` | Also `"always"` (state understanding/opinion/why first on every non-trivial task) or `"on_request"` (opinion only when you ask or it is blocked). |
| `voice_confidence_threshold` | `0.6` | Minimum confidence before voicing a disagreement. |
| `ask_min_risk` | `"high"` | Risk tier at which a delegated ("you decide") decision still asks for confirmation. |
| `max_alternatives` | `3` | Alternatives considered per opinion. |
| `ledger_max` | `500` | Decision ledger size (rotated). |
| `timeout_seconds` | `20` | Bound on the model opinion call; it falls back to the heuristic if exceeded. |

## Decision ledger

`.jarvis-runtime/deliberation/decisions.jsonl` (append-only, rotated) records each
decision: goal, recommendation, alternatives, confidence, risk, what was chosen, the
approval, and the real outcome. Read it back with `Deliberation.decisions()`.

## Design guarantees

- **Bounded model wait.** Opinion inference can wait up to its configured deadline;
  on timeout/error it returns a heuristic. Risky ambiguity still pauses planning.
- **No duplicated approvals.** High-risk actions funnel through the one existing approval
  gate; this layer advises and sequences, it does not grant permissions.
- **No new background autonomy.** Nothing acts on its own beyond today's authorized
  monitors.
- **Latency-aware.** Deliberation runs only for non-trivial free-form tasks; trivial
  imperatives and explicit commands stay fast.

## Limitations

- Model-based opinions need the local model to answer within `timeout_seconds`. On a
  CPU-bound machine the qwen3.5:9b `deliberate` call can take well over a minute, so the
  fast heuristic is used instead; raise `timeout_seconds` (and/or run with GPU offload) if
  you want full model opinions and accept the wait.
- Opinions are only as good as the local model and the evidence available; they are
  advisory and revisable, never a guarantee.

## Verification

- Unit/behavioral: `python -m unittest tests.test_deliberation` (risk tiers, opinion
  formation, disagreement/ambiguity/agreement decisions, feedback verdicts, heuristic
  fallback, confidence calibration, ledger round-trip and rotation).
- Regression: `python -m unittest tests.test_cognition tests.test_brain tests.test_toolkits`
  and the full suite.
- Readiness: `python -m jarvis.launcher --offline-check`.
- Live: the `deliberate` op was driven against the local qwen3.5:9b model and returned
  well-formed opinions (recommendation, three alternatives, typed claims, confidence). See
  the dated results in [the app README](../README.md#current-validation-and-update-history).
