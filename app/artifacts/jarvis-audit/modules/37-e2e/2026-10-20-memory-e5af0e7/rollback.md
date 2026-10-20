# Rollback and reproduction
Test-only proposal; omit new test if rejected. Preserve old evidence and user configuration. No production/runtime rollback needed.
From pinned app, set JARVIS_E2E_DEPENDENCY_APP to original installed app, JARVIS_E2E_EVIDENCE_DIR to a new owned output directory; run existing main Python `-m pytest tests/test_prompt37_reasoning_repeat.py -q`. No downloads. Memory tests skip explicitly if skills interpreter is absent.
The [final selection](boundary-selection.json) and [runner](run_suite.py) specify neighboring test IDs. Prior full relevant run is reusable only after matching source-hashes.json; it predates this test and is not a newly rerun full suite.
