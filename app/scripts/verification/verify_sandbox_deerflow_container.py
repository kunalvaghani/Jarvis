"""Explicit owned-container smoke: installed reviewed image, synthetic math/chart/failure only."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE))
OUT=BASE/'artifacts/jarvis-audit/modules/28-sandbox-deerflow'


def main():
    from jarvis.deerflow_sandbox import SandboxJob,IMAGE
    from jarvis.docker_runtime import engine_status
    from jarvis.repo_sandbox import RepositorySandbox
    from jarvis.deerflow_media import execute
    engine=engine_status();assert engine['status']=='available','Existing Linux engine required; no startup attempted'
    runtime=RepositorySandbox(IMAGE)
    image=json.loads(runtime.cli(['image','inspect',IMAGE]))[0]
    expected=json.loads((BASE/'config/runtime_manifest.json').read_text())['optional_deerflow']['sandbox']['tested_image_id']
    assert image['Id']==expected and image['Config'].get('Entrypoint') is None
    evidence={'date':'2026-10-16 IST','engine':engine,'image':image['Id'],'scope':'owned ephemeral jobs, synthetic data only; no Desktop start/pull/build/model/GPU/account actions'}
    math=SandboxJob(BASE)
    with math:
        info=math.owned();host=info['HostConfig']
        assert info['Config']['User']=='65534:65534' and host['NetworkMode']=='none' and host['ReadonlyRootfs']
        assert 'ALL' in host['CapDrop'] and 'no-new-privileges' in host['SecurityOpt']
        assert host['Memory']==2147483648 and host['MemorySwap']==2147483648 and host['PidsLimit']==128
        mounts=info['Mounts'];assert not any('docker.sock' in m['Destination'] for m in mounts)
        assert all(m['Destination'].startswith(('/mnt/user-data/','/mnt/skills/public','/mnt/models/kokoro/','/tmp')) for m in mounts)
        result=math.execute('python -c "import os,json;print(json.dumps({\'answer\':2+2,\'uid\':os.getuid()}))"',timeout=10)
        observed=json.loads(result);assert observed=={'answer':4,'uid':65534}
        evidence['math']={'id':math.identifier,'container_id':math.state['container_id'],'observed':observed,
            'isolation':{'network':'none','root_readonly':True,'capabilities':'ALL dropped','memory':host['Memory'],'pids':128}}
    assert runtime.cli(['ps','-aq','--filter','id='+math.state['container_id']]).strip()==b''
    evidence['math']['cleaned']=True
    rendered=json.loads(execute(SimpleNamespace(base=BASE),{'value':'chart','content':'{"title":"Synthetic audit fixture","labels":["A","B"],"values":[2,5]}'},lambda:False))
    assert rendered['verification']['format']=='PNG' and rendered['verification']['dimensions']==[1280,720]
    state=json.loads((Path(rendered['artifact_directory'])/'state.json').read_text());assert state['status']=='closed'
    assert runtime.cli(['ps','-aq','--filter','id='+state['container_id']]).strip()==b''
    evidence['render']=rendered;evidence['render']['cleaned']=True
    fault=SandboxJob(BASE)
    with fault:
        try:fault.execute('python -c "raise SystemExit(7)"',timeout=10)
        except ValueError:pass
        else:raise AssertionError('Nonzero exit reported success')
        assert fault.state['status']=='uncertain' and not fault.owned()['State']['Running']
        try:fault.execute('echo must-not-replay')
        except ValueError:pass
        else:raise AssertionError('Uncertain command replayed')
        assert len(fault.state['calls'])==1
        evidence['failure']={'id':fault.identifier,'status':fault.state['status'],'calls':1,'stopped':True}
    assert runtime.cli(['ps','-aq','--filter','id='+fault.state['container_id']]).strip()==b''
    evidence['failure']['cleaned']=True
    (OUT/'container-fixture.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print(json.dumps({'math':'PASS','PNG':'PASS','nonzero_and_no_replay':'PASS','cleanup':'PASS','image':image['Id']}))


if __name__=='__main__':main()
