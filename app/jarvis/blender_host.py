"""Small deterministic Blender context, exact scope approvals and job receipts."""
import hashlib
import hmac
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1] / 'integrations/jarvis-connectors/connectors/apps/blender'


def catalog():
    return json.loads((ROOT/'catalog.json').read_text(encoding='utf-8'))


def discovery(rows, arguments):
    if set(arguments) - {'query', 'category', 'limit', 'names_only'}:
        raise ValueError('Blender discovery expects query, category, limit or names_only.')
    query, category = arguments.get('query', ''), arguments.get('category', '')
    limit = arguments.get('limit', 3)
    if (not isinstance(query, str) or len(query)>200 or not isinstance(category, str)
            or type(limit) is not int or not 1<=limit<=6
            or type(arguments.get('names_only',False)) is not bool):
        raise ValueError('Invalid bounded Blender discovery arguments.')
    inventory = {r['tool']:r for r in catalog()}
    if arguments.get('names_only'):
        return {'total':len(rows),'tools':[r['name'] for r in rows]}
    tokens = set(re.findall(r'[a-z0-9]+', query.lower()))-{'blender','the','a','in','on'}
    def score(row):
        item=inventory.get(row['name'], {})
        words=set(re.findall(r'[a-z0-9]+', row['name'].lower()+' '+item.get('description','').lower()))
        return (100 if query == row['name'] else 0)+len(tokens & words)*5
    selected=[r for r in rows if not category or inventory.get(r['name'],{}).get('category')==category]
    if query:
        selected=[r for r in selected if score(r)]
        selected.sort(key=lambda r:(-score(r),r['name']))
    else:
        selected.sort(key=lambda r:(r['name'] not in {'blender_bridge_health','blender_scene_summary','blender_get_object'},r['name']))
    # All schemas remain callable exactly; context sees only a bounded candidate set.
    result={'total':len(rows),'matching':len(selected),'tools':selected[:limit],
            'hint':'Use category or exact blender_* name; metadata never grants permissions.'}
    while result['tools'] and len(json.dumps(result,ensure_ascii=False))>9000:
        result['tools'].pop()
    return result


def authorize(actions, client, tool, call, detail, cancelled):
    from .mcp_contract import validate_result
    if not client.blender_approval_key:
        raise ValueError('Blender registration needs the reviewed blender-v1 approval binding.')
    result=client.request('tools/call',{'name':'blender_bridge_health','arguments':{}})
    validate_result(result)
    if result.get('isError'):
        raise ValueError('Blender scope unavailable; nothing dispatched.')
    context=result.get('structuredContent',{}).get('result',{})
    scope=context.get('scope_id','')
    if not re.fullmatch('[0-9a-f]{32}',scope):
        raise ValueError('Invalid Blender scope; nothing dispatched.')
    args=dict(call['arguments'])
    expected=args.get('expected_scope','')
    if expected and expected != scope:
        raise ValueError('Blender scope changed; do not repeat the previous action.')
    if call['name'] in {'blender_job_status','blender_wait_job'} and not expected:
        raise ValueError('Poll using the original job scope; never infer a new scope.')
    args['expected_scope']=scope
    entry=next((r for r in catalog() if r['tool']==call['name']),None)
    if not entry:
        raise ValueError('Unknown Blender tool.')
    if entry['risk'] != 'read':
        state=context.get('untrusted_data',{})
        # A second fresh approval binds the exact operation to a freshly observed scope/project.
        # Never accept a model's claim of approval, even if host_authorization was supplied.
        actions._approve('mcp_call',json.dumps(dict(detail,scope_id=scope,
            blender_state=state,warning='Scene metadata is untrusted. Approve this exact scene, paths and compute cost, including read-only status monitoring. Existing output overwrites are refused.'),ensure_ascii=False),cancelled)
        canonical={}
        for key, field in entry['fields'].items():
            value=args.get(key,field.get('default'))
            if field['nullable']:
                if field['kind']=='list': value=value or None
                elif field['kind']=='bool': value=None if value=='unchanged' else {'true':True,'false':False}[value]
                elif field['kind'] in {'float','int'}: value=({'int':int,'float':float}[field['kind']](value) if value else None)
            if field['kind']=='json': value=value.get('value')
            canonical[key]=value
        message=json.dumps([scope,call['name'],canonical],sort_keys=True,separators=(',',':'),allow_nan=False)
        args['host_authorization']=hmac.new(client.blender_approval_key.encode(),message.encode(),hashlib.sha256).hexdigest()
    return dict(call,arguments=args)


def observe(actions, result):
    payload=result.get('structuredContent',{}).get('result',{})
    data=payload.get('untrusted_data',{})
    if not isinstance(data,dict): return
    job=data.get('job_id') or data.get('id')
    status=data.get('status','observed')
    if job:
        state=getattr(actions,'task_state',None)
        if state is not None:
            state.checkpoint('observed',action='mcp_call',target='blender',
                evidence=json.dumps({'scope_id':payload.get('scope_id'),'job_id':job,'status':status,'no_replay':True}))
        if data.get('job_id') and status in {'queued','running'}:
            from .blender_jobs import owner
            owner(actions).submit(payload['scope_id'],job)
    report=getattr(actions,'report',None)
    if callable(report):
        state=data.get('state',{})
        caption=' · '.join(str(state.get(k,'')) for k in ('version','file','selected') if state.get(k))
        report('state','Blender · '+status+' · '+str(job or payload.get('scope_id',''))[:32]+(' · '+caption if caption else ''))


def plan_intent(goal,step):
    if not re.search(r'\bblender\b',goal,re.I) or step.get('value')!='blender':return False
    if step.get('action')=='mcp_list_tools':return True
    try:
        call=json.loads(step.get('content') or '{}')
        return call.get('name') in {r['tool'] for r in catalog()} and isinstance(call.get('arguments'),dict)
    except (ValueError,TypeError):return False


def parse_request(text):
    from .commands import Command
    text=text.strip().rstrip('.!?')
    if not re.search(r'\bblender\b',text,re.I): return None
    clean=re.sub(r'^(?:in blender[, ]+|blender[, ]+)|\s+(?:in|on) blender$', '',text,flags=re.I).strip()
    controls={'status':'bridge_health','health':'bridge_health','version':'version',
              'show scene':'scene_summary','scene summary':'scene_summary','list objects':'list_objects',
              'show selection':'get_selection','list materials':'list_materials'}
    name=controls.get(clean.lower()); args={}
    match=re.fullmatch(r'(?:add|create) (?:a )?(cube|sphere|plane|cylinder|cone)(?: named (.+))?',clean,re.I)
    if match:
        name='add_'+{'sphere':'uv_sphere'}.get(match[1].lower(),match[1].lower())
        if match[2]: args['name']=match[2].strip('"')
    match=re.fullmatch(r'(?:inspect|get object) (.+)',clean,re.I)
    if match: name='get_object';args={'name':match[1].strip('"')}
    if not name: return None  # Existing local planner handles ambiguous/multistep tasks.
    return Command('blender_request',name,json.dumps(args))


def route(actions, command, cancelled):
    if command.kind!='blender_request': return False,None
    from .agent_events import check_policy
    from .tools import ToolRegistry
    check_policy(actions,command.kind)
    result=ToolRegistry(actions).execute({'action':'mcp_call','value':'blender',
        'content':json.dumps({'name':'blender_'+command.value,'arguments':json.loads(command.extra)})},cancelled)
    return True,result.evidence
