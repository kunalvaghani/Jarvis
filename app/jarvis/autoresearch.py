"""Autoresearch experiment loop over bounded Jarvis surfaces (Pillar C, Part B).

Adapted from karpathy/autoresearch (MIT): one falsifiable change per experiment, a fixed
budget, a read-only evaluation that the experimenter cannot edit, a results log, and a
keep-or-discard decision. No upstream code is copied. Each experiment:

 1. reads verified performance (train-split benchmarks) and verified failures (agent events);
 2. picks one measurable bottleneck surface;
 3. selects a parent from the DGM archive (score x 1/(1+children), seeded);
 4. states a falsifiable hypothesis with a predicted effect;
 5. builds one bounded surface mutation as a commit in the isolated lab repository;
 6. runs static checks and the target domain's unit tests;
 7. pre-screens on the train split with a fixed budget, then hands the candidate to the
    sealed retention gate (held-out data, all domains, paired repeats);
 8. compares against the parent and the approved baseline;
 9. records results, seeds and environment in the archive and ``results.tsv``;
10. keeps the candidate as a proposal or discards it. Production files are never written.
"""
import json
import math
from pathlib import Path
import random
import statistics
import sys
import time
import uuid

from .evolution_archive import EvolutionArchive
from .evolution_lab import ExperimentLab
from .evolution_surfaces import SURFACES, digest, distance, extract, validate

RESULTS_HEADER = 'when\trun\tcandidate\tlab_commit\tsurface\thypothesis\ttrain_parent\ttrain_child\tdecision\treason\n'
DEFAULT_SURFACES = ('dag_scheduling', 'tool_ranking', 'lesson_retrieval', 'percept_salience', 'read_retry_backoff', 'prompt_router')


class ExperimentCancelled(RuntimeError):
    pass


def _gate_class():
    base = Path(__file__).resolve().parents[1]
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))
    from evolution_eval.gate import RetentionGate
    return RetentionGate


class AutoResearch:
    def __init__(self, base, archive=None, lab=None, gate=None, log=None, surfaces=DEFAULT_SURFACES, now=time.time):
        self.base = Path(base).resolve()
        self.root = self.base / '.jarvis-runtime' / 'evolution'
        self.archive = archive or EvolutionArchive(self.root / 'archive.sqlite3')
        self.lab = lab or ExperimentLab(self.base)
        self.gate = gate or _gate_class()(self.base, self.base / 'evolution_eval')
        self.log = log or (lambda message: None)
        self.surfaces = tuple(surfaces)
        self.results = self.root / 'results.tsv'
        self.now = now

    # ---- archive seeds -----------------------------------------------------------------------------------------------
    def seed(self, surface):
        """The approved baseline (current canonical HEAD) as the root of the surface's lineage."""
        lab_commit, source_commit = self.lab.snapshot()
        for row in self.archive.candidates(surface, ['seed']):
            if row['source_commit'] == source_commit:
                return row
        values = extract(self.lab.read(lab_commit, SURFACES[surface]['file']), surface)
        identifier = self.archive.add(surface, values, digest(values), source_commit, status='seed',
                                      hypothesis='Approved baseline at canonical ' + source_commit[:12],
                                      environment=self.gate.environment())
        self.archive.update(identifier, lab_commit=lab_commit)
        return self.archive.get(identifier)

    # ---- 1-2: evidence and bottleneck --------------------------------------------------------------------------------
    def train_score(self, root, surface, cancelled=lambda: False):
        """Fixed-budget train-split score (higher is better), averaged over the policy's repeats for noisy timing."""
        spec = SURFACES[surface]
        repeats = self.gate.policy['benchmarks'].get(spec['benchmark'], {}).get('repeats', 1)
        means = []
        for _ in range(repeats):
            result = self.gate.benchmark(root, spec['benchmark'], split='train', cancelled=cancelled)
            if result['status'] != 'ok':
                return None, result
            means.append(statistics.fmean(result['scores']))
        mean = statistics.fmean(means)
        return (-mean if spec['objective'] == 'min' else mean), result

    def headroom(self, surface, score):
        """How far the train score is from the best attainable value (0 none, 1 large)."""
        spec = SURFACES[surface]
        if score is None:
            return 0.
        if spec['objective'] == 'max':
            return max(0., 1. - score)
        cases = self.gate.data(spec['benchmark'], 'train')['cases']
        bound = statistics.fmean(self.critical_path_ms(case) for case in cases)
        return max(0., (-score - bound) / -score)

    @staticmethod
    def critical_path_ms(case):
        steps = {s['id']: s for s in case['steps']}
        memo = {}
        def longest(identifier):
            if identifier not in memo:
                memo[identifier] = steps[identifier]['ms'] + max((longest(d) for d in steps[identifier]['deps']), default=0)
            return memo[identifier]
        return max(longest(i) for i in steps)

    def failure_weights(self):
        """Verified failure counts per domain from categorical tool outcomes (never raw logs)."""
        path = self.base / '.jarvis-runtime' / 'agent-events.jsonl'
        domains = {'dag_planning': 0, 'skill_registry': 0, 'memory': 0, 'voice_routing': 0, 'recovery': 0, 'prompt_routing': 0}
        try:
            lines = path.read_text(encoding='utf-8', errors='replace').splitlines()[-5000:]
        except OSError:
            return domains
        for line in lines:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get('kind') != 'tool.outcome' or row.get('status') not in {'failed', 'unverified'}:
                continue
            category = str(row.get('category', ''))
            if category in {'invalid_arguments', 'unavailable'}:
                domains['skill_registry'] += 1
            elif category == 'failed':
                domains['recovery'] += 1
        return domains

    def diagnose(self, cancelled=lambda: False):
        failures = self.failure_weights()
        rows = []
        for surface in self.surfaces:
            if cancelled():
                raise ExperimentCancelled('cancelled during diagnosis')
            seed = self.seed(surface)
            score, raw = self.train_score(self.base, surface, cancelled)
            if score is not None and not (seed.get('fitness') or {}).get('train_score'):
                self.archive.update(seed['id'], fitness={'train_score': score})
            room = self.headroom(surface, score)
            weight = 1 + math.log1p(failures.get(SURFACES[surface]['domain'], 0))
            rows.append({'surface': surface, 'train_score': score, 'headroom': round(room, 4),
                         'failure_weight': round(weight, 3), 'priority': round(room * weight, 4),
                         'status': raw['status']})
        rows.sort(key=lambda r: -r['priority'])
        return rows

    # ---- 4-5: hypothesis and mutation --------------------------------------------------------------------------------
    def hypothesis(self, surface, parent, rng):
        values = dict(parent['values'])
        bounds = SURFACES[surface]['bounds']
        bench = SURFACES[surface]['benchmark']
        if surface == 'dag_scheduling' and values['critical_path_weight'] == 0:
            values['critical_path_weight'] = 1.0
            return values, 'directed', ('Admitting ready steps with longer downstream chains first will lower ' + bench +
                                        ' makespan by at least 2% (falsified if the paired 95% CI includes zero).')
        numeric = [k for k, b in bounds.items() if b[0] is not str]
        key = rng.choice(numeric)
        kind, low, high = bounds[key]
        if kind is int:
            new = min(high, max(low, values[key] + rng.choice([-1, 1])))
        else:
            step = (high - low) * rng.choice([.05, .1, .2]) * rng.choice([-1, 1])
            new = round(min(high, max(low, values[key] + step)), 4)
        if new == values[key]:
            new = min(high, max(low, values[key] - (step if kind is float else rng.choice([-1, 1]))))
        values[key] = new
        validate(surface, values)
        return values, 'perturbation', (f'Changing {key} from {parent["values"][key]!r} to {new!r} will improve {bench} '
                                        'by at least 2% on held-out data (falsified if the paired 95% CI includes zero).')

    # ---- the experiment ----------------------------------------------------------------------------------------------
    def run_experiment(self, surface=None, cancelled=lambda: False, seed=None, max_proposals=3, budget_seconds=2400):
        started = self.now()
        run_id = 'run_' + uuid.uuid4().hex[:10]
        seed = int(seed if seed is not None else self.now() * 1000) % 2 ** 31
        rng = random.Random(seed)
        record = {'run': run_id, 'seed': seed, 'proposals': []}
        def checkpoint(stage, candidate=None, finished=False):
            self.archive.checkpoint(run_id, stage, record, candidate, finished)
        def over_budget():
            return cancelled() or self.now() - started > budget_seconds
        checkpoint('diagnose')
        try:
            diagnosis = self.diagnose(over_budget)
        except ExperimentCancelled:
            record['stopped'] = 'cancelled during diagnosis'
            checkpoint('cancelled', finished=True)
            return record
        record['diagnosis'] = diagnosis
        surface = surface or next((r['surface'] for r in diagnosis if r['priority'] > 0), diagnosis[0]['surface'])
        record['surface'] = surface
        self.seed(surface)
        for attempt in range(max_proposals):
            if over_budget():
                record['stopped'] = 'budget or cancellation'
                break
            checkpoint('select_parent')
            parent = self.archive.select_parent(surface, rng, 'train_score')
            values, kind, statement = self.hypothesis(surface, parent, rng)
            spread = self.archive.diversity(surface, values, distance)
            if spread == 0:
                record['proposals'].append({'duplicate_of_archived_variant': values})
                continue
            identifier = self.archive.add(surface, values, digest(values), parent['source_commit'], parent['id'], kind,
                                          {'from': parent['values'], 'to': values, 'rng_seed': seed, 'attempt': attempt},
                                          [SURFACES[surface]['file']], statement, 'running', seed, self.gate.environment())
            self.archive.update(identifier, diversity=round(spread, 6))
            checkpoint('mutate', identifier)
            outcome = self.evaluate_candidate(identifier, parent, over_budget, checkpoint)
            record['proposals'].append(outcome)
            if outcome['decision'] == 'qualified':
                break
        checkpoint('finished', finished=True)
        record['seconds'] = round(self.now() - started, 1)
        return record

    def evaluate_candidate(self, identifier, parent, cancelled, checkpoint=lambda *a, **k: None):
        row = self.archive.get(identifier)
        surface = row['surface']
        lab_commit = self.lab.create_candidate(identifier, parent['lab_commit'], surface, row['values'],
                                               f'{surface}: {row["mutation_type"]} {identifier}')
        self.archive.update(identifier, lab_commit=lab_commit)
        checkpoint('static_checks', identifier)
        child = self.lab.worktree(identifier, lab_commit)
        parent_tree = self.lab.worktree(identifier + '-parent', parent['lab_commit'])
        baseline = None
        try:
            import py_compile
            py_compile.compile(str(child / SURFACES[surface]['file']), doraise=True,
                               cfile=str(self.root / 'pycache-check.pyc'))
            checkpoint('unit_tests', identifier)
            domain = SURFACES[surface]['domain']  # target-domain unit tests before the full gate (fail fast)
            quick = self.gate.domain_tests(child, domain if domain in self.gate.policy['domains'] else 'voice_routing',
                                           cancelled)
            if not quick['passed']:
                return self._decide(row, parent, 'rejected', 'target domain unit tests failed: ' + quick['summary'],
                                    None, None, {'unit_tests': quick})
            checkpoint('train_prescreen', identifier)
            parent_score, _ = self.train_score(parent_tree, surface, cancelled)
            child_score, raw = self.train_score(child, surface, cancelled)
            if child_score is None:
                status = 'quarantined' if raw['status'] == 'resource_exhausted' else (
                    'interrupted' if raw['status'] == 'cancelled' else 'rejected')
                return self._decide(row, parent, status, 'train benchmark ' + raw['status'], parent_score, None, {})
            if parent_score is not None and child_score <= parent_score:
                return self._decide(row, parent, 'discarded', 'no train-split improvement', parent_score, child_score, {})
            checkpoint('gate', identifier)
            seeds = [r for r in self.archive.candidates(surface, ['seed']) if r['source_commit'] == row['source_commit']]
            if seeds and seeds[0]['lab_commit'] != parent['lab_commit']:
                baseline = self.lab.worktree(identifier + '-baseline', seeds[0]['lab_commit'])
            report = self.gate.evaluate(surface, parent_tree, child, baseline, cancelled,
                                        stage=lambda name: checkpoint('gate:' + name, identifier))
            return self._decide(row, parent, report['decision'], report['reason'], parent_score, child_score, report)
        except Exception as exc:  # a broken candidate must never break Jarvis
            return self._decide(row, parent, 'rejected', 'experiment error: ' + type(exc).__name__ + ': ' + str(exc)[:200],
                                None, None, {})
        finally:
            for path in (child, parent_tree, baseline):
                if path is not None:
                    self.lab.remove_worktree(path)

    def _decide(self, row, parent, decision, reason, parent_score, child_score, report):
        status = {'qualified': 'qualified', 'discarded': 'discarded', 'rejected': 'rejected', 'quarantined': 'quarantined',
                  'interrupted': 'interrupted', 'refused': 'rejected'}.get(decision, 'rejected')
        fitness = {'train_score': child_score, 'parent_train_score': parent_score}
        target = (report or {}).get('checks', {}).get('target') or {}
        if target.get('status') == 'ok':
            fitness.update(heldout_relative_delta=target['relative_delta'], heldout_ci95=target['ci95'])
        self.archive.update(row['id'], status=status, failure_reason=None if status == 'qualified' else reason,
                            fitness=fitness, gate=report or None)
        if status == 'discarded' and child_score is not None:
            front = self.archive.pareto_front(row['surface'], {'train_score': 'max'})
            if any(r['id'] == row['id'] for r in front):
                self.archive.update(row['id'], status='retained')  # useful non-winning variant kept as a parent
                status = 'retained'
        self._results(row, decision, reason, parent_score, child_score)
        self.log(f"{row['surface']} {row['id']}: {decision} ({reason})")
        return {'candidate': row['id'], 'decision': decision, 'status': status, 'reason': reason,
                'train_parent': parent_score, 'train_child': child_score, 'hypothesis': row['hypothesis']}

    def _results(self, row, decision, reason, parent_score, child_score):
        self.results.parent.mkdir(parents=True, exist_ok=True)
        new = not self.results.exists()
        with self.results.open('a', encoding='utf-8') as handle:
            if new:
                handle.write(RESULTS_HEADER)
            fresh = self.archive.get(row['id'])
            fields = [time.strftime('%Y-%m-%dT%H:%M:%S'), '', row['id'], (fresh.get('lab_commit') or '')[:7], row['surface'],
                      row['hypothesis'], '' if parent_score is None else f'{parent_score:.6f}',
                      '' if child_score is None else f'{child_score:.6f}', decision, reason]
            handle.write('\t'.join(str(f).replace('\t', ' ').replace('\n', ' ')[:300] for f in fields) + '\n')

    # ---- recovery and reproducibility --------------------------------------------------------------------------------
    def recover(self):
        """After a crash: mark interrupted candidates, drop stale lab worktrees, close unfinished runs."""
        recovered = []
        for run in self.archive.unfinished_runs():
            candidate = run.get('candidate_id')
            if candidate:
                row = self.archive.get(candidate)
                if row and row['status'] == 'running':
                    self.archive.update(candidate, status='interrupted', failure_reason='interrupted at ' + run['stage'])
                    recovered.append(candidate)
            self.archive.checkpoint(run['id'], 'recovered:' + run['stage'], run['state'], candidate, finished=True)
        self.lab.cleanup()
        return recovered

    def reevaluate(self, identifier, cancelled=lambda: False):
        """Re-run the gate on an archived candidate (its lab commit is immutable) for reproducibility."""
        row = self.archive.get(identifier)
        parent = self.archive.get(row['parent_id'])
        child = self.lab.worktree(identifier + '-re', row['lab_commit'])
        parent_tree = self.lab.worktree(identifier + '-re-parent', parent['lab_commit'])
        try:
            return self.gate.evaluate(row['surface'], parent_tree, child, None, cancelled)
        finally:
            self.lab.remove_worktree(child)
            self.lab.remove_worktree(parent_tree)
