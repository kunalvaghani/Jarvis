# Voice compatibility evidence — 2026-10-15 IST

Firecrawl retrieved current official pages with maxAge:0; public URLs only, no local recordings, repository payloads or secrets uploaded. Installed main environment: Python3.10.6, faster-whisper1.2.1, CTranslate2 4.6.0, sounddevice0.5.6, NumPy2.2.6, SciPy1.15.3.

| Component | Official release observed | Local decision |
| --- | --- | --- |
| [faster-whisper releases](https://github.com/SYSTRAN/faster-whisper/releases) | 1.2.1, 2025-10-31 | Installed1.2.1; repair owned integration, retain model/quantization/endpoint policy |
| [CTranslate2 release](https://github.com/OpenNMT/CTranslate2/releases/tag/v4.8.3), [official release API](https://api.github.com/repos/OpenNMT/CTranslate2/releases/latest) | v4.8.3, published2026-10-13T05:57:44Z | Installed4.6.0 retained. New release fixes an exhausted CUDA TopK candidate edge case; native/GPU compatibility and resource validation required before promotion. No install authorized/performed |
| [GPU prerequisites](https://github.com/SYSTRAN/faster-whisper) | Current README, retrieved2026-10-15 | Recent CTranslate2 requires CUDA12/cuDNN9; CUDA11/cuDNN8 and CUDA12/cuDNN8 have distinct older version guidance. Do not mix runtimes blindly |
| [Python lifecycle](https://devguide.python.org/versions/) | 3.10 EOL2026-10-01 | Installed3.10.6 is unsupported; interpreter migration requires separate ML-environment compatibility work |
| [Python threading](https://docs.python.org/3.10/library/threading.html) | Documentation checked2026-10-15 | Cooperative timeout/ownership; native stuck thread cannot be forcibly terminated. No hard native-hang containment claim |

RTX3050 Laptop has4096MiB total, observed2700MiB used/1396MiB free. No new heavyweight model was loaded, no shared process stopped. Missing labeled quiet-room/TV/long-pause corpora and dedicated inference headroom block acoustic acceptance. Fake PCM and transcript tests do not prove WER, natural prosody, end-to-end speech latency or newer native runtime suitability. No paid dependency or new runtime service.
