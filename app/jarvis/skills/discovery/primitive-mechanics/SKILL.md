---
name: primitive-mechanics
description: Inspect the mechanics schema through discovery_call help, then run bounded CPU MuJoCo primitive rigid-body models with explicit SI mass, topology and assumptions.
---

Call the existing planner's `discovery_call` with `operation=help`, `topic=mechanics` and an expected result to inspect MechanicsCase.
Then call it with `operation=run`, `command=lab simulate mechanics "{request}"`, the structured `request` object, and an expected result.
The skill name identifies this procedure; the native function is `discovery_call`.
Resolve each source and unknown property first. Do not describe proposed values as measurements.
Supported bodies are spheres, boxes (half extents), and capsules, with fixed/free/hinge/slide joints.
Body and shape positions are distinct: the shape offset determines mass distribution about the joint.
Contact, material strength, aerodynamics, actuator models, external meshes and arbitrary XML/plugins are unavailable.
Actual numeric trajectories and editable MJCF are retained in the existing Journal.
Check the independent verifier and quote evidence limitations; a simulation is conditional, never physical proof.
Only the owned fixed worker may execute. The isolated environment is not a sandbox for generated code.
The explicit global 50-call grant is nonrefundable; do not reset it or change global budgets.
