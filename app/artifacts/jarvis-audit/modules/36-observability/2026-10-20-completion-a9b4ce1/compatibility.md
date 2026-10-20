# Compatibility and operational limits

No dependency, model, launcher/runtime-manifest/config change. Version-1 agent readers tolerate added clock/task fields; cloud metadata rows explicitly version 2. Three regression assertions now expect metadata counts/digests and clock fields instead of raw text/payload. Existing approvals, actual fake outbound payload, counter idempotency and dispatch validation remain asserted.

Logging unavailable/capped: functionality proceeds once under the same policy and approval checks with diagnosis degraded; no replay. Missing outcomes cannot establish verification or trusted promotion. No automatic log deletion/rotation. Old raw telemetry is not migrated or claimed clean. Invalid legacy event JSON yields categorical metrics and invalid_evidence_count rather than a crash.

Hermes/skills roots read from original install where explicitly routed, not copied. Isolated launcher --check remains repair_required (missing local env/assets; unavailable Docker/Ollama endpoints). Physical/runtime skip reasons retained. Whole original environment was not recreated. No UI images applicable.
