# Prompt11 — skill selection audit

2026-10-15 IST. **31 catalog fixture PASS / 1 BLOCKED / 0 FAIL / 0 SKIPPED / 0 NOT RUN.** JRV-11-002 is blocked: no validated arbitrary PDF-edit adapter is offered. Markdown-to-PDF creation is not arbitrary PDF editing. Optional utility validation was stale before this change; it remains disabled rather than rewriting proof hashes. This is not whole-system production certification.

Repo `e9f6f735bc310d11e3cdecfbf95a85d96b170ec2`, branch `codex/jarvis-prove-fix-audit`; Windows/Python3.10.6, Ryzen7/32GB/RTX3050 Laptop4GB target from prior native observations. CPU metadata-only work here; no GPU/model acquisition. app/ canonical, existing dirty work preserved, no commit/reset/install/provider setup/personal deletion/account write/OS mutation/deployment. No GUI change or new screenshot.

## Source map, dependency graph and safe order

| Claim / entry point | Actual checked-out evidence | Proven boundary / limitation |
| --- | --- | --- |
| Native/custom/personal guides | skills/, custom-skills/, skill_memory.SkillMemory.refresh/context | 10 bundled; bounded50/source; builtin > custom > personal deterministic collision reporting; hot reload uses path/mtime/size, not adversarial metadata forgery protection |
| Tool discovery | capabilities.rank_tools/runtime_context → ToolRegistry.search/catalog | Existing handlers only, prerequisites/scope/provider filters retained; unknown names diagnostic, not executable |
| Trust/provenance | refresh → skill_read folder=@jarvis | Origin, relative path, SHA256 and untrusted_guidance label; registry policy/current authorization remain authoritative; hash is consistency, not authenticity |
| Hermes references | hermes_skills.HermesSkills → skill_list/read folder=@hermes | 210 indexed SKILL.md contents verified,1090 indexed resources; unique bounded metadata, indexed exact resource/read budget, hashes checked; helpers not run |
| DeerFlow references | deerflow.status/search_skills/read_skill → folder=@deerflow | 23 public guides present; existing neighboring fixture suite, no provider readiness inferred from guide availability |
| Utility activation | utility_profiles.availability/tools → toolkits/registry | Separate environment exists but validation already stale before this update:0 offered. Missing/malformed/stale states fail closed. No arbitrary PDF-edit adapter offered |
| Learned procedures | SkillMemory.record/context | Existing verified recipe preserved after failure; new success/attempt counts, relevance then smoothed rate then recency; historical missing failures not reconstructed |
| Builtin and lifecycle policy | commands.py immutable dispatch; ToolRegistry.execute → check_policy/_execute/event | Existing builtin wins; denied/cancelled tools never dispatched in fixtures; categorical UUID metadata excludes payloads; no replay/helper queue |


Read system-map and linked skill/learning/runtime/Hermes/utility/DeerFlow documents; historical counts and live trials remain dated historical evidence. Actual order: source/registration/policy inventory → existing baseline → defect reproductions → smallest bounded fixes → catalog/fault/concurrency/security journeys → paired ranking benchmark/public census → full regression/readiness → accounting/docs. Dependencies: source metadata → bounded catalog → relevance/tool binding → current registry scope/provider/policy → per-action approval/executor → fresh readback → verified procedure history. External guidance never skips execution gates. No semantic model reranker added: deterministic bounded scoring is sufficient for the verified fixtures and avoids extra inference/VRAM/latency; general semantic quality remains unmeasured.

## Executed assertions and actual census

Baseline **77 PASS**, 4.33s,[XML](existing-baseline.xml). Eight before-fix regression failures reproduced,[XML](reproduced-failures.xml);12 incidental imported unittest passes in that first run are not extra new tests. The import was moved inside a helper to avoid duplicate collection. Final targeted **157 PASS / 1 BLOCKED skip**, 16.19s,[XML](cases-and-contracts.xml). Full **2355 PASS / 9 explicit BLOCKED skips**, 349.16s,[XML](full-regression.xml),[actual completion](full-run-completion.txt). Counts overlap. Launcher **ready**,[redacted check](readiness.json). Existing pywinauto STA COM warning is retained. [Commands](commands.txt),[all32 catalog IDs/assertions](tests.jsonl).

Read-only public-source census: **10 bundled, 210 Hermes/210 hash-verified guides, 1090 indexed resources, 23 DeerFlow public guides**.0 census errors. [Census](census.json). Supporting resources were counted, not all executed or live-certified. No real personal vault sync or synthetic procedure insertion in the real vault. Existing utility environment present, **stale_validation**, **0 offered**. Historical38-local/3-mock claims do not describe current activation.

Journeys include native browser guidance+real registered navigation selection, guide hot reload/delete, builtin/custom/personal duplicate precedence, malformed/unknown binding diagnostics, policy denial despite forged approval text, reserved-source readback, five threads×20 rounds of independent bounded contexts, cancellation before dispatch, temporary vault restart, stale guide hashes, Unicode/CRLF, unavailable prerequisites/upstream isolation,50-guide cap, repeated discovery without effects and payload-free UUID events. No test executes newly learned helpers or performs real account operations. Network outage/timeout fixtures assert discovery calls no network; they do not certify a live remote timeout. Pressure fixture bounds metadata/context, not physical VRAM. Negation fixture proves retrieval is not dispatch, not all-language intent accuracy. The positive utility fixture uses an empty executable sentinel and fake validation hashes solely for discovery/scope assertions, never as real installation evidence.

## Matched component measurement and keep decision

| Version/cache | Samples | p50 ms | p95 ms | Peak traced Python bytes |
| --- | --- | --- | --- | --- |
| before_cold | 5 | 12.713 | 20.267 | 152423 |
| before_warm | 20 | 12.588 | 12.777 | 5793 |
| after_cold | 5 | 8.583 | 8.671 | 232295 |
| after_warm | 20 | 6.618 | 12.850 | 5478 |

[Raw50 samples](benchmarks.csv),[scope/summary](benchmark-summary.json). Saved pre-change algorithm versus current on identical150 synthetic guide rows/six tool labels and machine; all50 selections identical. Five cleared description-cache calls and20 warm calls/version; cold does not mean cold OS/model.0 helper/tool/network effects. TTFT, first audio and VRAM are not applicable; traced bytes are transient component allocation, not whole-host RAM. Bounded2048 description-token cache does not cache goals and bypasses recognized credential descriptions; other personal metadata may remain in process memory. Cold allocation increases; retain for reduced repeated scoring work and bounded warm allocation, with timing variation explicit. No general precision/voice latency guarantee is inferred.

## Remaining limits

JRV-11-002 needs a reviewed installed/allowed arbitrary PDF-edit adapter and authorized validation. Do not refresh utility hashes without rerunning appropriate reviewed verification; live account/OS checks require separate approval. Guides are local untrusted text; labels/hashes do not prove authorship or prevent every prompt injection. Approval enforcement remains in current tool/action policy. Historical failure counts cannot be reconstructed from legacy procedure rows; the rate is a smoothed observed estimate after a recipe exists. Guide hot reload uses file metadata; malicious same-size timestamp restoration is outside its guarantee. Supporting helpers/providers, native model selection quality, actual desktop execution, physical GPU contention and long soak remain unverified. No catalog case is silently dropped.

[Failures](failures.md),[changes](changes.md),[upstream compatibility](compatibility.md),[rollback/resume](rollback.md),[exact files](files-changed.json),[scoped patch](source.patch). Next module NOT RUN: **JRV-12-004**; earliest global unresolved **JRV-04-001**.
