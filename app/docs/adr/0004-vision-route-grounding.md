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

**Default model:** `qwen3-vl:2b`. It matches 4B on safety (0 wrong clicks for both), is 3.4 points less accurate and is 2.5× faster.

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

- **Old ground truth:** the prefill rows without read-back used the earlier truth, which counted only the 13 px input box of a checkbox or radio as correct.
- **Repeatability:** the chosen row was run twice and gave identical results.

**A tried and rejected variant:** letting a matching label read-back overrule a disagreement between the two passes. It produced a wrong click on 2B (the read-back crop also contained the neighbouring nav text), so the disagreement refusal stays unconditional.

**Also tried and rejected:** a yes/no confirmation question ("is the element at the centre X?"). Both models answered "no" to 6 of 7 cases, including correct ones.

**Live desktop:** `test_live_model_clicks_a_canvas_shape_in_a_real_chrome_window` passed 3/3 on 2026-10-30.
- **Steps:** real mss capture of a headful Chrome window, `qwen3-vl:2b` grounding, a real SendInput click, then an independent DOM check of the canvas hit.
- **The one failure along the way was a correct refusal:** the first run captured the window while it was still painting, so the pre-click comparison reported STALE_REF and nothing was clicked. The test now waits for two equal screen signatures.

## Consequences

- Vision alone is at **81% accuracy, below the 90% acceptance target**, but every failure is a refusal, not a wrong click. Task-level accuracy depends on the router choosing browser refs or UIA first, and on the planner re-observing after a refusal.
- **Candidates for a dedicated grounding model.** These need the user's approval to download, and none was measured here. Leaderboard figures are third-party, from [BenchmarkList, ScreenSpot-Pro](https://benchmarklist.com/benchmarks/screenspot_pro/), and still need checking against each model card:

  | Model | ScreenSpot-Pro (reported) |
  |---|---|
  | Holo2-4B | 68.6% |
  | UI-Venus-1.5-2B | 57.7% |
  | Qwen3.5-4B | 60.3% |
  | Qwen3.5-2B | 54.5% |

  Each would need a GGUF/Ollama build that fits the 3.5 GB budget, and the same benchmark.
- Open: dxcam (DXGI duplication) is installed but unused. mss captures a full window in about 50 ms, far below the grounding cost.
