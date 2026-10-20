# Rollback / reproduction

No implementation change to reverse. To reproduce: use the original installed main Python from this audit app directory, run the installed-dependency runner with test_prompt37_e2e_boundaries.py, test_task_state.py and test_task_recovery.py; run run_journeys.py in this packet; run python -m jarvis.launcher --check. No install step.

Review/apply prior source/test patches on claude only after preserving user work. Source revision must be newly committed and independently reverified; no merge/deployment requested. Retain every earlier audit original, uncertain-write checkpoint and cancelled demonstration state. No reset/clean or blind action replay.
