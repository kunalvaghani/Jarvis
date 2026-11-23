"""Resolve an explicitly requested public F1 model lookup through the same brain.

Only the user's own object words become the query. No asset, parameter values,
scientific answer or physical result is supplied. Returned provider declarations
remain untrusted; the source-verification neuron checks acquisition bytes only.
"""
import json,re
from .catalog import enabled
from .vehicle_assurance import applies


def query_from_goal(config,goal):
    if not enabled(config,'research') or not applies(config,goal):return None
    start=r'^\s*(?:please\s+)?(?:find|locate|source|search for)\s+(?:a |an |the )?(?:(?:legal|free|downloadable|licensed)\s+)*'
    after=re.match(start+r'(?:model|CAD|mesh)\s+(?:for|of)\s+(.+?)(?=[.;]|\s+and\s+(?:verify|build|run)\b|$)',goal,re.I)
    before=None if after else re.match(start+r'(.+?)\s+(?:model|CAD|mesh)\b',goal,re.I)
    match=after or before
    if not match:return None
    query=re.sub(r'\b(20\d{2})-regulation\b',r'\1',match[1],flags=re.I).strip()
    query=re.sub(r'^(?:a|an|the)\s+','',query,flags=re.I)
    if not 4<=len(query)<=200 or any(c in query for c in ('"','\r','\n','/','\\')):return None
    return query


def run(actions,goal,cancelled):
    query=query_from_goal(getattr(actions,'config',{}),goal)
    if query is None:return None
    allowed=getattr(actions,'allowed_tools',None)
    if isinstance(allowed,(set,frozenset)) and 'discovery_call' not in allowed:return None
    from ..tools import ToolRegistry
    command='lab assets search "'+query+'"'
    step={'action':'discovery_call','value':command,'content':'',
          'expected':'Read and independently verify public asset metadata for the exact user-requested variant.'}
    actions.report('brain','Lab preflight: checking public model metadata for '+query+' through the registered source adapter.')
    try:
        response=ToolRegistry(actions).execute(step,cancelled)
        child=json.loads(response.evidence)
        if child.get('verified') is not True:raise ValueError('source child not verified')
        from .acceptance import artifact
        journal=actions._neural_service.journal
        rows=journal.rows('SELECT result_ref,state FROM outbox WHERE goal_id=? AND node_id=?',
            (child['goal_id'],'discovery.assets.search_public@v1'))
        if len(rows)!=1 or rows[0]['state']!='done':raise ValueError('actual source outbox required')
        report=artifact(journal,artifact(journal,rows[0]['result_ref'])['report'])
        result=report['result']
        projection={k:result[k] for k in ('provider','query','items','source_ref','payload_sha256',
            'cached_metadata','content_is_untrusted','binary_download_performed','download_authentication_required','limits')}
        projection.update(goal_id=child['goal_id'],source_bytes_verified=True,full_goal_verified=False)
        actions.report('brain','Lab assets: '+str(len(result['items']))+' provider records cached and byte-verified; '
                       'asset identity, license suitability and binary acquisition remain separate checks.')
        return {'action':'discovery_call','value':command,'result':json.dumps(projection,ensure_ascii=False),
                'verified':True,'verification_scope':'source acquisition bytes only, not asset identity/license or full goal'}
    except Exception as exc:
        if cancelled():raise
        return {'action':'discovery_call','value':command,'result':json.dumps({'source_read_failed':True,
            'error':type(exc).__name__+': '+str(exc)[:700],'full_goal_verified':False,
            'next_action':'Use another permitted source or preserve the exact blocker; no automatic auth or binary download.'}),
            'verified':False}


def context(observation):
    """Small projection of actual retained source IDs, re-sent on every plan call.

    This is working context over the existing Journal, not a second memory.
    No engineering parameter value or case answer is generated here.
    """
    if observation.get('verified') is not True:return {}
    result=json.loads(observation['result'])
    year=re.search(r'\b20\d{2}\b',result['query'])
    items=sorted(result['items'],key=lambda i:0 if year and year[0] in i['name'] else 1)
    return {'source_refs':[result['source_ref']], 'query':result['query'],
        'content_is_untrusted':True,'verification_scope':'API bytes only; identity/license/engineering are not independently established',
        'candidate_total':len(items),
        'candidate_projection_partial':len(items)>4,'metadata_candidates':[
        {**{k:item[k] for k in ('uid','name','creator','license_declared','identity_verified','geometry_acquired')},
         'name_contains_requested_year':(year[0] in item['name']) if year else None}
        for item in items[:4]],'source_goal_id':result['goal_id'],'payload_sha256':result['payload_sha256'],
        'request_protocol':'Use actual source_refs in a structured Lab request. Author unverified physical assumptions in request JSON; no pre-existing request file is needed. Metadata details: lab assets inspect "<returned UID>".'}
