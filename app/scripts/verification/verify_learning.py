"""Original/upgraded knowledge-routing benchmarks; no user app operations."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import time
import psutil
from jarvis.actions import Actions
from jarvis.commands import parse
from scripts.verification.verify_hierarchical import inventory

BASE = Path(__file__).resolve().parents[2]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['baseline', 'upgraded'], required=True)
    args = parser.parse_args()
    commands = ['open Chrome', 'check my battery', 'set an alarm for 7 am', 'stop all tasks']
    routing = []
    for _ in range(100):
        for text in commands:
            start = time.perf_counter()
            try:
                parse(text)
            except ValueError:
                pass
            routing.append((time.perf_counter()-start)*1000)
    root = BASE/'.jarvis-runtime/learning-benchmark'/str(time.time_ns())
    root.mkdir(parents=True)
    config = {'files_root': 'managed', 'apps': {}, '_ui_verification': True, 'memory': {'enabled': False},
        'brain': {'enabled': False}, 'knowledge_acquisition': {'enabled': True}}
    actions = Actions(config, root, lambda *_: None)
    memory = actions.screen.knowledge
    lookups, assessments = [], []
    try:
        for _ in range(100):
            start = time.perf_counter()
            memory.describe('notepad.exe', 'Fixture', '')
            lookups.append((time.perf_counter()-start)*1000)
            if args.mode == 'upgraded':
                start = time.perf_counter()
                actions.acquisition.assess('Open Chrome')
                assessments.append((time.perf_counter()-start)*1000)
        process = psutil.Process()
        result = {'date': datetime.now(timezone.utc).isoformat(), 'mode': args.mode,
            'scope': '400 real parser calls; 100 app-memory lookups; upgraded deterministic assessment without web/model/GUI activity. Not a production latency distribution.',
            'routing_median_ms': statistics.median(routing), 'routing_p95_ms': sorted(routing)[379],
            'routing_p99_ms': sorted(routing)[395], 'memory_lookup_median_ms': statistics.median(lookups),
            'gap_assessment_median_ms': statistics.median(assessments) if assessments else 'Unsupported automatic task acquisition path',
            'unknown_app_end_to_end': 'Not measured', 'unknown_website_end_to_end': 'Not measured',
            'planner_latency': 'Not measured', 'peak_vram': 'Not measured',
            'background_overhead': 'Not measured', 'peak_working_set_mb': getattr(process.memory_info(),'peak_wset',process.memory_info().rss)/1048576,
            'source_inventory': inventory()}
        target = BASE/'artifacts/reports'/f'learning-{args.mode}.json'
        if target.exists():
            raise ValueError('Preserve historical measurements before an explicit rerun.')
        target.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k!='source_inventory'}, indent=2))
    finally:
        actions.close()

if __name__ == '__main__':
    main()
