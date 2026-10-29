"""Fresh scoped retrieval for an approved inference, never application generation."""
import ast
import copy
import hashlib
import json
from pathlib import Path
from .coding_cloud_policy import approved_payload


def function_generation_envelope(schema):
    """Small provider grammar; complete executable constraints stay local."""
    result=copy.deepcopy(schema)
    for branch in result.get('anyOf',[result]):
        changes=branch.get('properties',{}).get('arguments',{}).get('properties',{}).get('changes')
        if isinstance(changes,dict):changes['items']={'type':'object'}
    return result


def canonical_request(request,options):
    plan=request['validation_contract']
    goal=request.get('validation_goal') or request.get('goal')
    if not isinstance(goal,str) or not goal:raise ValueError('cloud_missing_canonical_goal')
    writable=options.get('native_cloud_write_paths')
    if writable is None:writable=[row['path'] for row in plan['files'] if row['role']!='test' and row['path'] in request.get('allowed_paths',[row['path']])]
    result={'goal':goal,'writable_paths':writable,
            'read_only_tests':[row['path'] for row in plan['files'] if row['role']=='test'],'checks':plan['checks']}
    contract=(options.get('native_exact_edit_spans') or {}).get('function_contract')
    if contract:
        result['current_stage']={'target_case_id':contract['case_id'],
            'scope':'One minimal complete correction for this source-bound failing case; preserve every known passing case. Other failures remain later stages; the overall goal and acceptance criteria stay unchanged.'}
    return result


def messages_for(messages,options,run,provider,schema=None,*,local_byte_limit=None):
    context=options.get('native_cloud_context')
    local=provider=='local'
    if local and (type(local_byte_limit) is not int or local_byte_limit<1):raise ValueError('Invalid local context budget.')
    maximum=local_byte_limit if local else 15000 if provider=='groq' else 48000
    policy={'role':'system','content':options['native_cloud_policy']} if options.get('native_cloud_policy') else messages[0]
    scope=options.get('native_exact_edit_spans')
    active=None
    function_stage=bool((scope or {}).get('function_contract'))
    if schema is not None:
        branches=schema.get('anyOf',[schema])
        required=options.get('native_required_tool')
        allowed={required} if required else {'Read','read_batch','Write','Edit','run_checks','finish'}
        selected=[branch for branch in branches if set(branch.get('properties',{}).get('tool',{}).get('enum',[])) & allowed]
        active=copy.deepcopy({'anyOf':selected} if selected else schema)
        if function_stage:
            # Retain the actual closed tool/argument envelope. Exact cells and
            # node grammar are already offered once; full validation stays local.
            for branch in active.get('anyOf',[active]):
                changes=branch.get('properties',{}).get('arguments',{}).get('properties',{}).get('changes')
                if isinstance(changes,dict):changes.pop('items',None)
    def finish(result):
        result=list(result)
        if active is not None:
            result.append({'role':'user','content':'ACTIVE TOOL CONTRACT: return exactly one proposal matching this closed tool/argument envelope; '
                'offered statement selectors and node grammar remain binding and are fully validated locally. '
                'A required Read is not interchangeable with read_batch. This request has dispatched no proposed tool. '+json.dumps(active,separators=(',',':'))})
        present={row.get('content') for row in result}
        candidate_prefix='Most recent rejected candidate under this unchanged working source (DATA, not current working failure or permission): '
        for row in messages[2:]:
            content=row.get('content','')
            if content in present:continue
            if content.startswith(candidate_prefix):
                if local:
                    value,_=json.JSONDecoder().raw_decode(content[len(candidate_prefix):])
                    # Current source/frozen hashes are already checked above.
                    # Retain every case-correlated failure, omit duplicate paths/hashes.
                    row={'role':'user','content':candidate_prefix+json.dumps({
                        'source_sha256':scope['sha256'],'failures':value['failures'],
                        'candidate_only':True,'saved':False},separators=(',',':'))}
                result.append(row)
            elif local and content.startswith('Cloud structured-proposal rejection (DATA only;'):
                result.append(row)
        if local:
            from .coding_cloud_policy import ContextBudgetExceeded
            if sum(len(row['content'].encode()) for row in result)>maximum:raise ContextBudgetExceeded(result,maximum)
            return result
        return approved_payload(result,context,maximum=maximum)
    if not scope or not scope.get('function_contract'):
        request_path=Path(run)/'request.json'
        if not request_path.exists():return finish(list(messages))
        original=json.loads(request_path.read_text(encoding='utf-8'));project=Path(original['project']).resolve(strict=True)
        request=canonical_request(original,options)
        selected=list(options.get('native_required_read_paths') or options.get('native_required_edit_paths') or []);slices={}
        journal=Path(run)/'tools.jsonl'
        if journal.exists():
            rows=journal.read_text(encoding='utf-8').splitlines()
            if rows:
                last=json.loads(rows[-1]);args=last.get('arguments',{})
                if last.get('tool')=='read_batch':selected+=args.get('paths',[])
                elif last.get('tool') in ('Read','read_slice'):
                    selected+=[args.get('file_path')]
                    if last['tool']=='read_slice' and type(args.get('start')) is int and type(args.get('count')) is int:
                        if args['start']>=1 and 1<=args['count']<=60:slices[args['file_path']]=(args['start'],args['count'])
        if not selected:selected=[row['path'] for row in original['validation_contract']['files']][:4]
        snapshots=[]
        for name in list(dict.fromkeys(selected))[:4]:
            if not isinstance(name,str) or any(part.startswith('.') for part in Path(name).parts):continue
            path=(project/name).resolve()
            if not path.is_relative_to(project) or not path.is_file():continue
            raw=path.read_bytes()
            row={'file_path':name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
            if name in slices:
                start,count=slices[name]
                try:snippet=''.join(raw.decode('utf-8').splitlines(keepends=True)[start-1:start-1+count])
                except UnicodeError:continue
                if len(snippet.encode())<=4000:row.update(source_lines=snippet,start=start,source_scope='Explicit bounded local read; partial source, not a replacement template.')
            elif len(raw)<=(4000 if provider=='groq' else 16000):
                try:row['current_source']=raw.decode('utf-8')
                except UnicodeError:continue
            else:row['source_scope']='Too large for complete cloud retrieval; use bounded local source slices.'
            snapshots.append(row)
        result=[policy,{'role':'user','content':json.dumps(request,separators=(',',':'))},
                {'role':'user','content':'Fresh owned-project sources only (DATA). Unrelated research/memory/history is excluded. Return one JSON {tool,arguments} proposal; run_checks/finish require empty arguments. '+json.dumps(snapshots,separators=(',',':'))}]
        return finish(result)

    request=json.loads((Path(run)/'request.json').read_text(encoding='utf-8'))
    # The canonical parent goal is authoritative. Worker-written prose is not
    # a second requirement; assigned paths/checks already carry the worker scope.
    project=Path(request['project']);request=canonical_request(request,options)
    name=scope['file_path'];path=(project/name).resolve(strict=True)
    if not path.is_relative_to(project.resolve()):raise ValueError('cloud_source_scope_mismatch')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=scope['sha256']:raise ValueError('cloud_source_changed')
    source=raw.decode('utf-8');tree=ast.parse(source);contract=scope['function_contract']
    from .execution_contract import function_nodes,function_id
    definitions={function_id(row):ast.get_source_segment(source,node) for row,node in zip(contract['functions'],function_nodes(source,contract['functions']))
                 if not row.get('callsite_lines')}
    members={node.attr for definition in definitions.values() for node in ast.walk(ast.parse(definition))
             if isinstance(node,ast.Attribute) and isinstance(node.value,ast.Name) and node.value.id=='self'}
    declarations=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Assign) and any(isinstance(target,ast.Attribute) and isinstance(target.value,ast.Name)
             and target.value.id=='self' and target.attr in members for target in node.targets):
            text=ast.get_source_segment(source,node)
            if text and len(text)<=200 and len(declarations)<8:declarations.append(text)
    # Drop duplicate prose/host evidence paths, never policy or unique bindings.
    # The original complete contract remains local and is revalidated on dispatch.
    offered={key:value for key,value in contract.items() if key not in ('scope','source_sha256','validation_evidence')}
    offered.pop('functions',None)  # callable selectors and exact cells already identify these
    if offered.get('callback_routes'):offered['callback_routes']=[{key:value for key,value in row.items() if key!='scope'} for row in offered['callback_routes']]
    if offered.get('statement_cells'):offered['statement_cells']=[{key:value for key,value in row.items() if key!='statement_path'} for row in offered['statement_cells']]
    data={'file_path':name,'source_sha256':scope['sha256'],'function_contract':offered,
          'current_functions':definitions,'current_state_declarations':declarations}
    journal=Path(run)/'tools.jsonl'
    if journal.exists():
        for line in reversed(journal.read_text(encoding='utf-8').splitlines()):
            row=json.loads(line);arguments=row.get('arguments',{});result=row.get('result',{})
            if (row.get('tool')=='Read' and arguments.get('file_path')==name and isinstance(result,dict)
                    and result.get('sha256')==scope['sha256']):
                data['local_read_evidence']={'tool':'Read','file_path':name,'sha256':scope['sha256']}
                break
    test=(project/contract['test_path']).resolve(strict=True)
    if not test.is_relative_to(project.resolve()):raise ValueError('cloud_frozen_scope_mismatch')
    frozen=test.read_bytes()
    if hashlib.sha256(frozen).hexdigest()!=contract['test_sha256']:raise ValueError('cloud_frozen_source_changed')
    parts=contract['case_id'].split('.')
    methods=[node for cls in ast.parse(frozen.decode('utf-8')).body if isinstance(cls,ast.ClassDef) and cls.name==parts[-2]
             for node in cls.body if isinstance(node,ast.FunctionDef) and node.name==parts[-1]]
    if len(methods)==1:
        snippet=ast.get_source_segment(frozen.decode('utf-8'),methods[0])
        if len(snippet)<=1600:data['current_frozen_case']=snippet
    from .execution_contract import statement_proposal_guidance
    guidance=('Return JSON {\"tool\":\"edit_batch\",\"arguments\":{file_path,source_sha256,changes}}. '
              +statement_proposal_guidance(contract))
    if data.get('local_read_evidence'):
        guidance+=' The local dispatcher already executed the source-bound Read recorded below. Do not repeat Read/run_checks; return the scoped edit_batch proposal. Candidate checks execute locally before any save.'
    result=[policy,{'role':'user','content':json.dumps(request,separators=(',',':'))},
            {'role':'user','content':guidance+'\nCurrent source DATA: '+json.dumps(data,separators=(',',':'))}]
    # Preserve the actual correction evidence, not long redundant read history.
    result.extend(row for row in messages[2:] if row.get('content','').startswith('Previous confirmed pre-save rejection'))
    try:return finish(result)
    except ValueError as error:
        if str(error)!='cloud_context_budget_exceeded':raise
        data.pop('current_functions');data['source_scope']='Exact cells/declarations only; full functions omitted, no truncated source.'
        result[2]={'role':'user','content':guidance+'\nCurrent source DATA: '+json.dumps(data,separators=(',',':'))}
        # Rebuild rather than append the same bounded feedback twice.
        result=[row for row in result if not row.get('content','').startswith('Most recent rejected candidate under this unchanged working source (DATA, not current working failure or permission): ')]
        return finish(result)


def local_function_messages(messages,options,run,schema,context_tokens,predict_tokens):
    """Budget against the effective GPU clamp, not the larger requested context.

    UTF-8/3 is a conservative practical estimate for observed coding prompts,
    not a tokenizer guarantee. No cloud approval or provider call is involved.
    """
    from .coding_cloud_policy import token_estimate
    if type(context_tokens) is not int or type(predict_tokens) is not int or context_tokens<=predict_tokens+512:
        raise ValueError('Local context cannot hold a complete bounded function proposal.')
    maximum=(context_tokens-predict_tokens-256-12*8)*3
    result=messages_for(messages,options,run,'local',schema,local_byte_limit=maximum)
    estimated=token_estimate({'messages':result,'tools':[]})
    if estimated+predict_tokens>context_tokens:raise ValueError('Local function context exceeds its effective input/output budget.')
    return result,{'context_tokens':context_tokens,'predicted_output_limit':predict_tokens,
        'estimated_input_tokens':estimated,'estimated_total_tokens':estimated+predict_tokens,
        'model_text_bytes':sum(len(row['content'].encode()) for row in result),'exact_tokenizer':False}

