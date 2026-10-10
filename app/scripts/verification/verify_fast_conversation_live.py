"""Live checks for fast planning, the task queue and natural conversation.

Runs real Jarvis tasks on this desktop (opens Chrome/YouTube, Wikipedia and a new
Notepad window) and a simulated spoken call through the real voice engine. Every
approval request is refused, so nothing is written, sent or deleted. The report
holds flags and timings only, never screen text, answers or account data.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from jarvis.actions import Actions, Desktop
from jarvis.commands import Command
from jarvis.engine import Engine
from jarvis.paths import artifact_path


def gpu_calls(path, offset):
    """Durations of primary-model calls recorded by the GPU scheduler since offset."""
    rows, open_at, calls = [], {}, []
    with path.open() as handle:
        handle.seek(offset)
        rows = [json.loads(line) for line in handle if line.strip()]
    for row in rows:
        if row['stage'] == 'dispatch' and row.get('gpu_slot'):
            open_at[row['role']] = row
        elif row['stage'] == 'released' and row['role'] in open_at:
            calls.append(round(row['at'] - open_at.pop(row['role'])['at'], 1))
    return calls


def main():
    base = Path(__file__).resolve().parents[2]
    config = json.loads((base / 'config/config.json').read_text())
    config['_ui_verification'] = True
    events_path = base / '.jarvis-runtime/gpu/events.jsonl'
    log = []
    t0 = [time.monotonic()]

    def report(kind, message=''):
        log.append((round(time.monotonic() - t0[0], 1), kind, message if isinstance(message, str) else ''))
    actions = Actions(config, base, report, Desktop())
    approvals = []
    actions.approval_handler = lambda kind, detail, cancelled: approvals.append(kind) or False
    result = {'date': datetime.now(timezone.utc).isoformat(), 'passed': False, 'tasks': {},
              'scope': 'Real Actions/Brain dispatch on the desktop and a simulated spoken call through the real Engine, '
                       'action queue and knowledge worker. Approvals refused; flags and timings only.'}
    try:
        for name, goal in (('wikipedia', 'go to wikipedia and open the article about black holes'),
                           ('notepad_typing', 'open notepad and type hello from jarvis')):
            offset = events_path.stat().st_size if events_path.exists() else 0
            t0[0] = time.monotonic()
            answer = str(actions._execute(Command('task', goal)))
            stages = getattr(actions.brain, 'last_step_timings', {}).get('stages', [])
            result['tasks'][name] = {
                'finished': answer.startswith('Finished'), 'seconds': round(time.monotonic() - t0[0], 1),
                'model_call_seconds': gpu_calls(events_path, offset),
                'planner_calls': [{k: row['inference'].get(k) for k in ('prompt_tokens', 'prompt_s', 'output_tokens', 'output_s', 'images', 'continued')}
                                  for row in stages if isinstance(row.get('inference'), dict)]}

        actions.knowledge.start()
        actions.thread.start()
        engine = Engine(actions.submit, report, config.get('wake_timeout_seconds', 600))
        log.clear()
        t0[0] = time.monotonic()
        script = [(0, "jarvis let's watch a video about cats on youtube"),
                  (2, 'go to wikipedia and open the article about black holes'),
                  (4, 'how are you doing?'),
                  (25, 'what are you working on'),
                  (30, "i'm feeling a bit tired today")]
        for at, text in script:
            while time.monotonic() - t0[0] < at:
                time.sleep(.1)
            engine.feed(text, final=True)
        deadline = time.monotonic() + 400
        while time.monotonic() < deadline:
            time.sleep(1)
            with actions.queue_lock:
                busy = actions.current_item is not None or actions.pending_tasks
            if (not busy and actions.queue.unfinished_tasks == 0 and actions.knowledge.queue.unfinished_tasks == 0
                    and time.monotonic() - t0[0] > 45):
                break
        spoken = [(at, text) for at, kind, text in log if kind == 'spoken_reply']
        answers = [(at, text) for at, kind, text in log if kind == 'answer']
        finished = [at for at, text in spoken if text.startswith('Finished')]
        result['call'] = {
            'queued_acknowledged': any(text.startswith("Okay, I'll do that next") for _, text in spoken),
            'tasks_finished': len(finished), 'task_finish_seconds': finished,
            'question_answered_during_task': bool(answers) and bool(finished) and answers[0][0] < max(finished),
            'queue_status_reported': any(text.startswith('Working on:') for _, text in spoken),
            'chat_answers': len(answers), 'answer_seconds': [at for at, _ in answers],
            'statement_classified_as_chat': len(answers) >= 2,
            'warnings': sum(1 for _, kind, _ in log if kind == 'warning')}
        result['approval_requests_refused'] = len(approvals)
        call = result['call']
        result['passed'] = (all(task['finished'] for task in result['tasks'].values()) and call['queued_acknowledged']
                            and call['tasks_finished'] == 2 and call['question_answered_during_task']
                            and call['queue_status_reported'] and call['statement_classified_as_chat'])
    except Exception as error:
        result.update(error_type=type(error).__name__, error=str(error)[:300])
    finally:
        actions.close()
        artifact_path(base, 'fast-conversation-live.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
