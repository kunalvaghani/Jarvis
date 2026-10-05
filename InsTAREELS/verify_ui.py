"""Construct and close Jarvis's UI without showing a window or starting listening."""
import tkinter as tk
import argparse
import os
from pathlib import Path

from main import App


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", type=Path, help="Render the test widget layout to PNG without screen capture.")
    parser.add_argument("--controls-preview", type=Path, help="Render compact control widgets without capturing the desktop.")
    parser.add_argument("--animation", type=Path, help="Export a labelled GIF using the runtime island morph/renderer.")
    parser.add_argument('--hd-preview', type=Path, help='Render Full HD native-DPI states with live task captions.')
    args = parser.parse_args()
    root = tk.Tk()
    root.withdraw()
    app = None
    previous = os.environ.get("JARVIS_UI_VERIFY")
    os.environ["JARVIS_UI_VERIFY"] = "1"
    try:
        app = App(root)
        root.update_idletasks()
        root.after(250, root.quit)
        root.mainloop()  # Exercise island rendering and scheduled callbacks while hidden.
        if app.panel.state() != "withdrawn":
            raise ValueError("Jarvis control panel was unexpectedly visible.")
        if app.listener is not None:
            raise ValueError("UI verification unexpectedly started microphone capture.")
        print("Dynamic Island initialized without starting microphone capture.")
        if args.preview:
            from jarvis.island import export_preview
            export_preview(args.preview)
            print("Saved rendered Dynamic Island state preview: " + str(args.preview))
        if args.controls_preview:
            from jarvis.ui_preview import export_preview as export_controls
            from jarvis.display import window_scale
            scale = window_scale(root)
            app.panel.geometry(f"{round(500*scale)}x{round(316*scale)}+20000+20000")
            app.panel.deiconify()
            app.config.setdefault('ui', {})['reduced_motion'] = True
            app.island.expand(True)
            app.island.features_open = True
            app.island.tick('STANDBY')
            app.live.set("Ready when you are. Ask a question or give me a task.")
            app.log.configure(state="normal")
            app.log.delete("1.0", "end")
            app.log.insert("end", "JARVIS  I can help with your projects, answer questions,\n        and use the apps on your PC.\n")
            app.log.configure(state="disabled")
            root.update_idletasks()
            root.update()
            export_controls(app, args.controls_preview)
            app.panel.withdraw()
            print("Saved rendered compact controls: " + str(args.controls_preview))
        if args.animation:
            from jarvis.island import export_animation
            export_animation(args.animation)
            print("Saved rendered island animation: " + str(args.animation))
        if args.hd_preview:
            from jarvis.island import export_hd_preview
            export_hd_preview(args.hd_preview)
            print('Saved Full HD rendered island states: ' + str(args.hd_preview))
    finally:
        if app is not None:
            app.close()
        else:
            root.destroy()
        if previous is None:
            os.environ.pop("JARVIS_UI_VERIFY", None)
        else:
            os.environ["JARVIS_UI_VERIFY"] = previous
    print("UI startup and shutdown passed.")


if __name__ == "__main__":
    main()
