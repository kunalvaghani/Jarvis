---
name: bounded-optimization
description: Run an explicitly bounded ideal-pendulum length study through the existing brain, durable queue and scientific evidence checks.
---

Requires lab.enabled and lab.sim in an authorized scope; shipped flags remain false.

From app/, use `lab optimize "examples/discovery/pendulum-study.json"`. Retain the returned study ID. Use `lab optimize queue "<study-id>"` to schedule all remaining trials in the existing queue. Without an active queue, use `lab optimize step "<study-id>"` for one bounded trial. Inspect with `lab optimize status "<study-id>"`; pause/resume/cancel are explicit commands with the same quoted ID.

The JSON declares every baseline physical value, permitted length interval, target period, tolerance, maximum gravitational moment and CPU budget. Only length varies. Preserve the source file; changed source or solver hashes block resume. Candidate order and objective scores are deterministic code, never model output. Numeric success is separate from constraint feasibility. Retain rejected, blocked and uncertain attempts.

An expired interrupted trial is charged and skipped, never replayed. Completed trials retain their content-addressed results across process restarts. Resume only explicitly paused studies; cancelled, completed and budget-stopped studies cannot reopen. Respect the shared free-local trial ledger; no reset, install, paid fallback or global activation.

Always disclose SIMULATION_PASSED_WITH_ASSUMPTIONS and physical_validation=false. The gravity-moment limit does not establish structural strength, actuator sizing or physical safety. This bounded grid search does not provide general autonomous invention, Optuna, program evolution or multiphysics.
