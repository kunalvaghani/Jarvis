"""Command -> durable fact -> restart -> local question -> SQLite readback."""
import json
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import Mock,patch

BASE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(BASE))
from jarvis.memory_curator import MemoryCurator,execute,parse_command
from jarvis.conversation_memory import ConversationMemory
from jarvis.knowledge_worker import answer


def main():
    start=time.monotonic()
    with tempfile.TemporaryDirectory() as directory:
        vault=Path(directory)/'synthetic-vault'
        c=MemoryCurator(vault,model_chat=Mock())
        command=parse_command('Remember that I prefer masala chai')
        reply=execute(SimpleNamespace(curator=c),command)
        assert 'remember' in reply and command.kind=='memory_save'
        fresh=MemoryCurator(vault,model_chat=Mock())
        facts=fresh.context('masala chai')['facts']
        assert facts==['Kunal prefers masala chai.']
        captured=[]
        def chat(client,options,messages,structured=False):
            captured.extend(messages)
            return '{"answer":"You prefer masala chai, according to local memory.","needs_web":false}'
        with patch('requests.sessions.Session.request',side_effect=AssertionError('external network forbidden')):
            result=answer({'question':'What tea do I prefer?','options':{'enabled':True},
                'memory_context':[{'source':'Jarvis Memory.md','observation':facts[0]}]},
                client=Mock(),chat_fn=chat,search_fn=lambda _:(_ for _ in ()).throw(AssertionError('private search forbidden')))
        assert 'masala chai' in result['answer'] and 'Kunal prefers masala chai' in json.dumps(captured)
        db=ConversationMemory(Path(directory)/'synthetic.db');s=db.start_session()
        key=db.begin(s,'What tea do I prefer?');db.finish(key,result['answer'])
        restarted=ConversationMemory(db.path)
        assert restarted.turns(s)[0]['answer']==result['answer']
        assert restarted.matches('masala chai','new-session')[0]['id']==key
        canonical=json.loads((vault/'Jarvis Memory.json').read_text(encoding='utf-8'))
        assert canonical['version']==1 and canonical['facts'][0]['text']==facts[0]
    data={'date':'2026-10-16 IST','passed':True,'seconds':time.monotonic()-start,'external_side_effects':0,
        'scope':'Actual memory command parser/executor, temporary JSON/Markdown fact storage, restart, knowledge_worker with authored local chat response and network forbidden, real SQLite/FTS commit/readback/reopen. No real vault or model, speaker, Obsidian GUI or cloud acceptance.',
        'facts':facts,'answer':result['answer'],'sqlite_reopen_verified':True}
    (BASE/'artifacts/jarvis-audit/modules/16-memory/memory-journey.json').write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(data,indent=2))


if __name__=='__main__':main()
