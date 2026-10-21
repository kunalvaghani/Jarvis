"""Opt-in installed-model observation; public arithmetic, no tool dispatch/download."""
import json
from pathlib import Path
import sys
import time

import requests

BASE = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(BASE))
from jarvis.gpu_scheduler import install

with requests.Session() as client:
    client.trust_env = False
    install(client, 'question')
    started = time.perf_counter()
    with client.post('http://127.0.0.1:11434/api/generate', json={
            'model': 'qwen2.5:0.5b', 'prompt': 'What is 2 + 2? Reply with only the integer.',
            'stream': False, 'options': {'num_ctx': 1024, 'num_predict': 16, 'temperature': 0}},
            timeout=(3, 120)) as response:
        response.raise_for_status()
        data = response.json()
    report = {'date': '2026-10-21', 'scope': 'one live installed local model call through existing GPU admission; public arithmetic only',
              'model': 'qwen2.5:0.5b', 'answer_matches_four': data.get('response', '').strip() == '4',
              'elapsed_seconds': time.perf_counter() - started,
              'done': data.get('done') is True,
              **{key: data.get(key) for key in ('total_duration', 'load_duration', 'prompt_eval_count',
                                               'prompt_eval_duration', 'eval_count', 'eval_duration')}}
    (Path(__file__).parent / 'live-inference.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))
