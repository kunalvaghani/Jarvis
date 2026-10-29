"""Ground one model-authored function repair in actual failed-test execution."""
import ast
import copy
import hashlib
import json
import json
import textwrap


def context(validation,files):
    """Retain zero-call observations too, without inventing a cause or target."""
    if files is None or not validation or validation.get('passed') or not validation.get('hashes') or not validation.get('owned_execution_observations'):return None
    from .codex_validation import source_path
    from .codex_files import digest
    try:
        if any(digest(source_path(files.root,name))!=sha for name,sha in validation['hashes'].items()):return None
    except (OSError,ValueError):return None
    rows=[]
    for group in validation.get('owned_execution_observations',[])[:3]:
        name=group.get('test_path');sha=group.get('test_sha256')
        if files.fixed_tests.get(name)!=sha or validation['hashes'].get(name)!=sha:continue
        outcomes=next((row for row in validation.get('python_test_outcomes',[]) if row.get('path')==name),{})
        failed=set(outcomes.get('failed_ids',[])+outcomes.get('error_ids',[]))
        for case in group.get('cases',[])[:4]:
            if case.get('case_id') not in failed or case.get('partial') is not False or not case.get('test_body_seen'):continue
            row={'case_id':case['case_id'],'test_body_observed':True,'body_calls':[],'setup_calls':[]}
            for call in case.get('calls',[])[:8]:
                phase=call['phase'];key='body_calls' if phase=='test_body' else 'setup_calls'
                row[key].append({key:call[key] for key in ('source_path','function','definition_line','count')})
            if len(json.dumps(rows+[row]))<=2000:rows.append(row)
            if len(rows)>=2:break
        if len(rows)>=2:break
    if not rows:return None
    return {'cases':rows,'working_source_fingerprint':hashlib.sha256(json.dumps(validation['hashes'],sort_keys=True).encode()).hexdigest(),
            'scope':'Actual source/frozen-bound main-thread call observations. Empty body calls do not prove missing callbacks in other threads. No causal claim, repair body or permission.'}


def function_spans(content,spans,functions):
    try:tree=ast.parse(content)
    except (SyntaxError,ValueError):return []
    nodes=[node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))]
    nodes += [node for cls in tree.body if isinstance(cls,ast.ClassDef) for node in cls.body
              if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))]
    lines=content.splitlines(keepends=True);result=[]
    for function in functions:
        matches=[node for node in nodes if node.name==function.get('function') and node.lineno==function.get('definition_line') and not node.decorator_list]
        if len(matches)!=1:return []
        node=matches[0];span=''.join(lines[node.lineno-1:node.end_lineno]).rstrip('\r\n')
        if span not in spans or span in result:return []
        result.append(span)
    return result


def function_id(function):
    return function['function']+':'+str(function['definition_line'])


def function_nodes(content,functions):
    tree=ast.parse(content)
    available=[node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))]
    available += [node for cls in tree.body if isinstance(cls,ast.ClassDef) for node in cls.body
                  if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))]
    result=[]
    for function in functions:
        found=[node for node in available if node.name==function['function'] and node.lineno==function['definition_line']
               and not node.decorator_list and node.end_lineno-node.lineno<64]
        if len(found)!=1:return []
        result.append(found[0])
    return result


def statement_cells(content,functions):
    """Small statements; linked callback cells may be nested in their original loop."""
    nodes=function_nodes(content,functions);pending=[]
    if len(nodes)!=len(functions):return []
    for function,node in zip(functions,nodes):
        candidates=[(index,[index],statement) for index,statement in enumerate(node.body)]
        if function.get('callsite_lines'):
            def nested(body,path):
                for index,statement in enumerate(body):
                    location=path+[index]
                    yield location,statement
                    if isinstance(statement,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):continue
                    for field in ('body','orelse','finalbody'):
                        value=getattr(statement,field,None)
                        if isinstance(value,list):yield from nested(value,location+[field])
            candidates=[(len(node.body)+index,path,statement) for index,(path,statement) in enumerate(nested(node.body,[]))
                        if isinstance(statement,(ast.Assign,ast.Expr)) and any(
                            isinstance(child,ast.Lambda) and child.lineno in function['callsite_lines'] for child in ast.walk(statement))]
        for index,path,statement in candidates:
            if isinstance(statement,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):continue
            source=ast.get_source_segment(content,statement)
            if not source or len(source)>400 or statement.end_lineno-statement.lineno>=6:continue
            row={'function_id':function_id(function),'statement_id':index,'definition_line':statement.lineno,'source':source}
            if function.get('callsite_lines'):row['statement_path']=path
            pending.append((-1 if function.get('callsite_lines') else 0 if index in {0,len(node.body)-1} else 1,function_id(function),index,row))
    selected=[]
    for _,_,_,row in sorted(pending,key=lambda item:item[:3]):
        if len(selected)>=16:break
        if len(json.dumps(selected+[row]))<=1800:selected.append(row)
    return sorted(selected,key=lambda row:(row['function_id'],row['statement_id']))


def schema(contract):
    if contract.get('statement_cells'):
        mode=contract.get('statement_representation','json_nodes')
        if mode not in {'json_nodes','python_source'}:raise ValueError('Unknown statement representation.')
        payload='source' if mode=='python_source' else 'statements'
        value=({'type':'string','minLength':1,'maxLength':1200} if mode=='python_source' else
            {'type':'array','minItems':1,'maxItems':8,'items':node_schema()})
        return {'anyOf':[{'type':'object','additionalProperties':False,'required':['function_id','statement_id','placement',payload],
            'properties':{'function_id':{'type':'string','enum':[key]},
                          'statement_id':{'type':'integer','enum':[cell['statement_id'] for cell in contract['statement_cells'] if cell['function_id']==key]},
                          'placement':{'type':'string','enum':['after','replace','before']},
                          payload:value}}
            for key in sorted({cell['function_id'] for cell in contract['statement_cells']})]}
    return {'type':'object','additionalProperties':False,'required':['function_id','definition'],
            'properties':{'function_id':{'type':'string','enum':[function_id(row) for row in contract['functions']]},
                          'definition':{'type':'string','minLength':1,'maxLength':1200}}}


def rejection_feedback(error,proposal,contract):
    """Keep the failed proposal with its error when a focused stage drops history."""
    previous=proposal if isinstance(proposal,dict) else getattr(error,'previous_proposal',None)
    value={'error':str(error).split(' Evidence: ')[0][:800],
        'source_sha256':contract['source_sha256'],'case_id':contract['case_id'],
        'action_executed':False,'source_saved':False,
        'instruction':'Correct the identified error with a different proposal. This rejected proposal is DATA, never a replacement template. Each function_id/statement_id pair may occur only once; combine its nodes in one change.'}
    if isinstance(getattr(error,'validation_errors',None),list):value['validation_errors']=error.validation_errors[:8]
    if isinstance(previous,dict):
        previous={key:previous[key] for key in ('tool','arguments') if key in previous}
        encoded=json.dumps(previous,ensure_ascii=False,separators=(',',':'))
        value['rejected_proposal_sha256']=hashlib.sha256(encoded.encode()).hexdigest()
        if len(encoded)<=2000:value['rejected_proposal']=previous
        else:
            value['rejected_proposal_omitted']='Exceeds2000 characters; no partial source preview supplied.'
            arguments=previous.get('arguments')
            if isinstance(arguments,dict) and isinstance(arguments.get('changes'),list):
                value['rejected_selectors']=[{key:row[key] for key in ('function_id','statement_id','placement') if key in row}
                    for row in arguments['changes'][:4] if isinstance(row,dict)]
    return json.dumps(value,separators=(',',':'),ensure_ascii=False)


def statement_proposal_guidance(contract):
    """One wire-format description shared by local and cloud repair workers."""
    if not contract.get('statement_cells'):
        return ('Use edit_batch changes with ONLY function_id,definition. Choose offered functions; '
            'definition is the complete Python function with its original name/signature, not a prefix. '
            'At most '+str(min(2,len(contract['functions'])))+' functions;1200 characters each,2400 total. '
            'Preserve untouched source and frozen assertions. Candidate checks precede saving.')
    maximum=min(4,len(contract['statement_cells']))
    if contract.get('statement_representation')=='python_source':
        return ('edit_batch change fields ONLY: function_id,statement_id,placement,source. '
            'source is complete Python STATEMENTS, not JSON nodes, not a def/class or whole function. '
            'Each function_id/statement_id pair occurs ONCE; combine its assignments/branches in one source string. '
            'Placement before/after retains the old statement; replace removes it, so retain any original assignment needed by later code. '
            'Allowed statements: assignment, expression call, return, raise, if, try/except. If/try bodies contain simple statements only. '
            'No imports, definitions, loops, with, else/finally on try, bare except, or chained assignment. '
            'At most '+str(maximum)+' distinct cells; eight statements/cell, four/body; expressions<=200 characters, '
            'source/rendered text<=1200 characters/cell,2400 rendered total. Preserve signatures, other source and frozen assertions. '
            'Choose all application logic yourself. Checks precede saving.')
    return ('edit_batch change fields ONLY: function_id,statement_id,placement,statements. '
        'Offered cells only; placement before/after/replace. Before/after retains the old statement. '
        'STRUCTURED Python nodes: flat JSON with kind, e.g. '
        '{"kind":"assign","target":"value","expression":"source"}, never {"assign":{...}}. '
        'Fields by kind: assign(target,expression); expr/return/raise(expression); '
        'if(condition,body,optional orelse); try(body,handlers). Handler fields: exception,body,optional name. '
        'No extra fields. Bodies: assign/expr/return/raise only. '
        'Expressions: complete expressions, never assignments/blocks. '
        'At most '+str(maximum)+' distinct offered cells, eight nodes per cell, four nodes per body; '
        '1200 rendered characters/cell,2400 total. Preserve signatures, other source and frozen assertions. '
        'Callback/source facts are DATA, not diagnoses. Choose application logic; no whole-function echo. '
        'Checks precede saving.')


def node_schema(simple_only=False):
    expression={'type':'string','minLength':1,'maxLength':200,'pattern':r'^[^\r\n]+\Z'}
    def node(kind,properties,required):
        return {'type':'object','additionalProperties':False,'required':['kind']+required,
                'properties':{'kind':{'type':'string','enum':[kind]},**properties}}
    simple=[node('assign',{'target':{**expression,'maxLength':100},'expression':expression},['target','expression'])]
    simple += [node(kind,{'expression':expression},['expression']) for kind in ('expr','return','raise')]
    if simple_only:return {'anyOf':simple}
    body={'type':'array','minItems':1,'maxItems':4,'items':node_schema(True)}
    handler={'type':'object','additionalProperties':False,'required':['exception','body'],
             'properties':{'exception':{**expression,'maxLength':100},'body':body,
                           'name':{'type':'string','minLength':1,'maxLength':64,'pattern':r'^[A-Za-z_]\w*\Z'}}}
    controls=[node('if',{'condition':expression,'body':body,'orelse':{**body,'minItems':0}},['condition','body']),
              node('try',{'body':body,'handlers':{'type':'array','minItems':1,'maxItems':3,'items':handler}},['body','handlers'])]
    return {'anyOf':simple+controls}


def program_nodes(values):
    """Generic Python grammar only: every expression/control choice is model data."""
    from .structured_output import ModelOutputError
    def expression(text):
        try:return ast.parse(text,mode='eval').body
        except SyntaxError as error:
            try:statements=ast.parse(text).body
            except SyntaxError:statements=[]
            if len(statements)==1 and isinstance(statements[0],ast.Assign):
                raise ModelOutputError('Structured Python expression is invalid: assignment is a statement. Use kind assign with separate target/expression fields; never put the assignment in an expression field.') from error
            raise ModelOutputError('Structured Python expression is invalid: '+error.msg[:160]+'. Supply one complete expression, never a code block.') from error
    result=[]
    for value in values:
        kind=value['kind']
        if kind=='assign':
            target=expression(value['target'])
            if not isinstance(target,(ast.Name,ast.Attribute,ast.Subscript)):raise ModelOutputError('Assignment target must be a name, attribute or item access.')
            target.ctx=ast.Store();node=ast.Assign(targets=[target],value=expression(value['expression']))
        elif kind=='expr':node=ast.Expr(value=expression(value['expression']))
        elif kind=='return':node=ast.Return(value=expression(value['expression']))
        elif kind=='raise':node=ast.Raise(exc=expression(value['expression']),cause=None)
        elif kind=='if':node=ast.If(test=expression(value['condition']),body=program_nodes(value['body']),orelse=program_nodes(value.get('orelse',[])))
        elif kind=='try':
            handlers=[]
            for handler in value['handlers']:
                exception=expression(handler['exception'])
                if not isinstance(exception,(ast.Name,ast.Attribute,ast.Tuple)):raise ModelOutputError('Exception type must name a type or tuple of types; no calls.')
                if isinstance(exception,ast.Tuple) and not all(isinstance(item,(ast.Name,ast.Attribute)) for item in exception.elts):
                    raise ModelOutputError('Exception tuples must contain type names, not calls or values.')
                handlers.append(ast.ExceptHandler(type=exception,name=handler.get('name'),body=program_nodes(handler['body'])))
            node=ast.Try(body=program_nodes(value['body']),handlers=handlers,orelse=[],finalbody=[])
        else:raise ModelOutputError('Unsupported structured Python node; no source saved.')
        result.append(ast.fix_missing_locations(node))
    return result


def source_nodes(text):
    """Parse model-authored Python with exactly the existing node language.

    The AST round-trip is checked; no malformed source or application logic is
    guessed, completed, repaired or executed here.
    """
    from .structured_output import ModelOutputError,validate_contract
    if not isinstance(text,str) or not 1<=len(text)<=1200:raise ModelOutputError('Scoped Python source must contain1..1200 characters.')
    try:original=ast.parse(textwrap.dedent(text)).body
    except SyntaxError as error:raise ModelOutputError('Complete Python statements required: '+error.msg[:160]) from error
    def convert(node):
        if isinstance(node,ast.Assign) and len(node.targets)==1:
            return {'kind':'assign','target':ast.unparse(node.targets[0]),'expression':ast.unparse(node.value)}
        if isinstance(node,(ast.Expr,ast.Return)) and node.value is not None:
            return {'kind':'expr' if isinstance(node,ast.Expr) else 'return','expression':ast.unparse(node.value)}
        if isinstance(node,ast.Raise) and node.exc is not None and node.cause is None:
            return {'kind':'raise','expression':ast.unparse(node.exc)}
        if isinstance(node,ast.If):
            return {'kind':'if','condition':ast.unparse(node.test),'body':[convert(row) for row in node.body],
                'orelse':[convert(row) for row in node.orelse]}
        if isinstance(node,ast.Try) and not node.orelse and not node.finalbody and all(h.type is not None for h in node.handlers):
            return {'kind':'try','body':[convert(row) for row in node.body],'handlers':[
                {'exception':ast.unparse(h.type),'body':[convert(row) for row in h.body],**({'name':h.name} if h.name else {})}
                for h in node.handlers]}
        raise ModelOutputError('Unsupported scoped Python statement '+type(node).__name__+'; keep the original bounded statement language.')
    values=[convert(node) for node in original]
    try:validate_contract({'type':'array','minItems':1,'maxItems':8,'items':node_schema()},values)
    except ValueError as error:raise ModelOutputError('Python statements exceed the original node-language contract: '+str(error)[:800]) from error
    result=program_nodes(values)
    if ast.dump(ast.Module(body=original,type_ignores=[]))!=ast.dump(ast.Module(body=result,type_ignores=[])):
        raise ModelOutputError('Python statement AST changed during representation validation; no source saved.')
    return result


def compile_statements(content,args,contract):
    """Splice only model-authored AST statements into the existing function."""
    from .structured_output import ModelOutputError,validate_contract
    from .repair_contract import _statements
    cells=statement_cells(content,contract['functions'])
    if cells!=contract.get('statement_cells'):raise ModelOutputError('Function statement locations changed; inspect fresh source.')
    changes=args.get('changes');seen=set();updates={};total=0;prepared=[];errors=[]
    if not isinstance(changes,list) or not 1<=len(changes)<=min(4,len(cells)):
        raise ModelOutputError('Use one to '+str(min(4,len(cells)))+' distinct scoped statement replacements.')
    def problem(index,change,error):
        errors.append({'change_index':index,
            'selector':{key:change[key] for key in ('function_id','statement_id') if isinstance(change,dict) and key in change},
            'error':str(error)[:300]})
    for index,change in enumerate(changes):
        try:validate_contract(schema(contract),change)
        except ValueError as error:
            problem(index,change,error);continue
        key=(change['function_id'],change['statement_id'])
        if key in seen:problem(index,change,'Duplicate function statement selector '+str(key)+
            '; combine all nodes for this cell in ONE change.')
        seen.add(key)
        try:replacement=(source_nodes(change['source']) if contract.get('statement_representation')=='python_source'
            else program_nodes(change['statements']))
        except (ValueError,KeyError,TypeError) as error:
            problem(index,change,error);continue
        rendered=ast.unparse(ast.Module(body=replacement,type_ignores=[]))
        if len(rendered)>1200:
            problem(index,change,'Structured Python replacement exceeds1200 rendered characters; use a smaller complete repair.');continue
        total+=len(rendered)
        prepared.append((key,change['placement'],replacement))
    if total>2400:errors.append({'error':'Combined scoped statement replacements exceed2400 rendered characters.'})
    if errors:
        error=ModelOutputError('Scoped statement proposal has independent pre-save errors; correct all reported errors: '+json.dumps(errors[:8],separators=(',',':'))+'. No source saved.')
        error.validation_errors=errors[:8]
        raise error
    for key,placement,replacement in prepared:
        cell=next(row for row in cells if (row['function_id'],row['statement_id'])==key)
        updates.setdefault(key[0],{})[tuple(cell.get('statement_path',[key[1]]))]=(placement,replacement)
    nodes=function_nodes(content,contract['functions']);lines=content.splitlines(keepends=True);splices=[];proof=[]
    for function,node in zip(contract['functions'],nodes):
        key=function_id(function)
        if key not in updates:continue
        updated=copy.deepcopy(node)
        paths=list(updates[key])
        if any(a!=b and a==b[:len(a)] for a in paths for b in paths):raise ModelOutputError('Overlapping statement scopes are not allowed; no source saved.')
        for path,(placement,replacement) in sorted(updates[key].items(),reverse=True):
            body=updated.body
            for index,field in zip(path[::2],path[1::2]):body=getattr(body[index],field)
            index=path[-1];original=body[index]
            replacement=([original]+replacement if placement=='after' else replacement+[original] if placement=='before' else replacement)
            body[index:index+1]=replacement
        if ast.dump(updated)==ast.dump(node):raise ModelOutputError('Scoped statement repair is unchanged; no source saved.')
        indentation=lines[node.lineno-1][:node.col_offset]
        rendered=textwrap.indent(ast.unparse(updated),indentation)
        if len(rendered.splitlines())>64:raise ModelOutputError('Scoped statement repair exceeds the existing64-line function observation bound; use a concise repair.')
        if ast.dump(_statements(rendered).body[0])!=ast.dump(updated):raise ModelOutputError('Scoped statement rendering changed the model AST; no source saved.')
        splices.append((node.lineno-1,node.end_lineno,rendered+('\n' if lines[node.end_lineno-1].endswith('\n') else '')))
        proof.append({'function':node.name,'model_statement_ast_preserved':True,'original_signature_retained':True,
                      'untouched_body_statements_retained':True,'controller_supplied_body':False,
                      'replaced_statement_paths':[list(path) for path in sorted(updates[key])]})
    for start,end,replacement in sorted(splices,reverse=True):lines[start:end]=[replacement]
    result=''.join(lines)
    if len(result.encode('utf-8'))>8000:raise ModelOutputError('Scoped statement repair exceeds the existing8000-byte source budget.')
    try:compile(result,'<owned statement candidate>','exec')
    except SyntaxError as error:
        raise ModelOutputError('Scoped statements are invalid in the function context: '+error.msg[:160]+'. No source saved.') from error
    return result,proof


def compile_definitions(args,contract,selected):
    """Resolve a model selector to fresh old source; all new code is model-authored."""
    from .structured_output import ModelOutputError,validate_contract
    mapping={function_id(function):span for function,span in zip(contract['functions'],selected)}
    rows=args.get('changes');seen=set();changes=[]
    if not isinstance(rows,list) or not 1<=len(rows)<=min(2,len(mapping)):
        raise ModelOutputError('Function repair needs one or two selected complete definitions; no source saved.')
    for row in rows:
        validate_contract(schema(contract),row)
        key=row['function_id']
        if key in seen:raise ModelOutputError('A function selector may occur once; no source saved.')
        seen.add(key);changes.append({'old_string':mapping[key],'new_string':row['definition']})
    return {**args,'changes':changes}


def focus(source,validation,spans,fixed_tests):
    """Positive calls only; execution is a repair scope hint, not causal proof.

    Interface/key exceptions retain their existing distinct repair contracts.
    A missing callback observation does not justify inventing an edit target.
    """
    from .source_observation import failure_context
    if not validation or validation.get('passed') or validation.get('hashes',{}).get(source['file_path'])!=source['sha256']:return None
    contexts=[failure_context(error) for error in validation.get('errors',[])[:3]]
    if not contexts or any(not context or not context['primary_error'].startswith('AssertionError:') for context in contexts):return None
    for group in validation.get('owned_execution_observations',[])[:3]:
        test=group.get('test_path');sha=group.get('test_sha256')
        if test not in fixed_tests or fixed_tests[test]!=sha or validation['hashes'].get(test)!=sha:continue
        outcomes=[row for row in validation.get('python_test_outcomes',[]) if row.get('path')==test]
        if len(outcomes)!=1 or outcomes[0].get('partial') is not False or outcomes[0].get('skipped')!=0:continue
        failed=outcomes[0].get('failed_ids',[])
        for case in group.get('cases',[])[:4]:
            if case.get('case_id') not in failed or case.get('partial') is not False or case.get('test_body_seen') is not True:continue
            functions=[]
            for call in case.get('calls',[])[:8]:
                if (call.get('phase')!='test_body' or call.get('source_path')!=source['file_path']
                        or call.get('source_sha256')!=source['sha256'] or not str(call.get('function','')).isidentifier()):continue
                function={key:call[key] for key in ('function','definition_line')}
                if function not in functions and function_nodes(source['current_source'],[function]):functions.append(function)
            if not 1<=len(functions)<=2:continue
            from .callback_contract import routes
            linked=routes(source['current_source'],functions,[call for call in case.get('calls',[])[:8] if call.get('phase')=='setup'
                and call.get('source_path')==source['file_path'] and call.get('source_sha256')==source['sha256']])
            if len(functions)==1 and linked:
                caller={'function':linked[0]['caller'],'definition_line':linked[0]['definition_line'],
                        'callsite_lines':[row['callback_line'] for row in linked if row['caller']==linked[0]['caller']]}
                if function_nodes(source['current_source'],[caller]):functions=functions+[caller]
                else:linked=[]
            selected=function_spans(source['current_source'],spans,functions)
            cells=statement_cells(source['current_source'],functions)
            use_cells=bool(linked) or len(selected)!=len(functions) or any(len(span)>1200 for span in selected)
            if use_cells and not cells:continue
            value={'test_path':test,'test_sha256':sha,'case_id':case['case_id'],'functions':functions,
                   'source_sha256':source['sha256'],'validation_evidence':validation.get('evidence'),
                   'scope':'Actual complete main-thread test-body call observations. Execution is not proof that these functions cause the assertion.'}
            if use_cells:value['statement_cells']=cells
            if linked:value['callback_routes']=linked
            return value if len(json.dumps(value))<=3500 else None
    return None


def render(args,contract):
    """Indent a complete model function at its original scope, preserving AST."""
    from .repair_contract import _statements
    from .structured_output import ModelOutputError
    changes=[];proof=[]
    allowed={(row['function'],row['definition_line']) for row in contract['functions']}
    for row in args['changes']:
        old=row.get('old_string');new=row.get('new_string')
        try:
            before=ast.parse(textwrap.dedent(old));after=_statements(new)
            if len(before.body)!=1 or len(after.body)!=1:raise ValueError()
            a,b=before.body[0],after.body[0]
            if (not isinstance(a,(ast.FunctionDef,ast.AsyncFunctionDef)) or type(a) is not type(b) or a.name!=b.name
                    or not any(name==a.name for name,line in allowed) or a.decorator_list or b.decorator_list
                    or ast.dump(a.args)!=ast.dump(b.args)):raise ValueError()
            # Optional annotations are part of the callable contract too.
            if (ast.dump(a.returns) if a.returns else None)!=(ast.dump(b.returns) if b.returns else None):raise ValueError()
            if ast.dump(a)==ast.dump(b):raise ModelOutputError('Owned function replacement is unchanged; no source saved.')
            indentation=old[:len(old)-len(old.lstrip(' \t'))]
            rendered=textwrap.indent(ast.unparse(after),indentation)
            if ast.dump(_statements(rendered))!=ast.dump(after):raise ValueError()
        except SyntaxError as error:
            raise ModelOutputError('Owned function Python is incomplete or invalid: '+error.msg[:160]+' at replacement line '
                +str(error.lineno)+'. Supplied '+str(len(new))+' of1200 allowed characters. Emit a COMPLETE concise definition '
                'within1200 characters; do not copy an unchanged long prefix. No source saved.') from error
        except (ValueError,TypeError,AttributeError) as error:
            if isinstance(error,ModelOutputError):raise
            raise ModelOutputError('Owned function repair requires one complete Python function with its original name, arguments, annotations and scope. No initializer or outside statements; no source saved.') from error
        changes.append({'old_string':old,'new_string':rendered})
        proof.append({'function':a.name,'model_ast_preserved':True,'controller_supplied_body':False,
                      'definition_sha256':hashlib.sha256(ast.dump(after).encode()).hexdigest()})
    return {**args,'changes':changes},proof
