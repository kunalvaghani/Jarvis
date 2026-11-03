# Control A/B comparison

Arm A (legacy control, brain shadow) from 2026-11-03T03:32:04; arm B (agent-desktop + agent-browser, brain on) from 2026-11-03T05:14:56. Same scenarios and shuffle seed, same machine, independent oracles. Intervals are 95%; a difference whose interval spans 0 is not a claim.

## Overall

| Metric | Legacy (A) | New (B) |
|---|---|---|
| Verified success | 31/48 (65%, CI 50%–77%) | 48/48 (100%, CI 93%–100%) |
| End-to-end p50 / p95 / mean (s) | 40.7 / 410.2 / 117.1 | 19.5 / 36.6 / 18.0 |
| First action p50 (s) | 25.5 | 0.3 |
| Model calls per task (mean) | 2.83 | 0.25 |
| Foreground changes (focus steals) | 45 | 30 |
| Wasted retries | 2 | 0 |
| Peak RAM / VRAM (MB) | 1097 / 2408 | 970 / 2362 |

Success difference B − A: **+35%** (95% CI +21% to +50%).
Median latency difference B − A: **-21.2 s** (95% CI -75.6 to -4.1 s).

## By category

| Category | A success | B success | Δ (95% CI) | A p50 s | B p50 s | Rule |
|---|---|---|---|---|---|---|
| native | 6/15 | 15/15 | +60% (+28%…+80%) | 63.3 | 8.2 | switch |
| shell | 4/12 | 12/12 | +67% (+30%…+86%) | 143.3 | 11.6 | switch |
| hard | 3/3 | 3/3 | +0% (-56%…+56%) | 1.3 | 1.7 | stay legacy |
| concurrency | 3/3 | 3/3 | +0% (-56%…+56%) | 128.3 | 33.4 | stay legacy |
| blender | 3/3 | 3/3 | +0% (-56%…+56%) | 17.0 | 39.9 | stay legacy |
| web reading | 12/12 | 12/12 | +0% (-24%…+24%) | 25.6 | 27.8 | switch |

## Per scenario

| Case | A | A s | B | B s | B problem |
|---|---|---|---|---|---|
| C01 | 0/3 | 164.2 | 3/3 | 35.3 |  |
| C03 | 3/3 | 2.4 | 3/3 | 12.7 |  |
| C05 | 0/3 | 374.5 | 3/3 | 0.1 |  |
| C06 | 3/3 | 409.9 | 3/3 | 0.1 |  |
| C08 | 0/3 | 1.5 | 3/3 | 8.2 |  |
| C14 | 3/3 | 76.3 | 3/3 | 3.9 |  |
| C17 | 1/3 | 98.0 | 3/3 | 0.5 |  |
| C18 | 0/3 | 261.3 | 3/3 | 19.2 |  |
| C19 | 0/3 | 296.0 | 3/3 | 20.0 |  |
| C38 | 3/3 | 1.3 | 3/3 | 1.7 |  |
| C42 | 3/3 | 128.3 | 3/3 | 33.4 |  |
| D12 | 3/3 | 11.9 | 3/3 | 22.9 |  |
| D14 | 3/3 | 25.7 | 3/3 | 34.9 |  |
| H2 | 3/3 | 17.0 | 3/3 | 39.9 |  |
| S1 | 3/3 | 26.5 | 3/3 | 27.4 |  |
| S1c | 3/3 | 26.2 | 3/3 | 34.6 |  |

Go/no-go rule (master prompt): the new backend becomes default for a category only if its verified success is at least legacy's, there are zero unauthorized side effects or double executions, and its latency is not significantly worse. "switch" above applies that rule to this round only; small counts need the repeat runs before any default changes.

## Run notes

- Legacy arm: 2026-11-03T03:32:04 to 2026-11-03T05:07:14 UTC. New arm: 2026-11-03T05:14:56 to 2026-11-03T05:30:47 UTC. 16 scenarios x 3 rounds, shuffle seed 303, Phase 1 flags on in both arms.
- An earlier new-arm run (2026-11-03T03:13:23 to 2026-11-03T03:32:04) scored 36/48: brain launches were refused because the multi-agent cursor session needs an agent id on every desktop command, and the C18 oracle read window rects DPI-unaware (800x600 read as 640x480 at 125% scaling). Both fixed in 9052909; the new arm was rerun in full rather than patched.
- "stay legacy" on hard / concurrency / blender is the rule's verdict on 3 runs per arm (tied success, interval too wide), not a measured regression, except Blender: its median is slower (17.0 s legacy vs 39.9 s new) and needs a look before switching.
- Not yet covered: Gmail / Drive / Docs / Sheets (C22, C28-C34) wait for remote debugging to be enabled in Chrome Person 1.
