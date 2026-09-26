# Jarvis hardware and model audit — 27 September 2026

## Current decision

Keep the installed stack. This is a measured recommendation for this PC, not a claim that these models are universally best. No model names, checkpoints, runtime settings, or dependencies were changed by this audit.

Hardware measured locally: AMD Ryzen 7 5800H, 31.35 GiB usable physical RAM (32 GB installed), NVIDIA RTX 3050 Laptop with 4,096 MiB dedicated VRAM. Available system RAM was about 10.66 GiB during inspection; other applications and model workers share it. Ollama inference uses CPU, leaving the GPU for Whisper.

| Role | Installed/current model | Runtime |
| --- | --- | --- |
| Plans, tool selection, independent decisions, coding, general answers | `qwen3.5:4b`, Q4_K_M, approximately 3.4 GB model file | CPU; planning context 16,384 tokens |
| Screen understanding and visual verification | `qwen3-vl:4b`, Q4_K_M, approximately 3.3 GB | CPU; dedicated vision baseline |
| Visible-control ranking | `convaiinnovations/laya`, English checkpoint pinned to `1c5edc17a7acd8701df6fc341c0d179f1c62c982` | CPU, installed Laya 0.3.5; up to eight shortlisted labels plus none |
| Speech recognition | Whisper `medium.en` via faster-whisper; installed `small.en` fallback | CUDA, `int8_float16`; current input is English only |
| Speech output | Piper `en_GB-alan-medium` and `hi_IN-rohan-medium` | Local voices |

Laya ranks candidate controls; it does not replace planning, vision, or tool execution, reduce another model's memory requirements, or authorize actions. Ambiguous selection still requires Qwen's independent agreement, while a unique exact control match can skip ranking. Published Laya confidence is not calibrated authority; retain the independent checker. See the [official Laya model card](https://huggingface.co/convaiinnovations/laya).

## Alternatives in the supplied screenshots

The screenshot rankings are suggestions, not verified Jarvis results. Mixture-of-experts active parameter counts do not mean only those weights must fit in memory. [Ollama's Qwen3-Coder documentation](https://ollama.com/library/qwen3-coder) lists the 480B model at about 290 GB and a minimum 250 GB memory requirement. The screenshot's 72B–671B models are unsuitable for this PC's practical local workflow. Their approximately four-bit raw weights alone exceed this machine's RAM at 72B, before cache and runtime overhead.

Some smaller alternatives can fit system RAM in isolation, but CPU latency and simultaneous Jarvis workers matter: [Phi-4](https://ollama.com/library/phi4) is about 9.1 GB, [Qwen3.5 9B](https://ollama.com/library/qwen3.5) about 6.6 GB, and [Qwen2.5-Coder 7B](https://ollama.com/library/qwen2.5-coder) about 4.7 GB. None has been shown to improve this Jarvis workflow enough to justify replacing the current stack. Gemma 4 E4B is not a same-size drop-in: its effective parameter naming differs from total stored parameters ([Google model card](https://ai.google.dev/gemma/docs/core/model_card_4)); the listed [26B quantized variants](https://ollama.com/library/gemma4/tags) are much heavier. SmolVLM2 requires integration and desktop-specific evaluation; being smaller does not establish better visual verification.

## Local comparison and limits

`verify_hardware_models.py` compared the installed vision-capable models sequentially on one synthetic English form, with no OCR text and no desktop actions. Each model correctly accepted matching field text and rejected mismatching field text: two checks passed per model. Results are in [hardware-model-comparison.json](artifacts/hardware-model-comparison.json).

| Model | Matching check seconds | Mismatching check seconds | Step checks passed |
| --- | ---: | ---: | ---: |
| `qwen3-vl:4b` | 44.848 | 9.481 | 2/2 |
| `qwen3.5:4b` | 25.391 | 19.899 | 2/2 |
| `qwen3-vl:2b` | 34.209 | 8.240 | 2/2 |

The first call for each model can include loading/warmup. These are single observations with different generated answers, not controlled throughput averages. The checks assess step verification, not the model's final goal-completion judgment. Two simple examples do not establish superiority on real screenshots, coding, Hindi/Hinglish, or all 52 tools. Keep the existing 4B vision baseline; the installed 2B model remains a smaller alternative. Future changes should compare repeated representative task success, wrong selections, memory use, and total task time, including Laya and the decision checker together.

## Historical audit — 25 September 2026

The following is historical context. Its multilingual Whisper Small recommendation does not describe the current English `medium.en` configuration above.

# Jarvis model audit — 25 September 2026

This PC has an RTX 3050 Laptop GPU with 4 GB VRAM. Jarvis runs its Ollama language models on CPU (`knowledge.num_gpu: 0` and `brain_worker.py` sets `num_gpu: 0`) so Whisper can keep the GPU. `ollama list` confirms the configured Qwen models are installed. A larger model's published benchmark does not establish that it will improve this machine's end-to-end task time or reliability.

| Job | Current choice | Assessment and next experiment |
| --- | --- | --- |
| Planning, decisions, code generation, general answers | `qwen3.5:4b` (Ollama, Q4_K_M, 3.4 GB on disk) | Reasonable local baseline for 4 GB hardware and multilingual goals. The official [Qwen3.5-4B card](https://huggingface.co/Qwen/Qwen3.5-4B) reports strong language, coding, agent and vision results for its size. It is still a small model; syntax checks and task evidence matter more than an untested model swap. Compare coding pass rate and latency against an installed larger model only if CPU latency is acceptable. |
| Screen understanding | `qwen3-vl:4b` (Ollama, 3.3 GB) | A dedicated vision model; keep as baseline. The installed `qwen3.5:4b` also advertises vision capability. Evaluate both on Jarvis's real screenshots and control questions before consolidating them. See [Qwen3-VL-4B](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct) and [Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B). |
| Speech recognition, English/Hindi/Hinglish | multilingual Whisper Small through faster-whisper, CUDA int8_float16 | Keep until measured on the user's own short voice commands. [Whisper Small](https://huggingface.co/openai/whisper-small) is multilingual. [Qwen3-ASR-0.6B](https://huggingface.co/Qwen/Qwen3-ASR-0.6B-hf) explicitly supports Hindi and streaming and is a worthwhile A/B candidate; it needs a new integration and recorded Hindi/Hinglish samples to prove an improvement. [Whisper large-v3-turbo](https://huggingface.co/openai/whisper-large-v3-turbo) is larger and is not an automatic latency win on this GPU. |
| Spoken answers | Piper `en_GB-alan-medium`, `hi_IN-rohan-medium` | Fast offline voices already installed. [Piper voices](https://huggingface.co/rhasspy/piper-voices) include Hindi. [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) also has Hindi voices, but naturalness, Hinglish pronunciation and startup cost require a local listening test before switching. |
| Selection among visible controls | local `convaiinnovations/laya` plus Qwen decision check | The current Laya checkpoint is English focused. [Laya Multilingual](https://huggingface.co/convaiinnovations/laya-multilingual) reports better Hindi performance and faster inference, but its own card notes weaker English performance and overconfident scores. Route Hindi requests to it only after testing mixed English/Hinglish control labels; keep Qwen's independent decision check. |

Public [Reddit discussion about small local models](https://www.reddit.com/r/LocalLLaMA/comments/1rirtyy/qwen35_9b_and_4b_benchmarks/) is mixed, which reinforces measuring Jarvis tasks rather than selecting from anecdotes. The next useful evaluation set is 20–30 actual voice commands, screenshots, and coding tasks with expected results. Track task success, Hindi/Hinglish transcription, wrong clicks, and time to completion. No model was changed by this audit.
