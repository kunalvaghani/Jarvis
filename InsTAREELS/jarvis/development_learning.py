"""Framework-scoped cases from independent build/browser evidence, not weights."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import threading
from .agent_context import scoped

LOCK=threading.RLock()
PRACTICE=[
 {'id':'responsive-landing','goal':'Build a responsive landing page with a working primary action and accessible navigation.'},
 {'id':'dashboard-forms','goal':'Build a React dashboard with real filtering, validated create form and keyboard dialog handling.'},
 {'id':'accessible-motion','goal':'Animate state changes and verify reduced-motion preferences on desktop and mobile.'},
 {'id':'data-routing','goal':'Build an application with routing and independently tested loading, empty, error and retry states.'},
 {'id':'platform-version','goal':'Adapt the verified interface to Electron or Expo; verify native lifecycle, packaging and device permissions separately.'},
]

def fingerprint(project):
    from .coder import project_files
    root=Path(project).resolve(strict=True)
    digest=hashlib.sha256()
    names=project_files(root,limit=2001)
    if len(names)>2000:
        raise ValueError('Narrow the verification scope to at most 2000 source files.')
    total=0
    for name in sorted(names):
        path=scoped(root,name)
        size=path.stat().st_size
        if size>8000000 or total+size>32000000:
            raise ValueError('Development source fingerprint exceeds the 32MB bound.')
        total+=size
        digest.update(name.encode('utf-8'))
        with path.open('rb') as source:
            for chunk in iter(lambda:source.read(65536),b''):
                digest.update(chunk)
    return digest.hexdigest()

def store_path(base):
    return scoped(base,'.jarvis-runtime/development-cases.jsonl')

def record(base, project, goal, evidence, failures=None):
    """Only the executor calls this with its current receipt; not a model tool."""
    root=Path(project).resolve(strict=True)
    stack=evidence.get('stack')
    if stack not in {'vite','next','electron','expo'}:
        raise ValueError('Unknown lesson framework.')
    if str(root)!=evidence.get('project') or evidence.get('source_fingerprint')!=fingerprint(root):
        raise ValueError('Project changed since verification; no lesson promoted.')
    browser=evidence.get('browser',{})
    passed=evidence.get('goal_verified') is True
    if passed and not (evidence.get('build_passed') is True
        and len(evidence.get('build',[]))==2 and all(c.get('exit_code')==0 for c in evidence['build'])
        and browser.get('source')=='playwright_chromium' and browser.get('goal_verified') is True
        and browser.get('functional_assertions',0)>=3 and browser.get('functional_interactions',0)>=1 and len(browser.get('views',[]))==3
        and all(Path(v.get('screenshot','')).is_file() and Path(v['screenshot']).resolve().is_relative_to(scoped(root,'.jarvis/development'))
                and not v.get('console_errors') and not v.get('accessibility_violations') and not v.get('horizontal_overflow')
                and all(s.get('passed') is True for s in v.get('scenarios',[])) for v in browser['views'])):
        raise ValueError('Independent browser/build evidence is incomplete; no success lesson promoted.')
    problems=[]
    for attempt in [*(failures or []),evidence]:
        for check in attempt.get('build',[]):
            if check.get('exit_code')!=0: problems.append(check['phase']+': '+check.get('output','')[-600:])
        for view in attempt.get('browser',{}).get('views',[]):
            problems += [v.get('id','accessibility') for v in view.get('accessibility_violations',[])]
            problems += [s.get('name','scenario') for s in view.get('scenarios',[]) if s.get('passed') is False]
    row={'version':1,'at':datetime.now(timezone.utc).isoformat(),'stack':stack,'project':str(root),
         'goal':str(goal)[:1200],'source_fingerprint':evidence['source_fingerprint'],'verified':passed,
         'failure_causes':list(dict.fromkeys(problems))[:12],
         'recovery':'New reviewed changes followed by independently rerun checks' if passed and failures else '',
         'verification_scope':'Type/build plus goal-specific desktop/mobile/reduced-motion browser checks; native platform unverified' if passed else 'Failed or incomplete; reference only',
         'patterns':(['Semantic named controls, typed state and independently tested responsive behavior',
                      'Verify reduced-motion, keyboard, forms, empty/error recovery and accessibility before completion'] if passed else []),
         'evidence_file':evidence.get('evidence_file',''),'package_versions':json.loads(scoped(root,'package.json').read_text(encoding='utf-8')).get('dependencies',{})}
    path=store_path(base)
    with LOCK:
        path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists() and path.stat().st_size>2000000:
            raise ValueError('Development case store is full; preserve and archive before adding more.')
        with path.open('a',encoding='utf-8') as out: out.write(json.dumps(row,ensure_ascii=False)+'\n')
    return row

def recall(base, stack, goal='', limit=3):
    path=store_path(base)
    if not path.exists(): return []
    if path.stat().st_size>2000000: return []
    with LOCK: lines=path.read_text(encoding='utf-8').splitlines()[-200:]
    rows=[]
    words=set(str(goal).casefold().split())
    for line in lines:
        try:
            row=json.loads(line)
            if row.get('version')!=1 or row.get('stack')!=stack: continue
            row={k:row.get(k) for k in ('goal','verified','failure_causes','recovery','verification_scope','patterns','package_versions')}
            rows.append((len(words & set(str(row['goal']).casefold().split())),row))
        except (ValueError,TypeError): continue
    rows.sort(key=lambda pair:pair[0],reverse=True)
    return [r for _,r in rows[:limit]]

def feedback(base, project, text, approved_reference=None):
    """Called only for an explicit human feedback request, never inference."""
    if not isinstance(text,str) or not 1<=len(text.strip())<=1200:
        raise ValueError('Give concise design feedback.')
    from .development_design import REFERENCES
    if approved_reference and approved_reference not in {r['id'] for r in REFERENCES}:
        raise ValueError('Unknown reference ID.')
    row={'at':datetime.now(timezone.utc).isoformat(),'project':str(Path(project).resolve(strict=True)),
         'human_feedback':text,'approved_reference':approved_reference,'execution_permission':False}
    path=scoped(base,'.jarvis-runtime/development-feedback.jsonl')
    with LOCK:
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('a',encoding='utf-8') as out:out.write(json.dumps(row,ensure_ascii=False)+'\n')
    return row

def preferences(base, project):
    path=scoped(base,'.jarvis-runtime/development-feedback.jsonl')
    if not path.exists() or path.stat().st_size>1000000: return []
    rows=[]
    for line in path.read_text(encoding='utf-8').splitlines()[-100:]:
        try:
            row=json.loads(line)
            if row.get('project')==str(Path(project).resolve()): rows.append(row)
        except ValueError:continue
    return rows[-5:]
