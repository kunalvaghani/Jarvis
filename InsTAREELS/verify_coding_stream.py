"""Explicit live Qwen coding check with source readback and streaming measurements."""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from jarvis.actions import Actions
from jarvis.coder import Coder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', required=True)
    parser.add_argument('--edit', action='store_true')
    args = parser.parse_args()
    base = Path(__file__).resolve().parent
    config = json.loads((base / 'config.json').read_text(encoding='utf-8'))
    if args.edit:
        config['memory'] = {**config.get('memory', {}), 'vault': '.jarvis-runtime/coding-verification-vault'}
    started = time.perf_counter()
    events, chunks = [], []
    def report(kind, message):
        if kind in {'brain', 'action', 'plan'}:
            events.append({'kind': kind, 'seconds': round(time.perf_counter()-started, 3), 'message': str(message)[:400]})
            print(kind + ': ' + str(message)[:300], flush=True)
    actions = Actions(config, base, report)
    if args.edit:
        target = base / '.jarvis-runtime/coding-verification/TestCodes'
        target.mkdir(parents=True, exist_ok=True)
        source = Path('D:/Phython Project/TestCodes/alarm.py')
        destination = target / 'alarm.py'
        if destination.exists():
            raise ValueError('The isolated verification target already exists; inspect it rather than overwriting.')
        destination.write_bytes(source.read_bytes())
        goal = 'Modify alarm.py to add an optional --label argument that prints its text when the alarm rings, preserving existing options.'
    else:
        target = Path('D:/Phython Project/TestCodes')
        goal = 'Create a python script for alarm in test codes folder'
    actions.task_state.start(goal, 'code_task', target)
    from jarvis.code_stream import CodeDraft
    write = CodeDraft.write
    def observed(draft, content):
        write(draft, content)
        chunks.append({'seconds': round(time.perf_counter()-started, 3), 'characters': len(content),
            'draft_on_disk': draft.path.read_text(encoding='utf-8') == draft.header + content})
    CodeDraft.write = observed
    try:
        result = Coder(actions, actions.brain.client).run(target, goal, selected=True)
        content = (target / 'alarm.py').read_text(encoding='utf-8')
        ast.parse(content)
        actions.task_state.finish('completed', result)
        output = {'checked_at': datetime.now(timezone.utc).isoformat(), 'model': config['brain']['coder'],
            'mode': 'isolated edit of generated alarm' if args.edit else 'actual requested alarm creation',
            'seconds': round(time.perf_counter()-started, 3), 'first_disk_update_seconds': chunks[0]['seconds'] if chunks else None,
            'first_code_update_seconds': next((c['seconds'] for c in chunks if c['characters'] > 0), None),
            'draft_updates': len(chunks), 'all_updates_read_back': all(c['draft_on_disk'] for c in chunks),
            'python_syntax_valid': True, 'final_sha256': hashlib.sha256(content.encode()).hexdigest(),
            'characters': len(content), 'scope': 'Real model and filesystem; syntax/readback checked. Alarm timing/sound not yet functionally checked.',
            'events': events, 'updates': chunks}
        name = 'coding-stream-edit-check' if args.edit else 'coding-stream-create-check'
        (base / 'artifacts' / (name + '.json')).write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
        (base / 'artifacts' / (name + '.py')).write_text(content, encoding='utf-8')
        print(json.dumps({k: v for k,v in output.items() if k not in {'events', 'updates'}}, indent=2), flush=True)
    except Exception as exc:
        actions.task_state.finish('failed', str(exc))
        raise
    finally:
        CodeDraft.write = write
        actions.close()


if __name__ == '__main__':
    main()
