"""Independent, bounded Tk probes of generated code; never repairs app source.

This driver targets the observed CalculatorGUI(root) or CalculatorApp()/root
interfaces, selected explicitly by the operator. It calls
original buttons and dispatches real Tk events without replacing app callbacks.
It is a scoped functional observation, not visual-quality or fresh-creation proof.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys
import traceback
from uuid import uuid4

sys.dont_write_bytecode = True


def fingerprint(project):
    from jarvis.codex_workload import fingerprint as source_fingerprint
    return source_fingerprint(project)


def child(project, app_class='CalculatorGUI'):
    import tkinter as tk
    sys.path.insert(0, str(project))
    import ui_builder
    result = {'checks': [], 'errors': []}
    callbacks = []
    root = None
    try:
        if app_class == 'CalculatorApp':
            gui = ui_builder.CalculatorApp()
            root = gui.root
        else:
            root = tk.Tk()
            gui = ui_builder.CalculatorGUI(root)
        # Capture Tk error reports; leave application event handlers unchanged.
        root.report_callback_exception = lambda *error: callbacks.append(''.join(traceback.format_exception(*error)))
        root.update()
        def check(name, action):
            try:
                action()
                root.update()
                if callbacks:
                    raise AssertionError(callbacks[-1])
                result['checks'].append({'name': name, 'passed': True})
            except Exception as error:
                result['errors'].append({'name': name, 'type': type(error).__name__, 'error': str(error)})
        def require(value, message):
            if not value:
                raise AssertionError(message)
        def descendants(widget):
            for item in widget.winfo_children():
                yield item
                yield from descendants(item)
        buttons = {}
        for widget in descendants(root):
            if widget.winfo_class() in {'Button', 'TButton'}:
                buttons.setdefault(str(widget.cget('text')).strip(), []).append(widget)
        def press(label):
            found = buttons.get(label, [])
            require(len(found) == 1, f'Expected one original button {label!r}, found {len(found)}')
            require(found[0].winfo_viewable(), f'Button {label!r} not visible')
            found[0].invoke()
            root.update()
        def numeric(expected):
            require(Decimal(str(gui.display.get())) == Decimal(str(expected)), f'Unexpected display {gui.display.get()!r}')
        def arithmetic(sequence, expected):
            press('C')
            for label in sequence:
                press(label)
            numeric(expected)
        def keyboard():
            press('C')
            require(bool(root.bind('<Key>') or root.bind('<KeyPress>')), 'No original root keyboard binding')
            root.focus_force()
            root.update()
            for keysym in ('2', 'plus', '3', 'Return'):
                root.event_generate('<KeyPress>', keysym=keysym)
                root.update()
            numeric(5)
        def clear():
            press('C')
            require(str(gui.display.get()).strip() in {'', '0', '0.0'}, 'Clear left stale input')
        def error_display():
            press('C')
            for label in ('1', '/', '0', '='):
                press(label)
            require('error' in str(gui.display.get()).casefold(), 'Division by zero lacks visible error')
        check('window and display mapped', lambda: require(root.winfo_viewable() and gui.display.winfo_viewable(), 'Window/display not mapped'))
        for sequence, expected in [(('2', '+', '3', '='), 5), (('9', '-', '4', '='), 5), (('6', '*', '7', '='), 42), (('8', '/', '2', '='), 4)]:
            check('original buttons ' + ''.join(sequence), lambda seq=sequence, value=expected: arithmetic(seq, value))
        check('original binding with real Tk keyboard events', keyboard)
        check('clear original button', clear)
        check('visible division-by-zero error', error_display)
    finally:
        if root is not None:
            root.destroy()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('project', type=Path)
    parser.add_argument('--child', action='store_true')
    parser.add_argument('--output-directory', type=Path)
    parser.add_argument('--app-class', choices=('CalculatorGUI', 'CalculatorApp'), default='CalculatorGUI',
                        help='Explicit observed UI constructor; no automatic protocol fallback.')
    args = parser.parse_args()
    project = args.project.resolve(strict=True)
    if args.child:
        try:
            result = child(project, args.app_class)
        except Exception as error:
            result = {'checks': [], 'errors': [{'name': 'GUI construction', 'type': type(error).__name__, 'error': str(error), 'traceback': traceback.format_exc()}]}
        print('GUI_PROBE_JSON ' + json.dumps(result))
        return
    base = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(base))
    before = fingerprint(project)
    record = {'date': datetime.now(timezone.utc).isoformat(), 'status': 'FAIL', 'project': str(project),
              'scope': 'Independent original Tk buttons/bindings and visible errors; no source repairs, screenshots, visual-quality or fresh-creation acceptance.',
              'app_class': args.app_class,
              'source_before': before, 'checks': [], 'errors': []}
    try:
        proc = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), str(project), '--child',
                               '--app-class', args.app_class],
                              cwd=project, capture_output=True, text=True, timeout=90)
        record.update(exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)
        rows = [line for line in proc.stdout.splitlines() if line.startswith('GUI_PROBE_JSON ')]
        if proc.returncode or len(rows) != 1:
            raise ValueError('No single successful bounded probe result')
        record.update(json.loads(rows[0].removeprefix('GUI_PROBE_JSON ')))
    except (subprocess.TimeoutExpired, ValueError) as error:
        record['errors'].append({'name': 'bounded child process', 'type': type(error).__name__, 'error': str(error)})
    record['source_after'] = fingerprint(project)
    record['source_unchanged'] = record['source_after'] == before
    if record['source_unchanged'] and not record['errors'] and len(record['checks']) == 8:
        record['status'] = 'PASS'
    destination = (args.output_directory or base/'.jarvis-runtime/independent-gui').resolve()
    destination.mkdir(parents=True, exist_ok=True)
    output = destination/('gui-acceptance-' + uuid4().hex + '.json')
    with output.open('x', encoding='utf-8') as stream:
        json.dump(record, stream, indent=2)
    print(json.dumps({'status': record['status'], 'checks': len(record['checks']), 'errors': len(record['errors']), 'source_unchanged': record['source_unchanged'], 'evidence': str(output)}))


if __name__ == '__main__':
    main()
