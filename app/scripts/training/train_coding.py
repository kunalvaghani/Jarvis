"""Run/resume the 100-project local coding curriculum with real model output."""
from jarvis.paths import APP_ROOT, artifact_path
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import requests
from jarvis.brain import BrainClient
from jarvis.coding_curriculum import catalogue
from jarvis.coding_lessons import recall, record

BASE = Path(__file__).resolve().parents[2]
ALLOWED = {'sys','json','math','collections','itertools','functools','heapq','bisect','re','statistics',
           'csv','io','datetime','decimal','fractions','hashlib','base64','typing','string','unicodedata'}
BLOCKED = {'open','eval','exec','compile','__import__','getattr','setattr','delattr','globals','locals','breakpoint'}
BLOCKED_ATTRIBUTES = BLOCKED | {'FileIO','BufferedReader','BufferedWriter','BufferedRandom',
                              'TextIOWrapper','os','sys','subprocess','importlib','builtins'}

def inspect_source(source):
    if not isinstance(source,str) or not source.strip() or len(source)>20000:
        return 'syntax','Empty or oversized source.'
    try: tree=ast.parse(source)
    except (SyntaxError,MemoryError,RecursionError) as exc:
        return 'syntax',str(exc) or 'Parser rejected excessively nested source.'
    sys_names={'sys'}
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):
            sys_names.update(a.asname or a.name for a in node.names if a.name=='sys')
    for node in ast.walk(tree):
        if isinstance(node,(ast.Import,ast.ImportFrom)):
            names=[a.name for a in node.names] if isinstance(node,ast.Import) else [node.module or '']
            if any(name.split('.')[0] not in ALLOWED for name in names) or getattr(node,'level',0):
                return 'policy','Use only permitted pure standard-library imports.'
            if isinstance(node,ast.ImportFrom) and any(a.name in BLOCKED_ATTRIBUTES or
                    a.name.startswith('__') or a.name=='*' for a in node.names):
                return 'policy','Unsupported import of execution, filesystem or introspection helpers.'
        if isinstance(node,ast.Name) and node.id in BLOCKED:return 'policy','Dynamic execution or filesystem access is unsupported.'
        if isinstance(node,ast.Attribute) and (node.attr.startswith('__') or node.attr in BLOCKED_ATTRIBUTES or
                isinstance(node.value,ast.Name) and node.value.id in sys_names and node.attr not in {'stdin','stdout','stderr','exit'}):
            return 'policy','Process introspection or unsupported sys access is forbidden.'
    return None,None

def equivalent(actual,expected):
    if isinstance(expected,bool) or expected is None:return actual is expected
    if isinstance(expected,(int,float)):
        return type(actual) in {int,float} and math.isclose(actual,expected,rel_tol=1e-8,abs_tol=1e-8)
    if isinstance(expected,list):return isinstance(actual,list) and len(actual)==len(expected) and all(equivalent(a,b) for a,b in zip(actual,expected))
    if isinstance(expected,dict):return isinstance(actual,dict) and actual.keys()==expected.keys() and all(equivalent(actual[k],v) for k,v in expected.items())
    return type(actual)==type(expected) and actual==expected

def failure_category(failures):
    """Select only canonical advice from actual checks; never learn error prose."""
    first=failures[0]
    for row in failures:
        stderr=row.get('stderr','')
        if row['kind']=='runtime' and "name 'json' is not defined" in stderr:
            return 'missing_import'
        if row['kind']=='runtime' and (" object has no attribute 'get'" in stderr or
                'Input must be a JSON object' in stderr or 'Input must be a JSON array' in stderr):
            return 'input_shape'
        if row['kind']=='json' and not row.get('stdout','').strip():
            return 'silent_output'
        if row['kind']=='logic':
            try:actual=json.loads(row.get('stdout',''))
            except ValueError:continue
            expected=row['expected']
            if isinstance(actual,(dict,list)) != isinstance(expected,(dict,list)) or \
                    isinstance(actual,dict) != isinstance(expected,dict):
                return 'output_shape'
    return first['kind']

def check(folder,cases,stdout_limit=8000,compare=equivalent):
    if type(stdout_limit) is not int or not 1000<=stdout_limit<=64000:
        raise ValueError('Invalid bounded stdout budget')
    results=[]
    for index,case in enumerate(cases):
        output,error=folder/f'case-{index}.stdout',folder/f'case-{index}.stderr'
        try:
            with output.open('wb') as out,error.open('wb') as err:
                run=subprocess.run([sys.executable,'-I',str(folder/'main.py')],input=json.dumps(case['input']).encode(),
                    stdout=out,stderr=err,cwd=folder,timeout=5,check=False,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            with output.open('rb') as stream:
                text=stream.read(stdout_limit).decode('utf-8',errors='replace')
            if output.stat().st_size>stdout_limit:raise ValueError('Oversized stdout')
            if run.returncode:kind='runtime';good=False
            else:
                try:actual=json.loads(text);good=compare(actual,case['expected']);kind='logic'
                except ValueError:good=False;kind='json'
            with error.open('rb') as stream:
                stream.seek(max(0,error.stat().st_size-1000))
                stderr=stream.read(1000).decode('utf-8',errors='replace')
            results.append({'case':index,'passed':good,'kind':None if good else kind,'exit_code':run.returncode,
                'expected':case['expected'],'stdout':text[:1500],'stderr':stderr})
        except subprocess.TimeoutExpired:results.append({'case':index,'passed':False,'kind':'timeout'})
        except ValueError as exc:results.append({'case':index,'passed':False,'kind':'json','error':str(exc)})
    return results

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume',help='Existing curriculum run directory')
    parser.add_argument('--limit',type=int,default=100,help='Total projects to cover, 1..100')
    parser.add_argument('--attempts',type=int,default=2,choices=(1,2,3))
    args=parser.parse_args()
    if not 1<=args.limit<=100:parser.error('--limit must be 1..100')
    if args.resume:
        root=Path(args.resume).resolve(strict=True)
        if not root.is_relative_to(BASE/'artifacts') or root.is_symlink():parser.error('Resume only a local artifact run')
        state=json.loads((root/'results.json').read_text(encoding='utf-8'))
    else:
        root=artifact_path(BASE, 'coding-curriculum-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        root.mkdir(parents=True,exist_ok=False)
        state={'version':1,'started':datetime.now(timezone.utc).isoformat(),'model':'qwen3.5:4b',
               'learning':'verified experience recall; no model-weight training','projects':[], 'runner_pid':os.getpid()}
    projects=catalogue()
    curriculum_path=root/'curriculum.json'
    if args.resume:
        if json.loads(curriculum_path.read_text(encoding='utf-8')) != projects:
            parser.error('Curriculum changed; start a new run to preserve the original reference cases')
    else:
        curriculum_path.write_text(json.dumps(projects,indent=2),encoding='utf-8')
    state['runner_pid']=os.getpid()
    state.setdefault('protocol_phases', []).append({
        'started':datetime.now(timezone.utc).isoformat(),
        'completed_before_start':len(state['projects']),
        'version':3,'repair_feedback':'failing input and observed output',
        'canonical_lessons':'specific verified import/input/output/silent-output categories'})
    def save():
        state['updated']=datetime.now(timezone.utc).isoformat()
        state['summary']={'completed':len(state['projects']),'passed':sum(p['passed'] for p in state['projects']),
                          'failed':sum(not p['passed'] for p in state['projects']),
                          'first_attempt_passed':sum(p['first_attempt_passed'] for p in state['projects'])}
        temp=root/'results.tmp';temp.write_text(json.dumps(state,indent=2),encoding='utf-8');os.replace(temp,root/'results.json')
    save();print('RUN: '+str(root),flush=True)
    client=requests.Session();client.trust_env=False;owned=None;brain=None
    try:
        try:client.get('http://127.0.0.1:11434/api/tags',timeout=3).raise_for_status()
        except (requests.ConnectionError,requests.Timeout):
            executable=shutil.which('ollama')
            if not executable:raise ValueError('Ollama executable missing')
            # A timeout can mean an existing busy server: never start or stop it.
            try:client.get('http://127.0.0.1:11434/api/tags',timeout=20).raise_for_status()
            except requests.ConnectionError:
                log=(root/'ollama.log').open('wb')
                owned=subprocess.Popen([executable,'serve'],env=dict(os.environ,OLLAMA_HOST='127.0.0.1:11434',OLLAMA_NUM_PARALLEL='1'),
                    stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                state['owned_ollama_pid']=owned.pid;save()
                for _ in range(60):
                    try:client.get('http://127.0.0.1:11434/api/tags',timeout=2).raise_for_status();break
                    except (requests.ConnectionError,requests.Timeout):time.sleep(1)
                else:raise ValueError('Owned Ollama startup timed out')
        options=json.loads((BASE/'config/config.json').read_text(encoding='utf-8'))['brain']
        brain=BrainClient(BASE,options)
        done={p['id'] for p in state['projects']}
        for project in projects[:args.limit]:
            if project['id'] in done:continue
            started=time.monotonic();attempts=[];feedback='';previous=''
            for number in range(1,args.attempts+1):
                folder=root/project['id']/f'attempt-{number}'
                # Crash resume cannot replay an old write: choose a new attempt directory.
                if folder.exists():folder=folder.with_name(folder.name+'-'+datetime.now(timezone.utc).strftime('%H%M%S%f'))
                folder.mkdir(parents=True,exist_ok=False)
                goal=('Create main.py as a complete Python standard-library JSON CLI project. '
                      'Read exactly one JSON value from stdin, calculate the following contract, and print exactly one JSON value. '
                      'Do not print labels or Markdown. No files, networking, subprocesses, dynamic eval/exec or installation. '
                      +project['contract'])
                prompt={'goal':goal,'project':project['id'],'path':'main.py','reason':project['contract'],
                        'current':'','plan':[{'path':'main.py','reason':project['contract']}],'files':[],
                        'references':{'visible_examples':json.dumps(project['cases'][:2])},
                        'previous':previous,'validation_error':feedback,
                        'coding_lessons':recall(BASE,goal),'repository_instructions':[],'selected_skills':[], 'repository_map':''}
                (folder/'README.md').write_text('# '+project['name']+'\n\n'+project['contract']+'\n\nRun `python main.py`; input/output are single JSON values.\n',encoding='utf-8')
                stage='inference'
                try:
                    response=brain.request('code_edit',lambda:False,**prompt)
                    stage='verification'
                    (folder/'response.json').write_text(json.dumps(response,indent=2),encoding='utf-8')
                    source=response.get('content','');previous=source[:8000]
                    kind,error=inspect_source(source)
                    if kind:
                        cases=[];passed=False;feedback=error;record(BASE,project['id'],kind,0,1,number)
                    else:
                        path=folder/'main.py';path.write_text(source,encoding='utf-8')
                        before=hashlib.sha256(path.read_bytes()).hexdigest()
                        cases=check(folder,project['cases']);passed=all(c['passed'] for c in cases)
                        if hashlib.sha256(path.read_bytes()).hexdigest()!=before:
                            passed=False;kind='policy';feedback='Generated source changed while running; stop this project.'
                        else:
                            failures=[c for c in cases if not c['passed']];kind=failure_category(failures) if failures else 'logic'
                            feedback=json.dumps([{**c,'input':project['cases'][c['case']]['input']} for c in failures[:2]])[:2500]
                        record(BASE,project['id'],kind,0 if kind=='policy' else sum(c['passed'] for c in cases),
                               1 if kind=='policy' else len(cases),number)
                    attempt={'number':number,'passed':passed,'kind':None if passed else kind,'feedback':feedback,'cases':cases,'path':str(folder.relative_to(root))}
                except Exception as exc:
                    passed=False;kind='generation' if stage=='inference' else 'runtime';feedback=str(exc)[:1000]
                    attempt={'number':number,'passed':False,'kind':kind,'error':feedback,'cases':[],'path':str(folder.relative_to(root))}
                    record(BASE,project['id'],kind,0,1,number)
                attempts.append(attempt)
                (folder/'verification.json').write_text(json.dumps(attempt,indent=2),encoding='utf-8')
                print(json.dumps({'project':project['id'],'attempt':number,'passed':passed,'kind':attempt['kind']}),flush=True)
                if passed or kind=='policy' and 'changed while running' in feedback:break
            state['projects'].append({'id':project['id'],'level':project['level'],'passed':passed,
                'first_attempt_passed':attempts[0]['passed'],'seconds':round(time.monotonic()-started,2),'attempts':attempts})
            save()
        state['status']='completed' if len(state['projects'])==100 else 'partial';save()
    finally:
        if brain:brain.close()
        client.close()
        if owned and owned.poll() is None:
            owned.terminate()
            try:owned.wait(timeout=5)
            except subprocess.TimeoutExpired:owned.kill();owned.wait(timeout=5)
        state['owned_ollama_stopped']=bool(owned and owned.poll() is not None);save()
    print(json.dumps(state['summary']),flush=True)
    return 1 if state['summary']['failed'] else 0

if __name__=='__main__':sys.exit(main())
