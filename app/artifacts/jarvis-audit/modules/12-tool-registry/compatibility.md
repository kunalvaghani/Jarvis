# Prompt 12 — upstream compatibility (checked 2026-10-15 IST)

The registry path's only third-party runtime dependencies are `requests` and `urllib3` (HTTP for toolkit tools).
The tests and benchmark also use `psutil`.

| Package | Installed (`.venv`) | Latest on PyPI | Python requirement | Action |
| --- | --- | --- | --- | --- |
| requests | 2.34.2 | 2.34.2 ([PyPI JSON](https://pypi.org/pypi/requests/json)) | >=3.10 (local 3.10.6) | Already current; no change |
| urllib3 | 2.8.0 | 2.8.0 ([PyPI JSON](https://pypi.org/pypi/urllib3/json)) | >=3.10 | Already current; no change |

Because both were current, this module improved the implementation instead (see [changes.md](changes.md)). No
dependency was installed or upgraded. `requirements/runtime.txt` (`requests>=2.32,<3`) is unchanged. The RTX 3050
is not involved: the registry path is CPU-only.
