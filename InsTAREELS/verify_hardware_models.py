"""Compare installed vision models on synthetic UI, without desktop actions."""
import base64
import io
import json
import os
from pathlib import Path
import time

from PIL import Image, ImageDraw, ImageFont
from jarvis.brain_worker import Models

BASE = Path(__file__).resolve().parent


def main():
    options = json.loads((BASE / "config.json").read_text(encoding="utf-8"))["brain"]
    canvas = Image.new("RGB", (720, 280), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arial.ttf"), 24)
    draw.text((20, 20), "Example form", fill="black", font=font)
    draw.text((20, 90), "Search:", fill="black", font=font)
    draw.rectangle((140, 80, 680, 130), outline="black", width=2)
    draw.text((155, 90), "robot tutorials", fill="black", font=font)
    draw.rectangle((20, 170, 220, 230), outline="black", width=2)
    draw.text((35, 185), "Save draft", fill="black", font=font)
    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    screen = {"title": "Example form", "ocr": "", "controls": ["Search", "Save draft"],
              "image": base64.b64encode(buffer.getvalue()).decode("ascii")}
    models = Models()
    rows = []
    (BASE / "artifacts").mkdir(exist_ok=True)
    try:
        for model in ("qwen3-vl:4b", "qwen3.5:4b", "qwen3-vl:2b"):
            for text, expected in (("robot tutorials", True), ("mountain maps", False)):
                started = time.perf_counter()
                try:
                    result = models.predict({"operation": "visual", "options": {**options, "screen_model": model,
                        "allow_model_fallback": False}, "goal": "Fill Search field with " + text,
                        "step": {"action": "fill_text", "value": "Search", "content": text,
                                 "expected": "Search field contains " + text},
                        "screen": screen, "completed": [], "previous": None})
                    row = {"model": model, "case": "matching" if expected else "mismatching", "expected": expected,
                           "passed": result.get("step_verified") is expected, "result": result}
                except Exception as exc:
                    row = {"model": model, "case": "matching" if expected else "mismatching",
                           "passed": False, "error": type(exc).__name__}
                row["elapsed_seconds"] = round(time.perf_counter() - started, 3)
                rows.append(row)
                print(json.dumps(row, ensure_ascii=False), flush=True)
                (BASE / "artifacts" / "hardware-model-comparison.json").write_text(json.dumps({
                    "date": "2026-09-27", "scope": "Two synthetic UI checks per installed vision model; no desktop actions. First call can include load/warmup.",
                    "results": rows}, indent=2, ensure_ascii=False), encoding="utf-8")
    finally:
        models.client.close()
    print("Comparison saved; no configuration changes made.", flush=True)
    if not all(row["passed"] for row in rows):
        raise SystemExit("One or more vision checks failed; see the comparison report.")


if __name__ == "__main__":
    main()
