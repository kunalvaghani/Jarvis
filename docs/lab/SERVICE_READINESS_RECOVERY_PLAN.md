# Existing-service start scope — 5 November 2026 IST

Read-only checks observed Ollama localhost11434 refusing connections (WinError10061) and Docker Desktop's Linux engine pipe absent. Earlier ready evidence is historical. Neither service was deliberately restarted by this recovery work. The reason they became unavailable is unknown.

Verified installed executable paths and signatures:

- `C:/Users/kunal/AppData/Local/Programs/Ollama/ollama.exe` —27,871,112 bytes, valid Authenticode signature.
- `C:/Program Files/Docker/Docker/Docker Desktop.exe` —15,699,376 bytes, valid Authenticode signature.

Proposed bounded action, only if approved and after the current regression process finishes:

1. Recheck existing service status; do not launch a duplicate if already available.
2. Start existing Docker Desktop once, hidden, preserving existing engine/WSL/resource/settings. No image pulls or new containers.
3. Start the existing Ollama executable once with `serve`, hidden, using the existing Jarvis runtime environment and a process-only `OLLAMA_HOST=127.0.0.1:11434`. Preserve existing model paths/settings. No persistent environment changes, model pull/load or inference.
4. Poll read-only Docker info and Ollama version/model metadata within120 seconds total, then run the existing read-only launcher readiness check. Retain failures instead of retrying indefinitely.

No installs, downloads, paid calls, C3 proposals, account writes, drivers, models, daemon kills, engine reconfiguration, WSL changes or shipped Lab flag activation. Existing running/shared processes are not terminated. Starting these services does not approve pending Chrono preparation/installation or expand any solver/model quota.

The application instructions require respecting deliberate stops; whether these services were intentionally closed is unknown. Ask the user before this start. Leave them untouched unless approved.
