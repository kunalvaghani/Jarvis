"""Phase 8 final measurements against the recorded Phase 1 baseline.

MEASURED here (real code, this machine): the Phase 1 harness (re-run), deterministic command parsing,
tool search and held-out tool-selection quality, ReasoningBank retrieval (lexical and, if available,
local embeddings), prompt routing, AZR oracle cost, idle self-evolution overhead, idle GPU memory.
RECORDED (dated evidence from earlier phases, cited by path) or NOT RUN (with a reason) for everything
that needs live voice, a running Jarvis UI, a live planner LLM session, or real user traffic.
Usage: python scripts/verification/phase08_final_benchmarks.py --out <dir>  (refuses to overwrite)
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))
PY = sys.executable


def summary(values):
    values = sorted(values)
    return {'n': len(values), 'p50_ms': round(statistics.median(values), 4),
            'p95_ms': round(values[int((len(values) - 1) * .95)], 4), 'max_ms': round(values[-1], 4)}


def timed(function, repeats):
    out = []
    for _ in range(repeats):
        started = time.perf_counter()
        function()
        out.append((time.perf_counter() - started) * 1000)
    return summary(out)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.out.exists():
        raise SystemExit('refusing to overwrite ' + str(args.out))
    args.out.mkdir(parents=True)
    result = {'measured_at': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'measured': {}, 'recorded': {},
              'not_run': {}}
    m = result['measured']

    # 1. Phase 1 harness, re-run now, versus the Phase 1 baseline file
    subprocess.run([PY, str(BASE / 'scripts/verification/phase_baseline.py'), '--label', 'final-phase08',
                    '--out', str(args.out / 'harness-final.json')], cwd=BASE, check=True, capture_output=True, timeout=900)
    before = json.loads((BASE / 'artifacts/jarvis-audit/phase-01/metrics-before.json').read_text(encoding='utf-8'))
    after = json.loads((args.out / 'harness-final.json').read_text(encoding='utf-8'))
    def pick(data):
        s = data['sections']
        return {'intent_routing_accuracy': s['intent_routing']['accuracy'], 'intent_routing_p50_ms': s['intent_routing']['routing_ms']['p50'],
                'privacy_private_marked_public': s['privacy_routing']['private_marked_public'],
                'privacy_classify_p50_ms': s['privacy_routing']['classify_ms']['p50'],
                'dag_success_rate': s['dag_execution']['success_rate'], 'dag_run_p50_ms': s['dag_execution']['run_ms']['p50'],
                'dag_cancel_return_ms': s['dag_execution']['cancellation']['returned_after_ms'],
                'tool_catalog_size': s['tool_registry']['catalog_size'], 'tool_search_p50_ms': s['tool_registry']['search_ms']['p50'],
                'tool_contract_error_rate': s['tool_registry']['contract_error_rate'],
                'skills_goals_with_selection': s['skills']['goals_with_selected_skill'], 'skills_context_p50_ms': s['skills']['context_ms']['p50'],
                'rss_end_mb': round(data['rss_bytes_end'] / 2 ** 20, 1)}
    m['phase1_harness'] = {'phase1_before': pick(before), 'final': pick(after),
                           'phase1_commit': before['git']['commit'], 'final_commit': after['git']['commit']}

    # 2. Simple deterministic command latency (parse only; nothing executes)
    from jarvis.commands import parse
    phrases = ['open notepad', 'play some jazz on spotify', 'pause the music', 'what time is it', 'read file notes.txt in project',
               'close chrome', 'volume up', 'search the web for python news', 'open my downloads folder', 'next track']
    m['command_parse'] = timed(lambda: [parse(p) for p in phrases], 50)
    m['command_parse']['per_command_p50_ms'] = round(m['command_parse']['p50_ms'] / len(phrases), 4)

    # 3. Tool selection: latency and held-out quality on the sealed Phase 6 benchmark
    from jarvis.tools import ToolRegistry
    from types import SimpleNamespace
    with tempfile.TemporaryDirectory() as folder:
        registry = ToolRegistry(SimpleNamespace(base=Path(folder), config={}, allowed_tools=None, skills=None,
                                                execute=lambda c, k: None, report=lambda *a: None))
        m['tool_search'] = timed(lambda: registry.search('put 42 into cell B3 of budget.xlsx'), 30)
    from evolution_eval.gate import RetentionGate
    gate = RetentionGate(BASE, BASE / 'evolution_eval')
    for name in ('tool_selection', 'lesson_retrieval', 'prompt_routing', 'retry_recovery'):
        run = gate.benchmark(BASE, name)
        m['heldout_' + name] = {'status': run['status'], 'mean': round(statistics.fmean(run['scores']), 4) if run.get('scores') else None,
                                'meta': run.get('meta')}

    # 4. Memory retrieval latency
    from jarvis.reasoning_bank import ReasoningBank
    with tempfile.TemporaryDirectory() as folder:
        bank = ReasoningBank(Path(folder), embedder=lambda *a: None)
        for index in range(40):
            bank._add({'kind': 'strategy', 'title': f'lesson {index}', 'description': 'benchmark',
                       'content': f'use adapter number {index} for workbook task {index % 7}', 'conditions': {}},
                      {'task_id': str(index)}, 'benchmark')
        m['reasoning_bank_lexical_retrieve'] = timed(lambda: bank.retrieve('workbook task adapter', k=3), 30)
    from jarvis.local_embeddings import embed
    if embed(['probe']) is not None:
        with tempfile.TemporaryDirectory() as folder:
            bank = ReasoningBank(Path(folder))
            for index in range(20):
                bank._add({'kind': 'strategy', 'title': f'lesson {index}', 'description': 'benchmark',
                           'content': f'use adapter number {index} for workbook task {index % 7}', 'conditions': {}},
                          {'task_id': str(index)}, 'benchmark')
            m['reasoning_bank_embedding_retrieve'] = timed(lambda: bank.retrieve('workbook task adapter', k=3), 10)
    else:
        result['not_run']['reasoning_bank_embedding_retrieve'] = 'local embedding model unavailable at measurement time'

    # 5. Prompt routing and AZR oracle cost
    from jarvis.prompt_router import route
    m['prompt_route'] = timed(lambda: [route(p) for p in phrases], 50)
    from jarvis.azr_tasks import abduction_task, check_abduction, render_target
    tasks = [abduction_task(seed) for seed in range(30)]
    m['azr_abduction_oracle'] = timed(lambda: [check_abduction(t, render_target(t)) for t in tasks], 5)

    # 6. Idle overhead of the self-evolution thread (real thread, synthetic actions, research disabled)
    code = ('import time,psutil,sys;sys.path.insert(0,r"%s");from types import SimpleNamespace;import tempfile;'
            'from jarvis.self_evolution import SelfEvolution;p=psutil.Process();'
            'a=SimpleNamespace(base=tempfile.mkdtemp(),config={"evolution_lab":{"enabled":False}});'
            's=SelfEvolution(a,{"enabled":True,"poll_seconds":1.0});c0=sum(p.cpu_times()[:2]);s.start();time.sleep(20);'
            's.close();c1=sum(p.cpu_times()[:2]);print(round((c1-c0)/20*100,3), round(p.memory_info().rss/2**20,1))') % BASE
    out = subprocess.run([PY, '-c', code], capture_output=True, text=True, timeout=120).stdout.split()
    m['idle_self_evolution'] = {'cpu_percent_of_one_core': float(out[0]), 'process_rss_mb': float(out[1]), 'window_s': 20,
                                'note': 'research disabled; resource probes and idle checks only'}

    # 7. Idle GPU memory (no training, no inference running)
    gpu = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.used,memory.total,utilization.gpu', '--format=csv,noheader'],
                         capture_output=True, text=True)
    m['gpu_idle'] = gpu.stdout.strip() or 'nvidia-smi unavailable'

    # 8. Real usage before the upgrade (categorical tool events only)
    events = BASE / '.jarvis-runtime' / 'agent-events.jsonl'
    if events.is_file():
        rows = [json.loads(line) for line in events.read_text(encoding='utf-8').splitlines() if line.strip()]
        started = sum(r.get('event') == 'tool.started' for r in rows)
        failed = sum(r.get('event') == 'tool.failed' for r in rows)
        stamps = sorted(r['at'] for r in rows if r.get('at'))
        result['recorded']['real_usage_before_upgrade'] = {'window': [stamps[0], stamps[-1]], 'tool_started': started,
                                                           'tool_failed': failed, 'failure_frequency': round(failed / started, 4) if started else None,
                                                           'source': '.jarvis-runtime/agent-events.jsonl (local, not committed)'}
    result['not_run']['real_usage_after_upgrade'] = 'Jarvis was not run interactively after the upgrade; no post-upgrade user traffic exists'
    result['recorded'].update({
        'voice_stt_capture': 'artifacts/jarvis-audit/modules/04-voice-stt/benchmark-summary.json (2026-10-15; fixture audio; WER BLOCKED)',
        'desktop_structured_vs_pointer': 'artifacts/jarvis-audit/phase-02 (structured UIA first; pointer last)',
        'openviking_search_p50_ms': 'artifacts/jarvis-audit/phase-04 (127 ms p50, real vault, 2026-10-18)',
        'demonstration_capture_replay': 'artifacts/jarvis-audit/phase-05/escalation-benchmark.json (3.9 s / 14.1 s)',
        'dag_makespan_proposal': 'artifacts/jarvis-audit/phase-06/experiments.md (synthetic DAGs, -15.2 %, not deployed)',
        'checkpoint_improvement': 'artifacts/jarvis-audit/phase-07 (0/165 -> 9/165 merged; qualified_experimental)',
        'training_resources': 'artifacts/jarvis-audit/phase-07 (peak 1,994 MB VRAM, 2.6 GB RSS, 9.6 min)',
        'resume_and_preemption': 'artifacts/jarvis-audit/phase-07/runs/experiment-record.json (exact resume, preempted at step 3)'})
    result['not_run'].update({
        'voice_to_action_latency': 'needs a live microphone session and the running app; not measured',
        'task_planning_latency_live_llm': 'needs the running brain worker with qwen3.5:9b; not measured in this phase',
        'coding_task_success_live': 'live coding agent runs not repeated; induction held-out accuracy recorded in Phase 7',
        'full_app_ram_vram': 'the full Jarvis UI was not launched; component RSS above only'})
    (args.out / 'final-benchmarks.json').write_text(json.dumps(result, indent=1), encoding='utf-8')
    print(json.dumps(result['measured'], indent=1)[:4000])


if __name__ == '__main__':
    main()
