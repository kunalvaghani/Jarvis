"""Real local text-generation timing; no microphone, speaker or private history."""
import json
import sys
import time
from pathlib import Path
from jarvis.natural_conversation import generate
from jarvis.knowledge_worker import chat


def main():
    base = Path(__file__).resolve().parents[2]
    options = json.loads((base/'config/config.json').read_text(encoding='utf-8'))['knowledge']
    history, rows = [], []
    from jarvis.question_client import QuestionClient
    first, started = None, 0
    def report(kind, value):
        nonlocal first
        if kind == 'answer_stream' and value.get('text') and first is None:
            first = time.monotonic()-started
    worker = QuestionClient(base, report) if '--worker' in sys.argv else None
    try:
        for question in ['Hello, Jarvis.', 'I had a rough day at work.', 'It was mostly the meetings. Any ideas?', 'Thanks, that helps.']:
            started, first = time.monotonic(), None
            request = {'question': question, 'options': options, 'history': history,
                       '_natural_chat': True, 'stream_answer': True, 'memory_retrieval_done': True}
            result = worker.request(request, lambda: False) if worker else generate(request, chat)
            rows.append({'question': question, **result, 'worker_protocol': bool(worker),
                         'request_seconds': time.monotonic()-started, 'first_visible_text_seconds': first})
            history.extend([{'role': 'user', 'content': question}, {'role': 'assistant', 'content': result['answer']}])
    finally:
        if worker:
            worker.close()
    suffix = '-worker' if worker else ''
    (base/f'.jarvis-runtime/natural-conversation-verification{suffix}.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    print(json.dumps(rows))


if __name__ == '__main__':
    main()
