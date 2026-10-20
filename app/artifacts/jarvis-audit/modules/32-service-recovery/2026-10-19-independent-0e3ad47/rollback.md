# Prompt 32 independent audit — 2026-10-19 IST

No application repair is installed, so no production rollback. Keep this dated packet, originals and original config. Source pin 0e3ad4706b5120e5d0479d34333e5faa7b0931b5; no fix SHA. Do not reset claude or blindly apply patches. From app/, using the existing original Python interpreter:
```powershell
python -m pytest tests/test_recovery.py tests/test_launcher_readiness.py tests/test_runtime_health.py tests/test_task_state.py tests/test_task_recovery.py tests/test_model_recovery.py tests/test_everyday_runtime.py tests/test_phase01_baseline.py -q
python -m pytest artifacts/jarvis-audit/modules/32-service-recovery/2026-10-19-independent-0e3ad47/test_recovery_boundaries.py -q
python -m jarvis.launcher --check
```
Boundary tests are expected to fail on the pinned source. Run future reproductions from a fresh copied packet and new XML/output directory so process traces do not overwrite this final trace. Test process cleanup is explicit in finally blocks and limited to spawned Job/Popen handles; never substitute a name-based cleanup command.
