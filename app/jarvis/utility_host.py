"""Reviewed host operations with owned lifecycle; no arbitrary shell adapter."""
import json
import os
from pathlib import Path
import re
import sys
import threading
from .utility_core import scoped,read,write
from .repo_acquisition import command,git


class OwnedServer:
    def __init__(self,root,port=0):
        import http.server
        from urllib.parse import unquote,urlsplit
        root=Path(root).resolve()
        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(root),**kwargs)
            def log_message(self,*args):pass
            def list_directory(self,path):self.send_error(403);return None
            def translate_path(self,path):
                relative=unquote(urlsplit(path).path).lstrip('/') or 'index.html'
                if any(piece.startswith('.') or re.search('secret|credential|password|token',piece,re.I) for piece in Path(relative).parts):raise ValueError('Private preview path denied.')
                return str(scoped(root,relative))
        self.server=http.server.ThreadingHTTPServer(('127.0.0.1',port),Handler)
        self.server.daemon_threads=True
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True,name='Jarvis owned static preview');self.thread.start()
        self.url='http://127.0.0.1:'+str(self.server.server_port)+'/'
    def close(self):self.server.shutdown();self.server.server_close();self.thread.join(2)
    def healthy(self):return self.thread.is_alive()


def execute(actions,name,root,args,cancelled):
    if name=='env_set':
        import winreg
        key=args['name'];value=args['value']
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{0,100}',key) or key in {'PATH','PATHEXT','COMSPEC','SYSTEMROOT','WINDIR','HOME','USERPROFILE','CODEX_HOME'}:raise ValueError('Reserved or invalid user environment name.')
        if not isinstance(value,str) or len(value)>4000 or '\x00' in value:raise ValueError('Environment value exceeds contract.')
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,'Environment') as environment:winreg.SetValueEx(environment,key,0,winreg.REG_SZ,value)
        os.environ[key]=value
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as environment:verified=winreg.QueryValueEx(environment,key)[0]==value
        return {'name':key,'user_scope':True,'readback_verified':verified,'new_processes_need_environment_refresh':True}
    if name=='git_workflow':
        branch=args['branch'];message=args['message'];files=args['files']
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_/-]{0,100}',branch) or not isinstance(message,str) or not 1<=len(message)<=500:raise ValueError('Invalid branch or commit message.')
        if not isinstance(files,list) or not 1<=len(files)<=30:raise ValueError('Name 1–30 exact files; staging all files is unsupported.')
        for file in files:
            path=scoped(root,file)
            if not path.is_file() or any(p.startswith('.') or re.search('secret|credential|password|token',p,re.I) for p in Path(file).parts):raise ValueError('Only explicit non-sensitive files can be staged.')
        if git(['-C',str(root),'diff','--cached','--name-only'],cancelled).strip():raise ValueError('Existing staged changes require review; nothing staged.')
        git(['-C',str(root),'check-ref-format','--branch',branch],cancelled)
        git(['-C',str(root),'switch','-c',branch],cancelled)
        git(['-C',str(root),'add','--',*files],cancelled)
        git(['-C',str(root),'commit','-m',message],cancelled)
        result={'commit':git(['-C',str(root),'rev-parse','HEAD'],cancelled).decode().strip(),'branch':branch,'pushed':False}
        if args.get('push'):
            remote=args.get('remote','origin')
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,30}',remote):raise ValueError('Invalid remote name.')
            git(['-C',str(root),'push','-u',remote,branch],cancelled);result['pushed']=True
        return result
    if name=='clipboard':
        import win32clipboard
        operation=args['operation'];win32clipboard.OpenClipboard()
        try:
            if operation=='read':return {'text':win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)[:10000] if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT) else ''}
            if operation=='write':
                text=args['text']
                if not isinstance(text,str) or len(text)>10000:raise ValueError('Clipboard text exceeds budget.')
                win32clipboard.EmptyClipboard();win32clipboard.SetClipboardText(text,win32clipboard.CF_UNICODETEXT);return {'written':True}
            raise ValueError('Use clipboard read/write.')
        finally:win32clipboard.CloseClipboard()
    if name=='local_server':
        current=getattr(actions,'utility_server',None)
        if args['operation']=='stop':
            if isinstance(current,OwnedServer):current.close();actions.utility_server=None
            return {'stopped':True}
        if args['operation']!='start':raise ValueError('Use server start/stop.')
        if isinstance(current,OwnedServer):raise ValueError('An owned preview already exists; stop it explicitly first.')
        port=args.get('port',0)
        if type(port) is not int or not (port==0 or 1024<=port<=65535):raise ValueError('Preview port must be zero or 1024–65535.')
        actions.utility_server=OwnedServer(root,port);return {'url':actions.utility_server.url,'loopback_only':True}
    if name=='audio_transcribe':
        path=scoped(root,args['source']);read(path)
        model_path=Path(actions.base)/actions.config['model_path']
        raw=command([sys.executable,'-m','jarvis.utility_audio_worker'],cancelled,45,
            json.dumps({'source':str(path),'model':str(model_path)}).encode(),1000000)
        result=json.loads(raw)
        if result.get('ok') is not True:raise ValueError(result.get('error','Transcription failed.'))
        return result['value']
    if name=='os_schedule':
        import subprocess
        task=args['name'];interval=args['interval_minutes'];script=scoped(root,args['script'])
        if not re.fullmatch(r'Jarvis-[A-Za-z0-9_-]{1,60}',task) or type(interval) is not int or not 1<=interval<=1440 or script.suffix!='.py' or not script.is_file():raise ValueError('Use Jarvis-name, trusted scoped .py script and 1–1440 minutes.')
        invocation=subprocess.list2cmdline([sys.executable,str(script)])
        schedule=['/sc','daily','/mo','1'] if interval==1440 else ['/sc','minute','/mo',str(interval)]
        command(['schtasks.exe','/create','/tn',task,'/tr',invocation,*schedule],cancelled,10)
        confirmed=command(['schtasks.exe','/query','/tn',task,'/xml'],cancelled,10)
        if task.encode() not in confirmed and task.encode('utf-16-le') not in confirmed:raise ValueError('Schedule readback uncertain; inspect without retrying.')
        return {'task':task,'created_and_queried':True,'replaced_existing':False}
    if name=='screenshots':
        import importlib.util
        # Capture in the installed utility runtime via a reviewed worker operation.
        from .utility_tools import core_call
        return core_call(actions,'screenshots',root,args,cancelled)
    if name=='dynamic_scrape':
        from .toolkits import public_url
        from urllib.parse import urlsplit
        current=getattr(actions,'utility_server',None)
        target=urlsplit(args['url'])
        owned=urlsplit(current.url) if isinstance(current,OwnedServer) and current.healthy() else None
        if owned and target.scheme==owned.scheme and target.netloc==owned.netloc and not target.username and not target.password:
            url=args['url']
        else:url=public_url(args['url'])
        browser=actions._browser()
        browser.request('navigate',cancelled,value=url,new_task=True)
        result=browser.request('read_text',cancelled)
        return result
    if name=='desktop_control':
        # Existing guarded native UIA dispatch and own cursor; never raw PyAutoGUI.
        if args.get('text') is not None and not args.get('field'):raise ValueError('Name the exact field before typing; no blind keyboard injection.')
        ui=actions._ui();handle=ui._handle()
        snapshot=ui.runner({'operation':'list','handle':handle,'owner_pid':os.getpid()},cancelled)
        controls=[c for c in snapshot['controls'] if c['name']==args['control'] and c['role'] in {'Button','Hyperlink','MenuItem','CheckBox','TabItem'} and not c.get('password')]
        if len(controls)!=1:raise ValueError('Desktop activation requires one exact freshly observed accessible control; no input issued.')
        result=ui._activate(handle,snapshot,controls[0],'click',cancelled)
        if args.get('text') is not None:
            if not args.get('field'):raise ValueError('Name the exact field before typing; no blind keyboard injection.')
            ui=actions._ui();handle=ui._handle()
            snapshot=ui.runner({'operation':'list','handle':handle,'owner_pid':os.getpid()},cancelled)
            controls=[c for c in snapshot['controls'] if c['role']=='Edit' and c['name']==args['field'] and not c.get('password')]
            if len(controls)!=1:raise ValueError('Field must be uniquely visible and non-password.')
            result=ui.runner({'operation':'fill_text','handle':handle,'owner_pid':os.getpid(),'signature':snapshot['signature'],'control':controls[0],'content':args['text']},cancelled)
        return {'evidence':str(result),'shared_mouse_used':False,'automatic_enter':False}
    if name=='local_llm':
        answer=actions.brain.client.request('tool_text',cancelled,tool='think',goal=args['prompt'],content='')
        return {'text':answer,'backend':'Existing local Qwen client and GPU admission'}
    raise ValueError('Unknown reviewed host operation.')
