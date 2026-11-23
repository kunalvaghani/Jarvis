"""User-word source preflight is a normal independently verified brain child."""
import json
from types import SimpleNamespace
from unittest.mock import patch,Mock
from jarvis.discovery.asset_preflight import query_from_goal,run
from jarvis.neural.service import BrainService
from jarvis.task_state import TaskState
from tests.test_discovery_asset_search import RAW

ON={'lab':{'enabled':True,'sim':True,'research':True},'neural':{'mode':'act','learning':'shadow'}}


def test_source_query_uses_user_words_without_invented_chassis_or_parameters():
    assert query_from_goal(ON,'Find a legal free downloadable 2025 McLaren F1 model. Run real vehicle dynamics.')=='2025 McLaren F1'
    assert query_from_goal(ON,'Find a legal free model for a 2026-regulation F1 car and verify its license. Simulate active aero.')=='2026 F1 car'
    assert query_from_goal(ON,'Simulate a pendulum.') is None
    assert query_from_goal({'lab':{'enabled':False}},'Find a 2025 McLaren F1 model. Simulate it.') is None


def test_preflight_executes_real_source_compile_dispatch_and_verifier(tmp_path):
    service=BrainService(ON,tmp_path/'brain.sqlite3')
    state=TaskState(tmp_path/'owner');goal='Find a free downloadable 2025 McLaren F1 model. Simulate vehicle dynamics.'
    state.start(goal,'task')
    actions=SimpleNamespace(config=ON,base=tmp_path,task_state=state,_neural_service=service,
        report=Mock(),allowed_tools=None)
    try:
        with patch('jarvis.discovery.adapters.asset_catalog.fetch',return_value=RAW) as fetch:
            result=run(actions,goal,lambda:False)
        assert result['verified']
        projection=json.loads(result['result'])
        assert projection['source_bytes_verified'] and not projection['full_goal_verified']
        assert not projection['items'][0]['identity_verified']
        assert fetch.call_count==1
        rows=service.journal.rows('SELECT * FROM discovery_asset_search_runs')
        assert len(rows)==1 and rows[0]['query']=='2025 McLaren F1'
        assert state.snapshot()['goal']==goal
        assert 'source_ref' in projection and 'maximum_engine_power_w' not in projection
        # The model-facing result starts with a source index, rather than a
        # repr containing descriptions that cut later candidates off-screen.
        from jarvis.discovery.acceptance import artifact
        stored=artifact(service.journal,service.journal.rows('SELECT result_ref FROM discovery_planner_calls')[0]['result_ref'])
        assert 'source_summary' in stored
        assert stored['source_summary']['source_refs']==[projection['source_ref']]
        assert stored['source_summary']['content_is_untrusted']
        assert not stored['source_summary']['metadata_candidates'][0]['identity_verified']
        # A re-entry in the same durable task reuses the completed child; no GET replay.
        with patch('jarvis.discovery.adapters.asset_catalog.fetch',side_effect=AssertionError('must reuse source child')):
            assert run(actions,goal,lambda:False)['verified']
            from jarvis.discovery.planner_access import execute
            rendered=execute(actions,'lab assets search "2025 McLaren F1"','',lambda:False)
            assert next(iter(json.loads(rendered)))=='source_summary'
            assert projection['source_ref'] in rendered[:1500]
    finally:service.journal.close()


def test_preflight_respects_allowed_tools_and_cancellation(tmp_path):
    actions=SimpleNamespace(config=ON,allowed_tools={'web_open'},report=Mock())
    goal='Find a 2025 McLaren F1 model. Simulate dynamics.'
    with patch('jarvis.tools.ToolRegistry.execute',side_effect=AssertionError('not allowed')):
        assert run(actions,goal,lambda:False) is None


def test_source_index_prioritizes_literal_year_without_choosing_or_promoting_assets():
    from jarvis.discovery.asset_preflight import context
    items=[{'uid':str(i),'name':name,'creator':'author','license_declared':{},
            'identity_verified':False,'geometry_acquired':False,'description':'long '*4000}
           for i,name in enumerate(['Road car 1998','Vehicle 2031 candidate','Car 2029','Vehicle 2031 concept','Other'])]
    result={'query':'2031 vehicle','items':items,'source_ref':'actual-source',
            'goal_id':'actual-child','payload_sha256':'actual-hash'}
    summary=context({'verified':True,'result':json.dumps(result)})
    assert [r['name'] for r in summary['metadata_candidates'][:2]]==['Vehicle 2031 candidate','Vehicle 2031 concept']
    assert summary['candidate_total']==5 and summary['candidate_projection_partial']
    assert all(not r['identity_verified'] for r in summary['metadata_candidates'])
    assert 'description' not in json.dumps(summary)
    assert items[0]['name']=='Road car 1998'  # Original source ordering/bytes untouched.


def test_canonical_cached_index_retains_source_ids_before_long_candidate_metadata():
    from jarvis.discovery.planner_access import _render_result
    value={'answer':'verbose '*2000,'verified':True,'source_summary':{
        'source_refs':['actual-byte-verified-source'],'query':'2031 vehicle',
        'content_is_untrusted':True,'metadata_candidates':[{'name':'long '*1000}]*4}}
    canonical=json.loads(json.dumps(value,sort_keys=True))
    rendered=_render_result(canonical)
    assert 'actual-byte-verified-source' in rendered[:200]
    assert json.loads(rendered)==value  # Presentation only; no data/verification changes.
