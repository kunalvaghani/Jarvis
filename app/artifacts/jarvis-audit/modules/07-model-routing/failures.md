# Failures and disposition — 2026-10-15 IST

Reproduced 11/12 initial regression variants failing: five bare key formats qualified as public; exhausted quota waited for metadata; mixed-case Retry-After used the default delay; zero/malformed usage refunded reservations; unsafe model metadata persisted. A separate real isolated SQLite readback showed bare keys saved in new conversation pairs. All now have executed assertions. These baseline failures are retained in reproduced-failures.xml and memory-reproduced.xml.

Additional hardened boundaries: response IDs and estimate metadata cannot store credential-shaped/arbitrary objects; route/reservation UUID correlation and allowed metadata fields are asserted. Existing ledger uncertainty, partial-stream non-replay and offline/manual preferences remain tested.

Harness errors retained in catalog-first.xml: 20 rounds exceeded the real fixture minute budget, a GPU test class name was incorrect, and a config helper duplicated a keyword. Corrected the harness (fake minute clock, real class, dictionary override); no product quota was increased. collection-error.xml records a nonexistent memory test filename; corrected invocation executes real assertions. Reporter import/paths and actual commands are reproducible, no collection result counts as a pass.

Unresolved live acceptance: no Groq inference/account mutation authorized by this audit, live_tests_enabled=false, entitlement/billing not independently verified, no org-peer spending visibility, no live web/GUI/microphone-to-speaker journey or shared STT/F5 contention run. New regex coverage is not universal secret detection. Existing historical private records were preserved rather than silently edited. Ollama upgrade/Python lifecycle work remains separately unvalidated.
