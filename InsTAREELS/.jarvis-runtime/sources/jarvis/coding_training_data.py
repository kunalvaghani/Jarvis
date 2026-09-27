"""Build reference-derived corrections from the trusted local curriculum oracle.

Never processes model-generated expressions or code. Executable case checks here
establish consistency with the reference, not independent algorithm validation.
"""
import ast
from pathlib import Path


def reference_source(name):
    path=Path(__file__).with_name('coding_curriculum.py')
    source=path.read_text(encoding='utf-8')
    tree=ast.parse(source)
    expressions={node.args[0].value:node.args[2].value for node in ast.walk(tree)
                 if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='add'
                 and len(node.args)>=3 and all(isinstance(a,ast.Constant) and isinstance(a.value,str) for a in node.args[:3])}
    expression=expressions[name]
    helpers={node.name:node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name!='catalogue'}
    needed=set()
    def collect(node):
        for call in ast.walk(node):
            if isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id in helpers and call.func.id not in needed:
                needed.add(call.func.id)
                collect(helpers[call.func.id])
    collect(ast.parse(expression,mode='eval'))
    definitions=[ast.get_source_segment(source,node) for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in needed]
    used={node.id for node in ast.walk(ast.parse('\n'.join([*definitions,f'result = ({expression})'])))
          if isinstance(node,ast.Name) and isinstance(node.ctx,ast.Load)}|{'json'}
    imports=[]
    for node in tree.body:
        if isinstance(node,ast.Import):
            aliases=[a for a in node.names if (a.asname or a.name.split('.')[0]) in used]
            if aliases: imports.append(ast.unparse(ast.Import(names=aliases)))
        elif isinstance(node,ast.ImportFrom):
            aliases=[a for a in node.names if (a.asname or a.name) in used]
            if aliases: imports.append(ast.unparse(ast.ImportFrom(module=node.module,names=aliases,level=node.level)))
    return '\n'.join(['import sys',*imports,'',*definitions,'','x = json.load(sys.stdin)',
                      f'result = ({expression})','print(json.dumps(result))',''])
