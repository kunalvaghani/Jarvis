"""Prepare a local Qwen alias for Claude Code without new weights or cloud keys."""
from datetime import datetime, timezone
import json
from pathlib import Path
from jarvis.knowledge_worker import session, ensure_server
from jarvis.claude_code import MODEL, executable

BASE=Path(__file__).resolve().parent


def setup():
    executable({})
    with session() as client:
        names={row['name'] for row in ensure_server(client).get('models',[])}
        if 'qwen3.5:9b' not in names: raise ValueError('Install local qwen3.5:9b first. No automatic cloud model or paid fallback.')
        response=client.post('http://127.0.0.1:11434/api/create',json={'model':MODEL,'from':'qwen3.5:9b',
            'parameters':{'num_ctx':32768,'num_gpu':20,'temperature':0.2,'num_predict':6000},'stream':False},timeout=(3,60))
        response.raise_for_status()
    receipt={'date':datetime.now(timezone.utc).isoformat(),'model':MODEL,'from':'qwen3.5:9b',
        'same_weights':True,'endpoint':'http://127.0.0.1:11434','context':32768,'gpu_layers':20,
        'scope':'Alias parameters sized for this 4GB GPU; official docs recommend 64K+ for larger repositories. No weights downloaded or remote model calls.'}
    (BASE/'artifacts/claude-code-setup.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__': setup()
