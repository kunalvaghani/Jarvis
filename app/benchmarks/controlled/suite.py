"""Load and validate controlled benchmark tasks; tiers and hold-out are fixed before a run."""
from pathlib import Path
import sys

import yaml

CATEGORIES = {'web', 'native', 'vision', 'cross_app', 'adversarial'}
SIZES = {'S', 'M', 'L'}
SUCCESS = {'dom_checked', 'dom_values', 'uia_value', 'path_exists', 'app_state', 'file_contains',
           'no_action_outside', 'url_matches', 'window_state', 'download_sha256'}
ROOT = Path(__file__).resolve().parent / 'tasks'


def load(root=ROOT):
    tasks, seen = [], set()
    for path in sorted(Path(root).glob('*.yaml')):
        data = yaml.safe_load(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('tasks'), list):
            raise ValueError(f'{path.name}: expected version 1 with a task list')
        for task in data['tasks']:
            validate(task, path.name)
            if task['id'] in seen:
                raise ValueError(f'{path.name}: duplicate task id {task["id"]}')
            seen.add(task['id'])
            tasks.append(task)
    return tasks


def validate(task, source='task'):
    required = {'id', 'category', 'size', 'holdout', 'command', 'setup', 'teardown', 'success'}
    if not isinstance(task, dict) or required - set(task):
        raise ValueError(f'{source}: task missing {sorted(required - set(task or {}))}')
    if task['category'] not in CATEGORIES or task['size'] not in SIZES or type(task['holdout']) is not bool:
        raise ValueError(f'{source}: {task["id"]} has an invalid category, size or holdout flag')
    if not isinstance(task['command'], str) or not task['command'].strip():
        raise ValueError(f'{source}: {task["id"]} needs a natural-language command')
    if not isinstance(task['success'], dict) or task['success'].get('type') not in SUCCESS:
        raise ValueError(f'{source}: {task["id"]} needs a machine-checkable success condition')


def summary(tasks):
    counts = {}
    for task in tasks:
        key = (task['category'], task['size'], 'holdout' if task['holdout'] else 'tuning')
        counts[key] = counts.get(key, 0) + 1
    return counts


if __name__ == '__main__':
    loaded = load()
    for key, count in sorted(summary(loaded).items()):
        print(*key, count)
    print('tasks', len(loaded), file=sys.stderr)
