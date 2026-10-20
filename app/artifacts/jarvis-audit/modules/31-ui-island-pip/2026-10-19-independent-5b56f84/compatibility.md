# Prompt 31 audit — 2026-10-19 IST

Windows Python 3.10 runtime/version provenance is in baseline.json. The current app is checked out without its ignored per-feature environments/models. `python -m jarvis.launcher --check` ran both restricted and unrestricted. The unrestricted result is repair_required: isolated .venv/.venv-brain, Whisper/F5/Laya/Harness assets are missing. Docker 29.8.2, local Ollama and configured Ollama models were available to the unrestricted probe; the restricted probe could not reach them. No installs, service starts or model downloads were performed.

Existing Tk fixtures exercised disposable application widgets, not the user's Jarvis UI. One combined-suite Tk initialization failed but passed alone. Native 200-percent scaling, secure desktop, real speech, GPU training contention and UI worker crash acceptance remain BLOCKED/NOT RUN. Full repository regression is NOT RUN after the mandatory P1 stop gate. No Python/dependency migration is implied.
