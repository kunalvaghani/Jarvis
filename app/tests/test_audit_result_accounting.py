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
