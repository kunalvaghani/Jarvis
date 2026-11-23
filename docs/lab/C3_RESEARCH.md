# C3 literature, hypothesis review and conditional theory

## Current C4 implementation and C3 repair — 2026-11-04 IST

C4 now runs bounded ideal-pendulum length studies through the existing brain, Journal, queue/DAG and TaskState, retaining hard-constraint rejections and uncertain interrupted trials. Actual queue/fresh-process/crash/budget proof passes. C3 compact proposer v2 passes both approved local model calls (0.8B: 17.797 s; 9B: 52.531 s), with stored hypotheses independently replayed; capability remains UNVERIFIED and scientific claims remain speculative. Shipped Lab flags stay false; repair campaign remains paused. [Current report](C4_OPTIMIZATION.md) · [C4 proof](evidence/c4-brain-proof.json) · [C3 proof](evidence/c3-compact-wire-proof.json).

**Final C4 regression: 5,281 passed / 42 existing failed / 161 skipped**, 1,568.422 s including runner setup. The exact42 previous failing IDs remain, with zero new failures, zero Discovery failures and an unchanged source fingerprint. [Terminal comparison](evidence/c4-full-final.json). This isolated regression is not live voice/UI/control, physical validation or full scientific/release acceptance. Earlier counts below are historical. Focused verification: **208 passed / zero failures/skips**,59.97 s, unchanged source hash. Repository-configured neural mypy (18 files) passes; actual host launcher readiness reports ready. [Focused receipt](evidence/c4-final-focused.json). G/H, live UI/control and full scientific/release gates remain open. Earlier continuation entries below describe historical checkpoints, including the now-repaired v1/first-v2 proposal failures.

**Final C3 whole-project regression: 5,270 passed / 42 failed / 161 skipped**, 1618.750 s including runner setup. The exact same 42 prior failing IDs remain: zero new failures, zero Discovery failures, unchanged source fingerprint. This includes the final theory source-context addition. It is an isolated regression result, not live model-generation, microphone/UI, control or scientific release acceptance. [Terminal comparison](evidence/c3-full-final.json).

2026-11-04 IST. Branch `lab/phase-c3-research`. **Verified core candidate; generative model proposal acceptance remains unmet.** All shipped Lab flags remain false. No package/model download, paid API, external write or new persistent service was added. The unrelated repair campaign remains PAUSED_BY_USER. C2 was rechecked at 225 passes on its exact prior source fingerprint before C3 changes.

## Working paths and measured evidence

The latest [real ingress proof](evidence/c3-brain-proof.json) passes five requests through Engine → Actions → existing brain → C3 adapters → independent verifier → existing Journal/LabMemory:

1. DOI lookup of the actual *Optical Clocks and Relativity* record, `10.1126/science.1192720`.
2. Public literature search for the same topic, returning four Crossref metadata records. The arXiv response is an actual successful empty feed for this query, not four additional papers.
3. Repeat search using the durable successful-response cache, with no new metadata attempt reserved during the repeat.
4. Conditional inertial time dilation: coordinate interval **10 s**, beta **0.6**, computed proper time **8 s**, checked independently with Decimal and analytic limits.
5. A provided qualitative three-hypothesis dossier: environmental/instrumental null, relative-velocity mechanism and gravitational-potential alternative. Citations refer to actual cached metadata; all candidates remain **UNVERIFIED_SPECULATION**. Supplying this dossier in an operator-assisted proof is not autonomous scientific discovery.

The existing Journal retains typed Source, Claim, Hypothesis and RunArtifact records, exact source/dossier hashes and locators, stable excerpt-to-source edges, raw provider receipts, failed attempts, and verification references. Repeated/historical candidate records are not independent scientific findings. No second memory, model router, planner or scheduler was created.

**Checks:** C2 pre-change 225 passes. Combined C3/Lab/brain integration 245 passes, zero failures/skips, unchanged source hash. A final source-context addition for theory inputs then passed all 20 C3 domain tests and a new live core proof; the final full-project run includes that addition. Strict neural mypy passes on 18 files; actual read-only launcher readiness reports ready. [Focused receipt](evidence/c3-final-focused.json) · [Final domain receipt](evidence/c3-final-domain.json). The final whole-project comparison is complete above; the preceding full baseline was 5,250 passed / 42 failed / 161 skipped.

## Commands

Use a deliberately enabled private configuration (`lab.enabled=true`, `lab.research=true`, existing brain mode act). Theory additionally requires `lab.sim=true`. Production configuration was not activated.

```text
lab research "Optical Clocks and Relativity"
lab lookup doi "10.1126/science.1192720"
lab review hypotheses "relative/path/to/proposals.json"
lab theory dilation "examples/discovery/clock-dilation.json"
```

A provided dossier contains `review_id` from a successful current-code review and `tournament.hypotheses`, three to six qualitative candidates, exactly one null. Each candidate has `statement`, `prediction`, `assumptions` (list), `citation_ids` (real IDs from that review), and `is_null`. Unknown citations, duplicate statements, proof claims, numeric proposal claims, invalid bounds, malformed JSON, source changes and forged caller-supplied pass verdicts are refused. Dossiers are scoped local files; they are never sent to metadata providers or executed.

Basic search generates transparent **evidence-audit alternatives**: insufficient evidence/null; apparent differences due to context; substantive disagreement surviving context matching. These are review hypotheses, not automatically invented domain mechanisms. The supplied-dossier path allows actual distinct mechanistic proposals to enter the same skeptic/provenance framework without waiting for a model.

Optional commands are implemented but the live proposer is **DEGRADED**:

```text
lab hypothesize "c3-review-id"
lab hypothesize quick "c3-review-id"
```

These use only the exact existing local BrainClient/worker. The ordinary route preserves the configured reviewed local planner; quick explicitly requests the installed 0.8B model for this request. No global model policy changes or silent fallback. Unknown/cloud aliases are refused; served model identity must match. Candidate JSON is strict and never grants tool/code execution. Model outputs, even accepted ones, remain speculation and are checked by the independent deterministic skeptic.

## Model limitation: not a passing live generation result

The initial configured **Qwen3.5 9B** and explicit **0.8B quick** requests timed out at their 90 s / 20 s bounds. The user then approved a **scratch-only allowance increase from 120 to 300**, retaining prior charges, for at most two additional local 9B attempts (90 s requests / 95 s outer cancellation). **Both additional attempts also timed out. All four failures and 290 admission units remain charged uncertain**, not reported as measured worker CPU use. The two-attempt extension is exhausted; a durable grant/slot ledger now refuses another run before any model/network dispatch. Default product quotas/configuration remain unchanged. [Extension result](evidence/c3-model-qualification.json) · [Exact approved scope](C3_MODEL_QUALIFICATION_PLAN.md). Existing GPU admission controls the model: the 9B request was dispatched with 10 GPU layers and the quick request with zero layers. C3 model work is therefore not described as CPU-only or zero-residency work. No shared service/model was killed, reset or manually unloaded.

Schema/guard fixtures and the supplied-dossier proof do not replace live generative acceptance. [Retained failure/resource evidence](evidence/c3-limitations.json). Before promoting this capability, resolve the existing worker latency/context/admission path within approved local resources, then obtain an actual structured result, independent skeptic pass and fresh-session reuse. Changing global model/GPU policy, resetting charged attempts, increasing resource budgets, using paid inference or installing a new model needs its applicable authorization. Deterministic evidence review and supplied hypotheses remain independently available.

## Retrieval and scientific-integrity boundaries

Crossref and arXiv adapters are new scientific data adapters, reusing installed requests and stdlib parsers. Existing `neural.adapters._relevant` and `control.web.scouts.brief` provide CPU extraction/ranking and bounded source maps. Public queries reject obvious secrets, addresses, URLs, control characters and Windows paths. DOI lookup verifies returned identity. Only exact HTTPS provider hosts are requested; environment credentials/proxies and redirects are disabled. No PDF, arbitrary source link, paid OpenAlex/Firecrawl call, package download, signed-in portal or Google write is performed.

Responses are bounded to **262,144 bytes**, fixed result count, bounded connect/read/overall streaming time, with cancellation and no automatic retry. A rolling-day **50-attempt limit per existing Journal** records a slot before a read. Successful raw-response cache lasts 24 h; failed/unfinished same-query reads have a five-minute cooldown. Failed/uncertain reservations are retained. Two earlier failed attempts remain historically marked started/uncertain, with three successful response records. Subsequent failure records link a bounded reason/request artifact. Exact source receipts are required before verified review persistence; a caller-made `passed=true` cannot bypass the verifier.

Source records preserve metadata identity, publication type/date, available authors, response/record hashes and excerpt locators. DOI duplicates are merged for the view while provider provenance is retained. Revisions with changed metadata have distinct immutable source identities. Journal metadata is not proof of peer review or scientific truth. Update/retraction notices are quarantined; a missing notice is **not** a complete retraction check. Unknown licenses remain unknown. Public reports avoid duplicating publisher quotations; private receipts retain the excerpt/locator and actual answer hash.

Each excerpt is contiguous and at most 24 words. The evidence gate independently re-parses actual provider receipts and replays excerpt/hash/locator and skeptical-score checks. Candidate negation overlaps are only `POSSIBLE_CONTRADICTION_REQUIRES_CONTEXT_REVIEW`, never asserted contradiction edges or scientific refutations. The ranking score is computed citation coverage, not a probability, truth score or evidence that a hypothesis works. Conservation, energy, units, stability, causality, controls and primary methods remain explicit critique/test requirements; they are not claimed solved by lexical checks.

Official implementation references, checked 2026-11-04: [Crossref REST metadata documentation](https://www.crossref.org/documentation/retrieve-metadata/rest-api/) and [arXiv API manual](https://info.arxiv.org/help/api/user-manual.html). The former describes publisher/trusted-source metadata and public retrieval; the latter documents Atom entries/query interfaces and points to API terms. Retrieved full text and scientific verification are separate steps.

## Theory scope

The [clock input](../../app/examples/discovery/clock-dilation.json) explicitly supplies seconds and dimensionless beta. The equation is `proper_time = coordinate_time * sqrt(1 - beta^2)` for a constant subluminal inertial worldline in flat spacetime. Stable factorization, independent Decimal arithmetic, zero-speed and known subluminal cases check the calculation. Negative/superluminal/nonfinite inputs are refused, and numerically ill-conditioned cases must pass the independent tolerance before any verified result is saved.

The run presents a Newtonian null and conditional SR result separately from a backward-travel hypothesis with **INSUFFICIENT_EVIDENCE** and no executable mechanism. No gravity, acceleration, GPS orbit, wormhole metric or closed-timelike-curve calculation is provided. A model-consistent result is not a new physical validation or a working time machine. The theory input Source and immutable output artifact are linked in the same Journal.

## Integration and rollback

Nine explicit C3 neurons: `discovery.literature.collect`, `discovery.hypotheses.load`, `discovery.literature.review`, `discovery.hypotheses.propose`, `discovery.hypotheses.skeptic`, `discovery.verify.literature`, `discovery.literature.remember`, `discovery.theory.dilation`, `discovery.verify.dilation` (all `@v1`). Network collection and local dossier loading have separate contracts. All Lab capabilities now total **23 reviewed built-ins**, with zero C3 neurons when its flags are off. The proposer Capability is DEGRADED; the other static capability records remain UNVERIFIED in the scientific qualification vocabulary, with per-run provenance/model gates reported separately. [Inventory](evidence/c3-capabilities.json).

Only existing Actions intake hooks, brain source/adapter composition/compiler and optional runtime metadata were extended. Domain logic, parsers, tests, own Agent Skill and proof/report files are new. No new dependency or always-on process. Rollback stays `lab.enabled=false`; preserve histories/files. Do not restart intentionally stopped apps or resume the paused repair campaign.

From repo root, with the existing approved environment:

```powershell
app/.venv/Scripts/python.exe -B docs/lab/run_c3_proof.py --provided-hypotheses
app/.venv/Scripts/python.exe -B docs/lab/run_checks.py --receipt c3-domain-recheck.json tests/test_discovery_research.py
```

The proof uses actual public reads/cache and creates a new inert owned proposal file per explicit run; it does not replay an uncertain native/external write. It does not start the microphone/UI. The existing scratch Journal is now above its ordinary 120-unit daily allowance because the explicitly approved proof-only extension retained all 290 model reservations. Ordinary reruns can stop at that budget until the next UTC budget day. Do not reset charges, create a new Journal as a quota workaround, renew the exhausted grant, or add `--local-hypotheses` merely to repeat the timed-out proof. Product/default Journal limits were not increased. Reading the retained verified receipts requires no inference.

Remaining: passing local mechanistic generation; full-text/source entailment and substantive contradiction review; comprehensive retraction checks; Semantic Scholar/OpenAlex/PaperQA2 integration if needed with appropriate gates; signed-in portal/Docs/Sheets acceptance; live microphone/UI; richer GR/theory solvers; autonomous scientific A–H including G/H; existing 42 legacy defects and full release acceptance. [Remaining phases](NEXT_STEPS.md). No perfect/universal-science or complete release acceptance claim is made.
