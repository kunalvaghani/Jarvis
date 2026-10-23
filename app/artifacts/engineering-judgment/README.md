# EJGAE verification — 2026-10-24 IST

Implemented and regression-verified on `codex/engineering-judgment`. Local configuration starts **advisory**. This is not full release acceptance. [Behavior and configuration](../../docs/engineering-judgment.md) · [Cumulative handoff](../../docs/CLAUDE_HANDOFF.md) · [56-category coverage map](acceptance-matrix.json) · [Release summary and open gates](release-summary.json).

## Final regression and readiness

- **PASS:** [complete suite](release-final/full-regression.txt): **4,268 passed / 150 skipped / zero failures / one existing COM threading warning / 1,383.89 s (23m 03s)**. Skips remain gated, not accepted live features.
- **PASS:** [804-file source integrity](release-final/source-integrity.json), [frozen inventory](release-final/source-before.json): no source/configuration/skill/test/verification-script or pinned-archive changes during the full run.
- **PASS:** [launcher readiness](launcher-final.txt): ready, no missing/incomplete components; configured Docker/Ollama/local Git available. Optional account inference was not live checked. No main microphone startup.
- [4,418 collected test IDs](full-test-collection.txt) and [individual outcome classifications](test-outcomes.json): the latter derive from sequential progress reconciled against the frozen-source collection order and exact final counts; this is not a native JUnit export. Each category in the acceptance map reports its referenced automated counts and remaining scope limits.
- [Known generated artifact restoration](generated-artifact-restoration.json): only the previously clean, suite-rewritten Blender natural-language audit fixture was restored from HEAD. No broad reset or user-work removal.

## Source and baseline

- [Reviewed upstream](upstream-review.json): current/pinned commit `2c606141936f1eeef17fa3043a72095b4765b9c2`; exact seven requested source files archived under `upstream/`. MIT declaration retained; no root LICENSE exists at that commit. Implementation attribution is forrestchang / multica-ai, inspired by Karpathy observations.
- [Architecture audit](architecture-audit.json) and [555-file baseline hashes](baseline-source.json): clean main `728c239` before runtime edits; task branch `codex/engineering-judgment`.
- [Pre-change regression](baseline-focused.txt): **360 passed / one gated skip / 67.61 s**.
- [Pre-change performance](baseline-performance.json): actual SkillMemory and parser plus five scoped atomic Coder fixtures, with a labelled model stub. Skill selection median **3.581 ms**, command parse **3.681 ms**, coding fixture **67.649 ms**, one model call/task, 5/5 expected outputs and unrelated notes unchanged. No live-model, acoustic, peak RAM/VRAM or general intelligence claim. Initial harness configuration/sandbox corrections are documented in the audit.

## Integration receipts

- [Initial integration](first-integration.txt): **251 passed / one skipped / four failed**. Failures were exact-count assertions/census for adding guide 12. Updated only current counts, retaining old dated snapshots.
- [Initial new policies](policy-first.txt): **57 passed / one failed**. `.git/config` was accepted by generic read scoping; the new write-scope guardian now explicitly refuses metadata/runtime/environment paths.
- [Corrected expanded integration](second-integration.txt): **350 passed / one gated skip / 117.32 s**, including actual native file edits and executable goal checks. Predates final planner/recovery/promotion refinements.
- [Final binding work](final-binding-focused.txt): **217 passed / one skipped / four failed**; new fixture harness errors (missing `apps` config and treating a report tuple as a dict), corrected in [125 passes](host-bindings-corrected.txt). These were not product failures.
- [Policy/crash/thread checks](policy-complete.txt): **74 passed**. Subsequent native and memory cases increased the new policy coverage.
- [Native readiness integration](native-readiness-focused.txt): **113 passed**; [subsequent native cases](native-ready-final.txt): **91 passed**.
- [Memory integration](final-memory-integration.txt): **133 passed / one gated skip**. The existing ReasoningBank storage/induction path is used; deterministic checks disable the embedder.
- [Final cognition/policy integration](final-awareness-focused-rerun.txt): **159 passed / 23.34 s** on the final runtime sources, including 79 new parameterized engineering cases. [The first command](final-awareness-focused.txt) used a nonexistent test filename and ran no tests; the corrected command is the receipt above. [An earlier command](pre-freeze-focused.txt) had the same harness-path error; [its corrected run](pre-freeze-focused-rerun.txt) passed **245 / one skip**.
- [Enabled skill evolution](enabled-skill-evolution.txt): **six passed / 37.53 s**, using [this additional check](test_enabled_skill_evolution.py), existing real stores and spreadsheet adapters, with a labelled stub text author. Larger bundled repairs remain review proposals; missing observations/new tool bindings are refused; an evolved repair with a failed real adapter check is rejected and preserves its old guide. This artifact check is separate from the frozen `tests/` full run.
- [Mapped repository-isolation cases](isolation-mapped-cases.txt): **two passed / 8.69 s**, using the existing real nonroot/cgroup/seccomp runtime and malicious-import isolation case. No runtime installation. These establish the referenced kernel boundaries, not general parallel coding isolation.

## Live local-model checks

These invoke the installed `qwen3.5:9b` through existing native coding, FileSession, executable checks, durable queue and result DAG. They edit only an owned connector-shaped fixture, with frozen tests and user notes; network/account/shell/install effects are excluded. They do **not** exercise the production YouTube account connector, voice/UI or an overnight duration. All `source_unchanged` values refer to source inventories frozen for that particular run.

| Run | Classification | Actual result |
|---|---|---|
| [First probe](live-native-1/acceptance.json), [counter review](live-native-1/review.json) | FAIL | First goal verified; second asked for a reliability target despite explicit return criteria. Fixed requirement validation; retained original receipt and clarified the initial aggregate counter. |
| [Second probe](live-native-2/acceptance.json) | PASS, earlier weaker fixture | 2/2 goals, 13 model calls; predates malformed-ID acceptance cases. |
| [Strict disabled control](live-disabled-final/acceptance.json) | PASS | 2/2 goals, 12 model calls, 306.08 s; frozen production-source inventory unchanged. |
| [Strict enforced attempt](live-enforced-final/acceptance.json) | FAIL | 1/2 goals; 9 model calls; second goal exhausted its time budget during redundant rereads. Frozen tests were protected. This is not a passing acceptance result. |
| [Corrected strict enforced probe](live-ready-final/acceptance.json) | PASS | 2/2 goals, 5 model calls, 93.16 s; actual checks and change scope verified, dependent result reused, unrelated notes/tests unchanged, frozen production-source inventory unchanged. |
| [Current memory binding](live-memory-binding.json) | PASS | Saved verified live task enters the existing ReasoningBank with goal provenance; repeat learning returns `already_learned`. Embeddings disabled in this owned storage fixture. |

The final native change invokes the existing verifier directly after a confirmed save when an enforced scoped assignment is ready. It avoids asking the model to request another check. Failed checks still enter the existing bounded repair path; there is no write replay. Memory/cognitive evidence refinements followed the successful native run; their current focused tests and the final full run cover those later changes. This two-goal comparison is not a general reliability or intelligence improvement claim.

## Performance and measurement limits

| Measurement | Post-change disabled control | Advisory | Interpretation |
|---|---:|---:|---|
| Warm skill selection median | 3.757 ms | 4.370 ms | +0.613 ms in this fixture; no extra classifier/model call. |
| Command parser median | 5.820 ms | 5.624 ms | Parser only; variation is not an acoustic or end-to-end speedup. |
| Five owned atomic coding tasks, median | 123.176 ms | 114.320 ms | Stubbed inference, one call/task, 5/5 expected outputs; load/noise precludes a speedup claim. |
| Process RSS before / after | 25.945 / 40.910 MiB | 25.898 / 41.777 MiB | Includes imports/catalog/coder work; not isolated or peak engine RAM. |
| Selected engineering context | 4,546 / 6,786 characters | 5,213 / 7,453 characters | +667 characters in the two engineering selection cases; ordinary open/Blender cases unchanged. Characters are not tokens. |

[Disabled measurements](control-disabled-performance.json) · [Advisory measurements](advisory-performance.json). The original pre-change coding median of 67.649 ms was measured under a different load; the matched post-change flag comparison above is more relevant. [Shared resident model snapshot](model-residency-snapshot.json) reports 2,155,756,911 VRAM bytes; this is not peak VRAM or EJGAE overhead. Exact prompt token counts, isolated peak RAM/VRAM, physical command response latency and population rates for unnecessary clarification, wrong assumptions and false completion are **NOT_RUN**. Known fixture failures and their fixes are recorded above; they cannot establish population rates.

The [machine-readable performance report](performance-report.json) classifies each requested metric explicitly and preserves these measurement limits.

## Remaining gates

The [56-category map](acceptance-matrix.json) distinguishes executable fixtures from broader semantic/live claims. General parallel coding isolation, semantic novelty of native repair strategies, external child/workload source attribution, actual YouTube/Spotify account operations, physical speech/duplex, battery/sleep/thermal and elapsed overnight endurance remain **NOT_RUN** for this upgrade. Existing historical voice 8/10 and multilingual failures remain open; they are not superseded by coding tests. Main microphone remains intentionally stopped. No package/model/driver installation or publication was performed.

Historical main/project/queue results remain historical and are not substituted for a fresh EJGAE full run.
