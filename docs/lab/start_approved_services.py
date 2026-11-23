"""One approved existing-service start, after the retained regression finishes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
APP=ROOT/'app'
OUT=APP/'.jarvis-runtime/lab-validation/approved-service-start-2026-11-05'
OLLAMA=r'C:\Users\kunal\AppData\Local\Programs\Ollama\ollama.exe'
DOCKER=r'C:\Program Files\Docker\Docker\Docker Desktop.exe'


def main():
    if sys.argv[1:]!=['--run']:raise ValueError('Explicit --run required; user grant recorded in this chat')
    receipt=APP/'.jarvis-runtime/lab-validation/ah-hook-full-confirmation-2026-11-05.json'
    json.loads(receipt.read_text(encoding='utf-8'))  # Never start during the prior run.
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/'attempt.json').open('x',encoding='utf-8') as f:
        json.dump({'approval':'user-approved-existing-service-start','max_seconds':120,'installs':False},f)
    started=time.monotonic();deadline=started+120;actions=[]
    def run(args,env=None,cap=5):
        left=deadline-time.monotonic()
        if left<=0:raise TimeoutError('approved120-second bound exhausted')
        return subprocess.run(args,env=env,capture_output=True,timeout=min(cap,left),
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    def health():
        status={}
        try:
            with urllib.request.urlopen('http://127.0.0.1:11434/api/version',timeout=min(2,max(.1,deadline-time.monotonic()))) as r:
                status['ollama']=bool(json.loads(r.read(4096)).get('version'))
        except Exception:status['ollama']=False
        try:
            r=run(['docker','info','--format','{{.ServerVersion}} {{.OSType}}'])
            status['docker']=r.returncode==0 and 'linux' in r.stdout.decode('utf-8',errors='replace').lower()
        except Exception:status['docker']=False
        return status
    result={'scope':'existing services only; no inference, installs, downloads or configuration changes'}
    try:
        initial=health();result['initial']=initial
        for name,path in (('docker',DOCKER),('ollama',OLLAMA)):
            if initial[name]:actions.append({'service':name,'action':'already available; no launch'});continue
            sig=run(['powershell.exe','-NoProfile','-NonInteractive','-Command',
                "[string](Get-AuthenticodeSignature -LiteralPath '"+path+"').Status"],cap=10)
            if sig.returncode or sig.stdout.decode().strip()!='Valid':raise ValueError(name+' executable signature not valid')
            env=os.environ.copy()
            if name=='ollama':
                sys.path.insert(0,str(APP))
                from jarvis.gpu_scheduler import runtime_environment
                env=runtime_environment(env);env['OLLAMA_HOST']='127.0.0.1:11434'
            with (OUT/(name+'-launch.json')).open('x',encoding='utf-8') as f:
                json.dump({'state':'consumed before launch','executable':path},f)
            command="Start-Process -FilePath '"+path+"'"+(' -ArgumentList serve' if name=='ollama' else '')+' -WindowStyle Hidden -PassThru | Select-Object -ExpandProperty Id'
            launch=run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],env=env,cap=10)
            actions.append({'service':name,'action':'one launch attempted','launcher_exit_code':launch.returncode})
        while deadline-time.monotonic()>12:
            status=health()
            if all(status.values()):break
            time.sleep(min(2,max(0,deadline-time.monotonic()-12)))
        result['health']=health()
        r=run([sys.executable,'-B','-m','jarvis.launcher','--check'],cap=max(1,deadline-time.monotonic())) if deadline-time.monotonic()>1 else None
        if r is not None:
            result['readiness_exit_code']=r.returncode
            result['readiness']=json.loads(r.stdout.decode('utf-8'))
    except Exception as e:result['error']=type(e).__name__+': '+str(e)[:300]
    finally:
        result.update(actions=actions,seconds=time.monotonic()-started,processes_killed=False)
        with (OUT/'result.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
        print(json.dumps({k:v for k,v in result.items() if k!='readiness'}))


if __name__=='__main__':
    os.chdir(APP)
    main()
