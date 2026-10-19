"""Evaluator subprocess entry: run one sealed benchmark against one candidate source tree.

Usage: python -I runner.py <candidate_root>   (request JSON on stdin, result JSON on stdout)

The benchmark code and its data come from this sealed evaluator directory; only the module
under test is imported from the candidate tree. The result records which ``jarvis`` package
was actually imported so a mix-up between candidate and production is detectable.
"""
import importlib.util
import json
from pathlib import Path
import sys


def main():
    candidate = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(candidate))
    request = json.loads(sys.stdin.read())
    spec = importlib.util.spec_from_file_location('sealed_benchmarks', Path(__file__).with_name('benchmarks.py'))
    benchmarks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(benchmarks)
    function = benchmarks.BENCHMARKS[request['benchmark']]
    scores, meta = function(request['data'], request.get('options', {}))
    import jarvis
    imported = Path(jarvis.__file__).resolve()
    if candidate not in imported.parents:
        raise SystemExit('Benchmark imported jarvis from outside the candidate tree: ' + str(imported))
    print(json.dumps({'scores': scores, 'meta': meta, 'imported_from': str(imported.parent)}))


if __name__ == '__main__':
    main()
