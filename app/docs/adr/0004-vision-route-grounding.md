# ADR 0004: Vision route grounding (Route 4)

Status: accepted, 2026-10-30. Branch `claude_ControlArchitect`.

## Context

Route 4 is the last resort, for targets with no API, browser ref or UIA element (canvas apps, games, custom-drawn UI). The hardware budget is an RTX 3050 Laptop with 4 GB of VRAM; the vision model must stay under 3.5 GB. Screenshots of the desktop are private and must not go to a cloud model. Downloading new models needs the user's approval, so the first version uses the models already installed: `qwen3-vl:2b` and `qwen3-vl:4b` in Ollama 0.40.0.

## Decision

`jarvis/control/routes/vision.py`:

1. **Capture.** mss captures physical pixels, and the process is made per-monitor DPI aware first. If the capture size differs from the region, the route refuses.
2. **Grounding pipeline.**
   - **Overview pass:** a downscaled capture, long edge 1280 px.
   - **Close-up pass:** a native-resolution crop, 4× the coarse box and at least 384 px.
   - **Mapping:** both passes map back through `coords.Transform`, which refuses (never clamps) out-of-frame or stale points.
   - **Refusals:** if the two passes disagree by more than one target size, the route refuses. A box covering at least 90% of the image on both axes counts as "not found".
3. **Label read-back.** When the caller knows the target's visible text (`label`), the model reads the text at the grounded point from an enlarged crop. The route refuses unless the label is there. Shape targets such as "the red square" skip this step.
4. **Before input.**
   - **Screen check:** the target's surroundings are captured again and compared with what the model saw. A mean grey-level difference above 12 means STALE_REF, and nothing is clicked.
   - **Window check:** the route refuses an elevated window, a window not on the allowlist, or the secure desktop under the point.
5. **Input.** All input goes through the shared `input.Input`, which also confirms that the pointer arrived.
6. **Privacy.** `OllamaGrounder` refuses any server that is not a loopback address, so screenshots never leave the PC.
7. **No thinking.** The installed Qwen3-VL builds think before answering even with `think=false`: 150–400 tokens, 10–35 s per pass, measured. Starting the assistant turn with the answer prefix (`{"bbox_2d": [`) skips the thinking: 20 tokens, about 0.5 s warm on 2B. Qwen3-VL boxes use a relative 0–1000 scale; this was confirmed on a known button.
8. **Context.** A 4k context keeps the model on the GPU. At 16k, `qwen3-vl:4b` took 5.8 GB and ran 68% on the CPU.

**Default: `qwen3-vl:2b`, escalating to `qwen3-vl:4b` only when 2B refuses** (`DEFAULT_CHAIN`, `default_grounders()`; amended 2026-10-30).
- Each model in the chain sees a fresh capture and runs every check above.
- Before escalating, 2B is unloaded from the GPU, and 4B is unloaded afterwards, so only one model is ever resident.
- Only a refusal escalates. A stale screen, a timeout or a cancel stops immediately.

## Measurements (2026-10-30, `benchmarks/vision_grounding.py`)

**Setup:**
- 32 present targets and 3 absent ones, on D1 pages at 1280×800 in headless Chrome.
- Ground truth comes from the DOM. A control's clickable area includes its own `<label>`, because clicking a label activates its control.
- The page screenshot stands in for the screen, so no desktop content is photographed.

| Variant | Model | Hits | Wrong clicks | Refused | Clicks on absent targets | p50 | p95 | Peak VRAM |
|---|---|---|---|---|---|---|---|---|
| Thinking, 80-token cap | 2B and 4B | 0/28 | — | — (no answer within the cap) | — | — | — | — |
| Prefill, no read-back | 2B | 25/32 | **4** | 3 | **2/3** | 1.8 s | 2.8 s | 2.7 GB |
| Prefill, no read-back | 4B | 28/32 | **3** | 1 | **1/3** | 4.7 s | 6.5 s | 2.8 GB |
| **Prefill + read-back (chosen)** | **2B** | **26/32 (81.2%)** | **0** | 6 | **0/3** | 3.0 s | 4.1 s | 2.7 GB |
| Prefill + read-back | 4B | 27/32 (84.4%) | 0 | 5 | 0/3 | 7.6 s | 9.4 s | 2.8 GB |
| 2B→4B escalation, both models resident | chain | 30/32 | 0 | 2 | 0/3 | 6.8 s | 30.2 s | **3.95 GB** (over budget; 4B ran 53% on CPU) |
| 2B→4B, unload around escalation, same capture | chain | 29/32 | 0 | 3 (one: 74 s grounding outlived the 60 s capture age) | 0/3 | 3.3 s | 23.9 s | 2.75 GB |
| **2B→4B, unload around escalation, fresh capture per model (chosen)** | **chain** | **30/32 (93.8%)** | **0** | 2 | **0/3** | **3.2 s** | 25.6 s | **2.76 GB** |
| Installed `qwen3.5:2b`, same pipeline | 2B | 1/32 | 4 | 27 | 0/3 | 3.0 s | 3.5 s | 2.6 GB |
| Installed `qwen3.5:4b`, same pipeline | 4B | 6/32 | 8 | 18 | 0/3 | 22.8 s | 30.6 s | 1.5 GB |

- **Old ground truth:** the prefill rows without read-back used the earlier truth, which counted only the 13 px input box of a checkbox or radio as correct.
- **Repeatability:** the chosen row was run twice and gave identical results.

**A tried and rejected variant:** letting a matching label read-back overrule a disagreement between the two passes. It produced a wrong click on 2B (the read-back crop also contained the neighbouring nav text), so the disagreement refusal stays unconditional.

**Also tried and rejected:** a yes/no confirmation question ("is the element at the centre X?"). Both models answered "no" to 6 of 7 cases, including correct ones.

**Live desktop:** `test_live_model_clicks_a_canvas_shape_in_a_real_chrome_window` passed 3/3 on 2026-10-30.
- **Steps:** real mss capture of a headful Chrome window, `qwen3-vl:2b` grounding, a real SendInput click, then an independent DOM check of the canvas hit.
- **The one failure along the way was a correct refusal:** the first run captured the window while it was still painting, so the pre-click comparison reported STALE_REF and nothing was clicked. The test now waits for two equal screen signatures.

## Consequences

- With escalation, vision alone reaches **93.8% on D1 with no wrong clicks**: above the 90% target. Two harder cases (a `<select>`, and a radio whose label sits next to another radio) are still refused. The occasional escalation is slow (p95 about 25 s).
- The installed Qwen3.5 models are unusable in this pipeline: 4–8 wrong clicks. Their box convention probably differs from Qwen3-VL's; this was not investigated further, because Qwen3-VL meets the target.
- **Download decision (2026-10-30).** The user approved downloading one dedicated model to D:. No download was made: the escalation chain met the target with installed models. Holo2-4B's official card reports 57.2% on ScreenSpot-Pro, while aggregators list its base, Qwen3-VL-4B-Instruct, at about 59.5%. Holo 3.1 publishes no grounding numbers in text and does not document its coordinate format. Ollama already stores models in `D:\Ollama\models`, so a future pull lands on D:.
- **Candidates for a dedicated grounding model, if more is needed later.** These need the user's approval to download, and none was measured here. Leaderboard figures are third-party, from [BenchmarkList, ScreenSpot-Pro](https://benchmarklist.com/benchmarks/screenspot_pro/), and still need checking against each model card:

  | Model | ScreenSpot-Pro (reported) |
  |---|---|
  | Holo2-4B | 68.6% |
  | UI-Venus-1.5-2B | 57.7% |
  | Qwen3.5-4B | 60.3% |
  | Qwen3.5-2B | 54.5% |

  Each would need a GGUF/Ollama build that fits the 3.5 GB budget, and the same benchmark.
- Open: dxcam (DXGI duplication) is installed but unused. mss captures a full window in about 50 ms, far below the grounding cost.
