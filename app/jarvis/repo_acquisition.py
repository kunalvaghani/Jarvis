"""Non-destructive, source-only repository snapshots with pinned provenance."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from uuid import uuid4

from .harness_process import OwnedJob, hidden_spawn
from .skill_memory import linked

SKIP={'.git','.venv','venv','node_modules','__pycache__','build','dist','site-packages','models','artifacts','.jarvis-runtime'}
SENSITIVE=re.compile(r'(?i)(secret|credential|password|api[_-]?key|token|id_rsa|id_ed25519)')


def environment():
    env={k:v for k,v in os.environ.items() if k.upper() in {'PATH','SYSTEMROOT','WINDIR','TEMP','TMP','COMSPEC','PATHEXT','PROGRAMFILES','PROGRAMFILES(X86)'}}
    env.update(GIT_TERMINAL_PROMPT='0',GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,GIT_LFS_SKIP_SMUDGE='1')
    return env


def command(argv, cancelled=lambda:False, timeout=60, input_bytes=None, limit=32000000):
    """Bounded owned trusted CLI invocation. This is not an untrusted-code sandbox."""
    if cancelled():raise ValueError('Operation cancelled before CLI dispatch.')
    job=OwnedJob()
    with tempfile.TemporaryFile() as output,tempfile.TemporaryFile() as source:
        if input_bytes is not None:source.write(input_bytes);source.seek(0)
        process=None
        try:
            process=hidden_spawn(job,subprocess.Popen)(argv,env=environment(),stdin=source if input_bytes is not None else subprocess.DEVNULL,stdout=output,stderr=output)
            deadline=time.monotonic()+timeout
            while process.poll() is None:
                if cancelled() or time.monotonic()>deadline or os.fstat(output.fileno()).st_size>limit:
                    raise ValueError('Owned CLI cancelled, timed out or exceeded output budget; no action replay.')
                time.sleep(.025)
            output.seek(0);raw=output.read(limit+1)
            if len(raw)>limit:raise ValueError('CLI output exceeded budget.')
            if process.returncode:raise ValueError('CLI failed: '+raw.decode('utf-8',errors='replace')[-700:])
            return raw
        finally:
            if process is not None and process.poll() is None:process.terminate();process.wait(timeout=5)
            job.close()


def git(argv,cancelled=lambda:False,timeout=60):
    binary=shutil.which('git')
    if not binary:raise ValueError('Git is unavailable; repository acquisition is disabled.')
    try:
        return command([binary,'-c','core.hooksPath='+os.devnull,'-c','core.fsmonitor=false',
            '-c','credential.helper=','-c','protocol.file.allow=never','-c','protocol.ext.allow=never',
            '-c','submodule.recurse=false',*argv],cancelled,timeout)
    except ValueError as error:
        operation=argv[2] if argv[0]=='-C' else argv[0]
        raise ValueError('Repository Git '+operation+' failed: '+str(error)) from error


def identity(target):
    if not isinstance(target,str) or not 1<=len(target)<=2000:raise ValueError('Repository target must be bounded text.')
    if '://' in target or target.startswith('git@'):
        match=re.fullmatch(r'https://github\.com/([A-Za-z0-9][A-Za-z0-9_.-]{0,99})/([A-Za-z0-9][A-Za-z0-9_.-]{0,99}?)(?:\.git)?/?',target)
        if not match:raise ValueError('Only canonical public HTTPS GitHub repository URLs are supported; no credentials, SSH, ports, query or ref suffixes.')
        return 'https://github.com/'+match[1]+'/'+match[2],None
    path=Path(target).absolute()
    if not path.is_dir():raise ValueError('Local repository directory is missing.')
    if path==Path(path.anchor) or len(path.parts)<3:raise ValueError('Select one project directory, not a drive/root.')
    if any(linked(p) for p in [path,*path.parents]):raise ValueError('Linked repository roots are refused.')
    if path.name.lower()=='appdata' or any(p.lower() in {'.ssh','.aws','.azure','.codex','.agents','windows','programdata'} for p in path.parts):
        raise ValueError('Sensitive/system directories are not repository sources.')
    return 'local:'+str(path.resolve()),path.resolve()


def eligible(relative):
    parts=relative.parts
    return (not any(p in SKIP or p.startswith('.') or SENSITIVE.search(p) for p in parts)
        and (relative.suffix.lower() in {'.py','.pyi','.toml','.cfg'} or relative.name in {'requirements.txt','LICENSE','LICENSE.txt','LICENSE.md','COPYING','README.md','README.rst'}))


def acquire(target,vault,cancelled=lambda:False):
    canonical,local=identity(target);vault=Path(vault)
    if any(linked(p) for p in [vault,*vault.parents]):raise ValueError('Repository vault must not be linked.')
    repo_id=hashlib.sha256(canonical.encode()).hexdigest()[:20]
    stage=vault/'snapshots'/repo_id/('pending-'+uuid4().hex);stage.mkdir(parents=True,exist_ok=False)
    records={};diagnostics=[];commit=None;total=0
    def save(relative,raw):
        nonlocal total
        if len(records)>=2000 or len(raw)>1000000 or total+len(raw)>20000000:raise ValueError('Repository exceeds 2,000 files, 1MB/file or 20MB source budget.')
        if cancelled():raise ValueError('Repository acquisition cancelled.')
        destination=stage/'source'/relative;destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(raw);records[relative.as_posix()]=hashlib.sha256(raw).hexdigest();total+=len(raw)
    try:
        if local:
            for folder,dirs,files in os.walk(local,followlinks=False):
                parent=Path(folder)
                dirs[:]=sorted(d for d in dirs if d not in SKIP and not d.startswith('.') and not linked(parent/d))
                for name in sorted(files):
                    path=parent/name;relative=path.relative_to(local)
                    if not eligible(relative):continue
                    if linked(path):diagnostics.append({'file':relative.as_posix(),'error':'Linked file excluded.'});continue
                    if path.stat().st_size>1000000:raise ValueError('Source file exceeds 1MB: '+relative.as_posix())
                    raw=path.read_bytes();save(relative,raw)
                    if hashlib.sha256(path.read_bytes()).hexdigest()!=records[relative.as_posix()]:raise ValueError('Local source changed during snapshot.')
            if (local/'.git').is_dir():
                commit=git(['-C',str(local),'rev-parse','HEAD'],cancelled).decode().strip()
        else:
            clone=vault/'acquisitions'/uuid4().hex;clone.parent.mkdir(parents=True,exist_ok=True)
            git(['clone','--depth','1','--no-tags','--no-checkout','--',canonical,str(clone)],cancelled,120)
            commit=git(['-C',str(clone),'rev-parse','HEAD'],cancelled).decode().strip()
            if not re.fullmatch(r'[a-f0-9]{40,64}',commit):raise ValueError('Git did not return a pinned commit.')
            tree=git(['-C',str(clone),'ls-tree','-rlz',commit],cancelled)
            for row in tree.split(b'\0'):
                if not row:continue
                fields,name=row.split(b'\t',1);mode,kind,oid,size=fields.decode().split()
                relative=Path(name.decode('utf-8'))
                if relative.is_absolute() or '..' in relative.parts or '\\' in name.decode():raise ValueError('Unsafe Git tree path.')
                if not eligible(relative):continue
                if mode not in {'100644','100755'} or kind!='blob':
                    diagnostics.append({'file':relative.as_posix(),'error':'Symlink/submodule excluded.'});continue
                if int(size)>1000000:raise ValueError('Git source file exceeds 1MB.')
                save(relative,git(['-C',str(clone),'cat-file','blob',oid],cancelled))
        revision=hashlib.sha256(json.dumps(records,sort_keys=True).encode()).hexdigest()
        if not any(p.endswith('.py') for p in records):raise ValueError('Repository has no eligible Python source.')
        destination=stage.parent/revision
        if destination.exists():
            # Idempotent snapshots retain both directories; never delete/overwrite.
            existing=json.loads((destination/'snapshot.json').read_text(encoding='utf-8'))
            if existing['hashes']!=records:raise ValueError('Existing snapshot manifest conflicts with pinned source.')
            return existing
        manifest={'version':1,'repo_id':repo_id,'revision':revision,'identity':canonical,'commit':commit,
            'source':str(destination/'source'),'hashes':records,'bytes':total,'diagnostics':diagnostics,
            'trust':'untrusted','provenance':'Git commit and source hashes' if commit else 'Local content hashes; no Git commit'}
        (stage/'snapshot.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        os.replace(stage,destination)
        return manifest
    except Exception:
        # Retain partial acquisitions for inspection. Never recursively delete.
        raise


def verify_snapshot(manifest,vault):
    root=Path(manifest['source']);expected=Path(vault)/'snapshots'/manifest['repo_id']/manifest['revision']/'source'
    if root!=expected or not root.is_dir() or any(linked(p) for p in [root,*root.parents]):raise ValueError('Snapshot location changed or is linked.')
    actual={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and not linked(p)}
    if actual!=manifest['hashes'] or any(linked(p) for p in root.rglob('*')):raise ValueError('Pinned repository source changed; skills quarantined until revalidation.')
    return root
