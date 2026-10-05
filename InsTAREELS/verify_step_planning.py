"""Real local next-step inference on an authored fixture; no desktop input."""
import argparse
import base64
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import time

from PIL import Image, ImageDraw, ImageFont
from jarvis.brain import BrainClient, validate_plan
from jarvis.step_planning import StepSession

BASE = Path(__file__).resolve().parent


def fixture():
    image = Image.new('RGB', (1000, 600), '#f5f5f5')
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(r'C:\Windows\Fonts\segoeui.ttf', 28)
    draw.rectangle((0, 0, 1000, 62), fill='#dddddd')
    draw.text((25, 13), 'Example - Notepad (authored test fixture)', font=font, fill='black')
    for x, label in ((30, 'Overview'), (310, 'Advanced'), (590, 'Help')):
        draw.rectangle((x, 105, x + 250, 165), fill='#ffffff', outline='#777777', width=2)
        draw.text((x + 20, 115), label, font=font, fill='black')
    draw.text((35, 230), 'Overview is currently selected.', font=font, fill='black')
    draw.text((35, 340), 'Synthetic pixels only. No real window or user data.', font=font, fill='#444444')
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    return image, base64.b64encode(buffer.getvalue()).decode('ascii')


def verify(live=False):
    image, encoded = fixture()
    image.save(BASE / 'artifacts' / 'next-step-fixture.png')
    session = StepSession()
    frames = [{'image': encoded}, {'image': 'previous fixture'}, {'image': 'current fixture'}]
    for frame in frames:
        session.capture(frame)
    checks = {'two_frames_maximum': len(session.frames) == 2,
              'oldest_frame_discarded': 'image' not in frames[0]}
    session.prepare('Select Advanced tab in Notepad', [], {'action': 'select', 'value': 'Advanced'}, [], [])
    checks['scaffold_has_no_future_screen'] = 'screen' not in session.consume()
    session.close()
    checks['no_images_after_task'] = not session.frames and all('image' not in f for f in frames)
    model_check = None
    if live:
        config = json.loads((BASE / 'config.json').read_text(encoding='utf-8'))
        client = BrainClient(BASE, config['brain'])
        started = time.monotonic()
        try:
            result = client.request('next_step', lambda: False,
                goal='Select Advanced tab in Notepad', step_number=1, completed=[],
                screen={'title': 'Example - Notepad', 'controls': ['Overview', 'Advanced', 'Help']},
                images=[encoded], tools=[{'action': 'select', 'description': 'Activate one unique visible tab by name.'}])
            elapsed = time.monotonic() - started
            steps = validate_plan(result)
            valid = result.get('done') is False and len(steps) == 1 and steps[0]['action'] == 'select' and steps[0]['value'].casefold() == 'advanced'
            model_check = {'passed': valid, 'seconds': round(elapsed, 3), 'under_five_seconds': elapsed < 5,
                           'model': result.get('model_used'), 'result': result}
        except Exception as exc:
            model_check = {'passed': False, 'seconds': round(time.monotonic() - started, 3), 'error': str(exc)[:500]}
        finally:
            client.close()
    return {'date': datetime.now(timezone.utc).isoformat(), 'checks': checks,
        'passed': all(checks.values()) and (model_check is None or model_check['passed']),
        'local_model_fixture': model_check,
        'scope': 'Authored pixels and real local inference only; no desktop capture/input, live voice, end-to-end speed or general accuracy evaluation.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--live-model', action='store_true')
    args = parser.parse_args()
    result = verify(args.live_model)
    (BASE / 'artifacts' / 'step-planning-check.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)
    raise SystemExit(0 if result['passed'] else 1)
