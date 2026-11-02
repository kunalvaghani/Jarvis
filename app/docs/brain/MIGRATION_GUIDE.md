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

## Phase status

| Phase | Mode it may use | Status |
|---|---|---|
| 0 Audit and baseline | `off` only | in progress (2026-11-02) |
| 1 Capability registry and graph | `off`, `shadow` | not started |
| 2 Signal bus and vertical slices | `shadow`, `act` for the slices only | not started |
| 3 Full orchestration | `shadow`, then `act` after the parity gate | not started |
| 4 Plasticity | inherits | not started |
| 5 Live neuron UI | inherits | not started |
