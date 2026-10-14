"""Run the real DeerFlow harness on one scoped Jarvis source-research question."""
import argparse
import json
from pathlib import Path

from .deerflow import request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--goal', required=True)
    parser.add_argument('--model', default='qwen3.5:4b')
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args()
    try:
        result = request(Path(__file__).resolve().parent.parent,
            {'mode': 'research', 'project': str(Path(args.project).resolve(strict=True)),
             'goal': args.goal, 'model': args.model}, timeout_seconds=args.timeout)
        for row in result['receipts']:
            print(json.dumps({'event': 'tool.completed', 'tool': row['action'], 'value': row['value']}))
        print(json.dumps({'event': 'turn.completed', 'answer': result['answer'], 'backend': 'deerflow'}))
        return 0
    except (ValueError, OSError) as exc:
        print(json.dumps({'event': 'error', 'error': str(exc)[:500]}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
