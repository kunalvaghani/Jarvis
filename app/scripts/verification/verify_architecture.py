"""Module 01: read-only code/config census and bounded architecture fixtures."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from types import SimpleNamespace

BASE=Path(__file__).resolve().parents[2]
OUT=BASE/'artifacts/jarvis-audit/modules/01-architecture-inventory'
_BASELINE_PAIR=None

def baseline_pair():
    global _BASELINE_PAIR
    if _BASELINE_PAIR is None:
        import importlib.util
        values=[]
        for name in ('launcher','agent_events'):
            path=BASE/'.jarvis-runtime/jarvis-audit/module01-pre'/(name+'.py')
            spec=importlib.util.spec_from_file_location('jarvis._audit_before_'+name,path)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);values.append(module)
        _BASELINE_PAIR=values
    return _BASELINE_PAIR

def fixture(root,baseline=False):
    import psutil
    from jarvis import launcher
    from jarvis.agent_events import event
    from jarvis.runtime_health import RuntimeHealth
    from jarvis.tools import ToolRegistry
    if baseline:
        launcher,events=baseline_pair();event=events.event
    root.mkdir(parents=True,exist_ok=True);(root/'config').mkdir(exist_ok=True)
    (root/'main.py').write_text('pass\n',encoding='utf-8')
    config={'apps':{},'whisper':{},'model_path':'models/speech','brain':{'enabled':False},'speech':{'enabled':False}}
    (root/'config/config.json').write_text(json.dumps(config),encoding='utf-8')
    process=psutil.Process();cpu_start=sum(process.cpu_times()[:2]);at=time.perf_counter()
    loaded=launcher.preflight(root,repair=False)
    actions=SimpleNamespace(base=root,config=loaded)
    catalog=ToolRegistry(actions).catalog()
    identifier=event(actions,'tool.started','runtime_capabilities')
    event(actions,'tool.completed','runtime_capabilities',identifier,backend='toolkit')
    log=(root/'.jarvis-runtime/agent-events.jsonl').read_text()
    rows=[json.loads(s) for s in log.splitlines()]
    assert len(catalog)>0 and rows[-1]['call_id']==identifier and rows[-1]['event']=='tool.completed'
    return {'ms':(time.perf_counter()-at)*1000,'cpu_ms':(sum(process.cpu_times()[:2])-cpu_start)*1000,
        'rss_bytes':process.memory_info().rss,'tools':len(catalog),'external_effects':0}

def benchmark(phase):
    OUT.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder);cold=[];warm=[]
        for i in range(5):
            at=time.perf_counter()
            p=subprocess.run([sys.executable,'-X','utf8','-m',__spec__.name,'--fixture',str(root/f'cold-{i}')],cwd=BASE,capture_output=True,text=True,timeout=20)
            if p.returncode:raise RuntimeError('Cold fixture failed: '+p.stderr[-200:])
            row=json.loads(p.stdout);row['process_ms']=(time.perf_counter()-at)*1000;cold.append(row)
        fixture(root/'prime')
        for i in range(20):warm.append(fixture(root/f'warm-{i}'))
    def metrics(rows,key):
        values=sorted(r[key] for r in rows)
        return {'samples':len(rows),'p50':statistics.median(values),'p95':values[int((len(values)-1)*.95)],'max':max(values)}
    result={'phase':phase,'observed_at':datetime.now().astimezone().isoformat(),'scope':'Five cold interpreter launches and twenty warm preflight/catalog/lifecycle requests. Owned fixtures only. No model TTFT or GPU allocations.',
        'cold_process_ms':metrics(cold,'process_ms'),'cold_request_ms':metrics(cold,'ms'),'warm_request_ms':metrics(warm,'ms'),
        'warm_cpu_ms':metrics(warm,'cpu_ms'),'cold_rss_bytes':metrics(cold,'rss_bytes'),'warm_rss_bytes':metrics(warm,'rss_bytes'),
        'external_effects':sum(r['external_effects'] for r in cold+warm),'raw':{'cold':cold,'warm':warm}}
    path=OUT/f'benchmark-{phase}.json'
    if path.exists():raise ValueError('Preserve existing benchmark before repeating')
    path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='raw'},indent=2))

def paired():
    """Interleave exact captured preimages/current code; never edit the running checkout."""
    rows={'before':{'cold':[],'warm':[]},'after':{'cold':[],'warm':[]}}
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder)
        for i in range(5):
            for phase in ('before','after') if i%2==0 else ('after','before'):
                argv=[sys.executable,'-X','utf8','-m',__spec__.name,'--fixture',str(root/f'{phase}-cold-{i}')]
                if phase=='before':argv.append('--baseline-fixture')
                at=time.perf_counter();p=subprocess.run(argv,cwd=BASE,capture_output=True,text=True,timeout=20)
                if p.returncode:raise RuntimeError('Paired fixture failed')
                row=json.loads(p.stdout);row['process_ms']=(time.perf_counter()-at)*1000;rows[phase]['cold'].append(row)
        fixture(root/'prime-old',True);fixture(root/'prime-new')
        for i in range(20):
            for phase in ('before','after') if i%2==0 else ('after','before'):
                rows[phase]['warm'].append(fixture(root/f'{phase}-warm-{i}',phase=='before'))
    result={'observed_at':datetime.now().astimezone().isoformat(),'scope':'Alternating exact owned preimage modules and current modules; no checkout edits or model loads', 'raw':rows,'summaries':{}}
    for phase in rows:
        result['summaries'][phase]={}
        for group,key in (('cold','process_ms'),('cold','ms'),('warm','ms'),('warm','rss_bytes')):
            values=sorted(r[key] for r in rows[phase][group])
            result['summaries'][phase][group+'_'+key]={'samples':len(values),'p50':statistics.median(values),'p95':values[int((len(values)-1)*.95)]}
    (OUT/'benchmark-paired.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result['summaries'],indent=2))

def inventory():
    from jarvis.tools import SPECS,ToolRegistry
    from jarvis.toolkits import status
    modules={}
    for path in sorted((BASE/'jarvis').glob('*.py')):
        text=path.read_text(encoding='utf-8-sig');tree=ast.parse(text)
        symbols={}
        for node in tree.body:
            if isinstance(node,(ast.FunctionDef,ast.ClassDef)):
                symbols[node.name]=node.lineno
                if isinstance(node,ast.ClassDef):
                    symbols.update({node.name+'.'+child.name:child.lineno for child in node.body if isinstance(child,(ast.FunctionDef,ast.AsyncFunctionDef))})
        modules[path.stem]={'source':'jarvis/'+path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'symbols':symbols,
            'imports':sorted({node.module or '' for node in ast.walk(tree) if isinstance(node,ast.ImportFrom) and node.level==1})}
    providers={r['tool']:r for r in status()}
    registry=ToolRegistry(SimpleNamespace(config={},base=BASE))
    tools=[]
    for spec in SPECS:
        provider=providers.get(spec.name)
        tools.append({'name':spec.name,'backend':spec.backend,'approval':spec.approval,
            'provider_configured':provider.get('configured') if provider else None,
            'state':'credential_or_prerequisite_gated' if provider and not provider.get('configured') else 'adapter_present_live_unverified',
            'dispatch':'jarvis/tools.py:ToolRegistry._execute'+(' -> jarvis/toolkits.py:execute' if spec.backend=='toolkit' else '')})
    manifest=json.loads((BASE/'config/runtime_manifest.json').read_text(encoding='utf-8'))
    map_text=(BASE/'docs/system-map.md').read_text(encoding='utf-8')
    result={'observed_at':datetime.now().astimezone().isoformat(),'map_sha256':hashlib.sha256(map_text.encode()).hexdigest(),'modules':modules,
        'tools':tools,'registered_tool_count':len(registry.specs),'manifest_services':manifest['services'],
        'scope':'Static code symbols, registry metadata and prerequisite presence. No app/model/account actions, no capability certification.'}
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'source-inventory.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('Modules',len(modules),'tools',len(tools),'services',len(manifest['services']))

def dependencies():
    rows=[]
    for folder in sorted(BASE.glob('.venv*')):
        interpreter=folder/'Scripts/python.exe'
        if not interpreter.is_file():continue
        version=subprocess.run([str(interpreter),'-c','import sys; print(sys.version.split()[0])'],capture_output=True,text=True,timeout=8)
        try:
            check=subprocess.run([str(interpreter),'-m','pip','check'],capture_output=True,text=True,timeout=20)
            # pip check contains package/version names only, not env credentials.
            report=check.stdout.strip()[:20000]
            result={'environment':folder.name,'python':version.stdout.strip(),'interpreter_present':True,
                'dependency_check':'PASS' if check.returncode==0 else 'BLOCKED' if 'No module named pip' in check.stderr else 'FAIL',
                'conflicts':report if check.returncode else '',
                'prerequisite':'pip unavailable in this interpreter' if 'No module named pip' in check.stderr else None}
        except (OSError,subprocess.TimeoutExpired) as exc:
            result={'environment':folder.name,'python':version.stdout.strip(),'interpreter_present':True,
                'dependency_check':'BLOCKED','error_type':type(exc).__name__}
        rows.append(result)
    (OUT/'dependency-checks.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(rows,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--fixture',type=Path);parser.add_argument('--benchmark',choices=('before','after'));parser.add_argument('--inventory',action='store_true');parser.add_argument('--dependencies',action='store_true');parser.add_argument('--paired',action='store_true');parser.add_argument('--baseline-fixture',action='store_true');args=parser.parse_args()
    if args.fixture:print(json.dumps(fixture(args.fixture,args.baseline_fixture)))
    if args.benchmark:benchmark(args.benchmark)
    if args.inventory:inventory()
    if args.dependencies:dependencies()
    if args.paired:paired()
