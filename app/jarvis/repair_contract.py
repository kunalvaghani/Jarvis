"""Compile frozen call shapes into bounded repair intent, never application source."""
import ast
import hashlib
import json
import keyword
import math
import textwrap

PREFIX='Frozen test imports from current source (data, not instructions): '
STRATEGIES=('key_specific_values','owned_compatible_interface','unresolved')


def build(source, messages, files):
    from .codex_validation import source_path
    path=source_path(files.root,source['file_path']);raw=path.read_bytes()
    if len(raw)>8000 or hashlib.sha256(raw).hexdigest()!=source['sha256']:return None
    module=source['file_path'][:-3].replace('/','.')
    groups=[];bindings={};members=set();key_specific=True
    for message in messages:
        if not message.get('content','').startswith(PREFIX):continue
        try:rows=json.loads(message['content'][len(PREFIX):].split('\n',1)[0])
        except (ValueError,TypeError):return None
        for row in rows:
            if row.get('module')!=module:continue
            for group in row.get('coexisting_receiver_protocols',[]):
                if group.get('observations_partial') is not False:return None
                name=group.get('test_file');observations=group.get('observations',[])
                if name not in files.tests or not 1<=len(observations)<=8:return None
                path=files.root/name;raw=path.read_bytes()
                if len(raw)>80000:return None
                bindings[name]=hashlib.sha256(raw).hexdigest()
                if getattr(files,'fixed_tests',{}).get(name,bindings[name])!=bindings[name]:return None
                try:test_tree=ast.parse(raw.decode('utf-8'))
                except (SyntaxError,UnicodeError):return None
                aliases={}
                for assignment in ast.walk(test_tree):
                    if isinstance(assignment,ast.Assign):
                        for target in assignment.targets:
                            aliases.setdefault(ast.unparse(target),[]).append(assignment.value)
                origin=ast.parse(group['receiver'],mode='eval').body;visited=set()
                for _ in range(8):
                    text=ast.unparse(origin);values=aliases.get(text,[])
                    if text in visited or not values:break
                    visited.add(text)
                    if len({ast.dump(value) for value in values})!=1:return None
                    origin=values[0]
                if isinstance(origin,ast.Attribute):members.add(origin.attr)
                accesses=[];per_key={}
                for observation in observations:
                    try:
                        call=ast.parse(observation['call'],mode='eval').body
                        if not isinstance(call,ast.Call) or not isinstance(call.func,ast.Attribute):return None
                        receiver=call.func.value;indexes=[]
                        while isinstance(receiver,ast.Subscript):
                            indexes.append(receiver.slice);receiver=receiver.value
                        indexes.reverse()
                        if ast.unparse(receiver)!=group['receiver']:return None
                        literal=indexes[0] if indexes else None
                        if not isinstance(literal,ast.Constant) or type(literal.value) not in (str,int):
                            key_specific=False;key=None
                        else:
                            key=literal.value
                            if len(str(key))>64:return None
                            per_key.setdefault((type(key).__name__,str(key)),set()).add(len(indexes)-1)
                        accesses.append({'key':key,'subscripts_after_key':max(0,len(indexes)-1),
                                         'line':observation['line'],'call':observation['call']})
                    except (ValueError,TypeError,KeyError,SyntaxError):return None
                if any(len(depths)>1 for depths in per_key.values()):key_specific=False
                groups.append({'test_file':name,'receiver':group['receiver'],'method':group['method'],'accesses':accesses})
    if not groups or len(groups)>4 or len(members)>4:return None
    value={'file_path':source['file_path'],'source_sha256':source['sha256'],'test_sha256':bindings,
           'members':sorted(members),'obligations':groups,
           'strategies':list(STRATEGIES if key_specific else STRATEGIES[1:])}
    return value if len(json.dumps(value))<=3600 else None


def schema(contract):
    return {'anyOf':[{'type':'object','additionalProperties':False,'required':['tool','arguments'],
        'properties':{'tool':{'type':'string','enum':['update_plan']},
          'arguments':{'type':'object','additionalProperties':False,
            'required':['observed_cause','strategy','uncertainty'],
            'properties':{'observed_cause':{'type':'string','minLength':1,'maxLength':240},
                          'strategy':{'type':'string','enum':contract['strategies']},
                          'uncertainty':{'type':'string','minLength':1,'maxLength':160}}},
          'note':{'type':'string','maxLength':240}}}]}


def compile_steps(value,contract):
    from .structured_output import validate_contract
    validate_contract(schema(contract),value)
    strategy=value['arguments']['strategy']
    if strategy=='unresolved':raise ValueError('Interface strategy remains unresolved; no replacement is authorized.')
    # Model prose is retained in the receipt, but cannot become the worker's
    # repair instructions or predict that unchanged verification will succeed.
    intent=('Preserve each exact key access route independently; do not generalize by key spelling or category.'
            if strategy=='key_specific_values' else
            'Use an owned compatible value interface preserving every recorded access route and the original real objects/callbacks.')
    return [intent,'Frozen source-bound obligations: '+json.dumps(contract['obligations'],ensure_ascii=False),
            'Run every original unchanged executable check. No passing result or additional permission is implied.']


def binding_spans(content,spans,contract):
    """Offer value bindings, excluding empty initializers and earlier factories.

    Selection only; replacement code always comes from the coding model.
    """
    direct=[];enclosing=[]
    for span in spans:
        try:tree=ast.parse(textwrap.dedent(span))
        except (SyntaxError,ValueError):continue
        matches=[]
        for node in ast.walk(tree):
            if not isinstance(node,(ast.Assign,ast.AnnAssign)) or node.value is None:continue
            targets=node.targets if isinstance(node,ast.Assign) else [node.target]
            for target in targets:
                indexed=isinstance(target,ast.Subscript)
                while isinstance(target,ast.Subscript):target=target.value
                if (isinstance(target,ast.Attribute) and target.attr in contract['members']
                        and (indexed or isinstance(node.value,ast.Dict) and bool(node.value.keys))):matches.append(node)
        if not matches:continue
        (direct if len(tree.body)==1 and tree.body[0] in matches else enclosing).append(span)
    return direct or enclosing


def _statements(text):
    from .structured_output import ModelOutputError
    try:return ast.parse(text)
    except IndentationError:
        wrapped=ast.parse('if True:\n'+text)
        if len(wrapped.body)!=1 or wrapped.body[0].orelse:
            raise ModelOutputError('Binding replacement escapes its statement scope; no source action executed.')
        return ast.Module(body=wrapped.body[0].body,type_ignores=[])


def owned_methods(spans,contract):
    """An indexed value binding can require a model-authored owned type."""
    if len(spans)!=1:return None
    try:tree=_statements(spans[0])
    except (SyntaxError,ValueError):return None
    if not (len(tree.body)==1 and isinstance(tree.body[0],ast.Assign)
            and len(tree.body[0].targets)==1 and isinstance(tree.body[0].targets[0],ast.Subscript)):return None
    methods={group['method'] for group in contract['obligations']}
    if any(access['subscripts_after_key'] for group in contract['obligations'] for access in group['accesses']):methods.add('__getitem__')
    return sorted(methods) if 1<=len(methods)<=8 else None


def key_specific_spec(spans,contract):
    """Ground a model-selected per-key edit in a side-effect-free local binding."""
    if len(spans)!=1 or len(contract.get('members',[]))!=1:return None
    try:tree=_statements(spans[0])
    except (SyntaxError,ValueError):return None
    if not (len(tree.body)==1 and isinstance(tree.body[0],ast.Assign) and len(tree.body[0].targets)==1
            and isinstance(tree.body[0].targets[0],ast.Subscript) and isinstance(tree.body[0].targets[0].slice,ast.Name)):return None
    original=tree.body[0].value;leaf=original;values=[]
    while isinstance(leaf,(ast.List,ast.Tuple)) and len(leaf.elts)==1:
        leaf=leaf.elts[0];values.append(ast.unparse(leaf))
    if not isinstance(leaf,ast.Name):return None
    values.append(ast.unparse(ast.List(elts=[original],ctx=ast.Load())))
    values=list(dict.fromkeys(value for value in values if value!=ast.unparse(original) and len(value)<=180))
    routes={}
    for group in contract['obligations']:
        for access in group['accesses']:
            key=access['key']
            if type(key) not in (str,int):return None
            identity=(type(key).__name__,key)
            if identity in routes and routes[identity]['depth']!=access['subscripts_after_key']:return None
            routes[identity]={'key':key,'depth':access['subscripts_after_key']}
    if not values or not routes:return None
    return {'old_string':spans[0],'index_name':tree.body[0].targets[0].slice.id,
            'routes':list(routes.values()),'value_expressions':values}


def key_specific_schema(spec):
    groups={}
    for row in spec['routes']:groups.setdefault(row['depth'],[]).append(row['key'])
    return {'anyOf':[{'type':'object','additionalProperties':False,'required':['old_string','when_keys','value_expression'],
        'properties':{'old_string':{'type':'string','enum':[spec['old_string']]},
            'when_keys':{'type':'array','minItems':1,'maxItems':min(8,len(keys)),
                'items':{'enum':keys}},
            'value_expression':{'type':'string','enum':spec['value_expressions']}}} for keys in groups.values()]}


def compile_key_specific_binding(arguments,spec):
    """Keep model selector/value decisions; retain the old fallback unchanged."""
    from .structured_output import ModelOutputError,validate_contract
    changes=arguments.get('changes',[])
    if len(changes)!=1:
        raise ModelOutputError('Key-specific binding requires one when_keys/value_expression change.')
    row=changes[0]
    try:validate_contract(key_specific_schema(spec),row)
    except ValueError as error:raise ModelOutputError('Key-specific strategy requires when_keys and value_expression, not a uniform assignment. Do not combine different frozen access routes. DATA: '+json.dumps(spec['routes'])+' '+str(error)) from error
    selected=[(type(key).__name__,key) for key in row['when_keys']]
    routes={(type(item['key']).__name__,item['key']):item['depth'] for item in spec['routes']}
    if len(set(selected))!=len(selected) or any(key not in routes for key in selected):
        raise ModelOutputError('when_keys must select distinct observed literal keys.')
    if len({routes[key] for key in selected})!=1:
        raise ModelOutputError('when_keys combines different frozen access routes. Select one homogeneous route group, or use an owned compatible interface. DATA: '+json.dumps(spec['routes']))
    old=_statements(row['old_string']);node=old.body[0]
    condition=ast.Compare(left=node.targets[0].slice,ops=[ast.In()],
        comparators=[ast.Tuple(elts=[ast.Constant(value=key) for key in row['when_keys']],ctx=ast.Load())])
    value=ast.IfExp(test=condition,body=ast.parse(row['value_expression'],mode='eval').body,orelse=node.value)
    tree=ast.fix_missing_locations(ast.Module(body=[ast.Assign(targets=node.targets,value=value)],type_ignores=[]))
    new=ast.unparse(tree)
    if len(new)>1200:raise ModelOutputError('Key-specific binding exceeds the existing1200-character replacement budget.')
    return {**arguments,'changes':[{'old_string':row['old_string'],'new_string':new}]},[{
        'model_selected_key_sha256':[hashlib.sha256(json.dumps(key).encode()).hexdigest() for key in row['when_keys']],
        'model_value_expression_sha256':hashlib.sha256(row['value_expression'].encode()).hexdigest(),
        'original_fallback_retained':True,'controller_supplied_selector_choices':False,
        'controller_supplied_callback_bodies':False}]


def owned_inputs(span):
    """Existing value expressions only; preserve the original real objects."""
    from .structured_output import ModelOutputError
    tree=_statements(span)
    if not (len(tree.body)==1 and isinstance(tree.body[0],ast.Assign) and len(tree.body[0].targets)==1
            and isinstance(tree.body[0].targets[0],ast.Subscript)):
        raise ModelOutputError('Owned binding requires one existing indexed assignment.')
    value=tree.body[0].value;inputs=[ast.unparse(value)]
    if isinstance(value,(ast.List,ast.Tuple)) and len(value.elts)==1:inputs.insert(0,ast.unparse(value.elts[0]))
    inputs=list(dict.fromkeys(text for text in inputs if len(text)<=180))
    if not inputs:raise ModelOutputError('Original bound value exceeds the existing constructor expression budget.')
    return inputs


def owned_change_schema(spans,methods):
    if len(spans)!=1:raise ValueError('Owned method contract requires one exact binding.')
    required=['__init__']+sorted(set(methods)-{'__init__'});limit=min(240,850//len(required))
    return {'type':'object','additionalProperties':False,'required':['old_string','owned_definition','constructor_arguments'],
        'properties':{'old_string':{'type':'string','enum':spans},
            'owned_definition':{'type':'object','additionalProperties':False,'required':['name','methods'],
                'properties':{'name':{'type':'string','minLength':1,'maxLength':64,'pattern':'^[A-Za-z_][A-Za-z0-9_]{0,63}$'},
                    'methods':{'type':'object','additionalProperties':False,'required':required,
                        'properties':{name:{'type':'string','minLength':1,'maxLength':limit} for name in required}}}},
            'constructor_arguments':{'type':'array','minItems':1,'maxItems':1,
                'items':{'type':'string','enum':owned_inputs(spans[0])}}}}


def frozen_failure_observations(current,history,frozen):
    """Carry verified check facts across context rebuilding, never old proposals.

    Historical inputs are already selected/verified by the workload loader; the
    extra frozen-hash check prevents cross-test attribution. Nothing here grants
    current verification credit, source permissions or an executable strategy.
    """
    rows=[];seen=set()
    for index,value in enumerate([current]+list(history)):
        if not value or value.get('passed') is not False:continue
        hashes=value.get('hashes',{})
        signature=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()
        if signature in seen:continue
        selected=[]
        for outcome in value.get('python_test_outcomes',[]):
            path=outcome.get('path')
            if (path not in frozen or hashes.get(path)!=frozen[path] or outcome.get('test_sha256')!=frozen[path]
                    or outcome.get('partial') is not False or outcome.get('successful') is not False):continue
            item={'test_file':path,'test_sha256':frozen[path],
                  'failed_cases':outcome.get('failed_ids',[])[:4],'error_cases':outcome.get('error_ids',[])[:4]}
            facts=[];fact_signatures=set()
            for error in value.get('errors',[]):
                if error.get('path')!=path:continue
                for fact in error.get('runtime_failure_facts',[]):
                    kind=fact.get('exception_type');method=fact.get('test_method')
                    if not isinstance(kind,str) or not kind.isidentifier() or not isinstance(method,str) or not method.isidentifier():continue
                    frames=[]
                    for frame in fact.get('frames',[])[:1]:
                        observed={key:frame[key] for key in ('module_path','sha256','line','function') if key in frame}
                        operands={}
                        for name,entry in frame.get('operands',{}).items():
                            if not isinstance(name,str) or len(name)>64 or not name.isidentifier() or not isinstance(entry,dict):continue
                            tag=entry.get('type')
                            if tag not in {'str','int','float','bool','NoneType'}:continue
                            scalar={'type':tag};number=entry.get('value')
                            known=('value' in entry and (tag=='NoneType' and number is None
                                or tag=='bool' and type(number) is bool
                                or tag=='int' and type(number) is int and abs(number)<=10**12
                                or tag=='float' and type(number) is float and math.isfinite(number) and abs(number)<=10**12))
                            if known:scalar['value']=number
                            operands[name]=scalar
                        observed['operands']=operands;frames.append(observed)
                    data={'test_method':method,'exception_type':kind,'frames':frames,'partial':True}
                    identity=json.dumps({'exception_type':kind,'frames':frames},sort_keys=True)
                    if identity not in fact_signatures and len(json.dumps(data))<=1200:
                        fact_signatures.add(identity);facts.append(data)
            if facts:item['runtime_failure_facts']=facts[:2]
            selected.append(item)
        if not selected:continue
        row={'kind':'current_failed_check' if index==0 else 'historical_counterexample',
             'source_fingerprint':signature,'checks':selected[:2],'untrusted_diagnostic_data':True,
             'current_check_credit':False}
        if len(json.dumps(rows+[row]))<=3000:rows.append(row);seen.add(signature)
        if len(rows)>=3:break
    return rows


def compile_owned_binding(arguments,methods):
    """Assemble model-authored methods with a model name and original value.

    Class/construction syntax and the old target are mechanical structure;
    every method body is supplied by the coding model, never the controller.
    """
    from .structured_output import ModelOutputError,validate_contract
    changes=arguments.get('changes',[])
    if len(changes)!=1 or set(changes[0])!={'old_string','owned_definition','constructor_arguments'}:
        raise ModelOutputError('Owned-interface binding requires owned_definition with explicit methods and constructor_arguments.')
    row=changes[0]
    try:validate_contract(owned_change_schema([row['old_string']],methods),row)
    except (ValueError,SyntaxError) as error:raise ModelOutputError('Invalid owned-method contract: '+str(error)) from error
    definition=row['owned_definition'];name=definition['name'];errors={};nodes=[]
    if not name.isidentifier() or not name.isascii() or keyword.iskeyword(name):errors['name']='Provide a valid owned class identifier.'
    for method,source in definition['methods'].items():
        try:
            tree=_statements(source)
            if not (len(tree.body)==1 and isinstance(tree.body[0],ast.FunctionDef)
                    and tree.body[0].name==method and not tree.body[0].decorator_list):
                raise ValueError('Provide exactly one complete def '+method+' with its original-object delegation body.')
            nodes.append(tree.body[0])
        except (SyntaxError,ValueError) as error:errors[method]=str(error)[:180]
    if errors:raise ModelOutputError('Owned-method component errors (all independent checks): '+json.dumps(errors))
    old=_statements(row['old_string']);target=old.body[0].targets[0]
    cls=ast.ClassDef(name=name,bases=[],keywords=[],body=nodes,decorator_list=[])
    construct=ast.Call(func=ast.Name(id=name,ctx=ast.Load()),
        args=[ast.parse(text,mode='eval').body for text in row['constructor_arguments']],keywords=[])
    tree=ast.fix_missing_locations(ast.Module(body=[cls,ast.Assign(targets=[target],value=construct)],type_ignores=[]))
    new=ast.unparse(tree)
    if len(new)>1200:raise ModelOutputError('Owned binding exceeds the existing1200-character replacement budget.')
    return {**arguments,'changes':[{'old_string':row['old_string'],'new_string':new}]},[{
        'model_owned_name':name,'model_method_sha256':{key:hashlib.sha256(text.encode()).hexdigest() for key,text in definition['methods'].items()},
        'model_constructor_argument_sha256':[hashlib.sha256(text.encode()).hexdigest() for text in row['constructor_arguments']],
        'constructor_inputs_from_original_binding':True,'derived_existing_target':ast.unparse(target),
        'controller_supplied_method_bodies':False}]


def render_bindings(arguments,members):
    """Render model statements at an existing binding's scope, preserving ASTs.

    This applies only to a sealed single-assignment span, never a method or an
    ordinary edit. No node, identifier, expression or literal is synthesized.
    Raw proposals remain in the inference journal; return formatting provenance.
    """
    from .structured_output import ModelOutputError
    statements=_statements
    changes=[];renderings=[]
    for change in arguments['changes']:
        old=change['old_string'];new=change['new_string']
        try:original=statements(old)
        except (SyntaxError,ValueError):original=None
        node=original.body[0] if original and len(original.body)==1 else None
        targets=node.targets if isinstance(node,ast.Assign) else [node.target] if isinstance(node,ast.AnnAssign) else []
        owned=False
        for target in targets:
            while isinstance(target,ast.Subscript):target=target.value
            owned|=isinstance(target,ast.Attribute) and target.attr in members
        if not owned:
            changes.append(dict(change));continue
        try:
            proposed=statements(new)
            if ast.dump(proposed)==ast.dump(original):
                raise ModelOutputError('Binding replacement has unchanged Python AST; no source action executed.')
            indent=old[:len(old)-len(old.lstrip(' \t'))]
            rendered=textwrap.indent(ast.unparse(proposed),indent)
            if ast.dump(statements(rendered))!=ast.dump(proposed):
                raise ModelOutputError('Binding formatting did not preserve the model Python AST; no source action executed.')
        except (SyntaxError,ValueError) as error:
            if isinstance(error,ModelOutputError):raise
            raise ModelOutputError('Binding replacement must contain complete Python statements; no source action executed. '+str(error)) from error
        if len(rendered)>1200:
            raise ModelOutputError('Rendered binding exceeds the existing1200-character replacement budget; no source action executed.')
        changes.append({**change,'new_string':rendered})
        if rendered!=new:
            renderings.append({'old_string':old,'proposed_sha256':hashlib.sha256(new.encode()).hexdigest(),
                'rendered_sha256':hashlib.sha256(rendered.encode()).hexdigest(),
                'rendered_new_string':rendered,'ast_unchanged':True})
    if sum(len(change['new_string']) for change in changes)>2400:
        raise ModelOutputError('Rendered bindings exceed the existing2400-character batch budget; no source action executed.')
    return {**arguments,'changes':changes},renderings
