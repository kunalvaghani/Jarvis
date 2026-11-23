"""Local text-ingress proof on an owned copy of real C4 history; no solver/model/native/UI execution."""
import argparse,hashlib,json,sqlite3,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];APP=ROOT/'app';sys.path.insert(0,str(APP))
PROOF=APP/'.jarvis-runtime/lab-validation/d-proof'
CONFIG={'neural':{'mode':'act','learning':'shadow'},'lab':{'enabled':True,'sim':True,'research':True,'learning':True}}

def phase(name):
    from jarvis.neural.service import BrainService
    if name=='off':
        s=BrainService({'neural':{'mode':'act'}},PROOF/'off.sqlite3')
        try:
            assert 'jarvis.discovery.d' not in sys.modules
            assert not any(n.startswith('discovery.') for n in s.graph.neurons)
            assert not s.journal.rows("SELECT name FROM sqlite_master WHERE name LIKE 'discovery_%'")
            return {'no_lab_import':True,'no_lab_neurons':True,'no_lab_tables':True}
        finally:s.journal.close()
    from jarvis.actions import Actions
    from jarvis.commands import Command
    from jarvis.engine import Engine
    from jarvis.discovery.memory import LabMemory
    s=BrainService(CONFIG,PROOF/'brain.sqlite3');a=Actions.__new__(Actions)
    a.config,a.base,a._neural_service,a.allowed_tools=CONFIG,APP,s,None
    def run(command):
        commands=[];engine=Engine(commands.append,lambda *args:None);engine.activate();engine.feed(command,final=True,raw=command)
        a.execute(commands[0]);row=s.journal.rows('SELECT ref FROM discovery_integration_snapshots ORDER BY rowid DESC LIMIT 1')[0]
        result=json.loads(s.journal.get(row['ref']))
        assert s.journal.rows('SELECT state FROM goals ORDER BY rowid DESC LIMIT 1')[0]['state']=='verified'
        return result
    try:
        before=run('lab audit integration')
        if name=='first':
            assert before['memory']['pending_links']>0 and not before['passed']
            after=run('lab memory wire');assert after['passed'] and not after['memory']['pending_links']
            assert after['inventory']['registered_count']==27
            native=next(n for n in after['inventory']['nodes'] if n['node_id']=='discovery.geometry.pendulum@v1')
            assert native['needs_approval']
            # Use real historic records, their Source context and the existing name resolver.
            m=LabMemory(s.journal);assert len(m.list('Experiment'))==4
            a.config={}
            try:a.execute(Command('task','lab audit integration'))
            except ValueError:blocked=True
            else:raise AssertionError('flags-off fell through')
            return {'before':before,'after':after,'flags_off_refused':blocked}
        assert before['passed'] and before['diff']=={'added':[],'removed':[],'changed':[]}
        return {'reused':before,'no_external_replay':True}
    finally:s.journal.close()

def main():
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['first','reuse','off']);args=p.parse_args()
    if args.phase:
        (PROOF/(args.phase+'.json')).write_text(json.dumps(phase(args.phase),indent=2),encoding='utf-8');return
    PROOF.mkdir(exist_ok=True)
    with (PROOF/'started.json').open('x') as f:json.dump({'scope':'existing local read-only audit/wiring, no inference or solver calls'},f)
    original=APP/'.jarvis-runtime/lab-validation/c4-proof-final/brain.sqlite3'
    digest=hashlib.sha256(original.read_bytes()).hexdigest()
    source=sqlite3.connect(original.resolve().as_uri()+'?mode=ro',uri=True);target=sqlite3.connect(PROOF/'brain.sqlite3')
    try:source.backup(target)
    finally:target.close();source.close()
    for name in ('first','reuse','off'):
        result=subprocess.run([sys.executable,'-B',__file__,'--phase',name],timeout=90,capture_output=True)
        if result.returncode:
            print(result.stderr.decode(errors='replace')[-2500:]);raise RuntimeError('proof failed: '+name)
    assert hashlib.sha256(original.read_bytes()).hexdigest()==digest
    result={'date_local':'2026-11-04 Asia/Calcutta','operator_assisted':True,'real_C4_source_unchanged':True,
            'original_source_sha256':digest,'new_model_solver_native_calls':0,'new_dependencies':[],
            **{name:json.loads((PROOF/(name+'.json')).read_text()) for name in ('first','reuse','off')}}
    (ROOT/'docs/lab/evidence/d-brain-proof.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'state':'passed','neurons':result['first']['after']['inventory']['registered_count'],
        'backfilled_links':result['first']['before']['memory']['pending_links'],'fresh_process_passed':result['reuse']['reused']['passed']}))
if __name__=='__main__':main()
