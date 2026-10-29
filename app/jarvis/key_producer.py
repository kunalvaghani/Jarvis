"""Parse-only provenance for a missing literal key; never supplies repair data."""
import ast
import textwrap


def _owned_nodes(node):
    yield node
    for child in ast.iter_child_nodes(node):
        if not isinstance(child,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef,ast.Lambda)):
            yield from _owned_nodes(child)


def _keys(value,position):
    if not isinstance(value,(list,tuple)) or not 1<=len(value)<=64:return None
    keys=[]
    for row in value:
        if position is not None:
            if not isinstance(row,(list,tuple)) or len(row)<=position:return None
            row=row[position]
        if type(row) not in (str,int) or len(str(row))>64:return None
        keys.append(row)
    if len({(type(key),key) for key in keys})!=len(keys):return None
    return keys


def producer(content,spans,members,key):
    """Unique local literal -> for target -> owned member indexed assignment.

    Ambiguous writes, mutations, aliases and computed producers do not qualify.
    Returned text must already be in the ordinary exact statement inventory.
    """
    if type(key) not in (str,int) or len(str(key))>64 or len(content)>8000:return None
    try:tree=ast.parse(content)
    except (ValueError,SyntaxError):return None
    found=[];lines=content.splitlines(keepends=True)
    for cls in tree.body:
        if not isinstance(cls,ast.ClassDef):continue
        methods=[method for method in cls.body if isinstance(method,ast.FunctionDef) and method.args.args and not method.decorator_list]
        for member in members:
            writes=[];unsafe=False
            for method in methods:
                receiver=method.args.args[0].arg
                def owned(node):
                    return isinstance(node,ast.Attribute) and node.attr==member and isinstance(node.value,ast.Name) and node.value.id==receiver
                for node in _owned_nodes(method):
                    if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and owned(node.func.value):unsafe=True
                    if isinstance(node,(ast.AugAssign,ast.Delete)):
                        targets=node.targets if isinstance(node,ast.Delete) else [node.target]
                        if any(owned(target) or isinstance(target,ast.Subscript) and owned(target.value) for target in targets):unsafe=True
                    if not isinstance(node,(ast.Assign,ast.AnnAssign)):continue
                    targets=node.targets if isinstance(node,ast.Assign) else [node.target]
                    for target in targets:
                        if owned(target) and not (isinstance(node.value,ast.Dict) and not node.value.keys):unsafe=True
                        if isinstance(target,ast.Subscript) and owned(target.value):writes.append((method,node,target))
            if unsafe or len(writes)!=1:continue
            method,write,target=writes[0]
            if not isinstance(target.slice,ast.Name) or not isinstance(write,ast.Assign) or len(write.targets)!=1:continue
            nodes=list(_owned_nodes(method))
            loops=[node for node in nodes if isinstance(node,ast.For) and write in node.body and isinstance(node.iter,ast.Name)]
            if len(loops)!=1:continue
            loop=loops[0];position=None
            if isinstance(loop.target,ast.Name):names=[loop.target.id]
            elif isinstance(loop.target,(ast.Tuple,ast.List)) and all(isinstance(item,ast.Name) for item in loop.target.elts):
                names=[item.id for item in loop.target.elts];position=names.index(target.slice.id) if names.count(target.slice.id)==1 else None
                if position is None:continue
            else:continue
            if names.count(target.slice.id)!=1:continue
            # A direct same-method declaration dominates the loop. Only that
            # loop may consume the iterable; no aliases or mutator calls.
            declarations=[node for node in nodes if isinstance(node,ast.Assign) and len(node.targets)==1
                          and isinstance(node.targets[0],ast.Name) and node.targets[0].id==loop.iter.id]
            uses=[node for node in nodes if isinstance(node,ast.Name) and node.id==loop.iter.id]
            if len(declarations)!=1 or len(uses)!=2:continue
            declaration=declarations[0]
            if declaration not in method.body or declaration.lineno>=loop.lineno:continue
            # Index reassignment would break the claimed row/key provenance.
            if sum(isinstance(node,ast.Name) and node.id==target.slice.id and isinstance(node.ctx,ast.Store) for node in nodes)!=1:continue
            try:value=ast.literal_eval(declaration.value)
            except (ValueError,TypeError,SyntaxError,MemoryError,RecursionError):continue
            keys=_keys(value,position)
            if not keys or any(type(item) is not type(key) for item in keys) or key in keys:continue
            span=''.join(lines[declaration.lineno-1:declaration.end_lineno]).rstrip('\r\n')
            if span not in spans:continue
            found.append({'old_string':span,'member':member,'missing_key':key,'observed_keys':keys,
                          'name':loop.iter.id,'key_position':position,'declaration_line':declaration.lineno,
                          'loop_line':loop.lineno,'binding_line':write.lineno})
    return found[0] if len(found)==1 else None


def focus(content,spans,contract,contexts):
    observed=[access['key'] for group in contract.get('obligations',[]) for access in group['accesses']]
    keys=[]
    for context in contexts:
        error=(context or {}).get('primary_error','')
        if not error.startswith('KeyError:') or len(error)>100:continue
        try:key=ast.literal_eval(error.split(':',1)[1].strip())
        except (ValueError,SyntaxError,MemoryError,RecursionError):continue
        if type(key) in (str,int) and any(type(item) is type(key) and item==key for item in observed):keys.append(key)
    if len(keys)!=1:return None
    return producer(content,spans,contract['members'],keys[0])


def validate_replacement(old,new,facts):
    """Data-only additions retain every original literal row, in order."""
    try:
        before=ast.parse(textwrap.dedent(old)).body;after=ast.parse(textwrap.dedent(new)).body
        if len(before)!=1 or len(after)!=1:raise ValueError()
        a,b=before[0],after[0]
        if not isinstance(a,ast.Assign) or not isinstance(b,ast.Assign) or len(b.targets)!=1:raise ValueError()
        if ast.dump(a.targets[0])!=ast.dump(b.targets[0]) or type(a.value) is not type(b.value):raise ValueError()
        previous=ast.literal_eval(a.value);current=ast.literal_eval(b.value)
        keys=_keys(current,facts['key_position'])
        if not keys or facts['missing_key'] not in keys or len(current)!=len(previous)+1:raise ValueError()
        remaining=iter(ast.dump(item) for item in b.value.elts)
        if not all(any(item==ast.dump(row) for item in remaining) for row in a.value.elts):raise ValueError()
        if any(type(key) is not type(facts['missing_key']) for key in keys):raise ValueError()
    except (ValueError,TypeError,SyntaxError,MemoryError,RecursionError):
        raise ValueError('Missing-key producer repair must add one literal row containing the observed missing key, retaining every original row and order. No method, loop or existing binding edits.') from None
