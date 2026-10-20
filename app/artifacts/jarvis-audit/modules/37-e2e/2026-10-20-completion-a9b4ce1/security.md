# Security boundary

Tests use disposable local workbooks/SQLite/TaskState files, fake window modules/hooks, simulated Brain send and recording-fake cloud provider. Actual postconditions include separate worker workbook readback, durable paused status/speech event, restart blocker, zero real sends/requests and fake hook stop call count. No desktop recording or real input was performed.

Rechecked cancellation and selected PID after consent before observing; denial/PID swap produces zero fake Desktop calls. Truthy non-booleans cannot promote. Terminal bad session status cannot promote even with literal True. Cleanup exceptions are persisted failed, propagated, and retain an owned reference for retry. This is not proof against HWND/PID reuse, all native races, arbitrary semantic injection or forged caller replay evidence. P35/P36 privacy/identity guards rerun; their unresolved independent provenance/final-verifier gates persist.

Logs normalized for local roots; original and saved hashes retained. Workflow journals record component names and synthetic readbacks only. No credentials/private desktop/audio exported. Original configuration untouched. No installs or system/service changes to make readiness green.
