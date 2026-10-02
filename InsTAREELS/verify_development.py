"""Reproducible real builds/browser checks on authored isolated acceptance fixtures."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
from jarvis.development import verify, tools_for
from jarvis.development_projects import scaffold
from jarvis.development_learning import record

BASE=Path(__file__).resolve().parent

def run(stack, install=False):
    root=BASE/'artifacts'/('development-dashboard' if stack=='vite' else 'development-'+stack)
    root.mkdir(parents=True,exist_ok=True)
    scaffold(root,stack,lambda:False,lambda *a:None,lambda *a,**kw:None)
    if stack=='vite':
        template=BASE/'jarvis/templates/development/dashboard'
        for name in ('App.tsx','styles.css'):
            (root/'src'/name).write_text((template/name).read_text(encoding='utf-8'),encoding='utf-8')
        tests=json.loads((template/'checks.json').read_text(encoding='utf-8'))
    else:
        heading={'next':'Next workspace','electron':'Electron renderer','expo':'Your workspace'}[stack]
        if stack in {'next','electron'}:
            path=root/('src/app/page.tsx' if stack=='next' else 'src/App.tsx')
            content="'use client';\nimport {useState} from 'react';\nexport default function App(){const [n,setN]=useState(0);return <main><h1>"+heading+"</h1><button onClick={()=>setN(n+1)}>Add task</button><p role=\"status\">Tasks {n}</p></main>;}\n"
            path.write_text(content,encoding='utf-8')
            tests=[{'name':'Typed client state','steps':[{'action':'assert_text','value':heading},{'action':'click','name':'Add task'},{'action':'assert_text','value':'Tasks 1'},{'action':'click','name':'Add task'},{'action':'assert_text','value':'Tasks 2'}]}]
        else:
            tests=[{'name':'Native components in web export','steps':[{'action':'assert_text','value':heading},{'action':'click','name':'Completed 0'},{'action':'assert_text','value':'Completed 1'},{'action':'click','name':'Completed 1'},{'action':'assert_text','value':'Completed 2'}]}]
    # --execute is explicit human authorization for these exact fixtures, unlike
    # normal Jarvis which uses its existing nonblocking island approval handler.
    actions=SimpleNamespace(base=BASE,report=lambda *a:None,
        _approve=lambda *a:None,development_tools=None)
    try:
        receipt=verify(actions,root,stack,tests,lambda:False,install=install)
        if not receipt['goal_verified']:raise ValueError('Acceptance failed: '+receipt['evidence_file'])
        record(BASE,root,'Authored '+stack+' acceptance fixture',receipt)
        dest=BASE/'artifacts/development-previews'
        dest.mkdir(exist_ok=True)
        for view in receipt['browser']['views']:
            shutil.copy2(view['screenshot'],dest/(stack+'-'+view['name']+'.png'))
        return receipt
    finally:
        tools_for(actions).close()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true',help='Authorize fixture writes, project code execution and browser interaction')
    parser.add_argument('--install',action='store_true',help='Also authorize pinned official npm dependencies, hooks disabled')
    parser.add_argument('--stack',choices=['vite','next','electron','expo','all'],default='vite')
    args=parser.parse_args()
    if not args.execute:parser.error('Pass --execute after reviewing this fixture runner. Normal Jarvis uses its own execution approval.')
    rows=[]
    for stack in (['vite','next','electron','expo'] if args.stack=='all' else [args.stack]):
        print('Checking '+stack,flush=True)
        receipt=run(stack,args.install)
        rows.append(receipt)
        print(stack+': type/build and '+str(receipt['browser']['functional_assertions'])+' assertions across three browser configurations passed.',flush=True)
    report={'date':datetime.now(timezone.utc).isoformat(),
        'scope':'Real tools and browsers on authored acceptance fixtures, not autonomous whole-project model generation or native-device verification.',
        'checks':rows}
    (BASE/'artifacts/development-acceptance-check.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
