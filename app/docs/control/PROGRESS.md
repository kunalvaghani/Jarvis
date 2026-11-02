# Control migration progress (agent-desktop / agent-browser)

Branch `control/agent-desktop-migration`, based on the brain branch. On 2026-11-02 the user asked to build now and run all live tests together with the brain afterwards. Runs and gates that need the live desktop are marked **live round**.

## Phase 0: understand (done, 2026-11-02)
- [x] Current control traced: [CURRENT_STATE.md](CURRENT_STATE.md)
- [x] Tools installed (pinned, checksummed); `status`, `--help` and the bundled skills read; contradictions noted (below)
- [x] [ADAPTER_PLAN.md](ADAPTER_PLAN.md): every legacy op has a replacement or "stays on fallback"
- [x] Preflight answers received (headed in benchmarks: yes; Chrome `Default` profile; all apps; real accounts allowed, drafts only; DND as the toggle; key in `secrets/`; not elevated)

Contradictions with the master prompt, and what was done instead:
- `--allowed-domains` cannot be combined with a Chrome profile; domains are guarded by Jarvis's URL policy instead.
- agent-browser errors have no delivery field; only proven pre-action errors count as not executed.
- Policy action names are protocol names (for example `evaluate`, not `eval`): the generated policy uses those.
- The standalone agent-browser exe ships no skills; they were read from the v0.41.1 tag on GitHub.
- The benchmark lives in the existing live suite (`benchmarks/live/control_cases.py`), not `tests/control_bench/`.

## Phase 1: benchmark and baseline
- [x] 44 scenarios with oracles (`python benchmarks/live/cases.py control`)
- [x] Gate 1 oracle validation: every oracle factory passes a known-good state and fails a known-bad state, and no scenario passes on an empty world (`tests/test_control_bench.py`; it caught a weak C08 oracle)
- [ ] **Live round:** legacy baseline, 5 warm and 2 cold runs per scenario, written to [BASELINE.md](BASELINE.md)

## Phase 2: agent-desktop PC backend
- [x] Runner with pydantic envelope models, error and disposition mapping, resolver, `AgentDesktopExecutor`, HeadedGate, fast paths, per-task traced sessions
- [x] Shadow executor with a read-only runner (tests prove no write command can run)
- [x] 31 unit tests from recorded envelopes covering every `error.code` and delivery branch, plus fault tests
- [ ] **Live round:** shadow across the suite; agreement and observe time

## Phase 3: agent-browser web backend
- [x] `AgentBrowserExecutor`, generated action policy, boundary enforcement, confirmations through the approval card, URL policy on final URLs, encrypted state key
- [x] Web shadow (isolated, read-only, test profile only); 15 unit tests including "boundaries and policy on every call" and "no state or keys tracked by git"
- [ ] **Live round:** shadow over the web scenarios

## Phase 4: A/B
- [ ] **Live round:** the same suite on the new backends; `COMPARISON.md` with Wilson and bootstrap intervals; per-category go or no-go; re-run with new defaults; rollback test; `FINAL_REPORT.md`

## Regression
- Before (brain branch, 2026-11-02): 5,062 passed, 39 known failures; see [reports/tests_before.txt](reports/tests_before.txt).
- After each control step: all control, fast-route and live-suite tests pass; mypy is clean on the new modules.
- After (control branch, 2026-11-02): **5,116 passed, 39 failed — exactly the 39 known failures, none new.**

## Combined live round, 2026-11-03 (brain on + agent-desktop + agent-browser + Laya on CPU + Phase 1 flags)

All 16 scenarios in the set passed: 11 desktop, Blender H2, and web D12, D14, S1, S1c. These are single runs; the repeat runs and the A/B intervals are still to come. The pass results came from runs B6 to B9, after the fixes each run exposed.

| Scenario | Before (2026-11-02) | Now |
|---|---|---|
| C01 Notepad write and save | 407 s | 30 s (brain workflow) |
| C03 Calculator | 150–226 s, failed | 9.5 s |
| C05 rename / C06 new folder | failed / 522 s | instant (brain workflows) |
| C08 open then close Paint | failed | 7.8 s |
| C14 Start menu launch | failed | 3.3 s |
| C18 resize / C19 minimize and restore | failed | 18 s each (brain workflow) |
| C42 side by side | failed | 34.5 s |
| H2 Blender live build | n/a | 17 s |
| D12 / D14 / S1 / S1c web | failed | 24 / 36 / 33 / 37 s |

Root causes found:
- The Phase 1 flags were off by default (the user promoted them).
- Laya on the GPU squeezed the 9B planner onto the CPU (Laya now runs on the CPU).
- The Windows foreground lock blocked physical input (paths are now headless first).
- Hosted Store app window identity.
- Website questions were treated as chat.
- The page title was missing from agent-browser reads.
- Parser bugs.

Full regression after the round: 5,131 passed, the same 39 known failures.

Still open:
- Gmail, Drive, Docs and Sheets scenarios need the user's `chrome://inspect/#remote-debugging` switch.
- Multi-agent cursors and parallel window reads.
- Repeat runs and `COMPARISON.md`.
