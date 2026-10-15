# Official compatibility check — 2026-10-15 IST

Firecrawl fetched [Python 3.10 regular-expression documentation](https://docs.python.org/3.10/library/re.html) live (`maxAge: 0`), documentation 3.10.22. Full matching covers an entire command; substring search is inappropriate for these new intent families. Existing compiled rule tuples reuse regex objects. No new regex package or model is required.

[Python version status](https://devguide.python.org/versions/) checked during module 02: Python 3.10 EOL 2026-10-01; Python 3.15 branch first release 2026-10-09. Those dates do not certify ML runtime compatibility. Installed main 3.10.6 remains a release risk; no interpreter migration or installation occurred. Built-in deterministic command routing needs neither CUDA nor GPU memory. External app/keymap/window availability remains an independent live acceptance prerequisite. Paired improvements are limited to the authored corpus.
