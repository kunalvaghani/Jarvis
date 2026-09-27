"""Ten larger executable checks of retained curriculum programs, without inference."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

from jarvis.coding_lessons import record
from jarvis.coding_curriculum import catalogue
from train_coding import BASE, check, failure_category, inspect_source


def stress_cases():
    grid=[[1]*100 for _ in range(100)]
    grid[0][1]=2;grid[1][1]=1000
    for row in range(2,100):grid[row][0]=1000
    return {
        'edit-distance': {'input':['a'*200+'b'*200,'a'*200+'c'*200], 'expected':200},
        'lcs-length': {'input':['a'*200+'b'*200,'b'*200+'a'*200], 'expected':200},
        'coin-change': {'input':[[1,3,4],10000], 'expected':2500},
        'knapsack': {'input':[[[1,n] for n in range(1,101)],50], 'expected':sum(range(51,101))},
        'lis-length': {'input':list(range(5000,0,-1)), 'expected':1},
        'weighted-shortest-path': {'input':[{str(i):[[str(i+1),1]] for i in range(499)},'0'],
                                  'expected':{str(i):i for i in range(500)}},
        'minimum-grid-cost': {'input':grid, 'expected':200},
        'histogram-area': {'input':[7]*1000, 'expected':7000},
        'trapped-water': {'input':[10]+[0]*10000+[10], 'expected':100000},
        'window-maxima': {'input':[list(range(1000)),128], 'expected':list(range(127,1000))},
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True)
    args=parser.parse_args()
    root=Path(args.run).resolve(strict=True)
    if not root.is_relative_to(BASE/'artifacts') or root.is_symlink():parser.error('Use a local artifact curriculum run')
    state=json.loads((root/'results.json').read_text(encoding='utf-8'))
    if len(state['projects'])!=100:parser.error('Complete the hundred projects before follow-up stress checks')
    output=root/('stress-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    output.mkdir(exist_ok=False)
    projects={p['id'].split('-',1)[1]:p for p in state['projects']}
    expected_ids={p['name']:p['id'] for p in catalogue()}
    results=[]
    for name,case in stress_cases().items():
        project=projects[name];attempt=project['attempts'][-1]
        if project['id']!=expected_ids[name]:parser.error('Invalid curriculum project identity')
        source=root/attempt['path']/'main.py'
        result={'project':project['id'],'original_attempt':attempt['number'],'case':case,'passed':False}
        if not source.exists():
            result.update(status='not_executed',reason='No runnable source in final attempt')
        else:
            if source.is_symlink() or not source.resolve().is_relative_to(root):parser.error('Source is outside the curriculum run')
            content=source.read_text(encoding='utf-8');kind,error=inspect_source(content)
            if kind:result.update(status='not_executed',reason=error,kind=kind)
            else:
                folder=output/project['id'];folder.mkdir()
                with (folder/'main.py').open('x',encoding='utf-8') as file:file.write(content)
                before=hashlib.sha256((folder/'main.py').read_bytes()).hexdigest()
                checks=check(folder,[case],stdout_limit=32000);good=checks[0]['passed']
                after=hashlib.sha256((folder/'main.py').read_bytes()).hexdigest()
                kind='logic' if good else failure_category(checks)
                if before!=after:good=False;kind='policy'
                result.update(status='executed',passed=good,checks=checks,source_sha256=before,source_unchanged=before==after)
                record(BASE,project['id'],kind,int(good),1,3)
        results.append(result)
        print(json.dumps({'project':project['id'],'passed':result['passed'],'status':result['status']}),flush=True)
    report={'at':datetime.now(timezone.utc).isoformat(),'learning':'follow-up verification, no new generation or weight training',
            'results':results,'summary':{'planned':10,'executed':sum(r['status']=='executed' for r in results),
                                        'passed':sum(r['passed'] for r in results)}}
    (output/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(str(output/'results.json'),flush=True)
    print(json.dumps(report['summary']),flush=True)
    return 0 if report['summary']['passed']==10 else 1

if __name__=='__main__':sys.exit(main())
