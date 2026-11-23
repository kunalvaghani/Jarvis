---
name: lab-units
description: Convert a finite scientific scalar with the reviewed isolated Pint worker, preserving units, provenance and unknown values.
tools: []
---

Requires lab.enabled and lab.sim. Example: "lab convert 180 degree to radian".
The existing brain compiles the request to a typed unit adapter, independent verifier and report.
Pint lives in .venv-discovery-units, with versions and hashes pinned in requirements/discovery-units.txt.
Do not install or upgrade it from a request without a concrete approved install plan.
Reject incompatible dimensions, non-finite numbers, missing provenance and invalid units.
Unknown input values remain null through conversion; never fill them with a guessed mass or zero.
Results are MODEL_CONSISTENT dimensional calculations, not measured physical evidence.
Only the owned units_worker.py is executable. This environment is not a sandbox for arbitrary downloaded or generated Python.
