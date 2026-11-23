"""Public asset-catalog acquisition as two ordinary source/verification neurons."""
import hashlib,json,re,uuid
from pathlib import Path
from .catalog import enabled
from .contracts import Source,Capability,RunArtifact
from .memory import LabMemory
from .adapters import asset_catalog

PATTERN=re.compile(r'^\s*lab assets search "([^"\r\n]{4,240})"\s*$',re.I)
INSPECT=re.compile(r'^\s*lab assets inspect "([a-f0-9]{32})"\s*$',re.I)
NODES={'run':'discovery.assets.search_public@v1','check':'discovery.verify.asset_search@v1'}


def neurons(config):
    if not enabled(config,'research'):return []
    from ..neural.contracts import Neuron
    from ..neural.registry import ports
    return [Neuron(node_id=node,kind='verifier' if key=='check' else 'skill',capability=node.split('@')[0],
        provider='jarvis.discovery.asset_search',contract='explicit',
        inputs=ports(('request:Report','report:Report') if key=='check' else ('request:Report',)),
        outputs=ports(('verdict:Verdict',) if key=='check' else ('report:Report',)),
        side_effect_class='read_only',privilege='read',privacy='public_data_only',runtime='network' if key=='run' else 'local',
        requirements=('flag:lab.enabled','flag:lab.research'),timeout_ms=25000,
        resource_cost={'money':0,'gpu_vram_mb':0,'cpu_s_estimate':1},
        description='Public downloadable-model metadata with cached hashes; no binary download or engineering identity claim',
        source='jarvis/discovery/asset_search.py') for key,node in NODES.items()]


def sources(config,previous):return {**previous,'discovery_asset_search':lambda:neurons(config)}


def compile_goal(goal,journal,config,graph_version=0):
    match=PATTERN.fullmatch(goal) or INSPECT.fullmatch(goal)
    if not enabled(config,'research') or not match:return None
    from ..neural.compiler import _const
    from ..neural.execution import Bind,Plan,Step
    request=_const(journal,{'uid':match[1]} if INSPECT.fullmatch(goal) else {'query':match[1]},'Report')
    return Plan(goal_id='g-'+uuid.uuid4().hex[:16],goal=goal,workflow='discovery.assets.search_public',
        steps=[Step(step_id='run',neuron=NODES['run'],bind={'request':request}),
               Step(step_id='check',neuron=NODES['check'],bind={'request':request,'report':Bind(step='run',port='report')}),
               Step(step_id='answer',neuron='motor.report@v1',bind={'report':Bind(step='run',port='report'),
                    'verdict':Bind(step='check',port='verdict')})],goal_verifier='check',answer_step='answer',
        graph_version=graph_version,deadline_s=30)


def adapters(graph,journal):
    memory=LabMemory(journal);memory.migrate()
    with journal.tx() as db:
        db.execute('CREATE TABLE IF NOT EXISTS discovery_asset_search_runs (ref TEXT PRIMARY KEY,query TEXT,payload_sha256 TEXT)')
    for node in NODES.values():
        if node in graph.neurons:
            memory.put(Capability(id=node,neuron_id=node,intents=('public licensed-asset metadata search',),
                golden_ref='tests/test_discovery_asset_search.py',justification='Public source bytes only; source claims remain unverified.'))

    def perform(neuron,inputs,env):
        from ..task_state import TaskState
        from .vehicle_assurance import asset_query_error
        state=getattr(env.actions,'task_state',None)
        parent=(state.snapshot() or {}).get('goal','') if isinstance(state,TaskState) else ''
        req=inputs['request']
        problem=asset_query_error(getattr(env.actions,'config',{}),parent,req.get('query',''),catalog_search='query' in req)
        if problem:raise ValueError(problem)
        env.actions.report('brain','Lab assets: reading bounded public catalog metadata; no asset binary is being downloaded.')
        result=asset_catalog.detail(env.actions.base,req['uid']) if 'uid' in req else asset_catalog.search(env.actions.base,req['query'])
        source=Source(id='catalog-search-'+result['payload_sha256']+'-'+uuid.uuid4().hex[:8],locator=result['endpoint'],
            sha256=result['payload_sha256'],author='Sketchfab public catalog',
            retrieved_at=result['retrieved_at_utc'],
            justification='Untrusted provider search metadata; creator/license/identity declarations are not independently established asset rights or engineering facts.')
        memory.put(source)
        result['source_ref']=source.id
        ref=journal.put(result,'Report')
        with journal.tx() as db:db.execute('INSERT OR IGNORE INTO discovery_asset_search_runs VALUES (?,?,?)',
            (ref,result['query'],result['payload_sha256']))
        memory.put(RunArtifact(id='catalog-result-'+ref.rsplit('/',1)[-1],locator=ref,
            sha256=hashlib.sha256(journal.get(ref).encode()).hexdigest(),media_type='application/json',
            source_ids=(source.id,),justification='Actual public API metadata, not an acquired 3D model or verified scientific claim.'))
        return {'report':{'result_ref':ref,'result':result,'evidence_status':'INSUFFICIENT_EVIDENCE'}}

    def verify(neuron,inputs,env):
        problems=[]
        try:
            from .acceptance import artifact
            from .adapters.assets import local_bytes
            report=inputs['report'];result=artifact(journal,report['result_ref'])
            if result!=report['result']:raise ValueError('published catalog result differs')
            receipt=journal.rows('SELECT query,payload_sha256 FROM discovery_asset_search_runs WHERE ref=?',(report['result_ref'],))
            req=inputs['request'];lookup='model:'+req['uid'] if 'uid' in req else req['query']
            mode='detail' if 'uid' in req else 'search'
            if len(receipt)!=1 or receipt[0]['query']!=lookup or result['lookup_mode']!=mode:raise ValueError('actual matching source read missing')
            raw=local_bytes(Path(env.actions.base),result['cached_metadata'],asset_catalog.CAP)
            if hashlib.sha256(raw).hexdigest()!=receipt[0]['payload_sha256'] or result['items']!=asset_catalog.parse(raw,mode):
                raise ValueError('cached source bytes or metadata changed')
            if result['binary_download_performed'] is not False or any(i['geometry_acquired'] or i['identity_verified'] for i in result['items']):
                raise ValueError('metadata cannot establish asset acquisition or identity')
        except Exception as exc:problems.append(type(exc).__name__+': '+str(exc)[:300])
        return {'verdict':{'passed':not problems,'problems':problems,
            'evidence':['actual public API read and unchanged cached metadata bytes; no scientific/asset promotion'] if not problems else []}}
    return {node:({'run':perform,'check':verify}[key]) for key,node in NODES.items() if node in graph.neurons}
