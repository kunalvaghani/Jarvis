# Compatibility / official upstream checks — 2026-10-14–15 IST

Observed main Python3.10.6; separate F5 torch2.6.0+cu124; NumPy2.2.6/SciPy1.15.3 in main; Docker29.8.2, Node24.14.0 and Ollama0.40.0 remain unchanged. [Actual interpreter/dependency checks](dependency-checks.json) enumerate nine environments: seven pip-check PASS; DeerFlow and Hermes BLOCKED (pip unavailable). A blocked dependency check is not proof of a conflict or of no conflict.

- [Python warning contract](https://docs.python.org/3.10/library/warnings.html), fetched through Firecrawl on2026-10-14 IST: typed warnings/catch_warnings support metadata-only unknown-field diagnostics. Observed docs title3.10.22; publication date not supplied.
- [Python audit-hook contract](https://docs.python.org/3.10/library/sys.html#sys.addaudithook), fetched through Firecrawl on2026-10-14–15 IST: hooks are observation facilities, not a secure sandbox against malicious Python. This corroborates the existing AbilityForge isolation concern; it is not an exploit claim.
- [Official Python version status](https://devguide.python.org/versions/), checked2026-10-15 IST: branch3.10 is listed end-of-life, first release2021-10-04, EOL2026-10-01. No unsupported blind interpreter swap or package installation was performed. Migration needs module34 compatibility tests across speech/native/brain environments.

The retained change uses stdlib JSON/warnings/sets and existing code only. No paid integration/model/pin changed. These checks cover the touched contracts; latest versions/advisories for every named integration and commercial model licenses remain separate pending work. Launcher --check retains its bounded import/probe controls and reports ready; this does not assert all services are running or live features operational.
