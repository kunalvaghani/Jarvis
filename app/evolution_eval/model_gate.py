"""Held-out retention gate for trained checkpoints (Pillar C gate applied to Pillar D models).

Like the source-candidate gate, it refuses to run unless the evaluator (including the sealed AZR
held-out tasks) equals the committed files. It does not accept answer files: it generates answers
for the approved base model and for the candidate adapter itself (greedy decoding, bounded
process), scores both with the independent oracle, and compares them pairwise per task with a
seeded bootstrap. A checkpoint qualifies only as *experimental* and only with a significant
overall gain, no significant regression in any mode, and latency/VRAM within budget.
"""
import json
from pathlib import Path
import statistics
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from gate import RetentionGate, EvaluatorUnsealed
    from process import minimal_env, run_bounded
    from stats import paired
else:
    from .gate import RetentionGate, EvaluatorUnsealed
    from .process import minimal_env, run_bounded
    from .stats import paired

MODES = ('deduction', 'abduction', 'induction')


def wilson(successes, total, z=1.96):
    if not total:
        return [0.0, 0.0]
    p = successes / total
    centre = (p + z * z / (2 * total)) / (1 + z * z / total)
    margin = z * ((p * (1 - p) / total + z * z / (4 * total * total)) ** .5) / (1 + z * z / total)
    return [round(max(0., centre - margin), 4), round(min(1., centre + margin), 4)]


class ModelGate:
    def __init__(self, app_root, evaluator_dir=None, training_python=None):
        self.app = Path(app_root).resolve()
        self.retention = RetentionGate(self.app, evaluator_dir or self.app / 'evolution_eval')
        self.policy = self.retention.policy['model_gate']
        self.training_python = Path(training_python or self.app / '.venv-training' / 'Scripts' / 'python.exe')

    def tasks(self):
        path = self.retention.dir / self.policy['heldout']
        return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]

    def generate(self, label, out_dir, adapter=None, merged=None, cancelled=lambda: False):
        out = Path(out_dir) / (label + '.answers.jsonl')
        command = [str(self.training_python), '-m', 'scripts.training.azr_generate', '--tasks',
                   str(self.retention.dir / self.policy['heldout']), '--out', str(out)]
        if adapter:
            command += ['--adapter', str(adapter)]
        if merged:
            command += ['--merged', str(merged)]
        run = run_bounded(command, self.app, self.policy['generation_timeout'], self.policy['generation_rss_mb'], cancelled,
                          env=minimal_env({'PYTHONPATH': str(self.app)}))
        if run['status'] != 'completed' or run['returncode'] != 0:
            raise RuntimeError(label + ' generation ' + run['status'] + ': ' + (run['stderr'] or run['stdout'])[-500:])
        answers = {}
        for line in out.read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            answers[row['id']] = row
        summary = json.loads(out.with_suffix('.summary.json').read_text(encoding='utf-8'))
        return answers, summary

    def score(self, tasks, answers):
        sys.path.insert(0, str(self.app))
        from jarvis.azr_reward import score_all
        from jarvis.azr_sandbox import run_programs
        rows = [{'key': t['id'], 'task': t['task'], 'answer': answers[t['id']]['answer']} for t in tasks]
        return score_all(self.app, rows, run_programs)

    def summarize(self, tasks, scores, answers, summary):
        report = {'peak_vram_mb': summary['peak_vram_mb'], 'seconds': summary['seconds']}
        per_task = [answers[t['id']]['batch_seconds'] / answers[t['id']]['batch_size'] for t in tasks]
        report['seconds_per_task_p50'] = round(statistics.median(per_task), 4)
        for mode in MODES:
            ids = [t['id'] for t in tasks if t['task']['mode'] == mode]
            correct = sum(scores[i]['correct'] for i in ids)
            report[mode] = {'correct': correct, 'total': len(ids), 'accuracy': round(correct / len(ids), 4) if ids else None,
                            'wilson95': wilson(correct, len(ids)),
                            'format_ok': sum(scores[i]['format_ok'] for i in ids),
                            'mean_reward': round(statistics.fmean(scores[i]['reward'] for i in ids), 4) if ids else None}
            if mode == 'induction':
                report[mode]['visible_only'] = sum(scores[i].get('reason') == 'visible_only' for i in ids)
        correct = sum(s['correct'] for s in scores.values())
        report['overall'] = {'correct': correct, 'total': len(scores), 'accuracy': round(correct / len(scores), 4),
                             'wilson95': wilson(correct, len(scores))}
        return report

    def evaluate(self, adapter, out_dir, base_cache=None, cancelled=lambda: False):
        result = {'adapter': str(adapter), 'environment': self.retention.environment()}
        try:
            result['seal'] = self.retention.seal()
        except EvaluatorUnsealed as exc:
            return {**result, 'decision': 'refused', 'reason': 'evaluator_unsealed: ' + str(exc)}
        tasks = self.tasks()
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        if base_cache and Path(base_cache).is_file():
            base = json.loads(Path(base_cache).read_text(encoding='utf-8'))
            if base.get('seal') != result['seal']:
                base = None
        else:
            base = None
        if base is None:
            answers, summary = self.generate('base', out_dir, cancelled=cancelled)
            scores = self.score(tasks, answers)
            base = {'seal': result['seal'], 'scores': scores, 'summary': self.summarize(tasks, scores, answers, summary)}
            if base_cache:
                Path(base_cache).write_text(json.dumps(base), encoding='utf-8')
        answers, summary = self.generate('candidate', out_dir, adapter=adapter, cancelled=cancelled)
        scores = self.score(tasks, answers)
        candidate = self.summarize(tasks, scores, answers, summary)
        result.update(base=base['summary'], candidate=candidate)
        p = self.policy
        comparisons = {}
        for mode in (*MODES, 'overall'):
            ids = [t['id'] for t in tasks if mode == 'overall' or t['task']['mode'] == mode]
            comparisons[mode] = paired([[float(base['scores'][i]['correct'])] for i in ids],
                                       [[float(scores[i]['correct'])] for i in ids], 'max', p['bootstrap_seed'], 2000)
        result['comparisons'] = comparisons
        overall = comparisons['overall']
        regressions = [m for m in MODES if comparisons[m]['mean_delta'] < -p['max_mode_regression'] and comparisons[m]['ci95'][1] < 0]
        budget = []
        if candidate['seconds_per_task_p50'] > p['max_latency_ratio'] * result['base']['seconds_per_task_p50']:
            budget.append('latency')
        if candidate['peak_vram_mb'] > p['vram_limit_mb']:
            budget.append('vram')
        if regressions:
            decision, reason = 'rejected', 'mode regression: ' + ', '.join(regressions)
        elif budget:
            decision, reason = 'rejected', 'budget exceeded: ' + ', '.join(budget)
        elif overall['mean_delta'] >= p['min_absolute_improvement'] and overall['ci95'][0] > 0:
            decision, reason = 'qualified_experimental', 'significant held-out gain with no mode regression'
        else:
            decision, reason = 'not_improved', 'no significant held-out gain'
        result.update(decision=decision, reason=reason)
        return result
