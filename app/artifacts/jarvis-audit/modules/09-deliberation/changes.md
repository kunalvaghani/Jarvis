# Retained scoped changes

- deliberation.py: configuration/opinion/goal bounds, finite values and worker claim schema; conservative high-risk ambiguity; exact approval replies; cancellation before/after inference; per-request timeout; UUID/correlated outcome events, Unicode and recognized private-text redaction; streamed retention and removal of unused unbounded ID cache; categorical ledger I/O failure diagnostic.
- actions.py: explicit boolean approval, bare refusal cancels pending proposal without replanning, cancellation propagates from opinion formation; added missing re import.
- brain.py: validate/consume private per-request timeout before worker wire; cap owned inference deadline without shared property mutation. Existing non-opinion callers unchanged.
- island_desk.py: lock-protected single decision, literalTrue consent, backward clock rejected. UI layout unchanged; no screenshot fabricated.
- Tests/accounting:32 catalog cases plus24 pre-fix variants and direct worker timeout assertion; explicit reviewed BLOCKED accounting. Reports include saved preimages, hash/diff, same-state A/B, upstream, full suite and readiness. Manifest/READMEs/guides updated together.

No new dependency, service, package/model installation or user config mutation. Changes retained for safety/correctness and bounded retention, not as a latency win. Earlier dirty work preserved; no commit made. Exact scope: [files-changed.json](files-changed.json); [source.patch](source.patch).
