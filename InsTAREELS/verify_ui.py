"""Construct and close Jarvis's UI without showing a window or starting listening."""
import tkinter as tk
import argparse
from pathlib import Path

from main import App


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", type=Path, help="Render the test widget layout to PNG without screen capture.")
    args = parser.parse_args()
    root = tk.Tk()
    root.withdraw()
    app = None
    try:
        app = App(root)
        root.update_idletasks()
        root.after(250, root.quit)
        root.mainloop()  # Exercise HUD rendering and scheduled callbacks while hidden.
        if app.panel.state() != "withdrawn":
            raise ValueError("Jarvis control panel was unexpectedly visible.")
        if app.listener is not None:
            raise ValueError("UI verification unexpectedly started microphone capture.")
        print("HUD and command center initialized without starting microphone capture.")
        if args.preview:
            from jarvis.ui_preview import export_preview
            app.panel.geometry("900x780+20000+20000")
            app.panel.deiconify()
            app.animate_orb()
            root.update_idletasks()
            root.update()
            try:
                app.log.configure(state="normal")
                app.log.delete("1.0", "end")  # Test-only widget contents, never files or checkpoints.
                app.log.insert("end", "YOU     Jarvis, what can you help me with?\n\n"
                               "JARVIS  I can answer questions, read your active screen,\n"
                               "        and help with tasks on your computer.\n\n"
                               "        Ask me something, or tell me what you'd like to do.\n")
                app.log.configure(state="disabled")
                export_preview(app, args.preview)
                print("Saved Jarvis widget-layout preview: " + str(args.preview))
            finally:
                app.panel.withdraw()
    finally:
        if app is not None:
            app.close()
        else:
            root.destroy()
    print("UI startup and shutdown passed.")


if __name__ == "__main__":
    main()
