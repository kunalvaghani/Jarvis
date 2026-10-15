"""Phase 2 live A/B: Ollama server KV-cache/flash-attention settings for qwen3.5:9b on the RTX 3050 4 GB.

Starts an OWNED `ollama serve` on 127.0.0.1:11435 per variant and stops only that process.
Usage: python ollama_env_bench.py <out.json>
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
HOST = '127.0.0.1:11435'
URL = 'http://' + HOST
VARIANTS = {
    'baseline': {},
    'fa_q8': {'OLLAMA_FLASH_ATTENTION': '1', 'OLLAMA_KV_CACHE_TYPE': 'q8_0'},
}
LAYERS = [0, 6, 9, 12, 16]
CONTEXT = 16384  # Jarvis's fixed native-planning context for qwen3.5:9b.
PROMPT = ('You are planning a desktop task. ' + ' '.join(
    f'Observation {i}: the window titled Report {i} lists files a{i}.txt, b{i}.txt and c{i}.csv.' for i in range(120))
    + '\nList, in order, the three steps to open c7.csv and read its first line. Be brief.')


def vram():
    out = subprocess.run(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
                         capture_output=True, text=True, timeout=5).stdout.strip()
    return int(out) if out.isdigit() else -1


def sampler(stop, peaks):
    while not stop.is_set():
        peaks.append(vram())
        time.sleep(.2)


def main(out_path):
    results = {'date': time.strftime('%Y-%m-%d %H:%M:%S'), 'context': CONTEXT, 'idle_vram_mb': vram(), 'runs': []}
    for name, extra in VARIANTS.items():
        env = {**os.environ, 'OLLAMA_HOST': HOST, **extra}
        log = open(Path(out_path).with_name(f'ollama-{name}.log'), 'w', encoding='utf-8')
        server = subprocess.Popen([OLLAMA, 'serve'], env=env, stdout=log, stderr=subprocess.STDOUT,
                                  creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            for _ in range(100):
                try:
                    requests.get(URL + '/api/version', timeout=1).raise_for_status(); break
                except requests.RequestException:
                    time.sleep(.3)
            for layers in LAYERS:
                stop, peaks = threading.Event(), []
                thread = threading.Thread(target=sampler, args=(stop, peaks), daemon=True); thread.start()
                row = {'variant': name, 'num_gpu': layers}
                try:
                    started = time.perf_counter()
                    body = requests.post(URL + '/api/generate', json={
                        'model': 'qwen3.5:9b', 'prompt': PROMPT, 'stream': False, 'think': False, 'keep_alive': '30s',
                        'options': {'num_ctx': CONTEXT, 'num_gpu': layers, 'num_predict': 48, 'temperature': 0,
                                    'seed': 7, 'num_thread': 12}}, timeout=600).json()
                    row['wall_s'] = round(time.perf_counter() - started, 2)
                    ps = requests.get(URL + '/api/ps', timeout=5).json().get('models', [])
                    row['size_vram_mb'] = round(ps[0]['size_vram'] / 2**20) if ps else None
                    row['size_total_mb'] = round(ps[0]['size'] / 2**20) if ps else None
                    if 'error' in body:
                        row['error'] = str(body['error'])[:300]
                    else:
                        row.update(load_s=round(body['load_duration'] / 1e9, 2), prompt_tokens=body['prompt_eval_count'],
                                   prompt_tps=round(body['prompt_eval_count'] / (body['prompt_eval_duration'] / 1e9), 1),
                                   gen_tps=round(body['eval_count'] / (body['eval_duration'] / 1e9), 2),
                                   output=body['response'])
                except requests.RequestException as exc:
                    row['error'] = type(exc).__name__ + ': ' + str(exc)[:200]
                finally:
                    stop.set(); thread.join()
                    row['peak_vram_mb'] = max(peaks) if peaks else None
                    try:
                        requests.post(URL + '/api/generate', json={'model': 'qwen3.5:9b', 'keep_alive': 0}, timeout=30)
                    except requests.RequestException:
                        pass
                    time.sleep(2)
                results['runs'].append(row)
                print(json.dumps({k: v for k, v in row.items() if k != 'output'}), flush=True)
        finally:
            server.terminate()
            try:
                server.wait(20)
            except subprocess.TimeoutExpired:
                server.kill()
            log.close()
            time.sleep(3)
    results['final_idle_vram_mb'] = vram()
    Path(out_path).write_text(json.dumps(results, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main(sys.argv[1])
