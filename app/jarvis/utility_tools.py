"""Permission-aware adapters for only the tested curated capabilities."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from .utility_profiles import BY_ID,tools
from .utility_core import scoped,read,write
from .repo_acquisition import command

TOOLS=tools()
CORE={'system_diagnostics','image_process','regex_rename','format_python','markdown_pdf','zip_extract','calendar_ics','config_validate','jwt_inspect','subtitles_srt','csv_profile','csv_parquet','prompt_inspect','symlink','ocr_image','ffmpeg_audio','strip_exif','security_audit'}
SERVICES={'port_check','ssl_check','rss_fetch','api_fuzz','mongodb','redis','slack_approval','github_comment','sms_send'}


def core_call(actions,name,root,args,cancelled):
    python=Path(actions.base)/'.venv-skills/Scripts/python.exe'
    if not python.is_file():raise ValueError('Separate utility environment is missing; run utility setup.')
    args=dict(args)
    if name=='ocr_image':args['_tesseract']=shutil.which('tesseract')
    raw=command([str(python),'-m','jarvis.utility_worker'],cancelled,40,json.dumps({'name':name,'root':str(root),'arguments':args}).encode(),1000000)
    result=json.loads(raw)
    if result.get('ok') is not True:raise ValueError('Utility failed: '+str(result.get('error_type'))+': '+str(result.get('error')))
    return result['value']


def key_for(actions,identifier,create):
    import win32crypt
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,60}',identifier):raise ValueError('Use a bounded key identifier, never key material.')
    root=Path(actions.base)/'.jarvis-runtime/utility-secrets';root.mkdir(parents=True,exist_ok=True)
    path=scoped(root,identifier+'.dpapi')
    if not path.exists():
        if not create:raise ValueError('Encryption key is unavailable; source is preserved.')
        key=base64.urlsafe_b64encode(os.urandom(32));protected=win32crypt.CryptProtectData(key,'Jarvis utility file key',None,None,None,0)
        write(path,protected)
    return win32crypt.CryptUnprotectData(read(path),None,None,None,0)[1].decode()


def run(actions,name,root,args,cancelled):
    if name not in BY_ID:raise ValueError('Unknown requested skill.')
    if not isinstance(args,dict) or any(k.startswith('_') for k in args):raise ValueError('Internal credential/fixture arguments are not planner inputs.')
    from .utility_profiles import schema
    from .repo_analysis import validate
    validate(schema(name)['properties']['arguments'],args)
    required=BY_ID[name][2].split()
    if set(required)-args.keys():raise ValueError('Missing required skill arguments: '+', '.join(sorted(set(required)-args.keys())))
    if cancelled():raise ValueError('Skill cancelled before dispatch.')
    effect=BY_ID[name][3]
    if name=='mongodb' and args.get('operation')=='find':effect=False
    if name=='redis' and args.get('operation')=='get':effect=False
    if name=='regex_rename' and args.get('dry_run',True):effect=False
    if name=='gmail_chrome' and args.get('operation') in {'inspect','verify_draft'}:effect=False
    # Every effect is approved at execution, not by the model or guide text.
    if effect:
        detail={'skill':name,'project':str(root),'arguments':args}
        if name in {'env_set','jwt_inspect'}:detail['arguments']={k:('[private value]' if k in {'value','token'} else v) for k,v in args.items()}
        actions._approve('utility_'+name,json.dumps(detail),cancelled)
    if name in CORE:return core_call(actions,name,root,args,cancelled)
    if name in SERVICES:
        # Service SDKs run in the separate utility dependency interpreter.
        from .utility_service_transport import call
        return call(actions,name,args,cancelled)
    if name in {'file_crypto','agent_state'}:
        operation=args['operation'];prepared=dict(args)
        if name=='file_crypto':
            if operation not in {'encrypt','decrypt'}:raise ValueError('Use encrypt or decrypt.')
            prepared['_key']=key_for(actions,args['key_id'],operation=='encrypt');target='encrypt_file' if operation=='encrypt' else 'decrypt_file'
        else:
            if operation not in {'save','load'}:raise ValueError('Use save or load.')
            target='state_save' if operation=='save' else 'state_load'
        return core_call(actions,target,root,prepared,cancelled)
    if name in {'notebook_execute','nmap_scan'}:
        from .utility_isolation import run as isolated
        if name=='nmap_scan':return isolated('nmap',args,cancelled=cancelled)
        source=scoped(root,args['source']);read(source)
        result=isolated('notebook',{},source,cancelled)
        saved=write(scoped(root,args['output']),result.pop('notebook').encode(),args.get('overwrite',False));return {**saved,**result,'host_execution':False,'network':'disabled'}
    if name=='gmail_chrome':
        from .ui_transport import UITransport
        transport=UITransport(actions.base,timeout=30,module='jarvis.gmail_chrome_worker')
        try:
            if args['operation']=='open':
                existing=transport.request({'operation':'open'},cancelled)
                if not existing['create_tab_needed']:return existing
                from .browser import browser_args
                import subprocess
                subprocess.Popen([*browser_args(actions.apps,'chrome'),'https://mail.google.com/'],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                return {'opened_existing_profile':False,'new_tab_requested':True,'profile_mode':'existing configured Chrome launch; no cookies copied','sent':False,'verification_required':True}
            return transport.request(args,cancelled)
        finally:transport.close()
    from .utility_host import execute
    return execute(actions,name,root,args,cancelled)


def execute(actions,step,cancelled):
    name=step['action'].removeprefix('skill_')
    if step['action'] not in tools(actions.base):raise ValueError('Capability validation is missing or stale; revalidate before use.')
    root=Path(actions.base if name=='gmail_chrome' else actions._task_folder(step.get('folder',''),cancelled)).resolve(strict=True)
    if root==Path(root.anchor):raise ValueError('Select one explicit project, not a drive.')
    args=json.loads(step.get('content') or '{}')
    return json.dumps(run(actions,name,root,args,cancelled),allow_nan=False,ensure_ascii=False)
