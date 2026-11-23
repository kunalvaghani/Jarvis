"""Prepare reviewable local payloads; read existing folder metadata, never create remote files."""
import hashlib,json,sqlite3,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];APP=ROOT/'app';sys.path.insert(0,str(APP))
PROOF=APP/'.jarvis-runtime/lab-validation/d2-live-root'

def main():
    PROOF.mkdir(exist_ok=True)
    with (PROOF/'prepared-once.json').open('x') as f:json.dump({'scope':'local previews and read-only existing Google folder metadata'},f)
    from jarvis.google_files import Files,FOLDER,DRIVE
    files=Files(APP)
    try:
        folders=files.find('Jarvis',FOLDER)
        if not folders:
            root=files._call('GET',DRIVE+'files/root',params={'fields':'id,mimeType'})
            if root.get('mimeType')!=FOLDER:raise ValueError('Drive root metadata differs')
            folders=[root]
            destination='My Drive root (no Jarvis folder exists; no folder will be created)'
        else:destination='existing Jarvis folder'
    finally:files.close()
    if len(folders)!=1:raise ValueError('one unambiguous existing Jarvis Drive folder required; no folder was created')
    parent=folders[0]['id']
    original=APP/'.jarvis-runtime/lab-validation/d-proof/brain.sqlite3'
    original_sha=hashlib.sha256(original.read_bytes()).hexdigest()
    source=sqlite3.connect(original.resolve().as_uri()+'?mode=ro',uri=True);target=sqlite3.connect(PROOF/'brain.sqlite3')
    try:source.backup(target)
    finally:source.close();target.close()
    from jarvis.neural.service import BrainService
    from jarvis.actions import Actions
    from jarvis.commands import Command
    from jarvis.discovery.memory import LabMemory
    from jarvis.discovery.contracts import RunArtifact
    config={'neural':{'mode':'act','learning':'shadow'},'lab':{'enabled':True,'sim':True,'research':True,'learning':True}}
    s=BrainService(config,PROOF/'brain.sqlite3');m=LabMemory(s.journal)
    try:
        study=s.journal.rows("SELECT id FROM discovery_studies WHERE path='study.json'")[0]['id']
        ids=[study+'-trial-'+str(i)+'-experiment' for i in (0,2)]
        entries=[m.get(i) for i in ids]
        summary={'purpose':'D2 delivery qualification from retained conditional C4 results; not a new physical result',
            'solver':entries[0].solver,'solver_version':entries[0].solver_version,
            'recorded_periods_s':[e.metrics['period'].value for e in entries],
            'evidence_status':'SIMULATION_PASSED_WITH_ASSUMPTIONS','physical_validation':False}
        ref=s.journal.put(summary,data_type='Report');identity='d2-qualification-summary'
        m.put(RunArtifact(id=identity,locator=ref,sha256=hashlib.sha256(s.journal.get(ref).encode()).hexdigest(),
            media_type='application/json',source_ids=entries[0].source_ids,
            evidence_status='SIMULATION_PASSED_WITH_ASSUMPTIONS',justification='Deterministic summary of actual retained C4 numerical records.'))
        specs={'report':{'title':'Jarvis D2 qualification report 2026-11-04','parent_id':parent,'artifact_id':identity},
               'table':{'title':'Jarvis D2 qualification sheet 2026-11-04','parent_id':parent,'experiment_ids':ids,
                        'metric':'period','source_path':'metrics.measured_period_s'}}
        a=Actions.__new__(Actions);a.config,a.base,a._neural_service,a.allowed_tools=config,APP,s,None
        a.report=lambda *args:None
        def deny(*args):raise ValueError('Live remote writes not yet approved; preparation only')
        a._approve=deny
        for kind,spec in specs.items():
            path=PROOF/(kind+'-request.json');path.write_text(json.dumps(spec,indent=2),encoding='utf-8')
            try:a.execute(Command('task','lab export '+kind+' "'+path.relative_to(APP).as_posix()+'"'))
            except ValueError:pass  # Expected existing approval gate denial, never a fabricated success.
        rows=s.journal.rows('SELECT id,state,payload_ref FROM discovery_deliveries')
        assert len(rows)==2 and all(r['state']=='PREPARED' for r in rows)
        assert hashlib.sha256(original.read_bytes()).hexdigest()==original_sha
        result={'date_local':'2026-11-04 Asia/Calcutta','state':'PREPARED_PENDING_APPROVAL','folder_id':parent,
            'folder_url':'https://drive.google.com/drive/folders/'+parent,'destination':destination,'source_history_unchanged':True,
            'writes':0,'source_model_solver_calls':0,'requests':specs,
            'deliveries':[{'id':r['id'],'payload':json.loads(s.journal.get(r['payload_ref']))} for r in rows]}
        (ROOT/'docs/lab/evidence/d2-live-prepared.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({'state':result['state'],'folder_url':result['folder_url'],'destination':destination,'titles':[v['title'] for v in specs.values()],
                          'periods_s':summary['recorded_periods_s'],'deliveries':[r['id'] for r in rows],'writes':0}))
    finally:s.journal.close()
if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps({'state':'PREPARATION_BLOCKED','error_type':type(exc).__name__,'remote_writes':0}));raise SystemExit(1)
