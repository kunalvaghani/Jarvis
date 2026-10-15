# Maintenance commands

`python -m scripts.verification.phase2_gpu_voice_probe` runs bounded synthetic
local model/synthesis checks and samples GPU memory. It writes `phase2-live-evidence.json`
and `phase2-vram-trace.csv` under `artifacts/`, uses existing weights without downloads,
and stops only an Ollama server it owns. See the [Phase 2 guide](../docs/phase2-gpu-voice-ui.md)
for fixture/live gates, socket restrictions and unmet latency targets.

Run Python commands from the application directory with `python -m
scripts.<group>.<command>`, using the environment documented for that command.
Packages contain setup, catalog, models, training, skills, integrations, audit,
verification and preview programs. See the [complete folder map](../docs/project-structure.md).

For ordinary regression/readiness checks, use `python -m unittest discover -s
tests -q` and `python -m jarvis.launcher --check`. Individual verification scripts
retain their original fixture, local-inference, UI or live-account behavior; they
are not one blanket smoke-test command.
