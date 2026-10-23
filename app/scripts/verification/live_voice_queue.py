"""User-started headphone/microphone acceptance in an owned fixture workspace.

Uses the actual Listener, Engine, Actions, durable queue and native QueueView.
Only ten named fixture-create commands and overnight control are admitted.
Unknown audio/text is neither retained nor dispatched. No recordings are saved.
"""
import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import queue
import re
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk

BASE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(BASE))
from jarvis.actions import Actions
from jarvis.audio import Listener
from jarvis.commands import Command
from jarvis.engine import Engine
from jarvis.island_queue import QueueView

WORDS='one two three four five six seven eight nine ten'.split()


def fixture_command(command):
    """Accept only numbered fixture names; ASR may spell numbers as digits."""
    if command.kind == 'task' and command.value.strip().lower().rstrip('.!?') in {
            'run the queue overnight','run queue overnight','run all queued tasks overnight'}:
        return Command('task','run the queue overnight')
    if command.kind != 'create' or command.extra:
        return None
    match=re.fullmatch(r'live\s*(one|two|three|four|five|six|seven|eight|nine|ten|10|[1-9])(?:\.txt)?', command.value.strip(), re.I)
    if not match:return None
    number=match[1].lower()
    word=WORDS[int(number)-1] if number.isdigit() else number
    return Command('create',f'live {word}.txt')


def main(output):
    session=str(int(time.time()))
    owned=BASE/'.jarvis-runtime'/'live-queue'/session
    owned.mkdir(parents=True,exist_ok=False)
    config=json.loads((BASE/'config/config.json').read_text(encoding='utf-8'))
    test=copy.deepcopy(config)
    test.update(files_root='files',apps={},project_roots=[str(owned/'files')])
    for name in ['memory','cognition','anticipation','realtime','self_evolution','viking_memory','knowledge_acquisition','exploration']:
        test.setdefault(name,{})['enabled']=False
    test['task_queue']['prevent_sleep']=False
    test['knowledge']['enabled']=False
    events=queue.Queue()
    receipt={'started_at':datetime.now(timezone.utc).isoformat(),'scope':'User-started physical headphone/microphone -> actual Listener/Engine/Actions/durable queue, owned fixture files only',
             'recordings_saved':False,'private_audio_uploaded':False,'unknown_commands_dispatched':0,'ignored_commands':0,'received_while_worker_held':0}
    release=threading.Event();held=threading.Event();stopping=threading.Event()
    listener=None
    def report(kind,message=''):
        # Deliberately exclude arbitrary recognized speech/partial text from logs.
        if kind in {'state','backend','fatal','task_received','task_decision','task_report','level'}:
            events.put((kind,message))
    actions=Actions(test,owned,report)
    original=actions.execute
    def execute(command,cancelled):
        if command.kind=='create' and not held.is_set():
            held.set()
            deadline=time.monotonic()+660
            while not release.wait(.1) and not cancelled():
                if time.monotonic()>deadline:raise TimeoutError('User test hold expired before release')
        return original(command,cancelled)
    actions.execute=execute
    expected={f'live {word}.txt' for word in WORDS}
    def submit(command):
        if stopping.is_set():return
        safe=fixture_command(command)
        if safe is not None:
            if held.is_set() and not release.is_set():receipt['received_while_worker_held']+=1
            actions.submit(safe)
            events.put(('feedback','Accepted fixture: '+safe.value))
        else:
            receipt['ignored_commands']+=1
            events.put(('feedback','Rejected command category: '+command.kind+' (only fixture commands are allowed)'))
    engine=Engine(submit,report,timeout=600)
    class PreviewEngine:
        def __getattr__(self,name):return getattr(engine,name)
        def activate(self):engine.activate()
        def feed(self,text,final=False,**kwargs):
            # Ephemeral local feedback only: never copy recognized text into receipt.
            if final:events.put(('recognized',text))
            return engine.feed(text,final=final,**kwargs)
    root=tk.Tk();root.title('Jarvis live acceptance — owned fixture tasks only');root.geometry('1180x850')
    state=tk.StringVar(value='Microphone OFF. Click Start when ready; the existing Jarvis listener stays stopped.')
    ttk.Label(root,textvariable=state,wraplength=1100,font=('Segoe UI',11,'bold')).pack(fill='x',pady=6)
    level=tk.DoubleVar(value=0)
    ttk.Label(root,text='Microphone input level (this test does not speak audio responses):').pack(anchor='w')
    ttk.Progressbar(root,variable=level,maximum=100).pack(fill='x')
    feedback=tk.StringVar(value='No fixture commands accepted yet.')
    ttk.Label(root,textvariable=feedback,wraplength=1100).pack(fill='x')
    recognized=tk.StringVar(value='Last final recognition appears here locally; it is never saved.')
    ttk.Label(root,textvariable=recognized,wraplength=1100).pack(fill='x')
    ttk.Label(root,text='Speak these as separate requests, without waiting for completion:\n'+
        '  '.join(f'Jarvis, create file live {word}.' for word in WORDS)+
        '\nThen say: Jarvis, run the queue overnight. Leave the displayed preference unanswered for 20 seconds, then click Finish.\n'
        'The first worker is intentionally held until Finish to verify continuous intake. No audio or unknown speech is saved.',wraplength=1120).pack(fill='x',pady=5)
    buttons=ttk.Frame(root);buttons.pack(fill='x')
    app=type('ProbeApp',(),{'actions':actions,'report':staticmethod(report)})()
    view=QueueView(root,app)
    started_at=None
    def start():
        nonlocal listener,started_at
        if listener is not None:return
        started_at=time.monotonic();receipt['microphone_started_by_user']=True
        state.set('Loading existing local ASR. Wait for the Listening status before speaking.')
        options=copy.deepcopy(config['whisper'])
        receipt['voice_profile']={'model_path':config['model_path'],'whisper':options,'microphone':config.get('microphone')}
        from jarvis.command_cleanup import CommandCleanup
        listener=Listener(BASE/config['model_path'],config.get('microphone'),PreviewEngine(),report,options,
            activate_on_start=True,command_cleanup=CommandCleanup(config.get('command_cleanup'),report))
        listener.start();start_button.configure(state='disabled')
    def finish():
        if stopping.is_set():return
        stopping.set();release.set()
        state.set('Stopping owned microphone probe and finishing admitted fixture jobs…')
        finish_button.configure(state='disabled')
        def collect():
            if listener is not None:listener.stop()
            deadline=time.monotonic()+30
            while actions.queue.unfinished_tasks or actions.queue.qsize():
                if time.monotonic()>deadline:break
                time.sleep(.05)
            ingress=actions.ingress
            rows=ingress.store.rows()
            decisions=ingress.decisions.rows()
            observed={name:(actions.root/name).is_file() for name in sorted(expected)}
            task_rows=[r for r in rows if r['command']['kind']=='create']
            receipt.update(finished_at=datetime.now(timezone.utc).isoformat(),
                capture_started=bool(listener and listener.capture_started),
                asr_decode_metrics=list(listener.decode_metrics) if listener else [],
                fixture_files=observed,task_states=[{'number':r['number'],'state':r['state'],'fixture':r['command']['value']} for r in task_rows],
                decisions=decisions,all_ten_files_verified=all(observed.values()),
                ten_distinct_jobs=len(task_rows)==10 and len({r['command']['value'] for r in task_rows})==10,
                all_jobs_completed=len(task_rows)==10 and all(r['state']=='COMPLETED' for r in task_rows),
                automatic_routine_decision=any(d['automatic'] and d['status']=='SELECTED' for d in decisions),
                probe_seconds=(time.monotonic()-started_at) if started_at else 0)
            receipt['passed']=all(receipt.get(k,False) for k in ['capture_started','all_ten_files_verified','ten_distinct_jobs','all_jobs_completed','automatic_routine_decision']) and receipt['received_while_worker_held']>=9
            output.parent.mkdir(parents=True,exist_ok=True)
            output.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            actions.close()
            events.put(('finished',receipt['passed']))
        threading.Thread(target=collect,name='Owned voice acceptance finalizer',daemon=True).start()
    start_button=ttk.Button(buttons,text='Start microphone test',command=start);start_button.pack(side='left')
    finish_button=ttk.Button(buttons,text='Finish and save receipt',command=finish);finish_button.pack(side='left')
    def tick():
        while True:
            try:kind,message=events.get_nowait()
            except queue.Empty:break
            if kind=='finished':
                state.set(('PASS' if message else 'Acceptance incomplete/failed — inspect receipt')+' · '+str(output))
                root.after(3000,root.destroy);return
            if kind=='level':level.set(float(message))
            elif kind=='recognized':recognized.set('Heard locally: '+str(message))
            elif kind=='feedback':feedback.set(str(message))
            elif kind=='fatal':state.set('Microphone error: '+str(message))
            elif kind in {'state','backend'} and not (listener and listener.capture_started):state.set(str(message))
        if listener and listener.capture_started and not stopping.is_set():
            state.set('Listening · input capture active · speak one fixture request at a time')
        view.tick()
        if started_at and time.monotonic()-started_at>600 and not stopping.is_set():finish()
        root.after(200,tick)
    root.protocol('WM_DELETE_WINDOW',finish)
    actions.start();root.after(100,tick)
    print('LIVE_PROBE_READY: user must click Start; microphone is currently off.',flush=True)
    root.mainloop()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args().output)
