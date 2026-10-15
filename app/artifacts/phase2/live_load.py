"""Phase 2 live peak-load trace on the RTX 3050 4 GB (no speaker playback, no user input).

Concurrently: faster-whisper medium.en (CUDA int8_float16) transcribing in a loop, F5-TTS (CUDA) synthesizing
normal and adversarial text, and a burst of scheduler-managed Ollama requests (planner/coding/question on
qwen3.5:9b and jarvis-codex-qwen3.5:9b; cleanup qwen2.5:0.5b and context qwen3.5:0.8b) through the real
jarvis.gpu_scheduler.install() path. Starts an OWNED `ollama serve` on 127.0.0.1:11434 only if the port is free,
and stops only that process. Usage: python live_load.py <out_dir>
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time

WT_APP = Path(__file__).resolve().parents[2]
MAIN_APP = Path(r'D:\Kunals GitHub Repo\Jarvis\app')
OLLAMA = r'C:\Users\kunal\AppData\Local\Programs\Ollama\ollama.exe'
sys.path.insert(0, str(WT_APP))

ADVERSARIAL = [
    'Hello, I finished the report and saved it to your documents folder.',
    '日本語のテキストと中文字符混在 mixed with English words.',
    'The integral of x squared dx equals x³/3 + C, and √2 ≈ 1.414, while ∑ from i=1 to n of i is n(n+1)/2.',
    'Open https://example.com/path?query=value&token=abc123#section and check C:\\Users\\kunal\\Documents\\report_v2.docx.',
    'Traceback (most recent call last):\n  File "main.py", line 42, in <module>\n    raise ValueError("bad input")\nValueError: bad input',
    '| Name | Value |\n| --- | --- |\n| cpu_threads | 12 |\n| gpu_layers | 9 |',
    ' '.join(['This is a long stream sentence number %d about the weather and the schedule.' % i for i in range(70)]),
]

F5_CHILD = r'''
import json, sys, time, threading, traceback
sys.path.insert(0, sys.argv[1]); main = sys.argv[2]; texts = json.loads(sys.argv[3]); seconds = float(sys.argv[4])
from pathlib import Path
cfg = json.loads((Path(sys.argv[1])/'config/config.json').read_text(encoding='utf-8'))['speech']['f5']
cfg = {**cfg, 'reference_audio': str(Path(main)/cfg['reference_audio'])}
from jarvis import f5_speech
from f5_tts.api import F5TTS
t0 = time.perf_counter()
voice = F5TTS(model='F5TTS_v1_Base', device='cuda', ckpt_file='', hf_cache_dir=str(Path(main)/'models/voices/f5/cache'))
voice.jarvis_options = cfg
for _ in f5_speech.render(voice, {'text': 'The voice system is ready.'}, threading.Event()): pass
print(json.dumps({'ready': True, 'load_s': round(time.perf_counter()-t0, 2)}), flush=True)
deadline = time.perf_counter() + seconds; index = 0
while time.perf_counter() < deadline:
    text = texts[index % len(texts)]; index += 1
    row = {'kind': 'f5', 'index': index % len(texts), 'chars': len(text)}
    start = time.perf_counter(); first = None; samples = 0; peak = 0.
    try:
        for audio, rate in f5_speech.render(voice, {'text': text}, threading.Event()):
            if first is None: first = time.perf_counter() - start
            samples += audio.size; peak = max(peak, float(abs(audio).max()))
        row.update(ttfa_s=round(first, 3) if first is not None else None, total_s=round(time.perf_counter()-start, 3),
                   audio_s=round(samples/24000, 2), peak=round(peak, 3), clipped=peak > 1.0)
    except Exception as exc:
        row.update(error=type(exc).__name__, oom='out of memory' in str(exc).lower(), detail=str(exc)[:200])
    print(json.dumps(row), flush=True)
print(json.dumps({'done': True}), flush=True)
'''

WHISPER_CHILD = r'''
import json, sys, time
main = sys.argv[1]; seconds = float(sys.argv[2]); sys.path.insert(0, sys.argv[3])
from jarvis.whisper_backend import load_model  # Jarvis's own CUDA DLL setup and model loader.
t0 = time.perf_counter()
model = load_model(main + r'\models\faster-whisper-medium.en', {'device': 'cuda', 'compute_type': 'int8_float16'})
from faster_whisper import decode_audio
audio = decode_audio(main + r'\models\voices\f5\reference.wav', sampling_rate=16000)
list(model.transcribe(audio, language='en', beam_size=1, vad_filter=False)[0])
print(json.dumps({'ready': True, 'load_s': round(time.perf_counter()-t0, 2)}), flush=True)
deadline = time.perf_counter() + seconds
while time.perf_counter() < deadline:
    start = time.perf_counter(); row = {'kind': 'whisper'}
    try:
        segments, _ = model.transcribe(audio, language='en', beam_size=1, vad_filter=False)
        row.update(text=' '.join(s.text.strip() for s in segments)[:120], latency_s=round(time.perf_counter()-start, 3))
    except Exception as exc:
        row.update(error=type(exc).__name__, oom='out of memory' in str(exc).lower(), detail=str(exc)[:200])
    print(json.dumps(row), flush=True)
print(json.dumps({'done': True}), flush=True)
'''


def vram_sample():
    total = subprocess.run(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
                           capture_output=True, text=True, timeout=5).stdout.strip()
    return int(total) if total.isdigit() else -1


def port_free(port):
    with socket.socket() as probe:
        return probe.connect_ex(('127.0.0.1', port)) != 0


def reader(process, sink, ready):
    for line in process.stdout:
        line = line.strip()
        if not line.startswith('{'):
            continue
        row = json.loads(line)
        if row.get('ready'):
            sink.append({'event': 'ready', **row}); ready.set()
        else:
            sink.append(row)


def llm_storm(out):
    import requests
    from jarvis.gpu_scheduler import install
    calls = []
    def call(role, model, delay, label):
        time.sleep(delay)
        client = install(requests.Session(), role)
        row = {'label': label, 'role': role, 'model': model, 'submitted': time.time()}
        try:
            response = client.post('http://127.0.0.1:11434/api/generate', json={
                'model': model, 'prompt': 'In one short sentence, what is a GPU scheduler? (' + label + ')',
                'stream': False, 'think': False, 'options': {'num_ctx': 4096 if model.startswith('qwen2.5') or '0.8b' in model else 16384,
                'num_predict': 32, 'temperature': 0}}, timeout=900)
            body = response.json()
            row.update(finished=time.time(), status=response.status_code, gpu=getattr(response, 'jarvis_gpu', None),
                       error=body.get('error'), oom='out of memory' in str(body.get('error', '')).lower())
        except Exception as exc:
            row.update(finished=time.time(), error=type(exc).__name__ + ': ' + str(exc)[:200],
                       oom='out of memory' in str(exc).lower())
        calls.append(row)
    plan = [('question', 'qwen3.5:9b', 0, 'question-1'),
            ('cleanup', 'qwen2.5:0.5b', 1.0, 'cleanup-1'), ('context', 'qwen3.5:0.8b', 1.0, 'context-1'),
            ('question', 'qwen3.5:9b', 1.5, 'question-2'), ('coding', 'jarvis-codex-qwen3.5:9b', 2.0, 'coding-1'),
            ('planner', 'qwen3.5:9b', 2.5, 'planner-1'), ('cleanup', 'qwen2.5:0.5b', 3.0, 'cleanup-2'),
            ('context', 'qwen3.5:0.8b', 3.0, 'context-2'), ('background', 'qwen2.5:0.5b', 3.0, 'background-1')]
    threads = [threading.Thread(target=call, args=item) for item in plan]
    [t.start() for t in threads]
    [t.join() for t in threads]
    out['llm'] = sorted(calls, key=lambda r: r['submitted'])


def main(out_dir):
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    result = {'date': time.strftime('%Y-%m-%d %H:%M:%S'), 'idle_vram_mb': vram_sample(), 'samples': []}
    if not port_free(11434):
        raise SystemExit('Port 11434 is in use by another Ollama; refusing to share or stop it.')
    gpu_events = WT_APP/'.jarvis-runtime/gpu/events.jsonl'
    if gpu_events.exists():
        gpu_events.unlink()
    log = open(out_dir/'live-ollama.log', 'w', encoding='utf-8')
    server = subprocess.Popen([OLLAMA, 'serve'], env={**os.environ, 'OLLAMA_HOST': '127.0.0.1:11434'}, stdout=log,
                              stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    stop = threading.Event()
    def sample():
        while not stop.is_set():
            result['samples'].append((round(time.time(), 2), vram_sample())); time.sleep(.1)
    sampler = threading.Thread(target=sample, daemon=True); sampler.start()
    children, rows = [], {'f5': [], 'whisper': []}
    try:
        import requests
        for _ in range(100):
            try:
                requests.get('http://127.0.0.1:11434/api/version', timeout=1).raise_for_status(); break
            except requests.RequestException:
                time.sleep(.3)
        ready = {'f5': threading.Event(), 'whisper': threading.Event()}
        f5 = subprocess.Popen([str(MAIN_APP/'.venv-f5/Scripts/python.exe'), '-c', F5_CHILD, str(WT_APP), str(MAIN_APP),
                               json.dumps(ADVERSARIAL), '240'], stdout=subprocess.PIPE, stderr=open(out_dir/'live-f5.err', 'w'),
                              text=True, encoding='utf-8', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        whisper = subprocess.Popen([str(MAIN_APP/'.venv/Scripts/python.exe'), '-c', WHISPER_CHILD, str(MAIN_APP), '240', str(WT_APP)],
                                   stdout=subprocess.PIPE, stderr=open(out_dir/'live-whisper.err', 'w'), text=True, encoding='utf-8',
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        children = [f5, whisper]
        for name, process in (('f5', f5), ('whisper', whisper)):
            threading.Thread(target=reader, args=(process, rows[name], ready[name]), daemon=True).start()
        for name in ready:
            if not ready[name].wait(600):
                raise SystemExit(name + ' did not become ready')
        result['warm_vram_mb'] = vram_sample()
        result['storm_started'] = time.time()
        llm_storm(result)
        result['storm_finished'] = time.time()
        for process in children:
            process.wait(600)
    finally:
        stop.set(); sampler.join()
        for process in children:
            if process.poll() is None:
                process.kill()
        server.terminate()
        try:
            server.wait(20)
        except subprocess.TimeoutExpired:
            server.kill()
        log.close()
    result['f5'], result['whisper'] = rows['f5'], rows['whisper']
    result['scheduler_events'] = [json.loads(l) for l in gpu_events.read_text().splitlines()] if gpu_events.exists() else []
    result['final_idle_vram_mb'] = vram_sample()
    (out_dir/'live-load.json').write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    main(sys.argv[1])
