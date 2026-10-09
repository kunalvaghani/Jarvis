"""Launch only verify_gui_edit's authored generated Tkinter fixture and invoke controls."""
from datetime import datetime, timezone
import json
from pathlib import Path
import runpy
import tkinter as tk
from tkinter import messagebox
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[2]


def verify():
    target = BASE / '.jarvis-runtime/gui-edit-fixture/calculator.py'
    roots, errors = [], []
    create = tk.Tk
    def owned_root(*args, **kwargs):
        root = create(*args, **kwargs)
        roots.append(root)
        return root
    result = {'date': datetime.now(timezone.utc).isoformat(), 'scope': 'Authored generated Tkinter fixture only; actual controls invoked through Tkinter.'}
    try:
        with patch.object(tk, 'Tk', side_effect=owned_root), patch.object(tk.Misc, 'mainloop', return_value=None), \
             patch.object(messagebox, 'showerror', side_effect=lambda *args, **kwargs: errors.append(str(args))):
            namespace = runpy.run_path(str(target), run_name='__main__')
            if len(roots) != 1:
                raise AssertionError('Normal launch did not create exactly one GUI window.')
            root = roots[0]
            root.update()
            def walk(widget):
                yield widget
                for child in widget.winfo_children():
                    yield from walk(child)
            widgets = list(walk(root))
            entries = [widget for widget in widgets if widget.winfo_class() in {'Entry', 'TEntry'}]
            combos = [widget for widget in widgets if widget.winfo_class() == 'TCombobox']
            buttons = [widget for widget in widgets if widget.winfo_class() in {'Button', 'TButton'}]
            labels = [widget for widget in widgets if widget.winfo_class() in {'Label', 'TLabel'}]
            if len(entries) != 2 or len(combos) != 1:
                raise AssertionError('Expected two inputs and one operation selector.')
            button = next(widget for widget in buttons if str(widget.cget('text')).casefold() == 'calculate')
            def calculate(operation, a, b):
                for widget, value in zip(entries, (a, b)):
                    widget.delete(0, tk.END)
                    widget.insert(0, str(value))
                combos[0].set(operation)
                button.invoke()
                root.update()
                return ' | '.join(str(widget.cget('text')) for widget in labels)
            observations = []
            for operation, a, b, expected in (('add', 5, 10, 15), ('subtract', 7, 2, 5),
                                             ('multiply', 6, 7, 42), ('divide', 12, 4, 3)):
                visible = calculate(operation, a, b)
                if str(expected) not in visible:
                    raise AssertionError(operation + ' result not visible: ' + visible)
                observations.append({'operation': operation, 'visible': visible})
            zero = calculate('divide', 2, 0)
            if 'zero' not in (zero + ' '.join(errors)).casefold():
                raise AssertionError('Division-by-zero error not visible.')
            invalid = calculate('add', 'bad input', 2)
            if not any(word in (invalid + ' '.join(errors)).casefold() for word in ('error', 'invalid', 'convert')):
                raise AssertionError('Invalid-input error not visible.')
            result.update(passed=True, normal_launch_window=True, controls=len(widgets), arithmetic=observations,
                          division_by_zero=zero, invalid_input=invalid)
            # Capture only this owned window; never a desktop screenshot.
            try:
                from PIL import ImageGrab
                import win32gui
                root.update()
                hwnd = win32gui.GetParent(root.winfo_id()) or root.winfo_id()
                image = ImageGrab.grab(window=hwnd)
                image.save(BASE / 'artifacts/media/qwen-generated-calculator-fixture.png')
                result['image'] = 'qwen-generated-calculator-fixture.png'
            except (OSError, TypeError, ImportError):
                result['image'] = None
    except Exception as exc:
        result.update(passed=False, error_type=type(exc).__name__, error=str(exc)[:500])
    finally:
        for root in roots:
            try:
                root.destroy()
            except tk.TclError:
                pass
    (BASE / 'artifacts/reports/gui-behavior-live-check.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)
    return result['passed']


if __name__ == '__main__':
    raise SystemExit(0 if verify() else 1)
