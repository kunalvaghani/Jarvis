---
name: pendulum-lab
description: Run the bounded ideal pendulum model, inspect solver assumptions, and create verified native scenes through the existing Discovery brain.
---

Use only with `lab.enabled` and `lab.sim` enabled in an explicitly approved scope. Shipped flags stay off.

Commands from the app folder:

- `lab simulate pendulum "examples/discovery/pendulum.json"`
- `lab build pendulum "examples/discovery/pendulum.json"`
- `lab build pendulum "examples/discovery/pendulum.json" length delta 0.5 m`

Supply all eight physical model fields explicitly. Supported design controls are length/radius/mass with set/delta and Pint-validated units. Source files and gravity/scenario stay fixed. Constraints, finite sampling and the existing Journal budget apply. Only explicitly authorized known free-local tools receive the 50-attempt cap; never infer permission for a paid service or a new package.

Route through Actions and the existing brain. Native creation requires the existing approval gate and writes a new owned experiment folder. After an uncertain write, inspect goal/artifact state; never replay automatically. Solver numeric checks precede native creation; fresh Blender readback precedes verified artifact/component persistence. Use generated component-project.json with existing C1 inspect/plan commands.

Scientific scope: uniform solid spherical bob, ideal massless connector, rigid revolute motion under constant gravity, optional viscous damping. SciPy supplies the numeric trajectory. Blender displays it with a kinematic bob and native hinge; this does not validate Bullet dynamics, materials, fatigue, a manufactured mechanism, or general multiphysics. Always show SIMULATION_PASSED_WITH_ASSUMPTIONS and physical_validation=false.

Blender uses the existing discovered executable, fixed owned template, background factory startup, offline mode and disabled autoexec. This is not an arbitrary-code sandbox. Never load untrusted downloaded assets/scripts through this adapter. No installs, global config edits, GUI/server startup, GPU or paid fallback.
