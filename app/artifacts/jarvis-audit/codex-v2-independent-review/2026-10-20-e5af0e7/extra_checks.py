"""Fresh bounded reproductions for every original IR finding, plus runner-only memory snapshot."""
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

out = Path(__file__).resolve().parent
source = Path('D:/Kunals GitHub Repo/LocalGithub/Jarvis-v2-mutants-e5af0e7/app')
old = out.parent/'2026-10-20-a9b4ce1/pinned-prior-findings.xml'
selected = []
for case in ET.parse(old).findall('.//testcase'):
    parts = case.get('classname').split('.')
    index = next(i for i, name in enumerate(parts) if name.startswith('test_'))
    name = str(source/'tests'/(parts[index]+'.py'))+'::'+'::'.join(parts[index+1:]+[case.get('name')])
    selected.append(name)
(out/'prior-findings-selection.json').write_text(json.dumps(selected,indent=2),encoding='utf-8')
done = subprocess.run([sys.executable,'-m','pytest',*selected,'-q','--tb=short','--junitxml='+str(out/'prior-findings.xml')],
    cwd=source, capture_output=True,timeout=180)
(out/'prior-findings.txt').write_bytes(done.stdout+done.stderr)
import psutil
samples = []
for process in psutil.process_iter(['pid','name','cmdline']):
    try:
        command = process.info['cmdline'] or []
        if not process.info['name'].lower().startswith('python'):
            continue
        if not any('run_candidate_suite.py' in item or 'run_suite.py' in item and '2026-10-20-e5af0e7' in item for item in command):
            continue
        info = process.memory_info()
        samples.append({'pid':process.pid,'rss_bytes':info.rss,'os_lifetime_peak_working_set_bytes':getattr(info,'peak_wset',None)})
    except (psutil.NoSuchProcess,psutil.AccessDenied):
        pass
(out/'interim-memory.json').write_text(json.dumps({'scope':'one interim snapshot of owned Python regression runners; excludes child aggregate and GPU; not end-user peak RAM',
    'samples':samples},indent=2),encoding='utf-8')
print(done.stdout.decode('utf-8',errors='replace')[-1200:])
raise SystemExit(done.returncode)
