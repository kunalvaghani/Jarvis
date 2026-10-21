"""Paired deterministic planner / real owned-file benchmark; no live LLM claim."""
import argparse
import json
from pathlib import Path
import tempfile
import time
from unittest.mock import patch

from jarvis.brain import Brain
from scripts.verification.verify_plan_execution import FixtureClient, fixture, scenario


def measure():
    original_init, original_request = Brain.__init__, FixtureClient.request
    first_actions, planning_times = [], []
    started = [0.0]
    original_dispatch = Brain.dispatch

    def initialize(self, actions, base, options):
        original_init(self, actions, base, {**options, 'adaptive_planning': True})

    def request(self, operation, cancelled, **data):
        before = time.perf_counter()
        try:
            if operation == 'replan':
                self.calls.append(operation)
                remaining = self.case['steps'][len(data['completed']):]
                return {'done': not remaining, 'question': '', 'steps': remaining}
            return original_request(self, operation, cancelled, **data)
        finally:
            if operation in {'plan', 'replan', 'next_step'}:
                planning_times.append(time.perf_counter() - before)

    def dispatch(self, *args, **kwargs):
        if not first_actions or first_actions[-1] is None:
            first_actions[-1] = time.perf_counter() - started[0]
        return original_dispatch(self, *args, **kwargs)

    results = []
    with tempfile.TemporaryDirectory() as tmp, patch.object(Brain, '__init__', initialize), patch.object(
            FixtureClient, 'request', request), patch.object(Brain, 'dispatch', dispatch):
        for index, length in enumerate((2, 5, 10, 20)):
            first_actions.append(None)
            started[0] = time.perf_counter()
            results.append(fixture(Path(tmp), scenario(index, length)))
    counts = [row.get('planner_calls') for row in results]
    return {'scope': 'simulated planner and deterministic verifier; real owned file tools',
            'cases': results, 'time_to_first_dispatch_seconds': first_actions,
            'planning_seconds': sum(planning_times),
            'planner_calls': sum(counts) if all(type(value) is int for value in counts) else None,
            'verified_successes': sum(row['passed'] for row in results),
            'quality_exact_order': all(row.get('exact_order_and_arguments') for row in results)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = measure()
    Path(args.output).write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items() if key != 'cases'}))
