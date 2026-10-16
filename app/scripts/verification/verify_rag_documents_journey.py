"""Synthetic drop -> command -> canonical readback -> restart; HTTP and sends forbidden."""
import json
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import Mock,patch

BASE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(BASE))
from jarvis import documents as d,file_drop as fd
from tests.test_documents import make_pdf,BRIEF


def main():
    started=time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='jarvis-doc-journey-') as tmp:
        base=Path(tmp);reports=[]
        actions=SimpleNamespace(base=base,report=lambda *a:reports.append(a),memory=None,closing=False)
        def model(system,payload,schema):
            if system.startswith('You answer'):
                assert any(e['page']==2 and '14 November' in e['text'] for e in payload['excerpts'])
                return 'The deadline is 14 November (p. 2).'
            return 'A synthetic client brief.'
        lib=d.Library(actions,{},model_chat=model);actions.documents=lib
        path=make_pdf(base/'fixture.pdf',BRIEF)
        forbidden=Mock(side_effect=AssertionError('external effect forbidden'))
        with patch('requests.sessions.Session.request',forbidden),patch('jarvis.whatsapp.send_files',forbidden),patch('jarvis.gmail_api.draft_with_attachments',forbidden),patch('jarvis.whatsapp.ask',return_value=0):
            result=fd.handle(actions,[str(path)])
            assert 'Ask me anything' in result and lib.focused().name==path.name
            doc=lib.focused()
            answer=d.execute(actions,d.parse_command('ask the pdf when is the deadline'),lambda:False)
            assert answer=='The deadline is 14 November (p. 2).'
            spill=json.loads((lib.root/'session'/f'{doc.id}.json').read_text())
            assert spill['questions'][-1]['a']==answer
            ended=d.execute(actions,d.parse_command('done with the pdf'),lambda:False)
            assert 'saved' in ended and lib.focused() is None
            lib.close()
            other=d.Library(actions,{},model_chat=model);actions.documents=other
            opened=d.execute(actions,d.parse_command('load the document fixture'),lambda:False)
            assert 'fixture.pdf' in opened and other.focused().id==doc.id
            assert other.focused().data['questions'][-1]['a']==answer
            other.close()
        assert forbidden.call_count==0
        assert any(r[0]=='media_card' for r in reports)
    result={'date':'2026-10-16 IST','passed':True,'seconds':time.perf_counter()-started,
        'scope':'Actual drop handler, scripted ask choice, local authored model fake, spoken-command parser/execute, session JSON and durable restart readback. No real account/model/Explorer drag.',
        'external_effect_calls':0,'network_calls':0,'steps':['drop','focus','command answer/page evidence','session readback','end','restart','load/readback']}
    (BASE/'artifacts/jarvis-audit/modules/17-rag-documents/document-journey.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
