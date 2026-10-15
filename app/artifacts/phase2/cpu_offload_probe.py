"""Does num_gpu=0 keep a model off the RTX 3050? Owned `ollama serve` on 127.0.0.1:11435, stopped afterwards.

Usage: python cpu_offload_probe.py <out.json>
"""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import requests

OLLAMA = r'C:\Users\kunal\AppData\Local\Programs\Ollama\ollama.exe'
URL = 'http://127.0.0.1:11435'
CASES = [('qwen3.5:9b', 16384, 2), ('qwen2.5:0.5b', 2048, 2), ('qwen3.5:0.8b', 4096, 2)]
PROMPT = 'Rewrite this voice command cleanly: ' + 'open the the notepad please and and type hello ' * 60


def vram():
    out = subprocess.run(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
                         capture_output=True, text=True, timeout=5).stdout.strip()
    return int(out) if out.isdigit() else -1


def main(out_path):
    env = {**os.environ, 'OLLAMA_HOST': '127.0.0.1:11435'}
    log = open(Path(out_path).with_name('ollama-cpu-probe.log'), 'w', encoding='utf-8')
    server = subprocess.Popen([OLLAMA, 'serve'], env=env, stdout=log, stderr=subprocess.STDOUT,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    rows = []
    try:
        for _ in range(100):
            try:
                requests.get(URL + '/api/version', timeout=1).raise_for_status(); break
            except requests.RequestException:
                time.sleep(.3)
        for model, context, repeats in CASES:
            for attempt in range(repeats):
                peaks, stop = [], threading.Event()
                sampler = threading.Thread(target=lambda: [peaks.append(vram()) or time.sleep(.1) for _ in iter(stop.is_set, True)], daemon=True)
                sampler.start()
                body = requests.post(URL + '/api/generate', json={'model': model, 'prompt': PROMPT, 'stream': False, 'think': False,
                    'keep_alive': '20s', 'options': {'num_ctx': context, 'num_gpu': 0, 'num_predict': 24, 'temperature': 0}},
                    timeout=600).json()
                stop.set(); sampler.join()
                ps = requests.get(URL + '/api/ps', timeout=5).json().get('models', [])
                rows.append({'model': model, 'attempt': attempt, 'num_gpu': 0, 'context': context,
                             'peak_vram_mb': max(peaks), 'size_vram_mb': round(ps[0]['size_vram'] / 2**20) if ps else None,
                             'load_s': round(body.get('load_duration', 0) / 1e9, 2), 'error': body.get('error')})
                print(json.dumps(rows[-1]), flush=True)
            requests.post(URL + '/api/generate', json={'model': model, 'keep_alive': 0}, timeout=30)
            time.sleep(2)
    finally:
        server.terminate()
        try:
            server.wait(20)
        except subprocess.TimeoutExpired:
            server.kill()
        log.close()
    Path(out_path).write_text(json.dumps({'date': time.strftime('%Y-%m-%d %H:%M:%S'), 'rows': rows}, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main(sys.argv[1])
