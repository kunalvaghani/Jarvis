# Reproductions, fixes and open blockers

Baseline `pytest tests/test_architecture_audit.py -q` reproduced2 failures ([baseline.xml](baseline.xml)): unknown root config was silent, and arbitrary lifecycle metadata retained fake private text/keys. The first authoring attempt also omitted the owned main.py fixture; [baseline-fixture-error.xml](baseline-fixture-error.xml) preserves that test mistake. No production claim is based on it.

Expanded run [first-expanded.xml](first-expanded.xml) reproduced missing config-byte bounds. Three additional failures were fixture-authoring mistakes: a nonexistent reviewed test class, missing per-task fixture directories, and a nonexistent cleanup hook. Fixtures were corrected to real entry points; no assertion was disabled.

Full regression later exposed a Pip fixture collision ([full-failed-buddy.xml](full-failed-buddy.xml)): an allowed random idle dance could coincide with media pause. The specific media-priority test now disables unrelated idle fidgets and additionally asserts playback state clears. Production animation is unchanged. Its corrected neighboring suite passed16 tests; the final full suite was rerun instead of silently accepting the failed assertion.

Repairs: shared bounded `load_config` on launcher and direct App paths; warnings contain counts only; fixed trace envelope and registered tool/categorical metadata labels; unreviewed metadata discarded. Non-finite/deep JSON returns typed opaque errors. Case17 ran100 owned requests in five-way batches without duplicate trace IDs/cross-task logs. Fake provider cases prove private material never reaches the captured cloud endpoint, and failure reasons do not contain the synthetic token.

Audit accounting also formerly overwrote a failed parameter variant with a later pass. Results now aggregate every variant with failure precedence, with an independent regression proving a FAIL stays in the remaining-ID list. No earlier pass counts are inflated by this fix.

Open architecture findings: missing guide, incomplete watchdog coverage, host ability isolation, two uncheckable venv dependency sets, unsupported main Python branch and all live features listed in inventory.md. They are not silently repaired by changing evidence labels.
