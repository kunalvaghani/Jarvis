# Module 03 intent/direct audit — 2026-10-15 IST

**PARTIAL:** {'PASS': 11, 'FAIL': 0, 'BLOCKED': 0, 'SKIPPED': 0, 'NOT RUN': 21}. [Executed cases](tests.jsonl), [exact pending IDs](remaining-case-ids.txt). Eleven named scenarios have controlled routing/handler fixture assertions. JRV-03-005 remains NOT RUN: safe latest-file delegation is tested, but actual ambiguity resolution/clarification has no complete assertion. The additional fault/concurrency/security/performance matrix remains separately pending where no exact assertion exists. No production or live GUI certification.

Checkout commit `e9f6f735bc310d11e3cdecfbf95a85d96b170ec2`, branch `codex/jarvis-prove-fix-audit`; existing dirty work preserved. Main Python 3.10.6, Windows, RTX 3050 Laptop 4096 MiB/31.35 GiB RAM from prior inventory. No new dependency/model/GPU allocation.

| Claim | Real path / boundary | Evidence / limit |
| --- | --- | --- |
| Deterministic reflexes | `jarvis/commands.py:parse`, immutable REFLEX | Exact pause/volume up/open Chrome bypass canonical and learned interpretation. No LLM invoked by parsing. |
| Everyday canonical form | `jarvis/phrasing.py:canonical` | Leading synonyms/wrappers and existing composed-versus-verbatim writing policy; finite coverage, not arbitrary language understanding. |
| Built-in precedence | `jarvis/intent_catalog.py:match`, COMPILED tuple and fingerprint | Full-match rules before generic app handlers and learned abilities. Four narrowly anchored additions. |
| Alias/collision handling | `jarvis/names.py:rank_spelling`, `Actions._execute` open branch | VS Code aliases tested; exact configured Chrome launch goes through a fake process transport once. |
| Negative command | `commands._parse`, `Engine.feed` | Please do not open Chrome produces no dispatch; approval/negative policy preserved. |
| Compound request | `engine.Engine._feed` | Open Notepad, then type hello dispatches ordered commands and binds target Notepad; no actual typing. |
| Latest-file ambiguity | intent temporal-file rule → task planner | Avoids guessed app launch. Actual newest-file resolution and live ambiguity dialogue not verified. |
| Volume/unknown tool | `spotify.volume`, commands toolkit admission | 150 percent rejected before fake volume setter; unknown tool and exact unknown-command phrase refused. |
| Tab scope | built-in Windows command 329 | Corrected tab phrase maps to existing tab-close command; no real shortcut/browser closure. Existing approval/target checks remain. |

Dependency order: Engine final speech → deterministic parse/phrasing/catalog → registered Actions handlers → owned executors and approval/readback. The cognition tick observes this pipeline, rather than executing it.

Commands executed from app: `.venv/Scripts/python.exe -m pytest tests/test_intent_direct_audit.py tests/test_intent_testbook.py tests/test_natural_names.py tests/test_jarvis.py tests/test_audit_resilience.py -q --tb=short --junitxml=artifacts/jarvis-audit/modules/03-intent-direct/cases-and-contracts.xml` (**98 PASS**); full `-m pytest tests -q --tb=short --junitxml=artifacts/jarvis-audit/modules/03-intent-direct/full-regression.xml` (**1942 PASS**, 485.17 seconds). [Targeted XML](cases-and-contracts.xml), [full XML](full-regression.xml).

Owned fixture journey: real Engine routes Chrome to real Actions open handling with fake Popen and fake foreground captures; exactly one executable dispatch. Negated input produces zero requests. Compound open/type preserves order and explicit target. No live app/account/desktop writes, personal deletes or dependency installs. Launcher `--check` readiness is recorded privately at `.jarvis-runtime/jarvis-audit/module03-pre/readiness-final.json`; readiness is not live feature acceptance.

Warm mixed-corpus per-phrase P95 3.0279 → 1.5765 ms. Cold import plus 12-phrase batch P95 801.77 → 818.25 ms. [CSV](benchmarks.csv), [raw corpus/routes](benchmark-summary.json). Sampling is model-free, RSS is not peak, audio/TTFT/GPU metrics N/A. Warm benefit comes partly from eliminating formerly rejected slow routes; it does not prove universal startup or speech speedup.

Next exact module case: **JRV-03-005**. Global unfinished cognition cases remain in the top-level ledger; moving to Prompt 03 does not mark them complete.
