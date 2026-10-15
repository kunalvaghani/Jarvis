# Compatibility and upstream checks — 2026-10-14 IST

Actual interpreter/package versions and requirements text are in [environment.json](environment.json). Main Python 3.10.6: NumPy 2.2.6, SciPy 1.15.3, faster-whisper 1.2.1, CTranslate2 4.6.0, Playwright 1.63.0, pytest 8.4.2. F5 Python 3.10.6: f5-tts 1.1.21, torch 2.6.0+cu124. DeerFlow Python 3.12.14, Hermes Python 3.14.7; environments are intentionally separate. Node v24.14.0, Docker client/server 29.8.2, GPU driver 610.74. Package metadata was read without loading all models.

Official sources retrieved through Firecrawl, not inferred from installed tags:

| Source | Observed contract / date | Decision |
| --- | --- | --- |
| [Python 3.10 threading](https://docs.python.org/3.10/library/threading.html) | Document title 3.10.22; RLock/Thread synchronization; publication date not supplied | Use existing RLock for state transitions; no Python runtime upgrade |
| [Python time](https://docs.python.org/3/library/time.html) | Monotonic clock cannot be set; search excerpt, release date not supplied | Existing tick deadlines retained; wall-time attention age clamped |
| [SciPy betaincinv](https://docs.scipy.org/doc/scipy/reference/generated/scipy.special.betaincinv.html) | Positive a,b; observed doc version 1.18.0, build June 19 2026 | Normalize invalid counts; retain installed 1.15.3 API |
| [SciPy 1.15.3 release](https://github.com/scipy/scipy/releases/tag/v1.15.3) | Bug-fix release May 8 2025 | No unsupported blind major upgrade on Python 3.10 |
| [pytest collection](https://docs.pytest.org/en/stable/example/pythoncollection.html) | Naming/discovery rules; release date not supplied | Fix imports and alias imported helper, preserve all real assertions |
| [F5 official repository](https://github.com/SWivid/F5-TTS) | Python 3.10+, MIT code and CC-BY-NC pretrained models; release date not established | Preserve voice environment; commercial deployment/license review unresolved |

No dependencies installed, downloaded or upgraded in this audit. A complete current-release/CVE/license review for every integration is NOT RUN, not a clean bill of health. Official sources are contract checks relevant to the retained changes; package tags and docs versions are not assertions of latest installed-compatible releases. Full provider live contracts, model quality, CUDA peak load and switching costs remain unverified.
