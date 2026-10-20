# Execution and reproduction

Source pinned at `0e3ad4706b5120e5d0479d34333e5faa7b0931b5`; original existing interpreter `D:/Kunals GitHub Repo/Jarvis/app/.venv/Scripts/python.exe`. All commands ran from this audit worktree's `app/` directory. No package installation or live account action.

The full relevant regression used all 26 files in `selected-suites.txt`, with the read-only interpreter routing in `run_installed_dependencies.py`, `-q`, and `--junitxml=<this run>/relevant-regression.xml`; stdout/stderr are in `relevant-regression.txt`. Use a new output directory for reproduction, not this historical packet:

```powershell
$auditSuites = Get-Content artifacts/jarvis-audit/modules/31-ui-island-pip/2026-10-19-independent-0e3ad47/selected-suites.txt
python artifacts/jarvis-audit/modules/31-ui-island-pip/2026-10-19-independent-0e3ad47/run_installed_dependencies.py @auditSuites -q
```

Separate runs:

- Approval: the two checked-in Prompt 31 files, the unchanged original `2026-10-19-independent-5b56f84/test_approval_binding.py`, and this run's adapted `test_receipt_replay.py`; 36 executions, with duplicate scenarios explicitly retained.
- Four component probes: this run's `test_catalog_components.py`.
- Two offscreen real-Tk requester/card/decision cases: this run's `test_widget_journey.py`.
- Original native exporter: `scripts/verification/verify_island_desk.py --output <this run>/native-island.json`. It failed on a stale unbound denial call; `native-island.txt` is preserved.
- Native rerun: this run's `verify_native_current_protocol.py --output <this run>/native-current-protocol/native-island.json`. Only the denial call is bound to the displayed token; original assertions remain. The temporary `PYTHONPATH` was the audit `app/` directory.
- Read-only launcher/local service probe: `python -m jarvis.launcher --check`, with stdout/stderr preserved in `launcher-check.txt`.
- `collect.py` builds fresh reports, prior/source hashes, the fixed-commit paired card benchmark and synthetic five-producer event profile. It does not mutate application or previous audit sources.

Readiness probes, simulated providers, owned native widgets, local containers and actual document readback retain their separate scopes. No microphone recording, private desktop capture or live voice/account journey is implied.
