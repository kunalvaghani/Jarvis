"""Phase 6 real experiments: autoresearch over Jarvis surfaces and EEVEE-style prompt co-evolution.

Everything runs for real against the committed Jarvis source: the isolated lab repository,
the sealed retention gate (held-out data, ten domain suites, paired repeats), and local
Ollama models for the prompt phase. Nothing is deployed; qualified candidates stay proposals.
Outputs go to --out (refuses to overwrite).
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import random
import shutil
import subprocess
import sys
import time

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    parser.add_argument('--solver', default='qwen3.5:0.8b')
    parser.add_argument('--reflector', default='qwen3.5:4b')
    args = parser.parse_args(argv)
    out = Path(args.out)
    if out.exists():
        raise SystemExit('Refusing to overwrite preserved experiment evidence: ' + str(out))
    out.mkdir(parents=True)
    from jarvis.autoresearch import AutoResearch
    from jarvis.prompt_evolution import PromptCoEvolution, ollama_reflector, ollama_solver
    from jarvis.prompt_router import ROUTER, SLOT_PROMPTS
    log_lines = []
    def log(message):
        line = datetime.now().strftime('%H:%M:%S ') + str(message)
        print(line, flush=True)
        log_lines.append(line)
        (out / 'experiment-log.txt').write_text('\n'.join(log_lines) + '\n', encoding='utf-8')
    research = AutoResearch(BASE, log=log)
    gate = research.gate
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=BASE, capture_output=True, text=True).stdout.strip()
    record = {'started_at': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'canonical_head': head,
              'evaluator_seal': gate.seal(), 'environment': {**gate.environment(), 'node': platform.node() and 'redacted'},
              'recovered': research.recover(), 'runs': {}}
    def timed(name, function):
        started = time.monotonic()
        log('start ' + name)
        try:
            result = function()
        except Exception as exc:
            result = {'error': type(exc).__name__ + ': ' + str(exc)[:500]}
        record['runs'][name] = {'seconds': round(time.monotonic() - started, 1), 'result': result}
        log(f'done {name} in {record["runs"][name]["seconds"]} s')
        (out / 'experiment-record.json').write_text(json.dumps(record, indent=1, default=str), encoding='utf-8')
        return result
    timed('diagnosis', research.diagnose)
    dag = timed('autoresearch_dag_scheduling', lambda: research.run_experiment('dag_scheduling', seed=601, max_proposals=2))
    timed('autoresearch_tool_ranking', lambda: research.run_experiment('tool_ranking', seed=602, max_proposals=4))
    timed('autoresearch_read_retry_backoff', lambda: research.run_experiment('read_retry_backoff', seed=603, max_proposals=4))
    timed('autoresearch_lesson_retrieval', lambda: research.run_experiment('lesson_retrieval', seed=604, max_proposals=3))
    evolution = PromptCoEvolution(research, solver=ollama_solver(args.solver), reflect=ollama_reflector(args.reflector),
                                  rng=random.Random(605))
    def router():
        best, score, history = evolution.router_phase(rounds=12)
        result = {'best': best, 'validation_score': score, 'history': history, 'changed': best != ROUTER}
        if best != ROUTER:
            result['gate'] = evolution.submit('prompt_router', best, 'EEVEE router phase: the evolved routing weights '
                                              'raise held-out slot accuracy by at least 2%.')
        return result
    timed('eevee_router_phase', router)
    def prompts():
        prompt, detail = evolution.prompt_phase('tool_selection', rounds=3)
        result = {'prompt': prompt, 'detail': detail, 'solver': args.solver, 'reflector': args.reflector}
        if prompt:
            values = dict(SLOT_PROMPTS)
            values['tool_selection'] = prompt
            result['gate'] = evolution.submit('prompt_slots', values, 'EEVEE prompt phase: the tool_selection slot prompt '
                                              'raises held-out local-model choice accuracy by at least 2%.')
        return result
    timed('eevee_prompt_phase_tool_selection', prompts)
    qualified = [r for r in research.archive.candidates(statuses=['qualified'])]
    def reproduce():
        rows = []
        for row in qualified:
            again = research.reevaluate(row['id'])
            first = row['gate']['checks']['target']
            second = again['checks'].get('target', {})
            rows.append({'candidate': row['id'], 'surface': row['surface'], 'first_decision': row['gate']['decision'],
                         'second_decision': again['decision'], 'first_relative_delta': first.get('relative_delta'),
                         'second_relative_delta': second.get('relative_delta'), 'first_ci95': first.get('ci95'),
                         'second_ci95': second.get('ci95')})
        return rows
    timed('reproducibility', reproduce)
    if any(p.get('decision') == 'qualified' for p in (dag or {}).get('proposals', [])):
        timed('autoresearch_dag_generation_2', lambda: research.run_experiment('dag_scheduling', seed=607, max_proposals=2))
    record['finished_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    record['archive_summary'] = research.archive.summary()
    candidates = research.archive.candidates()
    (out / 'candidates.json').write_text(json.dumps(candidates, indent=1, default=str), encoding='utf-8')
    (out / 'experiment-record.json').write_text(json.dumps(record, indent=1, default=str), encoding='utf-8')
    if research.results.exists():
        shutil.copy(research.results, out / 'results.tsv')
    lineage = {r['id']: [a['id'] for a in research.archive.lineage(r['id'])] for r in candidates}
    (out / 'lineage.json').write_text(json.dumps(lineage, indent=1), encoding='utf-8')
    log('lab branches: ' + ', '.join(research.lab.branches()))
    print(json.dumps(record['archive_summary'], indent=1))


if __name__ == '__main__':
    main()
