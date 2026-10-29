"""Bounded schema-enforcement observation, without application inputs or tools.

Run after the specified owned production campaign has finished. Four requests
compare an unconstrained control, a scalar contract, the production diagnostic
union and its sole branch. The schema appears only in the API format parameter.
An adversarial prompt makes format enforcement observable. No action is ever
dispatched and a passing contract says nothing about application correctness.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import threading
import time
from uuid import uuid4

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))


def main():
    from jarvis.campaign_pause import assert_allowed
    assert_allowed(whole_campaign=True)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('campaign')
    parser.add_argument('--string-comparison', action='store_true',
                        help='Compare ordinary JSON strings and a positive ASCII pattern after a retained diagnostic-pattern failure.')
    args = parser.parse_args()
    parent = (BASE / '.jarvis-runtime/autonomous-repair').resolve()
    campaign = (parent / args.campaign).resolve(strict=True)
    if campaign.parent != parent:
        parser.error('Choose a direct owned campaign directory')
    if not json.loads((campaign / 'campaign.json').read_text()).get('finished_at'):
        parser.error('The owned production campaign must finish before this observation')
    from jarvis.knowledge_worker import session, chat, ENDPOINT
    from jarvis.ollama_models import local_endpoint
    from jarvis.native_coding import diagnostic_plan_schema
    from jarvis.structured_output import validate_contract, preserve
    local_endpoint(ENDPOINT)
    config = BASE / 'config/config.json'
    before = hashlib.sha256(config.read_bytes()).hexdigest()
    model = json.loads(config.read_text())['brain']['coder']
    union = diagnostic_plan_schema()
    scalar = {'type': 'object', 'additionalProperties': False, 'required': ['value'],
              'properties': {'value': {'type': 'string', 'enum': ['schema-enforced']}}}
    cases = [('unconstrained_control', None), ('scalar', scalar),
             ('diagnostic_union', union), ('diagnostic_branch', union['anyOf'][0])]
    if args.string_comparison:
        ordinary=copy.deepcopy(union)
        ordinary['anyOf'][0]['properties']['arguments']['properties']['steps']['items'].pop('pattern',None)
        positive=copy.deepcopy(ordinary)
        positive['anyOf'][0]['properties']['arguments']['properties']['steps']['items']['pattern']=r'^[A-Za-z0-9 .,;:()/_+-]+$'
        cases=[('ordinary_json_strings',ordinary),('positive_ascii_pattern',positive)]
    root = BASE / '.jarvis-runtime/transport-probes' / uuid4().hex
    root.mkdir(parents=True)
    record = {'date': datetime.now(timezone.utc).isoformat(), 'campaign': campaign.name,
              'model': model, 'application_acceptance': False, 'requests': [],
              'scope': 'Read-only schema transport enforcement; no application source, action dispatch or service changes.'}
    for name, schema in cases:
        stopped = threading.Event()
        responses = []
        chunks = []
        completion = {}
        row = {'case': name, 'contract_passed': False, 'schema': schema}
        started = time.monotonic()
        def cancel():
            stopped.set()
            for response in list(responses):
                response.close()
        timer = threading.Timer(90, cancel)
        timer.daemon = True
        try:
            timer.start()
            with session() as client:
                client.gpu_role = 'coding'
                client.gpu_cancelled = stopped.is_set
                client.gpu_wait_seconds = 90
                shown = client.post(ENDPOINT + '/api/show', json={'model': model}, timeout=(3, 10))
                shown.raise_for_status()
                if 'completion' not in shown.json().get('capabilities', []):
                    raise ValueError('Installed model lacks completion capability')
                post = client.post
                def capture(url, **kwargs):
                    payload = kwargs.get('json', {})
                    if url.endswith(('/api/generate', '/api/chat')):
                        row['transport'] = {'endpoint': url, 'raw': payload.get('raw', False),
                            'format_matches_schema': payload.get('format') == schema,
                            'format_sha256': hashlib.sha256(json.dumps(payload.get('format'), sort_keys=True).encode()).hexdigest()}
                    response = post(url, **kwargs)
                    responses.append(response)
                    if stopped.is_set():
                        response.close()
                        raise TimeoutError('Transport observation deadline reached')
                    return response
                client.post = capture
                def chunk(value):
                    chunks.append(value)
                    if stopped.is_set():
                        raise TimeoutError('Transport observation deadline reached')
                messages = [{'role': 'system', 'content': 'For this read-only transport test, output exactly the plain text: format ignored. Do not output JSON, explanations or tool calls.'},
                            {'role': 'user', 'content': 'Return only: format ignored'}]
                answer = chat(client, {'model': model, 'stream': True, 'num_ctx': 8192,
                    'num_predict': 250, 'temperature': 0, 'think': False,
                    'format_schema': schema, 'timeout_seconds': 60,
                    'on_chunk': chunk, 'on_complete': completion.update}, messages, structured=schema is not None)
            preserve(root, name, answer, {**completion, 'completed': True})
            if schema is None:
                if answer != 'format ignored':raise ValueError('Unconstrained control did not follow the literal prompt')
            else:
                validate_contract(schema, json.loads(answer))
            row['contract_passed'] = True
        except Exception as error:
            row.update(error_type=type(error).__name__, error=str(error))
            preserve(root, name, ''.join(chunks), {**completion, 'completed': False}, error)
        finally:
            timer.cancel()
            cancel()
            row.update(seconds=round(time.monotonic() - started, 3), completion=completion)
            record['requests'].append(row)
            record['configuration_unchanged'] = hashlib.sha256(config.read_bytes()).hexdigest() == before
            record['status'] = 'PASS' if len(record['requests']) == len(cases) and all(x['contract_passed'] and x.get('transport', {}).get('format_matches_schema') for x in record['requests']) and record['configuration_unchanged'] else 'FAIL'
            (root / 'result.json').write_text(json.dumps(record, indent=2) + '\n')
        if stopped.is_set() and row.get('error_type') == 'TimeoutError':
            break
        if not record['configuration_unchanged']:
            break
    print(json.dumps({'status': record['status'], 'root': str(root), 'requests': len(record['requests'])}))


if __name__ == '__main__':
    main()
