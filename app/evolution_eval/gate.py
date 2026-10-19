"""Independent multi-domain retention gate for evolution candidates (Pillar C, Part D).

The gate lives outside ``jarvis/`` and outside every candidate workspace. It refuses to run
unless its own files (code, policy and held-out data) match the committed HEAD of the
canonical repository, so neither a candidate nor an uncommitted edit can change tests,
expected results, thresholds or permissions. For each candidate it checks, in order:

1. integrity: the child tree differs from its parent only in the declared surface literal,
   with values inside the evaluator's own bounds (checked with ``ast``; nothing is imported);
2. the target benchmark on the held-out split, paired against the parent (and the approved
   baseline), repeated, with a seeded bootstrap interval; one lucky result cannot qualify;
3. all ten domain suites (security domains are hard PASS) and every other benchmark for
   regressions;
4. the child tree is unchanged after its tests ran.

A qualified candidate becomes a proposal only; the gate never deploys anything.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from process import minimal_env, run_bounded
    from stats import paired
else:
    from .process import minimal_env, run_bounded
    from .stats import paired

SKIP_DIRS = {'__pycache__', '.pytest_cache', '.jarvis-runtime', '.git', 'JarvisFiles', '.venv'}


class EvaluatorUnsealed(RuntimeError):
    pass


def tree_hashes(root):
    root = Path(root)
    result = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if name.endswith('.pyc') or name == '.git':  # a worktree's .git is a per-checkout pointer file
                continue
            path = Path(dirpath) / name
            result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def tree_digest(hashes):
    return hashlib.sha256(json.dumps(sorted(hashes.items())).encode()).hexdigest()


def _surface_node(tree, symbol):
    found = [n for n in tree.body if isinstance(n, ast.Assign) and len(n.targets) == 1
             and isinstance(n.targets[0], ast.Name) and n.targets[0].id == symbol and isinstance(n.value, ast.Dict)]
    if len(found) != 1:
        raise ValueError('surface symbol is not exactly one module-level dict literal')
    return found[0]


def literal_only_change(parent_source, child_source, spec):
    """Independent re-implementation of the surface rule (does not trust the mutation worker)."""
    parent, child = ast.parse(parent_source), ast.parse(child_source)
    values = ast.literal_eval(_surface_node(child, spec['symbol']).value)
    for tree in (parent, child):
        _surface_node(tree, spec['symbol']).value = ast.Dict(keys=[], values=[])
    if ast.dump(parent) != ast.dump(child):
        raise ValueError('code outside the surface literal changed')
    if set(values) != set(spec['bounds']):
        raise ValueError('surface keys changed')
    for key, bound in spec['bounds'].items():
        value = values[key]
        if bound[0] == 'str':
            if not isinstance(value, str) or len(value) > bound[1] or not value.isascii():
                raise ValueError('prompt text out of bounds: ' + key)
        elif (bound[0] == 'int' and type(value) is not int) or (bound[0] == 'float' and type(value) not in (int, float)) \
                or not bound[1] <= value <= bound[2]:
            raise ValueError(f'{key}={value!r} outside evaluator bounds')
    return values


class RetentionGate:
    def __init__(self, canonical_root, evaluator_dir=None, python=None, log=None):
        self.dir = Path(evaluator_dir or Path(__file__).resolve().parent).resolve()
        self.canonical = Path(canonical_root).resolve()
        self.python = python or sys.executable
        self.log = log or (lambda message: None)
        self.policy = json.loads((self.dir / 'policy.json').read_text(encoding='utf-8'))

    # ---- sealing -----------------------------------------------------------------------------------------------------
    def _git(self, *args, stdin=None):
        # Read-only queries keep the repository's normal config so hash-object applies the same line-ending
        # conversion a commit would; nothing here writes to the repository.
        result = subprocess.run(['git', *args], cwd=self.canonical, capture_output=True, text=True, input=stdin, timeout=60,
                                env=minimal_env({'GIT_TERMINAL_PROMPT': '0'}))
        if result.returncode:
            raise EvaluatorUnsealed('git ' + args[0] + ' failed: ' + result.stderr.strip()[:200])
        return result.stdout

    def seal(self):
        """Every evaluator file must equal its committed blob; returns the seal digest."""
        top = Path(self._git('rev-parse', '--show-toplevel').strip()).resolve()
        relative = self.dir.relative_to(top).as_posix()
        committed = {}
        for line in self._git('ls-tree', '--full-tree', '-r', 'HEAD', '--', relative).splitlines():
            meta, path = line.split('\t', 1)
            committed[path] = meta.split()[2]
        local = sorted(p.relative_to(top).as_posix() for p in self.dir.rglob('*')
                       if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
        if not committed or set(local) != set(committed):
            raise EvaluatorUnsealed('Evaluator files differ from the committed set: ' +
                                    ', '.join(sorted(set(local) ^ set(committed)))[:300])
        # Absolute paths: hash-object applies the same clean filters (line endings) as a commit would.
        hashes = self._git('hash-object', '--stdin-paths', stdin='\n'.join(str(top / p) for p in local) + '\n').split()
        changed = [path for path, digest in zip(local, hashes) if committed[path] != digest]
        if changed:
            raise EvaluatorUnsealed('Evaluator files modified since commit: ' + ', '.join(changed)[:300])
        # The seal covers the evaluator's own committed blobs, so unrelated commits do not invalidate it.
        return hashlib.sha256(json.dumps(sorted(committed.items())).encode()).hexdigest()

    # ---- running -----------------------------------------------------------------------------------------------------
    def data(self, benchmark, split='heldout'):
        return json.loads((self.dir / split / (benchmark + '.json')).read_text(encoding='utf-8'))

    def benchmark(self, root, benchmark, split='heldout', cancelled=lambda: False):
        spec = self.policy['benchmarks'][benchmark]
        request = json.dumps({'benchmark': benchmark, 'data': self.data(benchmark, split)})
        run = run_bounded([self.python, '-I', '-B', str(self.dir / 'runner.py'), str(root)], root, spec['timeout'],
                          self.policy['limits']['benchmark_rss_mb'], cancelled, request)
        if run['status'] != 'completed' or run['returncode'] != 0:
            return {'status': run['status'] if run['status'] != 'completed' else 'error',
                    'detail': (run['stderr'] or run['stdout'])[-600:], 'peak_rss_mb': run['peak_rss_mb']}
        result = json.loads(run['stdout'].strip().splitlines()[-1])
        return {'status': 'ok', 'scores': result['scores'], 'meta': result['meta'], 'imported_from': result['imported_from'],
                'seconds': run['seconds'], 'peak_rss_mb': run['peak_rss_mb']}

    def compare(self, parent_root, child_root, benchmark, repeats, cancelled=lambda: False):
        """Interleaved repeats (parent/child order alternates) to cancel slow drift; returns stats or a failure."""
        parent_runs, child_runs = [], []
        for repeat in range(repeats):
            order = [('parent', parent_root), ('child', child_root)]
            for side, root in (order if repeat % 2 == 0 else order[::-1]):
                result = self.benchmark(root, benchmark, cancelled=cancelled)
                if result['status'] != 'ok':
                    return {'status': result['status'], 'side': side, 'detail': result.get('detail', ''),
                            'peak_rss_mb': result.get('peak_rss_mb')}
                (parent_runs if side == 'parent' else child_runs).append(result['scores'])
        objective = self.policy['benchmarks'][benchmark]['objective']
        t = self.policy['thresholds']
        stats = paired([list(v) for v in zip(*parent_runs)], [list(v) for v in zip(*child_runs)], objective,
                       t['bootstrap_seed'], t['bootstrap_resamples'])
        return {'status': 'ok', **stats}

    def domain_tests(self, root, name, cancelled=lambda: False):
        spec = self.policy['domains'][name]
        command = [self.python, '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider', *spec['tests']]
        if spec.get('select'):
            command += ['-k', spec['select']]
        for row in spec.get('deselect', []):
            command += ['--deselect', row['node']]
        run = run_bounded(command, root, self.policy['limits']['test_timeout'], self.policy['limits']['test_rss_mb'], cancelled)
        tail = (run['stdout'] or '').strip().splitlines()[-1:] or ['']
        return {'domain': name, 'status': run['status'], 'passed': run['status'] == 'completed' and run['returncode'] == 0,
                'returncode': run['returncode'], 'summary': tail[0][-200:], 'seconds': run['seconds'],
                'peak_rss_mb': run['peak_rss_mb'], 'security': bool(spec.get('security'))}

    def environment(self):
        return {'python': platform.python_version(), 'implementation': platform.python_implementation(),
                'platform': platform.platform(), 'machine': platform.machine(), 'cpu_count': os.cpu_count(),
                'executable': Path(self.python).name}

    # ---- the gate ----------------------------------------------------------------------------------------------------
    def evaluate(self, surface, parent_root, child_root, baseline_root=None, cancelled=lambda: False, stage=None):
        stage = stage or (lambda name: None)
        report = {'surface': surface, 'environment': self.environment(), 'checks': {}}
        def finish(decision, reason):
            report.update(decision=decision, reason=reason)
            report['receipt'] = hashlib.sha256(json.dumps(
                [report.get('seal'), report.get('child_tree'), report.get('parent_tree'), surface, decision],
                sort_keys=True).encode()).hexdigest()
            return report
        try:
            report['seal'] = self.seal()
        except EvaluatorUnsealed as exc:
            return finish('refused', 'evaluator_unsealed: ' + str(exc))
        spec = self.policy['surfaces'].get(surface)
        if spec is None:
            return finish('quarantined', 'unknown surface')
        stage('integrity')
        parent_hashes, child_hashes = tree_hashes(parent_root), tree_hashes(child_root)
        report['parent_tree'], report['child_tree'] = tree_digest(parent_hashes), tree_digest(child_hashes)
        changed = sorted(p for p in set(parent_hashes) | set(child_hashes) if parent_hashes.get(p) != child_hashes.get(p))
        report['checks']['changed_files'] = changed
        if changed != [spec['file']]:
            return finish('quarantined', 'integrity: changed files must be exactly the surface file; got ' + ', '.join(changed)[:300])
        try:
            values = literal_only_change((Path(parent_root) / spec['file']).read_text(encoding='utf-8'),
                                         (Path(child_root) / spec['file']).read_text(encoding='utf-8'), spec)
        except (ValueError, SyntaxError) as exc:
            return finish('quarantined', 'integrity: ' + str(exc)[:300])
        report['values'] = values
        if cancelled():
            return finish('interrupted', 'cancelled')
        stage('target_benchmark')
        target = spec['benchmark']
        bench = self.policy['benchmarks'][target]
        repeats = max(bench['repeats'], self.policy['thresholds']['deterministic_repeat_check'])
        result = self.compare(parent_root, child_root, target, repeats, cancelled)
        report['checks']['target'] = {'benchmark': target, **result}
        t = self.policy['thresholds']
        if result['status'] == 'resource_exhausted':
            return finish('quarantined', 'resource_exhausted during target benchmark')
        if result['status'] == 'cancelled':
            return finish('interrupted', 'cancelled')
        if result['status'] != 'ok':
            return finish('rejected', 'target benchmark failed: ' + result['status'])
        if not bench.get('timing', False) and not result['deterministic']:
            # A computed (non-timing) metric must reproduce exactly; if repeats disagree, no result from it can be
            # trusted, however lucky. Timing benchmarks are noisy by nature and are judged statistically below.
            return finish('discarded', 'nondeterministic result for a deterministic benchmark')
        improved = (result['relative_delta'] is not None and result['relative_delta'] >= t['min_relative_improvement']
                    and result['ci95'][0] > t['ci_lower_must_exceed'])
        if not improved:
            why = 'nondeterministic and not significant' if not result['deterministic'] else 'no significant improvement'
            return finish('discarded', why)
        if baseline_root and Path(baseline_root).resolve() != Path(parent_root).resolve():
            stage('baseline_benchmark')
            versus = self.compare(baseline_root, child_root, target, repeats, cancelled)
            report['checks']['versus_baseline'] = versus
            if versus['status'] != 'ok' or versus['ci95'][0] <= t['ci_lower_must_exceed']:
                return finish('discarded', 'not better than the approved baseline')
        stage('domain_tests')
        domains = []
        for name in self.policy['domains']:
            if cancelled():
                return finish('interrupted', 'cancelled')
            outcome = self.domain_tests(child_root, name, cancelled)
            domains.append(outcome)
            self.log(f"domain {name}: {outcome['summary']}")
            if outcome['status'] == 'resource_exhausted':
                report['checks']['domains'] = domains
                return finish('quarantined', 'resource_exhausted in domain ' + name)
        report['checks']['domains'] = domains
        failed = [d for d in domains if not d['passed']]
        if any(d['security'] for d in failed):
            return finish('quarantined', 'security invariant failed: ' + ', '.join(d['domain'] for d in failed if d['security']))
        if failed:
            return finish('rejected', 'domain regression: ' + ', '.join(d['domain'] for d in failed))
        stage('regression_benchmarks')
        regressions, others = [], {}
        for name, bench in self.policy['benchmarks'].items():
            if name == target or bench.get('requires'):
                continue
            outcome = self.compare(parent_root, child_root, name, bench['repeats'], cancelled)
            others[name] = outcome
            if outcome['status'] != 'ok':
                regressions.append(name + ':' + outcome['status'])
            elif (outcome['relative_delta'] is not None and outcome['relative_delta'] < -t['max_relative_regression']
                  and outcome['ci95'][1] < 0):
                regressions.append(name)
        report['checks']['other_benchmarks'] = others
        if regressions:
            return finish('rejected', 'benchmark regression: ' + ', '.join(regressions))
        stage('post_integrity')
        if tree_hashes(child_root) != child_hashes:
            return finish('quarantined', 'candidate tree changed during evaluation')
        return finish('qualified', 'verified target improvement with no detected regression')
