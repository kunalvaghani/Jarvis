"""Real SQLite workflow integration. Fixtures never claim physical overnight acceptance."""
from dataclasses import asdict
import hashlib
import json
import queue
import random
import threading
from types import SimpleNamespace

import pytest

from jarvis.commands import Command
from jarvis.task_decisions import DecisionManager
from jarvis.task_ingress import TaskIngress
from jarvis.task_scheduler import ScheduledQueue
from jarvis.task_store import TaskStore
from jarvis.workflow_graph import TaskRelationshipResolver


@pytest.fixture
def runtime(tmp_path):
    store = TaskStore(tmp_path/'graph.sqlite3')
    scheduler = ScheduledQueue(store, observe=lambda:{'ram_available_mb':32000,'cpu_percent':0,'desktop':True,'battery_low':False})
    yield store, scheduler, scheduler.graph
    scheduler.close(); store.db.close()


def add(scheduler, text, kind='jarvis_status', **spec):
    return scheduler.put_nowait((0,Command(kind,text),threading.Event()),overrides=spec)


def complete(scheduler, state='COMPLETED', checkpoint=None):
    scheduler.outcome(state,'Actual fixture result',checkpoint or {})
    scheduler.task_done()


def resolved(store,scheduler,text,kind='task'):
    command = Command(kind,text)
    identity,_ = store.admit(asdict(command))
    store.transition(identity,'CLASSIFYING')
    resolution = TaskRelationshipResolver(scheduler.graph).resolve(identity,command)
    if resolution.get('question'):
        store.transition(identity,'WAITING_USER',checkpoint={'relationship_question':resolution})
    else:
        scheduler.put_nowait((0,command,threading.Event()),identity,
            {'dependencies':[d['upstream'] for d in resolution['dependencies']], 'graph_dependencies':resolution['dependencies']})
    return identity,resolution


def test_ten_random_order_nodes_release_by_graph_not_arrival(runtime):
    store,scheduler,graph=runtime
    order=list(range(10));random.Random(19).shuffle(order)
    nodes={n:add(scheduler,f'node {n}') for n in order}
    for n in range(1,10):graph.set_dependencies(nodes[n],[nodes[n-1]])
    executed=[]
    for n in range(10):
        scheduler.get(lane='background',timeout=0)
        executed.append(scheduler.local.identity);complete(scheduler)
    assert executed==[nodes[n] for n in range(10)]
    assert all(store.get(t)['state']=='COMPLETED' for t in nodes.values())


def test_same_project_context_does_not_impose_sequencing(runtime):
    store,scheduler,graph=runtime
    first,_=resolved(store,scheduler,'Analyze project "alpha"')
    second,_=resolved(store,scheduler,'Review documentation for project "alpha"')
    assert graph.group_for(first)['id']==graph.group_for(second)['id']
    assert graph.node(first)['workflow']!=graph.node(second)['workflow']
    assert graph.edges(second)==[]
    assert any(r['kind']=='SAME_PROJECT_AS' and not r['data']['ordering'] for r in graph.snapshot()['relationships'])


def test_unrelated_command_between_continuations_uses_compatible_entity(runtime):
    store,scheduler,graph=runtime
    scan,_=resolved(store,scheduler,'Find issues in project "alpha"')
    unrelated,_=resolved(store,scheduler,'Tell me local time',kind='jarvis_status')
    repair,resolution=resolved(store,scheduler,'Now fix those issues in project "alpha"')
    assert resolution['dependencies'][0]['upstream']==scan
    assert graph.node(scan)['workflow']==graph.node(repair)['workflow']
    assert unrelated not in store.get(repair)['spec']['dependencies']


def test_after_that_is_explicit_ordering_with_unique_lineage(runtime):
    store,scheduler,graph=runtime
    repair,_=resolved(store,scheduler,'Fix project "alpha"')
    test,resolution=resolved(store,scheduler,'After that, run all tests for project "alpha"')
    assert resolution['dependencies'][0]['upstream']==repair
    assert graph.edges(test)[0]['data']['condition']=='success'


def test_ambiguous_pronoun_never_selects_most_recent_project(runtime):
    store,scheduler,graph=runtime
    a,_=resolved(store,scheduler,'Find issues in project "alpha"')
    b,_=resolved(store,scheduler,'Find issues in project "beta"')
    fix,result=resolved(store,scheduler,'Now fix those issues')
    assert set(result['candidates'])=={a,b}
    assert store.get(fix)['state']=='WAITING_USER' and fix not in scheduler.items


def test_two_actual_result_handoffs_resolved_at_dispatch(runtime):
    store,scheduler,graph=runtime
    a=add(scheduler,'scan A'); b=add(scheduler,'scan B'); child=add(scheduler,'compare')
    graph.set_dependencies(child,[{'upstream':a,'requires_result':True},{'upstream':b,'requires_result':True}])
    for value in ['A','B']:
        scheduler.get(lane='background',timeout=0)
        scheduler.publish_output({'value':value},findings=[value],verified=True)
        complete(scheduler)
    scheduler.get(lane='background',timeout=0)
    assert scheduler.local.identity==child
    assert [r['structured_output']['value'] for r in scheduler.current_inputs()]==['A','B']
    assert store.get(child)['checkpoint']['input_versions']=={a:1,b:1}
    complete(scheduler)


def test_independent_safe_lanes_overlap_but_file_edits_do_not(runtime):
    store,scheduler,graph=runtime
    first=add(scheduler,'write same.txt','task')
    second=add(scheduler,'write same.txt','task')
    observation=add(scheduler,'read status')
    scheduler.get(timeout=0);assert scheduler.local.identity==first
    with pytest.raises(queue.Empty):scheduler.get(timeout=0)
    ran=[]
    def parallel():
        scheduler.get(lane='background',timeout=0);ran.append(scheduler.local.identity);complete(scheduler)
    thread=threading.Thread(target=parallel);thread.start();thread.join(3)
    assert ran==[observation] and first in scheduler.active
    complete(scheduler)
    scheduler.get(timeout=0);assert scheduler.local.identity==second;complete(scheduler)


@pytest.mark.parametrize('passed',[True,False])
def test_conditional_test_branches_require_structured_verification(runtime,passed):
    store,scheduler,graph=runtime
    tests=add(scheduler,'tests')
    yes=add(scheduler,'pass branch');no=add(scheduler,'failure branch')
    graph.set_dependencies(yes,[{'upstream':tests,'condition':'tests_pass'}])
    graph.set_dependencies(no,[{'upstream':tests,'condition':'tests_fail'}])
    scheduler.get(lane='background',timeout=0)
    complete(scheduler,checkpoint={'tests':{'verified':True,'passed':passed,'exit_code':0 if passed else 1}})
    scheduler.get(lane='background',timeout=0)
    assert scheduler.local.identity==(yes if passed else no)
    complete(scheduler)
    assert not graph.evaluate(no if passed else yes)['ready']


def test_prose_claim_that_tests_passed_is_not_verification(runtime):
    store,scheduler,graph=runtime
    tests=add(scheduler,'tests'); commit=add(scheduler,'commit')
    graph.set_dependencies(commit,[{'upstream':tests,'condition':'tests_pass'}])
    scheduler.get(lane='background',timeout=0);complete(scheduler,checkpoint={'tests':['all passed allegedly']})
    assert not graph.evaluate(commit)['ready']


def test_optional_failed_prerequisite_does_not_block_other_path(runtime):
    store,scheduler,graph=runtime
    bad=add(scheduler,'bad',priority=10);other=add(scheduler,'other');child=add(scheduler,'child')
    graph.set_dependencies(child,[{'upstream':bad,'optional':True},other])
    scheduler.get(lane='background',timeout=0);complete(scheduler,'FAILED')
    scheduler.get(lane='background',timeout=0);assert scheduler.local.identity==other;complete(scheduler)
    scheduler.get(lane='background',timeout=0);assert scheduler.local.identity==child;complete(scheduler)


def test_failed_required_branch_leaves_unrelated_group_eligible(runtime):
    store,scheduler,graph=runtime
    first=add(scheduler,'failure');blocked=add(scheduler,'blocked');independent=add(scheduler,'unrelated')
    graph.set_dependencies(blocked,[first])
    scheduler.get(lane='background',timeout=0);complete(scheduler,'FAILED')
    scheduler.get(lane='background',timeout=0);assert scheduler.local.identity==independent;complete(scheduler)
    assert store.get(blocked)['state']=='WAITING_DEPENDENCY'


def test_cycle_rejection_is_atomic_and_revision_preserved(runtime):
    store,scheduler,graph=runtime
    a=add(scheduler,'a');b=add(scheduler,'b');c=add(scheduler,'c')
    graph.set_dependencies(b,[a]);graph.set_dependencies(c,[b])
    revision=graph.snapshot()['revision']
    with pytest.raises(ValueError,match='cycle'):graph.set_dependencies(a,[c])
    assert graph.edges(a)==[] and graph.snapshot()['revision']==revision


def test_restart_preserves_graph_results_and_never_replays_uncertain_write(tmp_path):
    path=tmp_path/'queue.sqlite3'; store=TaskStore(path)
    scheduler=ScheduledQueue(store,observe=lambda:{'ram_available_mb':32000,'cpu_percent':0,'desktop':True})
    a=add(scheduler,'read');scheduler.get(lane='background',timeout=0);complete(scheduler)
    write=add(scheduler,'effect','task');graph=scheduler.graph;graph.set_dependencies(write,[a]);scheduler.get(timeout=0)
    receipt=tmp_path/'effect.txt';receipt.write_text('already written')
    scheduler.record_effect({'kind':'file','path':str(receipt),'sha256':hashlib.sha256(receipt.read_bytes()).hexdigest()})
    store.db.close()  # Simulate abrupt owner loss, no normal close/requeue.
    recovered_store=TaskStore(path);recovered=ScheduledQueue(recovered_store);recovered.restore(1)
    try:
        assert recovered_store.get(write)['state']=='PAUSED'
        assert recovered.graph.result(a)['verification']=='verified'
        assert recovered.graph.edges(write)[0]['upstream']==a and write not in recovered.items
        with pytest.raises(ValueError,match='replay'):recovered.control('resume',write)
        assert receipt.read_text()=='already written'
    finally:recovered.close();recovered_store.db.close()


def test_upstream_artifact_change_invalidates_transitive_results_without_replay(runtime,tmp_path):
    store,scheduler,graph=runtime
    path=tmp_path/'artifact.txt';path.write_text('first')
    a=add(scheduler,'produce');b=add(scheduler,'consume');c=add(scheduler,'later')
    graph.set_dependencies(b,[{'upstream':a,'requires_result':True}]);graph.set_dependencies(c,[b])
    scheduler.get(lane='background',timeout=0)
    scheduler.record_effect({'kind':'file','path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()});complete(scheduler)
    scheduler.get(lane='background',timeout=0);complete(scheduler)
    path.write_text('changed')
    assert not graph.evaluate(c)['ready']
    assert not graph.result(a)['valid'] and not graph.result(b)['valid']
    assert store.get(a)['state']=='COMPLETED' and store.get(b)['state']=='COMPLETED'
    assert not graph.evaluate(c)['ready']


def test_similar_wording_independent_projects_and_explicit_separation(runtime):
    store,scheduler,graph=runtime
    a,_=resolved(store,scheduler,'Analyze project "alpha"')
    b,_=resolved(store,scheduler,'Analyze project "beta"')
    c,_=resolved(store,scheduler,'Analyze project "alpha" as a separate workflow')
    assert graph.group_for(a)['id']!=graph.group_for(b)['id']
    assert graph.node(a)['workflow']!=graph.node(c)['workflow'] and graph.edges(c)==[]


def make_ingress(tmp_path):
    actions=SimpleNamespace(base=tmp_path,generation=0,closed=threading.Event(),queue_lock=threading.RLock(),
        pending_tasks=[],thread=threading.Thread(),report=lambda *_:None)
    ingress=TaskIngress(actions,tmp_path/'queue.sqlite3')
    ingress.scheduler.observe=lambda:{'ram_available_mb':32000,'cpu_percent':0,'desktop':True,'battery_low':False}
    return ingress


def test_dynamic_expansion_is_bounded_deduplicated_reviewed_and_atomic(tmp_path):
    ingress=make_ingress(tmp_path);scheduler=ingress.scheduler;graph=scheduler.graph
    try:
        parent=add(scheduler,'scan');scheduler.get(lane='background',timeout=0)
        scheduler.publish_output({'issues':['a','b']},verified=True);complete(scheduler)
        children=ingress.expand(parent,[Command('jarvis_status','a'),Command('task','repair b')],'scan-1')
        assert ingress.expand(parent,[Command('jarvis_status','ignored')],'scan-1')==children
        assert all(graph.node(t)['parent']==parent for t in children)
        scheduler.get(lane='background',timeout=0);assert scheduler.local.identity==children[0];complete(scheduler)
        with pytest.raises(queue.Empty):scheduler.get(timeout=0)
        assert ingress.store.get(children[1])['state']=='WAITING_APPROVAL'
        scheduler.control('review',children[1]);scheduler.get(timeout=0)
        assert scheduler.local.identity==children[1];complete(scheduler)
        before=len(ingress.store.rows());items=dict(scheduler.items)
        with pytest.raises(ValueError):ingress.expand(parent,[Command('jarvis_status','ok'),Command('delete','bad')],'invalid')
        assert len(ingress.store.rows())==before and scheduler.items==items
        with pytest.raises(ValueError):ingress.expand(parent,[Command('jarvis_status',str(i)) for i in range(21)],'too-many')
    finally:ingress.close();ingress.store.db.close()


def test_join_running_workflow_move_split_and_group_pause(runtime):
    store,scheduler,graph=runtime
    a,_=resolved(store,scheduler,'Analyze project "alpha"',kind='jarvis_status')
    scheduler.get(lane='background',timeout=0)
    b=add(scheduler,'later')
    graph.move(b,graph.node(a)['workflow'])
    group=graph.group_for(a);graph.update_group(group['id'],paused=True)
    complete(scheduler)
    with pytest.raises(queue.Empty):scheduler.get(lane='background',timeout=0)
    graph.update_group(group['id'],paused=False,priority=99)
    previous=graph.node(b)['workflow']; new=graph.split(b)
    assert new!=previous and store.history(b)
    scheduler.get(lane='background',timeout=0);complete(scheduler)


def test_low_risk_visible_twenty_second_graph_decision_and_sensitive_gate(tmp_path):
    ingress=make_ingress(tmp_path);scheduler=ingress.scheduler
    try:
        now=[1000.];ingress.decisions.clock=lambda:now[0]
        a=add(scheduler,'a');b=add(scheduler,'b')
        decision=ingress.propose_strategies('Routine read ordering',{'Independent':{b:[]},'Sequential':{b:[a]}},
            confidence=.95,reversible=True,sensitive=False)
        now[0]+=30;assert not ingress.decisions.tick()
        ingress.decisions.presented(decision);now[0]+=20
        for result in ingress.decisions.tick():ingress.apply_decision(result)
        assert ingress.decisions.rows()[0]['automatic']
        assert ingress.store.setting('graph_decision_applied:'+decision)
        high=ingress.propose_strategies('Sensitive strategy',{'One':{b:[]},'Two':{b:[a]}},
            confidence=1,reversible=True,sensitive=True)
        ingress.decisions.presented(high);now[0]+=20
        for result in ingress.decisions.tick():ingress.apply_decision(result)
        assert ingress.decisions.rows()[1]['status']=='WAITING_APPROVAL'
        assert not ingress.store.setting('graph_decision_applied:'+high)
    finally:ingress.close();ingress.store.db.close()


def test_group_report_records_actual_failures_artifacts_and_blockers(runtime,tmp_path):
    store,scheduler,graph=runtime
    a,_=resolved(store,scheduler,'Analyze project "alpha"',kind='jarvis_status')
    b=add(scheduler,'followup');graph.move(b,graph.node(a)['workflow']);graph.set_dependencies(b,[a])
    scheduler.get(lane='background',timeout=0);complete(scheduler,'FAILED')
    with pytest.raises(queue.Empty):scheduler.get(lane='background',timeout=0)
    report,path=scheduler.report(tmp_path/'reports')
    assert json.loads(path.read_text())==report
    group=next(g for g in report['graph']['groups'] if a in g['tasks'])
    assert group['counts']=={'FAILED':1,'WAITING_DEPENDENCY':1} and group['progress']==0
    assert report['graph']['evaluations'][b]['blockers'][0]['task']==a
    assert report['files']==[]


def test_graph_strategy_validation_rejects_cycle_without_partial_edits(tmp_path):
    ingress=make_ingress(tmp_path);scheduler=ingress.scheduler
    try:
        a=add(scheduler,'a');b=add(scheduler,'b');before=scheduler.graph.snapshot()['revision']
        with pytest.raises(ValueError,match='cycle'):
            ingress.propose_strategies('invalid',{'One':{b:[a]},'Cycle':{a:[b],b:[a]}},sensitive=False)
        assert scheduler.graph.edges()==[] and scheduler.graph.snapshot()['revision']==before
        assert not ingress.decisions.rows()
    finally:ingress.close();ingress.store.db.close()


def test_conditional_commit_and_exact_multiple_reference_resolution(runtime):
    store,scheduler,graph=runtime
    tests,_=resolved(store,scheduler,'Run tests for project "alpha"')
    commit,result=resolved(store,scheduler,"Don't commit anything until the verification passes for project \"alpha\"")
    assert result['dependencies'][0]['upstream']==tests
    assert result['dependencies'][0]['condition']=='tests_pass'
    explicit_gate,gate=resolved(store,scheduler,f'After task {store.get(tests)["number"]} commit only when verification passes')
    assert gate['dependencies'][0]['upstream']==tests
    assert gate['dependencies'][0]['condition']=='tests_pass'
    assert not graph.evaluate(explicit_gate)['ready']
    scan,_=resolved(store,scheduler,'Analyze project "beta"')
    consumer,result=resolved(store,scheduler,f'Use results from tasks {store.get(tests)["number"]} and {store.get(scan)["number"]} to compare')
    assert set(store.get(consumer)['spec']['dependencies'])=={tests,scan}


@pytest.mark.parametrize('prior_tests',[False,True])
def test_internal_repair_until_pass_does_not_require_previous_task(runtime,prior_tests):
    store,scheduler,graph=runtime
    if prior_tests:
        resolved(store,scheduler,'Run tests for project "alpha"')
    identity,result=resolved(store,scheduler,'Repair calculator for project "alpha". Prioritize the control exception, then continue until both original unittest suites pass.','code_task')
    assert not result.get('question')
    assert result['dependencies']==[]
    assert not store.get(identity)['spec'].get('dependencies')


def test_until_completion_is_distinct_from_release_and_explicit_context_gates(runtime):
    from jarvis.workflow_graph import requires_prior_test_result
    assert not requires_prior_test_result('Fix this calculator until its tests pass.')
    assert not requires_prior_test_result('Run the tests until all checks pass.')
    assert requires_prior_test_result("Don't commit anything until verification passes.")
    assert requires_prior_test_result('Wait until tests pass before publishing.')
    assert requires_prior_test_result('Commit only when verification passes.')
    assert requires_prior_test_result('Repair the UI if those tests fail.')
    assert requires_prior_test_result('Continue until those tests pass.')
    store,scheduler,graph=runtime
    upstream,_=resolved(store,scheduler,'Analyze project "alpha"')
    identity,result=resolved(store,scheduler,f'Use results from task {store.get(upstream)["number"]} to repair until tests pass')
    assert result['dependencies'][0]['upstream']==upstream
    assert result['dependencies'][0]['condition']=='success'


def test_intake_does_not_coerce_internal_completion_loop_into_context_command():
    ingress=SimpleNamespace(local=SimpleNamespace())
    command=Command('ask','Repair this calculator. Continue until both original unittest suites pass.')
    assert TaskIngress._parse(ingress,command) is command
    assert ingress.local.new_task is False
    gated=TaskIngress._parse(ingress,Command('ask',"Don't commit until verification passes."))
    assert gated.kind=='task' and ingress.local.new_task is True


def test_pending_named_project_reference_resolves_when_producer_arrives(tmp_path):
    ingress=make_ingress(tmp_path);scheduler=ingress.scheduler;store=ingress.store
    try:
        child,_=store.admit(asdict(Command('task','Now fix those issues in project "alpha"')))
        store.transition(child,'CLASSIFYING');ingress.local.identity=child;ingress.local.overrides={}
        token=threading.Event();ingress.actions.pending_tasks.append((token,Command('task','repair')))
        ingress.enqueue((0,Command('task','Now fix those issues in project "alpha"'),token))
        assert store.get(child)['state']=='WAITING_USER'
        parent,_=resolved(store,scheduler,'Find issues in project "alpha"')
        ingress._resolve_waiting_relationships()
        assert store.get(child)['state']=='QUEUED'
        assert graph_dependencies(scheduler,child)==[parent]
        assert scheduler.graph.node(child)['workflow']==scheduler.graph.node(parent)['workflow']
    finally:ingress.close();store.db.close()


def graph_dependencies(scheduler,task):
    return [e['upstream'] for e in scheduler.graph.edges(task)]


def test_exact_artifact_reference_uses_verified_producer(runtime,tmp_path):
    store,scheduler,graph=runtime
    artifact=tmp_path/'actual-report.txt';artifact.write_text('verified contents')
    parent=add(scheduler,'scan');scheduler.get(lane='background',timeout=0)
    scheduler.record_effect({'kind':'file','path':str(artifact),'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest()});complete(scheduler)
    child,result=resolved(store,scheduler,'Use actual-report.txt to prepare a comparison')
    assert result['dependencies'][0]['upstream']==parent and graph_dependencies(scheduler,child)==[parent]


def test_expansion_tool_uses_existing_registry_and_deny_policy(tmp_path):
    from jarvis.tools import ToolRegistry,ToolArgumentError
    ingress=make_ingress(tmp_path);scheduler=ingress.scheduler
    ingress.actions.ingress=ingress
    try:
        parent=add(scheduler,'parent');scheduler.get(lane='background',timeout=0)
        registry=ToolRegistry(ingress.actions)
        step={'action':'workflow_expand','value':'stable-key','content':json.dumps({'requests':[asdict(Command('task','repair scoped issue'))]})}
        result=registry.execute(step,lambda:False)
        children=json.loads(result.evidence)['children'];assert len(children)==1
        assert scheduler.graph.node(children[0])['parent']==parent
        assert registry.execute(step,lambda:False).evidence==result.evidence
        invalid={**step,'content':json.dumps({'requests':[asdict(Command('task','unsafe','approved_plan'))]})}
        with pytest.raises(ToolArgumentError):registry.execute(invalid,lambda:False)
        policy=tmp_path/'.jarvis';policy.mkdir(exist_ok=True)
        (policy/'policy.json').write_text(json.dumps({'deny_tools':['workflow_expand']}))
        with pytest.raises(ValueError,match='denied'):registry.execute({**step,'value':'new-key'},lambda:False)
        complete(scheduler)
    finally:ingress.close();ingress.store.db.close()


def test_graph_decision_committed_before_crash_applies_once_after_restart(tmp_path):
    ingress=make_ingress(tmp_path);scheduler=ingress.scheduler
    try:
        a=add(scheduler,'a');b=add(scheduler,'b');now=[1000.];ingress.decisions.clock=lambda:now[0]
        identity=ingress.propose_strategies('Routine order',{'Sequential':{b:[a]},'Independent':{b:[]}},
            confidence=.95,reversible=True,sensitive=False)
        ingress.decisions.presented(identity);now[0]+=20
        selected=ingress.decisions.tick()[0] # Simulated owner loss before apply.
        assert not ingress.store.setting('graph_decision_applied:'+identity)
        ingress.apply_graph_decision(selected);revision=scheduler.graph.snapshot()['revision']
        ingress.apply_graph_decision(selected)
        assert graph_dependencies(scheduler,b)==[a] and scheduler.graph.snapshot()['revision']==revision
    finally:ingress.close();ingress.store.db.close()


def test_strategy_cannot_remove_existing_verification_condition(tmp_path):
    ingress=make_ingress(tmp_path);scheduler=ingress.scheduler
    try:
        a=add(scheduler,'tests');b=add(scheduler,'commit','task')
        scheduler.graph.set_dependencies(b,[{'upstream':a,'condition':'tests_pass'}])
        with pytest.raises(ValueError,match='cannot remove'):
            ingress.propose_strategies('Unsafe weakening',{'Skip gate':{b:[]},'Keep':{b:[a]}},confidence=1,reversible=True,sensitive=False)
        assert scheduler.graph.edges(b)[0]['data']['condition']=='tests_pass'
    finally:ingress.close();ingress.store.db.close()


def test_unverified_generic_completion_cannot_feed_result_dependent_write(runtime):
    store,scheduler,graph=runtime
    parent=add(scheduler,'claims success','task');child=add(scheduler,'repair','task')
    graph.set_dependencies(child,[{'upstream':parent,'requires_result':True}])
    scheduler.get(timeout=0);complete(scheduler)
    assert graph.result(parent)['verification']=='unverified'
    with pytest.raises(queue.Empty):scheduler.get(timeout=0)
    assert store.get(child)['state']=='WAITING_DEPENDENCY'


def test_large_result_bundle_defers_without_killing_worker(runtime):
    store,scheduler,graph=runtime
    parents=[]
    for i in range(4):
        parent=add(scheduler,str(i));parents.append(parent)
        scheduler.get(lane='background',timeout=0);scheduler.publish_output({'data':'x'*14000},verified=True);complete(scheduler)
    child=add(scheduler,'large input');graph.set_dependencies(child,parents)
    with pytest.raises(queue.Empty):scheduler.get(lane='background',timeout=0)
    assert store.get(child)['state']=='WAITING_DEPENDENCY'
    assert graph.evaluate(child)['blockers'][-1]['condition']=='bounded_result_context'


def test_group_priority_unlocks_descendant_but_blocked_node_stays_ineligible(runtime):
    store,scheduler,graph=runtime
    a=add(scheduler,'prerequisite');blocked=add(scheduler,'important child',priority=100)
    unrelated=add(scheduler,'other',priority=5)
    graph.set_dependencies(blocked,[a]);graph.update_group(graph.group_for(a)['id'],priority=10)
    scheduler.get(lane='background',timeout=0)
    assert scheduler.local.identity==a and blocked not in scheduler.active
    complete(scheduler);scheduler.get(lane='background',timeout=0)
    assert scheduler.local.identity==blocked;complete(scheduler)


def test_real_queue_database_migration_keeps_prior_outcomes_and_dependencies(tmp_path):
    store=TaskStore(tmp_path/'legacy.sqlite3')
    a,_=store.admit(asdict(Command('jarvis_status','old result')));store.transition(a,'CLASSIFYING')
    store.transition(a,'COMPLETED',outcome='Previously reported status',spec={'read_only':True})
    b,_=store.admit(asdict(Command('task','old pending')));store.transition(b,'CLASSIFYING')
    from jarvis.task_policy import classify
    store.transition(b,'QUEUED',spec={**classify(asdict(Command('task','old pending'))),'dependencies':[a]})
    scheduler=ScheduledQueue(store)
    try:
        assert graph_dependencies(scheduler,b)==[a] and scheduler.graph.result(a)['outcome']=='COMPLETED'
        assert store.get(a)['state']=='COMPLETED' and store.get(b)['state']=='QUEUED'
        revision=scheduler.graph.snapshot()['revision'];scheduler.graph.migrate()
        assert scheduler.graph.snapshot()['revision']==revision
    finally:scheduler.close();store.db.close()


def test_conversation_and_observed_project_must_agree_to_disambiguate(runtime):
    store,scheduler,graph=runtime
    a,_=resolved(store,scheduler,'Find issues in project "alpha"')
    b,_=resolved(store,scheduler,'Find issues in project "beta"')
    command=Command('task','Now fix those issues');task,_=store.admit(asdict(command));store.transition(task,'CLASSIFYING')
    weak=TaskRelationshipResolver(graph,lambda:{'referenced_projects':['alpha'],'active_projects':[]})
    assert weak.resolve(task,command).get('question')
    strong=TaskRelationshipResolver(graph,lambda:{'referenced_projects':['alpha'],'active_projects':['alpha']})
    assert strong.resolve(task,command)['dependencies'][0]['upstream']==a


def test_result_invalidation_is_idempotent_and_report_scopes_shared_group_to_batch(runtime,tmp_path):
    store,scheduler,graph=runtime
    old=add(scheduler,'old');scheduler.get(lane='background',timeout=0);complete(scheduler)
    new=add(scheduler,'new');graph.move(new,graph.node(old)['workflow']);graph.set_dependencies(new,[old])
    store.setting('batch_start',store.get(new)['number'])
    report,_=scheduler.report(tmp_path/'reports')
    assert report['graph']['groups'][0]['tasks']==[new]
    assert report['graph']['reused_prerequisites'][0]['task_id']==old
    graph.invalidate(old,'changed');revision=graph.snapshot()['revision'];graph.invalidate(old,'changed')
    assert graph.snapshot()['revision']==revision


def test_workflow_expansion_total_quota_and_depth_are_not_bypassed(tmp_path):
    ingress=make_ingress(tmp_path);scheduler=ingress.scheduler
    try:
        parent=add(scheduler,'parent');scheduler.get(lane='background',timeout=0);complete(scheduler)
        for key,size in [('one',20),('two',20),('three',10)]:
            ingress.expand(parent,[Command('jarvis_status','uptime') for _ in range(size)],key)
        with pytest.raises(ValueError,match='quota'):
            ingress.expand(parent,[Command('jarvis_status','uptime')],'over-quota')
        other=add(scheduler,'other root')
        # Bind execution explicitly using priority; descendants are independent safe observations.
        scheduler.control('urgent',other,100);scheduler.get(lane='background',timeout=0);assert scheduler.local.identity==other
        complete(scheduler)
        lineage=other
        for i in range(3):
            child=ingress.expand(lineage,[Command('jarvis_status','uptime')],f'depth-{i}')[0]
            scheduler.control('urgent',child,100);scheduler.get(lane='background',timeout=0)
            assert scheduler.local.identity==child;complete(scheduler);lineage=child
        with pytest.raises(ValueError,match='depth'):
            ingress.expand(lineage,[Command('jarvis_status','uptime')],'too-deep')
    finally:ingress.close();ingress.store.db.close()


def test_late_graph_decision_defers_when_task_has_started(tmp_path):
    ingress=make_ingress(tmp_path);scheduler=ingress.scheduler
    try:
        a=add(scheduler,'a');b=add(scheduler,'b');clock=[1000.];ingress.decisions.clock=lambda:clock[0]
        decision=ingress.propose_strategies('Routine strategy',{'Sequential':{b:[a]},'Independent':{b:[]}},
            confidence=.95,reversible=True,sensitive=False)
        scheduler.control('urgent',b,100);scheduler.get(lane='background',timeout=0);assert scheduler.local.identity==b
        ingress.decisions.presented(decision);clock[0]+=20
        ingress.apply_decision(ingress.decisions.tick()[0])
        assert ingress.store.setting('graph_decision_deferred:'+decision)
        assert scheduler.graph.edges(b)==[]
        complete(scheduler)
    finally:ingress.close();ingress.store.db.close()


def test_new_verification_gate_added_during_decision_cannot_be_removed(tmp_path):
    ingress=make_ingress(tmp_path);scheduler=ingress.scheduler
    try:
        a=add(scheduler,'tests');b=add(scheduler,'consumer');now=[1000.];ingress.decisions.clock=lambda:now[0]
        decision=ingress.propose_strategies('Routine ordering',{'Independent':{b:[]},'Sequential':{b:[a]}},
            confidence=.95,reversible=True,sensitive=False)
        scheduler.graph.set_dependencies(b,[{'upstream':a,'condition':'tests_pass'}])
        ingress.decisions.presented(decision);now[0]+=20
        ingress.apply_decision(ingress.decisions.tick()[0])
        assert ingress.store.setting('graph_decision_deferred:'+decision)
        assert scheduler.graph.edges(b)[0]['data']['condition']=='tests_pass'
    finally:ingress.close();ingress.store.db.close()


def test_result_commit_fault_keeps_effect_owner_until_reconciliation(runtime,monkeypatch):
    store,scheduler,graph=runtime
    task=add(scheduler,'write','task');scheduler.get(timeout=0)
    def fault(_):raise OSError('injected result metadata fault')
    monkeypatch.setattr(graph,'publish',fault)
    scheduler.outcome('COMPLETED','effect already happened')
    with pytest.raises(OSError):scheduler.task_done()
    assert task in scheduler.active and scheduler.held
    assert store.get(task)['state']=='VERIFYING'
    scheduler.close()
    assert store.get(task)['state']=='PAUSED' and store.get(task)['checkpoint']['uncertain']


def test_same_work_for_new_application_keeps_new_project_owner(runtime):
    store,scheduler,graph=runtime
    source,_=resolved(store,scheduler,'Analyze project "alpha"')
    target,result=resolved(store,scheduler,'Do the same for Blender')
    assert result['dependencies'][0]['upstream']==source
    assert graph.group_for(target)['project']=='blender'
    assert graph.node(target)['workflow']!=graph.node(source)['workflow']


def test_native_group_controls_hide_empty_moved_groups_and_preserve_task_inspection(tmp_path):
    import tkinter as tk
    from jarvis.island_queue import QueueView
    ingress=make_ingress(tmp_path);ingress.actions.ingress=ingress
    root=tk.Tk();root.withdraw()
    try:
        first=add(ingress.scheduler,'first');second=add(ingress.scheduler,'second')
        empty=ingress.scheduler.graph.group_for(second)['id']
        ingress.scheduler.graph.move(second,ingress.scheduler.graph.node(first)['workflow'])
        view=QueueView(root,SimpleNamespace(actions=ingress.actions,report=ingress.actions.report));view.tick()
        assert empty not in view.groups.get_children() and ingress.scheduler.graph.group(empty)
        view.groups.selection_set(ingress.scheduler.graph.group_for(first)['id']);view.group_action('pause')
        assert ingress.scheduler.graph.group_for(first)['paused']
        view.group_action('resume');view.tree.selection_set(second);view.inspect()
        assert 'ownership' in view.detail.get('1.0','end') and 'requirements' in view.detail.get('1.0','end')
    finally:root.destroy();ingress.close();ingress.store.db.close()


@pytest.mark.parametrize('age,status,visible,expected',[(10,'open',True,['alpha']),
    (31,'open',True,[]),(10,'closed',True,[]),(10,'open',False,[]),(-1,'open',True,[])])
def test_cached_application_context_must_be_recent_open_and_visible(tmp_path,age,status,visible,expected):
    ingress=make_ingress(tmp_path)
    try:
        resolved(ingress.store,ingress.scheduler,'Find issues in project "alpha"')
        ingress.actions.knowledge=SimpleNamespace(history=[{'role':'user','content':'Work on project "alpha"'}])
        ingress.actions.live_app=SimpleNamespace(lock=threading.RLock(),current=1,clock=lambda:100.,
            windows={1:{'title':'alpha project','status':status,'visible':visible,'observed_at':100.-age}})
        context=ingress._relationship_context()
        assert context['referenced_projects']==['alpha'] and context['active_projects']==expected
    finally:ingress.close();ingress.store.db.close()


def test_compact_island_body_scrolls_and_timer_requires_fully_visible_question(tmp_path):
    import tkinter as tk
    from jarvis.island_queue import QueueView
    ingress=make_ingress(tmp_path);ingress.actions.ingress=ingress
    root=tk.Tk();root.geometry('80x55+20+20')
    try:
        view=QueueView(root,SimpleNamespace(actions=ingress.actions,report=ingress.actions.report))
        decision=ingress.decisions.create(None,'Routine strategy',['Independent observations','Sequential observations'],
            confidence=.95,reversible=True,sensitive=False)
        view.tick();root.update();view.tick()
        assert ingress.decisions.rows()[0]['presented_at'] is None
        root.geometry('614x360+20+20');root.update();view.tick();root.update();view.tick()
        assert view.decision_visible() and ingress.decisions.rows()[0]['presented_at'] is not None
        assert view.canvas.yview()[1]<1
        view.canvas.yview_moveto(1);root.update()
        assert view.decision_visible()  # Body scrolling cannot hide the pending strategy.
        assert view.canvas.yview()[1]==pytest.approx(1)
        root.withdraw();root.update();assert not view.decision_visible()
        assert not view.body.winfo_ismapped()
        root.deiconify();root.update();assert view.body.winfo_ismapped()
        assert view.canvas.yview()[1]==pytest.approx(1)
    finally:root.destroy();ingress.close();ingress.store.db.close()
