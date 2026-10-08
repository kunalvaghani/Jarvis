"""Opt-in visible Jarvis widget fixture for Computer Use.

Uses actual controls/games in a normal decorated test window. Microphone,
inference, external media polling, recovery and real memory writes are disabled.
This is not a screenshot or live voice/media result.
"""
import json
import os
from pathlib import Path
import sys
import tkinter as tk
import time


def main():
    if sys.argv[1:] != ['--live']:
        raise SystemExit('Use --live for the operator-authorized interactive fixture.')
    os.environ['JARVIS_UI_VERIFY'] = '1'
    from main import App
    # The real notch excludes itself from capture to avoid recursive screen
    # observations. This synthetic, memory-disabled fixture must be observable;
    # leave the real application's capture policy unchanged.
    App.exclude_orb_from_capture = lambda self: None
    root = tk.Tk(); root.withdraw()
    app = App(root)
    app.speech.options['enabled'] = False
    state = Path(__file__).resolve().parent / '.jarvis-runtime' / 'interactive-ui-state.json'
    started = time.monotonic()
    def tick():
        if app.closing:
            return
        app.desk.tick(True)
        app.desk.draw_game()
        state.write_text(json.dumps({'fixture': True, 'view': app.desk.view,
            'game': app.desk.game.name, 'score': app.desk.game.score,
            'paused': app.desk.game.paused, 'microphone_started': app.listener is not None,
            'memory_enabled': app.config['memory']['enabled']}), encoding='utf-8')
        if time.monotonic() - started >= 600:
            app.close()
        else:
            root.after(80, tick)
    app.animate_island = tick
    app.island.tick = lambda *_args, **_kw: None
    root.title('Jarvis interactive validation fixture')
    root.overrideredirect(False)
    root.attributes('-topmost', False)
    root.attributes('-transparentcolor', '')
    root.attributes('-alpha', 1.)
    root.configure(bg='#000000')
    app.island.expanded = app.island.features_open = app.island.surface_open = True
    app.panel.geometry('720x780+320+100')
    app.panel.deiconify()
    app.panel.tkraise()
    app.live.set('Interactive UI fixture — microphone, memory and external actions disabled')
    app.desk.reply = 'Actual Jarvis widgets. Test navigation and local games here; live voice and media are separate checks.'
    app.desk.full_reply = app.desk.reply
    app.desk.show('Overview')
    root.deiconify()
    try:
        root.mainloop()
    finally:
        if not app.closing:
            app.close()


if __name__ == '__main__':
    main()
