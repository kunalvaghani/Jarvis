"""General public model discovery, independent per-file rights and honest blockers.

All object-specific repository/model IDs come from browser/API results. No F1
asset URL, mesh, solver configuration or numerical answer is embedded here.
"""
from pathlib import PurePosixPath
import re
from urllib.parse import quote,urlencode,urlsplit
from .browser_research import research
from .provider_metadata import MetadataClient
from .asset_rights import issue,FORMATS,named_year
from .literature import public_query


class ResearchCancelled(ValueError):pass


def unsuitable_title(title):
    """An author's explicit withdrawal is not a suitable engineering reference."""
    return bool(re.search(r'(?i)\b(?:outdated|inaccurate|obsolete|deprecated|superseded)\b',str(title)))


def failure(exc):
    # Error messages can contain untrusted page text or URLs. Keep only closed
    # actionable categories, rather than persisting arbitrary exception strings.
    from ..sandbox.budget import BudgetExceeded
    if isinstance(exc,BudgetExceeded):return 'DAILY_RESOURCE_ALLOWANCE_EXHAUSTED'
    message=str(exc).lower()
    if 'exhausted' in message:return 'PROJECT_METADATA_ALLOWANCE_EXHAUSTED'
    if 'required object year' in message:return 'SOURCE_IDENTITY_YEAR_MISMATCH'
    if 'license' in message or 'rights' in message:return 'PER_ASSET_RIGHTS_NOT_QUALIFIED'
    if 'timed out' in message or isinstance(exc,TimeoutError):return 'PROVIDER_TIMEOUT'
    if isinstance(exc,(KeyError,TypeError,AttributeError)):return 'PROVIDER_SCHEMA_CHANGED'
    return 'PROVIDER_OR_EVIDENCE_REJECTED'


def discover(actions,journal,project_id,query,*,target_year=None,cancelled=lambda:False,client=None,registry_factory=None):
    def check_cancelled():
        if cancelled():raise ResearchCancelled('asset research cancelled; no further provider operations')
    check_cancelled()
    query=public_query(query)
    if target_year is not None and str(target_year) not in query:raise ValueError('research query dropped required object year')
    client=client or MetadataClient(actions.base,journal,project_id,cancelled=cancelled)
    def get(provider,url):
        check_cancelled();value=client.get(provider,url);check_cancelled();return value
    browser=research(actions,query,cancelled,registry_factory=registry_factory)
    check_cancelled()
    # Store data and actual call references, never webpage instructions.
    browser_ref=journal.put(browser,'Report')
    qualified=[];blocked=[];source_refs=[]
    uids=[];repos=[]
    for item in browser['candidates']:
        p=urlsplit(item['url']);parts=p.path.strip('/').split('/')
        if item['provider']=='sketchfab.com':
            m=re.search(r'([a-f0-9]{32})$',p.path)
            if m and m[1] not in uids:uids.append(m[1])
        if item['provider']=='github.com' and len(parts)>=2 and all(re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',v) for v in parts[:2]):
            name='/'.join(parts[:2])
            if name not in repos:repos.append(name)
    try:
        def search_models():
            catalog_query=re.sub(r'(?i)\bF1\s+class\b','F1',query)
            ref,search=get('sketchfab','https://api.sketchfab.com/v3/search?'+urlencode({'type':'models','downloadable':'true','count':24,'q':catalog_query}))
            source_refs.append(ref)
            if not isinstance(search,dict) or not isinstance(search.get('results'),list):raise ValueError('provider search schema changed')
            candidates=[row for row in search['results'] if isinstance(row,dict) and re.fullmatch(r'[a-f0-9]{32}',str(row.get('uid','')))]
            for row in candidates:
                if target_year is not None and named_year(str(row.get('name','')))!=target_year:
                    blocked.append({'provider':'sketchfab','candidate':row['uid'],'reason':'SOURCE_IDENTITY_YEAR_MISMATCH','stage':'search_identity'})
                if unsuitable_title(row.get('name','')):
                    blocked.append({'provider':'sketchfab','candidate':row['uid'],'reason':'AUTHOR_MARKED_OUTDATED_OR_INACCURATE','stage':'search_suitability'})
            return [row['uid'] for row in candidates if not unsuitable_title(row.get('name',''))
                and (target_year is None or named_year(str(row.get('name','')))==target_year)][:2]
        searched=not uids
        if searched:uids=search_models()
        license_ref=None;seen=set()
        for route_number in range(2):
            if not uids:break
            if license_ref is None:
                license_ref,_=get('sketchfab','https://api.sketchfab.com/v3/licenses');source_refs.append(license_ref)
            for uid in uids[:2]:
                if uid in seen:continue
                seen.add(uid)
                try:
                    ref,model=get('sketchfab','https://api.sketchfab.com/v3/models/'+uid);source_refs.append(ref)
                    if unsuitable_title(model.get('name','')):
                        blocked.append({'provider':'sketchfab','candidate':uid,'reason':'AUTHOR_MARKED_OUTDATED_OR_INACCURATE','stage':'model_suitability'})
                        continue
                    admission,availability=issue(actions.base,journal,{'rule':'sketchfab-license-v1','uid':uid,
                        'model_ref':ref,'licenses_ref':license_ref},target_year=target_year)
                    qualified.append({'acquisition_ref':admission,'provider':'sketchfab','availability':availability})
                except Exception as exc:
                    check_cancelled()
                    blocked.append({'provider':'sketchfab','candidate':uid,'reason':failure(exc),'failure_type':type(exc).__name__,'source_refs':list(source_refs)})
            if searched or any(item['provider']=='sketchfab' for item in qualified):break
            # A search-result link is not the only acquisition strategy. Try
            # the official downloadable catalog after unusable browser hits.
            uids=search_models();searched=True
    except Exception as exc:
        check_cancelled()
        blocked.append({'provider':'sketchfab','reason':failure(exc),'failure_type':type(exc).__name__,'stage':'public_metadata'})
    try:
        if not repos:
            ref,search=get('github','https://api.github.com/search/repositories?'+urlencode({'q':query+' 3D CAD mesh','per_page':2}))
            source_refs.append(ref)
            if not isinstance(search,dict) or not isinstance(search.get('items'),list):raise ValueError('repository search schema changed')
            repos=[x['full_name'] for x in search['items'] if isinstance(x,dict) and re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',str(x.get('full_name','')))][:2]
        for repo in repos[:2]:
            try:
                root='https://api.github.com/repos/'+repo
                meta_ref,meta=get('github',root);source_refs.append(meta_ref)
                branch=meta['default_branch']
                commit_ref,commit=get('github',root+'/commits/'+quote(branch,safe=''));source_refs.append(commit_ref)
                revision=commit['sha']
                if not re.fullmatch(r'[a-f0-9]{40}',revision):raise ValueError('repository commit identity missing')
                tree_ref,tree=get('github',root+'/git/trees/'+revision+'?recursive=1');source_refs.append(tree_ref)
                entries=tree['tree']
                if not isinstance(entries,list):raise ValueError('repository tree schema changed')
                models=[e for e in entries if isinstance(e,dict) and e.get('type')=='blob' and PurePosixPath(e.get('path','')).suffix.lstrip('.').lower() in FORMATS]
                paths={e.get('path') for e in entries if isinstance(e,dict) and e.get('type')=='blob'}
                manifest=next((p for p in ('ASSET_LICENSES.json','MODEL_LICENSES.json') if p in paths),None)
                rights_ref=None
                if manifest:rights_ref,_=get('github',root+'/contents/'+manifest+'?ref='+revision);source_refs.append(rights_ref)
                for model in models[:8]:
                    path=model['path'];rule='github-asset-manifest-v1'
                    selected_rights=rights_ref
                    if selected_rights is None and path+'.license' in paths:
                        selected_rights,_=get('github',root+'/contents/'+quote(path+'.license',safe='/')+'?ref='+revision)
                        source_refs.append(selected_rights);rule='github-reuse-sidecar-v1'
                    if selected_rights is None:continue
                    try:
                        owner,name=repo.split('/')
                        admission,availability=issue(actions.base,journal,{'rule':rule,'owner':owner,'repo':name,'revision':revision,
                            'path':path,'tree_ref':tree_ref,'rights_ref':selected_rights},target_year=target_year)
                        qualified.append({'acquisition_ref':admission,'provider':'github','availability':availability})
                    except Exception as exc:
                        check_cancelled()
                        blocked.append({'provider':'github','candidate':path,'reason':failure(exc),'failure_type':type(exc).__name__})
                if not any(x['provider']=='github' for x in qualified):
                    blocked.append({'provider':'github','repository':repo,'stage':'per_asset_license',
                        'reason':'No selected file qualified from a per-asset rights declaration; a repository code license alone is insufficient.',
                        'model_files_observed':len(models),'tree_partial':tree.get('truncated') is True})
            except Exception as exc:
                check_cancelled()
                blocked.append({'provider':'github','repository':repo,'reason':failure(exc),'failure_type':type(exc).__name__,'stage':'public_metadata'})
    except Exception as exc:
        check_cancelled()
        blocked.append({'provider':'github','reason':failure(exc),'failure_type':type(exc).__name__,'stage':'public_metadata'})
    return {'query':query,'target_year':target_year,'browser_ref':browser_ref,'browser_status':browser['status'],
        'provider_source_refs':list(dict.fromkeys(source_refs)),'qualified_rights':qualified,'blocked_candidates':blocked,
        'original_files_acquired':0,'engineering_identity_verified':False,
        'limits':'Bounded discovery and per-file declared rights only; file acquisition, object identity, import and physics are separate gates.'}
