"""Real Blender+ToolRegistry benchmark; synthetic approvals apply ONLY to disposable assets."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace

BASE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(BASE))
from jarvis.commands import parse
from jarvis.tools import ToolRegistry
from jarvis.blender_host import route
from jarvis.task_state import TaskState
import psutil


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blender',required=True)
    options=parser.parse_args()
    root=BASE/'integrations/jarvis-connectors/connectors/apps/blender'
    report={'classification':'LIVE disposable Blender, real stdio/ToolRegistry; synthetic test approvals; no microphone/UI certification','requests':[]}
    with tempfile.TemporaryDirectory(prefix='jarvis-blender-e2e-') as temporary:
        base=Path(temporary);config=base/'scope.json'
        with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        env=dict(os.environ,JARVIS_BLENDER_CONFIG=str(config),JARVIS_BLENDER_PORT=str(port),JARVIS_BLENDER_ALLOWED_ROOTS=str(base))
        with (base/'blender.log').open('w',encoding='utf-8') as log:
            process=subprocess.Popen([options.blender,'--background','--factory-startup','--disable-autoexec','--python',str(root/'live_bridge_fixture.py')],env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            monitor_stop=threading.Event();samples=[]
            def sample():
                tracked=psutil.Process(process.pid);tracked.cpu_percent()
                while not monitor_stop.wait(.1):
                    try:samples.append({'rss':tracked.memory_info().rss,'cpu_percent':tracked.cpu_percent()})
                    except psutil.Error:return
            thread=threading.Thread(target=sample,daemon=True);thread.start()
            actions=None
            try:
                deadline=time.monotonic()+45
                while not config.exists():
                    if process.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Disposable Blender startup failed; inspect evidence log.')
                    time.sleep(.1)
                server={'enabled':True,'trusted':True,'persistent':True,'approval_binding':'blender-v1','command':sys.executable,
                    'args':[str(root/'server.py'),'--runtime','builtin','--allow-write','--bridge-config',str(config)],
                    'allow_tools':[r['tool'] for r in json.loads((root/'catalog.json').read_text())],'env_names':[],'timeout_seconds':20}
                (base/'.jarvis').mkdir();(base/'.jarvis/mcp.json').write_text(json.dumps({'servers':{'blender':server}}))
                events=[];approvals=[]
                actions=SimpleNamespace(base=base,config={},skills=None,allowed_tools=None,
                    report=lambda kind,text:events.append((kind,text)),_approve=lambda *args:approvals.append(args[:2]),closed=threading.Event())
                actions.task_state=TaskState(base);actions.task_state.start('Disposable Blender benchmark','task')
                def call(name,args):
                    result=ToolRegistry(actions).execute({'action':'mcp_call','value':'blender',
                        'content':json.dumps({'name':'blender_'+name,'arguments':args})},lambda:False)
                    return json.loads(result.evidence)['structuredContent']['result']
                def wait(value):
                    data=value['untrusted_data'];deadline=time.monotonic()+15
                    if 'job_id' not in data:return data
                    if 'wait_helper' not in report:
                        report['wait_helper']=call('wait_job',{'job_id':data['job_id'],'expected_scope':value['scope_id'],'timeout':1.0})
                        assert report['wait_helper']['untrusted_data']['status']=='done'
                    while time.monotonic()<deadline:
                        receipt=call('job_status',{'job_id':data['job_id'],'expected_scope':value['scope_id']})['untrusted_data']
                        if receipt['status'] in {'done','error'}:
                            if receipt['status']=='error':raise AssertionError(receipt)
                            return receipt['result']
                        time.sleep(.05)
                    raise TimeoutError('Job still running; never replay it.')
                phrases=[]
                for i in range(60):
                    shape=('cube','sphere','plane','cylinder','cone')[i%5]
                    phrases.append(f'create a {shape} named Benchmark{i} in Blender')
                phrases += ['status in Blender','list objects in Blender','show selection in Blender','show scene in Blender','version in Blender']*12
                for text in phrases:
                    start=time.perf_counter();command=parse(text);parsed=time.perf_counter()
                    handled,evidence=route(actions,command,lambda:False)
                    assert handled
                    submitted=time.perf_counter()
                    value=json.loads(evidence)['structuredContent']['result']
                    wait(value)
                    finished=time.perf_counter()
                    if command.value.startswith('add_'):
                        target=json.loads(command.extra)['name']
                        observed=wait(call('get_object',{'name':target}))
                        assert observed['data']['name']==target
                    report['requests'].append({'text':text,'parse_ms':(parsed-start)*1000,
                        'dispatch_ms':(submitted-parsed)*1000,'completion_ms':(finished-start)*1000,'independent_readback':command.value.startswith('add_')})
                for name in ('Medium','Large'):
                    report[name.lower()]=wait(call('get_mesh_stats',{'name':name}))
                report['bridge']=call('bridge_health',{})['untrusted_data']
                report['approval_count']=len(approvals)
                report['completed_notifications']=sum('Blender · done' in text for _,text in events)
            finally:
                if actions is not None:
                    actions.closed.set()
                    if hasattr(actions,'_blender_mcp'):actions._blender_mcp.close()
                    if hasattr(actions,'_blender_jobs'):actions._blender_jobs.close()
                config.with_suffix('.stop').touch()
                try:process.wait(timeout=12)
                except subprocess.TimeoutExpired:
                    process.terminate();process.wait(timeout=5) # Only this process handle, never another Blender.
                monitor_stop.set();thread.join(2)
                log.flush()
                (BASE/'artifacts/jarvis-audit/blender-connector/live-host.log').write_bytes((base/'blender.log').read_bytes())
        (BASE/'artifacts/jarvis-audit/blender-connector/live-host.log').write_bytes((base/'blender.log').read_bytes())
    for key in ('parse_ms','dispatch_ms','completion_ms'):
        values=sorted(r[key] for r in report['requests'])
        report[key]={p:values[min(len(values)-1,int(len(values)*q))] for p,q in [('p50',.5),('p95',.95),('p99',.99)]}
    report['resource_samples']={'count':len(samples),'peak_blender_rss_bytes':max((r['rss'] for r in samples),default=0),
        'peak_blender_cpu_percent':max((r['cpu_percent'] for r in samples),default=0),
        'gpu':'Not measured; Workbench/background geometry does not certify Cycles GPU behavior.',
        'main_thread':'Host dispatch benchmark only; live voice and Dynamic Island frame responsiveness not measured.'}
    target=BASE/'artifacts/jarvis-audit/blender-connector/live-host-e2e.json'
    target.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in {'requests','bridge'}},indent=2))


if __name__=='__main__':main()
