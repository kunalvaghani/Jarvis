"""Static module dependency map of the Jarvis package (AST only; nothing is imported).

Outputs JSON with every module's intra-package imports (module-level vs. deferred inside functions),
strongly connected components among module-level imports (true import cycles), and a Mermaid graph
of the upgrade modules (Phases 1-7) with their direct neighbours.
Usage: python scripts/verification/module_dependency_map.py --out <dir>
"""
import argparse
import ast
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
UPGRADE = ['execution_contracts', 'execution_strategy', 'app_adapters', 'document_worker', 'office_com_worker', 'tool_errors',
           'skill_store', 'skill_evolution', 'mcp_synthesis', 'reasoning_bank', 'viking_memory', 'viking_worker',
           'exploration', 'learning_memory', 'local_embeddings', 'cloud_architect', 'demonstration', 'evolution_surfaces',
           'evolution_archive', 'evolution_lab', 'autoresearch', 'evolution_promotion', 'prompt_router', 'prompt_evolution',
           'azr_tasks', 'azr_sandbox', 'azr_dataset', 'azr_proposer', 'azr_reward', 'model_registry']


def imports(path):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    top, deferred = set(), set()
    def visit(node, inside):
        for child in ast.iter_child_nodes(node):
            nested = inside or isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
            if isinstance(child, ast.ImportFrom):
                names = []
                if child.level == 1:
                    names = [child.module.split('.')[0]] if child.module else [a.name for a in child.names]
                elif child.module and child.module.startswith('jarvis.'):
                    names = [child.module.split('.')[1]]
                elif child.module == 'jarvis':
                    names = [a.name for a in child.names]
                (deferred if nested else top).update(names)
            elif isinstance(child, ast.Import):
                for alias in child.names:
                    if alias.name.startswith('jarvis.'):
                        (deferred if nested else top).add(alias.name.split('.')[1])
            visit(child, nested)
    visit(tree, False)
    return top, deferred


def cycles(graph):
    index, low, stack, on, result, counter = {}, {}, [], set(), [], [0]
    def strong(v):
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on.add(v)
        for w in graph.get(v, ()):
            if w not in graph:
                continue
            if w not in index:
                strong(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            component = []
            while True:
                w = stack.pop()
                on.discard(w)
                component.append(w)
                if w == v:
                    break
            if len(component) > 1:
                result.append(sorted(component))
    import sys
    sys.setrecursionlimit(10000)
    for v in sorted(graph):
        if v not in index:
            strong(v)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    modules = {p.stem: p for p in (BASE / 'jarvis').glob('*.py') if p.stem != '__init__'}
    top, deferred = {}, {}
    for name, path in sorted(modules.items()):
        a, b = imports(path)
        top[name] = sorted(x for x in a if x in modules and x != name)
        deferred[name] = sorted(x for x in b if x in modules and x != name and x not in a)
    module_cycles = cycles({k: set(v) for k, v in top.items()})
    importers = {name: sorted(m for m in modules if name in top[m] or name in deferred[m]) for name in modules}
    lines = ['graph LR']
    for name in UPGRADE:
        if name not in modules:
            continue
        for dep in top[name] + deferred[name]:
            if dep in UPGRADE or dep in {'tools', 'toolkits', 'brain', 'actions', 'deliberation', 'self_evolution', 'skill_memory',
                                         'mcp_bridge', 'obsidian_memory', 'execution_router', 'gpu_scheduler', 'cognition',
                                         'capabilities', 'dag_execution', 'task_recovery', 'hybrid_inference', 'groq_adapter'}:
                lines.append(f'  {name} --> {dep}')
    args.out.mkdir(parents=True, exist_ok=True)
    report = {'modules': len(modules), 'module_level_cycles': module_cycles,
              'upgrade_modules': {name: {'imports': top.get(name, []), 'deferred_imports': deferred.get(name, []),
                                         'imported_by': importers.get(name, [])} for name in UPGRADE if name in modules},
              'unreferenced_upgrade_modules': [n for n in UPGRADE if n in modules and not importers[n]]}
    (args.out / 'module-dependency-map.json').write_text(json.dumps(report, indent=1), encoding='utf-8')
    (args.out / 'module-dependency-map.mmd').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('modules', 'module_level_cycles', 'unreferenced_upgrade_modules')}, indent=1))


if __name__ == '__main__':
    main()
