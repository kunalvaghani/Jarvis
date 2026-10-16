# Failures and limits

Baseline17 PASS. Actual reproduction:10 FAIL/2 PASS/24 explicit skips, including absent cancellation API on press_send. The initial test import error was corrected before this reproduction. First fix iteration29 PASS/24 skips. A subsequent sandbox run failed9 temporary atomic-replacement/child fixtures (WinError5); the outside-sandbox isolated neighbors passed73/25, then106/17. Final focused77/17, independent supplement2/1. No failed assertion is removed from historical XML.

Fixed: expired/boolean/racing approval, unreadable-compose treated as empty, display-name collapse, stale target/draft/focus before Enter, false Pending success, unsafe partial-draft deletion, different-caller approval reuse, malformed public input and missing accessibility dependency. Durable text journal adds crash/timeout refusal; earlier implementation had no persistent boundary.

- **JRV-24-001 BLOCKED:** Read/check commands route into reply/draft flows; an independently scoped read-only friend lookup is not proved.
- **JRV-24-004 BLOCKED:** Duplicate display names now fail closed and ask for a unique saved name; UIA rows expose no stable contact/account ID for a meaningful disambiguation choice.
- **JRV-24-006 BLOCKED:** Minimized-window restoration and correct native foreground need an explicitly authorized owned UI fixture; no live window was focused.
- **JRV-24-007 BLOCKED:** Incoming-call watcher and composing task lack a complete draft-preserving arbitration protocol.
- **JRV-24-008 BLOCKED:** Group detection is heuristic; exact group membership/recipients are not included in the send approval.
- **JRV-24-010 BLOCKED:** No dedicated delete-chat workflow; generic planner deletion approval/non-action proof is absent.
- **JRV-24-011 BLOCKED:** Outgoing calls are not implemented here. Incoming-call replacement/Stop guards passed but cannot prove outgoing-call cancellation.
- **JRV-24-012 BLOCKED:** Fresh recipient/compose checks passed; row selection still retains a UIA element across search/choice, and full native UI-redesign re-grounding is unproved.
- **JRV-24-017 BLOCKED:** Text journal serializes sends, but no complete five-request x20 search/approval/window workflow proof; shared prompt stack and watcher remain potential contention boundaries.
- **JRV-24-018 BLOCKED:** Cancellation after answered approval and before Enter passed; complete TaskState cancellation during readback remains unproved.
- **JRV-24-021 BLOCKED:** Drafting uses local Ollama and journal omits plaintext, but cards/transcripts include private text. Complete cloud/telemetry/cache secrecy oracle absent.
- **JRV-24-022 BLOCKED:** Unicode/quotes and a >500-character body preview passed; long contact/title/path journey lacks executed proof (contact admission caps at200).
- **JRV-24-025 BLOCKED:** No complete RAM/GPU-pressure admission plus core-command responsiveness fixture; no heavyweight model test ran.
- **JRV-24-026 BLOCKED:** Uncertain identical text sends refuse replay; a new explicitly approved request can repeat a completed send. Event-ID dedupe, attachments and calls lack a common durable protocol.
- **JRV-24-027 BLOCKED:** Equivalent normalization CPU/tracemalloc A/B only; not five cold processes plus20 complete UI requests with RSS/VRAM and audio latency.
- **JRV-24-029 BLOCKED:** Public request flags/schema validated; watcher config still lacks complete typed enum/range validation with diagnostics.
- **JRV-24-030 BLOCKED:** Text disconnect/crash checkpoint proved; complete watcher/COM worker disconnect recovery with task provenance is unproved.
- **JRV-24-032 BLOCKED:** Hash-only text journals and readback fixtures passed; cross-flow correlation, exception and transcript redaction are incomplete.
