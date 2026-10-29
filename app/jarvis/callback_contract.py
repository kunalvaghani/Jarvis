"""Parse-only links between owned callbacks and executed methods; no repair code."""
import ast
import json


def routes(content, functions, setup_calls):
    tree = ast.parse(content)
    selected = {(row['function'], row['definition_line']) for row in functions}
    observed_setup = {(row.get('function'), row.get('definition_line')) for row in setup_calls}
    result = []
    for cls in (node for node in tree.body if isinstance(node, ast.ClassDef)):
        methods = [node for node in cls.body if isinstance(node, ast.FunctionDef) and not node.decorator_list]
        for target in methods:
            if (target.name, target.lineno) not in selected or not target.args.args:
                continue
            if sum(node.name == target.name for node in methods) != 1:
                continue
            parameters = target.args.args[1:]
            for caller in methods:
                if (caller.name, caller.lineno) not in observed_setup or caller is target or not caller.args.args:
                    continue
                if sum(node.name == caller.name for node in methods) != 1:
                    continue
                parents = {child: node for node in ast.walk(caller) for child in ast.iter_child_nodes(node)}
                for callback in (node for node in ast.walk(caller) if isinstance(node, ast.Lambda)):
                    chain = []; ancestor = parents.get(callback)
                    while ancestor is not None and ancestor is not caller:
                        chain.append(ancestor); ancestor = parents.get(ancestor)
                    if any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)) for node in chain):
                        continue
                    call = callback.body
                    if (not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute)
                            or not isinstance(call.func.value, ast.Name) or call.func.value.id != caller.args.args[0].arg
                            or call.func.attr != target.name or call.keywords or len(call.args) != 1 or len(parameters) != 1
                            or callback.args.posonlyargs or callback.args.kwonlyargs or callback.args.vararg or callback.args.kwarg
                            or len(callback.args.args) != 1 or len(callback.args.defaults) != 1
                            or not isinstance(call.args[0], ast.Name) or call.args[0].id != callback.args.args[0].arg
                            or not isinstance(callback.args.defaults[0], ast.Name)):
                        continue
                    loop = next((node for node in chain if isinstance(node, ast.For)), None)
                    if loop is None or not isinstance(loop.iter, ast.Name):
                        continue
                    bindings = list(loop.target.elts) if isinstance(loop.target, (ast.Tuple, ast.List)) else [loop.target]
                    if not bindings or not all(isinstance(node, ast.Name) for node in bindings):
                        continue
                    names = [node.id for node in bindings]; captured = callback.args.defaults[0].id
                    if captured not in names or len(set(names)) != len(names):
                        continue
                    assignments = [node for node in ast.walk(caller) if isinstance(node, ast.Assign)
                        and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == loop.iter.id]
                    uses = [node for node in ast.walk(caller) if isinstance(node, ast.Name) and node.id == loop.iter.id]
                    # A literal collection with any alias, mutation or additional use is not evidence.
                    if len(assignments) != 1 or len(uses) != 2 or loop.iter not in uses:
                        continue
                    if any(sum(isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Store)
                               for node in ast.walk(caller)) != 1 for name in names):
                        continue
                    try:
                        values = ast.literal_eval(assignments[0].value)
                    except (ValueError, TypeError, SyntaxError):
                        continue
                    if not isinstance(values, (list, tuple)) or not 1 <= len(values) <= 24:
                        continue
                    rows = values if len(bindings) > 1 else [(value,) for value in values]
                    if not all(isinstance(row, (list, tuple)) and len(row) == len(names)
                               and all(isinstance(value, str) and len(value) <= 64 for value in row) for row in rows):
                        continue
                    domains = [{ 'name': name, 'values': list(dict.fromkeys(row[index] for row in rows)) }
                               for index, name in enumerate(names)]
                    literals = []
                    for compare in (node for node in ast.walk(target) if isinstance(node, ast.Compare)):
                        if not isinstance(compare.left, ast.Name) or compare.left.id != parameters[0].arg or len(compare.ops) != 1:
                            continue
                        value = compare.comparators[0]
                        terms = value.elts if isinstance(compare.ops[0], (ast.In, ast.NotIn)) and isinstance(value, (ast.Tuple, ast.List, ast.Set)) else [value]
                        if isinstance(compare.ops[0], (ast.Eq, ast.NotEq, ast.In, ast.NotIn)):
                            literals += [node.value for node in terms if isinstance(node, ast.Constant) and isinstance(node.value, str)]
                    row = {'caller': caller.name, 'definition_line': caller.lineno, 'callback_line': callback.lineno,
                           'callee': target.name, 'parameter': parameters[0].arg, 'captured_name': captured,
                           'literal_captures': domains, 'dispatch_literals': list(dict.fromkeys(literals)),
                           'scope': 'Static literal callback route in an observed setup method; not causal proof or a repair instruction.'}
                    if len(json.dumps(result + [row])) <= 1600:
                        result.append(row)
                    if len(result) >= 2:
                        return result
    return result
