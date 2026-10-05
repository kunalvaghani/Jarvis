"""Reuse installed Qwen3.5 9B weights for Jarvis's isolated Codex CLI."""
from datetime import datetime, timezone
import json
from pathlib import Path
from jarvis.knowledge_worker import session, ensure_server
from jarvis.codex_code import MODEL, executable
from jarvis.ollama_models import create_alias

BASE=Path(__file__).resolve().parent


def setup():
    program=executable({})
    with session() as client:
        names={row['name'] for row in ensure_server(client).get('models',[])}
        if 'qwen3.5:9b' not in names: raise ValueError('Install local qwen3.5:9b first; no paid/cloud fallback.')
        create_alias(client,MODEL)
    receipt={'date':datetime.now(timezone.utc).isoformat(),'model':MODEL,'from':'qwen3.5:9b',
        'same_weights':True,'executable':program,'endpoint':'http://127.0.0.1:11434','context':32768,'gpu_layers':20,
        'scope':'32K context for this 4GB GPU; Ollama recommends at least 64K for Codex. No weights downloaded, global Codex settings changed, or remote inference.'}
    (BASE/'artifacts/codex-code-setup.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__': setup()
