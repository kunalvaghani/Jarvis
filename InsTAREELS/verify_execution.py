"""Independent native fixture checks and timing; no general accuracy claims."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

BASE = Path(__file__).resolve().parent


def main():
    import win32gui
    from jarvis.ui_worker import perform
    from jarvis.execution_adapters import PROVIDERS
    from jarvis.direct_execution import run
    from jarvis.task_state import TaskState
    folder = BASE / '.jarvis-runtime/execution-fixture' / str(time.time_ns())
    folder.mkdir(parents=True)
    path = folder / 'state.json'
    original = win32gui.GetForegroundWindow()
    process = subprocess.Popen([sys.executable, str(BASE / 'tests/execution_native_fixture.py'), str(path)],
        cwd=BASE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    result = {'date': datetime.now(timezone.utc).isoformat(),
              'scope': 'Live own Win32 fixture only; independent native text/counter readback. No user app automation, microphone, Qwen, clipboard or network. Timing is warm action/observation latency, not arbitrary task latency.',
              'provider_checks': [], 'direct_workflow': {}, 'passed': False}
    handles, transport = {}, None
    try:
        deadline = time.monotonic() + 10
        while not path.exists() and time.monotonic() < deadline and process.poll() is None:
            time.sleep(.05)
        if not path.exists():
            raise RuntimeError('Native fixture did not start: ' + (process.stderr.read().decode() if process.poll() is not None else 'timeout'))
        handles = json.loads(path.read_text())['handles']
        def text_readback(expected):
            # GetWindowText intentionally does not retrieve cross-process Edit text.
            # The fixture reads its own native child and publishes atomic snapshots.
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline:
                if json.loads(path.read_text())['text'] == expected:
                    return True
                time.sleep(.02)
            return False
        root = handles['root']
        from pywinauto import Desktop
        Desktop(backend='uia').window(handle=root).wrapper_object().set_focus()
        if win32gui.GetForegroundWindow() != root:
            raise RuntimeError('The owned fixture could not take focus; no test input issued.')
        basic = {'handle': root, 'owner_pid': os.getpid()}
        initial = perform({'operation': 'list', **basic})
        result['fixture_controls'] = [{'name': c['name'], 'role': c['role']} for c in initial['controls']]
        edits = [c for c in initial['controls'] if c['role'] == 'Edit']
        if len(edits) != 1:
            raise RuntimeError('Expected exactly one accessible Edit field.')
        # Force each adapter in the test process only. Production has no priority override.
        for provider in PROVIDERS:
            row = {'provider': provider.name}
            with patch('jarvis.execution_router.PROVIDERS', (provider,)):
                snapshot = perform({'operation': 'list', **basic})
                target = next(c for c in snapshot['controls'] if c['role'] == 'Edit')
                content = 'Verified ' + provider.name + ' café हिन्दी'
                started = time.monotonic()
                try:
                    receipt = perform({'operation': 'fill_text', 'control': target, 'content': content, **basic})
                    row['fill_seconds'] = round(time.monotonic() - started, 4)
                    row['fill_receipt'] = receipt
                    row['fill_readback'] = text_readback(content)
                except ValueError as exc:
                    row['fill_unavailable'] = str(exc)
                before = json.loads(path.read_text())['clicks']
                snapshot = perform({'operation': 'list', **basic})
                target = next(c for c in snapshot['controls'] if c['role'] == 'Button')
                started = time.monotonic()
                receipt = perform({'operation': 'activate', 'control': target, 'verb': 'click', **basic})
                row['click_seconds'] = round(time.monotonic() - started, 4)
                row['click_receipt'] = receipt
                deadline = time.monotonic() + 1
                while json.loads(path.read_text())['clicks'] <= before and time.monotonic() < deadline:
                    time.sleep(.02)
                row['clicked_once'] = json.loads(path.read_text())['clicks'] == before + 1
                if not row['clicked_once']:
                    raise AssertionError('Click count did not increase exactly once: ' + provider.name)
            result['provider_checks'].append(row)
        # Exercise the same persistent IPC worker used by a running Jarvis.
        from jarvis.ui_transport import UITransport
        transport = UITransport(BASE)
        warm_started = time.perf_counter()
        ping = transport.request({'operation': 'ping'})
        worker_pid = transport.process.pid
        result['worker'] = {'ping_ready': ping['ready'],
                            'startup_seconds': round(time.perf_counter() - warm_started, 4)}
        ui = SimpleNamespace(_handle=lambda: root, runner=transport.request)
        brain = Mock()
        brain.run.side_effect = AssertionError('Recognized fixture must not call Qwen')
        actions = SimpleNamespace(_ui=lambda: ui, task_state=TaskState(folder), config={},
                                  report=Mock(), brain=brain, resume_source=None)
        actions.task_state.start('native direct fixture', 'task')
        snapshot = transport.request({'operation': 'list', **basic})
        label = next(c['name'] for c in snapshot['controls'] if c['role'] == 'Edit')
        started = time.monotonic()
        message = run(actions, f'fill {label} field with Jarvis exact literal then select Enabled', lambda: False)
        result['direct_workflow'] = {'message': message, 'seconds': round(time.monotonic()-started, 4),
            'model_calls': brain.run.call_count, 'text_readback': text_readback('Jarvis exact literal'),
            'checkbox_readback': win32gui.SendMessage(handles['check'], 0x00F0, 0, 0) == 1,
            'stage': actions.task_state.snapshot()['stage']}
        result['worker']['same_process_reused'] = transport.process.pid == worker_pid
        before_cancel = json.loads(path.read_text())['clicks']
        try:
            transport.request({'operation': 'activate', **basic}, lambda: True)
        except ValueError:
            result['worker']['cancel_before_dispatch'] = json.loads(path.read_text())['clicks'] == before_cancel
        transport.close()
        result['worker']['closed'] = transport.closed.is_set() and transport.process is None
        direct = result['direct_workflow']
        providers_ok = all(row['clicked_once'] and (row.get('fill_readback') is True
                          if row['provider'] != 'agent-s' else 'fill_unavailable' in row)
                           for row in result['provider_checks'])
        worker_ok = all(result['worker'].get(key) is True for key in
                        ('ping_ready', 'same_process_reused', 'cancel_before_dispatch', 'closed'))
        result['passed'] = providers_ok and worker_ok and direct['text_readback'] and direct['checkbox_readback'] and direct['model_calls'] == 0 and direct['stage'] == 'goal_verified'
    except Exception as exc:
        result['error'] = type(exc).__name__ + ': ' + str(exc)
    finally:
        if transport is not None:
            transport.close()
        if handles and win32gui.IsWindow(handles['root']):
            if win32gui.GetForegroundWindow() == handles['root'] and win32gui.IsWindow(original):
                try:
                    win32gui.SetForegroundWindow(original)
                except Exception:
                    pass
            win32gui.PostMessage(handles['root'], 0x0010, 0, 0)
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.terminate()  # This process was created and owned by this verifier.
            process.wait(timeout=3)
        if process.stderr:
            result['fixture_stderr'] = process.stderr.read().decode(errors='replace')[-1000:]
            process.stderr.close()
        destination = BASE / 'artifacts/execution-native-check.json'
        if destination.exists():
            history = destination.with_name('execution-native-history.json')
            rows = json.loads(history.read_text(encoding='utf-8')) if history.exists() else []
            rows.append(json.loads(destination.read_text(encoding='utf-8')))
            history.write_text(json.dumps(rows, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
        destination.write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
