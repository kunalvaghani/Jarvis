"""Sequential actual question inference while the configured Whisper GPU model is resident.

No microphone, user prompts, app actions, model substitutions or shared-server shutdown.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time

import requests
from jarvis.knowledge_worker import answer
from jarvis.whisper_backend import load_model

BASE = Path(__file__).resolve().parents[2]


class MeasuredSession(requests.Session):
    def __init__(self):
        super().__init__(); self.trust_env = False; self.metrics = []

    def post(self, url, **kwargs):
        response = super().post(url, **kwargs)
        if kwargs.get('stream'):
            original = response.iter_lines
            def lines(*args, **options):
                for line in original(*args, **options):
                    if line:
                        row = json.loads(line)
                        if row.get('done'):
                            self.metrics.append({key: row.get(key) for key in
                                ('load_duration', 'prompt_eval_count', 'prompt_eval_duration', 'eval_count', 'eval_duration')})
                    yield line
            response.iter_lines = lines
        return response


def main():
    config = json.loads((BASE/'config/config.json').read_text(encoding='utf-8'))
    whisper = load_model(BASE/config['model_path'], config['whisper'])
    rows = []
    with MeasuredSession() as http:
        for gpu_layers in (0, 12):
            options = {**config['knowledge'], 'num_gpu': gpu_layers}
            for repetition in range(2):
                started = time.monotonic(); first = [None]; phases = []
                def progress(event):
                    phase = event.get('phase')
                    if phase not in phases: phases.append(phase)
                    if event.get('text') and first[0] is None: first[0] = time.monotonic()-started
                result = answer({'question': 'What is two plus two? Answer in one English sentence.',
                    'options': options, 'stream_answer': True, 'history': [], 'memory_retrieval_done': True},
                    client=http, progress=progress)
                elapsed = time.monotonic()-started
                text = result.get('answer', '').lower()
                correct = ('four' in text or '4' in text) and len(text) < 500
                gpu = subprocess.run(['nvidia-smi', '--query-gpu=memory.total,memory.used', '--format=csv,noheader,nounits'],
                    capture_output=True, text=True, timeout=10,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).stdout.strip()
                resident = http.get('http://127.0.0.1:11434/api/ps', timeout=5).json().get('models', [])
                row = {'num_gpu': gpu_layers, 'repetition': repetition+1, 'seconds': round(elapsed, 3),
                    'first_answer_seconds': round(first[0], 3) if first[0] is not None else None,
                    'correct': correct, 'phases': phases, 'model_metrics': http.metrics[-1] if http.metrics else {},
                    'gpu_total_used_mib': gpu,
                    'resident': [{key: model.get(key) for key in ('name', 'size', 'size_vram')} for model in resident]}
                rows.append(row); print(json.dumps(row), flush=True)
    record = {'date': datetime.now(timezone.utc).isoformat(),
        'scope': 'Four sequential actual configured 9B question calls, CPU vs partial GPU; configured Whisper resident. No live mic or concurrent tasks. Cold/load and repeated timings retained.',
        'whisper_device': whisper.model.device, 'checks': rows, 'passed': all(row['correct'] for row in rows)}
    path = BASE/'artifacts/reports/production-question-latency.json'
    if path.exists():
        history = path.with_name('production-question-latency-history.json')
        previous = json.loads(history.read_text()) if history.exists() else []
        previous.append(json.loads(path.read_text()))
        history.write_text(json.dumps(previous, indent=2)+'\n')
    path.write_text(json.dumps(record, indent=2)+'\n')
    return record['passed']


if __name__ == '__main__': raise SystemExit(0 if main() else 1)
