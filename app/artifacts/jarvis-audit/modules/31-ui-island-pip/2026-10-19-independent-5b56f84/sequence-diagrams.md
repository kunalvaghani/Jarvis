# Prompt 31 audit — 2026-10-19 IST

Actual current flow:
```mermaid
sequenceDiagram
  participant X as Actions / ToolRegistry
  participant A as App.request_approval
  participant Q as UIEventBuffer
  participant D as IslandDesk
  X->>A: kind, detail, cancelled
  A->>Q: answer dict + ready Event
  Q->>D: approval payload
  D->>D: append Approval with 180s lifetime
  Note over D: Approve callback has no card identity
  D->>D: pop current head, decide(True)
  D-->>A: ready Event + approved boolean
  A-->>X: approved and not cancelled
```
Failure sequence:
```mermaid
sequenceDiagram
  participant C as Old callback for A
  participant D as IslandDesk
  participant B as Request B
  C->>D: decide(True)
  D->>D: remove and approve A
  C->>D: stale decide(True)
  D->>B: approved=True (wrong request)
```
[Synthetic queue event trace](event-trace.json) preserves five terminal events; it is not a render/readback recording. Real GUI focus, secure-input, 200-percent scaling and process-crash evidence remain BLOCKED. Existing test XML contains fixture widget/readback assertions, accurately separate from full live acceptance.
