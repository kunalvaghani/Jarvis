"""Public native-planning comparison. Does not dispatch proposed actions.

Real app completion/recovery requires separate live acceptance. No simulated
planning correctness is reported as a verified external task completion rate.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import sys
import time

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))
from jarvis.brain_worker import Models
from jarvis.tools import SPECS
from jarvis.gpu_scheduler import memory

CASES = [
    ('windows', 'Open Calculator', 'open', 'Calculator'),
    ('youtube', 'Search YouTube for jazz piano', 'media_search', 'jazz piano'),
    ('spotify', 'Pause Spotify playback', 'media_control', 'pause'),
    ('blender', 'Inspect Blender before creating a cube', 'application_inspect', 'Blender'),
    ('unreal', 'Inspect Unreal Engine before editing the project', 'application_inspect', 'Unreal Engine'),
    ('coding', 'Read main.py in this folder before debugging the code', 'read_file', 'main.py'),
    ('research', 'Research public Python release documentation', 'web_search', 'Python'),
    ('autonomous', 'Start an autonomous review by listing files in this folder', 'list_files', ''),
    ('unfamiliar', 'Find a capability for an unfamiliar CAD application', 'tool_search', 'CAD'),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--models', nargs='+', default=['qwen3.5:9b', 'qwen3.5:4b', 'hierarchy'])
    parser.add_argument('--repeat', type=int, default=2)
    parser.add_argument('--executor', choices=['qwen3.5:2b', 'qwen3.5:4b'], default='qwen3.5:4b')
    parser.add_argument('--cases', nargs='+', choices=[row[0] for row in CASES])
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.repeat <= 10 or args.out.exists():
        parser.error('Use 1-10 repetitions and a new output directory.')
    args.out.mkdir(parents=True)
    config = json.loads((BASE/'config/config.json').read_text(encoding='utf-8'))
    worker = Models()
    installed = worker.client.get('http://127.0.0.1:11434/api/tags', timeout=5).json()['models']
    (args.out/'inventory.json').write_text(json.dumps([r for r in installed if r.get('name') in {'qwen3.5:2b', 'qwen3.5:4b', 'qwen3.5:9b'}], indent=2), encoding='utf-8')
    names = {row['name'] for row in installed}
    all_rows = []
    for model in args.models:
        if model != 'hierarchy' and model not in names:
            print(json.dumps({'model': model, 'status': 'missing'}), flush=True)
            continue
        for repetition in range(args.repeat):
            for group, goal, expected, value in CASES:
                if args.cases and group not in args.cases:
                    continue
                options = {**config['brain'], 'trained_pc_checkpoint': None}
                options['model_hierarchy'] = {**options.get('model_hierarchy', {}), 'enabled': model == 'hierarchy', 'execution_model': args.executor}
                if model != 'hierarchy':
                    options.update(planner=model, decision=model)
                # Same small catalog for every model. Unrelated alternative is
                # deliberate: the oracle checks selection, not schema alone.
                tools = [{'action': s.name, 'description': s.description} for s in SPECS
                         if s.name in {expected, 'tool_search', 'application_inspect'}]
                request = {'operation': 'next_step', 'options': options, 'goal': goal,
                           'tools': tools, 'screen': {'title': 'Benchmark owned fixture', 'controls': []},
                           'apps': ['Calculator', 'Blender', 'Unreal Engine'], 'completed': [], 'steps_left': 10}
                start = time.perf_counter()
                row = {'configuration': model, 'executor': args.executor, 'case': group, 'repetition': repetition,
                       'at': datetime.now(timezone.utc).isoformat(), 'before_gpu': memory()}
                try:
                    result = worker.predict(request)
                    steps = result.get('steps', [])
                    selected = steps[0] if len(steps) == 1 else {}
                    # Exact payload checks where the public request is literal;
                    # semantic research/CAD query quality is not inferred here.
                    row.update(selected_tool=selected.get('action'), expected_tool=expected,
                               tool_selection_correct=selected.get('action') == expected,
                               literal_preserved=(not value or value.casefold() in str(selected.get('value', '')).casefold()),
                               model_used=result.get('model_used'), route=result.get('model_route'),
                               inference=result.get('inference'), proposal=selected)
                except Exception as error:
                    row.update(error_type=type(error).__name__, error=str(error)[:500], tool_selection_correct=False)
                row.update(wall_s=time.perf_counter()-start, after_gpu=memory())
                import psutil
                row['benchmark_rss_mb'] = psutil.Process().memory_info().rss/1048576
                row['system_ram_used_mb'] = psutil.virtual_memory().used/1048576
                processes = {}
                for process in psutil.process_iter(['name']):
                    if (process.info['name'] or '').casefold() == 'ollama.exe':
                        try:
                            for resident in [process, *process.children(recursive=True)]:
                                processes[resident.pid] = resident.memory_info().rss/1048576
                        except psutil.Error:
                            pass
                row['ollama_process_rss_mb'] = sum(processes.values()) if processes else None
                try:
                    observed = worker.client.get('http://127.0.0.1:11434/api/ps', timeout=3).json()['models']
                    row['resident_models'] = [{k: r.get(k) for k in ('name', 'digest', 'size', 'size_vram', 'context_length')} for r in observed]
                except Exception:
                    row['resident_models'] = None
                all_rows.append(row)
                with (args.out/'rows.jsonl').open('a', encoding='utf-8') as output:
                    output.write(json.dumps(row)+'\n')
                print(json.dumps({k: row[k] for k in ('configuration', 'case', 'wall_s', 'tool_selection_correct')}), flush=True)
        summary = {}
        for name in args.models:
            rows = [r for r in all_rows if r['configuration'] == name]
            if rows:
                times = sorted(r['wall_s'] for r in rows)
                summary[name] = {'samples': len(rows), 'p50_s': statistics.median(times),
                    'p95_s': times[min(len(times)-1, __import__('math').ceil(.95*len(times))-1)],
                    'tool_selection_correct': sum(r['tool_selection_correct'] for r in rows),
                    'errors': sum('error_type' in r for r in rows), 'external_tasks_executed': 0}
        (args.out/'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    worker.client.close()


if __name__ == '__main__':
    main()
