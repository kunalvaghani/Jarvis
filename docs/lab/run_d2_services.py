"""Bounded real interface checks, existing public browser/CPU service only; no remote file writes."""
import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];APP=ROOT/'app';sys.path.insert(0,str(APP))
PROOF=APP/'.jarvis-runtime/lab-validation/d2-live-root'

def main():
    with (PROOF/'service-proof-once.json').open('x') as f:json.dump({'scope':'one public owned-session read; one existing resident CPU choice at most; no startup/download/Google writes'},f)
    from jarvis.neural.service import BrainService
    from jarvis.actions import Actions
    from jarvis.commands import Command
    from jarvis.engine import Engine
    from jarvis.control.web.extension_runner import ExtensionRunner
    from jarvis.discovery.adapters import lab_reads
    config={'neural':{'mode':'act','learning':'shadow'},'lab':{'enabled':True,'sim':True,'research':True,'learning':True}}
    s=BrainService(config,PROOF/'brain.sqlite3');a=Actions.__new__(Actions)
    a.config,a.base,a._neural_service,a.allowed_tools=config,APP,s,None;a.report=lambda *args:None
    a._approve=lambda *args:(_ for _ in ()).throw(ValueError('No external writes in service proof'))
    records=[]
    def execute(text,label):
        started=time.monotonic();error=None
        try:
            commands=[];engine=Engine(commands.append,lambda *args:None);engine.activate();engine.feed(text,final=True,raw=text)
            a.execute(commands[0])
        except Exception as exc:error=type(exc).__name__
        goal=s.journal.rows('SELECT goal_id,state FROM goals ORDER BY rowid DESC LIMIT 1')[0]
        records.append({'label':label,**goal,'seconds':time.monotonic()-started,'error_type':error})
    try:
        execute('lab read long "examples/discovery/d2-long.json"','real scoped long-read interface')
        execute('lab choose "examples/discovery/d2-choice.json"','exact label choice; no model')
        runner=ExtensionRunner(session='discovery-readiness')
        try:browser_ready=runner.available()
        finally:runner._drop()
        if browser_ready:execute('lab portal read "https://mujoco.readthedocs.io/en/stable/overview.html"','one public owned portal read')
        from jarvis.control.pc.laya import Resolver
        cpu_ready=lab_reads.cpu_resident(Resolver(timeout_s=3))
        before=s.journal.rows("SELECT COUNT(*) AS n FROM discovery_budget WHERE id LIKE 'd2-choice-%'")[0]['n']
        if cpu_ready:
            path=PROOF/'cpu-choice.json';path.write_text(json.dumps({'intent':'Choose the red color option','options':{'red':'Red','blue':'Blue','green':'Green'}}),encoding='utf-8')
            execute('lab choose "'+path.relative_to(APP).as_posix()+'"','one resident CPU Laya closed-choice attempt')
        after=s.journal.rows("SELECT COUNT(*) AS n FROM discovery_budget WHERE id LIKE 'd2-choice-%'")[0]['n']
        assert after-before<=1
        result={'date_local':'2026-11-04 Asia/Calcutta','operator_assisted_final_text_ingress':True,'microphone_used':False,
            'browser_already_connected':browser_ready,'cpu_checkpoint_already_resident':cpu_ready,
            'new_cpu_choice_attempts_upper_bound':after-before,'records':records,'new_google_writes':0,'new_services_started':0,
            'new_downloads_or_installs':0,'global_configuration_changed':False}
        (ROOT/'docs/lab/evidence/d2-services-live.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result))
    finally:s.journal.close()
if __name__=='__main__':main()
