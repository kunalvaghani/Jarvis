"""Real offscreen Tk widgets, synthetic button invocation, no external executor."""
import json
from pathlib import Path
import threading
import time

import pytest


@pytest.mark.parametrize('approve', [True, False], ids=['approve', 'close-denies'])
def test_request_event_card_readback_and_decision(approve):
    import main
    from jarvis.ui_events import UIEventBuffer
    from tests.test_island_desk import DeskWidgetTests
    fixture = DeskWidgetTests()
    fixture.setUp()
    thread = None
    stop = threading.Event()
    result = []
    payloads = []
    try:
        app = fixture.app
        buffer = UIEventBuffer()
        def report(kind, value):
            payloads.append(value)
            buffer.put((kind, value))
        app.report = report
        thread = threading.Thread(target=lambda: result.append(main.App.request_approval(
            app, 'fixture', 'Owned fixture only; no external effect', stop.is_set)))
        thread.start()
        until = time.monotonic() + 3
        while buffer.empty() and time.monotonic() < until:
            time.sleep(.005)
        kind, value = buffer.get_nowait()
        app.desk.notify(kind, value)
        app.root.update()
        readback = app.desk.approval_text.get('1.0', 'end').strip()
        assert 'Owned fixture only; no external effect' in readback
        assert app.desk.view == 'Approval' and not value[3].is_set()
        if approve:
            until = time.monotonic() + 3
            while app.desk.approve_button.instate(['disabled']) and time.monotonic() < until:
                app.root.update()
                time.sleep(.01)
            assert not app.desk.approve_button.instate(['disabled'])
            app.desk.approve_button.invoke()  # synthetic invocation of the real Tk widget
        else:
            app.desk.cancel_approvals()
        thread.join(3)
        assert not thread.is_alive() and result == [approve]
        assert value[3].is_set() and value[2]['approved'] is approve
        from jarvis.approval_receipt import approval_digest
        if approve:
            assert value[2]['digest'] == approval_digest('fixture', 'Owned fixture only; no external effect')
            assert len(value[2]['token']) == 32
        path = Path(__file__).parent / ('widget-readback-approve.json' if approve else 'widget-readback-close.json')
        path.write_text(json.dumps({'scope': 'offscreen real Tk; synthetic input; no executor',
            'rendered_text': readback, 'request_result': result[0], 'ready': value[3].is_set(),
            'receipt_digest_present': 'digest' in value[2], 'external_executor_calls': 0}, indent=2), encoding='utf-8')
    finally:
        stop.set()
        if thread:
            thread.join(1)
        fixture.tearDown()
