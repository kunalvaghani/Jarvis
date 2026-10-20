# Prompt 31 independent continuation — 2026-10-19 IST

Current normal path:
```mermaid
sequenceDiagram
  participant R as Requester
  participant Q as UIEventBuffer
  participant D as IslandDesk / Approval
  R->>Q: kind, detail, answer, ready, cancelled
  Q->>D: construct card; random token and text digest
  D->>D: bind click/voice to displayed token
  D-->>R: approved + token + digest, ready
  Note over R: Checks digest, not unique pending token
```
Synthetic replay:
```mermaid
sequenceDiagram
  participant A as Prior approved card A
  participant I as Fault injector at response seam
  participant B as New same-text request B
  A-->>I: saved token A + text digest
  B->>B: construct card B (different token)
  I->>B: deliver saved A receipt; no B decision
  B->>B: digest matches; returns True
```
event-trace.json records five synthetic producers and terminal barriers; it does not include rendered private data. widget-readback files contain real offscreen widget text/ready/result, with synthetic input and no external executor. Accessibility/focus/DPI/process-crash full acceptance is BLOCKED.
