# Ultron memory adaptation

Source: https://github.com/modelscope/ultron
Pinned revision: `801c16233a0c83cab7b7de9467513c5e0f44bf2c`.
Copyright (c) ModelScope Contributors. All rights reserved.
License: Apache-2.0, full text in `integrations/ULTRON-LICENSE`.

`jarvis/experience.py` adapts `_calculate_hotness` and the weighted decay
expression in `ultron/services/memory/memory_service.py`. Changes: standard
library only, UTC/Unix timestamps, invalid timestamp handling, fixed local
weights, and read-only lexical task recall instead of hosted embeddings.
The downloaded original modules are retained in `integrations/ultron-*.py`
for comparison; Jarvis does not import or execute them.

Jarvis now ranks UI suggestions using success count and time decay. A selection
must still match exactly one currently visible control in the same context and
pass the existing confirmation and fresh observation checks.

The initial desktop planner receives up to three deduplicated summaries from
the existing bounded task history. Only completed tasks with verified
checkpoints and no uncertain later action qualify. Summaries exclude executable
plans and file contents. The planner treats summaries as untrusted background;
the current goal, screen, validation, and approval rules remain authoritative.
Recall is lexical, not semantic, and lasts only as long as the existing 20-task
history. It does not train models, generate executable skills, upload data, or
add any service. No additional requirements are needed. Startup, stop, source
snapshots and silent recovery continue through the existing launcher.

Validation: `python -m unittest discover -s tests` and
`python -m jarvis.launcher --check` using Jarvis's main virtual environment.
On 2026-09-26, all 261 regression tests passed, including the existing recovery
fault, shutdown, and retry-backoff tests. Launcher check reported `ready` with
no missing dependencies. No new recovery paths or services were introduced.
