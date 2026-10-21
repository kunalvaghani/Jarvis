"""Optional local Qwen plan + actual owned-file tools; no cloud or user apps."""
import argparse
import json
from pathlib import Path
import tempfile

from jarvis.brain import BrainClient
from jarvis.paths import APP_ROOT
from scripts.verification.verify_plan_execution import fixture, scenario


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    options = {'enabled': True, 'planner': 'qwen3.5:9b', 'screen_aware': False,
               'native_tool_calling': False, 'incremental_planning': False,
               'max_task_actions': 20, 'timeout_seconds': 120}
    client = BrainClient(APP_ROOT, options)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            result = fixture(Path(tmp), scenario(0, 2), planner=client)
        result['scope'] = ('Real local qwen3.5:9b initial plan; actual owned file tools; '
                           'deterministic decision and independent disk/action-count verifier. '
                           'Not a live vision, voice, native-tool or cloud acceptance check.')
        Path(args.output).write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps({key: result.get(key) for key in
            ('passed', 'seconds', 'planner_calls', 'completed_actions', 'state_status', 'error', 'scope')}))
    finally:
        client.close()


if __name__ == '__main__':
    main()
