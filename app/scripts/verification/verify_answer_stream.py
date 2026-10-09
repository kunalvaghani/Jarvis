"""Separate real question inference, authored island preview, and regression checks."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

BASE = Path(__file__).resolve().parents[2]


def live(result):
    from jarvis.question_client import QuestionClient
    config = json.loads((BASE/'config/config.json').read_text(encoding='utf-8'))
    started = time.monotonic()
    last_print = 0.
    result.update(scope='Real Jarvis question-worker inference; no voice, desktop actions, compilation or execution.',
                  model=config['knowledge']['model'], progress_events=0, preview_characters=0)
    def report(kind, event):
        nonlocal last_print
        if kind != 'answer_stream':
            return
        elapsed = time.monotonic()-started
        result['progress_events'] += 1
        if event.get('text'):
            result.setdefault('first_text_seconds', round(elapsed, 3))
            result['preview_characters'] = len(event['text'])
        if elapsed-last_print >= 15 or result['progress_events'] == 1:
            print(f"{elapsed:.1f}s: {event['phase']} / {result['preview_characters']} preview characters", flush=True)
            last_print = elapsed
    client = QuestionClient(BASE, report)
    try:
        reply = client.request({'question': 'give c++ code for snake and ladder game with working ui',
                                'options': config['knowledge'], 'stream_answer': True}, lambda: False)
        result.update(total_seconds=round(time.monotonic()-started, 3), answer_characters=len(reply['answer']),
                      contains_cpp=('```cpp' in reply['answer'] or '#include' in reply['answer']),
                      passed=result.get('first_text_seconds') is not None and '#include' in reply['answer'])
        if not result['passed']:
            result['diagnostic_reply'] = reply['answer'][:500]
    finally:
        client.close()  # Only this verifier's question worker; never the shared Ollama server.


def ui(result):
    import gc
    import tkinter as tk
    import os
    from main import App
    from jarvis.ui_preview import export_preview
    from scripts.verification.verify_notch import keyed
    root = tk.Tk()
    root.withdraw()
    previous = os.environ.get('JARVIS_UI_VERIFY')
    os.environ['JARVIS_UI_VERIFY'] = '1'
    app = None
    try:
        app = App(root)
        for callback in root.tk.call('after', 'info'):
            root.after_cancel(callback)
        app.config.setdefault('ui', {})['reduced_motion'] = True
        root.geometry('614x600+20000+20000')
        root.deiconify()
        app.question.set('C++ game answer')
        event = {'phase': 'Generating answer', 'text': '```cpp\n#include <iostream>\n\nint main() {\n    int position = 1;\n    std::cout << "Snakes and ladders";\n'}
        app.island.notify('answer_stream', event)
        app.desk.notify('answer_stream', event)
        app.island.expand(True)
        for _ in range(3):
            app.island.tick('THINKING')
            root.update()
        path = BASE/'artifacts/media/answer-stream-preview.png'
        export_preview(app, path)
        from PIL import Image
        keyed(Image.open(path)).save(path)
        assert 'incomplete' in app.desk.answer_title.cget('text')
        assert app.desk.full_reply == event['text']
        assert not any(child.winfo_class() == 'Toplevel' for child in root.winfo_children())
        assert app.listener is None
        app.desk.notify('answer_stream', {'phase': 'Cancelled · incomplete', 'active': False})
        assert 'Cancelled' in app.desk.answer_title.cget('text')
        app.desk.notify('answer', 'Complete fixture answer')
        assert app.desk.answer_title.cget('text') == 'Jarvis · Answer'
        result.update(passed=True, scope='Authored off-screen widget fixture; not live Ollama output or a desktop screenshot.',
                      preview='artifacts/media/answer-stream-preview.png', single_window=True, complete_and_cancelled_labels=True)
    finally:
        if app:
            app.close()
        else:
            root.destroy()
        if previous is None:
            os.environ.pop('JARVIS_UI_VERIFY', None)
        else:
            os.environ['JARVIS_UI_VERIFY'] = previous
        app = root = None
        gc.collect()


def regression(result):
    from scripts.verification.verify_step_regression import run
    result['regression'] = run(['-m', 'unittest', 'discover', '-s', 'tests', '-q'])
    result['readiness'] = run(['-m', 'jarvis.launcher', '--check'])
    result.update(passed=result['regression']['exit_code'] == result['readiness']['exit_code'] == 0,
                  scope='Regression and launcher readiness; live generation and rendered fixture are separate.')


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'ui'
    if mode not in {'live', 'ui', 'regression'}:
        raise SystemExit('Use live, ui, or regression')
    result = {'date': datetime.now(timezone.utc).isoformat(), 'passed': False}
    try:
        {'live': live, 'ui': ui, 'regression': regression}[mode](result)
    except Exception as exc:
        result.update(passed=False, error=type(exc).__name__+': '+str(exc))
    destination = BASE/f'artifacts/answer-stream-{mode}-check.json'
    if destination.is_file():
        history = BASE/f'artifacts/answer-stream-{mode}-history.json'
        rows = json.loads(history.read_text(encoding='utf-8')) if history.is_file() else []
        rows.append(json.loads(destination.read_text(encoding='utf-8')))
        history.write_text(json.dumps(rows, indent=2)+'\n', encoding='utf-8')
    destination.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)
    raise SystemExit(0 if result['passed'] else 1)
