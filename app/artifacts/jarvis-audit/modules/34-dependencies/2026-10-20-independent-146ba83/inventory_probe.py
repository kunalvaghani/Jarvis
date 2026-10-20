"""Read-only metadata inventory. Never installs, starts services, loads models or invokes WSL distros."""
import hashlib
import http.client
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

OUT=Path(__file__).resolve().parent
APP=next(p for p in OUT.parents if (p/'main.py').is_file())
INSTALL=Path('D:/Kunals GitHub Repo/Jarvis/app')
def safe(text):
    text=str(text).replace(str(INSTALL),'%INSTALL_APP%').replace(str(APP),'%AUDIT_APP%')
    text=re.sub(r'(?i)[A-Z]:[\\/]+Users[\\/]+[^\\/\s]+','%USERPROFILE%',text)
    return re.sub(r'https?://\S+','[URL omitted]',text)
def dump(name,data): (OUT/name).write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def command(args,timeout=35):
    try:
        result=subprocess.run([str(a) for a in args],capture_output=True,timeout=timeout,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        raw=result.stdout+result.stderr
        encoding='utf-16' if b'\0' in raw[:100] else 'utf-8'
        return {'returncode':result.returncode,'output':safe(raw.decode(encoding,errors='replace'))[:12000]}
    except (OSError,subprocess.TimeoutExpired) as exc:
        return {'status':'BLOCKED','error_type':type(exc).__name__}

probe='''import sys,json,importlib.metadata as m
rows=[]
for d in m.distributions():
 name=d.metadata.get('Name')
 if name: rows.append({'name':name,'version':d.version,'requires':d.requires or []})
print(json.dumps({'python':sys.version,'packages':sorted(rows,key=lambda r:r['name'].lower())}))
'''
environments=[]
for folder in sorted(INSTALL.glob('.venv*')):
    exe=folder/'Scripts/python.exe'
    row={'environment':folder.name,'interpreter':'%INSTALL_APP%/'+folder.name+'/Scripts/python.exe','exists':exe.is_file()}
    if exe.is_file():
        data=command([exe,'-I','-c',probe])
        if data.get('returncode')==0:
            try: row.update(json.loads(data['output']))
            except ValueError:
                # Package inventories can exceed the console-output bound; retain the full sanitized JSON here.
                result=subprocess.run([str(exe),'-I','-c',probe],capture_output=True,timeout=35,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                row.update(json.loads(safe(result.stdout.decode('utf-8'))))
        else: row['probe']=data
    environments.append(row)
dump('environment-sbom.json',{'date':'2026-10-20','install_root':'%INSTALL_APP%',
    'audit_root':'%AUDIT_APP%','environments':environments,'method':'Python -I; importlib.metadata only; no package imports/models/inference'})

requirements=[]
for path in sorted((APP/'requirements').glob('*.txt')):
    lines=[line.strip() for line in path.read_text(encoding='utf-8').splitlines() if line.strip() and not line.lstrip().startswith('#')]
    requirements.append({'path':path.relative_to(APP).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'declared':lines,'range_or_unhashed':any('==' not in line or '--hash=' not in line for line in lines)})
lockpaths=[APP/'integrations/deerflow/runtime/resolved-requirements.txt',
           APP/'integrations/repository-runtime/requirements.txt',
           APP/'integrations/gods-eye-view-src/gods-eye-view-main/package-lock.json']
dump('lockfile-map.json',{'requirements':requirements,'known_lock_or_resolved_files':[{
    'path':p.relative_to(APP).as_posix(),'exists':p.is_file(),
    'sha256':hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None} for p in lockpaths],
    'caveat':'A requirements range or installed freeze is not a hash-locked reproducible installer; no install attempted.'})

workers=[]
for path in (APP/'jarvis').glob('*.py'):
    for number,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
        if re.search(r'\.venv[-\w]*.*(?:python|Scripts|environment)|worker_environment\s*=',line):
            workers.append({'path':path.relative_to(APP).as_posix(),'line':number,'source':safe(line.strip())[:300]})
dump('worker-interpreters.json',{'method':'Source references; not a claim every worker launched','references':workers})

tools={}
for name,args in [('node',['--version']),('npm',['--version']),('ollama',['--version']),
                  ('docker',['--version']),('nvcc',['--version']),('wsl',['--version'])]:
    exe=shutil.which(name)
    tools[name]={'executable':safe(exe) if exe else None,'probe':command([exe,*args],12) if exe else {'status':'NOT INSTALLED'}}
gpu=shutil.which('nvidia-smi')
tools['gpu']=command([gpu,'--query-gpu=name,driver_version,memory.total,memory.free','--format=csv,noheader,nounits'],12) if gpu else {'status':'BLOCKED'}
tools['os']={'platform':platform.platform(),'machine':platform.machine()}
main=INSTALL/'.venv/Scripts/python.exe'
tools['wheel_cache']=command([main,'-m','pip','cache','info'],15)
tools['wsl_status']='Version queried only; no distro started, Linux path/permission execution not certified.'
dump('os-gpu-tools.json',tools)

models=[]
try:
    conn=http.client.HTTPConnection('127.0.0.1',11434,timeout=8)
    conn.request('GET','/api/tags');response=conn.getresponse();data=json.loads(response.read(2000000));conn.close()
    for row in data.get('models',[])[:25]:
        models.append({key:row.get(key) for key in ('name','digest','size','details')})
    dump('ollama-models.json',{'status':response.status,'models':models,'scope':'Local tags metadata only; no pulls, inference or prompt/template capture.'})
except (OSError,ValueError,http.client.HTTPException) as exc:
    dump('ollama-models.json',{'status':'BLOCKED','error_type':type(exc).__name__})
dump('dependency-graph.json',{'edges':[{'environment':e['environment'],'package':p['name'],'requires':p['requires']}
    for e in environments for p in e.get('packages',[])],'source':'installed distribution metadata; markers retained, not a solved lock'})
print(json.dumps({'environments':len(environments),'packages_per_env':{e['environment']:len(e.get('packages',[])) for e in environments},
                  'models':len(models),'inventory':'saved; no installation/model inference/service start'}))
