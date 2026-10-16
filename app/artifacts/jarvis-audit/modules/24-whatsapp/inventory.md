# Prompt24 — WhatsApp audit, 2026-10-16 IST

**PARTIAL: 14 catalog PASS /18 BLOCKED.** These are fixture proofs, not production/live-account acceptance.

All sends/keys/UIA/LLM transports use authored fakes, isolated journals and one owned child exiting23. No personal chat read, message/call/file send, delete, account write, native window activation, credential read/setup, installation, service restart or heavyweight inference. The full suite includes pre-existing owned headless browser/local-server fixtures. No new screenshot: existing sample card artwork remains labelled as rendered preview.

| Claim | Source / actual path | Evidence / limitation |
| --- | --- | --- |
| Dispatch | commands.parse→whatsapp.parse_command→Actions.execute | whatsapp_send/reply preserved; bounded request_data runs before TaskState/window activity |
| Preview and approval | approve_and_send / auto_reply→Prompt / ask; Actions.submit→answer_prompt | Exact recipient/text card, edits then fresh approval; expired/boolean answers refused, resolver serialized, cancellation wins wait return |
| Identity | match_contacts→find_contact→open_row→is_open | Discovery stays phonetic; write identity now NFC/casefold literal, no fuzzy alias; ambiguous repeated names fail closed, no stable ID |
| Typing/send | send_approved_text→type_draft→press_send | Recheck empty compose/recipient/focus, exact normalized text, Enter once, fresh status Sent/Delivered/Read; Pending is uncertain, no partial-draft deletion |
| Recovery | whatsapp_writes.text_send→TaskState.checkpoint | Hash-only journal before typing; text-send desktop lock; damaged/pending checkpoint refuses replay after actual child crash; successful new approved requests may repeat |
| Calls | Watcher.run→call_controls→handle_call→press | Fresh caller/kind and Stop checked; changed caller denied; outgoing-call flow and same-caller ring-instance identity absent |
| Local composition | draft→knowledge_worker.chat→127.0.0.1:11434 | Structured untrusted history, system instruction stays separate, client closes; no complete transcript/cloud privacy oracle |
| Other apps | messengers.send / send_telegram | Telegram optional; other named apps honestly refuse. Signed-in Telegram and file-attachment paths are not covered by new text journal |
| Watcher/config | config.whatsapp→Actions.start_whatsapp_watch | enabled/watch_messages/auto_draft_replies/watch_calls true; groups/muted false,max5,poll2s; shared prompts, config typing and native contention remain open |
| Runtime contract | existing manifest jarvis.whatsapp and dependency group | No new long-running service/dependency; launcher readiness passed; Start/Stop/bootstrap/recovery source unchanged |

## Unresolved catalog contracts

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

[Complete report](../../final-report.md) · [Executed assertions](cases-and-contracts.xml) · [Source diff](source.patch)
