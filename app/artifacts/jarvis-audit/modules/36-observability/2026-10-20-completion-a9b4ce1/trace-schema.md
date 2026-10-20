# Trace schema and trust

Agent event version 1 retains at, event, call_id and allowlisted tool/metadata; adds monotonic_ns (integer nanoseconds) and clock_id (opaque process clock domain). task_id is optional host TaskState UUID captured in registry call context, never copied from model metadata. Call ID correlates tool.started/completed/failed/outcome; tool.completed means dispatch returned, not goal verified. Durations use perf_counter or same-clock monotonic differences; do not subtract wall dates or mix clock domains across restarts.

Cloud decision version 2: wall time, monotonic clock fields, optional scoped task_id, problem_id_hash and categorical decision. Sent records add payload_bytes/sha256 only. No payload, raw reasons, advice, credential, filename or source content in these new rows. Skill event metadata includes bounded integer version/evidence_count and categorical cause/reason. Raw historical evidence is sanitized on metrics read, not erased from storage.

Trace readback is five actual registry calls / actual TaskState with mocked read dispatch and no file access by tools. It does not cover STT/cleanup/model/DAG/Verify/memory/UI/speech/background request IDs end-to-end. Existing outcome authority and global UI truth remain separate release gates. Logging loss cannot grant approval or verification; missing records may block promotion/diagnosis.
