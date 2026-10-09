"""Read-only, bounded Ollama metadata; never export prompts or whole user logs."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess

import psutil
from jarvis.knowledge_worker import session

BASE = Path(__file__).resolve().parents[2]


def main():
    ram = psutil.virtual_memory()
    result = {'date': datetime.now(timezone.utc).isoformat(),
              'scope': 'Read-only metadata and historical error counts; no prompts, chat database, recordings or screenshot export.',
              'RAM_GiB': {'total': round(ram.total/2**30, 2), 'available': round(ram.available/2**30, 2)}}
    client = session()
    try:
        result['server'] = client.get('http://127.0.0.1:11434/api/version', timeout=3).json()
        result['models'] = []
        for name in ('qwen3.5:9b', 'qwen3.5:latest', 'qwen3-coder:latest'):
            response = client.post('http://127.0.0.1:11434/api/show', json={'model': name}, timeout=5)
            data = response.json()
            result['models'].append({'name': name, 'status': response.status_code,
                                     'details': data.get('details'), 'capabilities': data.get('capabilities')})
        result['loaded'] = client.get('http://127.0.0.1:11434/api/ps', timeout=3).json()
    except Exception as exc:
        result['api_error_type'] = type(exc).__name__
    finally:
        client.close()
    gpu = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,memory.used,driver_version', '--format=csv,noheader'],
                         capture_output=True, text=True, timeout=10)
    result['gpu'] = gpu.stdout.strip() if gpu.returncode == 0 else 'unavailable'
    logs = Path(os.environ['LOCALAPPDATA']) / 'Ollama'
    result['historical_log_counts'] = []
    phrases = {'port_conflict': 'Only one usage of each socket address',
               'gpu_discovery_timeout': 'GPU discovery watchdog timed out',
               'cancelled_load': 'client connection closed before llama-server finished loading',
               'desktop_shutdown': 'shutting down desktop server'}
    for path in sorted(logs.glob('*log')):
        if path.stat().st_size > 10_000_000 or path.name == 'upgrade.log':
            continue
        content = path.read_text(encoding='utf-8', errors='replace')
        counts = {name: content.count(phrase) for name, phrase in phrases.items()}
        if any(counts.values()):
            result['historical_log_counts'].append({'file': path.name, **counts})
    config = json.loads((BASE / 'config/config.json').read_text(encoding='utf-8'))
    result['jarvis'] = {'planner': config['brain']['planner'], 'coder': config['brain']['coder'],
                        'planning_http_seconds': config['brain'].get('timeout_seconds', 120),
                        'coding_seconds': config['brain'].get('coding_timeout_seconds', 900),
                        'question_num_gpu': config['knowledge'].get('num_gpu', 0)}
    state = json.loads((BASE / '.jarvis-runtime/state/task_state.json').read_text(encoding='utf-8')).get('current', {})
    result['last_task'] = {name: state.get(name) for name in ('status', 'stage', 'started_at', 'updated_at')}
    result['last_task']['read_timeout_120'] = 'read timeout=120' in str(state.get('result', ''))
    (BASE / 'artifacts/reports/ollama-diagnostics.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
