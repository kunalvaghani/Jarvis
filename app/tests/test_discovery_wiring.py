"""Phase D uses actual registry/compiler/dispatcher and typed Journal data, no solver/model fakes as proof."""
import copy,json
from types import SimpleNamespace
import pytest
from jarvis.discovery import contracts as C
from jarvis.discovery import wiring,memory_graph as mg,d
from jarvis.discovery.memory import LabMemory
from jarvis.neural.service import BrainService,act
from jarvis.neural.policy import Context

ON={'neural':{'mode':'act','learning':'shadow'},'lab':{'enabled':True,'sim':True,'research':True,'learning':True}}

@pytest.fixture
def service(tmp_path):
    s=BrainService(copy.deepcopy(ON),tmp_path/'brain.sqlite3')
    yield s
    s.journal.close()


def inventory(s):return wiring.inventory(s.graph,s.registry,s.dispatcher.adapters,LabMemory(s.journal),Context(config=s.config))


def test_every_registered_capability_has_explicit_contract_handler_and_owned_metadata(service):
    r=inventory(service)
    assert r['passed'] and r['registered_count']==52 and len(wiring.descriptors())==52
    assert all(n['handler_present'] and n['contract']=='explicit' and n['test_sha256'] and n['skill_sha256'] for n in r['nodes'])
    assert {n['verification'] for n in r['nodes']}=={'UNVERIFIED'}
    assert wiring.template_check(service.journal,ON,service.graph)['passed']
    assert len(wiring.template_check(service.journal,ON,service.graph)['workflows'])==43


@pytest.mark.parametrize('sim,research,learning',[(s,r,l) for s in (True,False) for r in (True,False) for l in (True,False)])
def test_all_feature_combinations_preserve_inventory_and_existing_eligibility(tmp_path,sim,research,learning):
    config={'neural':{'mode':'act'},'lab':{'enabled':True,'sim':sim,'research':research,'learning':learning}}
    s=BrainService(config,tmp_path/'j.sqlite3')
    try:
        r=inventory(s);assert r['passed']
        for row in r['nodes']:
            if not sim and 'flag:lab.sim' in s.graph.neurons[row['node_id']].requirements:assert not row['eligible']
        native=next(n for n in r['nodes'] if n['node_id']=='discovery.geometry.pendulum@v1')
        assert native['needs_approval']
    finally:s.journal.close()


def test_inventory_catches_unmapped_contract_handler_and_dependency_drift(service,monkeypatch):
    handlers=service.dispatcher.adapters
    monkeypatch.delitem(handlers,'discovery.optimization.advance@v1')
    assert any(p['code']=='missing_handler' for p in inventory(service)['issues'])
    rows=list(wiring.descriptors());rows[0]=rows[0].model_copy(update={'requires':('discovery.absent@v1',)})
    monkeypatch.setattr(wiring,'descriptors',lambda:tuple(rows))
    assert any(p['code']=='dangling_dependency' for p in inventory(service)['issues'])
    node=service.graph.neurons['discovery.optimization.advance@v1'];old=node.contract;node.contract='derived'
    try:assert any(p['code']=='contract_drift' for p in inventory(service)['issues'])
    finally:node.contract=old


def test_descriptor_schema_rejects_unknown_memory_kind_and_escaped_source():
    row=wiring.descriptors()[0].model_dump(mode='json');row['memory_kinds']=['InventedTruth']
    with pytest.raises(ValueError):wiring.Descriptor.model_validate_json(json.dumps(row))
    row=wiring.descriptors()[0].model_dump(mode='json');row['test_ref']='secrets/private.json'
    with pytest.raises(ValueError):wiring.Descriptor.model_validate_json(json.dumps(row))
    with pytest.raises(ValueError):wiring._owned_file('../../outside-owned-root.txt')


def test_memory_dependencies_capture_revisions_preserve_authored_evidence_and_names(service):
    m=LabMemory(service.journal);source=C.Source(id='spec',locator='fixture-reference');m.put(source)
    c=C.Component(id='wing',name='front wing',reality_class='R2',source_ids=('spec',));m.put(c)
    m.put(source.model_copy(update={'revision':2,'locator':'revised-reference'}));m.put(c)
    edge=service.journal.rows("SELECT target_revision FROM discovery_edges WHERE source='wing' AND target='spec'")
    assert edge==[{'target_revision':1}]
    m.put(C.Claim(id='claim',text='conditional claim',reality_class='T1',source_ids=('spec',)))
    authored=C.Edge(source='claim',target='spec',target_revision=2,relation='derived_from',source_ref='precise excerpt')
    m.link(authored);m.put(m.get('claim'));assert m.link(authored)
    assert mg.scan(m)[0]['passed']
    assert m.resolve('front wng','Component')==[c]
    m.put(C.Component(id='another-wing',name='front wing',reality_class='P1'))
    assert {r.id for r in m.resolve('front wing','Component')}=={'wing','another-wing'}
    assert m.resolve('wing','Component')==[c]
    with pytest.raises(ValueError):m.resolve('wing','MadeUp')


def test_forward_references_are_never_invented_and_explicit_wire_is_idempotent(service):
    m=LabMemory(service.journal)
    m.put(C.Component(id='dependent',name='child',parent_id='parent',reality_class='P1',source_ids=('missing',)))
    report,_=mg.scan(m);assert not report['passed'] and len(report['issues'])==2
    with pytest.raises(ValueError):mg.wire(m)
    assert not service.journal.rows("SELECT * FROM discovery_edges WHERE source='dependent'")
    m.put(C.Source(id='missing',locator='fixture-reference'));m.put(C.Component(id='parent',name='parent',reality_class='R1'))
    assert mg.scan(m)[0]['pending_links']==2
    first=mg.wire(m);assert first['passed'] and first['pending_links']==0
    assert mg.wire(m)==first
    assert not service.journal.rows("SELECT * FROM discovery_edges WHERE relation IN ('supports','contradicts')")


def test_wrong_kind_corrupt_artifact_and_bounded_audit_fail_closed(service,monkeypatch):
    m=LabMemory(service.journal);m.put(C.Component(id='wrong',name='wrong',reality_class='R2'))
    m.put(C.Claim(id='bad',text='conditional',reality_class='T1',source_ids=('wrong',)))
    assert any(p['code']=='reference_kind_or_self' for p in mg.scan(m)[0]['issues'])
    ref=m.put(C.Source(id='corrupt',locator='old-reference'))
    with service.journal.tx() as db:db.execute("UPDATE artifacts SET body=REPLACE(body,'old-reference','forged-reference') WHERE ref=?",(ref,))
    assert any(p['code']=='record_or_artifact_integrity' for p in mg.scan(m)[0]['issues'])
    monkeypatch.setattr(mg,'MAX_RECORDS',1)
    assert not mg.scan(m)[0]['complete']


def test_historical_failed_gap_is_retained_but_cannot_become_verified(service):
    m=LabMemory(service.journal);m.put(C.LearningEpisode(id='failed-gap',gap='unsupported solver',tool_id='never-installed',stage='review_failed'))
    r,_=mg.scan(m);assert r['passed'] and r['notices'][0]['code']=='retained_tool_gap'
    original=m.get('discovery.optimization.advance@v1')
    m.put(original.model_copy(update={'revision':2,'verification':'VERIFIED'}))
    r=inventory(service);assert not r['passed'] and any(p['code']=='unsupported_verified_state' for p in r['issues'])
    assert service.registry.get(original.id).status=='active'  # Audit never changes permission/status.


def test_real_ingress_audit_and_wire_keep_truthful_defects_visible(service,tmp_path):
    from jarvis.actions import Actions
    from jarvis.engine import Engine
    from jarvis.commands import Command
    a=Actions.__new__(Actions);a.config,a.base,a._neural_service,a.allowed_tools=ON,tmp_path,service,None
    commands=[];e=Engine(commands.append,lambda *args:None);e.activate();e.feed('lab audit integration',final=True,raw='lab audit integration')
    answer=a.execute(commands[0]);assert 'registered_count' in answer and '27' in answer
    first=service.journal.rows('SELECT ref FROM discovery_integration_snapshots ORDER BY rowid DESC LIMIT 1')[0]['ref']
    saved=json.loads(service.journal.get(first));assert saved['passed'] and len(saved['diff']['added'])==52
    a.execute(Command('task','lab audit integration'))
    latest=service.journal.rows('SELECT ref FROM discovery_integration_snapshots ORDER BY rowid DESC LIMIT 1')[0]['ref']
    assert json.loads(service.journal.get(latest))['diff']=={'added':[],'removed':[],'changed':[]}
    m=LabMemory(service.journal);m.put(C.Claim(id='forward',text='a conditional input',reality_class='T1',source_ids=('late-source',)))
    a.execute(Command('task','lab audit integration'))
    row=service.journal.rows('SELECT ref FROM discovery_integration_snapshots ORDER BY rowid DESC LIMIT 1')[0]
    assert not json.loads(service.journal.get(row['ref']))['passed']
    m.put(C.Source(id='late-source',locator='fixture-reference'))
    a.execute(Command('task','lab memory wire'));assert mg.scan(m)[0]['pending_links']==0
    a.config={}
    with pytest.raises(ValueError,match='no planner fallback'):a.execute(Command('task','lab audit integration'))


def test_audit_verifier_rejects_caller_report_without_real_receipt(service):
    from jarvis.neural.dispatcher import Env
    check=service.dispatcher.adapters[d.NODES[1]]
    r=check(None,{'request':{'operation':'audit integration'},'report':{'audit_ref':'missing','result':{'passed':True}}},Env(config=ON))
    assert not r['verdict']['passed']


def test_inventory_diff_preserves_deletions_and_changed_contracts():
    old={'nodes':[{'node_id':'old','contract':'explicit'},{'node_id':'same','version':1}]}
    new={'nodes':[{'node_id':'new','contract':'explicit'},{'node_id':'same','version':2}]}
    assert wiring.diff(old,new)=={'added':['new'],'removed':['old'],'changed':['same']}


def test_memory_parent_cycles_are_reported_without_hiding_history(service):
    m=LabMemory(service.journal)
    m.put(C.Component(id='a',name='a',parent_id='b',reality_class='P1'))
    m.put(C.Component(id='b',name='b',parent_id='a',reality_class='P1'))
    assert any(p['code']=='memory_dependency_cycle' for p in mg.scan(m)[0]['issues'])
    with pytest.raises(ValueError):mg.wire(m)
    assert m.get('a') is not None and m.get('b') is not None


def test_actual_golden_and_three_verified_uses_are_required_by_inventory(service):
    from jarvis.discovery.sandbox.env_manager import units_environment
    from jarvis.discovery.learning import LearningGate
    if not units_environment()['pins_match']:pytest.skip('approved isolated units worker unavailable')
    m=LabMemory(service.journal);gate=LearningGate(m,service.registry,ON)
    source=C.Source(id='pint-source',locator='https://pypi.org/project/Pint/0.25.2/',license='BSD-3-Clause')
    tool=C.Tool(id='pint-tool',name='Pint',version='0.25.2',environment=units_environment()['environment'],license='BSD-3-Clause')
    episode,candidate=gate.qualify(tool,source,'discovery.units.convert@v1')
    a=SimpleNamespace(config=ON,_neural_service=service,allowed_tools=None)
    for value in (1,2,3):
        act(a,f'lab convert {value} km to m',lambda:False)
        goal=service.journal.rows('SELECT goal_id FROM goals ORDER BY rowid DESC LIMIT 1')[0]['goal_id']
        gate.observe_use(episode.id,candidate.node_id,goal)
    service.rebuild();mg.wire(m)
    assert inventory(service)['passed']
    row=next(r for r in inventory(service)['nodes'] if r['node_id']==candidate.node_id)
    assert row['verification']=='VERIFIED' and row['eligible']
    registered=service.registry.get(candidate.node_id);original=registered.requirements
    registered.requirements=()
    try:assert any(p['code']=='unsupported_verified_state' for p in inventory(service)['issues'])
    finally:registered.requirements=original
    promoted=m.get(episode.id)
    m.put(promoted.model_copy(update={'revision':promoted.revision+1,'successful_goal_ids':(goal,goal,goal)}))
    assert any(p['code']=='unsupported_verified_state' for p in inventory(service)['issues'])
