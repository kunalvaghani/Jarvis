"""C4 bounded optimizer commands: existing brain, queue, Journal and checkpoint ownership."""
import json,re,threading,uuid
from .catalog import enabled
from .model.optimization import Studies,enqueue_remaining

PATTERN=re.compile(r'^\s*lab optimize(?:\s+(step|status|pause|resume|cancel|queue))?\s+"([^"\r\n]{1,500})"\s*$',re.I)
NODES={'action':'discovery.optimization.advance@v1','verify':'discovery.verify.optimization@v1'}


def route_command(command):
    from ..commands import Command
    if command.kind in ('task','ask') and command.extra in ('','unparsed') and re.match(r'^\s*lab optimize\b',command.value,re.I):
        if not PATTERN.fullmatch(command.value):raise ValueError('Use lab optimize [step/status/pause/resume/cancel/queue] with a quoted file or study ID')
        return Command('task',command.value)
    return command


def neurons(config):
    if not enabled(config,'sim'):return []
    from ..neural.contracts import Neuron
    from ..neural.registry import ports
    return [Neuron(node_id=identity,kind='verifier' if key=='verify' else 'skill',capability=identity.split('@')[0],
        provider='jarvis.discovery.c4',contract='explicit',inputs=ports(('request:Report','report:Report') if key=='verify' else ('request:Report',)),
        outputs=ports(('verdict:Verdict',) if key=='verify' else ('report:Report',)),side_effect_class='read_only',privilege='read',runtime='local',
        requirements=('flag:lab.enabled','flag:lab.sim'),resource_cost={'gpu_vram_mb':0,'money':0,'cpu_s_estimate':5},
        timeout_ms=30000,source='jarvis/discovery/c4.py',description='Bounded optimization with fixed scenario, hard constraints, charged failures and explicit resume')
        for key,identity in NODES.items()]


def sources(config,existing):return {**existing,'discovery_c4':lambda:neurons(config)}


def compile_goal(goal,journal,config,graph_version=0):
    match=PATTERN.fullmatch(goal)
    if not match or not enabled(config,'sim'):return None
    from ..neural.compiler import _const
    from ..neural.execution import Bind,Plan,Step
    request=_const(journal,{'operation':(match[1] or 'create').lower(),'value':match[2]},'Report')
    return Plan(goal_id='g-'+uuid.uuid4().hex[:16],goal=goal,workflow='discovery.c4',graph_version=graph_version,deadline_s=45,
        steps=[Step(step_id='run',neuron=NODES['action'],bind={'request':request}),
               Step(step_id='check',neuron=NODES['verify'],bind={'request':request,'report':Bind(step='run',port='report')}),
               Step(step_id='answer',neuron='motor.report@v1',bind={'report':Bind(step='run',port='report'),'verdict':Bind(step='check',port='verdict')})],goal_verifier='check',answer_step='answer')


def adapters(graph,journal):
    from .contracts import Capability
    from .memory import LabMemory
    studies=Studies(journal);memory=LabMemory(journal)
    for identity in NODES.values():
        if identity in graph.neurons:memory.put(Capability(id=identity,neuron_id=identity,intents=('bounded local optimization',),
            golden_ref='tests/test_discovery_optimization.py',justification='Reviewed deterministic study adapter; conditional numeric evidence only.'))

    def act(neuron,inputs,env):
        req=inputs['request'];op=req['operation'];value=req['value']
        if env.cancelled():raise ValueError('optimization request cancelled before execution')
        if op=='create':result=studies.create(env.actions.base,value)
        elif op=='step':result=studies.advance(value,env.actions.base,env.cancelled,getattr(env.actions,'task_state',None))
        elif op=='status':result=studies.describe(value)
        elif op in ('pause','resume','cancel'):
            studies.load(value,env.actions.base);result=studies.control(value,op)
        elif op=='queue':
            studies.load(value,env.actions.base)
            queued=enqueue_remaining(studies,getattr(env.actions,'queue',None),env.config,value,getattr(env.actions,'generation',0))
            result={**studies.describe(value),'queued_task_ids':queued}
        else:raise ValueError('unknown optimization operation')
        # A real handler receipt, not a caller-supplied pass boolean, binds the independent verifier.
        ref=journal.put(result,data_type='Report')
        request_ref=journal.put(req,data_type='Report')
        with journal.tx() as db:
            db.execute('CREATE TABLE IF NOT EXISTS discovery_optimization_receipts (ref TEXT NOT NULL, request_ref TEXT NOT NULL, PRIMARY KEY(ref,request_ref))')
            db.execute('INSERT OR IGNORE INTO discovery_optimization_receipts VALUES (?,?)',(ref,request_ref))
        return {'report':{'result':result,'receipt_ref':ref}}

    def check(neuron,inputs,env):
        problems=[]
        try:
            report=inputs['report'];req=inputs['request'];ref=report['receipt_ref'];result=report['result']
            if json.loads(journal.get(ref))!=result:raise ValueError('report differs from actual receipt')
            if not journal.rows('SELECT ref FROM discovery_optimization_receipts WHERE ref=? AND request_ref=?',(ref,journal.put(req,data_type='Report'))):raise ValueError('no actual optimization request receipt')
            expected=studies.describe(result['study_id']);queued=result.get('queued_task_ids')
            if queued is not None:
                for identity in queued:
                    row=env.actions.queue.store.get(identity)
                    if row['command']['value']!='lab optimize step "'+result['study_id']+'"':raise ValueError('queued command differs')
                expected['queued_task_ids']=queued
            if expected!=result:raise ValueError('study/solver/scenario/constraint replay differs')
        except Exception:problems.append('independent optimization receipt/constraint verification failed')
        return {'verdict':{'passed':not problems,'problems':problems,'evidence':['actual trial receipts, fixed scenario, independent physics and hard constraints; bounded stop state'] if not problems else []}}

    return {identity:handler for identity,handler in ((NODES['action'],act),(NODES['verify'],check)) if identity in graph.neurons}
