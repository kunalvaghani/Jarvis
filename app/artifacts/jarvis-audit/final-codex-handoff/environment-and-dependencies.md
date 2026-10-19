# Environment and external dependency requirements

| Component | Version on the verification machine | Needed for |
| --- | --- | --- |
| Windows | 11 Home, build 26200 | everything (UIA, COM, low-level hook) |
| Python (`.venv`) | 3.10.6 — [pip-freeze-venv.txt](environment/pip-freeze-venv.txt) | Jarvis runtime and tests |
| `.venv-training` | torch 2.6.0+cu124, transformers 4.57.6, peft 0.18.1, accelerate 1.12.0 — [freeze](environment/pip-freeze-venv-training.txt) | Phase 7 training/generation |
| `.venv-openviking` | openviking 0.5.0 (AGPL-3.0) — [freeze](environment/pip-freeze-venv-openviking.txt) | Phase 4 vault index |
| `.venv-skills` | openpyxl 3.1.5, python-docx 1.2.0 (see `requirements/skills.txt`) | Phase 2 document adapters |
| GPU | RTX 3050 Laptop 4 GB, driver 610.74, CUDA 12.4, BF16 | training, local models |
| Docker | Engine 29.8.2 with image `jarvis-mcp-runtime:1` (`scripts/setup/setup_mcp_runtime.py`) | MCP synthesis, cloud advice verification, induction sandbox |
| Ollama | 0.40.0 with `qwen3.5:9b`, `qwen3.5:4b`, `qwen3.5:0.8b`, `nomic-embed-text` | planner, proposer/solver, embeddings, EEVEE run |
| Git | 2.49.1 (system `core.autocrlf=true`) | lab snapshots, evaluator seal |
| Microsoft Office | installed (Word/Excel COM) | native fallbacks in Phase 2 |
| Blender | `D:\Blender\blender.exe` | Blender adapter and exploration sandbox |
| Unreal Engine | 5.8 manifest only | manifest read; editor projects BLOCKED |
| Base model weights | `models/qwen-jarvis-base` (Qwen2.5-Coder-0.5B-Instruct, SHA-256 pinned) | Phase 7 |

Optional or blocked: Groq free-tier account (not authorized for live calls), a GGUF converter (absent), a VM for
desktop exploration (absent). New Python dependencies across the upgrade are declared in `requirements/`
(`skills.txt`, `openviking.txt`) and in `config/runtime_manifest.json`.
