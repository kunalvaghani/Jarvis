"""Read-only inventory and private rollback snapshot; never emits credential values."""
import ast
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request

BASE = Path(__file__).resolve().parents[2]
OUT = BASE / 'artifacts/jarvis-audit'
PRIVATE = BASE / '.jarvis-runtime/jarvis-audit/pre-change'

def command(args, timeout=12, cwd=None):
    try:
        p = subprocess.run(args, capture_output=True, text=True, errors='replace', timeout=timeout, cwd=cwd or BASE)
        return {'exit_code': p.returncode, 'output': p.stdout.strip()[:200000],
                'error_type': 'command_failed' if p.returncode else None}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'error_type': type(exc).__name__}

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if PRIVATE.exists():
        inventory_only = True
    else:
        PRIVATE.mkdir(parents=True)
        inventory_only = False
    for name in ('config.json', 'runtime_manifest.json'):
        if not inventory_only: shutil.copy2(BASE/'config'/name, PRIVATE/name)
    # Preserve every tracked dirty file and untracked app source/test/report.
    # Keep this private: existing configuration and fixtures may contain personal data.
    status = command(['git','status','--porcelain'], cwd=BASE.parent)
    if not inventory_only: (PRIVATE/'git-status.txt').write_text(status['output'], encoding='utf-8')
    paths = command(['git','diff','--name-only'], cwd=BASE.parent)['output'].splitlines()
    paths += command(['git','ls-files','--others','--exclude-standard'], cwd=BASE.parent)['output'].splitlines()
    for name in paths:
        if not inventory_only and name.startswith('app/'):
            source = BASE.parent/name
            if source.is_file():
                target = PRIVATE/'dirty-files'/name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    manifest = json.loads((BASE/'config/runtime_manifest.json').read_text(encoding='utf-8'))
    config = json.loads((BASE/'config/config.json').read_text(encoding='utf-8'))
    def flags(value, prefix=''):
        rows = {}
        if isinstance(value, dict):
            for key, child in value.items():
                path = prefix+'.'+key if prefix else key
                if key in {'enabled','model','engine','planner','coding_backend','online','background_refresh'} and type(child) in (str,bool,int):
                    rows[path] = child
                elif isinstance(child, dict): rows.update(flags(child,path))
        return rows
    environments = {}
    package_code = 'import importlib.metadata as m,json,sys; print(json.dumps({"python":sys.version.split()[0],"packages":{d.metadata["Name"]:d.version for d in m.distributions()}}))'
    for folder in sorted(BASE.glob('.venv*')):
        interpreter = folder/'Scripts/python.exe'
        if interpreter.is_file():
            result = command([str(interpreter),'-c',package_code])
            try: environments[folder.name] = json.loads(result['output'])
            except (KeyError,ValueError): environments[folder.name] = result
    import psutil
    from jarvis.realtime_catalog import CATALOG
    hardware = {'logical_cpus':psutil.cpu_count(), 'physical_cpus':psutil.cpu_count(logical=False),
                'ram_total_bytes':psutil.virtual_memory().total,'ram_available_bytes':psutil.virtual_memory().available,
                'cpu_percent_sample':psutil.cpu_percent(interval=.2)}
    battery = psutil.sensors_battery()
    if battery: hardware['battery'] = {'percent':battery.percent,'plugged_in':battery.power_plugged}
    checks = {name:command(args) for name,args in {
        'gpu':['nvidia-smi','--query-gpu=name,memory.total,memory.used,driver_version','--format=csv,noheader'],
        'node':['node','--version'], 'docker':['docker','version','--format','{{json .}}'],
        'localgithub':['git','-C',str(BASE.parent.parent/'LocalGithub'),'rev-parse','--is-inside-work-tree'],
    }.items()}
    ollama = {}
    try:
        for endpoint in ('version','tags','ps'):
            with urllib.request.urlopen('http://127.0.0.1:11434/api/'+endpoint, timeout=8) as response:
                ollama[endpoint] = json.load(response)
        for name in sorted({v for k,v in flags(config).items() if k.endswith('.model') and isinstance(v,str)}):
            if name in {m['name'] for m in ollama.get('tags',{}).get('models',[])}:
                request = urllib.request.Request('http://127.0.0.1:11434/api/show',
                    data=json.dumps({'model':name}).encode(),headers={'Content-Type':'application/json'})
                with urllib.request.urlopen(request,timeout=8) as response: data=json.load(response)
                ollama.setdefault('show',{})[name] = {k:data.get(k) for k in ('details','capabilities','modified_at')}
    except Exception as exc: ollama['error_type'] = type(exc).__name__
    modules = {}
    for path in sorted((BASE/'jarvis').glob('*.py')):
        try:
            tree = ast.parse(path.read_text(encoding='utf-8-sig'))
            modules[path.stem] = {'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'imports':sorted({n.module or '' for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) and n.level==1})}
        except Exception as exc: modules[path.stem] = {'error_type':type(exc).__name__}
    integrations = []
    for path in sorted((BASE/'integrations').iterdir()):
        if path.is_dir():
            row = {'name':path.name,'licenses':[p.name for p in path.glob('*LICENSE*')]}
            if (path/'.git').exists(): row['commit'] = command(['git','rev-parse','HEAD'],cwd=path)
            integrations.append(row)
    result = {'date':'2026-10-14 IST','commit':command(['git','rev-parse','HEAD'])['output'],
        'branch':command(['git','branch','--show-current'])['output'], 'dirty_entries':len(status['output'].splitlines()),
        'snapshot':'PRIVATE .jarvis-runtime/jarvis-audit/pre-change; no credentials in public artifact',
        'environment':environments,'flags':flags(config),'hardware':hardware,'checks':checks,'ollama':ollama,
        'credentials':{key:bool(os.environ.get(key)) for key in ('GROQ_API_KEY','FIRECRAWL_API_KEY','GITHUB_TOKEN','YOUTUBE_API_KEY')},
        'credential_files_present':{p.name:p.is_file() for p in (BASE/'secrets').glob('*.json')},
        'manifest_sha256':hashlib.sha256((BASE/'config/runtime_manifest.json').read_bytes()).hexdigest(),
        'manifest_keys':list(manifest),'modules':modules,'integrations':integrations,'realtime_catalog_count':len(CATALOG),
        'test_cases_file_present':any((root/'jarvis_test_cases.jsonl').is_file() for root in (BASE/'test_cases',BASE.parent/'test_cases')),
        'requirements':{p.name:p.read_text(encoding='utf-8') for p in (BASE/'requirements').glob('*.txt')},
        'lockfiles':[str(p.relative_to(BASE)) for p in (BASE/'integrations').glob('*/package-lock.json')]}
    (OUT/'environment.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'environments':list(environments),'modules':len(modules),'integrations':len(integrations),
        'checks':checks,'hardware':hardware,'ollama_models':[m['name'] for m in ollama.get('tags',{}).get('models',[])],
        'snapshot':str(PRIVATE)},indent=2))

if __name__ == '__main__': main()
