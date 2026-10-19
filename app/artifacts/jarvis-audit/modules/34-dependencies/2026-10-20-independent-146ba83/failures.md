# Confirmed blockers

## P34-001 — P1: startup repair installs packages without approval

launcher.run calls prepare_runtime automatically. A failed dependency import leads directly to runtime_command([project_python, -m, pip, --isolated, install, -r, requirements/runtime.txt]); no approval context is required. Independent JRV-34-012 uses a disposable complete-runtime fixture, injects a failed import, and intercepts every runtime command. Pip installation is attempted despite no approval and offline environment flags. unapproved-install-trace.json records the exact sanitized command sequence; zero real commands/installs executed. Existing-installed control issues only a read-only import check.

--isolated also affects pip environment configuration; the existing pip argument-parser readback in pip-offline-option-probe.json records effective no-index behavior without installing. Regardless of network availability, implicit environment mutation lacks the requested consent gate. Fix SHA NONE / APPLIES OPEN.

## P34-002 — P1: missing-model recovery starts download setup without approval/disk budget

ModelRecovery.repair starts download in a background thread. download opens an owned log and launches setup_brain --ollama-only without an approval or disk-space preflight. The setup script tries local cache restoration then calls Ollama /api/pull for missing tags; Whisper setup similarly streams model weights with no available-space budget check. The independent JRV-34-011 low-disk fixture intercepts Popen and injects one byte free; it still records one setup launch with no approval. No real setup child, provider call or weight download occurred. Deliberate shutdown control prevents launch. unapproved-model-trace.json is the exact intercepted evidence. The observed native effect is command admission, not a reproduced disk exhaustion. Fix SHA NONE / APPLIES OPEN.

STOP on two P1s under Prompt 34. No package upgrade or source repair by Codex. Existing positive regressions do not waive the new boundary failures.
