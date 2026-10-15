# Security findings and limits — 2026-10-14 IST

**2026-10-15 follow-up:** Startup now bounds configuration input and lifecycle
events enforce fixed envelopes and categorical metadata. All 32 architecture
cases passed. [Reproductions and limits](modules/01-architecture-inventory/failures.md)
cover these repairs; other open concerns below remain. Official Python
documentation corroborates the audit-hook isolation limitation; Python 3.10 is
upstream end-of-life. A clean scoped regression is not a whole-system security
certification.

Passed executed boundaries include private-context Groq exclusion, forged learned-command precedence, unsupported tool/scope rejection, volume validation without audio mutation, negated-command non-dispatch, bulk destructive task proposal, and uncertain external-write non-replay. Existing Docker repository isolation tests execute only authored throwaway fixtures and assert non-root/read-only mounts, network/process denial and resource limits. No real accounts or private captures were used.

Open release concerns:

1. **AbilityForge host isolation (module 19/35):** `repo_abilities._execute` starts `ability_runner.py` in a host venv subprocess. Python audit hooks/static checking differ from `repo_sandbox.py` kernel isolation. Standard-library generated self-tests can run before activation approval. No live learned code was executed during this audit and no exploit/escape was demonstrated. Arbitrary learned-code host execution is not certified; a bounded Docker migration needs its own compatibility, approval and regression pass. This prevents an all-system security release claim.
2. **Cloud provenance:** regex/NFKC privacy guards pass the authored corpus but cannot prove arbitrary quoted private prose safe. Approved private/screen/file/account material must stay local. No live Groq/private-payload test was sent; live provider contract remains NOT RUN.
3. **Audit traces:** lifecycle events omit arguments/responses, but repository-wide exception/repair-log redaction is not comprehensively proven. No actual credential is stored in this bundle; environment credential flags report presence only. Synthetic exception traces remain. Full adversarial secrets census is pending.
4. **Ground-truth learning — updated 2026-10-15:** `Cognition.act` excludes unexecuted pending proposals; attempted failures followed by recovery still count. Task UUIDs now bind planner results and explicit tool metadata, with stale completion rejected. Executed fixtures prove mismatched IDs and a task replaced during inference cannot execute the stale plan or finish the new task. Complete typed terminal verification and universal concurrency safety remain unproved; no claim of model-calibrated success beyond the audited statistical contract. See [module 02 evidence](modules/02-perception-cognition/inventory.md).
5. **Licensing and hardware:** commercial pretrained F5 licensing, human voice similarity/pronunciation, long GPU contention, unattended self-patching and live external account workflows are not release-certified.

No unapproved external writes were performed by this audit. Passing finite fixtures is not a proof of universal absence of leaks. Catalog red-team cases remain visible in test-results.jsonl and remaining-case-ids.txt.

**Prompt05 follow-up — 2026-10-15:** Production Speech workers now discard native
stderr instead of appending spoken/reference text to speech.log. Parent/worker
protocol failures and health are categorical; malformed/stale/duplicate frames,
Stop races and audio bounds have executed assertions. Existing private logs and
the ignored no-playback audit diagnostic log were preserved, not published or
silently deleted. This does not prove repository-wide log redaction.

Real cached F5 CUDA, Speech→Kokoro missing-reference fallback and Piper PCM passed
with speakers disabled. Human French/Hindi pronunciation acceptability is blocked.
STT and F5 remain outside the shared Ollama lease coordinator: Qwen speech
reservation is tested, but shared STT/F5 admission/contention is not certified.
Both limits remain explicit in the [module05 ledger](modules/05-voice-tts/tests.jsonl)
and prevent a complete speech/whole-system production readiness claim.

## Prompt06 — 2026-10-15 IST

Private malformed-answer search escalation, unsafe/empty evidence, selector cancellation and shared-reply isolation fixed with reproduced/asserted boundaries. Question health uses content-free UUID/status/error categories. Broad semantic injection resistance, live web/cloud, two-second acoustics and prior shared GPU lease blockers remain open. See modules/06-questions-context/inventory.md.

## Prompt07 — 2026-10-15 IST

Common bare-key outbound and new-record redaction, exhausted-quota wait, mixed-case backoff, zero/malformed usage and unsafe model metadata repaired with failing-before/passing-after assertions. Route UUIDs correlate reservations. Live cloud entitlement/billing/inference remains blocked; regex matching is heuristic and historical records are preserved. See modules/07-model-routing/inventory.md.

## Prompt08 — 2026-10-15 IST

Bounded owner/cache state, role-priority integrity, metadata filtering, probe-failure cleanup, duplicate acquisition and low-resource learning repaired with fixtures. Shared F5/Whisper ownership002/012 remains blocked; no timeout kills a live/shared owner. Calibrated20% arithmetic margin is not universal physical capacity proof. See modules/08-gpu-scheduler/inventory.md.
