"""D2 service adapters as ordinary registered brain neurons. No alternate executor."""
import hashlib,json,re,uuid
from pathlib import Path
from .catalog import enabled
from .contracts import Capability,Source,RunArtifact
from .memory import LabMemory
from .adapters import delivery as remote,lab_reads,lab_jobs
from .model import delivery

NODES={k:'discovery.'+name+'@v1' for k,name in (
    ('source','source.from_drive'),('portal','literature.portal_read'),('long','literature.read_long'),
    ('background','literature.background'),('choose','choose.option'),
    *((op,'jobs.'+op) for op in ('queue','status','pause','resume','cancel')),
    ('prepare','export.prepare'),('report','report.to_doc'),('table','table.to_sheet'),('inspect','export.inspect'),('verify','verify.d2'))}
PATTERNS=[(mode,re.compile(pattern,re.I)) for mode,pattern in (
    ('report',r'^\s*lab export report "([^"\r\n]{1,300})"\s*$'),('table',r'^\s*lab export table "([^"\r\n]{1,300})"\s*$'),
    ('inspect',r'^\s*lab export inspect "(delivery-[a-f0-9]{64})"\s*$'),
    ('drive_query',r'^\s*lab source drive "([^"\r\n]{1,100})"\s*$'),('drive_id',r'^\s*lab source drive-id "([A-Za-z0-9_-]{10,100})"\s*$'),
    ('portal',r'^\s*lab portal read "([^"\r\n]{1,1500})"\s*$'),('long',r'^\s*lab read long "([^"\r\n]{1,300})"\s*$'),
    ('background',r'^\s*lab background "([^"\r\n]{4,240})"\s*$'),('background_doc',r'^\s*lab background doc "([^"\r\n]{1,300})"\s*$'),
    ('choose',r'^\s*lab choose "([^"\r\n]{1,300})"\s*$'),
    *((op,r'^\s*lab jobs '+op+r' "(study-[a-f0-9]{32})"\s*$') for op in ('queue','status','pause','resume','cancel')))]
PREFIX=re.compile(r'^\s*lab (?:export|source drive|portal read|read long|background|choose|jobs)\b',re.I)

def parsed(text):
    for mode,pattern in PATTERNS:
        match=pattern.fullmatch(text)
        if match:return mode,match[1]
    return None

def route_command(command):
    from ..commands import Command
    if command.kind in ('task','ask') and command.extra in ('','unparsed') and PREFIX.match(command.value):
        if not parsed(command.value):
            # STT/text may omit quotation marks. Quote only a bounded literal
            # argument of an already-known command; never reinterpret its data.
            literal=re.fullmatch(r'\s*(lab (?:export (?:report|table|inspect)|source (?:drive-id|drive)|portal read|read long|background doc|background|choose|jobs (?:queue|status|pause|resume|cancel))) ([^"\r\n]{1,1500})\s*',command.value,re.I)
            if literal:
                candidate=literal[1]+' "'+literal[2].strip()+'"'
                if parsed(candidate):return Command('task',candidate)
            raise ValueError('Use a bounded D2 command with its quoted request, source, delivery or study ID')
        return Command('task',command.value)
    return command

def feature(mode):return 'sim' if mode in ('queue','status','pause','resume','cancel') else 'research' if mode in ('source','portal','long','background') else 'enabled'

def neurons(config):
    if not enabled(config):return []
    from ..neural.contracts import Neuron
    from ..neural.registry import ports
    rows=[]
    for key,identity in NODES.items():
        inputs=('request:Report','prepared:Report') if key in ('report','table') else ('request:Report','report:Report') if key=='verify' else ('request:Report','background:Report?','verdict:Verdict?') if key=='prepare' else ('request:Report',)
        writes=key in ('report','table');network=key in ('report','table','source','portal','background','inspect')
        rows.append(Neuron(node_id=identity,kind='verifier' if key=='verify' else 'skill',capability=identity.split('@')[0],
            provider='jarvis.discovery.d2',contract='explicit',inputs=ports(inputs),outputs=ports(('verdict:Verdict',) if key=='verify' else ('report:Report',)),
            runtime='network' if network else 'local',privacy='local_private',side_effect_class='external_write' if writes else 'ui_or_media_state' if key in ('portal','background') else 'read_only',
            privilege='approval_required' if writes else 'write' if key in ('portal','background') else 'read',requirements=('flag:lab.enabled',)+((f'flag:lab.{feature(key)}',) if feature(key)!='enabled' else ()),
            timeout_ms=120000,resource_cost={'money':0,'gpu_vram_mb':0,'cpu_s_estimate':2},source='jarvis/discovery/d2.py',
            description='D2 '+key+': existing interfaces, bounded inputs, source context and independent readback; no scientific promotion'))
    return rows

def sources(config,existing):return {**existing,'discovery_d2':lambda:neurons(config)}

def compile_goal(goal,journal,config,graph_version=0):
    match=parsed(goal)
    if not match or not enabled(config):return None
    mode,value=match;key='source' if mode.startswith('drive_') else mode
    from ..neural.compiler import _const
    from ..neural.execution import Bind,Plan,Step
    request=_const(journal,{'mode':mode,'value':value},'Report')
    if mode=='background_doc':
        steps=[Step(step_id='research',neuron=NODES['background'],bind={'request':request}),
            Step(step_id='sourcecheck',neuron=NODES['verify'],bind={'request':request,'report':Bind(step='research',port='report')}),
            Step(step_id='prepare',neuron=NODES['prepare'],bind={'request':request,'background':Bind(step='research',port='report'),'verdict':Bind(step='sourcecheck',port='verdict')}),
            Step(step_id='run',neuron=NODES['report'],bind={'request':request,'prepared':Bind(step='prepare',port='report')},
                approval_scope='Create one Google Doc from the prepared research preview for '+value)]
    elif mode in ('report','table'):
        steps=[Step(step_id='prepare',neuron=NODES['prepare'],bind={'request':request}),
            Step(step_id='run',neuron=NODES[mode],bind={'request':request,'prepared':Bind(step='prepare',port='report')},
                approval_scope='Create one Google '+('Doc' if mode=='report' else 'Sheet')+' from the prepared preview for '+value)]
    else:steps=[Step(step_id='run',neuron=NODES[key],bind={'request':request})]
    return Plan(goal_id='g-'+uuid.uuid4().hex[:16],goal=goal,workflow='discovery.d2.'+mode,graph_version=graph_version,deadline_s=180,
        steps=steps+[Step(step_id='check',neuron=NODES['verify'],bind={'request':request,'report':Bind(step='run',port='report')}),
            Step(step_id='answer',neuron='motor.report@v1',bind={'report':Bind(step='run',port='report'),'verdict':Bind(step='check',port='verdict')})],goal_verifier='check',answer_step='answer')

def adapters(graph,journal):
    memory=LabMemory(journal);memory.migrate();ledger=remote.Ledger(journal)
    for key,identity in NODES.items():
        if identity in graph.neurons:memory.put(Capability(id=identity,neuron_id=identity,intents=('bounded D2 '+key,),
            golden_ref='tests/test_discovery_delivery.py',justification='Registered service bridge; live service qualification and scientific evidence remain separate.'))
    with journal.tx() as db:db.execute('CREATE TABLE IF NOT EXISTS discovery_d2_receipts (ref TEXT NOT NULL,request_ref TEXT NOT NULL,PRIMARY KEY(ref,request_ref))')

    def load(base,path,schema):
        raw=lab_reads.safe_bytes(base,path,30000)
        try:value=schema.model_validate_json(raw).model_dump(mode='json')
        except Exception:raise ValueError('D2 request schema invalid; nothing was sent') from None
        journal.put(value,data_type='Report')
        return value,hashlib.sha256(raw).hexdigest()

    def receipt(request,result):
        ref=journal.put(result,data_type='Report');req=journal.put(request,data_type='Report')
        with journal.tx() as db:db.execute('INSERT OR IGNORE INTO discovery_d2_receipts VALUES (?,?)',(ref,req))
        return {'report':{'result_ref':ref,'result':result}}

    def prepare(neuron,inputs,env):
        if env.cancelled():raise ValueError('export cancelled before preparation')
        req=inputs['request']
        if req['mode']=='background_doc':
            spec,digest=load(env.actions.base,req['value'],delivery.BackgroundExport)
            if inputs.get('verdict',{}).get('passed') is not True:raise ValueError('background source verification required before export')
            bg=inputs['background'];actual=json.loads(journal.get(bg['result_ref']))
            if actual!=bg['result'] or not journal.rows('SELECT ref FROM discovery_d2_receipts WHERE ref=? AND request_ref=?',(bg['result_ref'],journal.put(req,data_type='Report'))):raise ValueError('actual background receipt required')
            if actual['request_file_sha256']!=digest:raise ValueError('research request changed before preparation')
            effective={'title':spec['title'],'parent_id':spec['parent_id'],'artifact_id':actual['artifact_id']}
        else:spec,digest=load(env.actions.base,req['value'],delivery.Export);effective=spec
        payload=delivery.prepare(memory,'report' if req['mode']=='background_doc' else req['mode'],effective)
        key=ledger.stage(payload)
        root=Path(env.actions.base)/'.jarvis-runtime/discovery/deliveries';path=root/(key+'.json')
        from ..skill_memory import linked
        if any(linked(p) for p in (path,*path.parents)):raise ValueError('linked delivery preview root')
        root.mkdir(parents=True,exist_ok=True);text=json.dumps(payload,indent=2,ensure_ascii=False)
        try:
            with path.open('x',encoding='utf-8') as handle:handle.write(text)
        except FileExistsError:
            if path.read_text(encoding='utf-8')!=text:raise ValueError('owned preview differs; no overwrite')
        report=getattr(env.actions,'report',None)
        if callable(report):report('answer','Prepared '+payload['kind']+' "'+payload['title']+'" in folder '+payload['parent_id']+'. Review full payload: '+str(path))
        return {'report':{'delivery_id':key,'request_sha256':digest,'preview_file':str(path),'effective_spec':effective}}

    def write(neuron,inputs,env):
        req=inputs['request'];prepared=inputs['prepared'];spec,digest=load(env.actions.base,req['value'],delivery.BackgroundExport if req['mode']=='background_doc' else delivery.Export)
        if req['mode']=='background_doc' and any(prepared['effective_spec'][field]!=spec[field] for field in ('title','parent_id')):raise ValueError('research export destination/title changed')
        payload=delivery.prepare(memory,'report' if req['mode']=='background_doc' else req['mode'],prepared['effective_spec'] if req['mode']=='background_doc' else spec)
        if digest!=prepared['request_sha256'] or payload!=ledger.payload(prepared['delivery_id']):raise ValueError('export input changed after preview/approval; nothing was sent')
        result=ledger.create(prepared['delivery_id'],env.actions.base,env.cancelled)
        return receipt(req,{'stage':'delivery','result':result,'physical_validation':False})

    def read(neuron,inputs,env):
        req=inputs['request'];mode,value=req['mode'],req['value']
        if env.cancelled():raise ValueError('D2 request cancelled before execution')
        digest=None
        if mode in ('drive_query','drive_id'):
            from .adapters import drive_sources
            client=remote.files(env.actions.base)
            try:
                if mode=='drive_id':result=drive_sources.read(client,value,memory=memory)
                else:result={'matches':drive_sources.search(client,value,limit=5),'content_is_untrusted':True,'coverage':'Choose an explicit file ID; no ambiguous source was read.'}
            except Exception:raise ValueError('Drive source read failed; no write or fallback was attempted') from None
            finally:client.close()
        elif mode=='portal':
            journal.put({'requested_url':value},data_type='Report');result=lab_reads.portal(value,env.cancelled)
        elif mode=='long':
            spec,digest=load(env.actions.base,value,delivery.LongRead);result=lab_reads.read_long(env.actions.base,spec)
        elif mode in ('background','background_doc'):
            if mode=='background_doc':spec,digest=load(env.actions.base,value,delivery.BackgroundExport);value=spec['query']
            journal.put({'public_query':value},data_type='Report');result=lab_reads.background(value,env.cancelled)
        elif mode=='choose':
            spec,digest=load(env.actions.base,value,delivery.Options);result=lab_reads.choose(spec,journal=journal)
        elif mode=='inspect':
            row=ledger.row(value)
            if not row['remote_id']:raise ValueError('unknown external outcome: inspect Drive; no automatic creation')
            return receipt(req,{'stage':'delivery','result':{'delivery_id':value,'remote_id':row['remote_id']},'physical_validation':False})
        else:result=lab_jobs.operate(journal,env.actions,env.config,mode,value)
        source_ids=()
        all_sources=([result['source']] if 'source' in result else [])+result.get('sources',[])
        for source in all_sources:
            item=Source.model_validate_json(json.dumps(source));previous=memory.get(item.id)
            if previous is None:memory.put(item)
            elif previous.sha256!=item.sha256 or previous.locator!=item.locator:raise ValueError('source identity conflict')
            source_ids=(*source_ids,item.id)
        ref=journal.put(result,data_type='Report');identity='d2-result-'+delivery.sha([mode,ref])[:32]
        memory.put(RunArtifact(id=identity,locator=ref,sha256=hashlib.sha256(journal.get(ref).encode()).hexdigest(),
            media_type='application/json',source_ids=source_ids,justification='Actual bounded adapter response; content is untrusted and scientific acceptance is not implied.'))
        return receipt(req,{'stage':'reader','artifact_id':identity,'result':result,'request_file_sha256':digest,
                            'evidence_status':'INSUFFICIENT_EVIDENCE','physical_validation':False})

    def verify(neuron,inputs,env):
        issues=[];evidence=[]
        try:
            req=inputs['request'];out=inputs['report'];result=out['result'];ref=out['result_ref']
            if env.cancelled():raise ValueError('verification cancelled')
            if json.loads(journal.get(ref))!=result or not journal.rows('SELECT ref FROM discovery_d2_receipts WHERE ref=? AND request_ref=?',(ref,journal.put(req,data_type='Report'))):raise ValueError('actual D2 adapter receipt required')
            if result['stage']=='delivery':
                back=ledger.inspect(result['result']['delivery_id'],env.actions.base,env.cancelled)
                if back['remote_id']!=result['result']['remote_id']:raise ValueError('remote ID changed')
                evidence.append('Full Google readback/formula check: '+back['readback_sha256'])
            else:
                actual=result['result']
                if req['mode'] in ('long','choose','background_doc'):
                    spec,digest=load(env.actions.base,req['value'],{'long':delivery.LongRead,'choose':delivery.Options,'background_doc':delivery.BackgroundExport}[req['mode']])
                    if digest!=result['request_file_sha256']:raise ValueError('request source changed')
                    if req['mode']=='long' and lab_reads.read_long(env.actions.base,spec)!=actual:raise ValueError('source/brief changed')
                    if req['mode']=='choose' and actual['selected_ref'] is not None:
                        if actual['selected_ref'] not in spec['options'] or not .9<=actual['confidence']<=1:raise ValueError('invalid or low-confidence option')
                if req['mode']=='portal' and actual.get('owned_session_closed') is not True:raise ValueError('portal session cleanup not verified')
                artifact=memory.get(result['artifact_id']);raw=journal.get(artifact.locator)
                if hashlib.sha256(raw.encode()).hexdigest()!=artifact.sha256 or json.loads(raw)!=actual:raise ValueError('typed result artifact differs')
                evidence.append('Bound actual adapter receipt, scoped source and typed artifact checked; no scientific truth promotion')
        except Exception:issues.append('D2 source, provenance, closure, choice, job or full Google readback verification failed')
        return {'verdict':{'passed':not issues,'problems':issues,'evidence':evidence if not issues else []}}

    return {identity:(prepare if key=='prepare' else write if key in ('report','table') else verify if key=='verify' else read)
            for key,identity in NODES.items() if identity in graph.neurons}
