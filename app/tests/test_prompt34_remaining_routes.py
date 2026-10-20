"""Safe remaining Prompt 34 seams: no real documents, network or training."""
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock,patch
import urllib.error
import zipfile

import pytest


def test_JRV_34_014_missing_local_embedding_falls_back_and_reports_lexical(tmp_path):
    from jarvis import local_embeddings
    from jarvis.reasoning_bank import ReasoningBank
    row={'kind':'strategy','title':'Spreadsheet export format',
         'description':'Choose the spreadsheet format before export',
         'content':'Choose the spreadsheet export format before exporting.',
         'conditions':{},'failure_conditions':[]}
    with patch('urllib.request.urlopen',side_effect=urllib.error.URLError('offline fixture')),patch.dict(local_embeddings._STATE,{'available':None}):
        bank=ReasoningBank(tmp_path,embedder=local_embeddings.embed)
        bank._add(row,{'source':'synthetic'},'fixture')
        hits=bank.retrieve('spreadsheet export format')
        assert local_embeddings.status()['available'] is False
    assert hits['lessons'] and hits['lessons'][0]['method']=='lexical'


@pytest.mark.parametrize('member,label',[('xl/vbaProject.bin','macros'),('_xmlsignatures/sig1.xml','signatures')])
def test_JRV_34_018_unsupported_xlsx_features_are_not_rewritten(tmp_path,member,label):
    from jarvis import app_adapters
    from jarvis.tool_errors import ToolUnavailable
    workbook=tmp_path/'protected.xlsx'
    with zipfile.ZipFile(workbook,'w') as package:
        package.writestr('xl/workbook.xml','<workbook/>')
        package.writestr(member,'SYNTHETIC_PROTECTED_CONTENT')
    original=hashlib.sha256(workbook.read_bytes()).hexdigest()
    actions=SimpleNamespace(base=tmp_path,_task_folder=lambda *a:str(tmp_path),task_state=None,_approve=Mock())
    step={'action':'office_xlsx','value':workbook.name,'folder':str(tmp_path),
          'content':json.dumps({'operation':'write','sheet':'Data','cells':{'A1':'change'}})}
    with patch.object(app_adapters,'worker') as worker,pytest.raises(ToolUnavailable,match=label):
        app_adapters.office_xlsx(actions,step,lambda:False)
    worker.assert_not_called()
    actions._approve.assert_not_called()
    assert hashlib.sha256(workbook.read_bytes()).hexdigest()==original
