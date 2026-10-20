# Remaining blockers and review risks

P36-R1: completed_verified telemetry now rejects explicit step refutation, but still relies on host task/checkpoint history for other cases. Direct historical/host event insertion and model/self-asserted or stale goal_verified provenance need uniform independent verifier identity/version binding. Global TaskState/UI completion is not repaired by a counter fix (case 014 remains BLOCKED).

P36-R2: no universal trace across voice/STT/router/model/Verify/UI/speech and background workers; no ten warm commands, cold first tokens, physical voice-under-training or 100-action process leak alert. Cannot turn helper timings into throughput or responsiveness claims.

P36-R3: caps/locks are per process; no cross-process logging/retention/backpressure/crash-fsync stress. Status flags exist but every UI/dashboard consumer has not been audited. Old raw cloud/skill logs remain local and require an explicitly reviewed migration/export policy; do not silently delete them. All-sink privacy/case 024 remains blocked.

P36-R4: original raw N=500 samples unavailable (aggregate/code present); fresh samples are separate. No real matched API/UIA/GUI or actual accuracy/p95 tradeoff or loss/heldout training experiment. CI is a normal approximation for paired mean of serial synthetic samples, not population/median/p95 certification.

Initial Hermes baseline failure is a deterministic isolated-data issue, not a flake. Final wrapper reads verified existing install metadata; final assertion is not waived. Skipped physical/runtime checks remain explicit. Prior P31–P35 release gates remain in cumulative handoff. No final executed regression failure may be called healthy.
