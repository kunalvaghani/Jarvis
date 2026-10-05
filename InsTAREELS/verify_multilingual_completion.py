"""Inspect owned example state, repair observed failures with local CLI, retest.

This is an explicitly requested verification workflow, not production recovery
or automatic replay of an uncertain edit. Each repair starts from fresh disk
source and actual syntax/browser diagnostics. No user's project is executed.
"""
import argparse
import hashlib
from pathlib import Path
from verify_multilingual_ui import BASE, ROOT, CASES, receipt, save, generate, test
from jarvis.coder import check_content

def finish(only=None, attempts=5):
    if not 1<=attempts<=5: raise ValueError('Use one to five inspected attempts.')
    for ident,kind,level,target,title,goal in CASES:
        if only and only!=ident:continue
        project=ROOT/ident;project.mkdir(parents=True,exist_ok=True)
        path=project/target
        data=receipt();row=data['projects'].setdefault(ident,{})
        verifier=BASE/'verify_multilingual_ui.py'
        if (row.get('passed') and path.is_file()
            and row.get('tested_source_sha256')==hashlib.sha256(path.read_bytes()).hexdigest()
            and row.get('verifier_sha256')==hashlib.sha256(verifier.read_bytes()).hexdigest()):
            print('Unchanged verified fixture: '+ident,flush=True);continue
        if path.exists():
            # Fresh observation before another model may edit this source.
            try:
                check_content(path,path.read_text(encoding='utf-8'))
                row.update(generated=True,kind=kind,level=level,title=title,target=target,goal=goal,
                    inspected_source_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                save(data)
            except ValueError as exc:
                row.update(generated=False,error=str(exc));save(data)
        if not row.get('generated'):
            generate(ident,backend='codex')
        for attempt in range(attempts):
            if path.exists():
                try:
                    check_content(path,path.read_text(encoding='utf-8'))
                    observed=receipt();observed['projects'][ident]['generated']=True;save(observed)
                except ValueError:pass
            test(ident)
            data=receipt();row=data['projects'].get(ident,{})
            if row.get('passed'):break
            if attempt==attempts-1:break
            # A completed browser/source inspection authorizes this concrete
            # correction. Source is read again by the CLI, originals retained.
            generate(ident,repair=True,backend='codex')
        if not receipt()['projects'].get(ident,{}).get('passed'):
            print('Needs further inspected repair: '+ident,flush=True)
    return receipt().get('passed',False)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--only');parser.add_argument('--attempts',type=int,default=5);args=parser.parse_args()
    raise SystemExit(0 if finish(args.only,args.attempts) else 1)
