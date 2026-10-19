# Prompt 31 independent audit — 2026-10-19 IST

Corrected request flow:
```mermaid
sequenceDiagram
  participant R as Requester
  participant Q as UIEventBuffer
  participant C as Approval card
  R->>R: generate request ID and issue time
  R->>Q: kind, detail, request ID, answer/Event
  Q->>C: capture ID; derive text+ID digest
  C->>C: token-bound user callback; TTL/cancel check
  C-->>R: receipt and ready Event
  R->>R: compare own ID digest; own TTL; cancellation
```
Replay of an earlier same-text receipt fails the new request's digest comparison. Event-trace.json shows five synthetic producers and retained terminal barriers; it is not a renderer or restart recording. Widget-readback files hold authored real-Tk output. Resource profiles and paired-card-profile state their exact synthetic scope.
