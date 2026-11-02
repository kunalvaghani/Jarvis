# Brain migration guide

How Jarvis moves from the legacy orchestrator to the neural brain ([ARCHITECTURE.md](ARCHITECTURE.md)), and how to go back at any time.

## The switch

| Setting | Values | Effect |
|---|---|---|
| `neural.mode` in `config/config.json` | `off` (shipped), `shadow`, `act` | `off`: legacy only. `shadow`: legacy acts; the brain only plans and logs what it would have done. `act`: the brain acts. (`suggest` reads as `shadow`; anything malformed reads as `off`.) |
| `JARVIS_BRAIN_MODE` environment variable | `off`, `shadow`, `on` | Overrides the config when set to one of these values. |

The current value is read through `jarvis.neural.brain_mode(config)`.

## Rollback (one step)

Any one of these restores legacy behaviour:

1. Set the environment variable `JARVIS_BRAIN_MODE=off` and restart Jarvis (`Stop Jarvis.cmd`, then `Start Jarvis.cmd`). It wins over the config.
2. Or set `"neural": {"mode": "off"}` in `config/config.json` and restart.

The legacy orchestrator (`Actions` → `Brain` planner → `ToolRegistry`) stays in place and unchanged until `GO_NO_GO.md` records parity. The brain never deletes or rewrites legacy modules; it wraps them with adapters.

## Learning switch

`neural.learning` in `config/config.json` is `shadow` when absent. In `shadow`, verified outcomes are recorded but routing ignores them. `on` lets them reorder eligible routes. `off` rolls back to retrieval order and priors. Eligibility is never learned in any mode.

## Brain tools

`python -m jarvis.neural status | rebuild | route "<request>" | export [folder] | viewer | replay | consolidate | proposals | approve <id>`. The journal lives at `.jarvis-runtime/brain/journal.sqlite3`; the key `neural.journal` overrides it. To reset the brain's memory, stop Jarvis and move that file away. The legacy path does not use it.

## Phase status

| Phase | Mode it may use | Status |
|---|---|---|
| 0 Audit and baseline | `off` only | done (2026-11-02), partial baseline |
| 1 Capability registry and graph | `off`, `shadow` | implemented and unit-tested; live gate open |
| 2 Signal bus and vertical slices | `shadow`, `act` for the slices only | implemented and unit-tested; live gate open |
| 3 Full orchestration | `shadow`, then `act` after the parity gate | brain workflows plus legacy fallback; live gate open |
| 4 Plasticity | inherits; `neural.learning` stays `shadow` | implemented and unit-tested; live gate open |
| 5 Live neuron view | inherits | implemented and unit-tested; live gate open |
