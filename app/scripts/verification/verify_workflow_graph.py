"""Owned live SQLite/Actions/Engine/Island exercise; no mic or account effects.

Writes only a fresh acceptance directory. This is a short overnight-mode batch,
not an elapsed overnight endurance claim. Optional inference is not substituted.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import sys
import time
import tkinter as tk
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from jarvis.actions import Actions
from jarvis.commands import Command
from jarvis.engine import Engine
from jarvis.island_queue import QueueView
from scripts.verification.render_queue_fixture import capture


def main(out):
    out.mkdir(parents=True,exist_ok=False)
    events=[]
    config={'files_root':'files','apps':{},'project_roots':[str(out/'files')],
            'task_queue':{'enabled':True},'knowledge':{'enabled':False}}
    for name in ['memory','cognition','anticipation','realtime','self_evolution','viking_memory','knowledge_acquisition','exploration']:
        config[name]={'enabled':False}
    actions=Actions(config,out,lambda kind,value:events.append((kind,value)))
    ingress=actions.ingress;store=ingress.store;scheduler=ingress.scheduler
    root=tk.Tk();root.title('Jarvis workflow graph — owned acceptance, microphone OFF');root.geometry('614x660+20+20')
    app=SimpleNamespace(actions=actions,report=actions.report)
    view=QueueView(root,app)
    result={'started_at':datetime.now(timezone.utc).isoformat(),'microphone_started':False,'account_effects':False,
            'scope':'Real Actions file handlers, Engine typed intake, SQLite graph, mapped 20-second decisions and native QueueView; bounded batch, not overnight endurance'}
    def wait_for(check, timeout=40):
        until=time.monotonic()+timeout
        while time.monotonic()<until:
            root.update();view.tick()
            if check():return
            time.sleep(.03)
        raise TimeoutError('Owned workflow acceptance condition did not finish')
    try:
        store.setting('paused',True)
        actions.start()
        engine=Engine(actions.submit,lambda *_:None);engine.activate()
        order=list(range(10));random.Random(24).shuffle(order)
        for number in order:
            phrase=f'create file workflow acceptance {number}'
            engine.feed(phrase,final=True,raw=phrase)
        readonly=[ingress.submit(Command('jarvis_status','uptime')),ingress.submit(Command('system_info','memory'))]
        wait_for(lambda:len(store.rows())==12 and all(r['state']=='QUEUED' for r in store.rows()))
        files={int(r['command']['value'].removesuffix('.txt').split()[-1]):r['id'] for r in store.rows() if r['command']['kind']=='create'}
        assert len(files)==10
        workflow=scheduler.graph.node(files[0])['workflow']
        other_workflow=scheduler.graph.node(files[5])['workflow']
        for i,task in files.items():scheduler.graph.move(task,workflow if i<5 else other_workflow)
        for n in (1,2,3,4):scheduler.graph.set_dependencies(files[n],[files[0]] if n<3 else [files[1],files[2]])
        for n in (6,7,8,9):scheduler.graph.set_dependencies(files[n],[files[5]] if n<8 else [files[6],files[7]])
        decision=ingress.propose_strategies('Routine read-only branch order',
            {'Independent observations':{readonly[1]:[]},'Sequential observations':{readonly[1]:[readonly[0]]}},
            confidence=.95,reversible=True,sensitive=False)
        wait_for(lambda:any(d['id']==decision and d['status']=='SELECTED' for d in ingress.decisions.rows()),30)
        graph_decision=next(d for d in ingress.decisions.rows() if d['id']==decision)
        assert graph_decision['automatic'] and store.setting('graph_decision_applied:'+decision)
        result['graph_decision']=graph_decision
        groups=scheduler.graph.snapshot()['groups']
        for group in groups:scheduler.graph.update_group(group['id'],paused=True)
        actions.submit(Command('task','run the queue overnight'))
        wait_for(lambda:any(d['question']=='Overnight scheduling preference' for d in ingress.decisions.rows()))
        wait_for(lambda:any(d['question']=='Overnight scheduling preference' and d['status']=='SELECTED' for d in ingress.decisions.rows()),30)
        result['overnight_decision']=next(d for d in ingress.decisions.rows() if d['question']=='Overnight scheduling preference')
        for group in groups:scheduler.graph.update_group(group['id'],paused=False)
        wait_for(lambda:all(store.get(t)['state']=='COMPLETED' for t in list(files.values())+readonly),60)
        report,path=scheduler.report(out/'reports')
        receipts=[]
        for number,task in sorted(files.items()):
            row=store.get(task);receipt=scheduler.graph.result(task)
            assert receipt and receipt['verification']=='verified'
            for artifact in receipt['artifacts']:
                assert hashlib.sha256(Path(artifact['path']).read_bytes()).hexdigest()==artifact['sha256']
            assert row['checkpoint']['input_versions']=={e['upstream']:1 for e in scheduler.graph.edges(task)}
            receipts.append({'task':task,'number':number,'result':receipt})
        result.update(passed=True,files=receipts,report=str(path),graph=report['graph'],
                      completed=sum(r['state']=='COMPLETED' for r in store.rows()),
                      decisions=ingress.decisions.rows(),counts=store.counts())
        view.tick();view.groups.selection_set(scheduler.graph.group_for(files[0])['id']);view.group_action('inspect')
        root.update_idletasks();root.update()
        painted=tk.BooleanVar(value=False)
        root.after(300,lambda:painted.set(True));root.wait_variable(painted)
        import ctypes
        hwnd=ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
        try:
            capture(hwnd,out/'native-workflow-current.png');result['native_capture']='native-workflow-current.png'
        except RuntimeError as exc:result['native_capture_error']=str(exc)
    except BaseException as exc:
        result.update(passed=False,error=type(exc).__name__+': '+str(exc),rows=store.rows())
        raise
    finally:
        result['finished_at']=datetime.now(timezone.utc).isoformat()
        (out/'acceptance.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        root.destroy();actions.close()
    print(json.dumps({'passed':result['passed'],'completed':result['completed'],'receipt':str(out/'acceptance.json')}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args().output.resolve())
