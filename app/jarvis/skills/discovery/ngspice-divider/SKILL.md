---
name: ngspice-divider
description: Fixed ideal DC resistor-divider simulation through the reviewed Linux ngspice library and existing Jarvis sandbox.
tools: []
---

Use only after the operator-approved libraries, license review and bounded proof authorization are present. Do not install a solver, run host binaries or widen approval from this guide. The shipped Lab remains off.

The deterministic command is `lab simulate divider 10 V 1000 ohm 1000 ohm`: supply voltage, upper resistance, lower resistance, all explicitly in V/ohm. `jarvis.discovery.integration` compiles it onto the existing brain, sandbox adapter and independent verifier. Bounds are ±100 V and 1 to 1e9 ohm. The proof batch permits at most 20 attempted solver calls across restarts; failures consume slots.

Only an ideal voltage source and two linear resistors are modeled. Temperature, semiconductor behavior, wiring parasitics, power ratings and physical hardware are not modeled. No supplied SPICE syntax, model files, plugins, shell or arbitrary circuit is accepted. Numeric results come from actual ngspice vectors and must pass independent Ohm/Kirchhoff checks and an actual Journal solver receipt.

Store raw outputs, immutable Experiment/RunArtifact records and conditional evidence status in the existing Journal. A successful ideal-model test is SIMULATION_PASSED_WITH_ASSUMPTIONS; it is not physical validation. Qualification uses three canonical solver cases, followed by three independent verified brain goals. A fresh session must reuse the learned wrapper without rerunning qualification. Do not describe this operator-assisted proof as autonomous tool research or spoken/microphone acceptance.
