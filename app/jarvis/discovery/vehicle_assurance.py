"""Read-only whole-goal evidence gate for requested F1 engineering work.

Called by the existing planner's bounded correction loop. Browsing success,
screenshots, model prose and a conditional numerical subtask cannot certify
an entire scientific project. Gaps remain in the existing task checkpoint.
"""
import re
from urllib.parse import urlsplit,parse_qs
from .catalog import enabled


def applies(config,goal):
    return bool(enabled(config,'sim') and re.search(r'\b(?:F1|formula\s*(?:one|1))\b',goal,re.I)
                and re.search(r'\b(?:simulate|simulation|dynamics|active aero)\b',goal,re.I))


def audit(actions,goal):
    if not applies(getattr(actions,'config',{}),goal):return {'applies':False,'passed':False}
    required=sorted(set(int(y) for y in re.findall(r'\b(2025|2026)\b',goal)))
    checks={str(year):{'controlled_solver':False,'spatial_active_aero':year!=2026,
        'licensed_asset_identity':False,'native_visual_and_functional_assembly':False,
        'track_and_terminal_speed_validation':False,'reproducible_complete_report':False} for year in required}
    if not checks:checks={'requested_variant':{'exact_variant_resolved':False}}
    issues=[]
    from ..task_state import TaskState
    state=getattr(actions,'task_state',None)
    task_id=state.running_identity() if isinstance(state,TaskState) else None
    service=getattr(actions,'_neural_service',None)
    if task_id is None or service is None:
        issues.append('No current-task Journal solver evidence is available.')
    else:
        journal=service.journal
        from .acceptance import artifact
        from .model.vehicle import VehicleCase,validate_result
        from .adapters.chrono import worker_hash
        tables={r['name'] for r in journal.rows("SELECT name FROM sqlite_master WHERE type='table'")}
        if {'discovery_planner_calls','discovery_vehicle_runs'}<=tables:
            calls=journal.rows("SELECT proposal_ref,result_ref FROM discovery_planner_calls WHERE state='done'")
            for call in calls:
                try:
                    proposal=artifact(journal,call['proposal_ref'])
                    if proposal.get('task_id')!=task_id:continue
                    request=proposal['proposal']
                    if request['command']!='lab compare vehicle "{request}"':continue
                    from .vehicle_wire import parse
                    case=parse(__import__('json').dumps(request['request']))
                    if str(case.year) not in checks:continue
                    child=artifact(journal,call['result_ref'])
                    if not child.get('verified') or child.get('autonomous_task_id')!=task_id:raise ValueError('child task binding missing')
                    goal_row=journal.goal(child['goal_id'])
                    if not goal_row or goal_row['state']!='verified':raise ValueError('child goal not independently verified')
                    rows=journal.rows('SELECT result_ref,state FROM outbox WHERE goal_id=? AND node_id=?',
                        (child['goal_id'],'discovery.vehicle.compare@v1'))
                    if len(rows)!=1 or rows[0]['state']!='done':raise ValueError('actual producer outbox missing')
                    public=artifact(journal,artifact(journal,rows[0]['result_ref'])['report'])
                    result=artifact(journal,public['run_ref']);validate_result(case,result)
                    receipt=journal.rows('SELECT worker_sha256 FROM discovery_vehicle_runs WHERE ref=?',(public['run_ref'],))
                    if len(receipt)!=1 or receipt[0]['worker_sha256']!=worker_hash():raise ValueError('current solver receipt missing')
                    checks[str(case.year)]['controlled_solver']=True
                    checks[str(case.year)]['spatial_active_aero']=True
                    # This adapter explicitly declares flat-terrain surrogate and
                    # observed-speed limitations. Do not infer asset/track/visual
                    # completion from its unrelated numerical success.
                except Exception:
                    issues.append('A retained vehicle call failed current-task/input/receipt verification.')
        else:issues.append('No controlled vehicle-comparison execution is recorded.')
    missing=[era+': '+name for era,row in checks.items() for name,passed in row.items() if not passed]
    return {'applies':True,'passed':bool(checks) and not missing and not issues,
            'checks':checks,'missing':missing,'issues':issues,'source':'deterministic current-task Journal audit',
            'physical_validation':False}


def completion_error(actions,goal):
    verdict=audit(actions,goal)
    if not verdict['applies'] or verdict['passed']:return None
    return ('Independent scientific whole-goal verification rejected completion. Missing actual evidence: '
            +'; '.join(verdict['missing'])+'. '+' '.join(verdict['issues'])
            +' Inspect available Lab help/source tools and complete supported prerequisites. '
            'Do not repeat completed navigation, invent assets/results, treat a conditional subtest as full acceptance, '
            'or bypass permissions. If a required capability is unavailable, preserve the checkpoint and state the precise blocker.')[:1800]


def asset_query_error(config,goal,query,*,catalog_search=False):
    """Preserve explicit target years in whole-vehicle asset queries.

    This derives constraints only from the user's goal, not a supervisor's
    chassis/model knowledge. General API documentation and component searches
    remain available; no query or user objective is silently rewritten.
    """
    if not applies(config,goal) or not isinstance(query,str):return None
    years=set(re.findall(r'\b(20\d{2})\b',goal))
    if len(years)!=1:return None
    brand=re.search(r'\b20\d{2}\s+([A-Z][A-Za-z0-9_-]+)',goal)
    names=r'\b(?:F1|formula\s*(?:one|1)|car|vehicle)\b'
    identity=bool(re.search(names,query,re.I) or (brand and re.search(r'\b'+re.escape(brand[1])+r'\b',query,re.I)))
    asset=catalog_search or bool(re.search(r'\b(?:models?|meshes?|3d|CAD|download(?:able)?|sketchfab)\b',query,re.I))
    documentation=bool(re.search(r'\b(?:API|SDK|documentation|authentication|endpoint)\b',query,re.I))
    if identity and asset and not documentation and not any(year in query for year in years):
        return ('The user explicitly requested the '+next(iter(years))+' vehicle variant. This whole-vehicle asset query '
                'drops that identity constraint and can return a different road/race car. Retain the requested year '
                'in the query; do not silently substitute a different variant. No search was executed from this proposal.')
    return None


def search_step_error(config,goal,step):
    if step.get('action') in ('web_search','browser_search'):
        return asset_query_error(config,goal,step.get('value',''))
    if step.get('action')=='discovery_call':
        match=re.fullmatch(r'lab assets search "([^"\r\n]+)"',step.get('value',''),re.I)
        return asset_query_error(config,goal,match[1],catalog_search=True) if match else None
    if step.get('action')=='web_open':
        try:
            parts=urlsplit(step.get('value',''))
            host=(parts.hostname or '').casefold()
            if host in ('www.bing.com','bing.com','www.google.com','google.com','duckduckgo.com','www.duckduckgo.com'):
                query=parse_qs(parts.query).get('q',[''])[0]
                return asset_query_error(config,goal,query)
        except ValueError:return None
    return None
