"""Audit results must not let a passing variant erase a failed assertion."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch
from scripts.verification import audit_catalog

def test_failed_catalog_variant_cannot_be_masked_by_later_pass(tmp_path):
    rows=[{'id':'JRV-01-003','module':'architecture-inventory','tier':'P0','case_type':'scenario'}]
    (tmp_path/'catalog-input.jsonl').write_text(json.dumps(rows[0])+'\n')
    (tmp_path/'module-map.json').write_text(json.dumps([{'sources':[],'test_candidates':[]}]))
    (tmp_path/'catalog-tests.xml').write_text('<testsuite><testcase classname="fixture" name="JRV-01-003-first"><failure/></testcase><testcase classname="fixture" name="JRV-01-003-second"/></testsuite>')
    with patch.object(audit_catalog,'OUT',tmp_path):audit_catalog.reconcile()
    result=json.loads((tmp_path/'test-results.jsonl').read_text())
    assert result['status']=='FAIL'
    assert len(result['executed_assertions'])==2
    assert (tmp_path/'remaining-case-ids.txt').read_text().strip()=='JRV-01-003'


@pytest.mark.parametrize('classname,message,expected', [
    ('tests.test_audit_completion_cases', 'BLOCKED: labeled acoustic corpus missing', 'BLOCKED'),
    ('tests.test_voice_tts_audit', 'BLOCKED: labeled listening evaluation missing', 'BLOCKED'),
    ('tests.test_questions_context_audit', 'BLOCKED: local model not installed', 'BLOCKED'),
    ('tests.test_model_routing_audit', 'BLOCKED: live entitlement not independently verified', 'BLOCKED'),
    ('tests.test_gpu_scheduler_audit', 'BLOCKED: speech lease protocol missing', 'BLOCKED'),
    ('tests.test_repo_learning_audit', 'BLOCKED: arbitrary repository behavior not sandbox validated', 'BLOCKED'),
    ('tests.test_ability_forge_audit', 'BLOCKED: live generated-code acceptance requires separate authorization', 'BLOCKED'),
    ('tests.test_self_evolution_audit', 'BLOCKED: independent privacy oracle and canary contract missing', 'BLOCKED'),
    ('tests.test_native_coding_audit', 'BLOCKED: same-function conflict resolution contract missing', 'BLOCKED'),
    ('tests.test_web_development_audit', 'BLOCKED: HMR lifecycle missing', 'BLOCKED'),
    ('tests.test_gmail_audit', 'BLOCKED: multi-account identity binding missing', 'BLOCKED'),
    ('tests.test_whatsapp_audit', 'BLOCKED: durable attachment replay protocol missing', 'BLOCKED'),
    ('tests.test_media_audit', 'BLOCKED: durable playback identity missing', 'BLOCKED'),
    ('tests.test_realtime_audit', 'BLOCKED: complete feed freshness contracts missing', 'BLOCKED'),
    ('tests.test_gods_eye_audit', 'BLOCKED: complete map/provider contracts missing', 'BLOCKED'),
    ('tests.test_harness_planners_audit', 'BLOCKED: matched optional-planner acceptance missing', 'BLOCKED'),
    ('tests.test_reverse_engineering_audit', 'BLOCKED: complete REA acceptance missing', 'BLOCKED'),
    ('tests.test_sandbox_deerflow_audit', 'BLOCKED: complete sandbox/research contracts missing', 'BLOCKED'),
    ('tests.test_rag_documents_audit', 'BLOCKED: citation faithfulness oracle missing', 'BLOCKED'),
    ('tests.test_memory_audit', 'BLOCKED: cross-store erase protocol missing', 'BLOCKED'),
    ('tests.test_app_research_audit', 'BLOCKED: plugin scope namespace missing', 'BLOCKED'),
    ('tests.test_browser_playwright_audit', 'BLOCKED: production download/tab-selection adapter missing', 'BLOCKED'),
    ('tests.test_desktop_control_audit', 'BLOCKED: no authorized live DPI/UAC fixture', 'BLOCKED'),
    ('tests.test_skill_selection_audit', 'BLOCKED: no validated PDF-edit adapter offered', 'BLOCKED'),
    ('tests.test_deliberation_audit', 'BLOCKED: deterministic research-before-action policy absent', 'BLOCKED'),
    ('tests.test_audit_completion_cases', 'optional fixture unavailable', 'SKIPPED'),
    ('unreviewed_test', 'BLOCKED: arbitrary label', 'NOT RUN'),
])
def test_only_reviewed_explicit_blockers_change_catalog_status(tmp_path, classname, message, expected):
    module=tmp_path/'modules/04-voice-stt'
    module.mkdir(parents=True)
    rows=[{'id':'JRV-04-001','tier':'P0','case_type':'scenario'}]
    (tmp_path/'catalog-input.jsonl').write_text(json.dumps(rows[0])+'\n')
    (tmp_path/'module-map.json').write_text(json.dumps([{'sources':[],'test_candidates':[]}]*4))
    (module/'cases-and-contracts.xml').write_text(
        f'<testsuite><testcase classname="{classname}" name="case[JRV-04-001]">'
        f'<skipped message="{message}"/></testcase></testsuite>')
    with patch.object(audit_catalog,'OUT',tmp_path):
        audit_catalog.reconcile()
    result=json.loads((tmp_path/'test-results.jsonl').read_text())
    assert result['status']==expected
    assert ('JRV-04-001' in (tmp_path/'remaining-case-ids.txt').read_text()) == (expected != 'SKIPPED')
