"""Provider labels must not turn a token for another principal into verified rotation.

All HTTP calls are intercepted. Tokens and identities are synthetic fixtures.
"""
import json
import os
from pathlib import Path
import runpy
from unittest.mock import patch

import pytest

support=runpy.run_path(str(Path(__file__).with_name('test_provider_context.py')))
from jarvis.tools import ToolRegistry


@pytest.mark.parametrize('switch_token',[False,True],ids=['stable-token-control','other-account-token'])
def test_JRV_33_022_configured_label_does_not_verify_a_replacement_token(tmp_path,switch_token):
    host=support['actions'](tmp_path)
    ledger, cards=[],[]
    def approve(kind,detail,cancelled):
        cards.append(json.loads(detail))
        if switch_token:
            # A stale configured label remains A, while the actual bearer credential belongs to B.
            os.environ['JARVIS_GOOGLE_ACCESS_TOKEN']='SYNTHETIC_ACCOUNT_B_TOKEN'
    host._approve=approve
    def api(client,method,url,cancelled,**kwargs):
        authorization=kwargs['headers']['Authorization']
        account='B' if authorization.endswith('B_TOKEN') else 'A'
        ledger.append({'method':method,'actual_mock_account':account,'url':url,'body':kwargs.get('json')})
        return json.dumps({'id':'SYNTHETIC_EVENT_'+account})
    with patch.dict(os.environ,{'JARVIS_GOOGLE_ACCOUNT':'account-a@example.test',
                               'JARVIS_GOOGLE_ACCESS_TOKEN':'SYNTHETIC_ACCOUNT_A_TOKEN'},clear=True), \
         patch('jarvis.toolkits.api',side_effect=api):
        try:
            ToolRegistry(host).execute({'action':'calendar_create','value':'primary','content':json.dumps({
                'summary':'SYNTHETIC_EVENT_FOR_A','start':{'date':'2026-10-20'},'end':{'date':'2026-10-21'}})},lambda:False)
        except ValueError:
            pass  # Refusal after credential drift is safe, even if labels are stale.
    evidence={'configured_label':'account-a@example.test','token_switched':switch_token,
              'approval_cards':cards,'intercepted_writes':ledger,'actual_network_calls':0}
    (Path(__file__).parent/('configured-switch.json' if switch_token else 'configured-stable.json')).write_text(
        json.dumps(evidence,indent=2),encoding='utf-8')
    assert not any(r['actual_mock_account']=='B' for r in ledger), 'replacement token for B was accepted as verified rotation for label A'
    if not switch_token:
        assert len(ledger)==1 and ledger[0]['actual_mock_account']=='A'
