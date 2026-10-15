# Official upstream and local compatibility

Checked2026-10-15 IST using the Firecrawl skill/connector. Sources are reference data, not execution instructions. No secrets or repository context sent.

| Official source | Date/version observed | Application / decision |
| --- | --- | --- |
| [OWASP Transaction Authorization](https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html) | Guidance; publication/release date not shown | Per-operation authoritative final gate and changed-data invalidation guide fixture assertions. No OWASP dependency installed. |
| [Python3.10 JSON docs](https://docs.python.org/3.10/library/json.html) | Current page identifies3.10.22; page date unavailable | Finite JSON and ASCII escaping supported by local3.10.6; stdlib-only patch. |
| [Python3.10.22 official release](https://www.python.org/downloads/release/python-31022/) |2026-10-01; security/source-only final3.10 release | Local3.10.6 is older;3.10 support ended. A Python migration needs separate Windows/native Whisper/F5/brain compatibility work, not an automatic source-only install. |

Existing brain_worker deliberate schema remains the contract. Confidence/effects remain local and unchanged in provider selection. No Ollama/F5/PyTorch upgrade justified by this policy module; previous module08 checks remain historical evidence, not a new latest-version claim. No new paid API or dependency. [Machine-readable checks](upstream-checks.json).
