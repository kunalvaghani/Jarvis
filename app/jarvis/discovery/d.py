"""Phase D audit/wiring commands composed by the existing brain and dispatcher."""
import json,re,uuid
from .catalog import enabled
from .contracts import Capability
from .memory import LabMemory
from . import wiring,memory_graph

PATTERN=re.compile(r'^\s*lab (audit integration|memory wire)\s*$',re.I)
PREFIX=re.compile(r'^\s*lab (?:audit integration|memory wire)\b',re.I)
NODES=('discovery.integration.audit@v1','discovery.verify.integration@v1')


def route_command(command):
    from ..commands import Command
    if command.kind in ('task','ask') and command.extra in ('','unparsed') and PREFIX.match(command.value):
        if not PATTERN.fullmatch(command.value):raise ValueError('Use lab audit integration or lab memory wire without extra arguments')
        return Command('task',command.value)
    return command


def neurons(config):
    if not enabled(config):return []
    from ..neural.contracts import Neuron
    from ..neural.registry import ports
    return [Neuron(node_id=identity,kind='skill' if index==0 else 'verifier',capability=identity.split('@')[0],
        provider='jarvis.discovery.d',contract='explicit',inputs=ports(('request:Report',)) if index==0 else ports(('request:Report','report:Report')),
        outputs=ports(('report:Report',) if index==0 else ('verdict:Verdict',)),side_effect_class='read_only',privilege='read',
        requirements=('flag:lab.enabled',),timeout_ms=30000,resource_cost={'gpu_vram_mb':0,'money':0,'cpu_s_estimate':2},
        description='Inspect real Lab contracts, hard eligibility, typed memory references and retained learning proof',
        source='jarvis/discovery/d.py') for index,identity in enumerate(NODES)]


def sources(config,existing):return {**existing,'discovery_d':lambda:neurons(config)}


def compile_goal(goal,journal,config,graph_version=0):
    if not enabled(config) or not PATTERN.fullmatch(goal):return None
    from ..neural.compiler import _const
    from ..neural.execution import Bind,Plan,Step
    request=_const(journal,{'operation':PATTERN.fullmatch(goal)[1].lower()},'Report')
    return Plan(goal_id='g-'+uuid.uuid4().hex[:16],goal=goal,workflow='discovery.d',graph_version=graph_version,deadline_s=45,
        steps=[Step(step_id='run',neuron=NODES[0],bind={'request':request}),Step(step_id='check',neuron=NODES[1],bind={'request':request,'report':Bind(step='run',port='report')}),
            Step(step_id='answer',neuron='motor.report@v1',bind={'report':Bind(step='run',port='report'),'verdict':Bind(step='check',port='verdict')})],
        goal_verifier='check',answer_step='answer')


def adapters(graph,journal,registry,handlers):
    memory=LabMemory(journal);memory.migrate()
    for identity in NODES:
        if identity in graph.neurons:memory.put(Capability(id=identity,neuron_id=identity,intents=('Lab integration/reference audit',),
            golden_ref='tests/test_discovery_wiring.py',justification='Registered audit adapter; runtime audit does not promote capabilities or scientific claims.'))
    with journal.tx() as db:
        db.execute('CREATE TABLE IF NOT EXISTS discovery_integration_snapshots (ref TEXT PRIMARY KEY, inventory_ref TEXT NOT NULL, previous_ref TEXT)')

    def projection(env):
        from ..neural.policy import Context
        allowed=getattr(env.actions,'allowed_tools',None)
        context=Context(goal=env.notes.get('d_goal','lab audit integration'),config=env.config,
                        allowed_tools=allowed if isinstance(allowed,(set,frozenset)) else None)
        inventory=wiring.inventory(graph,registry,handlers,memory,context)
        refs,_=memory_graph.scan(memory);templates=wiring.template_check(journal,env.config,graph)
        return {'inventory':inventory,'memory':refs,'templates':templates,
                'passed':inventory['passed'] and refs['passed'] and refs['pending_links']==0 and templates['passed'],
                'evidence_status':'INSUFFICIENT_EVIDENCE','physical_validation':False,
                'scope':'contract/reference integration audit; no solver, model, permission change or scientific promotion'}

    def audit(neuron,inputs,env):
        if env.cancelled():raise ValueError('integration audit cancelled before inspection')
        operation=inputs['request']['operation']
        if operation not in ('audit integration','memory wire'):raise ValueError('unknown integration operation')
        if operation=='memory wire':memory_graph.wire(memory)
        result=projection(env)
        result['operation']=operation
        prior=journal.rows('SELECT inventory_ref FROM discovery_integration_snapshots ORDER BY rowid DESC LIMIT 1')
        previous_ref=prior[0]['inventory_ref'] if prior else None
        previous=json.loads(journal.get(previous_ref)) if previous_ref else None
        result['diff']=wiring.diff(previous,result['inventory']);result['previous_ref']=previous_ref
        inventory_ref=journal.put(result['inventory'],data_type='Report');ref=journal.put(result,data_type='Report')
        with journal.tx() as db:db.execute('INSERT OR IGNORE INTO discovery_integration_snapshots VALUES (?,?,?)',(ref,inventory_ref,previous_ref))
        return {'report':{'audit_ref':ref,'result':result}}

    def check(neuron,inputs,env):
        problems=[]
        try:
            report=inputs['report'];ref=report['audit_ref'];result=report['result']
            if env.cancelled():raise ValueError('audit cancelled')
            if json.loads(journal.get(ref))!=result:raise ValueError('audit receipt differs')
            rows=journal.rows('SELECT inventory_ref,previous_ref FROM discovery_integration_snapshots WHERE ref=?',(ref,))
            if not rows or rows[0]['previous_ref']!=result['previous_ref']:raise ValueError('actual registered audit required')
            expected=projection(env)
            expected['operation']=inputs['request']['operation']
            for key in expected:
                if expected[key]!=result[key]:raise ValueError('fresh contract/memory/eligibility inspection differs')
            previous=json.loads(journal.get(result['previous_ref'])) if result['previous_ref'] else None
            if result['diff']!=wiring.diff(previous,result['inventory']):raise ValueError('inventory diff differs')
            # A truthful failed audit is a completed inspection, not permission to
            # hide defects or promote the capabilities it inspected.
        except Exception:problems.append('integration inventory, typed reference, dependency or qualification check failed')
        return {'verdict':{'passed':not problems,'problems':problems,'evidence':['fresh registered contracts/handlers, compiled DAGs, typed references and retained qualification proof'] if not problems else []}}

    return {identity:handler for identity,handler in zip(NODES,(audit,check)) if identity in graph.neurons}
