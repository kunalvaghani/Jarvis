"""Temporary anticipation fixtures, real worker protocol and hidden widget preview.

--live additionally performs one generic public search, never desktop actions.
No microphone, user activity, personal vault or user project is used as evidence.
"""
from jarvis.paths import APP_ROOT, artifact_path
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import time

from jarvis.anticipation import Anticipation
from jarvis.anticipation_worker import prepare

BASE = Path(__file__).resolve().parents[2]


def verify(live=False, ui=True):
    checks = {}
    sample = dict(kind='research',topic='Python asyncio',origin='request',authorized=True,
                  evidence='Sample explicit research request: Python asyncio',options=dict(public_search=False))
    # Use the real owned subprocess/JSON protocol without touching runtime storage.
    worker = Anticipation(BASE,dict(enabled=False),lambda *_:None)
    output = worker._worker(sample,lambda:False,15)
    checks['real_worker_protocol_offline_outline'] = 'Public search disabled' in output['content']
    worker.close()
    now = [10000.]
    fixture_sources = [dict(title='Python asyncio documentation (fixture)',
        href='https://docs.python.org/3/library/asyncio.html',body='Fixture snippet: async/await, tasks and cancellation.'),
        dict(title='Python task documentation (fixture)',href='https://docs.python.org/3/library/asyncio-task.html',
             body='Fixture snippet: task scheduling and cancellation.')]
    events=[]
    with tempfile.TemporaryDirectory(prefix='jarvis-anticipation-fixture-') as directory:
        service=Anticipation(directory,dict(idle_seconds=5,dwell_seconds=5,cooldown_seconds=30,expiry_seconds=60),
            lambda kind,value:events.append((kind,value)),clock=lambda:now[0],wall=lambda:now[0],
            runner=lambda request,cancelled,budget:prepare(request,search_fn=lambda _:fixture_sources))
        service.observe_request('task','research Python asyncio')
        service.tick()
        checks['waits_for_idle']=not service.rows
        now[0]+=6; service.tick()
        row=service.snapshot()['preparations'][0]
        checks['prepared_artifact_readback']=(service.directory/row['artifact']).read_text(encoding='utf-8')==row['content']
        checks['source_attribution_and_questions']='asyncio-task.html' in row['content'] and 'Unanswered questions' in row['content']
        checks['no_automatic_speech_or_popup']=all(k=='anticipation' for k,_ in events)
        now[0]+=61; service.tick()
        checks['expired_card_rejected']='expired' in service.handle('accept',row['id'])
        service.observe_window('JavaScript promises - Google Search - Google Chrome',123)
        now[0]+=6; service.tick()
        checks['window_inference_suggests_without_search']=service.rows[-1]['status']=='suggested'
        service.handle('accept',service.rows[-1]['id']); now[0]+=31; service.tick()
        checks['accepted_read_only_preparation']=service.rows[-1]['status']=='prepared'
        service.cancel(microphone=True); service.close()
        checks['shutdown_and_stop_retained']=service.microphone_stopped and not service.repair()
    live_result=None
    if live:
        live_worker=Anticipation(BASE,dict(enabled=False),lambda *_:None)
        try:
            live_output=live_worker._worker({**sample,'options':dict(public_search=True)},lambda:False,30)
            count=live_output.get('source_count',0)
            live_result=dict(source_count=count,passed=count>0,scope=live_output.get('scope'),
                retrieval_status=live_output.get('retrieval_status'),
                limitation='Search snippets only; no full pages, model synthesis, real user activity or prediction-accuracy evaluation.')
        except Exception as exc:
            live_result=dict(passed=False,error=str(exc)[:300],scope='Generic public search attempt')
        finally:
            live_worker.close()
    if ui:
        previous=os.environ.get('JARVIS_UI_VERIFY')
        os.environ['JARVIS_UI_VERIFY']='1'
        from main import App
        from jarvis.ui_preview import export_preview
        import tkinter as tk
        root=tk.Tk(); root.withdraw()
        app=None
        try:
            app=App(root)
            app.speech.options['enabled']=False
            fixture=prepare(sample,search_fn=lambda _:fixture_sources)
            # Explicitly marked sample data, and only native widgets are rendered.
            fixture['content']=row['content']
            app.desk.notify('anticipation',dict(preparations=[dict(id='non-executable-fixture',
                kind='research',topic='Python asyncio · sample',evidence='Sample browser/search activity; no actual activity captured.',
                mode='prepare',status='prepared',expires=time.time()+900,content=fixture['content'])]))
            app.desk.show('Prepared')
            app.desk.now.set('Now working · Ready\nPrepared work · sample research outline')
            for callback in root.tk.call('after','info'):
                root.after_cancel(callback)
            root.geometry('208x52+20000+20000'); root.deiconify()
            app.panel.geometry('720x820+20000+20000'); app.panel.deiconify()
            root.update()
            preview=artifact_path(BASE, 'anticipation-preview.png')
            export_preview(app,preview)
            checks['hidden_prepared_widgets_rendered']=bool(preview.is_file() and app.desk.views['Prepared'].winfo_ismapped())
            checks['no_microphone_or_real_vault']=app.listener is None and not app.actions.memory.enabled
            checks['anticipation_disabled_in_ui_verification']=not app.actions.anticipation.options['enabled']
        finally:
            if app: app.close()
            else: root.destroy()
            if previous is None: os.environ.pop('JARVIS_UI_VERIFY',None)
            else: os.environ['JARVIS_UI_VERIFY']=previous
    return dict(date=datetime.now(timezone.utc).isoformat(),checks=checks,passed=all(checks.values()),
        scope='Temporary synthetic activity/source fixtures, real offline worker protocol and hidden rendered widgets; not a live anticipation-quality benchmark.',
        live_public_search=live_result)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--no-ui',action='store_true')
    args=parser.parse_args()
    result=verify(args.live,not args.no_ui)
    output=artifact_path(BASE, 'anticipation-check.json')
    output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['passed'] else 1)
