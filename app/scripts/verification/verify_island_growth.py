"""Replay authored long output in an off-screen island; never capture the desktop."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import tkinter as tk
from unittest.mock import patch

from main import App
from jarvis.ui_preview import export_preview
from scripts.verification.verify_notch import keyed
from scripts.verification.verify_step_regression import run

BASE = Path(__file__).resolve().parents[2]


def ui(result):
    root = tk.Tk()
    root.withdraw()
    previous = os.environ.get('JARVIS_UI_VERIFY')
    os.environ['JARVIS_UI_VERIFY'] = '1'
    app = None
    try:
        app = App(root)
        for callback in root.tk.call('after', 'info'):
            root.after_cancel(callback)
        app.config.setdefault('ui', {})['reduced_motion'] = False
        root.geometry('402x40+20000+20000')
        root.deiconify()
        app.question.set('Long answer growth fixture')
        clock = 100.
        timings, heights = [], []
        def tick():
            nonlocal clock
            clock += 1/30
            started = time.perf_counter()
            with patch('jarvis.island.time.monotonic', return_value=clock):
                app.island.tick('THINKING')
            root.update()
            timings.append((time.perf_counter()-started)*1000)
            heights.append(root.winfo_height())
        app.island.notify('answer_stream', {'phase': 'Preparing answer', 'text': ''})
        app.desk.notify('answer_stream', {'phase': 'Preparing answer', 'text': ''})
        for _ in range(16):
            tick()
        overview = app.desk.views['Overview']
        unmaps = []
        overview.bind('<Unmap>', lambda event: unmaps.append(event.widget), add='+')
        initial_widgets = tuple(overview.winfo_children())
        text = '```cpp\n// Authored output fixture; this code is not executed.\n'
        captured = []
        layout = app.layout_notch
        with patch.object(app, 'layout_notch', wraps=layout) as relayout:
            for index in range(160):
                text += f'    std::cout << "Output row {index:03d}" << std::endl;\n'
                event = {'phase': 'Generating answer', 'text': text}
                app.island.notify('answer_stream', event)
                app.desk.notify('answer_stream', event)
                for _ in range(3):
                    tick()
                if index in (2, 11, 39, 159):
                    path = BASE/f'artifacts/island-growth-{index+1}.png'
                    export_preview(app, path)
                    from PIL import Image
                    picture = keyed(Image.open(path))
                    picture.save(path)
                    captured.append(picture.copy())
            assert relayout.call_count == 0, 'Streaming reconfigured the feature layout'
        assert not unmaps, 'Streaming unmapped the answer view'
        assert tuple(overview.winfo_children()) == initial_widgets
        assert app.desk.full_reply == text
        assert all(b >= a for a, b in zip(heights, heights[1:])), 'Growth shrank between chunks'
        assert heights[-1] > heights[0]
        # Expire the temporary caption to simulate a slow model pause.
        app.island.message_until = 0
        tick()
        assert app.island.surface_open and app.panel.state() == 'normal'
        from PIL import Image, ImageDraw
        from jarvis.island import font
        board = Image.new('RGB', (1100, 1220), '#181c23')
        draw = ImageDraw.Draw(board)
        draw.text((32, 22), 'Island growth · authored streaming fixture · 2026-10-04', font=font(22, True), fill='#eeeeee')
        draw.text((32, 56), 'Rendered widget layouts; no desktop capture or live model inference', font=font(15), fill='#a4aab5')
        factor = min(500/max(p.width for p in captured), 510/max(p.height for p in captured))
        for index, picture in enumerate(captured):
            picture = picture.resize((round(picture.width*factor), round(picture.height*factor)), Image.Resampling.LANCZOS)
            x, y = 32+index%2*540, 98+index//2*550
            draw.text((x,y), ('3', '12', '40', '160')[index]+' output rows', font=font(16), fill='#becbe3')
            board.paste(picture, (x, y+28))
        board.save(BASE/'artifacts/media/island-growth-preview.png')
        result.update(passed=True, scope='Authored off-screen streaming fixture, real Tk widgets and animation; no live Ollama or voice claim.',
                      chunks=160, animation_frames=len(heights), characters=len(text), answer_view_unmaps=len(unmaps),
                      stream_relayouts=relayout.call_count, widgets_preserved=True, monotonic_growth=True,
                      first_height=heights[0], final_height=heights[-1], stays_open_during_pause=True,
                      median_frame_ms=round(sorted(timings)[len(timings)//2], 2),
                      preview='artifacts/media/island-growth-preview.png')
    finally:
        if app:
            app.close()
        else:
            root.destroy()
        if previous is None:
            os.environ.pop('JARVIS_UI_VERIFY', None)
        else:
            os.environ['JARVIS_UI_VERIFY'] = previous


if __name__ == '__main__':
    mode = 'regression' if '--regression' in __import__('sys').argv else 'ui'
    result = {'date': datetime.now(timezone.utc).isoformat(), 'passed': False}
    try:
        if mode == 'regression':
            result['regression'] = run(['-m', 'unittest', 'discover', '-s', 'tests', '-q'])
            result['readiness'] = run(['-m', 'jarvis.launcher', '--check'])
            result.update(passed=result['regression']['exit_code'] == result['readiness']['exit_code'] == 0,
                          scope='Regression/readiness only; UI replay is recorded separately.')
        else:
            ui(result)
    except Exception as exc:
        result.update(passed=False, error=type(exc).__name__+': '+str(exc))
    destination = BASE/f'artifacts/island-growth-{mode}-check.json'
    if destination.is_file():
        history = BASE/f'artifacts/island-growth-{mode}-history.json'
        rows = json.loads(history.read_text(encoding='utf-8')) if history.is_file() else []
        rows.append(json.loads(destination.read_text(encoding='utf-8')))
        history.write_text(json.dumps(rows, indent=2)+'\n', encoding='utf-8')
    destination.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)
    raise SystemExit(0 if result['passed'] else 1)
