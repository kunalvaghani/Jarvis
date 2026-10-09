"""Exercise the configured local planner against synthetic UI, without PC actions."""
import json
import argparse
from pathlib import Path

from jarvis.brain import validate_plan
from jarvis.brain_worker import Models
from jarvis.tools import ToolRegistry


if __name__ == "__main__":
    options = json.loads(Path("config/config.json").read_text(encoding="utf-8"))["brain"]
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="Test an installed planner without changing Jarvis configuration")
    parser.add_argument("--vision-only", action="store_true", help="Test the configured vision model on a synthetic form")
    args = parser.parse_args()
    if args.model:
        options = {**options, "planner": args.model, "decision": args.model}
    models = Models()
    if args.vision_only:
        import base64
        import io
        from PIL import Image, ImageDraw, ImageFont
        canvas = Image.new("RGB", (700, 300), "white")
        draw = ImageDraw.Draw(canvas)
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 24)
        draw.text((20, 20), "Example app - File menu", fill="black", font=font)
        draw.text((20, 100), "Search:", fill="black", font=font)
        draw.rectangle((140, 90, 650, 145), outline="black", width=2)
        draw.text((150, 100), "robot tutorials", fill="black", font=font)
        buffer = io.BytesIO()
        canvas.save(buffer, format="PNG")
        result = models.predict({"operation": "visual", "options": options,
            "goal": "Fill Search field with robot tutorials",
            "step": {"action": "fill_text", "value": "Search", "content": "robot tutorials", "expected": "Search field contains robot tutorials"},
            "completed": [], "previous": None,
            "screen": {"title": "Example app", "ocr": "Search robot tutorials", "controls": ["Search"],
                       "image": base64.b64encode(buffer.getvalue()).decode("ascii")}})
        if result.get("step_verified") is not True:
            raise ValueError("Vision model did not verify the visible text field: " + json.dumps(result))
        print(json.dumps(result, indent=2))
        print("Vision check passed on a synthetic screen. No desktop actions were executed.")
        raise SystemExit(0)
    plan = models.predict({"operation": "plan", "options": options,
        "goal": "Fill Search field with robot tutorials then open File menu",
        "screen": {"title": "Example app", "is_dialog": False,
                   "controls": ["Search", "File"], "fields": ["Search"]},
        "apps": [], "completed": [], "prior_task": None,
        "tools": ToolRegistry(None).catalog()})
    steps = validate_plan(plan)
    if [step["action"] for step in steps] != ["fill_text", "open_menu"]:
        raise ValueError("Planner did not select the requested field and menu tools: " + json.dumps(plan))
    if steps[0]["content"] != "robot tutorials":
        raise ValueError("Planner changed the exact text to enter.")
    if steps[0]["value"].casefold() != "search" or steps[1]["value"].casefold() != "file":
        raise ValueError("Planner selected the wrong field or menu: " + json.dumps(plan))
    print(json.dumps(plan, indent=2))
    decision = models.predict({"operation": "decide", "options": options,
        "goal": "Fill Search field with robot tutorials", "step": steps[0],
        "screen": {"title": "Example app", "controls": ["Search", "File"]},
        "candidates": [{"key": "c0", "name": "Search", "role": "Edit"},
                       {"key": "c1", "name": "File", "role": "MenuItem"}]})
    if decision.get("approved") is not True or decision.get("choice") != "c0":
        raise ValueError("Decision model failed to select the Search field: " + json.dumps(decision))
    print("Field decision:", json.dumps(decision))
    print("Local model selected the correct desktop tools. No desktop actions were executed.")
