"""JRV-37-021: real owned child crash/queue/Tk readback; mock outbox, no account or audio."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
from unittest.mock import Mock, patch

APP = Path('D:/Kunals GitHub Repo/LocalGithub/Jarvis-e2e-e5af0e7/app')
sys.path.insert(0, str(APP))
os.environ['JARVIS_UI_VERIFY'] = '1'

CHILD = '''import os,sys
from pathlib import Path
from jarvis.actions import Actions
from jarvis.commands import Command
base=Path(sys.argv[1])
actions=Actions({'files_root':'files','apps':{},'memory':{'enabled':False}},base,lambda *args:None)
def interrupted(goal,cancelled):
    with (base/'owned-outbox.jsonl').open('a',encoding='utf-8') as output:
        output.write('{"mock_delivery_attempt":1}\\n')
    actions.task_state.checkpoint('uncertain_external_write',action='send',target='owned-mock')
    os._exit(27)
actions.brain.run=interrupted
actions.start()
actions.submit(Command('task','send a synthetic fixture message'))
actions.queue.join()
'''


def test_JRV_37_021_crashed_mock_send_restart_reaches_actual_tk_text(tmp_path):
    done = subprocess.run([sys.executable, '-c', CHILD, str(tmp_path)], cwd=APP,
                          capture_output=True, timeout=30)
    assert done.returncode == 27, done.stderr.decode(errors='replace')
    outbox = tmp_path / 'owned-outbox.jsonl'
    assert len(outbox.read_text().splitlines()) == 1

    import tkinter as tk
    from main import App
    from jarvis.actions import Actions
    from jarvis.commands import Command
    from jarvis.interface import build_interface
    root = tk.Tk()
    root.withdraw()
    ui = Mock()
    ui.root = root
    ui.config = {'_ui_verification': True, 'whisper': {'model': 'fixture'}, 'knowledge': {}}
    ui.speech.options = {'enabled': False}
    ui.events = queue.Queue()
    ui.runtime_health = None
    ui.closing = False
    ui.ui_failures = {}
    build_interface(ui)
    ui.panel.withdraw()
    report = lambda kind, message: App.report(ui, kind, message)
    actions = Actions({'files_root': 'files', 'apps': {}, 'memory': {'enabled': False}}, tmp_path, report)
    ui.actions = actions
    actions.brain.run = Mock(side_effect=AssertionError('uncertain send must not reach planner'))
    captured_events = []
    try:
        restored = actions.task_state.snapshot()
        assert restored['status'] == 'interrupted'
        assert restored['uncertain_external_writes']
        actions.start()
        actions.submit(Command('resume_task'))
        actions.queue.join()
        with ui.events.mutex:
            captured_events = list(ui.events.queue)
        # Run the actual event consumer. Bypass only recovery's exception-swallowing scheduler wrapper.
        with patch('main.record'):
            for _ in range(20):
                if ui.events.empty(): break
                App.drain.__wrapped__(ui)
        assert ui.events.empty()
        root.update_idletasks()
        rendered = ui.desk.overview.get('1.0', 'end-1c')
        live = ui.live.get()
        assert 'Task paused:' in rendered and 'uncertain' in rendered
        assert 'Task paused:' in live and 'uncertain' in live
        assert 'Message sent' not in rendered
        assert ui.speech.say.call_count == 1
        assert 'Task paused:' in ui.speech.say.call_args.args[0]
        actions.brain.run.assert_not_called()
        assert len(outbox.read_text().splitlines()) == 1
        assert actions.task_state.snapshot()['uncertain_external_writes']
        record = {'id': 'JRV-37-021', 'source_sha': 'e5af0e700517bac5fb48dcebc8f6cc9c9df9a369',
            'classification': 'real owned child crash, Actions restart/queue, App report/drain and Tk widgets; simulated send and speech sink',
            'input': 'queued mock send; child exits 27 after uncertain checkpoint; restart; resume task',
            'actual_components': ['Actions.submit', 'Actions worker', 'TaskState.checkpoint', 'process os._exit(27)',
                'TaskState reload', 'Actions resume_task', 'App.report', 'App.drain', 'Island.notify', 'Desk.notify', 'Tk Text readback'],
            'postconditions': {'child_exit': done.returncode, 'mock_outbox_rows': 1, 'restored_state': restored['status'],
                'ui_overview': rendered, 'live_text': live, 'speech_sink_calls': ui.speech.say.call_count,
                'planner_calls_after_restart': actions.brain.run.call_count, 'uncertain_writes_retained': True},
            'real_sends': 0, 'real_audio_or_mic': 0, 'desktop_capture': False, 'status': 'PASS'}
        (Path(__file__).parent / 'ui-restart-journal.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    finally:
        actions.close()
        ui.desk.close()
        root.destroy()
