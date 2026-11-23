"""Typed reference projection inside LabMemory's existing Journal, never a second graph store.

Declared references express provenance/dependency, not scientific support. Missing
targets stay visible; no source, solver value or successful learning event is invented.
"""
from __future__ import annotations
import hashlib,json
from .contracts import Edge,RECORD,Capability,Component,Experiment,Skill,LearningEpisode,RunArtifact

MAX_RECORDS=2000
MAX_EDGES=10000


def declared(record):
    # Requires expresses a typed source/context dependency. Authored derived_from,
    # supports and contradicts evidence links remain separate and immutable.
    refs=[(identity,'Source','requires') for identity in record.source_ids]
    if isinstance(record,Component) and record.parent_id:refs.append((record.parent_id,'Component','requires'))
    if isinstance(record,Experiment):
        refs += [(identity,'RunArtifact','requires') for identity in record.artifact_ids]
        if record.parent_id:refs.append((record.parent_id,'Experiment','derived_from'))
    if isinstance(record,Skill):refs += [(identity,'Tool','uses_tool') for identity in record.tool_ids]
    if isinstance(record,LearningEpisode):refs.append((record.tool_id,'Tool','uses_tool'))
    # Scenario/Experiment parameters are embedded typed values, not duplicate memory nodes.
    for parameter in getattr(record,'parameters',()):
        refs += [(identity,'Source','requires') for identity in parameter.source_ids]
    return sorted(set(refs))


def _edge(memory,record,target_id,kind,relation):
    target=memory.get(target_id)
    if target is None or target.kind!=kind or target.id==record.id:return None
    return Edge(source=record.id,source_revision=record.revision,target=target.id,target_revision=target.revision,
                relation=relation,source_ref=memory.journal.rows('SELECT ref FROM discovery_records WHERE id=? AND revision=?',
                         (record.id,record.revision))[0]['ref'])


def index_ready(memory,record):
    """Add only resolvable, kind-correct relations after the record's immutable commit.

    Back/forward references unresolved during a multi-record save are reconciled by
    the explicit wire command. Existing evidence-bearing links are never replaced.
    """
    for identity,kind,relation in declared(record):
        if memory.journal.rows('SELECT ref FROM discovery_edges WHERE source=? AND source_revision=? AND target=? AND relation=?',
                               (record.id,record.revision,identity,relation)):continue
        edge=_edge(memory,record,identity,kind,relation)
        if edge is None:continue
        existing=memory.journal.rows('SELECT ref FROM discovery_edges WHERE source=? AND source_revision=? AND '
            'target=? AND target_revision=? AND relation=?',(edge.source,edge.source_revision,edge.target,edge.target_revision,edge.relation))
        if not existing:memory.link(edge)


def scan(memory):
    """Read all revisions within explicit bounds. Report an incomplete scan as failing."""
    from ..neural.contracts import artifact_ref
    j=memory.journal;issues=[];notices=[];records={};kinds={};pending=[]
    rows=j.rows('SELECT id,revision,kind,ref FROM discovery_records ORDER BY id,revision LIMIT ?',(MAX_RECORDS+1,))
    edges=j.rows('SELECT * FROM discovery_edges ORDER BY source,source_revision,target,target_revision,relation LIMIT ?',(MAX_EDGES+1,))
    if len(rows)>MAX_RECORDS or len(edges)>MAX_EDGES:
        return {'passed':False,'issues':[{'code':'scan_limit','id':'scientific-memory'}], 'notices':[],
                'record_count':len(rows),'edge_count':len(edges),'pending_links':0,'kind_counts':{},'complete':False},[]
    for row in rows:
        try:
            body=j.get(row['ref'])
            if body is None or artifact_ref(body)!=row['ref']:raise ValueError('record artifact hash mismatch')
            record=RECORD.validate_json(body)
            if (record.id,record.revision,record.kind)!=(row['id'],row['revision'],row['kind']):raise ValueError('index mismatch')
            records[(record.id,record.revision)]=record;kinds[record.kind]=kinds.get(record.kind,0)+1
            if isinstance(record,RunArtifact) and record.locator.startswith('artifact://'):
                body=j.get(record.locator)
                if body is None or artifact_ref(body)!=record.locator or hashlib.sha256(body.encode()).hexdigest()!=record.sha256:raise ValueError('artifact hash mismatch')
        except Exception:issues.append({'code':'record_or_artifact_integrity','id':row['id'],'revision':row['revision']})
    latest={}
    for (identity,revision),record in records.items():
        if identity not in latest or revision>latest[identity].revision:latest[identity]=record
    present=set()
    for row in edges:
        try:
            body=j.get(row['ref'])
            if body is None or artifact_ref(body)!=row['ref']:raise ValueError('edge artifact hash mismatch')
            edge=Edge.model_validate_json(body)
            key=(edge.source,edge.source_revision,edge.target,edge.target_revision,edge.relation)
            if key!=tuple(row[k] for k in ('source','source_revision','target','target_revision','relation')):raise ValueError('edge index mismatch')
            if (edge.source,edge.source_revision) not in records or (edge.target,edge.target_revision) not in records:raise ValueError('edge endpoint absent')
            present.add(key)
        except Exception:issues.append({'code':'edge_integrity_or_dangling','id':row['source'],'revision':row['source_revision']})
    # Audit historical revisions too. A target revision captured by an existing link
    # is retained; a later target revision must not silently rebind old provenance.
    for (identity,revision),record in records.items():
        for target_id,kind,relation in declared(record):
            existing=[key for key in present if key[0]==identity and key[1]==revision and key[2]==target_id and key[4]==relation]
            target=records.get((target_id,existing[0][3])) if existing else latest.get(target_id)
            if target is None:
                issue={'code':'unresolved_reference','id':identity,'revision':revision,'target':target_id}
                if isinstance(record,LearningEpisode) and record.stage in ('gap','reviewed','review_failed'):
                    notices.append({**issue,'code':'retained_tool_gap'})
                else:issues.append(issue)
            elif target.kind!=kind or target.id==identity:
                issues.append({'code':'reference_kind_or_self','id':identity,'revision':revision,'target':target_id})
            elif not existing:
                pending.append(Edge(source=identity,source_revision=revision,target=target.id,target_revision=target.revision,
                                    relation=relation,source_ref=next(r['ref'] for r in rows if r['id']==identity and r['revision']==revision)))
    result={'passed':not issues,'issues':issues,'notices':notices,'record_count':len(rows),'edge_count':len(edges),
            'pending_links':len(pending),'kind_counts':dict(sorted(kinds.items())),'complete':True}
    import rustworkx as rx
    graph=rx.PyDiGraph();nodes={key:graph.add_node(key) for key in records}
    dependency_edges=[key for key in present if key[4]=='requires']
    dependency_edges += [(e.source,e.source_revision,e.target,e.target_revision,e.relation) for e in pending if e.relation=='requires']
    for source,source_revision,target,target_revision,_ in dependency_edges:
        if (source,source_revision) in nodes and (target,target_revision) in nodes:
            graph.add_edge(nodes[(source,source_revision)],nodes[(target,target_revision)],None)
    if not rx.is_directed_acyclic_graph(graph):
        issues.append({'code':'memory_dependency_cycle','id':'scientific-memory'});result['passed']=False
    return result,pending


def wire(memory):
    report,pending=scan(memory)
    if not report['passed']:raise ValueError('memory reference audit failed; no links were inferred')
    # Each append is idempotent and Journal-backed. A crash leaves a safe prefix;
    # retry inspects fresh references, never replays an external effect.
    for edge in pending:memory.link(edge)
    result,_=scan(memory)
    return result


def resolve(memory,query,kind):
    from ..names import rank
    if type(query) is not str or not 1<=len(query.strip())<=120:raise ValueError('bounded name query required')
    if kind not in RECORD.json_schema()['discriminator']['mapping']:raise ValueError('unknown scientific record kind')
    exact=memory.get(query)
    if exact is not None and exact.kind==kind:return [exact]
    rows=memory.journal.rows('SELECT r.ref FROM discovery_records r WHERE r.kind=? AND r.revision='
        '(SELECT MAX(n.revision) FROM discovery_records n WHERE n.id=r.id) ORDER BY r.id LIMIT ?',(kind,MAX_RECORDS+1))
    if len(rows)>MAX_RECORDS:raise ValueError('name resolution exceeds bounded scope')
    candidates=[RECORD.validate_json(memory.journal.get(r['ref'])) for r in rows]
    labels={}
    for record in candidates:
        for label in (record.id,getattr(record,'name','')):
            if label:labels.setdefault(label,[]).append(record)
    hits=rank(query,labels)
    found={r.id:r for label in hits for r in labels[label]}
    return [found[k] for k in sorted(found)]


def qualification(memory,registry,capability):
    """Independent read-only check of existing learning proof, not a promotion API."""
    if not isinstance(capability,Capability) or capability.verification!='VERIFIED':return []
    try:
        from .learning import QUALIFIERS
        from .golden import load
        candidate=registry.get(capability.neuron_id)
        if candidate is None or candidate.status!='active' or candidate.provider!='jarvis.neural.learning':raise ValueError('not an active learned wrapper')
        base=candidate.source.removeprefix('discovery-qualified:')
        if base not in QUALIFIERS:raise ValueError('unreviewed qualifier')
        adapter=registry.get(base)
        if adapter is None or adapter.side_effect_class!='read_only':raise ValueError('reviewed base missing')
        for field in ('inputs','outputs','side_effect_class','privilege','runtime','privacy','timeout_ms'):
            if getattr(candidate,field)!=getattr(adapter,field):raise ValueError('qualified wrapper contract changed')
        if not set((*adapter.requirements,'flag:lab.learning'))<=set(candidate.requirements):raise ValueError('qualification requirements weakened')
        case,verifier=QUALIFIERS[base];load(memory.journal,capability.golden_ref,case)
        episodes=[e for e in memory.list('LearningEpisode',limit=200) if e.golden_ref==capability.golden_ref and e.stage=='promoted']
        if not episodes:raise ValueError('no promoted episode')
        valid=False
        for episode in episodes:
            goals=set(episode.successful_goal_ids)
            if len(goals)<3:continue
            good=True
            for identity in goals:
                goal=memory.journal.goal(identity);plan=json.loads(goal['plan']) if goal and goal.get('plan') else {}
                steps=plan.get('steps',[])
                if (not goal or goal['state']!='verified' or not any(s['neuron'] in (base,candidate.node_id) for s in steps)
                    or not any(s['step_id']==plan.get('goal_verifier') and s['neuron']==verifier for s in steps)
                    or not any(s['type']=='verification.passed' and s.get('target_node')==verifier for s in memory.journal.signals(identity))):
                    good=False;break
            if good:valid=True;break
        if not valid:raise ValueError('independent uses missing')
    except Exception:return [{'code':'unsupported_verified_state','id':capability.id}]
    return []
