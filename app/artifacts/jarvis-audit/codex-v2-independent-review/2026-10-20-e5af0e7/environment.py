"""Fresh offline metadata/consistency checks; no model imports or installation."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
APP = Path('D:\\Kunals GitHub Repo\\LocalGithub\\Jarvis-e2e-e5af0e7\\app')
INSTALL = Path('D:/Kunals GitHub Repo/Jarvis/app')
historical = json.loads((APP / 'artifacts/jarvis-audit/modules/34-dependencies/2026-10-20-completion-a9b4ce1/environment-sbom.json').read_text())
code = "import importlib.metadata as m,json,platform,sys;print(json.dumps({'python':platform.python_version(),'packages':sorted([{'name':d.metadata.get('Name',''),'version':d.version} for d in m.distributions()],key=lambda r:r['name'].lower())}))"
def query(row):
    python = Path(row['interpreter'].replace('%INSTALL_APP%', str(INSTALL)))
    start = time.perf_counter()
    metadata = subprocess.run([str(python), '-c', code], capture_output=True, text=True, timeout=90)
    pip = subprocess.run([str(python), '-m', 'pip', 'check'], capture_output=True, text=True, timeout=90)
    direct = {'returncode': pip.returncode, 'stderr': pip.stderr.strip()}
    route = 'worker pip'
    if pip.returncode and 'No module named pip' in pip.stderr:
        pip = subprocess.run([sys.executable, '-m', 'pip', '--python', str(python), 'check'], capture_output=True, text=True, timeout=90)
        route = 'existing main pip --python worker (read-only)'
    return {'environment': row['environment'], 'metadata_returncode': metadata.returncode,
        'metadata': json.loads(metadata.stdout) if metadata.returncode == 0 else None,
        'direct_worker_pip': direct, 'pip_check_route': route,
        'pip_check_returncode': pip.returncode, 'pip_check': pip.stdout.strip(), 'pip_stderr': pip.stderr.strip(),
        'seconds': time.perf_counter() - start}
with ThreadPoolExecutor(max_workers=3) as pool:
    results = list(pool.map(query, historical['environments']))
(OUT / 'environment-readback.json').write_text(json.dumps({'date': '2026-10-20', 'platform': platform.platform(),
    'cpus': os.cpu_count(), 'environment_results': results, 'model_imports_or_loads': 0,
    'installations': 0, 'network_requests': 0}, indent=2), encoding='utf-8')
print(json.dumps({'environments': len(results), 'pip_check_pass': sum(r['pip_check_returncode'] == 0 for r in results)}))
