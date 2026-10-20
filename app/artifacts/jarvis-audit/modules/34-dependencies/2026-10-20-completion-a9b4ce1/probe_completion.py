"""Read-only compatibility probes; no installation, model inference or service startup."""
import json
import os
from pathlib import Path
import re
import subprocess

OUT=Path(__file__).resolve().parent
INSTALL=Path('D:/Kunals GitHub Repo/Jarvis/app')
def safe(text):
    return re.sub(r'(?i)[A-Z]:[\\/]+Users[\\/]+[^\\/\s]+','%USERPROFILE%',str(text)).replace(str(INSTALL),'%INSTALL_APP%')
def command(exe,args,timeout=60):
    env=dict(os.environ,PYTORCH_NVML_BASED_CUDA_CHECK='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    try:
        row=subprocess.run([str(exe),*args],capture_output=True,timeout=timeout,env=env,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        return {'returncode':row.returncode,'stdout':safe(row.stdout.decode(errors='replace'))[:24000],
                'stderr':safe(row.stderr.decode(errors='replace'))[:5000]}
    except (OSError,subprocess.TimeoutExpired) as exc:
        return {'status':'BLOCKED','error_type':type(exc).__name__}
pip_checks={}
for folder in sorted(INSTALL.glob('.venv*')):
    exe=folder/'Scripts/python.exe'
    if exe.is_file():
        row=command(exe,['-m','pip','check'])
        if 'No module named pip' in row.get('stderr',''):
            row=command(INSTALL/'.venv/Scripts/python.exe',['-m','pip','--python',str(exe),'check'])
            row['method']='Existing main pip check delegated to the pip-less target interpreter; no pip installed.'
        pip_checks[folder.name]=row
(OUT/'pip-checks.json').write_text(json.dumps(pip_checks,indent=2)+'\n',encoding='utf-8')
abi={}
for folder in ['.venv-brain','.venv-f5','.venv-training']:
    code='import json,torch; print(json.dumps({"torch":torch.__version__,"cuda_runtime":torch.version.cuda,"cuda_available":torch.cuda.is_available()}))'
    if folder=='.venv-f5': code='import torchaudio; '+code
    abi[folder]=command(INSTALL/folder/'Scripts/python.exe',['-I','-c',code])
(OUT/'torch-import-readback.json').write_text(json.dumps({'scope':'Native library import/driver availability only; no model, tensor, CUDA kernels or training allocated.',
    'environments':abi},indent=2)+'\n',encoding='utf-8')
browser_code='''import json,os
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 print(json.dumps({'bundled_chromium_exists':os.path.isfile(p.chromium.executable_path),
                   'bundled_chromium_name':os.path.basename(p.chromium.executable_path)}))
'''
(OUT/'playwright-readback.json').write_text(json.dumps({'probe':command(INSTALL/'.venv/Scripts/python.exe',['-I','-c',browser_code]),
    'scope':'Owned Playwright driver metadata only; no browser page/profile or download opened.'},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'pip_check_returncodes':{name:row.get('returncode',row.get('status')) for name,row in pip_checks.items()},
                  'torch_import_returncodes':{name:row.get('returncode',row.get('status')) for name,row in abi.items()}}))
