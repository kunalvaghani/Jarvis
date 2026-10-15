# Compatibility — checked 2026-10-15 IST

Firecrawl retrieved these official primary sources live (`maxAge: 0`); no private repository text was uploaded:

- [Python 3.10 threading contract](https://docs.python.org/3.10/library/threading.html), documentation 3.10.22: Events support cooperative timed waiting; threads cannot be forcibly stopped/interrupted; the GIL limits CPU-bound thread isolation. No hard native-parser containment is claimed.
- [Python 3.10 heapq](https://docs.python.org/3.10/library/heapq.html), documentation 3.10.22: nlargest ordering matches reverse sorting, but implementation choice requires measurement. Candidate reverted after paired regression.
- [Official Python version status](https://devguide.python.org/versions/): 3.10 EOL **2026-10-01**; 3.15 first release **2026-10-09**, 3.14 **2025-10-07**. Those are branch first-release dates, not an assurance that all Jarvis ML environments support them. Installed main 3.10.6 is unsupported. No automatic interpreter/package migration, installation or model download occurred.

This change uses existing standard-library primitives and existing SciPy posterior calculation. It does not require a newer PyTorch/CUDA/SciPy or model release. Existing environment/dependency compatibility and separate F5 environment evidence remain in module 01. Two environments still lack pip for dependency checks. Windows scheduling is not hard real-time. No GPU/TTFT/first-audio benchmark applies to this model-free attention fixture.
