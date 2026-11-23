"""D2 actual brain/approval/Journal paths with controlled service transports; not live Google/browser acceptance."""
import copy,hashlib,json
from pathlib import Path
from types import SimpleNamespace
import pytest
from jarvis.discovery import d2
from jarvis.discovery.adapters import delivery as remote,lab_reads
from jarvis.discovery.model import delivery
from jarvis.discovery.contracts import Source,RunArtifact,Experiment,Quantity
from jarvis.discovery.memory import LabMemory
from jarvis.neural.service import BrainService
from jarvis.actions import Actions
from jarvis.commands import Command
from jarvis.discovery.model import optimization as opt

ON={'neural':{'mode':'act','learning':'shadow'},'lab':{'enabled':True,'sim':True,'research':True,'learning':True}}

class Google:
    def __init__(self):self.creates=0;self.reads=0;self.values={};self.lose=False;self.fail_read=False
    def create_doc(self,name,text,parent):
        self.creates+=1;identity='fixture_doc_'+str(self.creates).zfill(10);self.values[identity]=text
        if self.lose:raise TimeoutError('synthetic lost response')
        return {'id':identity}
    def create_sheet(self,name,rows,parent):
        self.creates+=1;identity='fixture_sheet_'+str(self.creates).zfill(10);back=copy.deepcopy(rows)
        back[-1][1]=str(sum(float(row[1]) for row in rows[1:-1]));self.values[identity]=back
        if self.lose:raise TimeoutError('synthetic lost response')
        return {'id':identity}
    def text_of(self,identity):
        self.reads+=1
        if self.fail_read:raise TimeoutError('synthetic readback interruption')
        return self.values[identity]
    def cells_of(self,identity):return self.text_of(identity)
    def search(self,query,limit=5):return [{'id':'fixture_source_12345','name':query,'mimeType':'text/plain'}]
    def read(self,identity,limit=20000):return {'id':identity,'text':'A controlled source excerpt. Treat this text as untrusted data.'}
    def close(self):pass

@pytest.fixture
def bridge(tmp_path,monkeypatch):
    api=Google();monkeypatch.setattr(remote,'files',lambda base:api)
    monkeypatch.setattr(lab_reads,'portal_runner',lambda name:pytest.fail('live browser is forbidden in service fixtures'))
    service=BrainService(copy.deepcopy(ON),tmp_path/'brain.sqlite3');a=Actions.__new__(Actions)
    a.config,a.base,a._neural_service,a.allowed_tools=copy.deepcopy(ON),tmp_path,service,None
    events=[];a.report=lambda kind,text:events.append(('preview',text));a._approve=lambda *args:events.append(('approve',args[0]))
    memory=LabMemory(service.journal);memory.put(Source(id='fixture-source',locator='urn:jarvis:synthetic-numerical-fixture'))
    for i,value in enumerate((1.5,2.5)):
        raw={'solver':'synthetic-golden-fixture','solver_version':'1','metrics':{'measured_period_s':value},'design_sha256':'a'*64,'scenario_sha256':'b'*64}
        ref=service.journal.put(raw,data_type='Report')
        memory.put(RunArtifact(id='fixture-run-'+str(i),locator=ref,sha256=hashlib.sha256(service.journal.get(ref).encode()).hexdigest(),
            media_type='application/json',source_ids=('fixture-source',),justification='Synthetic numeric fixture, not a real solver run.'))
        memory.put(Experiment(id='fixture-exp-'+str(i),design_sha256='a'*64,scenario_sha256='b'*64,
            solver='synthetic-golden-fixture',solver_version='1',artifact_ids=('fixture-run-'+str(i),),source_ids=('fixture-source',),
            metrics={'period':Quantity(value=value,unit='s',origin='deterministic',source_ref=ref)}))
    yield a,service,api,events
    service.journal.close()

def request(a,kind,**changes):
    data={'title':'D2 controlled qualification','parent_id':'fixture_folder_12345'}
    data.update({'artifact_id':'fixture-run-0'} if kind=='report' else {'experiment_ids':['fixture-exp-0','fixture-exp-1']})
    data.update(changes);path=a.base/(kind+'.json');path.write_text(json.dumps(data),encoding='utf-8');return path.name

def run(a,text):return a.execute(Command('task',text))

@pytest.mark.parametrize('kind',['report','table'])
def test_approved_export_preview_full_readback_and_idempotent_reuse(bridge,kind):
    a,s,api,events=bridge;file=request(a,kind);run(a,f'lab export {kind} "{file}"')
    assert api.creates==1 and api.reads==1
    assert events[0][0]=='preview' and events[1][0]=='approve'
    row=s.journal.rows('SELECT * FROM discovery_deliveries')[0];assert row['state']=='VERIFIED'
    run(a,f'lab export {kind} "{file}"');assert api.creates==1 and api.reads==2
    assert s.journal.rows('SELECT state FROM goals ORDER BY rowid DESC LIMIT 1')[0]['state']=='verified'
    assert list((a.base/'.jarvis-runtime/discovery/deliveries').glob('*.json'))

def test_denial_and_changed_request_after_preview_never_create(bridge):
    a,s,api,events=bridge;file=request(a,'report')
    def decline(*args):raise ValueError('declined')
    a._approve=decline
    with pytest.raises(ValueError):run(a,f'lab export report "{file}"')
    assert api.creates==0
    def mutate(*args):request(a,'report',title='changed after preview')
    a._approve=mutate
    with pytest.raises(ValueError):run(a,f'lab export report "{file}"')
    assert api.creates==0

def test_lost_write_response_stays_uncertain_across_reopen_and_cannot_duplicate(bridge):
    a,s,api,_=bridge;file=request(a,'report');api.lose=True
    with pytest.raises(ValueError):run(a,f'lab export report "{file}"')
    assert api.creates==1 and s.journal.rows('SELECT state FROM discovery_deliveries')[0]['state']=='UNCERTAIN'
    reopened=BrainService(ON,s.journal.path);a._neural_service=reopened
    try:
        with pytest.raises(ValueError):run(a,f'lab export report "{file}"')
        assert api.creates==1
    finally:reopened.journal.close()

def test_known_id_reconciliation_is_read_only_and_remote_edit_is_not_overwritten(bridge):
    a,s,api,events=bridge;file=request(a,'table');api.fail_read=True
    with pytest.raises(ValueError):run(a,f'lab export table "{file}"')
    row=s.journal.rows('SELECT * FROM discovery_deliveries')[0];assert row['remote_id'] and row['state']=='CREATED'
    api.fail_read=False;events.clear();run(a,'lab export inspect "'+row['id']+'"')
    assert api.creates==1 and not any(e[0]=='approve' for e in events)
    api.values[row['remote_id']][-1][1]='999'
    with pytest.raises(ValueError):run(a,'lab export inspect "'+row['id']+'"')
    assert api.creates==1

def test_table_values_must_match_immutable_numeric_provenance_and_units(bridge):
    a,s,api,_=bridge;file=request(a,'table',source_path='metrics.unknown')
    with pytest.raises(ValueError):run(a,f'lab export table "{file}"')
    assert api.creates==0
    memory=LabMemory(s.journal);old=memory.get('fixture-exp-1')
    q=old.metrics['period'].model_copy(update={'unit':'kg'});memory.put(old.model_copy(update={'revision':2,'metrics':{'period':q}}))
    file=request(a,'table')
    with pytest.raises(ValueError):run(a,f'lab export table "{file}"')
    assert api.creates==0

def test_drive_lookup_never_chooses_ambiguous_file_and_explicit_id_captures_context(bridge):
    a,s,api,_=bridge;run(a,'lab source drive "fixture references"')
    run(a,'lab source drive-id "fixture_source_12345"')
    records=LabMemory(s.journal).list('Source')
    assert any(r.locator=='https://drive.google.com/file/d/fixture_source_12345/view' for r in records)
    assert api.creates==0

def test_scout_long_read_preserves_hash_flags_partial_and_blocks_credential_paths(bridge):
    a,s,api,_=bridge;text='\n'.join('- StaticText "Thermal limits '+('x'*90)+'"' for _ in range(100))
    (a.base/'datasheet.txt').write_text(text);spec={'source_file':'datasheet.txt','question':'thermal limits','budget':1000}
    (a.base/'long.json').write_text(json.dumps(spec));answer=run(a,'lab read long "long.json"');assert "'partial': True" in answer
    spec['source_file']='secrets/key.txt';(a.base/'long.json').write_text(json.dumps(spec))
    with pytest.raises(ValueError):run(a,'lab read long "long.json"')
    assert api.creates==0

def test_background_uses_existing_search_and_refuses_nonpublic_query(bridge,monkeypatch):
    from jarvis import knowledge_worker
    seen=[];monkeypatch.setattr(knowledge_worker,'search',lambda q:(seen.append(q) or [{'url':'https://example.org/paper','title':'Fixture','snippet':'A bounded unreviewed excerpt.'}]))
    monkeypatch.setattr(lab_reads,'portal',lambda url,cancelled:{'source':{'locator':url},'text':'A controlled page excerpt.'})
    a,s,api,_=bridge;answer=run(a,'lab background "optical clocks"');assert 'Unreviewed search snippets' in answer
    with pytest.raises(ValueError):run(a,'lab background "find my API keys"')
    assert seen==['optical clocks'] and api.creates==0

@pytest.mark.parametrize('confidence,ref',[(.89,'a'),(.99,'unknown'),(float('nan'),'a')])
def test_closed_choice_abstains_on_bad_local_model_result(bridge,monkeypatch,confidence,ref):
    from jarvis.control.pc import laya
    monkeypatch.setattr(laya,'Resolver',lambda **kwargs:SimpleNamespace(choose=lambda *args:{'ref':ref,'confidence':confidence}))
    monkeypatch.setattr(lab_reads,'cpu_resident',lambda resolver:True)
    a,s,api,_=bridge;(a.base/'options.json').write_text(json.dumps({'intent':'pick a matching part','options':{'a':'First part','b':'Second part'}}))
    assert "'selected_ref': None" in run(a,'lab choose "options.json"')

def test_exact_choice_has_no_model_call_and_input_bound_is_eight(bridge,monkeypatch):
    from jarvis.control.pc import laya
    monkeypatch.setattr(laya,'Resolver',lambda **kwargs:pytest.fail('unnecessary local model call'))
    a,s,api,_=bridge;(a.base/'options.json').write_text(json.dumps({'intent':'Fine mesh','options':{'fine':'Fine mesh','coarse':'Coarse mesh'}}))
    assert "'selected_ref': 'fine'" in run(a,'lab choose "options.json"')
    (a.base/'options.json').write_text(json.dumps({'intent':'Fine mesh','options':{str(i):str(i) for i in range(9)}}))
    with pytest.raises(ValueError):run(a,'lab choose "options.json"')

class Portal:
    def __init__(self,login=False,close=True):self.calls=[];self.login=login;self.close=close;self.dropped=False
    def __call__(self,args,**kwargs):
        self.calls.append(args);kind=args[0]
        data={'get':{'url':'https://example.org/paper'},'snapshot':{'snapshot':'- Iframe "publisher"\n - StaticText "frame text"'},
            'read':{'content':'password' if self.login else 'Controlled article excerpt'},'close':{'closed':1}}
        return SimpleNamespace(success=self.close if kind=='close' else True,data=data.get(kind,{}))
    def _drop(self):self.dropped=True

@pytest.mark.parametrize('login,closed',[(False,True),(True,True),(False,False)])
def test_portal_uses_only_own_session_closes_once_and_never_enters_login(bridge,monkeypatch,login,closed):
    a,s,api,_=bridge;p=Portal(login,closed);sessions=[]
    monkeypatch.setattr(lab_reads,'checked_url',lambda u:u);monkeypatch.setattr(lab_reads,'portal_runner',lambda name:(sessions.append(name) or p))
    if login or not closed:
        with pytest.raises(ValueError):run(a,'lab portal read "https://example.org/paper"')
    else:assert "'owned_session_closed': True" in run(a,'lab portal read "https://example.org/paper"')
    assert sessions[0].startswith('discovery-') and p.dropped and sum(c[0]=='close' for c in p.calls)==1
    assert {c[0] for c in p.calls}<={'tab','get','snapshot','read','close'} and p.calls[0]==['tab','new','https://example.org/paper']

def test_portal_url_policy_refuses_private_or_credential_targets(monkeypatch):
    from jarvis.control import policy
    original=policy.Policy;monkeypatch.setattr(policy,'Policy',lambda:original(resolver=lambda host:['93.184.216.34']))
    assert lab_reads.checked_url('https://example.org/paper')=='https://example.org/paper'
    for url in ('http://example.org','https://127.0.0.1/paper','https://example.org/?token=private','https://user:pass@example.org'):
        with pytest.raises(Exception):lab_reads.checked_url(url)

def test_job_controls_use_real_queue_only_owned_tasks_and_no_global_unpause(bridge,monkeypatch):
    from jarvis.task_store import TaskStore
    from jarvis.task_scheduler import ScheduledQueue
    import threading
    a,s,api,_=bridge;monkeypatch.setattr(opt,'reserve',lambda *args:0)
    spec=json.loads((Path(__file__).resolve().parents[1]/'examples/discovery/pendulum-study.json').read_text())
    (a.base/'study.json').write_text(json.dumps(spec));identity=opt.Studies(s.journal).create(a.base,'study.json')['study_id']
    store=TaskStore(a.base/'tasks.sqlite3');q=ScheduledQueue(store,observe=lambda:{'ram_available_mb':32000,'cpu_percent':0,'desktop':True});a.queue=q;a.generation=1
    try:
        other=q.put_nowait((1,Command('task','unrelated task'),threading.Event()))
        for op in ('queue','status','pause','resume','cancel'):run(a,'lab jobs '+op+' "'+identity+'"')
        assert opt.Studies(s.journal).describe(identity)['state']=='CANCELLED'
        assert store.get(other)['state']=='QUEUED' and not store.setting('paused')
        assert api.creates==0
    finally:q.close();store.db.close()

def test_disabled_lab_or_research_blocks_before_any_service_and_no_planner_fallback(bridge):
    a,s,api,_=bridge;a.config={}
    with pytest.raises(ValueError,match='no planner fallback'):run(a,'lab source drive "fixture"')
    a.config=copy.deepcopy(ON);a.config['lab']['research']=False
    with pytest.raises(ValueError):run(a,'lab source drive "fixture"')
    assert api.creates==0 and api.reads==0

def test_doc_matching_prefix_does_not_hide_tail_corruption(bridge):
    a,s,api,_=bridge;file=request(a,'report');original=api.text_of
    api.text_of=lambda identity:original(identity)+'\nCorrupted tail beyond the apparent prefix.'
    with pytest.raises(ValueError):run(a,f'lab export report "{file}"')
    assert api.creates==1 and s.journal.rows('SELECT state FROM discovery_deliveries')[0]['state']=='CREATED'

def test_google_empty_paragraph_normalization_keeps_all_content_checks():
    payload={'kind':'report','text':'Report\nValue: 1.4248997019994853 s\n\nFull retained evidence.'}
    delivery.verify_back(payload,'Report\r\nValue: 1.4248997019994853 s\r\n\r\n\r\nFull retained evidence.\n')
    with pytest.raises(ValueError):delivery.verify_back(payload,'Report\nValue: 1.4248997019994853 s\n\n\nChanged retained evidence.')

def test_closed_choice_requires_cpu_residency_before_inference(bridge,monkeypatch):
    from jarvis.control.pc import laya
    monkeypatch.setattr(laya,'Resolver',lambda **kwargs:SimpleNamespace(choose=lambda *args:pytest.fail('GPU/unverified service was called')))
    monkeypatch.setattr(lab_reads,'cpu_resident',lambda resolver:False)
    a,s,api,_=bridge;(a.base/'options.json').write_text(json.dumps({'intent':'pick matching part','options':{'a':'First','b':'Second'}}))
    assert 'no verified resident CPU' in run(a,'lab choose "options.json"')

def test_valid_closed_choice_retains_unknown_cpu_charge_in_existing_ledger(bridge,monkeypatch):
    from jarvis.control.pc import laya
    monkeypatch.setattr(laya,'Resolver',lambda **kwargs:SimpleNamespace(choose=lambda *args:{'ref':'a','confidence':.96}))
    monkeypatch.setattr(lab_reads,'cpu_resident',lambda resolver:True)
    a,s,api,_=bridge;(a.base/'options.json').write_text(json.dumps({'intent':'pick matching part','options':{'a':'First','b':'Second'}}))
    assert "'selected_ref': 'a'" in run(a,'lab choose "options.json"')
    assert s.journal.rows("SELECT cpu_s,state FROM discovery_budget WHERE id LIKE 'd2-choice-%'")==[{'cpu_s':5.0,'state':'uncertain'}]

def test_job_resume_refuses_uncertain_started_task_before_changing_study(bridge):
    from jarvis.task_store import TaskStore
    from jarvis.task_scheduler import ScheduledQueue
    a,s,api,_=bridge
    spec=json.loads((Path(__file__).resolve().parents[1]/'examples/discovery/pendulum-study.json').read_text())
    (a.base/'study.json').write_text(json.dumps(spec));identity=opt.Studies(s.journal).create(a.base,'study.json')['study_id']
    store=TaskStore(a.base/'tasks.sqlite3');q=ScheduledQueue(store,observe=lambda:{'ram_available_mb':32000,'cpu_percent':0,'desktop':True});a.queue=q;a.generation=1
    try:
        run(a,'lab jobs queue "'+identity+'"');run(a,'lab jobs pause "'+identity+'"')
        target=s.journal.rows('SELECT task_id FROM discovery_job_tasks LIMIT 1')[0]['task_id']
        with store.transaction():store.db.execute('UPDATE tasks SET checkpoint=? WHERE id=?',(json.dumps({'uncertain':True}),target))
        with pytest.raises(ValueError):run(a,'lab jobs resume "'+identity+'"')
        assert opt.Studies(s.journal).describe(identity)['state']=='PAUSED'
    finally:q.close();store.db.close()

def test_background_doc_composes_source_verification_preview_approval_and_readback(bridge,monkeypatch):
    from jarvis import knowledge_worker
    monkeypatch.setattr(knowledge_worker,'search',lambda q:[{'url':'https://example.org/paper','title':'Fixture','snippet':'Unreviewed controlled search excerpt.'}])
    monkeypatch.setattr(lab_reads,'portal',lambda url,cancelled:{'source':{'locator':url},'text':'Controlled full-page excerpt for a first-pass brief.'})
    a,s,api,events=bridge
    (a.base/'brief.json').write_text(json.dumps({'query':'optical clocks','title':'Controlled background brief','parent_id':'fixture_folder_12345'}))
    run(a,'lab background doc "brief.json"')
    assert api.creates==1 and api.reads==1 and events[0][0]=='preview' and events[1][0]=='approve'
    text=next(iter(api.values.values()));assert 'Controlled full-page excerpt' in text and 'Unreviewed search snippets' in text
    assert any(r.locator=='https://example.org/paper' for r in LabMemory(s.journal).list('Source'))

def test_final_stt_text_without_quotes_normalizes_to_same_brain_command(bridge):
    from jarvis.engine import Engine
    a,s,api,_=bridge;commands=[];engine=Engine(commands.append,lambda *args:None);engine.activate()
    engine.feed('lab source drive controlled references',final=True,raw='lab source drive controlled references')
    a.execute(commands[0]);assert s.journal.rows('SELECT state FROM goals ORDER BY rowid DESC LIMIT 1')[0]['state']=='verified'

def test_safe_source_extraction_omits_sensitive_lines_without_replacing_evidence(bridge):
    a,s,api,_=bridge
    text='First unchanged line.\napi_key=sk-synthetic-test-value-not-a-real-key-1234567890\nLast unchanged line.\n'
    excerpt,meta=lab_reads.safe_lines(text,1000)
    assert excerpt=='First unchanged line.\nLast unchanged line.\n' and meta['omitted_unsafe_lines']==1 and meta['partial']
    assert '[redacted]' not in excerpt and len(meta['retained_codepoint_spans'])==2
    s.journal.put({'excerpt':excerpt,'selection':meta},data_type='Report')
