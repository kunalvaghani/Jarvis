"""Prompt 33 direct optional-adapter cases. Every provider request is intercepted."""
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

APP = next(p for p in Path(__file__).resolve().parents if (p / 'main.py').is_file())
sys.path.insert(0,str(APP))
from jarvis.tools import ToolRegistry
from jarvis.task_state import TaskState


def actions(tmp_path):
    state = TaskState(tmp_path)
    state.start('Synthetic optional provider case', 'task')
    return SimpleNamespace(base=tmp_path, config={}, skills=None, allowed_tools=None,
                           task_state=state, report=Mock(), _approve=Mock())


def test_JRV_33_003_absent_jira_not_advertised(tmp_path):
    with patch.dict(os.environ,{},clear=True):
        names = {r['action'] for r in ToolRegistry(actions(tmp_path)).catalog('list jira projects')}
    assert not any(name.startswith('jira_') for name in names)


def test_JRV_33_001_calendar_read_uses_only_current_mock_account(tmp_path):
    host = actions(tmp_path)
    ledger = []
    def api(client, method, url, cancelled, **kwargs):
        ledger.append((method,url,kwargs['headers']['Authorization']))
        assert method == 'GET'
        return json.dumps({'items':[{'id':'A-1','summary':'SYNTHETIC_ACCOUNT_A_EVENT'}]})
    with patch.dict(os.environ,{'JARVIS_GOOGLE_ACCESS_TOKEN':'SYNTHETIC_ACCOUNT_A_TOKEN'},clear=True), \
         patch('jarvis.toolkits.api',side_effect=api):
        result = ToolRegistry(host).execute({'action':'calendar_list','value':'primary','content':''},lambda:False)
    assert json.loads(result.evidence)['items'][0]['id']=='A-1'
    assert ledger[0][2]=='Bearer SYNTHETIC_ACCOUNT_A_TOKEN' and len(ledger)==1
    host._approve.assert_not_called()


def test_JRV_33_002_calendar_approval_denial_prevents_mock_write(tmp_path):
    host = actions(tmp_path)
    host._approve.side_effect = ValueError('approval denied')
    with patch.dict(os.environ,{'JARVIS_GOOGLE_ACCESS_TOKEN':'SYNTHETIC_ACCOUNT_A_TOKEN'},clear=True), \
         patch('jarvis.toolkits.api') as api:
        with pytest.raises(ValueError,match='approval denied'):
            ToolRegistry(host).execute({'action':'calendar_create','value':'primary','content':json.dumps({
                'summary':'SYNTHETIC','start':{'date':'2026-10-20'},'end':{'date':'2026-10-21'}})},lambda:False)
        api.assert_not_called()


def test_JRV_33_022_account_switch_during_approval_must_not_write_other_workspace(tmp_path):
    host = actions(tmp_path)
    ledger = []
    approvals = []
    def approve(kind, detail, cancelled):
        approvals.append(json.loads(detail))
        # Simulate the configured account switching while this approval was pending.
        os.environ['JARVIS_GOOGLE_ACCESS_TOKEN']='SYNTHETIC_ACCOUNT_B_TOKEN'
    host._approve=approve
    def api(client, method, url, cancelled, **kwargs):
        token=kwargs['headers']['Authorization']
        ledger.append({'method':method,'account':'B' if token.endswith('B_TOKEN') else 'A',
                       'url':url,'body':kwargs.get('json')})
        return json.dumps({'id':'SYNTHETIC_CREATED_EVENT'})
    with patch.dict(os.environ,{'JARVIS_GOOGLE_ACCESS_TOKEN':'SYNTHETIC_ACCOUNT_A_TOKEN'},clear=True), \
         patch('jarvis.toolkits.api',side_effect=api):
        try:
            ToolRegistry(host).execute({'action':'calendar_create','value':'primary','content':json.dumps({
                'summary':'SYNTHETIC_EVENT_FOR_A','start':{'date':'2026-10-20'},'end':{'date':'2026-10-21'}})},lambda:False)
        except ValueError:
            pass  # Refusing after identity drift is a safe outcome; writing as B is not.
    (Path(__file__).parent/'account-switch-observation.json').write_text(json.dumps({
        'initial_account':'A','approval_details':approvals,'intercepted_requests':ledger,
        'network_calls':'ZERO; jarvis.toolkits.api replaced by an in-memory ledger'},indent=2))
    assert not any(row['method']=='POST' and row['account']=='B' for row in ledger), \
        'account A request dispatched as account B after approval'
