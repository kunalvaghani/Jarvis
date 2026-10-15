# Compatibility / official checks — 2026-10-15 IST

Actual Ollama0.40.0, installed cached Qwen3.5:9b, Python3.10.6, NVIDIA RTX3050 Laptop4096MiB. Official [latest Ollama release](https://github.com/ollama/ollama/releases/tag/v0.40.4) is0.40.4,12Oct2026 at19:00 (timezone not established); notes mention reuse of verified manifests/loaded models. No installation/download authorized/performed; newer runtime/native performance remains unvalidated here. Existing runtime completed both native series. Prior Python support-window concern remains separate work.

Official [FAQ](https://docs.ollama.com/faq) documents context/parallelism memory costs and keep_alive cache retention. Current application overrides differ from default provider values. [Loaded-model API](https://docs.ollama.com/api/ps) supplies size_vram/context/expiry fields used for fresh identity checks; example numbers in documentation are not measurements of this machine. No date is stated on those guides. [Captured source checks](upstream-checks.json).

No quantization, CUDA library, PyTorch/Whisper runtime, global parallelism or driver change. No brittle manual CUDA clear. Real cold/warm samples use the existing API/GPU scheduler; defaults remain compatible in executed scope, not certified across optional integrations or a future release.
