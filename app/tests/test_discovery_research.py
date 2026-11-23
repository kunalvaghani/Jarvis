"""C3 source/claim integrity and real brain paths; HTTP/model fixtures are explicitly synthetic."""
import copy
import json
from types import SimpleNamespace
import pytest

from jarvis.discovery.adapters import literature as lit
from jarvis.discovery.model.literature_review import review,audit_hypotheses,skeptic,verify,Tournament
from jarvis.discovery.model.relativity import ClockCase,calculate
from jarvis.neural.journal import Journal

ON={'neural':{'mode':'act','learning':'shadow'},'lab':{'enabled':True,'research':True,'sim':True}}


def payload(abstract='A moving ideal clock records less elapsed time than a stationary clock under the stated inertial assumptions.'):
    return json.dumps({'message':{'items':[{'DOI':'10.1234/test','title':['Synthetic clock study'],
        'abstract':abstract,'type':'journal-article','published':{'date-parts':[[2020,1,2]]},
        'author':[{'given':'Fixture','family':'Author'}]}]}}).encode()


@pytest.fixture
def journal(tmp_path):
    value=Journal(tmp_path/'brain.sqlite3');yield value;value.close()


def test_metadata_doi_identity_dates_markup_and_no_false_peer_review():
    p=lit.parse('crossref',payload('<jats:p>Only metadata.</jats:p>'))[0]
    assert p.abstract=='Only metadata.' and p.published=='2020-1-2'
    assert p.retraction=='not_checked' and p.license is None
    assert lit.doi('https://doi.org/10.1234/Test')=='10.1234/test'
    xml=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/2401.12345v2</id><title>Preprint</title><summary>Fixture text.</summary></entry></feed>'
    assert lit.parse('arxiv',xml)[0].publication_type=='preprint'
    with pytest.raises(ValueError):lit.parse('arxiv',b'<!DOCTYPE x><feed/>')
    with pytest.raises(ValueError):lit.parse('crossref',b'x'*(lit.LIMIT+1))


@pytest.mark.parametrize('value',['api key sk-secretvalue','https://localhost/a','x@y.org',r'C:\private','x'])
def test_public_queries_never_send_secrets_urls_paths_or_addresses(value):
    with pytest.raises(ValueError):lit.public_query(value)


def test_cache_restart_cancellation_failure_retention_and_paid_refusal(journal,monkeypatch):
    calls=[]
    monkeypatch.setattr(lit,'fetch',lambda url,cancelled:(calls.append(url) or payload()))
    first,cache=lit.read(journal,'crossref','moving clocks')
    assert not cache and len(calls)==1
    second,cache=lit.read(journal,'crossref','moving clocks')
    assert cache and first==second and len(calls)==1
    with pytest.raises(PermissionError):lit.read(journal,'openalex','moving clocks')
    with pytest.raises(ValueError):lit.read(journal,'crossref','moving clocks',cancelled=lambda:True)
    monkeypatch.setattr(lit,'fetch',lambda *a:(_ for _ in ()).throw(ValueError('fixture failure')))
    with pytest.raises(ValueError):lit.read(journal,'crossref','another topic')
    assert journal.rows("SELECT state FROM discovery_literature_reads WHERE state='failed'")
    monkeypatch.setattr(lit,'fetch',lambda *a:pytest.fail('failed request was automatically replayed'))
    with pytest.raises(ValueError,match='cooldown'):lit.read(journal,'crossref','another topic')


def test_http_rejects_ssrf_and_redirect_targets_before_any_socket():
    for url in ('http://api.crossref.org/works','https://localhost/','https://api.crossref.org.evil/a','https://user@api.crossref.org/a','https://api.crossref.org:443/a'):
        with pytest.raises(ValueError):lit.fetch(url,lambda:False)


def responses(journal,monkeypatch):
    monkeypatch.setattr(lit,'fetch',lambda *a:payload())
    return [lit.read(journal,'crossref','moving clocks')[0]]


def test_excerpts_dedup_locators_tournament_and_tamper_refusal(journal,monkeypatch):
    data=responses(journal,monkeypatch); report=review('moving clocks',data+data)
    assert len(report['citations'])==1 and len(report['duplicate_identities'])==1
    assert report['citations'][0]['peer_review']=='not_verified'
    assert len(report['excerpts'][0]['quote'].split())<=24
    tournament=audit_hypotheses(report); ranking=skeptic(report,tournament)
    assert len(ranking)==3 and sum(r['proposal']['is_null'] for r in ranking)==1
    assert verify(report,data+data,tournament,ranking)
    changed=copy.deepcopy(report);changed['excerpts'][0]['quote']='Invented result.'
    with pytest.raises(ValueError):verify(changed,data+data,tournament,ranking)
    changed=copy.deepcopy(tournament.model_dump(mode='json'));changed['hypotheses'][1]['citation_ids']=['nonexistent']
    with pytest.raises(ValueError):skeptic(report,Tournament.model_validate_json(json.dumps(changed)))
    changed['hypotheses'][1]['statement']='This effect is guaranteed to improve time by 20 percent.'
    with pytest.raises(ValueError):skeptic(report,Tournament.model_validate_json(json.dumps(changed)))


def test_retracted_sources_are_not_usable_hypothesis_evidence(journal,monkeypatch):
    row=json.loads(payload());row['message']['items'][0]['update-to']=[{'type':'retraction'}]
    monkeypatch.setattr(lit,'fetch',lambda *a:json.dumps(row).encode())
    data=[lit.read(journal,'crossref','moving clocks')[0]];report=review('moving clocks',data)
    assert not report['excerpts']
    with pytest.raises(ValueError):skeptic(report,audit_hypotheses(report))


def test_new_metadata_revision_keeps_distinct_immutable_source_identity():
    a={'papers':[p.model_dump(mode='json') for p in lit.parse('crossref',payload('First abstract.'))]}
    b={'papers':[p.model_dump(mode='json') for p in lit.parse('crossref',payload('Revised abstract.'))]}
    assert review('clocks',[a])['citations'][0]['id']!=review('clocks',[b])['citations'][0]['id']


def test_conditional_theory_analytic_limits_and_impossible_speed_refusal():
    result=calculate(ClockCase(coordinate_time_s=10.0,beta=.6))
    assert result['proper_time_s']==8.0 and result['independent_decimal_s']==8.0
    assert not result['physical_validation'] and result['hypotheses'][-1]['result']=='INSUFFICIENT_EVIDENCE'
    assert calculate(ClockCase(coordinate_time_s=10.0,beta=0.0))['proper_time_s']==10.0
    for beta in (1.0,-.1,float('nan')):
        with pytest.raises(ValueError):ClockCase(coordinate_time_s=10.0,beta=beta)
    with pytest.raises(ValueError):calculate(ClockCase(coordinate_time_s=10.0,beta=.6),lambda:True)


def actions(tmp_path):
    from jarvis.actions import Actions
    from jarvis.neural.service import BrainService
    service=BrainService(ON,tmp_path/'brain.sqlite3');a=Actions.__new__(Actions)
    a.config,a.base,a._neural_service,a.allowed_tools=ON,tmp_path,service,None
    return a,service


def test_actual_ingress_research_cache_skeptic_and_theory(tmp_path,monkeypatch):
    from jarvis.engine import Engine
    from jarvis.discovery.memory import LabMemory
    monkeypatch.setattr(lit,'fetch',lambda url,c:payload() if 'crossref' in url else b'<feed xmlns="http://www.w3.org/2005/Atom"/>')
    a,s=actions(tmp_path)
    try:
        for goal in ('lab research "moving clocks"','lab research "moving clocks"'):
            commands=[];e=Engine(commands.append,lambda *a:None);e.activate();e.feed(goal,final=True,raw=goal)
            answer=a.execute(commands[0])
            assert 'INSUFFICIENT_EVIDENCE' in answer and 'doi.org/10.1234/test' in answer
            assert s.journal.rows('SELECT state FROM goals ORDER BY rowid DESC LIMIT 1')[0]['state']=='verified'
        m=LabMemory(s.journal)
        assert len(m.list('Hypothesis'))==3 and len(m.list('Claim'))==1
        assert len(s.journal.rows('SELECT id FROM discovery_literature_reads'))==2
        (tmp_path/'clock.json').write_text('{"coordinate_time_s":10.0,"beta":0.6}')
        from jarvis.commands import Command
        assert '8.0' in a.execute(Command('task','lab theory dilation "clock.json"'))
        assert s.journal.rows('SELECT state FROM goals ORDER BY rowid DESC LIMIT 1')[0]['state']=='verified'
        assert any(record.source_ids and record.evidence_status=='MODEL_CONSISTENT' for record in m.list('RunArtifact'))
    finally:s.journal.close()


def test_fabricated_pass_verdict_cannot_persist_sources(tmp_path):
    from jarvis.discovery import c3
    a,s=actions(tmp_path)
    try:
        handler=c3.adapters(s.graph,s.journal)[c3.NODES['save']]
        item={'review':{'citations':[]}}
        with pytest.raises(ValueError,match='actual current-code'):
            handler(None,{'review':item,'ranking':[],'verdict':{'passed':True}},SimpleNamespace(cancelled=lambda:False))
    finally:s.journal.close()


def test_theory_reuses_immutable_historical_source_context_after_upgrade(tmp_path):
    import hashlib
    from jarvis.discovery import c3
    from jarvis.discovery.contracts import Source
    from jarvis.discovery.memory import LabMemory
    from jarvis.commands import Command
    a,s=actions(tmp_path)
    try:
        raw=b'{"coordinate_time_s":10.0,"beta":0.6}'
        (tmp_path/'clock.json').write_bytes(raw)
        digest=hashlib.sha256(raw).hexdigest()
        identity='c3-theory-input-'+c3.digest(['clock.json',digest])[:32]
        historical=Source(id=identity,locator='clock.json',sha256=digest,
            justification='Explicit user-declared inertial clock inputs, not a physical measurement.')
        memory=LabMemory(s.journal);memory.put(historical)
        assert '8.0' in a.execute(Command('task','lab theory dilation "clock.json"'))
        assert memory.get(identity)==historical
        assert len(s.journal.rows('SELECT * FROM discovery_records WHERE id=?',(identity,)))==1
    finally:s.journal.close()


def test_flags_contracts_invalid_syntax_and_no_paid_model_fallback(journal):
    from jarvis.discovery import c3
    from jarvis.commands import Command
    assert not c3.neurons({}) and not c3.neurons({'lab':{'enabled':True}})
    assert all(n.contract=='explicit' and n.resource_cost['money']==0 for n in c3.neurons(ON))
    with pytest.raises(ValueError):c3.route_command(Command('task','lab research unquoted'))
    with pytest.raises(ValueError,match='local BrainClient'):
        c3.generate({'question':'clock','excerpts':[]},SimpleNamespace(),lambda:False,journal)


def test_doi_lookup_cannot_substitute_another_work(journal,monkeypatch):
    monkeypatch.setattr(lit,'fetch',lambda *a:payload())
    with pytest.raises(ValueError,match='different or ambiguous'):lit.read(journal,'crossref','10.1234/other',lookup=True)
    assert journal.rows("SELECT state FROM discovery_literature_reads")[0]['state']=='failed'


def test_fifty_attempt_cap_and_real_cache_reopen(journal,monkeypatch):
    import time
    monkeypatch.setattr(lit,'fetch',lambda *a:payload())
    expected,_=lit.read(journal,'crossref','moving clocks')
    another=Journal(journal.path)
    try:
        monkeypatch.setattr(lit,'fetch',lambda *a:pytest.fail('cache reopen made a network call'))
        assert lit.read(another,'crossref','moving clocks')==(expected,True)
        with another.tx() as db:
            for i in range(49):db.execute('INSERT INTO discovery_literature_reads VALUES (?,?,?,?,?)',(str(i),'other',time.time(),None,'failed'))
        with pytest.raises(PermissionError,match='50 public'):lit.read(another,'crossref','another query')
    finally:another.close()


def test_possible_contradiction_is_not_asserted_as_scientific_refutation():
    row=json.loads(payload('The moving clock shows a stable difference under identical inertial conditions.'))
    other=copy.deepcopy(row['message']['items'][0]);other['DOI']='10.1234/opposite'
    other['abstract']='The moving clock does not show a stable difference under identical inertial conditions.'
    row['message']['items'].append(other)
    r=review('moving clocks',[{'papers':[p.model_dump(mode='json') for p in lit.parse('crossref',json.dumps(row).encode())]}])
    assert r['possible_contradictions'][0]['state']=='POSSIBLE_CONTRADICTION_REQUIRES_CONTEXT_REVIEW'
    assert all(h['evidence_status']=='UNVERIFIED_SPECULATION' for h in skeptic(r,audit_hypotheses(r)))


def test_explicit_local_route_hint_is_private_and_bad_model_numbers_are_retained(journal):
    from jarvis.discovery import c3
    from jarvis.brain import BrainClient
    client=BrainClient.__new__(BrainClient);client.options={'planner':'existing-local-default'}
    observed=[]
    def request(*args,**kwargs):
        observed.append(kwargs);return {'text':'{"hypotheses":[]}', 'model_used':'fixture-only'}
    client.request=request
    a=SimpleNamespace(brain=SimpleNamespace(client=client))
    with pytest.raises(ValueError):c3.generate({'question':'clock','excerpts':[],'citations':[]},a,lambda:False,journal,True)
    assert client.options=={'planner':'existing-local-default'}
    assert observed[0]['options']['planner']=='qwen3.5:0.8b'
    assert observed[0]['options']['allow_model_fallback'] is False


def test_provided_hypotheses_use_real_cached_sources_and_scoped_file(tmp_path,monkeypatch):
    from jarvis.commands import Command
    from jarvis.discovery.memory import LabMemory
    monkeypatch.setattr(lit,'fetch',lambda url,c:payload() if 'crossref' in url else b'<feed xmlns="http://www.w3.org/2005/Atom"/>')
    a,s=actions(tmp_path)
    try:
        a.execute(Command('task','lab research "moving clocks"'))
        row=s.journal.rows('SELECT id,ref FROM discovery_reviews ORDER BY rowid DESC LIMIT 1')[0]
        report=json.loads(s.journal.get(row['ref']))['review']
        dossier={'review_id':row['id'],'tournament':audit_hypotheses(report).model_dump(mode='json')}
        file=tmp_path/'provided.json';file.write_text(json.dumps(dossier))
        original=file.read_bytes()
        answer=a.execute(Command('task','lab review hypotheses "provided.json"'))
        assert 'provided_qualitative_hypotheses_not_autonomous_generation' in answer and file.read_bytes()==original
        assert len(LabMemory(s.journal).list('Hypothesis'))==6
        assert len(s.journal.rows('SELECT id FROM discovery_literature_reads'))==2
    finally:s.journal.close()
