"""Per-stage voice latency on this PC: speech recognition, intent, chat reply, speech output, internal hand-offs.

Offline: public/generated fixtures in artifacts/realtime-voice, no microphone, no playback, no network beyond the
local Ollama. Prints one JSON report (timings only, never audio). Run from app/:

    .venv/Scripts/python scripts/verification/benchmark_voice_latency.py [--stages asr,intent,chat,tts,hops]
"""
import argparse
import json
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))
FIXTURES = BASE / 'artifacts/realtime-voice'


def ms(seconds):
    return round(seconds * 1000, 1)


def summary(values):
    values = sorted(values)
    return {'median_ms': ms(statistics.median(values)), 'min_ms': ms(values[0]), 'max_ms': ms(values[-1]), 'runs': len(values)}


def asr(models=('faster-whisper-medium.en', 'faster-whisper-large-v3-turbo'), repeats=3):
    from faster_whisper.audio import decode_audio
    from jarvis.whisper_backend import load_model
    from jarvis.audio import ASR_PROMPT
    clips = [('en', 'public-fixture.wav'), ('en', 'fleurs-en-0.wav'), ('hi', 'public-hindi-fixture.wav'),
             ('hi-en', 'mixed-en-hi.wav')]
    report = {}
    for name in models:
        model = load_model(BASE / 'models' / name, {'device': 'cuda', 'compute_type': 'int8_float16',
                                                    'language': 'en' if name.endswith('.en') else 'auto'})
        list(model.transcribe(decode_audio(str(FIXTURES / clips[0][1]), sampling_rate=16000), beam_size=1)[0])
        rows = {}
        for language, clip in clips:
            if name.endswith('.en') and language != 'en':
                continue
            audio = decode_audio(str(FIXTURES / clip), sampling_rate=16000)
            for beam in (5, 1):
                times, text, detected = [], '', ''
                for _ in range(repeats):
                    started = time.perf_counter()
                    segments, info = model.transcribe(
                        audio, language='en' if name.endswith('.en') else None, beam_size=beam, temperature=0,
                        condition_on_previous_text=False, word_timestamps=True, vad_filter=False,
                        initial_prompt=ASR_PROMPT)
                    text = ' '.join(s.text.strip() for s in segments)
                    times.append(time.perf_counter() - started)
                    detected = info.language
                rows[f'{clip} beam{beam}'] = {**summary(times), 'audio_s': round(len(audio) / 16000, 2),
                                              'language': detected, 'text': text[:120]}
        report[name] = rows
        del model
    return report


def intent():
    from jarvis.conversation_intent import quick_kind, model_kind
    samples = ['open notepad', "I'm tired today", 'what do you think about that', 'remind me what we said',
               'youtube kholo', 'mujhe ek joke sunao']
    report = {}
    for text in samples:
        started = time.perf_counter()
        kind = quick_kind(text)
        quick = time.perf_counter() - started
        row = {'quick_kind': kind, 'quick_ms': ms(quick)}
        if kind is None:
            started = time.perf_counter()
            row['model_kind'] = model_kind(text, {'model': 'qwen3.5:0.8b', 'timeout_seconds': 3.0})
            row['model_ms'] = ms(time.perf_counter() - started)
        report[text] = row
    return report


def chat(repeats=3):
    import requests
    from jarvis.natural_conversation import SYSTEM
    session = requests.Session()
    session.trust_env = False
    report = {}
    for text in ('hello, how is your day going?', 'mera din aaj bahut thaka dene wala tha'):
        firsts, totals = [], []
        answer = ''
        for _ in range(repeats):
            payload = {'model': 'qwen3.5:0.8b', 'stream': True, 'think': False, 'keep_alive': '30m',
                       'messages': [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': text}],
                       'options': {'num_ctx': 2048, 'num_predict': 160, 'num_gpu': 0, 'num_thread': 6, 'temperature': .65}}
            started, first, answer = time.perf_counter(), None, ''
            with session.post('http://127.0.0.1:11434/api/chat', json=payload, stream=True, timeout=60) as response:
                for line in response.iter_lines():
                    if not line:
                        continue
                    piece = json.loads(line).get('message', {}).get('content', '')
                    if piece and first is None:
                        first = time.perf_counter() - started
                    answer += piece
            firsts.append(first or 0.)
            totals.append(time.perf_counter() - started)
        report[text] = {'first_token': summary(firsts), 'total': summary(totals), 'answer': answer[:160]}
    return report


def tts(repeats=3):
    """Time from request to the first synthesized audio in the warm Kokoro worker (no playback)."""
    process = subprocess.Popen([sys.executable, '-m', 'jarvis.kokoro_speech', '--serve', '--no-playback'], cwd=BASE,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               encoding='utf-8', bufsize=1)
    started = time.perf_counter()
    for line in process.stdout:
        if json.loads(line).get('ready'):
            break
    report = {'worker_ready_ms': ms(time.perf_counter() - started)}
    request = 0
    try:
        for label, voice, text in (('en short', 'am_michael:60,am_fenrir:40', 'On it.'),
                                   ('en sentence', 'am_michael:60,am_fenrir:40', 'Sure, I am opening YouTube for you now.'),
                                   ('en reply', 'am_michael:60,am_fenrir:40', 'Sure. That sounds like a long day, so take it easy tonight and get some proper rest.'),
                                   ('hi sentence', 'hm_omega', 'हाँ बिल्कुल, मैं अभी आपके लिए यूट्यूब खोल रहा हूँ।')):
            times = []
            for _ in range(repeats):
                request += 1
                sent = time.perf_counter()
                process.stdin.write(json.dumps({'id': request, 'text': text, 'voice': voice, 'speed': 1.0,
                                                'natural': True, 'breaths': False}, ensure_ascii=False) + '\n')
                process.stdin.flush()
                first = None
                for line in process.stdout:
                    row = json.loads(line)
                    if row.get('id') != request:
                        continue
                    if row.get('audio_ready') and first is None:
                        first = time.perf_counter() - sent
                    if row.get('done') or row.get('error'):
                        if row.get('error'):
                            first = None
                        break
                if first is not None:
                    times.append(first)
            report[label] = summary(times) if times else {'error': 'no audio'}
    finally:
        process.stdin.close()
        process.wait(timeout=20)
    return report


def hops(repeats=200):
    """Hand-offs inside Jarvis that add delay without doing work."""
    import queue as queue_module
    from jarvis.commands import Command
    from jarvis.engine import Engine
    report = {}
    sent = []
    engine = Engine(sent.append, lambda *_: None, 600)
    engine.activate()
    times = []
    for _ in range(repeats):
        started = time.perf_counter()
        engine.feed('open notepad', final=True)
        times.append(time.perf_counter() - started)
    report['engine_feed_to_submit'] = summary(times)
    # ScheduledQueue.get(): the lane threads ask for work; measure put -> get wake-up on a real store.
    import tempfile
    from jarvis.task_store import TaskStore
    from jarvis.task_scheduler import ScheduledQueue
    from jarvis.task_policy import classify
    from dataclasses import asdict
    folder = Path(tempfile.mkdtemp())
    store = TaskStore(folder / 'q.sqlite3', capacity=4096)
    scheduler = ScheduledQueue(store, {}, recover=False)
    waits, takes = [], []
    for index in range(40):
        command = Command('ask', f'hello {index}')
        got, box = threading.Event(), {}

        def take():
            while not got.is_set():
                try:
                    box['item'] = scheduler.get(timeout=2., lane='legacy')
                    box['at'] = time.perf_counter()
                    got.set()
                    scheduler.outcome('COMPLETED', 'benchmark')
                    scheduler.task_done()
                except queue_module.Empty:
                    pass
        thread = threading.Thread(target=take)
        thread.start()
        time.sleep(.03)  # the lane thread is already waiting, as in Jarvis
        identity, _ = store.admit(asdict(command), None)
        store.transition(identity, 'CLASSIFYING')
        put = time.perf_counter()
        scheduler.put_nowait((0, command, threading.Event()), identity, classify(asdict(command)))
        got.wait(5)
        thread.join(5)
        waits.append(box['at'] - put)
        started = time.perf_counter()
        scheduler._take('legacy')
        takes.append(time.perf_counter() - started)
    report['scheduler_put_to_lane'] = summary(waits)
    report['scheduler_one_poll_cost'] = summary(takes)
    report['ui_event_drain'] = {'note': 'speech started from the Tk event drain: 16 ms tick, mean 8 ms when idle'}
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stages', default='asr,intent,chat,tts,hops')
    parser.add_argument('--out')
    args = parser.parse_args()
    report = {'date': time.strftime('%Y-%m-%d %H:%M'), 'machine_note': 'idle PC, Ollama local, Whisper on CUDA'}
    for stage in args.stages.split(','):
        started = time.perf_counter()
        report[stage] = globals()[stage]()
        report[stage + '_elapsed_s'] = round(time.perf_counter() - started, 1)
        print(stage, 'done', flush=True, file=sys.stderr)
    text = json.dumps(report, indent=1, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text, encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
