"""Owned local inference probe; synthetic evidence, no microphone or accounts."""
from datetime import datetime, timezone
import json
from pathlib import Path
import threading

from jarvis.cloud_policy import classify
from jarvis.knowledge import Knowledge


def main():
    base = Path(__file__).resolve().parents[2]
    out = base / 'artifacts/workflow-graph/live-private-context.json'
    finished = threading.Event()
    reports, requests = [], []
    worker = Knowledge({'enabled': True, 'model': 'qwen3.5:0.8b', 'internet': False,
        'stream': False, 'num_predict': 256, 'timeout_seconds': 90,
        'natural_conversation': {'enabled': True, 'model': 'qwen3.5:0.8b'}},
        lambda kind, value: reports.append((kind, value)))
    original = worker.client.request

    def observed(request, cancelled):
        requests.append(request)
        return original(request, cancelled)

    worker.client.request = observed
    try:
        worker.submit('What is the measured value? Reply with the number only.', web=True,
            workflow_context=[{'task': 'synthetic-owned-producer', 'version': 1,
                'verification': 'verified', 'output': {'measured_value': 7319}}],
            on_complete=lambda *args: finished.set())
        worker.start()
        completed = finished.wait(180)
        answers = [value for kind, value in reports if kind == 'answer']
        policy = classify(requests[0]) if requests else {}
        receipt = {'checked_at': datetime.now(timezone.utc).isoformat(),
            'scope': 'Real Knowledge thread, QuestionClient child and installed local Ollama model; synthetic TaskResult only.',
            'microphone': 'off', 'external_search': 'disabled',
            'model': 'qwen3.5:0.8b', 'completed': completed,
            'policy': policy, 'structured_context': bool(requests and requests[0].get('memory_context', {}).get('task_results')),
            'web_false': bool(requests and requests[0].get('web') is False),
            'answer': answers[-1] if answers else None,
            'errors': [value for kind, value in reports if kind == 'answer_error']}
        receipt['passed'] = bool(completed and answers and '7319' in answers[-1]
            and policy.get('privacy') == 'INTERNAL' and receipt['structured_context'] and receipt['web_false'])
        out.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(receipt), flush=True)
        return 0 if receipt['passed'] else 1
    finally:
        worker.close()


if __name__ == '__main__':
    raise SystemExit(main())
