"""Synthetic paced island text through real F5 worker; no speaker playback."""
import json
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
from jarvis.speech import Speech, spoken_text


def main():
    base = Path(__file__).resolve().parents[2]
    config = json.loads((base/'config/config.json').read_text(encoding='utf-8'))
    speech = Speech(config['speech'], lambda *args: None)
    events = queue.Queue()
    text = ('Your current voice settings are preserved, and I can begin speaking as the answer arrives. '
            'A complete sentence is sent to the voice worker while the rest of this synthetic reply continues to appear. '
            'The model uses the same reference recording and quality settings, and the final answer adds only words that have not already been queued. '
            'You can still stop speech whenever you need to.')
    with (base/'.jarvis-runtime/f5-island-stream.log').open('w', encoding='utf-8') as log:
        worker = subprocess.Popen([sys.executable, '-u', '-m', 'jarvis.f5_speech', '--serve', '--no-playback'],
            cwd=base, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, encoding='utf-8',
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        def read():
            for line in worker.stdout:
                events.put(json.loads(line))
            events.put({'error': 'Worker exited'})
        threading.Thread(target=read, daemon=True).start()
        try:
            ready = events.get(timeout=120)
            if not ready.get('ready'):
                raise RuntimeError(ready)
            started = time.monotonic()
            finished = []
            def feed():
                words = text.split()
                for index in range(len(words)):
                    speech.stream(' '.join(words[:index+1]), phase='Groq public answer')
                    time.sleep(.1)
                speech.say(text)
                finished.append(time.monotonic()-started)
            producer = threading.Thread(target=feed)
            producer.start()
            submitted, pending, first_audio, first_submit = [], set(), None, None
            deadline = started+180
            while producer.is_alive() or not speech.queue.empty() or pending:
                if time.monotonic()>deadline:
                    raise TimeoutError('Streaming voice verification timed out')
                try:
                    _, content = speech.queue.get_nowait()
                    request_id = len(submitted)+1
                    submitted.append(content)
                    pending.add(request_id)
                    if first_submit is None:
                        first_submit = time.monotonic()-started
                    worker.stdin.write(json.dumps({'id': request_id, 'text': content})+'\n')
                    worker.stdin.flush()
                except queue.Empty:
                    pass
                try:
                    row = events.get(timeout=.02)
                except queue.Empty:
                    continue
                if row.get('error'):
                    raise RuntimeError(row)
                if row.get('audio_ready') and first_audio is None:
                    first_audio = time.monotonic()-started
                if row.get('done'):
                    pending.discard(row['id'])
            assert ' '.join(submitted) == spoken_text(text), submitted
            result = {'kind': 'Synthetic text paced at 0.1 s per word; actual CUDA F5 synthesis, no speaker playback',
                      'first_sentence_queued_seconds': round(first_submit, 3),
                      'first_audio_ready_seconds': round(first_audio, 3),
                      'text_finished_seconds': round(finished[0], 3),
                      'audio_before_text_finished': first_audio < finished[0],
                      'synthesis_completed_seconds': round(time.monotonic()-started, 3),
                      'all_words_queued_once': True, 'requests': len(submitted),
                      'nfe_step': config['speech']['f5']['nfe_step']}
            (base/'.jarvis-runtime/f5-island-stream-verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            print(json.dumps(result))
        finally:
            worker.stdin.close()
            try:
                worker.wait(timeout=5)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait(timeout=5)
            worker.stdout.close()
            speech.close()


if __name__ == '__main__':
    main()
