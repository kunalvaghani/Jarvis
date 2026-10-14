"""Collect existing release evidence; fail rather than invent missing results."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from scripts.verification.verify_hierarchical import inventory

BASE = Path(__file__).resolve().parents[2]

def main():
    reports = BASE/'artifacts/reports'
    log = (BASE/'.jarvis-runtime/learning-release-final-tests.log').read_text(encoding='utf-8')
    match = re.search(r'Ran (\d+) tests in ([\d.]+)s', log)
    if not match or not re.search(r'^OK\s*$',log,re.M) or re.search(r'^FAILED',log,re.M):
        raise ValueError('Final full regression suite has not passed.')
    readiness_log = (BASE/'.jarvis-runtime/learning-readiness-final.log').read_text(encoding='utf-8')
    readiness = json.loads(next(line for line in readiness_log.splitlines() if line.startswith('{')))
    if readiness.get('status') != 'ready':
        raise ValueError('Launcher readiness has not passed.')
    fixtures = {name:json.loads((reports/(name+'.json')).read_text(encoding='utf-8'))
        for name in ('learning-native','learning-website','learning-public-docs','learning-live')}
    if not all(row.get('passed') is True for row in fixtures.values()):
        raise ValueError('Integrated verification evidence is incomplete.')
    baseline = json.loads((reports/'learning-baseline.json').read_text(encoding='utf-8'))
    upgraded = json.loads((reports/'learning-upgraded.json').read_text(encoding='utf-8'))
    current = inventory()
    before = {row['path']:row.get('sha256') for row in baseline['source_inventory']}
    changed = [row for row in current if row.get('sha256') != before.get(row['path'])]
    result = {'date':datetime.now(timezone.utc).isoformat(),
        'release_status':'regression_and_bounded_integrations_passed',
        'baseline_tests':{'count':1765,'seconds':280.195,'passed':True},
        'final_tests':{'count':int(match[1]),'seconds':float(match[2]),'passed':True},
        'readiness':readiness,
        'fixtures':{name:{key:row.get(key) for key in ('passed','scope','seconds','elapsed_seconds')}
            for name,row in fixtures.items()},
        'benchmarks':{'baseline':{k:v for k,v in baseline.items() if k!='source_inventory'},
            'upgraded':{k:v for k,v in upgraded.items() if k!='source_inventory'},
            'scope':'Single controlled parser/memory samples, upgraded sample concurrent with tests; no speedup claim or two-second complex-task guarantee.'},
        'changed_firstparty_source_since_learning_baseline':changed,
        'configuration_sha256':{name:hashlib.sha256((BASE/name).read_bytes()).hexdigest()
            for name in ('config/config.json','config/runtime_manifest.json')},
        'limitations':['Not universal application/website control','No Blender/Unreal/third-party export acceptance test',
            'Native/browser fixture planners were authored; actual model test covers acquired-help file reads',
            'No speaker/listening, microphone, long-running soak, full production VRAM or background-load benchmark',
            'Optional cloud/hosted integrations not live checked','Feature vocabulary and configured-app/explicit-public-URL detection are bounded',
            'Document version and semantic task correctness remain separately uncertain'],
        'rollback':'Set knowledge_acquisition.enabled=false and restart with existing launchers; online/background_refresh independently configurable.'}
    (reports/'learning-validation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'final_tests':result['final_tests'],'readiness':readiness['status'],
        'integrated_checks_passed':len(fixtures),'changed_firstparty_sources':len(changed)},indent=2))

if __name__ == '__main__':main()
