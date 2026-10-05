"""Bounded synthetic output check on the existing local Ollama server."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from jarvis.knowledge_worker import chat, session

BASE = Path(__file__).resolve().parent


def main():
    client = session()
    result = {'date': datetime.now(timezone.utc).isoformat(), 'model': 'qwen3.5:9b',
              'scope': 'Synthetic local text inference only; no user task, voice, desktop input or code execution.',
              'options': {'num_gpu': 0, 'num_ctx': 2048, 'num_predict': 16, 'think': False},
              'passed': False}
    started = time.perf_counter()
    def chunk(text):
        if 'first_content_seconds' not in result:
            result['first_content_seconds'] = round(time.perf_counter() - started, 3)
            print('First response text after ' + str(result['first_content_seconds']) + ' seconds', flush=True)
    try:
        result['server'] = client.get('http://127.0.0.1:11434/api/version', timeout=3).json()
        reply = chat(client, {'model': result['model'], **result['options'],
                             'stream': True, 'timeout_seconds': 120, 'on_chunk': chunk},
                     [{'role': 'user', 'content': 'Reply with exactly OK, no explanation.'}])
        result['reply'] = reply
        result['passed'] = reply.strip().strip('.') == 'OK'
        started_warm = time.perf_counter()
        response = client.post('http://127.0.0.1:11434/api/chat', json={
            'model': result['model'], 'messages': [{'role': 'user', 'content': 'Reply with exactly OK, no explanation.'}],
            'think': False, 'stream': False, 'options': result['options']}, timeout=(5, 120))
        response.raise_for_status()
        body = response.json()
        result['standard_chat'] = {'seconds': round(time.perf_counter() - started_warm, 3),
            'reply': body.get('message', {}).get('content'),
            'load_seconds': round(body.get('load_duration', 0)/1e9, 3),
            'prompt_tokens': body.get('prompt_eval_count'), 'output_tokens': body.get('eval_count')}
        from jarvis.native_tools import plan
        started_native = time.perf_counter()
        proposal = plan(client, result['model'], 'Return one proposal to open the named installed application.',
            {'goal': 'Open notepad', 'apps': ['notepad'],
             'tools': [{'action': 'open', 'description': 'Open one explicitly named installed application.'}]},
            {'timeout_seconds': 300, 'num_gpu': 0})
        result['native_proposal'] = {'seconds': round(time.perf_counter() - started_native, 3),
                                     'proposal': proposal, 'executed': False}
        result['passed'] = (result['passed'] and result['standard_chat']['reply'] == 'OK'
                            and len(proposal.get('steps', [])) == 1
                            and proposal['steps'][0]['action'] == 'open'
                            and proposal['steps'][0]['value'].casefold() == 'notepad')
        result['loaded_models'] = client.get('http://127.0.0.1:11434/api/ps', timeout=3).json()
    except Exception as exc:
        result['passed'] = False
        result['error'] = type(exc).__name__ + ': ' + str(exc)
    finally:
        result['total_seconds'] = round(time.perf_counter() - started, 3)
        client.close()
        destination = BASE / 'artifacts/ollama-output-check.json'
        history = BASE / 'artifacts/ollama-output-check-history.json'
        if destination.is_file():
            rows = json.loads(history.read_text(encoding='utf-8')) if history.is_file() else []
            rows.append(json.loads(destination.read_text(encoding='utf-8')))
            history.write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')
        destination.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
