"""Off-screen real Tk pacing and owned alpha-edge verification; no desktop capture."""
import ctypes
from ctypes import wintypes
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import statistics
import time
from unittest.mock import patch

from PIL import Image, ImageDraw
from jarvis.island import contour_mask, render_island, font

BASE = Path(__file__).resolve().parents[2]


def percentile(samples, fraction):
    return sorted(samples)[round((len(samples) - 1) * fraction)]


def preview(path):
    board = Image.new('RGB', (1200, 680), '#20242d')
    draw = ImageDraw.Draw(board)
    draw.text((28, 16), 'Jarvis edge finish · rendered fixtures · 2026-10-10 IST', font=font(22, True), fill='white')
    draw.text((28, 48), 'Same shapes and motion; fractional alpha over light and dark backgrounds. No desktop screenshot.',
              font=font(14), fill='#bac1cd')
    for index, background in enumerate(('#20242d', '#eef0f4')):
        x, y = 28, 94 + index * 280
        draw.rounded_rectangle((x, y, 1172, y + 252), radius=16, fill=background)
        image = render_island(560, 126, 'WORKING', 1.2, scale=2., smooth_edges=True,
            media={'service':'spotify', 'phase':'playing', 'title':'Sample track', 'subtitle':'Sample artist',
                   'position':48, 'duration':240, 'at':time.time(), 'image':''})
        board.paste(image, (x + 12, y), image.getchannel('A'))
    board.save(path)


def main():
    previous = os.environ.get('JARVIS_UI_VERIFY')
    os.environ['JARVIS_UI_VERIFY'] = '1'
    # main enables Per Monitor V2 DPI before Tk creates the fixture.
    from main import App
    import tkinter as tk
    import win32gui
    root = tk.Tk()
    root.withdraw()
    app = None
    report = {'date':datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat(),
              'scope':'Off-screen authored fixtures, real Tk callbacks and native alpha layer; no desktop capture, microphone or live model.',
              'stages':{}}
    try:
        app = App(root)
        for callback in root.tk.call('after', 'info'):
            root.after_cancel(callback)
        app.config.setdefault('ui', {})['reduced_motion'] = False
        app.ui_activity = 'Rendering fixture'
        root.geometry('402x40+20000+20000')
        root.deiconify()
        root.update()
        app.island.tick('THINKING')
        assert app.island.edges.active, 'Native alpha surface unavailable'
        edge_handle = app.island.edges.handle
        styles = win32gui.GetWindowLong(edge_handle, -20)
        assert styles & 0x80000 and styles & 0x20 and styles & 0x08000000
        assert app.panel.winfo_toplevel() == root
        report['native_edge_active'] = True
        report['edge_input_transparent'] = True
        original_tick = app.island.tick
        samples, durations = [], []
        def tick(*args, **kwargs):
            started = time.perf_counter()
            original_tick(*args, **kwargs)
            samples.append(started)
            durations.append((time.perf_counter() - started) * 1000)
        app.island.tick = tick
        for stage in ('compact', 'expanded', 'media'):
            if stage == 'expanded':
                app.island.expand(True)
                app.desk.notify('answer', 'Authored sample answer.\n' * 20)
            elif stage == 'media':
                app.island.expand(False)
                app.desk.has_reply = False
                app.island.notify('media_card', {'service':'spotify','phase':'playing','title':'Sample track',
                    'subtitle':'Sample artist','position':48,'duration':240,'at':time.time()})
            samples.clear()
            durations.clear()
            app.animate_island()
            root.after(1800, root.quit)
            root.mainloop()
            for callback in root.tk.call('after', 'info'):
                root.after_cancel(callback)
            intervals = [(b-a)*1000 for a,b in zip(samples,samples[1:])]
            assert len(intervals) >= 40, 'Animation stalled: ' + stage
            report['stages'][stage] = {'frames':len(samples),'target_fps':app.animation_fps,
                'callback_fps':round(1000/statistics.mean(intervals),1),
                'interval_p50_ms':round(statistics.median(intervals),2),
                'interval_p95_ms':round(percentile(intervals,.95),2),
                'render_p50_ms':round(statistics.median(durations),2),
                'render_p95_ms':round(percentile(durations,.95),2)}
        # Fault injection: a failed compositor call releases its own native handles
        # and switches to the corrected hard-mask fallback; it never restarts UI.
        edge = app.island.edges
        with patch.object(edge.user, 'UpdateLayeredWindow', return_value=0):
            edge.present(contour_mask(600,126,32,32),20000,20000)
        assert not edge.active and edge.handle is None and edge.dc is None and edge.bitmap is None
        assert not win32gui.IsWindow(edge_handle)
        report['compositor_failure_cleanup_passed'] = True
        app.island.tick('THINKING')
        assert app.island.preview_image.mode == 'RGB'
        report['fallback_render_passed'] = True
        assert app.listener is None
        output = BASE / 'artifacts/reports/island-smoothness-2026-10-10.json'
        picture = BASE / 'artifacts/media/island-smoothness-preview.png'
        output.parent.mkdir(parents=True,exist_ok=True)
        picture.parent.mkdir(parents=True,exist_ok=True)
        preview(picture)
        report['preview'] = 'artifacts/media/island-smoothness-preview.png'
        report['passed'] = True
        output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report,indent=2))
    finally:
        if app is not None:
            app.close()
        else:
            root.destroy()
        if previous is None:
            os.environ.pop('JARVIS_UI_VERIFY',None)
        else:
            os.environ['JARVIS_UI_VERIFY'] = previous


if __name__ == '__main__':
    main()
