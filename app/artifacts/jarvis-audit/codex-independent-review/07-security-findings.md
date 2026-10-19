# Independent Jarvis audit checkpoint — 2026-10-19 IST

Pinned `claude`: `36fbf3ce925080f7f54afa87eaf1d9b88414142d`. Isolated branch `codex-review`. This package reports actual execution, not a certification of the entire assistant.

IR-001 is a local recording/privacy defect: rejecting a clicked password element did not screen the separate before/after state snapshot. Reused is_password now excludes true and unknown privacy states from text/toggle observations. Synthetic public text remains observable. Window titles and arbitrary non-password accessible names can still contain personal information: this change does not claim comprehensive PII removal.

IR-002 is a resource-safety defect: corrupt/unreadable state must defer optional training. The trainer now bounds the read, calls the scheduler's validate_state, distinguishes FileNotFoundError from unknown state and checks admission before dependency imports/output writes. Missing state retains idle compatibility; existing live/stale holder tests remain.

IR-003 preserves recipe hashes across LF/CRLF conversion; edited content still fails. IR-004 enables long paths per owned lab Git command without changing global configuration. reference-before.xml and reference-verified.xml preserve the pre-repair failures; lab-final.xml verifies the lab repair.

Cloud adversarial tests use fake providers and synthetic paths/tokens. No sensitive test strings were sent to a cloud model. MCP hostile code runs in reviewed isolated containers, not host execution. Evolution candidates use disposable Git repositories. No automatic deployment or merger is performed.

Unverified security scope: physical UI disclosure, all generated-tool privilege boundaries under concurrency, training/foreground race-free exclusion, and prompt injection through every live external service. Regex/static screens are not a general semantic privacy proof.
